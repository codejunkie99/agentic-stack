"""Bounded maker/verifier/checker orchestration with durable resumption."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .policy import Decision, check_changed_paths, estimate_tokens, evaluate_breaker
from .process import ProcessResult, run_profile
from .schema import ContractError, load_contracts
from .storage import (
    CheckpointError,
    append_event,
    is_paused,
    load_checkpoint,
    save_checkpoint,
)
from .worktrees import OwnedWorktree, WorktreeError, changed_paths, create_worktree

_DECISION = re.compile(r"^(APPROVE|REJECT|ESCALATE)(?::\s*(.*))?$")
_TERMINAL = {"completed", "cancelled", "exhausted", "audit_failed", "interrupted"}


def new_run_id(now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:12]}"


def contract_digest(contracts: dict[str, dict]) -> str:
    encoded = json.dumps(contracts, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _execution_digest(contracts: dict[str, dict]) -> str:
    return contract_digest({"loop": contracts["loop"], "profiles": contracts["profiles"]})


def parse_checker(output: str) -> tuple[str, str | None]:
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    if not lines:
        return "MALFORMED", "checker returned no decision"
    match = _DECISION.fullmatch(lines[-1])
    if not match:
        return "MALFORMED", "checker returned a malformed decision"
    return match.group(1), match.group(2)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _process_dict(result: ProcessResult) -> dict:
    return asdict(result)


def _effective_limits(contracts: dict[str, dict]) -> dict:
    loop_limits = contracts["loop"]["limits"]
    budget = contracts["budget"]
    names = (
        "max_attempts",
        "max_runtime_seconds",
        "max_output_chars",
        "estimated_token_budget",
        "stagnation_threshold",
    )
    return {name: min(loop_limits[name], budget[name]) for name in names}


def _counters(run: dict) -> dict:
    return run.setdefault(
        "counters",
        {
            "attempts": 0,
            "runtime_seconds": 0.0,
            "output_chars": 0,
            "estimated_tokens": 0,
        },
    )


def _audit_failure(target_root: Path, run: dict, detail: str) -> dict:
    run["status"] = "audit_failed"
    run["reason"] = "event_write_failed"
    run["error"] = detail
    save_checkpoint(target_root, run)
    return run


def _transition(target_root: Path, run: dict, event: str, **fields: object) -> bool:
    save_checkpoint(target_root, run)
    payload = {"run_id": run["run_id"], "loop": run["loop_name"], "event": event}
    payload.update(fields)
    try:
        append_event(target_root, payload)
    except CheckpointError as exc:
        _audit_failure(target_root, run, str(exc))
        return False
    return True


def _worktree_payload(owned: OwnedWorktree) -> dict:
    return {
        "repository": owned.repository,
        "path": str(owned.path),
        "branch": owned.branch,
        "base_commit": owned.base_commit,
    }


def _owned_from_payload(payload: dict) -> OwnedWorktree:
    return OwnedWorktree(
        repository=payload["repository"],
        path=Path(payload["path"]),
        branch=payload["branch"],
        base_commit=payload["base_commit"],
    )


def _approval_required(contracts: dict[str, dict]) -> bool:
    loop = contracts["loop"]
    maker = contracts["profiles"]["profiles"][loop["executor"]]
    return bool(
        (maker["mutates_workspace"] and loop["approval"]["before_first_mutating_run"])
        or ("external_write" in maker["capabilities"] and loop["approval"]["before_external_write"])
    )


def _breaker_decision(target_root: Path, run: dict, contracts: dict[str, dict]) -> Decision:
    counters = _counters(run)
    counters["paused"] = is_paused(target_root)
    return evaluate_breaker(run.get("attempts", []), _effective_limits(contracts), counters)


def _pause(target_root: Path, run: dict, reason: str, detail: str | None = None) -> dict:
    run["status"] = "paused"
    run["reason"] = reason
    if detail:
        run["detail"] = detail
    _transition(target_root, run, "paused", reason=reason)
    return run


def _run_child(
    profile: dict,
    prompt: str,
    target: Path,
    run: dict,
    max_output_chars: int,
) -> ProcessResult:
    values = {
        "prompt": prompt,
        "task": run["task"],
        "target": str(target),
        "run_id": run["run_id"],
        "attempt": str(len(run.get("attempts", [])) + 1),
    }
    return run_profile(profile, values, target, max_output_chars)


def _update_counters(run: dict, result: ProcessResult) -> None:
    counters = _counters(run)
    counters["runtime_seconds"] += result.duration_seconds
    counters["output_chars"] += result.output_chars
    counters["estimated_tokens"] += estimate_tokens(result.stdout, result.stderr)


def _feedback(attempt: dict) -> str:
    verifier = attempt.get("verifier", {})
    checker = attempt.get("checker", {})
    text = verifier.get("stderr") or verifier.get("stdout") or checker.get("reason") or ""
    return str(text)[-2000:]


def _execute(target_root: Path, run: dict, contracts: dict[str, dict], approved: bool) -> dict:
    loop = contracts["loop"]
    profiles = contracts["profiles"]["profiles"]
    if run.get("status") in _TERMINAL:
        return run
    if _approval_required(contracts) and not approved and not run.get("approval_granted"):
        run["status"] = "awaiting_approval"
        _transition(target_root, run, "awaiting_approval", reason="approval_required")
        return run
    run["approval_granted"] = bool(approved or run.get("approval_granted"))

    if loop["isolation"]["mode"] == "worktree":
        if run.get("worktree"):
            owned = _owned_from_payload(run["worktree"])
        else:
            try:
                owned = create_worktree(target_root, loop["name"], run["run_id"])
            except WorktreeError as exc:
                return _pause(target_root, run, "worktree_error", str(exc))
            run["worktree"] = _worktree_payload(owned)
            if not _transition(target_root, run, "worktree_created"):
                return run
        execution_root = owned.path
    else:
        execution_root = Path(target_root).resolve()

    maker = profiles[loop["executor"]]
    checker = profiles.get(loop.get("checker")) if loop.get("checker") else None
    feedback = ""
    while True:
        _counters(run)["attempts"] = len(run.get("attempts", []))
        decision = _breaker_decision(target_root, run, contracts)
        if decision.stop:
            reason = "exhausted" if decision.reason == "attempt_budget" else decision.reason or "paused"
            run["status"] = "exhausted" if reason == "exhausted" else "paused"
            run["reason"] = decision.reason
            _transition(target_root, run, run["status"], reason=decision.reason)
            return run

        attempt_number = len(run.setdefault("attempts", [])) + 1
        instruction = loop["instructions"]["initial"] if attempt_number == 1 else loop["instructions"]["retry"]
        prompt = f"{instruction}\nTASK: {run['task']}"
        if feedback:
            prompt += f"\nVERIFIER FEEDBACK:\n{feedback}"
        attempt = {"attempt": attempt_number, "prompt_summary": prompt}
        try:
            maker_result = _run_child(maker, prompt, execution_root, run, loop["limits"]["max_output_chars"])
        except KeyboardInterrupt:
            run["status"] = "interrupted"
            run["reason"] = "keyboard_interrupt"
            _transition(target_root, run, "interrupted", reason=run["reason"])
            return run
        attempt["maker"] = _process_dict(maker_result)
        _update_counters(run, maker_result)
        if not _transition(target_root, run, "maker_finished", attempt=attempt_number, status=maker_result.status):
            return run
        if maker_result.status == "failed_to_start":
            attempt["outcome"] = "failed_to_start"
            run["attempts"].append(attempt)
            return _pause(target_root, run, "failed_to_start", maker_result.error)

        try:
            paths = changed_paths(owned) if loop["isolation"]["mode"] == "worktree" else []
        except WorktreeError as exc:
            run["attempts"].append(attempt)
            return _pause(target_root, run, "worktree_error", str(exc))
        attempt["changed_paths"] = paths
        path_decision = check_changed_paths(paths, contracts["constraints"])
        if path_decision.stop:
            run["attempts"].append(attempt)
            return _pause(target_root, run, path_decision.reason or "policy", path_decision.detail)

        if _breaker_decision(target_root, run, contracts).stop:
            run["attempts"].append(attempt)
            decision = _breaker_decision(target_root, run, contracts)
            run["status"] = "paused"
            run["reason"] = decision.reason
            _transition(target_root, run, "paused", reason=decision.reason)
            return run

        verification = loop.get("verification")
        try:
            if verification is None:
                verifier_result = ProcessResult("completed", 0, "", "", 0, 0.0)
            else:
                verifier_result = _run_child(
                    {"command": verification["command"], "timeout_seconds": verification["timeout_seconds"]},
                    loop["instructions"]["check"],
                    execution_root,
                    run,
                    loop["limits"]["max_output_chars"],
                )
        except KeyboardInterrupt:
            run["status"] = "interrupted"
            run["reason"] = "keyboard_interrupt"
            _transition(target_root, run, "interrupted", reason=run["reason"])
            return run
        attempt["verifier"] = _process_dict(verifier_result)
        _update_counters(run, verifier_result)
        if verifier_result.status == "failed_to_start":
            attempt["outcome"] = "failed_to_start"
            run["attempts"].append(attempt)
            return _pause(target_root, run, "failed_to_start", verifier_result.error)
        feedback = verifier_result.stderr or verifier_result.stdout
        if verifier_result.exit_code != 0 or verifier_result.timed_out:
            attempt["outcome"] = "failed"
            run["attempts"].append(attempt)
            if not _transition(target_root, run, "verifier_finished", attempt=attempt_number, status="failed"):
                return run
            continue

        if checker is not None:
            try:
                checker_result = _run_child(
                    checker,
                    loop["instructions"]["check"] + f"\nTASK: {run['task']}",
                    execution_root,
                    run,
                    loop["limits"]["max_output_chars"],
                )
            except KeyboardInterrupt:
                run["status"] = "interrupted"
                run["reason"] = "keyboard_interrupt"
                _transition(target_root, run, "interrupted", reason=run["reason"])
                return run
            _update_counters(run, checker_result)
            if checker_result.status == "failed_to_start":
                attempt["checker"] = {
                    **_process_dict(checker_result),
                    "decision": "MALFORMED",
                    "reason": checker_result.error,
                }
                attempt["outcome"] = "failed_to_start"
                run["attempts"].append(attempt)
                return _pause(target_root, run, "failed_to_start", checker_result.error)
            checker_decision, checker_reason = parse_checker(checker_result.stdout)
            attempt["checker"] = {
                **_process_dict(checker_result),
                "decision": checker_decision,
                "reason": checker_reason,
            }
            if checker_decision == "APPROVE":
                attempt["outcome"] = "completed"
                run["attempts"].append(attempt)
                run["status"] = "completed"
                if not _transition(target_root, run, "completed", status="completed"):
                    return run
                return run
            if checker_decision == "ESCALATE":
                attempt["outcome"] = "escalated"
                run["attempts"].append(attempt)
                return _pause(target_root, run, "checker_escalated", checker_reason)
            if checker_decision == "MALFORMED":
                attempt["outcome"] = "escalated"
                run["attempts"].append(attempt)
                return _pause(target_root, run, "checker_malformed", checker_reason)
            feedback = checker_reason or checker_result.stdout
            attempt["outcome"] = "failed"
            run["attempts"].append(attempt)
            if not _transition(target_root, run, "checker_finished", attempt=attempt_number, status="rejected"):
                return run
            continue

        attempt["outcome"] = "completed"
        run["attempts"].append(attempt)
        run["status"] = "completed"
        if not _transition(target_root, run, "completed", status="completed"):
            return run
        return run


def start_run(target_root: Path, loop_name: str, task: str, *, approved: bool = False) -> dict:
    if not isinstance(task, str) or not task.strip():
        raise ContractError("task must be a non-empty string")
    contracts = load_contracts(Path(target_root), loop_name)
    run = {
        "schema_version": 1,
        "run_id": new_run_id(),
        "loop_name": loop_name,
        "task": task,
        "status": "created",
        "created_at": _iso_now(),
        "contract_digest": contract_digest(contracts),
        "execution_digest": _execution_digest(contracts),
        "attempts": [],
        "counters": {"attempts": 0, "runtime_seconds": 0.0, "output_chars": 0, "estimated_tokens": 0},
    }
    if not _transition(Path(target_root), run, "created", status="created"):
        return run
    return _execute(Path(target_root), run, contracts, approved)


def resume_run(target_root: Path, run_id: str, *, approved: bool = False) -> dict:
    target_root = Path(target_root)
    run = load_checkpoint(target_root, run_id)
    if run.get("status") in _TERMINAL:
        return run
    contracts = load_contracts(target_root, run["loop_name"])
    if _execution_digest(contracts) != run.get("execution_digest"):
        return _pause(target_root, run, "contract_mismatch")
    run["contract_digest"] = contract_digest(contracts)
    return _execute(target_root, run, contracts, approved)


def cancel_run(target_root: Path, run_id: str) -> dict:
    target_root = Path(target_root)
    run = load_checkpoint(target_root, run_id)
    if run.get("status") in _TERMINAL:
        return run
    run["status"] = "cancelled"
    run["reason"] = "cancelled_by_user"
    _transition(target_root, run, "cancelled", reason=run["reason"])
    return run

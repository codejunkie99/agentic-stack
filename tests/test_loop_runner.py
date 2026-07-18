from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

import harness_manager.loops.runner as runner
from harness_manager.loops.process import ProcessResult
from harness_manager.loops.runner import (
    cancel_run,
    contract_digest,
    new_run_id,
    parse_checker,
    resume_run,
    start_run,
)
from harness_manager.loops.storage import load_checkpoint


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def install_target(tmp_path: Path, checker_output: str = "APPROVE") -> Path:
    target = tmp_path / "project"
    loops = target / ".agent" / "loops"
    loops.mkdir(parents=True)
    maker = target / "maker.py"
    verifier = target / "verify.py"
    checker = target / "checker.py"
    maker.write_text(
        "import pathlib, sys\n"
        "prompt = sys.argv[1]\n"
        "value = 'green' if 'VERIFIER FEEDBACK' in prompt else 'wrong'\n"
        "pathlib.Path('result.txt').write_text(value)\n",
        encoding="utf-8",
    )
    verifier.write_text(
        "import pathlib, sys\n"
        "p = pathlib.Path('result.txt')\n"
        "ok = p.exists() and p.read_text() == 'green'\n"
        "print('result must equal green') if not ok else print('verified')\n"
        "raise SystemExit(0 if ok else 1)\n",
        encoding="utf-8",
    )
    checker.write_text(f"print({checker_output!r})\n", encoding="utf-8")
    loop = {
        "schema_version": 1,
        "name": "ci-sweeper",
        "description": "test loop",
        "autonomy": "L2",
        "executor": "maker",
        "checker": "checker",
        "state_file": ".agent/runtime/loops/ci-sweeper-state.json",
        "isolation": {"mode": "worktree", "base": "HEAD"},
        "instructions": {
            "initial": "Make the requested change.",
            "retry": "Use the verifier feedback.",
            "check": "Review the result independently.",
        },
        "verification": {"command": [sys.executable, str(verifier)], "timeout_seconds": 5},
        "limits": {
            "max_attempts": 3,
            "max_runtime_seconds": 60,
            "max_output_chars": 10000,
            "estimated_token_budget": 5000,
            "stagnation_threshold": 2,
        },
        "approval": {"before_first_mutating_run": True, "before_external_write": True},
        "tags": ["test"],
    }
    profiles = {
        "schema_version": 1,
        "profiles": {
            "maker": {
                "adapter": "custom",
                "command": [sys.executable, str(maker), "{prompt}"],
                "timeout_seconds": 5,
                "mutates_workspace": True,
                "capabilities": ["workspace_write"],
                "usage_source": "none",
            },
            "checker": {
                "adapter": "custom",
                "command": [sys.executable, str(checker), "{prompt}"],
                "timeout_seconds": 5,
                "mutates_workspace": False,
                "capabilities": [],
                "usage_source": "none",
            },
        },
    }
    constraints = {
        "schema_version": 1,
        "deny_paths": ["auth/**"],
        "allow_paths": [],
        "max_changed_files": 10,
        "external_writes_require_approval": True,
    }
    budget = {"schema_version": 1, **loop["limits"]}
    for name, payload in (
        ("ci-sweeper.json", loop),
        ("harnesses.json", profiles),
        ("constraints.json", constraints),
        ("budget.json", budget),
    ):
        (loops / name).write_text(json.dumps(payload), encoding="utf-8")
    git(target, "init")
    git(target, "config", "user.name", "Loop Test")
    git(target, "config", "user.email", "loop@example.test")
    git(target, "add", ".")
    git(target, "commit", "-m", "fixture")
    return target


def rewrite_json(path: Path, update) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    update(payload)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_feedback_loop_completes_on_second_attempt(tmp_path: Path):
    target = install_target(tmp_path)
    result = start_run(target, "ci-sweeper", "make result equal green", approved=True)
    assert result["status"] == "completed"
    assert len(result["attempts"]) == 2
    assert result["attempts"][0]["verifier"]["exit_code"] != 0
    assert "VERIFIER FEEDBACK" in result["attempts"][1]["prompt_summary"]
    assert result["attempts"][1]["checker"]["decision"] == "APPROVE"
    assert Path(result["worktree"]["path"], "result.txt").read_text() == "green"


def test_initial_approval_pause_then_resume(tmp_path: Path):
    target = install_target(tmp_path)
    paused = start_run(target, "ci-sweeper", "do it")
    assert paused["status"] == "awaiting_approval"
    assert "worktree" not in paused
    completed = resume_run(target, paused["run_id"], approved=True)
    assert completed["status"] == "completed"


def test_checker_reject_exhausts_and_escalate_or_malformed_pause(tmp_path: Path):
    rejected_target = install_target(tmp_path / "reject", "REJECT: needs work")
    rejected = start_run(rejected_target, "ci-sweeper", "do it", approved=True)
    assert rejected["status"] == "exhausted"
    assert rejected["attempts"][-1]["checker"]["decision"] == "REJECT"

    for folder, output, reason in (
        ("escalate", "ESCALATE: human needed", "checker_escalated"),
        ("malformed", "looks fine", "checker_malformed"),
    ):
        target = install_target(tmp_path / folder, output)
        result = start_run(target, "ci-sweeper", "do it", approved=True)
        assert result["status"] == "paused"
        assert result["reason"] == reason


def test_parse_checker_uses_only_last_nonempty_line():
    assert parse_checker("notes\n\nAPPROVE") == ("APPROVE", None)
    assert parse_checker("REJECT: fix tests") == ("REJECT", "fix tests")
    assert parse_checker("not a decision")[0] == "MALFORMED"


def test_cancelled_run_cannot_resume(tmp_path: Path):
    target = install_target(tmp_path)
    paused = start_run(target, "ci-sweeper", "do it")
    cancelled = cancel_run(target, paused["run_id"])
    assert cancelled["status"] == "cancelled"
    assert resume_run(target, paused["run_id"], approved=True)["status"] == "cancelled"


def test_deny_path_escalates_before_verification(tmp_path: Path):
    target = install_target(tmp_path)
    maker = target / "maker.py"
    maker.write_text(
        "import pathlib\npathlib.Path('auth').mkdir()\npathlib.Path('auth/token.py').write_text('x')\n",
        encoding="utf-8",
    )
    git(target, "add", "maker.py")
    git(target, "commit", "-m", "deny writer")
    result = start_run(target, "ci-sweeper", "do it", approved=True)
    assert result["status"] == "paused"
    assert result["reason"] == "deny_path"
    assert "verifier" not in result["attempts"][0]


def test_contract_execution_drift_refuses_resume(tmp_path: Path):
    target = install_target(tmp_path)
    paused = start_run(target, "ci-sweeper", "do it")
    harnesses = target / ".agent" / "loops" / "harnesses.json"
    rewrite_json(harnesses, lambda value: value["profiles"]["maker"]["command"].append("changed"))
    result = resume_run(target, paused["run_id"], approved=True)
    assert result["status"] == "paused"
    assert result["reason"] == "contract_mismatch"


def test_keyboard_interrupt_is_checkpointed(monkeypatch, tmp_path: Path):
    target = install_target(tmp_path)

    def interrupt(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "run_profile", interrupt)
    result = start_run(target, "ci-sweeper", "do it", approved=True)
    assert result["status"] == "interrupted"
    assert load_checkpoint(target, result["run_id"])["status"] == "interrupted"


@pytest.mark.parametrize(
    ("counter", "reason"),
    [("output_chars", "output_budget"), ("estimated_tokens", "token_budget"), ("runtime_seconds", "runtime_budget")],
)
def test_hard_breakers_pause_before_next_phase(monkeypatch, tmp_path: Path, counter: str, reason: str):
    target = install_target(tmp_path)
    loop_path = target / ".agent" / "loops" / "ci-sweeper.json"
    budget_path = target / ".agent" / "loops" / "budget.json"
    field = {"output_chars": "max_output_chars", "estimated_tokens": "estimated_token_budget", "runtime_seconds": "max_runtime_seconds"}[counter]
    rewrite_json(loop_path, lambda value: value["limits"].__setitem__(field, 1))
    rewrite_json(budget_path, lambda value: value.__setitem__(field, 1))
    fake = ProcessResult("completed", 0, "12345", "", 5, 2.0)
    monkeypatch.setattr(runner, "run_profile", lambda *args, **kwargs: fake)
    result = start_run(target, "ci-sweeper", "do it", approved=True)
    assert result["status"] == "paused"
    assert result["reason"] == reason


def test_terminal_event_failure_cannot_report_success(monkeypatch, tmp_path: Path):
    target = install_target(tmp_path)
    real_append = runner.append_event

    def fail_terminal(root, payload):
        if payload.get("event") == "completed":
            raise runner.CheckpointError("event sink failed")
        real_append(root, payload)

    monkeypatch.setattr(runner, "append_event", fail_terminal)
    result = start_run(target, "ci-sweeper", "do it", approved=True)
    assert result["status"] == "audit_failed"
    assert result["reason"] == "event_write_failed"


def test_run_ids_and_contract_digests_are_stable():
    now = datetime(2026, 7, 18, 1, 2, 3, tzinfo=timezone.utc)
    assert new_run_id(now).startswith("20260718T010203Z-")
    assert contract_digest({"b": {"x": 1}, "a": {"y": 2}}) == contract_digest(
        {"a": {"y": 2}, "b": {"x": 1}}
    )

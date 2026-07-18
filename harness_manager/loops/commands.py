"""Nested command-line interface for the loop lifecycle."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from .runner import cancel_run, resume_run, start_run
from .schema import ContractError, load_contracts
from .storage import CheckpointError, list_checkpoints, runtime_dir, set_pause_all
from .worktrees import WorktreeError, cleanup_worktree
from .runner import _owned_from_payload


def _emit(value: object, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True))
    elif isinstance(value, dict):
        reason = value.get("reason")
        suffix = f" reason={reason}" if reason else ""
        print(f"run_id={value.get('run_id', '-') } status={value.get('status', '-')}{suffix}")
    else:
        print(value)


def _result_code(result: dict) -> int:
    status = result.get("status")
    if status == "interrupted":
        return 130
    if status == "failed_to_start" or result.get("reason") == "failed_to_start":
        return 4
    if status == "exhausted":
        return 3
    if status == "audit_failed":
        return 5
    return 0


def cmd_init(ns: argparse.Namespace, stack_root: Path) -> int:
    source = stack_root / ".agent" / "loops"
    if not source.is_dir():
        print(f"error: loop assets not found at {source}", file=sys.stderr)
        return 2
    target = Path(ns.target)
    for source_file in sorted(p for p in source.rglob("*") if p.is_file()):
        relative = source_file.relative_to(source)
        destination = target / ".agent" / "loops" / relative
        if destination.exists() and not ns.force:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_file, destination)
    print(f"initialized loop assets in {target / '.agent' / 'loops'}")
    return 0


def cmd_validate(ns: argparse.Namespace) -> int:
    try:
        contracts = load_contracts(Path(ns.target), ns.loop_name)
    except (ContractError, OSError) as exc:
        if ns.as_json:
            _emit({"status": "invalid", "error": str(exc)}, True)
        else:
            print(f"invalid: {exc}", file=sys.stderr)
        return 2
    result = {
        "status": "valid",
        "loop": contracts["loop"]["name"],
        "autonomy": contracts["loop"]["autonomy"],
        "executor": contracts["loop"]["executor"],
        "checker": contracts["loop"].get("checker"),
    }
    _emit(result, ns.as_json)
    return 0


def cmd_run(ns: argparse.Namespace) -> int:
    try:
        result = start_run(Path(ns.target), ns.loop_name, ns.task, approved=ns.approved)
    except (ContractError, CheckpointError, WorktreeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _emit(result, ns.as_json)
    return _result_code(result)


def cmd_resume(ns: argparse.Namespace) -> int:
    try:
        result = resume_run(Path(ns.target), ns.run_id, approved=ns.approved)
    except (ContractError, CheckpointError, WorktreeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _emit(result, ns.as_json)
    return _result_code(result)


def cmd_status(ns: argparse.Namespace) -> int:
    try:
        runs = list_checkpoints(Path(ns.target))
    except CheckpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if ns.as_json:
        _emit({"runs": runs}, True)
    else:
        for run in runs:
            _emit(run, False)
        if not runs:
            print("no loop runs")
    return 0


def cmd_stop(ns: argparse.Namespace) -> int:
    target = Path(ns.target)
    if ns.all:
        try:
            set_pause_all(target, True)
        except CheckpointError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        _emit({"status": "paused", "reason": "pause_all"}, ns.as_json)
        return 0
    try:
        result = cancel_run(target, ns.run_id)
    except CheckpointError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _emit(result, ns.as_json)
    return 0


def cmd_cleanup(ns: argparse.Namespace) -> int:
    try:
        from .storage import load_checkpoint

        run = load_checkpoint(Path(ns.target), ns.run_id)
        payload = run.get("worktree")
        if not payload:
            print(f"run_id={ns.run_id} status=no_worktree")
            return 0
        if run.get("status") not in {"completed", "cancelled", "exhausted", "paused", "interrupted", "audit_failed"}:
            print("error: cleanup requires a terminal or paused run", file=sys.stderr)
            return 2
        cleanup_worktree(Path(ns.target), _owned_from_payload(payload), allow_dirty=ns.force)
    except (CheckpointError, WorktreeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _emit({"run_id": ns.run_id, "status": "cleaned"}, ns.as_json)
    return 0


def cmd_audit(ns: argparse.Namespace) -> int:
    try:
        contracts = load_contracts(Path(ns.target), ns.loop_name)
        runs = list_checkpoints(Path(ns.target))
    except (ContractError, CheckpointError) as exc:
        print(f"audit failed: {exc}", file=sys.stderr)
        return 2
    loop = contracts["loop"]
    failures = []
    if ns.strict and loop["autonomy"] in {"L2", "L3"}:
        if "verification" not in loop:
            failures.append("verification")
        if not loop.get("checker"):
            failures.append("checker")
        if loop["isolation"]["mode"] != "worktree":
            failures.append("isolation")
        if not contracts.get("constraints") or not contracts.get("budget"):
            failures.append("safety contracts")
        if not runs:
            failures.append("run evidence")
    result = {"status": "ok" if not failures else "failed", "failures": failures, "runs": len(runs)}
    _emit(result, ns.as_json)
    return 0 if not failures else 2


def run(argv: list[str], *, default_target: Path, stack_root: Path) -> int:
    parser = argparse.ArgumentParser(prog="./install.sh loop")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("target", nargs="?", default=str(default_target))
    init.add_argument("--target", dest="target_opt")
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=cmd_init)

    validate = sub.add_parser("validate")
    validate.add_argument("target", nargs="?", default=str(default_target))
    validate.add_argument("--target", dest="target_opt")
    validate.add_argument("--loop", dest="loop_name", default="ci-sweeper")
    validate.add_argument("--json", dest="as_json", action="store_true")
    validate.set_defaults(handler=cmd_validate)

    loop_run = sub.add_parser("run")
    loop_run.add_argument("loop_name")
    loop_run.add_argument("task")
    loop_run.add_argument("target", nargs="?", default=str(default_target))
    loop_run.add_argument("--target", dest="target_opt")
    loop_run.add_argument("--approved", "--yes", action="store_true")
    loop_run.add_argument("--json", dest="as_json", action="store_true")
    loop_run.set_defaults(handler=cmd_run)

    resume = sub.add_parser("resume")
    resume.add_argument("run_id")
    resume.add_argument("target", nargs="?", default=str(default_target))
    resume.add_argument("--target", dest="target_opt")
    resume.add_argument("--approved", "--yes", action="store_true")
    resume.add_argument("--json", dest="as_json", action="store_true")
    resume.set_defaults(handler=cmd_resume)

    status = sub.add_parser("status")
    status.add_argument("target", nargs="?", default=str(default_target))
    status.add_argument("--target", dest="target_opt")
    status.add_argument("--json", dest="as_json", action="store_true")
    status.set_defaults(handler=cmd_status)

    stop = sub.add_parser("stop")
    stop.add_argument("run_id", nargs="?")
    stop.add_argument("target", nargs="?", default=str(default_target))
    stop.add_argument("--target", dest="target_opt")
    stop.add_argument("--all", action="store_true")
    stop.add_argument("--json", dest="as_json", action="store_true")
    stop.set_defaults(handler=cmd_stop)

    cleanup = sub.add_parser("cleanup")
    cleanup.add_argument("run_id")
    cleanup.add_argument("target", nargs="?", default=str(default_target))
    cleanup.add_argument("--target", dest="target_opt")
    cleanup.add_argument("--force", action="store_true")
    cleanup.add_argument("--json", dest="as_json", action="store_true")
    cleanup.set_defaults(handler=cmd_cleanup)

    audit = sub.add_parser("audit")
    audit.add_argument("target", nargs="?", default=str(default_target))
    audit.add_argument("--target", dest="target_opt")
    audit.add_argument("--loop", dest="loop_name", default="ci-sweeper")
    audit.add_argument("--strict", action="store_true")
    audit.add_argument("--json", dest="as_json", action="store_true")
    audit.set_defaults(handler=cmd_audit)

    ns = parser.parse_args(argv)
    if getattr(ns, "target_opt", None):
        ns.target = ns.target_opt
    if ns.command == "init":
        return ns.handler(ns, stack_root)
    return ns.handler(ns)

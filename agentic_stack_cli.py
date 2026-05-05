#!/usr/bin/env python3
"""agentic-stack command front door."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from typing import Any

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, ".agent", "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

import trust_model  # noqa: E402
import trust_tui  # noqa: E402


ADAPTERS = set(trust_model.SUPPORTED_HARNESSES)


def _dump_json(payload: Any) -> int:
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def _project_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--project", default=None, help="Project root to inspect. Defaults to cwd.")


def _print_doctor(payload: dict[str, Any]) -> None:
    print(f"agentic-stack doctor  health={payload['score']}%")
    print(f"project: {payload['project_root']}")
    print("")
    for check in payload["checks"]:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(check["status"], check["status"].upper())
        print(f"{marker:4} {check['label']}: {check['detail']}")
    memory = payload["memory"]
    print("")
    print("memory:")
    print(f"  episodes: {memory['episodic']['count']} ({memory['episodic']['failures']} failures)")
    print(f"  lessons: {memory['lessons']['accepted']} accepted, {memory['lessons']['provisional']} provisional")
    print(
        "  candidates: "
        f"{memory['candidates']['staged']} staged, "
        f"{memory['candidates']['graduated']} graduated, "
        f"{memory['candidates']['rejected']} rejected"
    )
    print("")
    print("next:")
    print("  agentic-stack tui")
    print("  agentic-stack verify --all")
    print("  agentic-stack memory learned")


def _cmd_doctor(args: argparse.Namespace) -> int:
    payload = trust_model.collect_health(args.project)
    if args.json:
        return _dump_json(payload)
    _print_doctor(payload)
    return 1 if any(check["status"] == "fail" for check in payload["checks"]) else 0


def _cmd_tui(args: argparse.Namespace) -> int:
    return trust_tui.run(project_root=args.project, plain=args.plain)


def _print_lessons(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No accepted lessons.")
        return
    for row in rows:
        print(f"{row.get('id', '-')}: {row.get('claim', '')}")
        rationale = row.get("rationale")
        if rationale:
            print(f"  rationale: {rationale}")


def _print_rejected(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No rejected candidates.")
        return
    for row in rows:
        print(f"{row.get('id', '-')}: {row.get('claim', '')}")
        decisions = row.get("decisions") or []
        if decisions:
            latest = decisions[-1]
            reason = latest.get("reason") or latest.get("rationale") or ""
            if reason:
                print(f"  reason: {reason}")


def _print_why(payload: dict[str, Any]) -> None:
    if not payload.get("found"):
        print(f"No lesson or candidate found for {payload.get('identifier')}")
        return
    lesson = payload["lesson"]
    print(f"id: {lesson.get('id', '-')}")
    print(f"claim: {lesson.get('claim', '')}")
    print(f"status: {lesson.get('status', '-')}")
    if lesson.get("reviewer"):
        print(f"reviewer: {lesson.get('reviewer')}")
    if lesson.get("rationale"):
        print(f"rationale: {lesson.get('rationale')}")
    evidence_ids = lesson.get("evidence_ids") or []
    print(f"evidence ids: {', '.join(map(str, evidence_ids)) if evidence_ids else '-'}")
    print(f"matched evidence: {len(payload.get('evidence', []))}")
    for entry in payload.get("evidence", [])[:5]:
        print(f"  - {entry.get('timestamp', '-')}: {entry.get('action', entry.get('reflection', ''))}")


def _cmd_memory(args: argparse.Namespace) -> int:
    if args.memory_cmd == "learned":
        rows = trust_model.memory_learned(args.project)
        if args.json:
            return _dump_json({"lessons": rows})
        _print_lessons(rows)
        return 0
    if args.memory_cmd == "rejected":
        rows = trust_model.memory_rejected(args.project)
        if args.json:
            return _dump_json({"rejected": rows})
        _print_rejected(rows)
        return 0
    if args.memory_cmd == "why":
        payload = trust_model.memory_why(args.identifier, args.project)
        if args.json:
            return _dump_json(payload)
        _print_why(payload)
        return 0 if payload.get("found") else 1
    if args.memory_cmd == "status":
        payload = trust_model.collect_health(args.project)["memory"]
        if args.json:
            return _dump_json(payload)
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0
    raise ValueError(f"unknown memory command: {args.memory_cmd}")


def _print_verify(payload: dict[str, Any]) -> None:
    print(f"agentic-stack verify  project={payload['project_root']}")
    print("")
    print(f"{'harness':<18} {'install':<8} {'memory':<7} {'skills':<7} {'recall':<7} {'reflect':<8} permissions")
    for row in payload["harnesses"]:
        print(
            f"{row['harness']:<18} "
            f"{row['installed']['status']:<8} "
            f"{row['memory']['status']:<7} "
            f"{row['skills']['status']:<7} "
            f"{row['recall']['status']:<7} "
            f"{row['reflect']['status']:<8} "
            f"{row['permissions']['status']}"
        )


def _cmd_verify(args: argparse.Namespace) -> int:
    harness = None if args.all else args.harness
    payload = trust_model.verify_harnesses(harness=harness, project_root=args.project)
    if args.json:
        return _dump_json(payload)
    _print_verify(payload)
    return 0


def _print_team(payload: dict[str, Any]) -> None:
    print(f"team brain: {'present' if payload['exists'] else 'missing'}")
    print(f"path: {payload['path']}")
    for name, meta in payload["files"].items():
        status = "present" if meta["exists"] else "missing"
        print(f"  {name:<24} {status}")


def _cmd_team(args: argparse.Namespace) -> int:
    if args.team_cmd == "status":
        payload = trust_model.team_status(args.project)
        if args.json:
            return _dump_json(payload)
        _print_team(payload)
        return 0
    if args.team_cmd == "init":
        payload = trust_model.team_init(args.project)
        if args.json:
            return _dump_json(payload)
        print(f"team brain initialized: {payload['path']}")
        print(f"created={payload['created']} existing={payload['existing']}")
        return 0
    raise ValueError(f"unknown team command: {args.team_cmd}")


def _dispatch_install(argv: list[str]) -> int:
    script = os.path.join(HERE, "install.sh")
    if not os.path.exists(script):
        print("install.sh not found next to agentic_stack_cli.py", file=sys.stderr)
        return 1
    proc = subprocess.run([script, *argv], cwd=os.getcwd())
    return proc.returncode


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agentic-stack",
        description="Portable memory, skill, and trust layer for coding agents.",
    )
    sub = parser.add_subparsers(dest="command")

    doctor = sub.add_parser("doctor", help="Inspect local .agent health.")
    _project_arg(doctor)
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    doctor.set_defaults(func=_cmd_doctor)

    tui = sub.add_parser("tui", help="Open the read-only Trust Console TUI.")
    _project_arg(tui)
    tui.add_argument("--plain", action="store_true", help="Render plain text instead of curses.")
    tui.set_defaults(func=_cmd_tui)

    memory = sub.add_parser("memory", help="Inspect accepted/rejected memory.")
    memory_sub = memory.add_subparsers(dest="memory_cmd", required=True)
    for name in ("status", "learned", "rejected"):
        p = memory_sub.add_parser(name)
        _project_arg(p)
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=_cmd_memory)
    why = memory_sub.add_parser("why")
    _project_arg(why)
    why.add_argument("--json", action="store_true")
    why.add_argument("identifier")
    why.set_defaults(func=_cmd_memory)

    verify = sub.add_parser("verify", help="Verify harness conformance.")
    _project_arg(verify)
    verify.add_argument("harness", nargs="?", choices=sorted(ADAPTERS), help="Harness to verify.")
    verify.add_argument("--all", action="store_true", help="Verify all supported harnesses.")
    verify.add_argument("--json", action="store_true")
    verify.set_defaults(func=_cmd_verify)

    team = sub.add_parser("team", help="Inspect or initialize team brain files.")
    team_sub = team.add_subparsers(dest="team_cmd", required=True)
    for name in ("status", "init"):
        p = team_sub.add_parser(name)
        _project_arg(p)
        p.add_argument("--json", action="store_true")
        p.set_defaults(func=_cmd_team)

    install = sub.add_parser("install", help="Install an adapter into a project.")
    install.add_argument("install_args", nargs=argparse.REMAINDER)
    install.set_defaults(func=lambda args: _dispatch_install(args.install_args))

    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ADAPTERS:
        return _dispatch_install(argv)
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    if args.command == "verify" and not args.all and not args.harness:
        args.all = True
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())

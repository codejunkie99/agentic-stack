#!/usr/bin/env python3
"""ztk host-neutral policy CLI."""
import argparse
import json
import os
import shlex
import subprocess
import sys


BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))

from ztk_policy import claude_output, codex_output, evaluate_event, load_event  # noqa: E402


def _print_json(payload):
    if payload:
        print(json.dumps(payload))


def cmd_pre_tool(args):
    event = load_event(sys.stdin)
    event.setdefault("host", args.host)
    decision = evaluate_event(event)
    _print_json(decision)
    return 0


def cmd_claude_hook(_args):
    decision = evaluate_event(load_event(sys.stdin))
    _print_json(claude_output(decision))
    return 0


def cmd_codex_hook(_args):
    event = load_event(sys.stdin)
    decision = evaluate_event(event)
    _print_json(codex_output(decision, event))
    return 0


def cmd_exec(args):
    if not args.exec_args:
        print("usage: ztk exec -- <command>", file=sys.stderr)
        return 2

    command = shlex.join(args.exec_args)
    decision = evaluate_event(
        {
            "host": args.host,
            "event": "pre_tool_use",
            "tool": "shell",
            "operation": "run",
            "input": {"command": command},
        }
    )
    if decision["decision"] != "allow":
        print(decision["reason"], file=sys.stderr)
        return 3 if decision["decision"] == "ask" else 2

    return subprocess.run(args.exec_args, check=False).returncode


def cmd_recall(args):
    recall_py = os.path.join(BASE, "tools", "recall.py")
    result = subprocess.run(
        [sys.executable, recall_py, args.intent],
        check=False,
    )
    return result.returncode


def main(argv=None):
    parser = argparse.ArgumentParser(prog="ztk")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    pre_tool = sub.add_parser("pre-tool")
    pre_tool.add_argument("--host", default="generic")
    pre_tool.set_defaults(func=cmd_pre_tool)

    claude_hook = sub.add_parser("claude-hook")
    claude_hook.set_defaults(func=cmd_claude_hook)

    codex_hook = sub.add_parser("codex-hook")
    codex_hook.set_defaults(func=cmd_codex_hook)

    exec_cmd = sub.add_parser("exec")
    exec_cmd.add_argument("--host", default="generic")
    exec_cmd.add_argument("exec_args", nargs=argparse.REMAINDER)
    exec_cmd.set_defaults(func=cmd_exec)

    recall = sub.add_parser("recall")
    recall.add_argument("intent")
    recall.set_defaults(func=cmd_recall)

    args = parser.parse_args(argv)
    if getattr(args, "subcommand", None) == "exec" and args.exec_args[:1] == ["--"]:
        args.exec_args = args.exec_args[1:]
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Host-agent bridge to the external Brain CLI.

This script is copied into installed projects by `agentic-stack upgrade`. It
keeps agent instructions stable even though Brain itself is a separate Rust
binary and release stream.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


INSTALL_HINT = """brain CLI not found.

Install Brain:
  brew install codejunkie99/tap/brain

Or set:
  AGENTIC_STACK_BRAIN_BIN=/path/to/brain
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bridge .agent workflows to Brain.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    sub.add_parser("log")
    doctor = sub.add_parser("doctor")
    doctor.add_argument("--deep", action="store_true")
    ask = sub.add_parser("ask")
    ask.add_argument("query", nargs=argparse.REMAINDER)
    note = sub.add_parser("note")
    note.add_argument("text", nargs=argparse.REMAINDER)
    sub.add_parser("mcp-command")

    args = parser.parse_args(argv)
    brain = _brain_bin()
    if brain is None:
        print(INSTALL_HINT.rstrip(), file=sys.stderr)
        return 2

    if args.command == "status":
        print(f"brain={brain}")
        return _call([brain, "doctor"])
    if args.command == "mcp-command":
        print(f"{brain} serve --mcp")
        return 0
    if args.command == "doctor":
        cmd = [brain, "doctor"]
        if args.deep:
            cmd.append("--deep")
        return _call(cmd)
    if args.command in {"ask", "note"}:
        text = " ".join(getattr(args, "query", None) or getattr(args, "text", [])).strip()
        if not text:
            print(f"error: brain_bridge.py {args.command} requires text", file=sys.stderr)
            return 2
        return _call([brain, args.command, text])
    if args.command == "log":
        return _call([brain, "log"])
    return 2


def _brain_bin() -> str | None:
    configured = os.environ.get("AGENTIC_STACK_BRAIN_BIN")
    if configured:
        return configured
    return shutil.which("brain")


def _call(cmd: list[str]) -> int:
    try:
        return subprocess.run(cmd, cwd=Path.cwd(), check=False).returncode
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

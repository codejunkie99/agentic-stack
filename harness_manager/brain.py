"""Optional integration with the external `brain` CLI.

agentic-stack owns project wiring and `.agent/` infrastructure. The Brain repo
owns the Rust binary, git-backed event store, TUI, and MCP server. This module
bridges the two without vendoring Brain into this Python package.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Callable


INSTALL_HINT = """brain CLI not found.

Install Brain first:
  brew install codejunkie99/tap/brain

From source:
  git clone https://github.com/codejunkie99/brain.git
  cd brain
  cargo install --path crates/brain-cli

Set AGENTIC_STACK_BRAIN_BIN=/path/to/brain if it is not on PATH.
"""


def run(
    args: list[str],
    *,
    target_root: Path | str,
    stack_root: Path | str,
    log: Callable[[str], None] | None = None,
) -> int:
    """Dispatch `agentic-stack brain ...` commands."""
    if log is None:
        log = print
    parser = _parser()
    ns = parser.parse_args(args or ["status"])
    target = Path(getattr(ns, "target", target_root) or target_root)
    brain_bin = _brain_bin()

    if ns.command == "install-help":
        log(INSTALL_HINT.rstrip())
        return 0

    if brain_bin is None:
        print(INSTALL_HINT.rstrip(), file=sys.stderr)
        return 2

    if ns.command == "status":
        return _status(brain_bin, target, log)
    if ns.command == "onboard":
        return _onboard(brain_bin, target, ns)
    if ns.command == "mcp-command":
        log(f"{brain_bin} serve --mcp")
        return 0
    if ns.command in {"ask", "note"}:
        text = " ".join(ns.text).strip()
        if not text:
            print(f"error: brain {ns.command} requires text", file=sys.stderr)
            return 2
        return _call([brain_bin, ns.command, text], cwd=target)
    if ns.command in {"log", "tui"}:
        return _call([brain_bin, ns.command], cwd=target)
    if ns.command == "doctor":
        cmd = [brain_bin, "doctor"]
        if ns.deep:
            cmd.append("--deep")
        return _call(cmd, cwd=target)

    parser.print_help()
    return 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="./install.sh brain",
        description="Bridge agentic-stack projects to the external Brain CLI.",
    )
    sub = parser.add_subparsers(dest="command")

    status = sub.add_parser("status", help="Check Brain CLI and project wiring.")
    status.add_argument("target", nargs="?", default=str(Path.cwd()))

    onboard = sub.add_parser("onboard", help="Run `brain onboard` for a project.")
    onboard.add_argument("target", nargs="?", default=str(Path.cwd()))
    onboard.add_argument("--agents", default="none")
    onboard.add_argument("--yes", action="store_true")
    onboard.add_argument("--reconfigure", action="store_true")

    ask = sub.add_parser("ask", help="Search Brain memory.")
    ask.add_argument("text", nargs=argparse.REMAINDER)
    note = sub.add_parser("note", help="Save a Brain note.")
    note.add_argument("text", nargs=argparse.REMAINDER)

    sub.add_parser("log", help="Show recent Brain notes.")
    doctor = sub.add_parser("doctor", help="Run `brain doctor`.")
    doctor.add_argument("--deep", action="store_true")
    sub.add_parser("tui", help="Open `brain tui`.")
    sub.add_parser("mcp-command", help="Print the stdio MCP command.")
    sub.add_parser("install-help", help="Print Brain install guidance.")
    return parser


def _brain_bin() -> str | None:
    configured = os.environ.get("AGENTIC_STACK_BRAIN_BIN")
    if configured:
        return configured
    return shutil.which("brain")


def _status(brain_bin: str, target: Path, log: Callable[[str], None]) -> int:
    log("agentic-stack brain integration")
    log(f"  brain:   {brain_bin}")
    log(f"  project: {target}")
    log(f"  .agent:  {'present' if (target / '.agent').is_dir() else 'missing'}")
    log("")
    try:
        result = subprocess.run(
            [brain_bin, "doctor"],
            cwd=target,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if result.stdout:
        log(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    return result.returncode


def _onboard(brain_bin: str, target: Path, ns: argparse.Namespace) -> int:
    cmd = [
        brain_bin,
        "onboard",
        "--project-dir",
        str(target),
        "--agents",
        ns.agents,
    ]
    if ns.yes:
        cmd.append("--yes")
    if ns.reconfigure:
        cmd.append("--reconfigure")
    return _call(cmd, cwd=target)


def _call(cmd: list[str], *, cwd: Path) -> int:
    try:
        return subprocess.run(cmd, cwd=cwd, check=False).returncode
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

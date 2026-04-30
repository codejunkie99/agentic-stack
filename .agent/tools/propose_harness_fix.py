#!/usr/bin/env python3
"""Capture a proposed fix to a harness file (skill, agent prompt, protocol)
without mutating the file in place.

When `skill_evolution_mode` in `.agent/config.json` is set to
`"propose_only"`, per-skill self-rewrite hooks and `skillforge` should
route through this tool instead of writing directly to
`.agent/skills/`. The proposal lands in
`.agent/memory/working/HARNESS_FEEDBACK.md`, an append-only log that
can be reviewed and graduated back to the fork in a separate ritual.

Even in `in_place` mode, this tool is the right place to log a
"this prompt or skill is wrong, but I shouldn't mutate it from this
session" observation — for example, when the lock list (CLAUDE.md,
agents/, harness/, AGENTS.md, settings.json, permissions.md)
prevents a direct edit.

Usage:
    python3 .agent/tools/propose_harness_fix.py \\
        --target adapters/claude-code/agents/architect.md \\
        --reason "architect dispatch missed parallel-explore opportunity" \\
        --change "Add explicit instruction: when 2+ independent unknowns, dispatch Explore in parallel"

    python3 .agent/tools/propose_harness_fix.py \\
        --target .agent/skills/planner/SKILL.md \\
        --reason "planner produced unbounded story list — need cap heuristic" \\
        --change "Cap stories per plan at 7; longer plans must split into phases" \\
        --severity 7

The output is a markdown block appended to HARNESS_FEEDBACK.md with
provenance (timestamp, current branch if in a git repo, active_client
if set). Not a git commit; not a file mutation outside the working
memory layer.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

# Resolve .agent/ root from this file's location:
#   __file__  = .agent/tools/propose_harness_fix.py
#   parent    = .agent/tools/
#   parent.parent = .agent/
HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
FEEDBACK_LOG = AGENT_ROOT / "memory" / "working" / "HARNESS_FEEDBACK.md"
CONFIG = AGENT_ROOT / "config.json"


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=AGENT_ROOT.parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "(detached)"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "(no git)"


def _active_client() -> str:
    if not CONFIG.exists():
        return "(none)"
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "(unreadable)"
    return cfg.get("active_client") or "(none)"


def _evolution_mode() -> str:
    if not CONFIG.exists():
        return "(unset)"
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "(unreadable)"
    return cfg.get("skill_evolution_mode") or "in_place"


def _ensure_log_header(path: Path) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "# Harness Feedback Log\n\n"
        "> Append-only log of proposed fixes to harness-territory files\n"
        "> (skills, agent prompts, protocols, CLAUDE.md, settings.json).\n"
        "> Each entry is a proposal, not a mutation. Review in a batch and\n"
        "> graduate the durable ones back to the fork (`agent-stack/`)\n"
        "> on the appropriate branch.\n"
        ">\n"
        "> Newest entries appended at the bottom.\n\n",
        encoding="utf-8",
    )


def append_proposal(
    target: str,
    reason: str,
    change: str,
    severity: int,
    log_path: Path = FEEDBACK_LOG,
) -> None:
    _ensure_log_header(log_path)
    timestamp = dt.datetime.now().isoformat(timespec="seconds")
    branch = _git_branch()
    client = _active_client()
    mode = _evolution_mode()

    block = (
        f"## {timestamp} — `{target}`\n\n"
        f"- **Severity:** {severity}/10\n"
        f"- **Branch:** `{branch}`\n"
        f"- **active_client:** `{client}`\n"
        f"- **skill_evolution_mode:** `{mode}`\n\n"
        f"**Reason:**\n\n{reason.strip()}\n\n"
        f"**Proposed change:**\n\n{change.strip()}\n\n"
        f"---\n\n"
    )
    with log_path.open("a", encoding="utf-8") as f:
        f.write(block)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Append a proposed harness fix to HARNESS_FEEDBACK.md."
    )
    parser.add_argument(
        "--target",
        required=True,
        help="Path (relative to fork root) of the file the fix should apply to.",
    )
    parser.add_argument(
        "--reason",
        required=True,
        help="One- or two-sentence explanation of what's wrong and why this matters.",
    )
    parser.add_argument(
        "--change",
        required=True,
        help="Concrete proposed change. Diff, replacement text, or specific instruction.",
    )
    parser.add_argument(
        "--severity",
        type=int,
        default=5,
        help="Severity 1-10. 1=nice-to-have, 5=meaningful, 10=blocker. Default 5.",
    )
    args = parser.parse_args(argv)

    if not (1 <= args.severity <= 10):
        print(f"error: severity must be 1-10, got {args.severity}", file=sys.stderr)
        return 2

    append_proposal(
        target=args.target,
        reason=args.reason,
        change=args.change,
        severity=args.severity,
    )
    print(f"ok: appended proposal for {args.target} (severity {args.severity}/10)")
    print(f"     → {FEEDBACK_LOG}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

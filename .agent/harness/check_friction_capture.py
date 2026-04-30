#!/usr/bin/env python3
"""Step 8.4 Gap 11 Part B: SessionEnd hook.

Computes (feedback_lines_now - feedback_lines_at_start) + tool_calls_in_session.
If tool_calls > 30 AND delta == 0: emit operator console warning. Otherwise silent.

Observability only — warning goes to operator console; agent has stopped by
the time this fires. Fail-OPEN.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_WORKING = AGENT_ROOT / "memory" / "working"
DEFAULT_EPISODIC = AGENT_ROOT / "memory" / "episodic"
LONG_SESSION_THRESHOLD = 30


def _working_dir() -> Path:
    return Path(os.environ.get("FRICTION_CHECK_WORKING_DIR", DEFAULT_WORKING))


def _episodic_dir() -> Path:
    return Path(os.environ.get("FRICTION_CHECK_EPISODIC_DIR", DEFAULT_EPISODIC))


def _count_tool_calls_since(jsonl_path: Path, started_at: str) -> int:
    if not jsonl_path.exists():
        return 0
    try:
        cutoff = dt.datetime.fromisoformat(started_at)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return 0
    count = 0
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            ts_dt = dt.datetime.fromisoformat(ts)
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if ts_dt >= cutoff:
            count += 1
    return count


def main() -> int:
    working = _working_dir()
    state_path = working / ".session-state.json"
    if not state_path.exists():
        return 0  # first session, no baseline
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    started_at = state.get("session_started_at", "")
    feedback_at_start = int(state.get("feedback_lines_at_start", 0))
    feedback = working / "HARNESS_FEEDBACK.md"
    feedback_now = sum(1 for _ in feedback.open()) if feedback.exists() else 0
    delta = feedback_now - feedback_at_start

    episodic_jsonl = _episodic_dir() / "AGENT_LEARNINGS.jsonl"
    tool_calls = _count_tool_calls_since(episodic_jsonl, started_at)

    if tool_calls > LONG_SESSION_THRESHOLD and delta == 0:
        msg = (
            f"⚠ harness-friction check: this session ran {tool_calls} tool calls "
            f"and captured 0 harness fixes. If that's right, ignore. If not, run "
            f"propose_harness_fix.py before starting your next session."
        )
        print(msg, file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"check_friction_capture error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)

#!/usr/bin/env python3
"""Step 8.4 Gap 11 Part B: SessionStart hook.

Snapshots HARNESS_FEEDBACK.md line count + session-start timestamp into
.session-state.json so check_friction_capture.py (SessionEnd) can compute
the delta. Fail-OPEN on any error.
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


def _working_dir() -> Path:
    return Path(os.environ.get("FRICTION_CHECK_WORKING_DIR", DEFAULT_WORKING))


def main() -> int:
    working = _working_dir()
    working.mkdir(parents=True, exist_ok=True)
    feedback = working / "HARNESS_FEEDBACK.md"
    lines_at_start = sum(1 for _ in feedback.open()) if feedback.exists() else 0
    state = {
        "feedback_lines_at_start": lines_at_start,
        "session_started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    (working / ".session-state.json").write_text(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"init_session_state error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)

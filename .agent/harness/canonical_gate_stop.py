#!/usr/bin/env python3
"""Step 8.4.5 Layer 4: Stop hook for canonical-evidence gate.

Fires before the assistant turn ends. If `.harness-mode.json` is set
(Layer 1 wrote it during UserPromptSubmit), the hook scans the assistant's
outgoing response for a structured Evidence block. Missing/malformed:
blocks the turn until the agent appends one.

Fail-OPEN on any error.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_FLAG_DIR = AGENT_ROOT / "memory" / "working"
FLAG_FILENAME = ".harness-mode.json"

EVIDENCE_BLOCK_RE = re.compile(
    r"\*\*Evidence:?\*\*\s*\n"
    r"(?:.*?)source\b[^:]*:\s*(article|upstream|gstack|gbrain|fork-decisions|none-applies)\b"
    r"(?:.*?)reference\b[^:]*:\s*\S+"
    r"(?:.*?)justification\b[^:]*:\s*\S+",
    re.IGNORECASE | re.DOTALL,
)
QUOTE_FIELD_RE = re.compile(
    r"quote\b[^:]*:\s*\S+", re.IGNORECASE,
)


def _flag_dir() -> Path:
    override = os.environ.get("CANONICAL_GATE_FLAG_DIR")
    if override:
        return Path(override)
    return DEFAULT_FLAG_DIR


def _is_block_valid(text: str) -> bool:
    m = EVIDENCE_BLOCK_RE.search(text)
    if not m:
        return False
    source = m.group(1).lower()
    if source != "none-applies":
        # quote field is required for non-none-applies sources
        block_text = m.group(0)
        if not QUOTE_FIELD_RE.search(block_text):
            return False
    return True


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0

    flag_path = _flag_dir() / FLAG_FILENAME
    if not flag_path.exists():
        return 0  # not in harness mode; allow

    transcript = payload.get("transcript", "") or payload.get("response", "")
    if not transcript:
        return 0  # nothing to scan; fail-open

    if _is_block_valid(transcript):
        return 0

    block_reason = (
        "Response touches harness territory but contains no valid Evidence "
        "block. Append the structured block: **Evidence:** with source, "
        "reference, quote (unless source=none-applies), justification. "
        "See .agent/protocols/canonical-sources.md."
    )
    print(json.dumps({"decision": "block", "reason": block_reason}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"canonical_gate_stop error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)

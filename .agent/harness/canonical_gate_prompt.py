#!/usr/bin/env python3
"""Step 8.4.5 Layer 1: UserPromptSubmit hook for canonical-evidence gate.

Reads user prompt body from stdin (Claude Code hook payload as JSON).
Regex-matches against keyword list. On match: writes `.harness-mode.json`
flag and injects a citation reminder via `additionalContext`. On no match
when flag exists: clears the flag.

Fail-OPEN: any error logs to stderr and exits 0 (allows session to proceed).
"""
from __future__ import annotations

import json
import os
import re
import sys
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
KEYWORDS_FILE = AGENT_ROOT / "protocols" / "harness-territory-keywords.txt"
DEFAULT_FLAG_DIR = AGENT_ROOT / "memory" / "working"
FLAG_FILENAME = ".harness-mode.json"

REMINDER_TEXT = (
    "This message touches harness-primitive territory. Before proposing OR "
    "actioning, run `python .agent/tools/cite_canonical.py` with `--source "
    "--reference --quote --justification`. See "
    "`.agent/protocols/canonical-sources.md` 5-step. Layer 2 will block "
    "harness-territory file writes without a fresh citation; Layer 4 will "
    "block your turn-end without an Evidence block in the response."
)


def _flag_dir() -> Path:
    override = os.environ.get("CANONICAL_GATE_FLAG_DIR")
    if override:
        return Path(override)
    return DEFAULT_FLAG_DIR


def _load_keywords() -> list[re.Pattern]:
    if not KEYWORDS_FILE.exists():
        return []
    patterns = []
    for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line, re.IGNORECASE))
        except re.error:
            print(f"warning: bad regex in keywords: {line}", file=sys.stderr)
    return patterns


def _match_keywords(prompt: str, patterns: list[re.Pattern]) -> list[str]:
    matched = []
    for p in patterns:
        if p.search(prompt):
            matched.append(p.pattern)
    return matched


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        # Fail-open on bad payload
        return 0

    prompt = payload.get("prompt", "") or payload.get("user_prompt", "")
    flag_dir = _flag_dir()
    flag_dir.mkdir(parents=True, exist_ok=True)
    flag_file = flag_dir / FLAG_FILENAME

    patterns = _load_keywords()
    matched = _match_keywords(prompt, patterns)

    if matched:
        flag_file.write_text(json.dumps({
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "matched_keywords": matched,
        }, indent=2))
        print(json.dumps({"additionalContext": REMINDER_TEXT}))
    else:
        if flag_file.exists():
            flag_file.unlink()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"canonical_gate_prompt error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)

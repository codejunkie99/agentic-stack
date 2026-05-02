#!/usr/bin/env python3
"""Step 8.4.5 Layer 2: PreToolUse hook for Edit/Write/MultiEdit.

Reads tool call payload from stdin. If the target file_path matches any
harness-territory glob, requires a fresh `.canonical-citation.json`
(TTL 30 min). Without it, returns block decision.

Fail-OPEN on any error.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
REPO_ROOT = AGENT_ROOT.parent
PATHS_FILE = AGENT_ROOT / "protocols" / "harness-territory-paths.json"
DEFAULT_CITATION_DIR = AGENT_ROOT / "memory" / "working"
CITATION_FILENAME = ".canonical-citation.json"
TTL_MINUTES = 30

LESSONS_PIPELINE_PATHS = (
    ".agent/memory/semantic/LESSONS.md",
    ".agent/memory/semantic/lessons.jsonl",
)
GRADUATION_WRITER_ENV = "HARNESS_GRADUATION_WRITER"


def _citation_dir() -> Path:
    override = os.environ.get("CANONICAL_CITATION_DIR")
    if override:
        return Path(override)
    return DEFAULT_CITATION_DIR


def _load_globs() -> list[str]:
    if not PATHS_FILE.exists():
        return []
    try:
        data = json.loads(PATHS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data.get("globs", [])


def _normalize_path(p: str) -> str:
    """Reduce file_path to repo-relative POSIX form for glob matching."""
    pp = Path(p).resolve()
    try:
        rel = pp.relative_to(REPO_ROOT)
        return str(rel).replace(os.sep, "/")
    except ValueError:
        return str(pp).replace(os.sep, "/")


def _is_harness_territory(file_path: str, globs: list[str]) -> bool:
    norm = _normalize_path(file_path)
    return any(fnmatch.fnmatch(norm, g) for g in globs)


def _is_lessons_pipeline_path(file_path: str) -> bool:
    return _normalize_path(file_path) in LESSONS_PIPELINE_PATHS


def _lessons_pipeline_block_reason(file_path: str) -> str:
    return (
        f"pipeline-discipline block: `{file_path}` is durable lesson storage. "
        "Direct edits forbidden — graduation pipeline is the only legitimate writer. "
        "Routing:\n"
        "  • harness-shape fix (skill/agent/protocol/hook): "
        "python3 .agent/tools/propose_harness_fix.py --target <file> --reason ... --change ...\n"
        "  • behavioral lesson: emerges from episodic — log via tool calls, "
        "let auto_dream cluster, then graduate.py promotes. Single observations "
        "are not graduate-worthy.\n"
        "  • graduate an existing candidate: python3 .agent/memory/graduate.py\n"
        f"To bypass intentionally (graduate.py / auto-render only), set {GRADUATION_WRITER_ENV}=1. "
        "See .agent/protocols/canonical-sources.md."
    )


def _is_citation_fresh(citation_path: Path) -> tuple[bool, str]:
    if not citation_path.exists():
        return False, "no citation file present"
    try:
        data = json.loads(citation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "citation file unreadable"
    ts = data.get("timestamp")
    if not ts:
        return False, "citation missing timestamp"
    try:
        ts_dt = dt.datetime.fromisoformat(ts)
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return False, "citation timestamp unparseable"
    age = dt.datetime.now(dt.timezone.utc) - ts_dt
    if age.total_seconds() > TTL_MINUTES * 60:
        return False, f"citation stale (age {int(age.total_seconds()/60)}min, ttl {TTL_MINUTES}min)"
    return True, ""


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0  # fail-open

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return 0  # not our matcher

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    if _is_lessons_pipeline_path(file_path):
        if os.environ.get(GRADUATION_WRITER_ENV) == "1":
            return 0  # allow — graduate.py / auto-render
        print(json.dumps({
            "decision": "block",
            "reason": _lessons_pipeline_block_reason(file_path),
        }))
        return 0

    globs = _load_globs()
    if not _is_harness_territory(file_path, globs):
        return 0  # allow non-harness writes

    citation_path = _citation_dir() / CITATION_FILENAME
    fresh, reason = _is_citation_fresh(citation_path)
    if fresh:
        return 0  # allow

    block_reason = (
        f"harness-primitive write to `{file_path}` blocked ({reason}). "
        f"Cite canonical evidence first: python .agent/tools/cite_canonical.py "
        f"--source <article|upstream|gstack|gbrain|fork-decisions|none-applies> "
        f"--reference <line/path/sha> --quote <verbatim> --justification <text>. "
        f"See .agent/protocols/canonical-sources.md."
    )
    print(json.dumps({"decision": "block", "reason": block_reason}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"canonical_gate_write error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)

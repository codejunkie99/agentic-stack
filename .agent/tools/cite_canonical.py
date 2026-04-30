#!/usr/bin/env python3
"""Record a canonical-evidence citation for harness-territory work.

Step 8.4.5 Layer 3. Writes `.agent/memory/working/.canonical-citation.json`
which Layer 2 (PreToolUse Edit/Write hook) checks for freshness (TTL 30 min)
before allowing harness-territory file writes.

Sources:
  article         — examples/agentic-stack-resource/agentic-stack-source-article.md
  upstream        — git show upstream/master:<path>
  gstack          — pattern from garrytan/gstack
  gbrain          — pattern from garrytan/gbrain
  fork-decisions  — .agent/memory/semantic/DECISIONS.md
  none-applies    — fork extension; canonical does not cover this case
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_CITATION_DIR = AGENT_ROOT / "memory" / "working"
CITATION_FILENAME = ".canonical-citation.json"
TTL_MINUTES = 30
SOURCES = ("article", "upstream", "gstack", "gbrain", "fork-decisions", "none-applies")
ARTICLE_PATH = AGENT_ROOT.parent / "examples/agentic-stack-resource/agentic-stack-source-article.md"
DECISIONS_PATH = AGENT_ROOT / "memory/semantic/DECISIONS.md"


def _citation_dir() -> Path:
    override = os.environ.get("CANONICAL_CITATION_DIR")
    if override:
        return Path(override)
    return DEFAULT_CITATION_DIR


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=AGENT_ROOT.parent, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return out or "(detached)"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "(no git)"


def _validate_none_applies(justification: str) -> tuple[bool, str]:
    if len(justification) < 40:
        return False, "justification must be >=40 chars for source=none-applies"
    valid_prefixes = ("canonical-uncovered because:", "fork-extension because:")
    if not any(justification.lower().startswith(p) for p in valid_prefixes):
        return False, (
            "justification must start with 'canonical-uncovered because:' or "
            "'fork-extension because:' for source=none-applies"
        )
    return True, ""


def _flexible_substring_in(haystack: str, needle: str) -> bool:
    """Whitespace-flexible, case-insensitive substring check."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    return norm(needle) in norm(haystack)


def _validate_article(reference: str, quote: str) -> tuple[bool, str]:
    if not re.match(r"^lines?\s+\d+(-\d+)?$", reference, re.IGNORECASE):
        return False, "reference must match 'line N' or 'lines N-M' for source=article"
    if not ARTICLE_PATH.exists():
        return False, f"article not found at {ARTICLE_PATH}"
    text = ARTICLE_PATH.read_text(encoding="utf-8", errors="replace")
    if not _flexible_substring_in(text, quote):
        return False, "quote not found in article (whitespace-flexible substring check failed)"
    return True, ""


def _validate_upstream(reference: str, quote: str) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(
            ["git", "show", f"upstream/master:{reference}"],
            cwd=AGENT_ROOT.parent, stderr=subprocess.DEVNULL, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        return False, f"git show upstream/master:{reference} failed: {e}"
    if not _flexible_substring_in(out, quote):
        return False, f"quote not found in upstream/master:{reference}"
    return True, ""


def _validate_fork_decisions(reference: str, quote: str) -> tuple[bool, str]:
    if not DECISIONS_PATH.exists():
        return False, f"DECISIONS.md not found at {DECISIONS_PATH}"
    text = DECISIONS_PATH.read_text(encoding="utf-8", errors="replace")
    if not _flexible_substring_in(text, quote):
        return False, "quote not found in fork DECISIONS.md"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Record a canonical-evidence citation for harness-territory work."
    )
    p.add_argument("--source", required=True, choices=SOURCES)
    p.add_argument("--reference", default="")
    p.add_argument("--quote", default="")
    p.add_argument("--justification", required=True)
    p.add_argument("--topic", default="")
    args = p.parse_args(argv)

    if args.source == "none-applies":
        ok, msg = _validate_none_applies(args.justification)
        if not ok:
            print(f"error: {msg}", file=sys.stderr)
            return 2
    else:
        if not args.reference:
            print(f"error: --reference required for source={args.source}", file=sys.stderr)
            return 2
        if not args.quote:
            print(f"error: --quote required for source={args.source}", file=sys.stderr)
            return 2
        if args.source == "article":
            ok, msg = _validate_article(args.reference, args.quote)
        elif args.source == "upstream":
            ok, msg = _validate_upstream(args.reference, args.quote)
        elif args.source == "fork-decisions":
            ok, msg = _validate_fork_decisions(args.reference, args.quote)
        else:
            ok, msg = True, ""  # gstack / gbrain — no fetcher in v1
        if not ok:
            print(f"error: {msg}", file=sys.stderr)
            return 2

    citation_dir = _citation_dir()
    citation_dir.mkdir(parents=True, exist_ok=True)
    citation = {
        "topic": args.topic,
        "source": args.source,
        "reference": args.reference,
        "quote": args.quote,
        "justification": args.justification,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "branch": _git_branch(),
        "ttl_minutes": TTL_MINUTES,
    }
    (citation_dir / CITATION_FILENAME).write_text(json.dumps(citation, indent=2))
    print(f"ok: citation recorded; harness-territory writes allowed for next {TTL_MINUTES} min.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

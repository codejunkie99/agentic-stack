#!/usr/bin/env python3
"""Phase H: Cross-install lesson + DECISIONS graduation (target → fork).

Operates from the FORK side; reads target's semantic memory; surfaces
target-only entries via interactive prompts; appends approved entries
to fork's semantic memory with provenance.

Anti-mistakes:
- Never auto-merge (interactive y/n + --rationale required for lessons).
- Hash dedup: pattern_id collision → auto-skip.
- Engagement-specificity heuristic: lessons mentioning client paths get
  flagged; require explicit y to override.
- Recommends `/regenerate-decisions` after DECISIONS appends to honor
  canonical's regenerated-not-edited rule.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_FORK_ROOT = AGENT_ROOT.parent

_DECISIONS_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}): (.+)$", re.MULTILINE)


def _fork_root() -> Path:
    override = os.environ.get("HARNESS_GRADUATE_FORK_ROOT")
    return Path(override) if override else DEFAULT_FORK_ROOT


def _load_lessons(jsonl_path: Path) -> list[dict]:
    if not jsonl_path.exists():
        return []
    out = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _engagement_specific(lesson: dict, target_root: Path) -> bool:
    text = (lesson.get("claim", "") + " " + " ".join(lesson.get("conditions", []))).lower()
    client_dir = target_root / ".agent/memory/client"
    if client_dir.exists():
        for slug_dir in client_dir.iterdir():
            if slug_dir.is_dir() and slug_dir.name.lower() in text:
                return True
    return False


def _prompt_y_n_skip(message: str, dry_run: bool) -> str:
    if dry_run:
        return "skip"
    while True:
        sys.stdout.write(f"{message} [y/n/skip]: ")
        sys.stdout.flush()
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            return "skip"
        if not line:
            return "skip"
        v = line.strip().lower()
        if v in ("y", "n", "skip"):
            return v
        sys.stdout.write("(unrecognized; type y, n, or skip)\n")


def _prompt_rationale(dry_run: bool) -> str:
    if dry_run:
        return "(dry-run)"
    while True:
        sys.stdout.write("rationale (required, >=20 chars): ")
        sys.stdout.flush()
        line = sys.stdin.readline().strip()
        if len(line) >= 20:
            return line


def _parse_decisions(text: str) -> list[dict]:
    """Parse DECISIONS.md by heading. Returns list of {date, title, heading, body}."""
    out = []
    matches = list(_DECISIONS_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        out.append({
            "date": m.group(1),
            "title": m.group(2).strip(),
            "heading": m.group(0),
            "body": text[start:end],
        })
    return out


def _graduate_lessons(target_root: Path, fork_root: Path,
                     target_slug: str, dry_run: bool) -> dict:
    target_lessons = _load_lessons(target_root / ".agent/memory/semantic/lessons.jsonl")
    fork_lessons_path = fork_root / ".agent/memory/semantic/lessons.jsonl"
    fork_lessons_path.parent.mkdir(parents=True, exist_ok=True)
    fork_lessons = _load_lessons(fork_lessons_path)
    fork_ids = {l.get("id") for l in fork_lessons if l.get("id")}

    counts = {"graduated": 0, "skipped": 0, "dedup_skipped": 0, "rejected": 0}

    for lesson in target_lessons:
        lid = lesson.get("id", "")
        if lid in fork_ids:
            print(f"  [dedup] {lid} already in fork — auto-skip")
            counts["dedup_skipped"] += 1
            continue

        flagged = _engagement_specific(lesson, target_root)
        flag_label = "[engagement-specific?]" if flagged else ""

        if dry_run:
            label = "WOULD-FLAG-ENG-SPECIFIC" if flagged else "WOULD-GRADUATE"
            print(f"  [{label}] {lid}: {lesson.get('claim','')[:80]}")
            counts["graduated"] += 1
            continue

        msg = (
            f"\nlesson {lid} {flag_label}\n"
            f"  claim: {lesson.get('claim','')}\n"
            f"  conditions: {lesson.get('conditions',[])}\n"
            f"graduate?"
        )
        choice = _prompt_y_n_skip(msg, dry_run)
        if choice == "y":
            rationale = _prompt_rationale(dry_run)
            entry = dict(lesson)
            entry["graduated_from"] = target_slug
            entry["graduated_on"] = dt.date.today().isoformat()
            entry["graduation_rationale"] = rationale
            with fork_lessons_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            counts["graduated"] += 1
        elif choice == "n":
            counts["rejected"] += 1
        else:
            counts["skipped"] += 1

    return counts


def _graduate_decisions(target_root: Path, fork_root: Path,
                       target_slug: str, dry_run: bool) -> dict:
    target_md = target_root / ".agent/memory/semantic/DECISIONS.md"
    fork_md = fork_root / ".agent/memory/semantic/DECISIONS.md"
    if not target_md.exists():
        print("  (target has no DECISIONS.md)")
        return {"graduated": 0, "skipped": 0, "dedup_skipped": 0, "rejected": 0}

    target_entries = _parse_decisions(target_md.read_text(encoding="utf-8"))
    fork_text = fork_md.read_text(encoding="utf-8") if fork_md.exists() else ""
    fork_entries = _parse_decisions(fork_text)
    fork_keys = {(e["date"], e["title"]) for e in fork_entries}

    counts = {"graduated": 0, "skipped": 0, "dedup_skipped": 0, "rejected": 0}

    for entry in target_entries:
        key = (entry["date"], entry["title"])
        if key in fork_keys:
            print(f"  [dedup] '{entry['title']}' (target {entry['date']}) already in fork — auto-skip")
            counts["dedup_skipped"] += 1
            continue

        if dry_run:
            print(f"  [WOULD-GRADUATE] {entry['heading']}")
            counts["graduated"] += 1
            continue

        msg = (
            f"\nDECISIONS entry: {entry['date']}: {entry['title']}\n"
            f"  body preview: {entry['body'][:200]}...\n"
            f"graduate?"
        )
        choice = _prompt_y_n_skip(msg, dry_run)
        if choice == "y":
            provenance = f"\n> Graduated from {target_slug} on {dt.date.today().isoformat()}.\n"
            body = entry["body"]
            heading_end = body.find("\n") + 1
            graduated_block = body[:heading_end] + provenance + body[heading_end:]
            fork_md.parent.mkdir(parents=True, exist_ok=True)
            existing = fork_md.read_text(encoding="utf-8") if fork_md.exists() else ""
            with fork_md.open("a", encoding="utf-8") as f:
                if existing and not existing.endswith("\n\n"):
                    f.write("\n")
                f.write(graduated_block)
            counts["graduated"] += 1
        elif choice == "n":
            counts["rejected"] += 1
        else:
            counts["skipped"] += 1

    if counts["graduated"] > 0:
        print(
            f"\nRECOMMENDATION: appended {counts['graduated']} DECISIONS entries. "
            f"Consider running '/regenerate-decisions' on fork to re-derive from "
            f"updated LESSONS + episodic. Direct append is for high-value entries "
            f"that don't need re-derivation; bulk additions warrant re-derivation."
        )

    return counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cross-install lesson + DECISIONS graduation.")
    p.add_argument("target_path", help="Path to target install root")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--lessons-only", action="store_true")
    p.add_argument("--target-slug", default="")
    args = p.parse_args(argv)

    target_root = Path(args.target_path).resolve()
    if not target_root.exists():
        print(f"error: target path does not exist: {target_root}", file=sys.stderr)
        return 2
    target_slug = args.target_slug or target_root.name
    fork_root = _fork_root()

    print(f"=== harness-graduate: {target_slug} → fork ===\n")
    print("--- LESSONS ---")
    lesson_counts = _graduate_lessons(target_root, fork_root, target_slug, args.dry_run)
    print(
        f"\nlessons: graduated={lesson_counts['graduated']}, skipped={lesson_counts['skipped']}, "
        f"dedup-skipped={lesson_counts['dedup_skipped']}, rejected={lesson_counts['rejected']}"
    )

    if args.lessons_only:
        return 0

    print("\n--- DECISIONS ---")
    dec_counts = _graduate_decisions(target_root, fork_root, target_slug, args.dry_run)
    print(
        f"\ndecisions: graduated={dec_counts['graduated']}, skipped={dec_counts['skipped']}, "
        f"dedup-skipped={dec_counts['dedup_skipped']}, rejected={dec_counts['rejected']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

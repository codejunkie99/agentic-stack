#!/usr/bin/env python3
"""Smart-merge fork's harness gate hooks into target's .claude/settings.json.

Step 8.6 sync extension. sync-target.sh preserves settings.json wholesale
to avoid clobbering target permissions/customizations, but that means
new fork-side gates never reach existing targets. This tool does the
narrow merge: add missing harness gate hooks (anything in
`.agent/harness/`) to the target's settings.json under the matching
trigger, preserving target's permissions block + any non-harness hooks.

Usage:
    python3 merge_target_settings.py <target_dir> [--dry-run] [--yes]

Idempotent: re-run does nothing when target already has all fork hooks.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FORK_ROOT = HERE.parent.parent
HOOK_RE = re.compile(r"\.agent/harness/[A-Za-z_]+\.py")


def _harness_hook_paths(hook_entries: list) -> list[str]:
    out = []
    for entry in hook_entries:
        for h in entry.get("hooks", []):
            cmd = h.get("command", "")
            for m in HOOK_RE.findall(cmd):
                out.append(m)
    return out


def _build_hook_entry(script: str) -> dict:
    return {
        "type": "command",
        "command": f'python3 "$CLAUDE_PROJECT_DIR/{script}"',
    }


def merge(fork_settings: dict, target_settings: dict) -> tuple[dict, list[str]]:
    """Return (merged_settings, change_log)."""
    fork_hooks = fork_settings.get("hooks", {})
    target_hooks = dict(target_settings.get("hooks", {}))
    added = []
    for trigger, fork_entries in fork_hooks.items():
        fork_paths = _harness_hook_paths(fork_entries)
        if not fork_paths:
            continue
        target_entries = target_hooks.get(trigger, [])
        target_paths = _harness_hook_paths(target_entries)
        missing = [p for p in fork_paths if p not in target_paths]
        if not missing:
            continue
        if target_entries:
            wildcard_entry = next(
                (e for e in target_entries if e.get("matcher") == "*"), None
            )
            if wildcard_entry is None:
                wildcard_entry = {"matcher": "*", "hooks": []}
                target_entries.append(wildcard_entry)
            for p in missing:
                wildcard_entry["hooks"].append(_build_hook_entry(p))
                added.append(f"{trigger}: + {p}")
        else:
            new_entry = {
                "matcher": "*",
                "hooks": [_build_hook_entry(p) for p in missing],
            }
            target_hooks[trigger] = [new_entry]
            for p in missing:
                added.append(f"{trigger}: + {p} (new trigger)")
    merged = dict(target_settings)
    merged["hooks"] = target_hooks
    return merged, added


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target_dir", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    ap.add_argument("--fork-root", type=Path, default=FORK_ROOT)
    args = ap.parse_args(argv)

    fork_settings_path = args.fork_root / ".claude/settings.json"
    target_settings_path = args.target_dir / ".claude/settings.json"

    if not fork_settings_path.is_file():
        print(f"error: fork settings not found at {fork_settings_path}", file=sys.stderr)
        return 1
    if not target_settings_path.is_file():
        print(f"error: target settings not found at {target_settings_path}", file=sys.stderr)
        return 1

    fork_settings = json.loads(fork_settings_path.read_text(encoding="utf-8"))
    target_settings = json.loads(target_settings_path.read_text(encoding="utf-8"))

    merged, changes = merge(fork_settings, target_settings)

    if not changes:
        print("no changes — target already has all fork harness hooks")
        return 0

    print(f"target: {target_settings_path}")
    print("changes:")
    for c in changes:
        print(f"  {c}")

    if args.dry_run:
        print("(dry-run — no write)")
        return 0

    if not args.yes:
        try:
            resp = input("apply? [y/N] ").strip().lower()
        except EOFError:
            resp = ""
        if resp != "y":
            print("aborted")
            return 0

    target_settings_path.write_text(json.dumps(merged, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {target_settings_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

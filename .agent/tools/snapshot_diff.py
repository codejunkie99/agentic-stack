#!/usr/bin/env python3
"""Capture install-time snapshot of harness-evolvable surfaces; diff later.

Two modes:

    --snapshot  : Capture a fingerprint of every file under
                  .agent/skills/, .claude/agents/, .claude/agent-memory/,
                  .agent/skills/_index.md, .agent/skills/_manifest.jsonl
                  to .agent/memory/working/install_snapshot.json.
                  Run by post_install at end of install. Idempotent —
                  re-running just refreshes the snapshot to current state.

    --diff      : Compare current state against the snapshot. Writes a
                  structured report to
                  .agent/memory/working/HARNESS_DIFF.md. Reports added /
                  modified / deleted files with content diffs for text
                  files. Run after a dry-run or any session where you
                  want to see what evolved in place.

The snapshot is the basis for `harness-graduate.py` (Step 8.4): the
diff identifies candidate improvements that emerged in this install
and could be propagated back to fork. Snapshot/diff itself does no
graduation — it just makes the change set visible.
"""
from __future__ import annotations

import argparse
import datetime as dt
import difflib
import hashlib
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent  # .agent/

# When run from inside an install, AGENT_ROOT.parent is the install root.
# Snapshot tracks files relative to install root.
INSTALL_ROOT = AGENT_ROOT.parent

SNAPSHOT_PATH = AGENT_ROOT / "memory" / "working" / "install_snapshot.json"
DIFF_REPORT = AGENT_ROOT / "memory" / "working" / "HARNESS_DIFF.md"

# Surfaces we track. Each entry: (relative path from install root, kind)
# kind == "dir": recurse, snapshot every file under it
# kind == "file": snapshot just that one file
TRACKED = [
    (".agent/skills", "dir"),
    (".claude/agents", "dir"),
    (".claude/agent-memory", "dir"),
]


def _file_fingerprint(path: Path) -> dict:
    """Hash + content for a single file. Content is captured for text
    files so the diff can show what changed; binaries get hash only."""
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    out = {"sha256": sha, "size": len(raw)}
    try:
        text = raw.decode("utf-8")
        out["content"] = text
        out["is_text"] = True
    except UnicodeDecodeError:
        out["is_text"] = False
    return out


def _walk_dir(install_root: Path, rel_dir: str) -> dict[str, dict]:
    base = install_root / rel_dir
    if not base.is_dir():
        return {}
    out = {}
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(install_root).as_posix()
        out[rel] = _file_fingerprint(path)
    return out


def _walk_file(install_root: Path, rel_file: str) -> dict[str, dict]:
    p = install_root / rel_file
    if not p.is_file():
        return {}
    return {rel_file: _file_fingerprint(p)}


def take_snapshot(install_root: Path = INSTALL_ROOT, snapshot_path: Path = SNAPSHOT_PATH) -> dict:
    """Capture the current state of all tracked surfaces.

    The snapshot embeds full text content for text files (skills are
    small markdown — fits comfortably). Binaries get hash + size only.
    """
    files: dict[str, dict] = {}
    for rel, kind in TRACKED:
        if kind == "dir":
            files.update(_walk_dir(install_root, rel))
        elif kind == "file":
            files.update(_walk_file(install_root, rel))

    snapshot = {
        "schema_version": 1,
        "captured_at": dt.datetime.now().isoformat(timespec="seconds"),
        "install_root": str(install_root),
        "tracked_count": len(files),
        "files": files,
    }
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return snapshot


def _current_state(install_root: Path) -> dict[str, dict]:
    files: dict[str, dict] = {}
    for rel, kind in TRACKED:
        if kind == "dir":
            files.update(_walk_dir(install_root, rel))
        elif kind == "file":
            files.update(_walk_file(install_root, rel))
    return files


def _format_text_diff(rel_path: str, old: str, new: str) -> str:
    diff_lines = list(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"a/{rel_path}",
            tofile=f"b/{rel_path}",
            n=3,
        )
    )
    if not diff_lines:
        return ""
    return "```diff\n" + "".join(diff_lines).rstrip() + "\n```\n"


def diff_against_snapshot(
    install_root: Path = INSTALL_ROOT,
    snapshot_path: Path = SNAPSHOT_PATH,
    diff_report: Path = DIFF_REPORT,
) -> dict:
    """Compare current state vs snapshot. Write report. Return summary dict."""
    if not snapshot_path.exists():
        return {
            "status": "no_snapshot",
            "stderr": f"snapshot not found at {snapshot_path}; run --snapshot first",
        }
    snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    snapshot_files: dict[str, dict] = snapshot.get("files", {})

    current = _current_state(install_root)

    added = sorted(set(current) - set(snapshot_files))
    removed = sorted(set(snapshot_files) - set(current))
    modified = sorted(
        rel for rel in set(current) & set(snapshot_files)
        if current[rel]["sha256"] != snapshot_files[rel]["sha256"]
    )

    captured_at = snapshot.get("captured_at", "(unknown)")
    now = dt.datetime.now().isoformat(timespec="seconds")

    body: list[str] = [
        "# Harness Diff Report",
        "",
        f"- **Snapshot taken:** `{captured_at}`",
        f"- **Diff generated:** `{now}`",
        f"- **Install root:** `{install_root}`",
        f"- **Added:** {len(added)} | **Modified:** {len(modified)} | **Removed:** {len(removed)}",
        "",
        "> Surfaces tracked: `.agent/skills/**`, `.claude/agents/**`, `.claude/agent-memory/**`.",
        "> Snapshot is captured at install time by `post_install.take_install_snapshot`.",
        "> Re-snapshot anytime by running `--snapshot`.",
        "",
    ]

    if not (added or modified or removed):
        body.append("**No changes since install.**\n")
    else:
        if added:
            body.append("## Added\n")
            for rel in added:
                fp = current[rel]
                body.append(f"- `{rel}` ({fp['size']} bytes)")
                if fp.get("is_text"):
                    body.append("  ```")
                    text = fp["content"]
                    snippet = "\n".join(text.splitlines()[:30])
                    body.append(snippet)
                    if len(text.splitlines()) > 30:
                        body.append(f"  ... ({len(text.splitlines()) - 30} more lines)")
                    body.append("  ```")
            body.append("")

        if modified:
            body.append("## Modified\n")
            for rel in modified:
                old = snapshot_files[rel]
                new = current[rel]
                body.append(f"### `{rel}`")
                body.append("")
                if old.get("is_text") and new.get("is_text"):
                    body.append(_format_text_diff(rel, old["content"], new["content"]))
                else:
                    body.append(
                        f"- binary or non-text content; sha changed "
                        f"`{old['sha256'][:12]}` → `{new['sha256'][:12]}`"
                    )
                    body.append("")

        if removed:
            body.append("## Removed\n")
            for rel in removed:
                body.append(f"- `{rel}`")
            body.append("")

    diff_report.parent.mkdir(parents=True, exist_ok=True)
    diff_report.write_text("\n".join(body) + "\n", encoding="utf-8")

    return {
        "status": "ok",
        "added": len(added),
        "modified": len(modified),
        "removed": len(removed),
        "report": str(diff_report),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Snapshot or diff harness-evolvable surfaces in an install."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "--snapshot",
        action="store_true",
        help="Capture current state to install_snapshot.json.",
    )
    mode.add_argument(
        "--diff",
        action="store_true",
        help="Diff current state against snapshot; write HARNESS_DIFF.md.",
    )
    parser.add_argument(
        "--install-root",
        default=None,
        help="Override install root (default: parent of .agent/).",
    )
    args = parser.parse_args(argv)

    install_root = Path(args.install_root) if args.install_root else INSTALL_ROOT

    if args.snapshot:
        snap = take_snapshot(install_root=install_root)
        print(
            f"ok: captured snapshot of {snap['tracked_count']} files "
            f"at {snap['captured_at']}"
        )
        print(f"     → {SNAPSHOT_PATH}")
        return 0

    if args.diff:
        result = diff_against_snapshot(install_root=install_root)
        if result["status"] == "no_snapshot":
            print(f"error: {result['stderr']}", file=sys.stderr)
            return 1
        print(
            f"ok: diff complete — added={result['added']} "
            f"modified={result['modified']} removed={result['removed']}"
        )
        print(f"     → {result['report']}")
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())

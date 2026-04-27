"""Snapshot store for the tldraw skill.

The live tldraw canvas at http://localhost:3030 is ephemeral; this module
persists a canvas state into `snapshots/` next to the skill so a later
session can recall it. Source of truth is `snapshots.jsonl`; `INDEX.md`
is rendered from it and is gitignored (never hand-edited, never committed).

Scope: this is skill-local storage, not a memory layer. It has no
lifecycle, no clustering, no dream-cycle integration, and is not read by
recall.py. Skills that need retrieval hooks should log to episodic memory
via tools/memory_reflect.py instead.

Concurrency: JSONL mutations hold an advisory exclusive flock (same
pattern as memory/render_lessons.py) so concurrent append / archive
calls serialize instead of corrupting the file. Windows (no fcntl) falls
through without locking — safe for single-user repos.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import sys
import threading
import warnings
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOTS_DIR = os.path.join(HERE, "snapshots")
ARCHIVE_DIR = os.path.join(SNAPSHOTS_DIR, "archive")
JSONL_PATH = os.path.join(HERE, "snapshots.jsonl")
INDEX_PATH = os.path.join(HERE, "INDEX.md")

_LABEL_RE = re.compile(r"[^a-zA-Z0-9._-]+")
_SID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
_MAX_RESAMPLE = 8

try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False

# Process-local mutex used as a fallback when fcntl is unavailable
# (i.e. Windows). Covers the in-process / multi-threaded case; cross-
# process serialization on Windows is not attempted and would require
# msvcrt.locking against a sidecar lock file.
_THREAD_LOCK = threading.RLock()

if not _HAS_FLOCK:
    warnings.warn(
        "fcntl unavailable; snapshots.jsonl is serialized by a process-"
        "local threading lock only. Safe for single-process use; not "
        "safe for concurrent writers across multiple OS processes.",
        RuntimeWarning, stacklevel=2,
    )


# ── helpers ────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _make_id(when: Optional[datetime] = None) -> str:
    """Time-sortable id: `YYYYMMDD-HHMMSS-<6-hex-random>`."""
    when = when or _now_utc()
    return f"{when.strftime('%Y%m%d-%H%M%S')}-{secrets.token_hex(3)}"


def _sanitize_label(label: str) -> str:
    cleaned = _LABEL_RE.sub("-", (label or "").strip()).strip("-")
    return cleaned or "unlabeled"


def _parse_tags(raw) -> list[str]:
    if raw is None:
        return []
    items: Iterable[str] = raw if isinstance(raw, list) else (raw or "").split(",")
    return [t.strip() for t in items if t and t.strip()]


def _require_valid_sid(sid: str) -> str:
    """Refuse anything that isn't a plain id token.

    `os.path.join(dir, f"{sid}.json")` would happily resolve `../../etc`
    and escape the snapshots dir. Constraining the character class blocks
    traversal before it can reach the filesystem.
    """
    if not isinstance(sid, str) or not _SID_RE.match(sid):
        raise ValueError(f"invalid snapshot id: {sid!r}")
    return sid


# ── filesystem primitives ─────────────────────────────────────────────

def _ensure_dirs() -> None:
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _atomic_write(path: str, data: str) -> None:
    # Unique tmp name per call — pid + thread id alone isn't enough, two
    # threads writing the same target in the same millisecond would race
    # to create the tmp file on Windows. 6 bytes of entropy eliminate that.
    tmp = f"{path}.tmp.{os.getpid()}.{secrets.token_hex(6)}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)


@contextmanager
def _locked_jsonl(path: str):
    """Hold an advisory exclusive flock for the scope of the block.

    Same pattern as memory/render_lessons.py. 'a+' mode creates the file
    if missing and permits read. Callers that need to rewrite the file
    must seek(0) and truncate() before writing.
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    # Acquire process-local lock first; on Unix the OS flock adds
    # cross-process safety on top. On Windows it's the only serialization.
    _THREAD_LOCK.acquire()
    f = open(path, "a+", encoding="utf-8")
    try:
        if _HAS_FLOCK:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        if _HAS_FLOCK:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass
        f.close()
        _THREAD_LOCK.release()


def _read_jsonl_locked(f) -> list[dict]:
    """Read all records from an already-open, already-locked file handle.

    Malformed lines are logged to stderr and skipped — silently swallowing
    JSONDecodeError hides the very corruption this store exists to avoid.
    """
    f.seek(0)
    out = []
    for lineno, raw in enumerate(f, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.append(json.loads(raw))
        except json.JSONDecodeError as e:
            print(f"[tldraw/store] skipping malformed {JSONL_PATH}:{lineno}: {e}",
                  file=sys.stderr)
    return out


# ── shape-payload normalization ───────────────────────────────────────

def _coerce_shapes(payload) -> list:
    shapes = payload["shapes"] if isinstance(payload, dict) and "shapes" in payload \
             else payload
    if not isinstance(shapes, list):
        raise ValueError("shapes must be a list or a {'shapes': [...]} envelope")
    return shapes


# ── public API ────────────────────────────────────────────────────────

def snapshot(shapes_payload, label: str, tags=None, note: str = "",
             when: Optional[datetime] = None) -> dict:
    """Persist the current canvas state. Returns the metadata record."""
    _ensure_dirs()
    shapes = _coerce_shapes(shapes_payload)
    tags_list = _parse_tags(tags)
    label_clean = _sanitize_label(label)
    when = when or _now_utc()

    # Reserve a unique id + filename. Extremely unlikely to collide
    # (24 bits of entropy per second), but bound the retry so a caller
    # passing a fixed `when` under a degenerate RNG can't spin forever.
    sid = None
    shape_path = None
    for _ in range(_MAX_RESAMPLE):
        candidate = _make_id(when=when)
        candidate_path = os.path.join(SNAPSHOTS_DIR, f"{candidate}.json")
        if not os.path.exists(candidate_path):
            sid, shape_path = candidate, candidate_path
            break
    if sid is None:
        raise RuntimeError(
            f"failed to allocate unique snapshot id after {_MAX_RESAMPLE} "
            f"attempts; check for a clock/RNG anomaly"
        )

    full = {
        "id": sid, "label": label_clean, "tags": tags_list, "note": note or "",
        "created_at": when.isoformat(), "shape_count": len(shapes),
        "shapes": shapes,
    }
    _atomic_write(shape_path, json.dumps(full, ensure_ascii=False, indent=2) + "\n")

    meta = {k: v for k, v in full.items() if k != "shapes"}
    meta["status"] = "active"

    with _locked_jsonl(JSONL_PATH) as f:
        f.seek(0, os.SEEK_END)
        f.write(json.dumps(meta, ensure_ascii=False) + "\n")
        f.flush()
        records = _read_jsonl_locked(f)
        _render_index(records)
    return meta


def list_snapshots(tag: Optional[str] = None,
                   include_archived: bool = False) -> list[dict]:
    if not os.path.exists(JSONL_PATH):
        return []
    with _locked_jsonl(JSONL_PATH) as f:
        records = _read_jsonl_locked(f)
    out = []
    for r in records:
        if not include_archived and r.get("status") == "archived":
            continue
        if tag and tag not in (r.get("tags") or []):
            continue
        out.append(r)
    return out


def load_snapshot(sid: str) -> dict:
    _require_valid_sid(sid)
    for root in (SNAPSHOTS_DIR, ARCHIVE_DIR):
        path = os.path.join(root, f"{sid}.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    raise FileNotFoundError(f"no snapshot with id {sid}")


def archive_snapshot(sid: str) -> dict:
    """Move snapshot file to archive/ and flip status in the jsonl."""
    _require_valid_sid(sid)
    _ensure_dirs()
    src = os.path.join(SNAPSHOTS_DIR, f"{sid}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"no active snapshot with id {sid}")
    shutil.move(src, os.path.join(ARCHIVE_DIR, f"{sid}.json"))

    with _locked_jsonl(JSONL_PATH) as f:
        records = _read_jsonl_locked(f)
        hit = None
        for r in records:
            if r.get("id") == sid:
                r["status"] = "archived"
                r["archived_at"] = _now_utc().isoformat()
                hit = r
        if hit is None:
            raise RuntimeError(
                f"snapshot {sid} has no metadata in snapshots.jsonl")
        body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
        f.seek(0)
        f.truncate()
        f.write(body)
        f.flush()
        _render_index(records)
    return hit


# ── INDEX.md renderer ─────────────────────────────────────────────────

_INDEX_HEADER = """# tldraw snapshots

Rendered from `snapshots.jsonl`. Do not hand-edit — re-render by calling
`store.py snapshot|archive` or the module's `_render_index`. This file
is gitignored; it exists only in installed projects.
"""


def _render_index(records: Optional[list[dict]] = None) -> None:
    if records is None:
        if not os.path.exists(JSONL_PATH):
            records = []
        else:
            with _locked_jsonl(JSONL_PATH) as f:
                records = _read_jsonl_locked(f)

    lines = [_INDEX_HEADER.rstrip(), ""]
    active = [r for r in records if r.get("status") != "archived"]
    archived = [r for r in records if r.get("status") == "archived"]

    def _row(r: dict) -> str:
        tags = ", ".join(r.get("tags") or []) or "-"
        note = (r.get("note") or "").replace("|", "\\|").replace("\n", " ")
        if len(note) > 80:
            note = note[:77] + "..."
        return (f"| `{r.get('id','')}` | {r.get('label','')} | {tags} | "
                f"{r.get('shape_count', 0)} | {r.get('created_at','')} | "
                f"{note or '-'} |")

    table_header = [
        "| id | label | tags | shapes | created | note |",
        "|---|---|---|---|---|---|",
    ]
    if active:
        lines += ["## Active", ""] + table_header + [_row(r) for r in active] + [""]
    else:
        lines += ["## Active", "", "_(no snapshots yet)_", ""]
    if archived:
        lines += ["## Archived", ""] + table_header + [_row(r) for r in archived] + [""]

    _atomic_write(INDEX_PATH, "\n".join(lines).rstrip() + "\n")


# ── CLI ───────────────────────────────────────────────────────────────

def _read_shapes_from_args(args) -> list:
    if args.file:
        with open(args.file, encoding="utf-8") as f:
            data = json.load(f)
    elif args.shapes_json:
        data = json.loads(args.shapes_json)
    else:
        raw = sys.stdin.read()
        if not raw.strip():
            raise SystemExit("error: no canvas JSON on stdin "
                             "(use --file or --shapes-json to supply it)")
        data = json.loads(raw)
    return _coerce_shapes(data)


def _cmd_snapshot(args) -> int:
    shapes = _read_shapes_from_args(args)
    meta = snapshot(shapes, label=args.label, tags=args.tags or [],
                    note=args.note or "")
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def _cmd_list(args) -> int:
    rows = list_snapshots(tag=args.tag, include_archived=args.all)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("(no snapshots)")
        return 0
    for r in rows:
        tags = ",".join(r.get("tags") or []) or "-"
        flag = " [archived]" if r.get("status") == "archived" else ""
        print(f"{r.get('id')}  {r.get('label')}  tags={tags}  "
              f"shapes={r.get('shape_count', 0)}{flag}")
    return 0


def _cmd_load(args) -> int:
    print(json.dumps(load_snapshot(args.id), ensure_ascii=False, indent=2))
    return 0


def _cmd_archive(args) -> int:
    print(json.dumps(archive_snapshot(args.id), ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tldraw-store",
                                description="Snapshot store for the tldraw skill.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="persist a canvas state")
    s.add_argument("--label", required=True)
    s.add_argument("--tags", type=lambda v: _parse_tags(v))
    s.add_argument("--note", default="")
    src = s.add_mutually_exclusive_group()
    src.add_argument("--file", help="read shapes JSON from this path")
    src.add_argument("--shapes-json", help="inline shapes JSON string")
    s.set_defaults(func=_cmd_snapshot)

    ls = sub.add_parser("list", help="list stored snapshots")
    ls.add_argument("--tag", help="filter by a single tag")
    ls.add_argument("--all", action="store_true", help="include archived")
    ls.add_argument("--json", action="store_true")
    ls.set_defaults(func=_cmd_list)

    lo = sub.add_parser("load", help="print full snapshot JSON")
    lo.add_argument("id")
    lo.set_defaults(func=_cmd_load)

    ar = sub.add_parser("archive", help="archive a snapshot (no delete)")
    ar.add_argument("id")
    ar.set_defaults(func=_cmd_archive)

    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

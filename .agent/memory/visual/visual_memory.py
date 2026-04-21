"""Visual memory layer — canvas snapshots as persistent agent memory.

The tldraw skill draws on an ephemeral live canvas. This module persists
a canvas state into `memory/visual/snapshots/` so later sessions can
recall it. Source of truth is `snapshots.jsonl` (one metadata record per
line); `INDEX.md` is rendered from it and never hand-edited.

The module has no network dependency on the tldraw MCP server. Shapes
come in as JSON (stdin or `--file`); storage is plain filesystem writes.
This keeps the layer harness-agnostic: any agent that can call
`get_canvas` and pipe the result can write visual memory.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import sys
import time
from datetime import datetime, timezone
from typing import Iterable, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SNAPSHOTS_DIR = os.path.join(HERE, "snapshots")
ARCHIVE_DIR = os.path.join(SNAPSHOTS_DIR, "archive")
JSONL_PATH = os.path.join(HERE, "snapshots.jsonl")
INDEX_PATH = os.path.join(HERE, "INDEX.md")

_LABEL_RE = re.compile(r"[^a-zA-Z0-9._-]+")


# ── id + label helpers ──────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _make_id(when: Optional[datetime] = None) -> str:
    """Time-sortable id: `YYYYMMDD-HHMMSS-<6-hex-random>`.

    The random suffix (24 bits of entropy) is what actually disambiguates —
    an earlier payload-hash design collided on identical same-second writes
    and silently overwrote the first file. Label isn't in the id because it
    would freeze at create time; label lives in the jsonl metadata instead.
    """
    when = when or _now_utc()
    stamp = when.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{secrets.token_hex(3)}"


def _sanitize_label(label: str) -> str:
    cleaned = _LABEL_RE.sub("-", (label or "").strip()).strip("-")
    return cleaned or "unlabeled"


def _parse_tags(raw) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        items: Iterable[str] = raw
    else:
        items = (raw or "").split(",")
    return [t.strip() for t in items if t and t.strip()]


# ── filesystem primitives ──────────────────────────────────────────────

def _ensure_dirs() -> None:
    os.makedirs(SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


def _atomic_write(path: str, data: str) -> None:
    tmp = f"{path}.tmp.{os.getpid()}.{int(time.time()*1000)}"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
    os.replace(tmp, path)


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _append_jsonl(path: str, record: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _rewrite_jsonl(path: str, records: list[dict]) -> None:
    body = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    _atomic_write(path, body)


# ── shape-payload normalization ────────────────────────────────────────

def _coerce_shapes(payload) -> list:
    """Accept either a raw list of shapes or a `{shapes: [...]}` envelope.

    `get_canvas()` returns the envelope; callers who already unpacked it
    can pass the list directly.
    """
    if isinstance(payload, dict) and "shapes" in payload:
        shapes = payload["shapes"]
    else:
        shapes = payload
    if not isinstance(shapes, list):
        raise ValueError("shapes must be a list or a {'shapes': [...]} envelope")
    return shapes


# ── public API ─────────────────────────────────────────────────────────

def snapshot(shapes_payload, label: str, tags=None, note: str = "",
             when: Optional[datetime] = None) -> dict:
    """Persist the current canvas state. Returns the metadata record."""
    _ensure_dirs()
    shapes = _coerce_shapes(shapes_payload)
    tags_list = _parse_tags(tags)
    label_clean = _sanitize_label(label)
    when = when or _now_utc()

    sid = _make_id(when=when)
    # Defensive: if a caller passes a fixed `when` and we somehow collide,
    # resample rather than clobber an existing snapshot. Filesystem is the
    # source of uniqueness — the jsonl would be out of sync if we overwrote.
    shape_path = os.path.join(SNAPSHOTS_DIR, f"{sid}.json")
    while os.path.exists(shape_path):
        sid = _make_id(when=when)
        shape_path = os.path.join(SNAPSHOTS_DIR, f"{sid}.json")

    full = {
        "id": sid,
        "label": label_clean,
        "tags": tags_list,
        "note": note or "",
        "created_at": when.isoformat(),
        "shape_count": len(shapes),
        "shapes": shapes,
    }
    _atomic_write(shape_path, json.dumps(full, ensure_ascii=False, indent=2) + "\n")

    meta = {k: v for k, v in full.items() if k != "shapes"}
    meta["status"] = "active"
    _append_jsonl(JSONL_PATH, meta)
    _render_index()
    return meta


def list_snapshots(tag: Optional[str] = None,
                   include_archived: bool = False) -> list[dict]:
    records = _read_jsonl(JSONL_PATH)
    out = []
    for r in records:
        if not include_archived and r.get("status") == "archived":
            continue
        if tag and tag not in (r.get("tags") or []):
            continue
        out.append(r)
    return out


def load_snapshot(sid: str) -> dict:
    path = os.path.join(SNAPSHOTS_DIR, f"{sid}.json")
    if not os.path.exists(path):
        path = os.path.join(ARCHIVE_DIR, f"{sid}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"no snapshot with id {sid}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def archive_snapshot(sid: str) -> dict:
    """Move snapshot file to archive/ and flip status in the jsonl."""
    _ensure_dirs()
    src = os.path.join(SNAPSHOTS_DIR, f"{sid}.json")
    if not os.path.exists(src):
        raise FileNotFoundError(f"no active snapshot with id {sid}")
    shutil.move(src, os.path.join(ARCHIVE_DIR, f"{sid}.json"))

    records = _read_jsonl(JSONL_PATH)
    hit = None
    for r in records:
        if r.get("id") == sid:
            r["status"] = "archived"
            r["archived_at"] = _now_utc().isoformat()
            hit = r
    if hit is None:
        raise RuntimeError(f"snapshot {sid} has no metadata in snapshots.jsonl")
    _rewrite_jsonl(JSONL_PATH, records)
    _render_index()
    return hit


def status() -> dict:
    records = _read_jsonl(JSONL_PATH)
    active = [r for r in records if r.get("status") != "archived"]
    archived = [r for r in records if r.get("status") == "archived"]
    tags = sorted({t for r in active for t in (r.get("tags") or [])})
    return {
        "active": len(active),
        "archived": len(archived),
        "tags": tags,
        "jsonl": JSONL_PATH,
        "snapshots_dir": SNAPSHOTS_DIR,
    }


# ── INDEX.md renderer ──────────────────────────────────────────────────

_INDEX_HEADER = """# Visual memory index

Rendered from `snapshots.jsonl`. Do not hand-edit entries — re-render by
calling `visual_memory.py snapshot|archive` or the module's `_render_index`.
"""


def _render_index() -> None:
    records = _read_jsonl(JSONL_PATH)
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

    if active:
        lines += [
            "## Active", "",
            "| id | label | tags | shapes | created | note |",
            "|---|---|---|---|---|---|",
        ]
        lines += [_row(r) for r in active]
        lines.append("")
    else:
        lines += ["## Active", "", "_(no snapshots yet)_", ""]

    if archived:
        lines += [
            "## Archived", "",
            "| id | label | tags | shapes | created | note |",
            "|---|---|---|---|---|---|",
        ]
        lines += [_row(r) for r in archived]
        lines.append("")

    _atomic_write(INDEX_PATH, "\n".join(lines).rstrip() + "\n")


# ── CLI ────────────────────────────────────────────────────────────────

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
    data = load_snapshot(args.id)
    print(json.dumps(data, ensure_ascii=False, indent=2))
    return 0


def _cmd_archive(args) -> int:
    meta = archive_snapshot(args.id)
    print(json.dumps(meta, ensure_ascii=False, indent=2))
    return 0


def _cmd_status(_args) -> int:
    print(json.dumps(status(), ensure_ascii=False, indent=2))
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="visual_memory",
                                description="Canvas snapshot store for the "
                                            "visual memory layer.")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("snapshot", help="persist a canvas state")
    s.add_argument("--label", required=True)
    s.add_argument("--tags", type=lambda s: _parse_tags(s))
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

    st = sub.add_parser("status", help="layer overview")
    st.set_defaults(func=_cmd_status)

    return p


def main(argv=None) -> int:
    args = _build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

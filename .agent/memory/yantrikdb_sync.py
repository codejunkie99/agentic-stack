#!/usr/bin/env python3
"""
YantrikDB Sync [BETA] — mirror .agent/memory/ markdown into a yantrikdb server.

Purpose: layer yantrikdb's cognitive primitives (multi-signal recall,
contradiction detection, temporal decay, consolidation) on top of the
portable markdown brain WITHOUT replacing it. The filesystem stays
authoritative; yantrikdb is an optional enhanced recall/consolidation
layer that users opt into.

How it fits:
  - .agent/memory/*.md / *.jsonl remain the canonical store (git-tracked,
    human-readable, no vendor lock-in).
  - This tool walks the tree and upserts each memory document into
    yantrikdb with a stable rid derived from the file path.
  - Subsequent runs are incremental (mtime + content-hash).
  - Type tagging is directory-based:
      semantic/   → memory_type="semantic"
      episodic/   → memory_type="episodic"
      personal/   → memory_type="self_model"
      working/    → memory_type="working"
  - Metadata attached: source_path, mtime, doc_hash.

BETA + opt-in: disabled by default. Enable via onboarding
(agentic-stack <harness> --reconfigure) or by setting
    {"yantrikdb_memory": {"enabled": true, "url": "...", "token": "..."}}
in .agent/memory/.features.json.

Usage:
  python3 yantrikdb_sync.py                   # incremental sync (default)
  python3 yantrikdb_sync.py --full            # full resync (drops cache)
  python3 yantrikdb_sync.py --dry-run         # show what would sync
  python3 yantrikdb_sync.py --status          # counts + last sync time

Requires: pip install yantrikdb-client>=0.2.1
"""
import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
FEATURES_PATH = MEMORY_DIR / ".features.json"
CACHE_PATH = MEMORY_DIR / ".index" / "yantrikdb_sync_cache.json"

MEMORY_SUFFIXES = (".md", ".jsonl")

# Directory → yantrikdb memory_type mapping. Unknown dirs default to "semantic".
TYPE_MAP = {
    "semantic": "semantic",
    "episodic": "episodic",
    "personal": "self_model",
    "working": "working",
    "candidates": "hypothesis",  # graduate.py treats candidates as unconfirmed
}


def feature_config() -> dict:
    """Return the yantrikdb_memory feature config, or {} if disabled/missing.

    Resolves env vars (YDB_URL, YDB_TOKEN) when the .features.json values
    are empty strings — lets users keep secrets out of the repo.
    """
    try:
        data = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    entry = data.get("yantrikdb_memory") or {}
    if not entry.get("enabled"):
        return {}
    # Fill from env if unset
    cfg = dict(entry)
    if not cfg.get("url"):
        cfg["url"] = os.environ.get("YDB_URL", "http://localhost:7438")
    if not cfg.get("token"):
        cfg["token"] = os.environ.get("YDB_TOKEN", "")
    if not cfg.get("namespace"):
        cfg["namespace"] = _default_namespace()
    return cfg


def _default_namespace() -> str:
    """Derive a stable per-project namespace from the repo root path so
    multiple projects sharing one yantrikdb server don't collide."""
    repo_root = MEMORY_DIR.parent.parent  # .agent/memory → project root
    digest = hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]
    return f"agentic-stack/{repo_root.name}/{digest}"


def _load_cache() -> dict:
    """Load the per-path mtime+hash cache so we can skip unchanged files."""
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, sort_keys=True), encoding="utf-8")


def _memory_files():
    """Yield (Path, memory_type, relative_dir_name) for each indexable doc.

    Skips .index/ and hidden files. Type is derived from the first path
    component under .agent/memory/.
    """
    for f in MEMORY_DIR.rglob("*"):
        if any(p.startswith(".") for p in f.relative_to(MEMORY_DIR).parts):
            continue
        if f.suffix not in MEMORY_SUFFIXES or not f.is_file():
            continue
        rel = f.relative_to(MEMORY_DIR)
        if not rel.parts:
            continue
        top = rel.parts[0]
        mtype = TYPE_MAP.get(top, "semantic")
        yield f, mtype, top


def _doc_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _upsert(client, path: Path, memory_type: str, top_dir: str,
            namespace: str) -> str:
    """Upsert a single document. Returns the yantrikdb rid."""
    text = path.read_text(encoding="utf-8", errors="replace")
    rel = str(path.relative_to(MEMORY_DIR))
    metadata = {
        "source_path": rel,
        "source_dir": top_dir,
        "mtime": path.stat().st_mtime,
        "doc_hash": _doc_hash(path),
    }
    return client.remember(
        text,
        memory_type=memory_type,
        importance=0.7 if top_dir == "personal" else 0.5,
        domain="agentic-stack",
        source=f"file:{top_dir}",
        namespace=namespace,
        metadata=metadata,
    )


def run_sync(full: bool = False, dry_run: bool = False) -> dict:
    """Sync all indexable docs under .agent/memory/ into yantrikdb.

    Returns a summary dict: {synced, skipped, errors, elapsed_s}.
    """
    cfg = feature_config()
    if not cfg:
        print("yantrikdb_memory feature is disabled. Enable in .features.json "
              "or via onboarding wizard.")
        return {"synced": 0, "skipped": 0, "errors": 0, "elapsed_s": 0}

    try:
        from yantrikdb import connect
    except ImportError:
        print("Missing dependency: pip install 'yantrikdb-client>=0.2.1'",
              file=sys.stderr)
        return {"synced": 0, "skipped": 0, "errors": 1, "elapsed_s": 0}

    cache = {} if full else _load_cache()
    t0 = time.time()
    synced = skipped = errors = 0

    if dry_run:
        client = None
    else:
        client = connect(cfg["url"], token=cfg["token"])

    try:
        for path, mtype, top in _memory_files():
            rel = str(path.relative_to(MEMORY_DIR))
            new_hash = _doc_hash(path)
            cached = cache.get(rel)
            if cached and cached.get("doc_hash") == new_hash:
                skipped += 1
                continue
            if dry_run:
                print(f"  would sync: {rel} ({mtype})")
                synced += 1
                continue
            try:
                rid = _upsert(client, path, mtype, top, cfg["namespace"])
                cache[rel] = {"doc_hash": new_hash,
                              "rid": rid,
                              "mtime": path.stat().st_mtime,
                              "memory_type": mtype}
                synced += 1
            except Exception as exc:  # noqa: BLE001 — surface all upsert errors
                print(f"  ERROR syncing {rel}: {exc}", file=sys.stderr)
                errors += 1
    finally:
        if client is not None:
            client.close()

    if not dry_run:
        _save_cache(cache)
    elapsed = round(time.time() - t0, 2)
    return {"synced": synced, "skipped": skipped, "errors": errors,
            "elapsed_s": elapsed}


def show_status() -> None:
    """Print counts of what's been synced and last sync time."""
    cfg = feature_config()
    if not cfg:
        print("yantrikdb_memory: disabled")
        return
    cache = _load_cache()
    by_type = {}
    for entry in cache.values():
        t = entry.get("memory_type", "unknown")
        by_type[t] = by_type.get(t, 0) + 1
    print(f"yantrikdb_memory: enabled")
    print(f"  url:       {cfg['url']}")
    print(f"  namespace: {cfg['namespace']}")
    print(f"  synced:    {sum(by_type.values())} docs in cache")
    for t, n in sorted(by_type.items()):
        print(f"    {t}: {n}")
    if cache:
        newest = max((e.get("mtime", 0) for e in cache.values()), default=0)
        if newest:
            print(f"  newest mtime: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(newest))}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("--full", action="store_true",
                   help="Full resync, ignoring the incremental cache.")
    p.add_argument("--dry-run", action="store_true",
                   help="Show what would sync without talking to the server.")
    p.add_argument("--status", action="store_true",
                   help="Print sync status and exit.")
    args = p.parse_args()

    if args.status:
        show_status()
        return 0

    summary = run_sync(full=args.full, dry_run=args.dry_run)
    print(f"sync: {summary['synced']} synced, {summary['skipped']} skipped, "
          f"{summary['errors']} errors in {summary['elapsed_s']}s")
    return 0 if summary["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
YantrikDB Recall [BETA] — multi-signal recall over .agent/memory/ via yantrikdb.

Augments the default lexical `recall.py` and the FTS5 `memory_search.py`
with yantrikdb's combined (vector × decay × importance × graph ×
retrieval-feedback) scoring. Falls back gracefully: if yantrikdb is
not configured or unreachable, prints a clear message and exits — does
NOT fake results. The agent can then fall back to the existing tools.

Pipeline:
  1. Read .features.json; bail if yantrikdb_memory is disabled.
  2. Connect to yantrikdb via `yantrikdb-client>=0.2.1` (auto-embedder on).
  3. Run recall(query, top_k, namespace=current-project) with the project-
     scoped namespace established by yantrikdb_sync.py.
  4. Print ranked results with:
       - source file path (from metadata)
       - memory_type
       - score + `why_retrieved` (yantrikdb's explanation hooks)
       - 140-char text preview

Usage:
  python3 yantrikdb_recall.py "<query>"            # pretty output, top 10
  python3 yantrikdb_recall.py "<query>" --top-k 5
  python3 yantrikdb_recall.py "<query>" --json     # machine-readable
  python3 yantrikdb_recall.py "<query>" --type rule

BETA + opt-in. Requires yantrikdb-client installed and the
yantrikdb_memory feature enabled.
"""
import argparse
import json
import os
import sys
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent.parent / "memory"
FEATURES_PATH = MEMORY_DIR / ".features.json"


def _feature_config() -> dict:
    try:
        data = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    entry = data.get("yantrikdb_memory") or {}
    if not entry.get("enabled"):
        return {}
    cfg = dict(entry)
    if not cfg.get("url"):
        cfg["url"] = os.environ.get("YDB_URL", "http://localhost:7438")
    if not cfg.get("token"):
        cfg["token"] = os.environ.get("YDB_TOKEN", "")
    if not cfg.get("namespace"):
        # Must match yantrikdb_sync.py's default namespace to find anything
        import hashlib
        repo_root = MEMORY_DIR.parent.parent
        digest = hashlib.sha256(str(repo_root.resolve()).encode()).hexdigest()[:12]
        cfg["namespace"] = f"agentic-stack/{repo_root.name}/{digest}"
    return cfg


def recall(query: str, top_k: int = 10, memory_type: str | None = None) -> list[dict]:
    """Run yantrikdb recall. Returns a list of dicts ready for rendering.

    Raises RuntimeError with a clear message if the feature is disabled
    or the SDK isn't installed — callers (e.g. agents) should catch and
    fall back to lexical tools.
    """
    cfg = _feature_config()
    if not cfg:
        raise RuntimeError(
            "yantrikdb_memory feature disabled. Enable in .features.json "
            "or via onboarding wizard."
        )
    try:
        from yantrikdb import connect
    except ImportError as exc:
        raise RuntimeError(
            "yantrikdb-client not installed. pip install 'yantrikdb-client>=0.2.1'"
        ) from exc

    client = connect(cfg["url"], token=cfg["token"])
    try:
        result = client.recall(
            query,
            top_k=top_k,
            namespace=cfg["namespace"],
            memory_type=memory_type,
            expand_entities=True,
        )
    finally:
        client.close()

    out = []
    for mem in result.results:
        meta = getattr(mem, "metadata", {}) or {}
        out.append({
            "rid": mem.rid,
            "source_path": meta.get("source_path", ""),
            "memory_type": mem.memory_type,
            "score": round(mem.score, 3),
            "why": getattr(mem, "why_retrieved", []),
            "text": mem.text[:140] + ("…" if len(mem.text) > 140 else ""),
        })
    return out


def _render_pretty(query: str, items: list[dict]) -> str:
    if not items:
        return f"(no yantrikdb matches for: {query})"
    lines = [f"yantrikdb recall: {query!r}  →  {len(items)} hits"]
    for i, it in enumerate(items, 1):
        why = ", ".join(it["why"][:3]) if it["why"] else ""
        why_s = f"  [{why}]" if why else ""
        src = it["source_path"] or f"rid:{it['rid'][:8]}"
        lines.append(
            f"  {i}. [{it['memory_type']:<10}] score={it['score']}  {src}{why_s}\n"
            f"     {it['text']}"
        )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    p.add_argument("query", help="Natural-language recall query")
    p.add_argument("--top-k", type=int, default=10,
                   help="Max results to return (default 10)")
    p.add_argument("--type", dest="memory_type",
                   choices=["semantic", "episodic", "self_model", "rule",
                            "constraint", "hypothesis", "working", "narrative_arc"],
                   help="Filter to a specific memory_type.")
    p.add_argument("--json", action="store_true",
                   help="Machine-readable JSON output.")
    args = p.parse_args()

    try:
        items = recall(args.query, top_k=args.top_k, memory_type=args.memory_type)
    except RuntimeError as exc:
        print(f"yantrikdb_recall: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"query": args.query, "results": items},
                         indent=2, default=str))
    else:
        print(_render_pretty(args.query, items))
    return 0


if __name__ == "__main__":
    sys.exit(main())

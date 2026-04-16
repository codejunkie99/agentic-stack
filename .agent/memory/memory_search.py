#!/usr/bin/env python3
"""
Memory Search [BETA] — SQLite FTS5 full-text search over .agent/memory/ files.

Indexes all .md and .jsonl files under .agent/memory/ and provides ranked
keyword search. Falls back to grep (restricted to .md/.jsonl) if FTS5 is
not available.

BETA + opt-in: disabled by default. Enable via onboarding
(agentic-stack <harness> --reconfigure) or by setting
    {"memory_search_fts": {"enabled": true}}
in .agent/memory/.features.json.

Usage:
  python3 memory_search.py <query>       Search memories by keyword
  python3 memory_search.py --rebuild     Force rebuild the index
  python3 memory_search.py --status      Show index status

The index is stored at .agent/memory/.index/memory.db and auto-rebuilds
when any memory file changes, is renamed, or is deleted.
"""
import json
import sys
import sqlite3
import subprocess
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
INDEX_DIR = MEMORY_DIR / ".index"
INDEX_PATH = INDEX_DIR / "memory.db"
FEATURES_PATH = MEMORY_DIR / ".features.json"

# Files we consider "memory documents" for both indexing and search.
MEMORY_SUFFIXES = (".md", ".jsonl")


def feature_enabled() -> bool:
    """True iff `memory_search_fts` is opted in via .features.json.

    Default OFF: beta features are explicit opt-in. Missing config file,
    missing key, or `enabled: false` all resolve to disabled.
    """
    try:
        data = json.loads(FEATURES_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return False
    entry = data.get("memory_search_fts") or {}
    return bool(entry.get("enabled"))


def _memory_files():
    """Yield memory document paths, skipping the .index/ side directory."""
    for f in MEMORY_DIR.rglob("*"):
        if ".index" in f.parts:
            continue
        if f.suffix in MEMORY_SUFFIXES and f.is_file():
            yield f


def check_fts5() -> bool:
    """Check if SQLite FTS5 extension is available."""
    try:
        conn = sqlite3.connect(":memory:")
        conn.execute("CREATE VIRTUAL TABLE _t USING fts5(c)")
        conn.close()
        return True
    except Exception:
        return False


def needs_rebuild() -> bool:
    """True if the index is stale.

    Stale means any of:
      - index file does not exist
      - a current memory file is newer than the index
      - a file that WAS indexed no longer exists (delete / rename)

    Without the third check, deleted files keep showing up in search
    results until some unrelated edit bumps the index.
    """
    if not INDEX_PATH.exists():
        return True
    index_mtime = INDEX_PATH.stat().st_mtime

    current_rel = set()
    for f in _memory_files():
        if f.stat().st_mtime > index_mtime:
            return True
        current_rel.add(str(f.relative_to(MEMORY_DIR)))

    try:
        conn = sqlite3.connect(INDEX_PATH)
        indexed_rel = {row[0] for row in conn.execute("SELECT filename FROM memories")}
        conn.close()
    except sqlite3.OperationalError:
        return True  # corrupt schema / unreadable — rebuild from scratch

    # Any previously-indexed file no longer present? Rebuild to flush it.
    if indexed_rel - current_rel:
        return True
    return False


def _read_jsonl(path: Path) -> str:
    """Read a .jsonl file and return a searchable text representation."""
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            entry = json.loads(raw)
            parts = [
                entry.get("action", ""),
                entry.get("reflection", ""),
                entry.get("detail", ""),
                entry.get("skill", ""),
            ]
            lines.append(" ".join(p for p in parts if p))
        except json.JSONDecodeError:
            continue
    return "\n".join(lines)


def build_index() -> int:
    """Build or rebuild the FTS5 index from all memory files."""
    INDEX_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(INDEX_PATH)
    conn.execute("DROP TABLE IF EXISTS memories")
    conn.execute("""
        CREATE VIRTUAL TABLE memories
        USING fts5(filename, content, tokenize='porter unicode61')
    """)
    indexed = 0
    for f in _memory_files():
        try:
            if f.suffix == ".md":
                content = f.read_text(encoding="utf-8")
            elif f.suffix == ".jsonl":
                content = _read_jsonl(f)
            else:
                continue
            rel_path = f.relative_to(MEMORY_DIR)
            conn.execute("INSERT INTO memories VALUES (?, ?)",
                         (str(rel_path), content))
            indexed += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return indexed


def search_fts5(query: str):
    """Search the FTS5 index. Returns (filename, snippet) pairs."""
    if needs_rebuild():
        build_index()
    conn = sqlite3.connect(INDEX_PATH)
    try:
        rows = conn.execute(
            """SELECT filename,
                      snippet(memories, 1, '>>>', '<<<', '...', 30)
               FROM memories
               WHERE memories MATCH ?
               ORDER BY rank""",
            (query,),
        ).fetchall()
    except sqlite3.OperationalError:
        # Query syntax error — fall back to LIKE
        rows = conn.execute(
            "SELECT filename, substr(content, 1, 300) FROM memories WHERE content LIKE ?",
            (f"%{query}%",),
        ).fetchall()
    conn.close()
    return rows


def search_grep(query: str):
    """Fallback search using grep, restricted to memory document files.

    Passing explicit target paths (not the whole directory) ensures we
    don't match implementation files like archive.py or auto_dream.py —
    keyword retrieval must only surface .md / .jsonl memory content.
    """
    targets = [str(f) for f in _memory_files()]
    if not targets:
        return []
    result = subprocess.run(
        ["grep", "-ril", query, *targets],
        capture_output=True,
        text=True,
    )
    files = [f for f in result.stdout.strip().split("\n") if f]
    return [
        (Path(f).relative_to(MEMORY_DIR), f"(match in {Path(f).name})")
        for f in files
    ]


def cmd_rebuild():
    if not check_fts5():
        print("FTS5 not available — cannot build index.")
        return
    count = build_index()
    print(f"Index rebuilt: {count} files indexed.")


def cmd_status():
    enabled = feature_enabled()
    tag = "ENABLED" if enabled else "DISABLED (beta, opt-in)"
    print(f"Feature: memory_search_fts [BETA] — {tag}")
    if not enabled:
        print("Enable via: agentic-stack <harness> --reconfigure")
        print("Or edit .agent/memory/.features.json directly.")
        return
    if not check_fts5():
        print("Mode: BASIC (grep fallback)")
        print("Reason: SQLite FTS5 not available in this Python build.")
        return
    if not INDEX_PATH.exists():
        print("Mode: FTS5 (index not built yet — auto-builds on first search)")
        return
    conn = sqlite3.connect(INDEX_PATH)
    count = conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]
    conn.close()
    size_kb = INDEX_PATH.stat().st_size // 1024
    print(f"Mode: FTS5")
    print(f"Index: {count} files indexed ({size_kb} KB)")
    print(f"Location: {INDEX_PATH}")


def _refuse_disabled():
    print(
        "memory_search [BETA] is disabled — opt-in only.\n"
        "Enable via onboarding:  agentic-stack <harness> --reconfigure\n"
        "Or set enabled=true for memory_search_fts in "
        ".agent/memory/.features.json",
        file=sys.stderr,
    )
    sys.exit(2)


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage [BETA, opt-in]:")
        print("  memory_search.py <query>     Search memories by keyword")
        print("  memory_search.py --rebuild   Force rebuild index")
        print("  memory_search.py --status    Show index status")
        sys.exit(0)

    # --status always works (lets the user see whether the feature is on).
    # All other commands require the opt-in flag.
    if args[0] == "--status":
        cmd_status()
        return

    if not feature_enabled():
        _refuse_disabled()

    if args[0] == "--rebuild":
        cmd_rebuild()
        return

    query = " ".join(args)
    use_fts5 = check_fts5()

    if use_fts5:
        results = search_fts5(query)
        mode = "FTS5"
    else:
        results = search_grep(query)
        mode = "grep"

    if not results:
        print(f"No results for: '{query}'  [mode: {mode}]")
        return

    print(f"Results for: '{query}'  [mode: {mode}]\n")
    for filename, snippet in results:
        print(f"  {filename}")
        print(f"  {snippet}\n")


if __name__ == "__main__":
    main()

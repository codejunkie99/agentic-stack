#!/usr/bin/env python3
"""
Memory Search — SQLite FTS5 full-text search over .agent/memory/ files.

Indexes all .md and .jsonl files under .agent/memory/ and provides ranked
keyword search. Falls back to grep if FTS5 is not available.

Usage:
  python3 memory_search.py <query>       Search memories by keyword
  python3 memory_search.py --rebuild     Force rebuild the index
  python3 memory_search.py --status      Show index status

The index is stored at .agent/memory/.index/memory.db and auto-rebuilds
when any memory file changes. It is gitignored (derived data).
"""
import json
import sys
import sqlite3
import subprocess
from pathlib import Path

MEMORY_DIR = Path(__file__).resolve().parent
INDEX_DIR = MEMORY_DIR / ".index"
INDEX_PATH = INDEX_DIR / "memory.db"


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
    """Check if index is stale (any source file newer than the index)."""
    if not INDEX_PATH.exists():
        return True
    index_mtime = INDEX_PATH.stat().st_mtime
    for f in MEMORY_DIR.rglob("*"):
        if ".index" in str(f):
            continue
        if f.suffix in (".md", ".jsonl") and f.stat().st_mtime > index_mtime:
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
    for f in MEMORY_DIR.rglob("*"):
        if ".index" in str(f):
            continue
        try:
            if f.suffix == ".md":
                content = f.read_text(encoding="utf-8")
            elif f.suffix == ".jsonl":
                content = _read_jsonl(f)
            else:
                continue
            rel_path = f.relative_to(MEMORY_DIR)
            conn.execute("INSERT INTO memories VALUES (?, ?)", (str(rel_path), content))
            indexed += 1
        except Exception:
            pass
    conn.commit()
    conn.close()
    return indexed


def search_fts5(query: str) -> list[tuple[str, str]]:
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


def search_grep(query: str) -> list[tuple[str, str]]:
    """Fallback search using grep when FTS5 is not available."""
    result = subprocess.run(
        ["grep", "-ril", query, str(MEMORY_DIR)],
        capture_output=True,
        text=True,
    )
    files = [
        f
        for f in result.stdout.strip().split("\n")
        if f and ".index" not in f
    ]
    return [(Path(f).relative_to(MEMORY_DIR), f"(match in {Path(f).name})") for f in files]


def cmd_rebuild():
    if not check_fts5():
        print("FTS5 not available — cannot build index.")
        return
    count = build_index()
    print(f"Index rebuilt: {count} files indexed.")


def cmd_status():
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


def main():
    args = sys.argv[1:]

    if not args or args[0] in ("-h", "--help"):
        print("Usage:")
        print("  memory_search.py <query>     Search memories by keyword")
        print("  memory_search.py --rebuild   Force rebuild index")
        print("  memory_search.py --status    Show index status")
        sys.exit(0)

    if args[0] == "--rebuild":
        cmd_rebuild()
        return

    if args[0] == "--status":
        cmd_status()
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

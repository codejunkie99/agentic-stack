"""Bounded, read-only personal and current-work context for coding agents."""
from __future__ import annotations

import re
from pathlib import Path

MAX_FILE = 2_000_000


def _read(path):
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > MAX_FILE:
            return ""
        return path.read_text(errors="replace")
    except OSError:
        return ""


def _terms(value):
    return {term.lower() for term in re.findall(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,}", value)}


def _sections(text):
    rows, title, body = [], "", []
    for line in text.splitlines():
        if line.startswith("#"):
            if title or body:
                rows.append((title or "Notes", "\n".join(body).strip()))
            title, body = line.lstrip("# ").strip(), []
        else:
            body.append(line)
    if title or body:
        rows.append((title or "Notes", "\n".join(body).strip()))
    return [(title, body) for title, body in rows if body]


def profile(root, query="", limit=8):
    """Return static preferences, dynamic work state, and relevant reviewed memory."""
    root = Path(root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError("projectPath must be an existing directory")
    personal = root / ".agent/memory/personal"
    working = root / ".agent/memory/working/WORKSPACE.md"
    static_sources = sorted(personal.glob("*.md")) if personal.is_dir() and not personal.is_symlink() else []
    static = [{"source": str(path.relative_to(root)), "content": _read(path)} for path in static_sources]
    static = [item for item in static if item["content"]]
    dynamic_text = _read(working)
    relevant = []
    if query:
        wanted = _terms(query)
        corpus = [(item["source"], item["content"]) for item in static]
        retrieved = root / "RETRIEVED_MEMORY.md"
        if retrieved.is_file() and not retrieved.is_symlink():
            corpus.append((retrieved.name, _read(retrieved)))
        for source, text in corpus:
            for title, body in _sections(text):
                score = len(wanted & _terms(title + " " + body))
                if score:
                    relevant.append({"source": source, "title": title, "content": body[:2400], "score": score})
        relevant.sort(key=lambda item: (-item["score"], item["source"], item["title"]))
    return {"static": static, "dynamic": {"source": str(working.relative_to(root)), "content": dynamic_text},
            "relevant": relevant[:max(1, min(limit, 20))]}

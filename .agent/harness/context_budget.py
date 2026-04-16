"""Assemble context from memory + matched skills + protocols within a token budget.

Query-aware: episodes and lessons are scored against user_input so the agent
sees the memory that matters for *this* task, not just the most salient memory
in general. Always-on slots (PREFERENCES, WORKSPACE, permissions) are loaded
whole regardless of query — they're cheap and safety-critical.
"""
import json, os, re, sys
from salience import salience_score
from text import word_set, jaccard

ROOT = os.path.join(os.path.dirname(__file__), "..")
# skill_loader lives in tools/ — make it importable without requiring callers
# to configure PYTHONPATH themselves
sys.path.insert(0, os.path.join(ROOT, "tools"))
RELEVANCE_FLOOR = 0.3  # even zero-overlap episodes surface if very salient

# Keep in sync with memory/validate._extract_lesson_lines — both filters
# want TERMINAL-only lesson content.
_STATUS_RE = re.compile(r"status=(\w+)")


def _read(path, limit=None):
    full = os.path.join(ROOT, path)
    if not os.path.exists(full):
        return ""
    content = open(full).read()
    return content[:limit] if limit else content


def _token_estimate(text):
    """Rough chars-to-tokens estimate for budgeting."""
    return len(text) // 4


def _relevance(entry_text, query_words):
    """Fraction of query words that appear in entry. 1.0 when no query."""
    if not query_words:
        return 1.0
    ew = word_set(entry_text)
    if not ew:
        return 0.0
    return len(query_words & ew) / len(query_words)


def _top_episodes(query, k=5):
    path = os.path.join(ROOT, "memory/episodic/AGENT_LEARNINGS.jsonl")
    if not os.path.exists(path):
        return ""
    entries = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue

    query_words = word_set(query)

    def _score(e):
        text = " ".join([
            e.get("action", ""),
            e.get("reflection", ""),
            e.get("detail", ""),
        ])
        rel = _relevance(text, query_words)
        return salience_score(e) * (RELEVANCE_FLOOR + (1.0 - RELEVANCE_FLOOR) * rel)

    entries.sort(key=_score, reverse=True)
    top = entries[:k]
    return "\n".join(
        f"- [{e.get('timestamp','')[:10]}] {e.get('action','')}: "
        f"{e.get('reflection', e.get('detail',''))}"
        for e in top
    )


def _lines_up_to_budget(lines, char_budget):
    out, used = [], 0
    for line in lines:
        block = f"- {line}\n"
        if used + len(block) > char_budget:
            break
        out.append(block)
        used += len(block)
    return "".join(out)


def _top_lessons(query, lessons_md, char_budget=8000):
    """Rank accepted lesson bullets by query overlap; fall back to original order.

    Only terminal (status=accepted) lessons reach the host agent as retrievable
    guidance. Provisional, legacy, and superseded bullets exist in LESSONS.md
    for audit but must not be injected into the system prompt — they'd let the
    agent act on probationary or stale memory.
    """
    lines = []
    for line in (lessons_md or "").splitlines():
        s = line.strip()
        if not s.startswith("- ") or len(s) <= 2:
            continue
        # Primary status filter: HTML annotation
        if "<!--" in s:
            ann = s.split("<!--", 1)[1]
            m = _STATUS_RE.search(ann)
            if m and m.group(1) != "accepted":
                continue
        text = s[2:].split("<!--")[0].strip()
        # Fallback: visual markers
        if text.startswith("[PROVISIONAL]"):
            continue
        if text.startswith("~~") and text.endswith("~~"):
            continue
        if text:
            lines.append(text)
    if not lines:
        # No accepted lessons → return empty. Returning raw markdown would
        # leak the non-terminal content the filter is designed to block.
        return ""

    query_words = word_set(query)
    if not query_words:
        return _lines_up_to_budget(lines, char_budget)

    scored = [(len(query_words & word_set(l)), i, l) for i, l in enumerate(lines)]
    relevant = sorted([s for s in scored if s[0] > 0], key=lambda s: (-s[0], s[1]))

    if not relevant:
        return _lines_up_to_budget(lines, char_budget)
    return _lines_up_to_budget([l for _, _, l in relevant], char_budget)


def build_context(user_input: str, budget: int = 88000):
    """Returns (context_string, tokens_used). Lean and query-aware."""
    parts, used = [], 0

    # always load: personal preferences + live workspace + AGENTS map + DECISIONS
    # AGENTS.md and DECISIONS.md were missing despite AGENTS.md specifying the
    # read order — the standalone path was not faithful to its own contract.
    for rel in (
        "AGENTS.md",
        "memory/personal/PREFERENCES.md",
        "memory/working/WORKSPACE.md",
        "memory/working/REVIEW_QUEUE.md",
        "memory/semantic/DECISIONS.md",
    ):
        text = _read(rel)
        if text:
            parts.append(f"# {rel}\n{text}")
            used += _token_estimate(text)

    # query-aware lessons
    lessons_raw = _read("memory/semantic/LESSONS.md")
    if lessons_raw:
        lessons = _top_lessons(user_input, lessons_raw, char_budget=8000)
        if lessons:
            parts.append(f"# LESSONS (query-relevant)\n{lessons}")
            used += _token_estimate(lessons)

    # query-aware top episodes
    episodes = _top_episodes(user_input, k=5)
    if episodes:
        parts.append(f"# RECENT EPISODES (salience x relevance)\n{episodes}")
        used += _token_estimate(episodes)

    # matched skills only (progressive_load is already input-matched).
    # Lazy import so a missing skill_loader doesn't kill context assembly.
    try:
        from skill_loader import progressive_load
        skills = progressive_load(user_input)
    except Exception:
        skills = []
    for s in skills:
        block = f"## Skill: {s['name']}\n{s['content']}"
        t = _token_estimate(block)
        if used + t < budget:
            parts.append(block)
            used += t

    # permissions always last, small, safety-critical
    perms = _read("protocols/permissions.md")
    if perms:
        parts.append(f"# PERMISSIONS\n{perms}")
        used += _token_estimate(perms)

    return "\n\n---\n\n".join(parts), used

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


_TRUNC_MARKER = "\n\n[truncated to fit budget]"
_OMIT_MARKER_FMT = "[{n} items omitted: budget exceeded]"


class _UsedTokens(int):
    """int subclass that carries an `overflow` flag.

    Existing callers do `ctx, used = build_context(...)` and treat `used` as an
    int — they still see the correct number. New callers can read
    `used.overflow` to learn whether enforcement had to drop or truncate
    content. This keeps the public 2-tuple signature compatible.
    """

    # int subclasses can't accept __slots__ for instance attrs (variable-size
    # base type), so we override __new__ to stash overflow on the instance dict
    # via plain assignment after relying on the default dict.
    def __new__(cls, value, overflow=False):
        obj = super().__new__(cls, value)
        obj.overflow = overflow
        return obj


def _truncate_to_tokens(text, max_tokens):
    """Truncate text so its token estimate fits in max_tokens, with marker.

    Uses the same chars-to-tokens ratio as `_token_estimate` (4 chars/token).
    Reserves room for the truncation marker so the post-truncation estimate
    still fits the budget the caller passed in.
    """
    if max_tokens <= 0:
        return ""
    if _token_estimate(text) <= max_tokens:
        return text
    marker_tokens = _token_estimate(_TRUNC_MARKER)
    char_budget = max(0, (max_tokens - marker_tokens) * 4)
    if char_budget <= 0:
        # No room even for body. Emit just the marker so the section still
        # signals presence (required sections must remain in the output).
        return _TRUNC_MARKER.lstrip()
    return text[:char_budget] + _TRUNC_MARKER


def build_context(user_input: str, budget: int = 88000):
    """Returns (context_string, used_tokens). Lean, query-aware, budget-enforced.

    Budget enforcement (P1 fix):
      * Required sections (AGENTS map, active workspace, permissions) are
        always present in the output. If they would overflow the budget,
        their content is truncated to fit and tagged with a
        `[truncated to fit budget]` marker — never dropped silently.
      * Optional sections (lessons, episodes, matched skills) are skipped
        entirely with an `[N items omitted: budget exceeded]` marker when
        they would overflow.
      * Every assembled context ends with a `[budget: used X / Y tokens]`
        summary so callers can see the final accounting.

    Return shape is preserved: a 2-tuple `(context_string, used_tokens)`.
    `used_tokens` is an int subclass that exposes an `overflow: bool`
    attribute for new callers; existing callers that treat it as a plain
    int are unaffected.
    """
    parts, used = [], 0
    overflow = False

    # Each appended block costs its own tokens *plus* the `\n\n---\n\n`
    # separator that join() will add between it and the next block. We track
    # separator overhead explicitly so the budget check matches what the
    # caller actually receives.
    SEPARATOR_TOKENS = _token_estimate("\n\n---\n\n")  # 9 chars → 2 tokens
    # Reserve room for the final `[budget: used X / Y tokens]` summary line
    # plus its leading separator. Width here is a conservative upper bound.
    SUMMARY_RESERVE_TOKENS = _token_estimate("[budget: used 99999999 / 99999999 tokens]") + SEPARATOR_TOKENS
    # Per-block `len(s)//4` truncation undercounts vs the post-join estimate.
    # Reserve small headroom so the final joined string still fits the budget.
    DRIFT_HEADROOM_TOKENS = 4

    # Required sections are *mandatory* — their headers + omission markers
    # are floor-cost overhead. To keep the joined output within budget, we
    # pre-reserve that floor so early required sections don't eat budget
    # that later required sections need just for their stub.
    required_files = (
        "AGENTS.md",
        "memory/personal/PREFERENCES.md",
        "memory/working/WORKSPACE.md",
        "memory/working/REVIEW_QUEUE.md",
        "memory/semantic/DECISIONS.md",
    )
    perms_path = "protocols/permissions.md"

    def _stub_cost(rel_or_label):
        """Token cost of the minimum stub (header + omission marker + sep)."""
        if rel_or_label == perms_path:
            header = "# PERMISSIONS\n"
        else:
            header = f"# {rel_or_label}\n"
        stub = header + _OMIT_MARKER_FMT.format(n=1)
        return _token_estimate(stub) + SEPARATOR_TOKENS

    # Floor = stub cost for every required file that exists on disk + perms.
    required_floor = 0
    for rel in required_files:
        if _read(rel):
            required_floor += _stub_cost(rel)
    if _read(perms_path):
        required_floor += _stub_cost(perms_path)

    def _append(block):
        """Append a block, charging both its tokens and the join separator."""
        nonlocal used
        parts.append(block)
        # First block has no preceding separator; subsequent blocks do.
        sep_cost = SEPARATOR_TOKENS if len(parts) > 1 else 0
        used += _token_estimate(block) + sep_cost

    def _block_cost(block):
        """Token cost of appending `block` (block + separator if not first)."""
        sep_cost = SEPARATOR_TOKENS if len(parts) >= 1 else 0
        return _token_estimate(block) + sep_cost

    # Track how much of `required_floor` we've already paid; the remainder
    # is reserved out of `_room()` so we don't overspend on early sections.
    paid_floor = 0

    def _room():
        # Remaining required_floor we haven't paid yet stays reserved.
        remaining_floor = max(0, required_floor - paid_floor)
        return budget - used - SUMMARY_RESERVE_TOKENS - DRIFT_HEADROOM_TOKENS - remaining_floor

    # ------------------------------------------------------------------
    # Required sections — must appear in output. Truncate if oversized.
    # Preserves the original load order: AGENTS map first, then personal
    # preferences, live workspace, review queue, semantic decisions. These
    # are the sections agentic-stack treats as always-on context.
    # ------------------------------------------------------------------
    for rel in required_files:
        text = _read(rel)
        if not text:
            continue
        header = f"# {rel}\n"
        # Pay this section's floor first so _room() releases its reservation.
        paid_floor += _stub_cost(rel)
        # Room for the *body*, after subtracting header and separator overhead.
        sep_cost = SEPARATOR_TOKENS if parts else 0
        body_room = _room() - _token_estimate(header) - sep_cost
        body_tokens = _token_estimate(text)
        if body_room <= 0:
            # No room left at all. Emit header + omission marker so the
            # caller still sees the section name in the assembled context.
            block = header + _OMIT_MARKER_FMT.format(n=1)
            _append(block)
            overflow = True
            continue
        if body_tokens > body_room:
            text = _truncate_to_tokens(text, body_room)
            overflow = True
        _append(header + text)

    # ------------------------------------------------------------------
    # Optional: query-aware lessons. Skip with marker on overflow.
    # ------------------------------------------------------------------
    lessons_raw = _read("memory/semantic/LESSONS.md")
    if lessons_raw:
        lessons = _top_lessons(user_input, lessons_raw, char_budget=8000)
        if lessons:
            header = "# LESSONS (query-relevant)\n"
            block = header + lessons
            if _block_cost(block) <= _room():
                _append(block)
            else:
                n = sum(1 for ln in lessons.splitlines() if ln.strip().startswith("- "))
                marker_block = header + _OMIT_MARKER_FMT.format(n=max(n, 1))
                if _block_cost(marker_block) <= _room():
                    _append(marker_block)
                overflow = True

    # ------------------------------------------------------------------
    # Optional: query-aware top episodes. Skip with marker on overflow.
    # ------------------------------------------------------------------
    episodes = _top_episodes(user_input, k=5)
    if episodes:
        header = "# RECENT EPISODES (salience x relevance)\n"
        block = header + episodes
        if _block_cost(block) <= _room():
            _append(block)
        else:
            n = sum(1 for ln in episodes.splitlines() if ln.strip().startswith("- "))
            marker_block = header + _OMIT_MARKER_FMT.format(n=max(n, 1))
            if _block_cost(marker_block) <= _room():
                _append(marker_block)
            overflow = True

    # ------------------------------------------------------------------
    # Optional: matched skills (progressive_load is already input-matched).
    # Lazy import so a missing skill_loader doesn't kill context assembly.
    # ------------------------------------------------------------------
    try:
        from skill_loader import progressive_load
        skills = progressive_load(user_input)
    except Exception:
        skills = []
    skipped_skills = 0
    for s in skills:
        block = f"## Skill: {s['name']}\n{s['content']}"
        if _block_cost(block) <= _room():
            _append(block)
        else:
            skipped_skills += 1
            overflow = True
    if skipped_skills:
        marker_block = _OMIT_MARKER_FMT.format(n=skipped_skills) + " (skills)"
        if _block_cost(marker_block) <= _room():
            _append(marker_block)

    # ------------------------------------------------------------------
    # Required: permissions. Last and safety-critical — must appear,
    # truncated if oversized.
    # ------------------------------------------------------------------
    perms = _read(perms_path)
    if perms:
        header = "# PERMISSIONS\n"
        # Pay the perms floor so _room() releases its reservation.
        paid_floor += _stub_cost(perms_path)
        sep_cost = SEPARATOR_TOKENS if parts else 0
        body_room = _room() - _token_estimate(header) - sep_cost
        body_tokens = _token_estimate(perms)
        if body_room <= 0:
            block = header + _OMIT_MARKER_FMT.format(n=1)
            _append(block)
            overflow = True
        else:
            if body_tokens > body_room:
                perms = _truncate_to_tokens(perms, body_room)
                overflow = True
            _append(header + perms)

    # ------------------------------------------------------------------
    # Final summary line. Always appended so callers can audit the
    # assembled context's accounting at a glance.
    # ------------------------------------------------------------------
    summary = f"[budget: used {used} / {budget} tokens]"
    _append(summary)

    # Reconcile the running tally against the actually joined string. Per-block
    # `len(s) // 4` integer truncation undercounts vs the concatenated whole,
    # so prefer the post-join estimate as the authoritative number returned.
    final = "\n\n---\n\n".join(parts)
    final_tokens = _token_estimate(final)
    if final_tokens > budget:
        overflow = True
    return final, _UsedTokens(final_tokens, overflow)

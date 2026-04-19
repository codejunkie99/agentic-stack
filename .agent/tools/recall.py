"""Proactive lesson recall for the current intent.

    python3 .agent/tools/recall.py "add a created_at column to orders"

Surfaces graduated lessons relevant to the described intent, with
lexical-overlap scores (NOT semantic relevance — see `_score` docstring).
Makes the *invisible* part of the agent (what memory is informing the
next action) *visible and auditable*.

Reads the structured lessons.jsonl source of truth if present; falls back
to parsing LESSONS.md for accepted bullets on fresh repos where no lesson
has been graduated yet.

Logs every recall event to episodic memory so:
  - you can grep the audit trail (`grep proactive-recall AGENT_LEARNINGS.jsonl`)
  - dream-cycle clustering sees when recall fires and what it surfaced
  - "did the lesson actually inform behavior" becomes measurable later

Output modes:
  --pretty   (default)   readable block for humans/agents
  --json                 machine-readable
  --quiet                no logging (useful for scripting / tests)
"""
import argparse, json, os, re, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "harness"))
from text import word_set  # noqa: E402

LESSONS_JSONL = os.path.join(BASE, "memory/semantic/lessons.jsonl")
LESSONS_MD = os.path.join(BASE, "memory/semantic/LESSONS.md")

_STATUS_RE = re.compile(r"status=(\w+)")


def _load_structured():
    """Prefer the structured source of truth when it exists.

    Tags each entry with `_source="lessons.jsonl"` so downstream labeling
    is accurate even when results merge with markdown seeds. Drops in-place
    rather than overwriting if the entry already has a source field.
    """
    if not os.path.exists(LESSONS_JSONL):
        return []
    out = []
    for line in open(LESSONS_JSONL):
        line = line.strip()
        if not line:
            continue
        try:
            l = json.loads(line)
        except json.JSONDecodeError:
            continue
        if l.get("status") != "accepted":
            continue
        l.setdefault("_source", "lessons.jsonl")
        out.append(l)
    return out


def _load_markdown_fallback():
    """Parse LESSONS.md for accepted bullets.

    On fresh repos lessons.jsonl doesn't exist yet, but hand-curated seed
    bullets in LESSONS.md can still inform recall. Uses the same filter as
    context_budget._top_lessons: skip [PROVISIONAL], strikethrough, and
    explicit non-accepted status annotations.
    """
    if not os.path.exists(LESSONS_MD):
        return []
    text = open(LESSONS_MD).read()
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("- ") or len(s) <= 2:
            continue
        if "<!--" in s:
            ann = s.split("<!--", 1)[1]
            m = _STATUS_RE.search(ann)
            if m and m.group(1) != "accepted":
                continue
        claim = s[2:].split("<!--")[0].strip()
        if claim.startswith("[PROVISIONAL]"):
            continue
        if claim.startswith("~~") and claim.endswith("~~"):
            continue
        if claim:
            out.append({
                "id": None,
                "claim": claim,
                "conditions": [],
                "status": "accepted",
                "_source": "LESSONS.md",
            })
    return out


def _score(claim, conditions, query_words):
    """Lexical overlap of query content words with claim + conditions, in [0, 1].

    NOT "relevance" in the semantic sense — this is lexical (token) overlap.
    A strong semantic match with different vocabulary will score low. A
    weak semantic match with shared buzzwords may score high. Use as a
    cheap first-pass retrieval signal, not a final ranking authority.

    Conditions are weighted 2x because they're the explicit trigger
    surface — a condition match is a stronger lexical signal than
    incidental word overlap in the claim text. The max possible weighted
    hit-count is (len(query_words) + 2*len(query_words)) = 3*len(query_words),
    so we divide by that to keep the score in [0, 1]. A perfect 1.0
    requires every query word to appear in BOTH claim and conditions.
    """
    if not query_words:
        return 0.0
    claim_words = word_set(claim)
    cond_words = set()
    for c in conditions or []:
        cond_words |= word_set(c)
    claim_hits = len(query_words & claim_words)
    cond_hits = len(query_words & cond_words)
    raw = claim_hits + 2 * cond_hits
    max_raw = 3 * len(query_words)
    return raw / max_raw if max_raw else 0.0


def _merge_sources():
    """Union accepted lessons from lessons.jsonl + LESSONS.md.

    lessons.jsonl is structured and carries ids + graduation metadata.
    LESSONS.md carries hand-curated seed bullets that never go through
    graduate.py and would otherwise disappear from recall the moment the
    first lesson is graduated. Merge by normalized claim so duplicates are
    suppressed (structured entries win — they have metadata).
    """
    import re as _re
    structured = _load_structured()
    md_only = _load_markdown_fallback()

    def _norm(s):
        t = _re.sub(r"[^\w\s]", " ", (s or "").lower())
        return _re.sub(r"\s+", " ", t).strip()

    seen = {_norm(l.get("claim", "")) for l in structured}
    merged = list(structured)
    for l in md_only:
        if _norm(l.get("claim", "")) not in seen:
            merged.append(l)
    return merged, (not structured)


def recall(intent, top_k=3, min_score=0.01):
    lessons, only_md = _merge_sources()

    qwords = word_set(intent)
    scored = []
    for l in lessons:
        score = _score(l.get("claim", ""), l.get("conditions", []), qwords)
        if score >= min_score:
            scored.append((score, l))
    scored.sort(key=lambda x: -x[0])
    top = [
        {
            "id": l.get("id"),
            "claim": l.get("claim"),
            "conditions": l.get("conditions", []),
            "lexical_overlap": round(s, 3),
            "source": l.get("_source", "unknown"),
            "accepted_at": l.get("accepted_at"),
        }
        for s, l in scored[:top_k]
    ]
    # Meta reports the mix of sources that contributed to the RESULT set,
    # not a global "did we fall back" bit. When both sources contribute,
    # the caller sees both — no lying by omission.
    source_counts = {}
    for r in top:
        source_counts[r["source"]] = source_counts.get(r["source"], 0) + 1
    return top, {
        "intent": intent,
        "considered": len(lessons),
        "returned": len(top),
        "source_counts": source_counts,
        "only_md_available": only_md,
    }


def log_recall(intent, result, meta):
    """Record the recall event in episodic memory so it's auditable."""
    try:
        sys.path.insert(0, os.path.join(BASE, "tools"))
        from memory_reflect import reflect  # noqa: E402
        detail = {
            "returned": [r["claim"][:80] for r in result],
            "considered": meta["considered"],
            "source_counts": meta.get("source_counts", {}),
            "only_md_available": meta.get("only_md_available", False),
        }
        reflect(
            "proactive-recall",
            f"recall:{intent[:80]}",
            json.dumps(detail, ensure_ascii=False),
            success=True,
            importance=6,
        )
    except Exception as e:
        # Never fail the recall because logging broke — that would make the
        # visibility feature a new source of flakiness.
        print(f"(warning: recall log failed: {e})", file=sys.stderr)


def format_pretty(intent, result, meta):
    lines = [f"Consulted lessons for intent: {intent!r}"]
    lines.append(f"  ({meta['considered']} accepted lessons available in corpus)")
    returned = meta.get("source_counts", {})
    if returned:
        returned_summary = ", ".join(
            f"{src}:{n}" for src, n in sorted(returned.items())
        )
        lines.append(f"  → returned {meta['returned']}: {returned_summary}")
    if not result:
        lines.append("  → no relevant lessons. Proceeding without prior guidance.")
        return "\n".join(lines)
    lines.append("")
    for i, r in enumerate(result, 1):
        src = r.get("source", "unknown")
        score = r.get("lexical_overlap", r.get("relevance", 0))
        lines.append(
            f"  [{i}] lexical_overlap={score}  {r['claim']}  [{src}]"
        )
        if r["conditions"]:
            lines.append(f"      conditions: {', '.join(r['conditions'])}")
    return "\n".join(lines)


def main():
    p = argparse.ArgumentParser(description="Surface relevant lessons for an intent.")
    p.add_argument("intent", help="Free-text description of what you're about to do.")
    p.add_argument("--top", type=int, default=3)
    p.add_argument("--json", action="store_true", help="Emit JSON instead of pretty.")
    p.add_argument("--quiet", action="store_true", help="Don't log to episodic.")
    args = p.parse_args()

    result, meta = recall(args.intent, top_k=args.top)
    if not args.quiet:
        log_recall(args.intent, result, meta)

    if args.json:
        print(json.dumps({"result": result, "meta": meta}, indent=2))
    else:
        print(format_pretty(args.intent, result, meta))


if __name__ == "__main__":
    main()

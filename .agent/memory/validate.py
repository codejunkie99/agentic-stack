"""Heuristic pre-filter for candidate lessons. Deterministic, no LLM.

The host agent does actual reasoning via the CLI tools in .agent/tools/
(graduate.py, reject.py). This module catches
obvious junk — too-short claims, exact duplicates — before the reviewer
sees the candidate at all. Anything subjective is the host's job.
"""
import os, re, sys

# Make harness/text.py importable for content-word counting. Codex review
# caught that raw char-length gates let `!!!!!!!!!!!!!!!!!abc` pass — a
# claim with exactly one real token. Content-word count is the real gate.
_HARNESS = os.path.join(os.path.dirname(__file__), "..", "harness")
if _HARNESS not in sys.path:
    sys.path.insert(0, _HARNESS)
from text import word_set

MIN_CLAIM_LEN = 20
MIN_CONTENT_WORDS = 3  # minimum non-stopword tokens for a meaningful claim
LENGTH_SATURATE = 100
CLUSTER_SATURATE = 5

_STATUS_RE = re.compile(r"status=(\w+)")


def _normalize(text):
    """Lowercase, strip punctuation, collapse whitespace. For exact-dup detection."""
    t = re.sub(r"[^\w\s]", " ", (text or "").lower())
    return re.sub(r"\s+", " ", t).strip()


def extract_lesson_lines(lessons_md):
    """Extract accepted lesson claims from rendered markdown.

    Only TERMINAL lessons count for duplicate detection. Non-terminal status
    values — `provisional` (probationary), `legacy` (imported from pre-restructure
    LESSONS.md), and anything superseded — must be skipped so recurrences can
    reach the host agent for re-review, evidence accumulation, or supersession.
    Status is read from the HTML annotation written by render_lessons; visual
    markers (`[PROVISIONAL]`, `~~...~~`) are the fallback for unannotated lines.
    """
    out = []
    for line in (lessons_md or "").splitlines():
        s = line.strip()
        if not s.startswith("- ") or len(s) <= 2:
            continue
        # Primary signal: status in HTML annotation
        if "<!--" in s:
            ann = s.split("<!--", 1)[1]
            m = _STATUS_RE.search(ann)
            if m and m.group(1) != "accepted":
                continue
        text = s[2:].split("<!--")[0].strip()
        # Fallback: visual markers (for pre-existing bullets without annotations)
        if text.startswith("[PROVISIONAL]"):
            continue
        if text.startswith("~~") and text.endswith("~~"):
            continue
        if text:
            out.append(text)
    return out


def check_exact_duplicate(claim, existing_lessons_md):
    """Return lesson lines whose normalized form matches the candidate."""
    nc = _normalize(claim)
    if not nc:
        return []
    return [l for l in extract_lesson_lines(existing_lessons_md)
            if _normalize(l) == nc]


def heuristic_check(candidate, existing_lessons_md=""):
    """Deterministic pre-filter. Takes a candidate dict, not a claim string.

    passed=False means obvious junk: too short, or exact duplicate of a
    lesson already in LESSONS.md. Everything else should reach the host
    agent for real review — overlap != contradiction.

    Returns {passed, confidence, reasons, duplicates}.
      confidence — structural quality hint for reviewer priority only, not a gate.
    """
    claim = (candidate.get("claim") or "").strip()
    reasons, duplicates = [], []

    if len(claim) < MIN_CLAIM_LEN:
        reasons.append("claim_too_short")

    # Content-word gate: raw char length alone let garbage like
    # `!!!!!!!!!!!!!!!!!abc` through. A real lesson needs at least three
    # non-stopword tokens so the reviewer has something substantive to
    # evaluate and retrieval has hooks to score on.
    content_words = word_set(claim)
    if len(content_words) < MIN_CONTENT_WORDS:
        reasons.append(
            f"insufficient_content_words_{len(content_words)}_of_{MIN_CONTENT_WORDS}")

    if claim:
        duplicates = check_exact_duplicate(claim, existing_lessons_md)
        if duplicates:
            reasons.append(f"exact_duplicate_of_{len(duplicates)}_lessons")

    cluster_size = candidate.get("cluster_size", 1)
    length_score = min(1.0, len(claim) / LENGTH_SATURATE)
    size_score = min(1.0, cluster_size / CLUSTER_SATURATE)
    confidence = round(0.5 * length_score + 0.5 * size_score, 3)

    return {
        "passed": not reasons,
        "confidence": confidence,
        "reasons": reasons,
        "duplicates": duplicates,
    }


def validate_candidate(claim_or_candidate, existing_lessons_md="", bootstrap=False):
    """Backwards-compat shim. Old callers passed a claim string; new callers
    pass a candidate dict. bootstrap is accepted but ignored — heuristic
    check has no threshold to loosen."""
    if isinstance(claim_or_candidate, str):
        return heuristic_check({"claim": claim_or_candidate}, existing_lessons_md)
    return heuristic_check(claim_or_candidate, existing_lessons_md)

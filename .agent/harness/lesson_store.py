"""Helpers for reading accepted lessons across shared + branch-local stores."""
import json
import os
import re

from runtime import resolve_runtime, semantic_dirs

_STATUS_RE = re.compile(r"status=(\w+)")


def _norm_claim(claim):
    text = re.sub(r"[^\w\s]", " ", (claim or "").lower())
    return re.sub(r"\s+", " ", text).strip()


def _semantic_sources(runtime_ctx):
    sources = [("shared", runtime_ctx.shared_semantic_path)]
    if runtime_ctx.semantic_path != runtime_ctx.shared_semantic_path:
        sources.append((runtime_ctx.instance_id or "instance", runtime_ctx.semantic_path))
    return sources


def _load_structured(semantic_dir, label):
    path = os.path.join(semantic_dir, "lessons.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            lesson = json.loads(line)
        except json.JSONDecodeError:
            continue
        if lesson.get("status") != "accepted":
            continue
        lesson.setdefault("_source", f"{label}:lessons.jsonl")
        lesson.setdefault("_semantic_dir", semantic_dir)
        out.append(lesson)
    return out


def _load_structured_all(semantic_dir, label):
    """Like _load_structured but returns ALL lessons regardless of status.

    Provisional, retired, and superseded lessons must still be visible to
    duplicate detection — otherwise a provisional lesson can be staged or
    graduated again as a "new" candidate because dedup can't see it.
    """
    path = os.path.join(semantic_dir, "lessons.jsonl")
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            lesson = json.loads(line)
        except json.JSONDecodeError:
            continue
        lesson.setdefault("_source", f"{label}:lessons.jsonl")
        lesson.setdefault("_semantic_dir", semantic_dir)
        out.append(lesson)
    return out


def _load_markdown_fallback_all(semantic_dir, label):
    """Like _load_markdown_fallback but keeps provisional + superseded bullets.

    Mirrors _load_markdown_fallback's parser, minus the status filter — every
    bullet in LESSONS.md becomes a dedup candidate, including [PROVISIONAL]
    and ~~superseded~~ entries that the visible-corpus loader skips.
    """
    path = os.path.join(semantic_dir, "LESSONS.md")
    if not os.path.exists(path):
        return []
    text = open(path).read()
    out = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("- ") or len(s) <= 2:
            continue
        status = "accepted"
        if "<!--" in s:
            ann = s.split("<!--", 1)[1]
            m = _STATUS_RE.search(ann)
            if m:
                status = m.group(1)
        claim = s[2:].split("<!--")[0].strip()
        if claim.startswith("[PROVISIONAL]"):
            claim = claim[len("[PROVISIONAL]"):].strip()
            if status == "accepted":
                status = "provisional"
        if claim.startswith("~~") and claim.endswith("~~"):
            claim = claim[2:-2].strip()
        if claim:
            out.append(
                {
                    "id": None,
                    "claim": claim,
                    "conditions": [],
                    "status": status,
                    "_source": f"{label}:LESSONS.md",
                    "_semantic_dir": semantic_dir,
                }
            )
    return out


def _load_markdown_fallback(semantic_dir, label):
    path = os.path.join(semantic_dir, "LESSONS.md")
    if not os.path.exists(path):
        return []
    text = open(path).read()
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
            out.append(
                {
                    "id": None,
                    "claim": claim,
                    "conditions": [],
                    "status": "accepted",
                    "_source": f"{label}:LESSONS.md",
                    "_semantic_dir": semantic_dir,
                }
            )
    return out


def load_accepted_lessons(runtime_ctx=None):
    """Return accepted lessons visible to the current runtime.

    Shared semantic memory is always the base corpus. Managed instances layer a
    local semantic overlay on top, so later sources win on duplicate claims.
    """
    runtime_ctx = runtime_ctx or resolve_runtime()
    merged = {}
    order = []
    any_structured = False

    for label, semantic_dir in _semantic_sources(runtime_ctx):
        structured = _load_structured(semantic_dir, label)
        if structured:
            any_structured = True
        structured_keys = {_norm_claim(item.get("claim", "")) for item in structured}
        merged_source = list(structured)
        for lesson in _load_markdown_fallback(semantic_dir, label):
            if _norm_claim(lesson.get("claim", "")) not in structured_keys:
                merged_source.append(lesson)

        for lesson in merged_source:
            key = _norm_claim(lesson.get("claim", ""))
            if not key:
                continue
            if key not in merged:
                order.append(key)
            merged[key] = lesson

    lessons = [merged[key] for key in order]
    source_counts = {}
    for lesson in lessons:
        source = lesson.get("_source", "unknown")
        source_counts[source] = source_counts.get(source, 0) + 1
    return lessons, {
        "only_md_available": not any_structured,
        "source_counts": source_counts,
        "semantic_dirs": semantic_dirs(runtime_ctx=runtime_ctx),
    }


def render_visible_lessons_md(runtime_ctx=None):
    """Render the runtime-visible accepted lesson corpus as markdown bullets."""
    lessons, _ = load_accepted_lessons(runtime_ctx=runtime_ctx)
    return "\n".join(
        f"- {lesson.get('claim', '').strip()}  <!-- status=accepted -->"
        for lesson in lessons
        if lesson.get("claim", "").strip()
    )


def _load_all_for_dedup(runtime_ctx=None):
    """Return ALL lessons (any status) across shared + branch-local stores.

    Counterpart to load_accepted_lessons used exclusively for duplicate
    detection. Provisional, retired, and superseded lessons must be visible
    here so a candidate matching one of them is correctly flagged as a
    duplicate instead of slipping through as a "new" lesson.
    """
    runtime_ctx = runtime_ctx or resolve_runtime()
    merged = {}
    order = []

    for label, semantic_dir in _semantic_sources(runtime_ctx):
        structured = _load_structured_all(semantic_dir, label)
        structured_keys = {_norm_claim(item.get("claim", "")) for item in structured}
        merged_source = list(structured)
        for lesson in _load_markdown_fallback_all(semantic_dir, label):
            if _norm_claim(lesson.get("claim", "")) not in structured_keys:
                merged_source.append(lesson)

        for lesson in merged_source:
            key = _norm_claim(lesson.get("claim", ""))
            if not key:
                continue
            if key not in merged:
                order.append(key)
            merged[key] = lesson

    return [merged[key] for key in order]


def render_dedup_text(runtime_ctx=None):
    """Render every lesson — accepted, provisional, retired, superseded — as
    bullets formatted for the heuristic duplicate check.

    Each bullet is annotated with `status=accepted` regardless of the
    underlying lesson's true status. This is intentional: validate.extract_lesson_lines
    treats non-accepted bullets as non-terminal and skips them, which would
    re-introduce the very bug this function exists to fix. From dedup's
    perspective every lesson is "real enough to block a duplicate," so we
    present them as accepted to the substring/extract-line checker. The
    bullet body is just the claim text (no conditions appended) because
    validate._normalize compares the full bullet body — adding extras would
    de-normalize a real-claim duplicate and let it slip through. The HTML
    annotation preserves the true status for any caller that wants to inspect
    it.
    """
    lessons = _load_all_for_dedup(runtime_ctx=runtime_ctx)
    lines = []
    for lesson in lessons:
        claim = (lesson.get("claim") or "").strip()
        if not claim:
            continue
        true_status = lesson.get("status", "accepted")
        lid = lesson.get("id") or ""
        id_part = f" id={lid}" if lid else ""
        lines.append(
            f"- {claim}  "
            f"<!-- status=accepted dedup_true_status={true_status}{id_part} -->"
        )
    return "\n".join(lines)

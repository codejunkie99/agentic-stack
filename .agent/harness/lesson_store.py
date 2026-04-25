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

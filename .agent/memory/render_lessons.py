"""Render semantic/LESSONS.md from structured semantic/lessons.jsonl.

lessons.jsonl is the source of truth. LESSONS.md is a derived view. Graduate.py
and reject.py write to lessons.jsonl and call render_lessons to regenerate
the markdown.

Preserves user content above the sentinel. On first call, the existing
`## Auto-promoted entries will be appended below` line (shipped in the
template) is treated as the sentinel; subsequent calls replace everything
from the sentinel onward. If the sentinel is missing it's appended at the
end of the file. This means hand-curated preambles and seed bullets above
the sentinel survive every render.
"""
import os, json, datetime
from collections import defaultdict


LESSONS_JSONL = "lessons.jsonl"
LESSONS_MD = "LESSONS.md"

SENTINEL = "## Auto-promoted entries will be appended below"


def append_lesson(lesson, semantic_dir):
    """Append a lesson to semantic/lessons.jsonl. Returns the written path."""
    os.makedirs(semantic_dir, exist_ok=True)
    path = os.path.join(semantic_dir, LESSONS_JSONL)
    with open(path, "a") as f:
        f.write(json.dumps(lesson) + "\n")
    return path


def load_lessons(semantic_dir):
    path = os.path.join(semantic_dir, LESSONS_JSONL)
    if not os.path.exists(path):
        return []
    out = []
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _bullet_for(lesson, superseded_by):
    claim = lesson.get("claim", "")
    conf = lesson.get("confidence", "?")
    status = lesson.get("status", "accepted")
    ev = lesson.get("evidence_ids", [])
    lid = lesson.get("id", "?")
    ann = f"status={status} confidence={conf} evidence={len(ev)} id={lid}"
    sup_by = superseded_by.get(lid)
    if sup_by:
        return f"- ~~{claim}~~  <!-- {ann} superseded_by={sup_by} -->"
    if status == "provisional":
        return f"- [PROVISIONAL] {claim}  <!-- {ann} -->"
    return f"- {claim}  <!-- {ann} -->"


def _build_auto_section(lessons):
    superseded_by = {}
    for L in lessons:
        sup = L.get("supersedes")
        if sup:
            superseded_by[sup] = L.get("id")

    groups = defaultdict(list)
    for L in lessons:
        month = (L.get("accepted_at") or "")[:7] or "unknown"
        groups[month].append(L)

    lines = []
    for month in sorted(groups.keys(), reverse=True):
        lines.append(f"### {month}")
        lines.append("")
        for L in groups[month]:
            lines.append(_bullet_for(L, superseded_by))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n" if lines else ""


def render_lessons(semantic_dir):
    """Re-render LESSONS.md. Preserves hand-curated content above the sentinel."""
    lessons = load_lessons(semantic_dir)
    auto_section = _build_auto_section(lessons)

    path = os.path.join(semantic_dir, LESSONS_MD)

    if os.path.exists(path):
        existing = open(path).read()
        if SENTINEL in existing:
            prefix = existing.split(SENTINEL)[0].rstrip()
            new = f"{prefix}\n\n{SENTINEL}\n\n{auto_section}"
        else:
            new = existing.rstrip() + f"\n\n{SENTINEL}\n\n{auto_section}"
    else:
        header = (
            "# Lessons\n\n"
            "> _Auto-managed below. Hand-curated preamble + seed lessons "
            "above the sentinel are preserved across renders._\n"
        )
        new = f"{header}\n{SENTINEL}\n\n{auto_section}"

    os.makedirs(semantic_dir, exist_ok=True)
    with open(path, "w") as f:
        f.write(new)
    return path


def render_lessons_as_text(semantic_dir):
    return open(render_lessons(semantic_dir)).read()


if __name__ == "__main__":
    import sys
    sem = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "semantic")
    path = render_lessons(sem)
    print(f"rendered: {path}")

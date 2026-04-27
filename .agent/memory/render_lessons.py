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

Concurrency: append_lesson and render_lessons both acquire an advisory
exclusive flock on lessons.jsonl so a concurrent appender can't land a new
row between render's load and write, leaving LESSONS.md stale. LESSONS.md
is rewritten atomically (temp file + rename) so readers never see a
half-written file. Windows (no fcntl) falls through without locking; safe
for single-user, noted in a one-time warning.
"""
import os, json, datetime, hashlib, warnings
from collections import defaultdict
from contextlib import contextmanager


LESSONS_JSONL = "lessons.jsonl"
LESSONS_MD = "LESSONS.md"

SENTINEL = "## Auto-promoted entries will be appended below"


try:
    import fcntl
    _HAS_FLOCK = True
except ImportError:
    _HAS_FLOCK = False
    warnings.warn(
        "fcntl unavailable; lessons.jsonl concurrent-write protection "
        "disabled. Safe for single-user repos; not safe for shared/multi-"
        "process access.",
        RuntimeWarning,
        stacklevel=2,
    )


@contextmanager
def _locked_jsonl(path):
    """Open lessons.jsonl with an advisory exclusive flock held for the scope.

    Creates the file if missing ('a+' mode, which also permits read). The
    lock is process-level on Unix via fcntl.flock — two appenders serialize,
    and a render() call wrapping its entire read-render-write cycle in this
    lock blocks concurrent appenders until the render is done. Windows falls
    through without locking (see module-level warning).

    Note: within a single process, opening the same path twice yields two
    separate fds with separate flock states, so nesting `_locked_jsonl`
    around another `_locked_jsonl` in the same thread will deadlock. Call
    `_append_lesson_unlocked(fd, lesson)` instead when already inside a
    lock (e.g. migrate_legacy_bullets is deliberately called OUTSIDE the
    render lock to sidestep this).
    """
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    f = open(path, "a+")
    try:
        if _HAS_FLOCK:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
    finally:
        if _HAS_FLOCK:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            except OSError:
                # Release-on-close is the kernel default; swallowing a late
                # release failure doesn't leak the lock.
                pass
        f.close()


def _append_lesson_unlocked(f, lesson):
    """Write a lesson row to an already-open, already-locked jsonl file.

    Use this only when you already hold the lock (via `_locked_jsonl`).
    Seeks to end first because 'a+' mode tracks position across reads
    and the caller may have read from the head.
    """
    f.seek(0, os.SEEK_END)
    f.write(json.dumps(lesson) + "\n")
    f.flush()


def append_lesson(lesson, semantic_dir):
    """Append a lesson to semantic/lessons.jsonl. Returns the written path."""
    os.makedirs(semantic_dir, exist_ok=True)
    path = os.path.join(semantic_dir, LESSONS_JSONL)
    with _locked_jsonl(path) as f:
        _append_lesson_unlocked(f, lesson)
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
    # Only accepted supersessions flip the old lesson to strikethrough.
    # A provisional --supersedes would otherwise blank the active lesson
    # before its replacement has been accepted, leaving no active guidance
    # on that topic at all (retrieval skips both provisional and
    # strikethrough).
    superseded_by = {}
    for L in lessons:
        if L.get("status") != "accepted":
            continue
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


def migrate_legacy_bullets(semantic_dir):
    """Import any bullets below the sentinel not yet in lessons.jsonl.

    Upgrade safety: installations that ran the old markdown-only promotion
    have auto-promoted bullets below the sentinel. Without this pass, the
    first call to render_lessons with an empty lessons.jsonl would rewrite
    LESSONS.md with an empty auto-section and lose all of them silently.
    Migrated entries land with status='legacy' so they're visually distinct
    and can be reviewed + superseded by the host agent later.
    """
    md_path = os.path.join(semantic_dir, LESSONS_MD)
    if not os.path.exists(md_path):
        return 0
    content = open(md_path).read()
    if SENTINEL not in content:
        return 0

    below = content.split(SENTINEL, 1)[1]
    bullets = []
    for line in below.splitlines():
        s = line.strip()
        if not s.startswith("- ") or len(s) <= 2:
            continue
        text = s[2:].split("<!--")[0].strip()
        # Skip superseded entries — they're historical, not content to re-ingest
        if text.startswith("~~") and text.endswith("~~"):
            continue
        # Strip provisional prefix if present
        if text.startswith("[PROVISIONAL]"):
            text = text[len("[PROVISIONAL]"):].strip()
        if text:
            bullets.append(text)

    if not bullets:
        return 0

    existing_claims = {(L.get("claim") or "").strip().lower()
                       for L in load_lessons(semantic_dir)}
    try:
        accepted_at = datetime.datetime.fromtimestamp(
            os.path.getmtime(md_path), tz=datetime.timezone.utc).isoformat()
    except OSError:
        accepted_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    migrated = 0
    for claim in bullets:
        if claim.strip().lower() in existing_claims:
            continue
        lid = "lesson_legacy_" + hashlib.md5(claim.lower().encode()).hexdigest()[:12]
        lesson = {
            "id": lid, "claim": claim,
            "conditions": [], "evidence_ids": [],
            "status": "legacy", "accepted_at": accepted_at,
            "reviewer": "render_lessons_migration",
            "rationale": "Imported from pre-restructure LESSONS.md bullets below sentinel",
            "cluster_size": 1, "canonical_salience": 5.0,
            "confidence": 0.7, "support_count": 0, "contradiction_count": 0,
            "supersedes": None, "source_candidate": None,
        }
        append_lesson(lesson, semantic_dir)
        existing_claims.add(claim.strip().lower())
        migrated += 1
    return migrated


def _dedupe_by_id(lessons):
    """Keep the latest entry per lesson id.

    lessons.jsonl is append-only, so a provisional→accepted state transition
    writes two rows with the same id. The render should show only the latest
    state for each lesson; the jsonl is preserved for audit.
    """
    latest = {}
    order = []
    for L in lessons:
        lid = L.get("id")
        if not lid:
            # No id? Treat as-is, keyed by its position so we keep it.
            lid = f"_anon_{len(order)}"
        if lid not in latest:
            order.append(lid)
        latest[lid] = L
    return [latest[lid] for lid in order]


def render_lessons(semantic_dir):
    """Re-render LESSONS.md. Preserves hand-curated content above the sentinel.

    Auto-migrates legacy auto-promoted bullets below the sentinel into
    lessons.jsonl before rendering, so upgrades from the old markdown-only
    format don't silently erase past promotions. Deduplicates entries by
    lesson id so a provisional-then-accepted lesson renders once, not twice.

    Concurrency-safe: the entire read-render-write cycle runs under an
    exclusive flock on lessons.jsonl. A concurrent append_lesson() either
    lands BEFORE our load (we include it) or AFTER our write (it blocks
    on the flock, then will re-render on its own — graduate.py calls
    render_lessons right after appending). LESSONS.md is rewritten
    atomically via temp file + rename so readers never see a half-written
    file.
    """
    # Migrate BEFORE taking the render lock. migrate_legacy_bullets calls
    # append_lesson internally, which acquires its own lock; nesting would
    # deadlock (two fds on the same file within one process each want
    # LOCK_EX). Migration is idempotent and only does real work on first
    # run after an upgrade, so the ordering is safe.
    migrate_legacy_bullets(semantic_dir)

    jsonl_path = os.path.join(semantic_dir, LESSONS_JSONL)
    md_path = os.path.join(semantic_dir, LESSONS_MD)

    os.makedirs(semantic_dir, exist_ok=True)

    with _locked_jsonl(jsonl_path):
        lessons = _dedupe_by_id(load_lessons(semantic_dir))
        auto_section = _build_auto_section(lessons)

        if os.path.exists(md_path):
            existing = open(md_path).read()
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

        # Atomic rewrite: write to .tmp next to the target, then rename.
        # os.replace is atomic on POSIX and Windows (Python 3.3+), so a
        # reader of LESSONS.md always sees either the old or the new
        # complete content, never a half-written file.
        tmp_path = md_path + ".tmp"
        with open(tmp_path, "w") as f:
            f.write(new)
        os.replace(tmp_path, md_path)

    return md_path


def render_lessons_as_text(semantic_dir):
    return open(render_lessons(semantic_dir)).read()


if __name__ == "__main__":
    import sys
    sem = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "semantic")
    path = render_lessons(sem)
    print(f"rendered: {path}")

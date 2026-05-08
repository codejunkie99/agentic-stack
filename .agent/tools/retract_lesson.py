"""Retract an accepted lesson from semantic memory.

This is an append-only transition: a new row with the same lesson id is
written to lessons.jsonl with status='retracted'. LESSONS.md is then
re-rendered from the structured source of truth.
"""
import argparse
import datetime
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from render_lessons import append_lesson, load_lessons, render_lessons

SEMANTIC = os.path.join(BASE, "memory/semantic")


def _latest_by_id(lesson_id, lessons):
    latest = None
    for lesson in lessons:
        if lesson.get("id") == lesson_id:
            latest = lesson
    return latest


def retract_lesson(lesson_id, rationale, reviewer="host-agent", semantic_dir=SEMANTIC):
    if not str(rationale or "").strip():
        raise ValueError("retraction rationale is required")

    lessons = load_lessons(semantic_dir)
    latest = _latest_by_id(lesson_id, lessons)
    if latest is None:
        raise ValueError(f"lesson not found: {lesson_id}")

    status = latest.get("status")
    if status != "accepted":
        raise ValueError(
            f"lesson {lesson_id} is not retractable (current status: {status})"
        )

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    updated = {
        **latest,
        "status": "retracted",
        "retracted_at": now,
        "retracted_by": reviewer,
        "retraction_rationale": rationale,
    }

    append_lesson(updated, semantic_dir)
    md_path = render_lessons(semantic_dir)
    return updated, md_path


def main():
    parser = argparse.ArgumentParser(
        description="Retract an accepted lesson by lesson id."
    )
    parser.add_argument("lesson_id")
    parser.add_argument(
        "--rationale",
        required=True,
        help="Why this lesson should stop guiding future decisions.",
    )
    parser.add_argument("--reviewer", default="host-agent")
    args = parser.parse_args()

    try:
        lesson, md_path = retract_lesson(
            lesson_id=args.lesson_id,
            rationale=args.rationale,
            reviewer=args.reviewer,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"retracted {args.lesson_id}")
    print(f"status: {lesson.get('status')}")
    print(f"re-rendered: {md_path}")


if __name__ == "__main__":
    main()

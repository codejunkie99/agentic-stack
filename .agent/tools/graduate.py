"""Graduate a staged candidate to semantic memory.

The host agent reviews a candidate, decides it's worth keeping, and calls
this tool with a rationale. A heuristic re-check (length + exact duplicate
against current LESSONS.md) runs automatically so last-minute issues get
caught. The rationale is REQUIRED — rubber-stamped promotions are the
whole failure mode this layer is designed to prevent.
"""
import os, sys, json, argparse, hashlib

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from review_state import mark_graduated
from validate import heuristic_check
from render_lessons import append_lesson, render_lessons

CANDIDATES = os.path.join(BASE, "memory/candidates")
SEMANTIC = os.path.join(BASE, "memory/semantic")


def _lesson_id(candidate):
    claim = (candidate.get("claim") or "").strip().lower()
    return "lesson_" + hashlib.md5(claim.encode()).hexdigest()[:12]


def main():
    p = argparse.ArgumentParser(description="Graduate a staged candidate.")
    p.add_argument("candidate_id")
    p.add_argument("--rationale", required=True,
                   help="Why this lesson should be accepted. Required, not optional.")
    p.add_argument("--reviewer", default="host-agent")
    p.add_argument("--provisional", action="store_true",
                   help="Accept as provisional (probationary) rather than full.")
    p.add_argument("--supersedes", default=None,
                   help="ID of an existing lesson this replaces.")
    args = p.parse_args()

    cand_path = os.path.join(CANDIDATES, f"{args.candidate_id}.json")
    if not os.path.exists(cand_path):
        print(f"ERROR: candidate not found: {args.candidate_id}", file=sys.stderr)
        sys.exit(1)
    with open(cand_path) as f:
        cand = json.load(f)

    lessons_md = os.path.join(SEMANTIC, "LESSONS.md")
    existing = open(lessons_md).read() if os.path.exists(lessons_md) else ""
    check = heuristic_check(cand, existing)
    if not check["passed"]:
        print(f"ERROR: candidate fails heuristic check: {check['reasons']}",
              file=sys.stderr)
        sys.exit(2)

    graduated = mark_graduated(
        args.candidate_id, args.reviewer, args.rationale, CANDIDATES,
        provisional=args.provisional,
    )

    lesson = {
        "id": _lesson_id(cand),
        "claim": cand.get("claim"),
        "conditions": cand.get("conditions", []),
        "evidence_ids": cand.get("evidence_ids", []),
        "status": "provisional" if args.provisional else "accepted",
        "accepted_at": graduated.get("accepted_at"),
        "reviewer": args.reviewer,
        "rationale": args.rationale,
        "cluster_size": cand.get("cluster_size", 1),
        "canonical_salience": cand.get("canonical_salience", 0.0),
        "confidence": check["confidence"],
        "support_count": 0,
        "contradiction_count": 0,
        "supersedes": args.supersedes,
        "source_candidate": args.candidate_id,
    }
    append_lesson(lesson, SEMANTIC)
    md_path = render_lessons(SEMANTIC)

    print(f"graduated {args.candidate_id} → lesson {lesson['id']}")
    print(f"re-rendered: {md_path}")


if __name__ == "__main__":
    main()

"""Graduate a staged candidate to semantic memory.

The host agent reviews a candidate, decides it's worth keeping, and calls
this tool with a rationale. A heuristic re-check (length + exact duplicate
against current LESSONS.md) runs automatically so last-minute issues get
caught. The rationale is REQUIRED — rubber-stamped promotions are the
whole failure mode this layer is designed to prevent.
"""
import os, sys, json, argparse, hashlib, datetime

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from review_state import mark_graduated
from validate import heuristic_check
from render_lessons import append_lesson, render_lessons, load_lessons

CANDIDATES = os.path.join(BASE, "memory/candidates")
SEMANTIC = os.path.join(BASE, "memory/semantic")


def _lesson_id(candidate):
    """1:1 with the candidate's own id (claim + conditions, stable).

    Using md5(claim) alone collides when two distinct patterns happen to
    share canonical text — different clusters about different situations
    with the same "the test failed" reflection, etc. Keying off the
    candidate id keeps them distinct and matches how write_candidates
    identifies the pattern lifecycle.
    """
    cid = candidate.get("id") or ""
    if cid:
        return f"lesson_{cid}"
    # Fallback for older candidate dicts without `id`
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

    lesson_id = _lesson_id(cand)

    # Retry-safety: if a prior graduation run got as far as appending to
    # lessons.jsonl but crashed before the candidate move, the staged file
    # still exists and the lesson is already recorded. Heuristic check
    # would otherwise reject the retry as an exact duplicate of its own
    # prior output, leaving the candidate stuck. Detect and complete the
    # move without re-appending.
    prior_lesson = next(
        (l for l in load_lessons(SEMANTIC) if l.get("id") == lesson_id),
        None,
    )
    if prior_lesson:
        print(f"retry detected: lesson {lesson_id} already in lessons.jsonl; "
              f"completing candidate move")
        mark_graduated(
            args.candidate_id, args.reviewer, args.rationale, CANDIDATES,
            provisional=args.provisional,
        )
        print(f"graduated {args.candidate_id} → lesson {lesson_id} (retry)")
        return

    lessons_md = os.path.join(SEMANTIC, "LESSONS.md")
    existing = open(lessons_md).read() if os.path.exists(lessons_md) else ""
    # When superseding, exclude the target lesson from the duplicate check —
    # replacing a lesson with structurally-better content but same wording
    # is exactly what supersession is for.
    if args.supersedes:
        existing = "\n".join(
            line for line in existing.splitlines()
            if f"id={args.supersedes}" not in line
        )
    check = heuristic_check(cand, existing)
    if not check["passed"]:
        print(f"ERROR: candidate fails heuristic check: {check['reasons']}",
              file=sys.stderr)
        sys.exit(2)

    # Atomicity: write to semantic memory BEFORE moving the candidate.
    # If we crash mid-graduation, the staged candidate remains and the
    # reviewer can retry. The retry-safety block above catches the
    # specific "lesson appended but candidate not moved" scenario.
    accepted_at = datetime.datetime.now().isoformat()
    lesson = {
        "id": lesson_id,
        "claim": cand.get("claim"),
        "conditions": cand.get("conditions", []),
        "evidence_ids": cand.get("evidence_ids", []),
        "status": "provisional" if args.provisional else "accepted",
        "accepted_at": accepted_at,
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

    # Semantic writes survived — now move the candidate file.
    mark_graduated(
        args.candidate_id, args.reviewer, args.rationale, CANDIDATES,
        provisional=args.provisional,
    )

    print(f"graduated {args.candidate_id} → lesson {lesson['id']}")
    print(f"re-rendered: {md_path}")


if __name__ == "__main__":
    main()

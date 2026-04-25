"""Graduate a staged candidate to semantic memory.

The host agent reviews a candidate, decides it's worth keeping, and calls
this tool with a rationale. A heuristic re-check (length + exact duplicate
against current LESSONS.md) runs automatically so last-minute issues get
caught. The rationale is REQUIRED — rubber-stamped promotions are the
whole failure mode this layer is designed to prevent.
"""
import os, sys, json, argparse, hashlib, datetime, re
from pathlib import Path

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(BASE, "memory"))

from review_state import mark_graduated
from validate import heuristic_check
from render_lessons import append_lesson, render_lessons, load_lessons

CANDIDATES = os.path.join(BASE, "memory/candidates")
SEMANTIC = os.path.join(BASE, "memory/semantic")

# Candidate IDs come from sys.argv (CLI-supplied, untrusted). Without
# validation, a value like "../../etc/passwd" or "../some/path" gets joined
# straight into a filesystem path, letting a caller read or move JSON files
# outside the candidate directory. Use the same regex the sister
# review_state._validate_candidate_id uses so the two layers stay in sync.
_CANDIDATE_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,128}$")


def _local_validate_candidate_id(cid):
    """Reject anything that isn't a plain candidate id token.

    Path separators, traversal segments, NULs, and the like are all
    excluded by the alphanumeric/underscore/hyphen character class.
    """
    if not isinstance(cid, str) or not _CANDIDATE_ID_RE.match(cid):
        raise ValueError(
            f"invalid candidate_id: {cid!r} (must match "
            f"{_CANDIDATE_ID_RE.pattern})"
        )
    return cid


# Prefer the sister implementation if it's been landed in review_state, so
# the two stay aligned (same regex, identical semantics). Fall back to the
# local copy when the import doesn't resolve — the sister agent may still
# be in flight, and we don't want graduate.py to break if review_state has
# nothing exported yet. The import is a best-effort lookup, not a hard
# dependency on a public name.
try:
    from review_state import _validate_candidate_id as _imported_validator
    validate_candidate_id = _imported_validator
except ImportError:
    validate_candidate_id = _local_validate_candidate_id


def _safe_candidate_path(candidates_dir, cid):
    """Build the candidate JSON path and assert it stays inside the dir.

    Even after the regex check, run a realpath containment check so any
    surprise (symlink in candidates_dir, weird OS handling) still can't
    let the resolved path escape the candidates root.
    """
    validate_candidate_id(cid)
    root = Path(candidates_dir).resolve()
    cand_path = (Path(candidates_dir) / f"{cid}.json").resolve()
    try:
        cand_path.relative_to(root)
    except ValueError:
        raise ValueError(
            f"candidate path escapes candidates dir: {cand_path} not under {root}"
        )
    return str(cand_path)


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

    # Validate the CLI-supplied id at the boundary — before it's used in
    # any path. A bad id (e.g. "../some/path") otherwise gets joined into
    # CANDIDATES and lets the caller read or move JSON outside the
    # candidate directory.
    try:
        validate_candidate_id(args.candidate_id)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(4)

    # Build the candidate path with a realpath containment check on top of
    # the regex, in case symlinks or unusual filesystems shift the resolved
    # location outside CANDIDATES.
    try:
        cand_path = _safe_candidate_path(CANDIDATES, args.candidate_id)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(4)
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

        # Guard: lessons.jsonl row must carry the metadata we're about to
        # sync into the candidate file. A legacy / hand-edited / sparse row
        # missing reviewer or rationale would otherwise get silently mixed
        # with retry args (candidate gets args.*, jsonl stays missing) —
        # the exact drift this branch exists to prevent.
        missing_fields = [
            f for f in ("reviewer", "rationale")
            if not prior_lesson.get(f)
        ]
        if missing_fields:
            print(
                f"ERROR: cannot complete retry — lessons.jsonl row "
                f"{lesson_id} is missing {missing_fields}. This is a "
                f"legacy or hand-edited row. Fix it manually (add the "
                f"missing fields) and re-run, or delete the staged "
                f"candidate to start fresh.",
                file=sys.stderr,
            )
            sys.exit(3)

        # Re-render LESSONS.md too. The first attempt could have crashed
        # between append_lesson() and render_lessons(), leaving lessons.jsonl
        # and the rendered LESSONS.md out of sync. Idempotent: if they're
        # already in sync, this is a no-op write of the same content.
        md_path = render_lessons(SEMANTIC)

        # Use the ORIGINAL reviewer/rationale/provisional-flag from the
        # prior lesson, not the retry invocation's args. The retry is
        # finishing the first decision, not making a new one. The guard
        # above ensures prior_lesson has non-empty reviewer + rationale.
        retry_reviewer = prior_lesson["reviewer"]
        retry_rationale = prior_lesson["rationale"]
        retry_provisional = (prior_lesson.get("status") == "provisional")

        diffs = []
        if retry_reviewer != args.reviewer:
            diffs.append(f"reviewer: {args.reviewer!r} → {retry_reviewer!r}")
        if retry_provisional != args.provisional:
            diffs.append(
                f"provisional: {args.provisional} → {retry_provisional}"
            )
        if retry_rationale != args.rationale:
            diffs.append(
                "rationale: overridden (see first-run text in lessons.jsonl)"
            )
        if diffs:
            print(
                f"note: retry invocation metadata differs from the "
                f"first-run record in lessons.jsonl. Honoring the "
                f"original values so lessons.jsonl and the candidate "
                f"file stay in sync:\n  "
                + "\n  ".join(diffs),
                file=sys.stderr,
            )

        # Re-validate before lifecycle movement. Defense in depth — even
        # though the entry-point check has already run, mark_graduated
        # joins the id into a path inside review_state, and we don't want
        # to depend on the sister module having its own check landed yet.
        validate_candidate_id(args.candidate_id)
        mark_graduated(
            args.candidate_id, retry_reviewer, retry_rationale, CANDIDATES,
            provisional=retry_provisional,
        )
        print(f"graduated {args.candidate_id} → lesson {lesson_id} (retry)")
        print(f"re-rendered: {md_path}")
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

    # Semantic writes survived — now move the candidate file. Re-validate
    # the id at this second path-construction site so an inadvertent
    # mutation between the entry check and here can't slip through.
    validate_candidate_id(args.candidate_id)
    mark_graduated(
        args.candidate_id, args.reviewer, args.rationale, CANDIDATES,
        provisional=args.provisional,
    )

    print(f"graduated {args.candidate_id} → lesson {lesson['id']}")
    print(f"re-rendered: {md_path}")


if __name__ == "__main__":
    main()

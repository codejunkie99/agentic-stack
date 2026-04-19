"""One-shot lesson teaching.

    python3 .agent/tools/learn.py "Always serialize timestamps in UTC" \\
        --rationale "prior bugs from mixed local/UTC comparisons"

Stages a candidate and graduates it in a single command. Removes the
stage-then-graduate ceremony for the common case: you already know the
lesson, you just want the agent to know it too.

The candidate id comes from the shared `cluster.pattern_id` helper (same
algorithm auto-dream uses) so repeat calls are idempotent within the manual
path: same claim + same conditions → same id → safe retry. IDs will differ
from auto-dream's ids for the same claim because auto-dream infers
conditions from a cluster's common vocabulary, not from the claim alone;
that's intentional (different birth paths, different context).

If graduation fails (e.g., exact-duplicate heuristic reject), the staged
candidate file is removed so `show.py` / `REVIEW_QUEUE.md` don't show
orphaned dead-ends.
"""
import argparse, datetime, json, os, subprocess, sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CANDIDATES = os.path.join(BASE, "memory/candidates")
sys.path.insert(0, os.path.join(BASE, "harness"))
sys.path.insert(0, os.path.join(BASE, "memory"))
from text import word_set  # noqa: E402
from cluster import pattern_id  # noqa: E402


def _lesson_already_appended(cid):
    """Did graduate.py get as far as writing the lesson to lessons.jsonl?

    Read-only probe. If the lesson_<cid> row is present, graduate.py's
    retry-safety path will complete the move on the next run — the staged
    candidate file MUST stay put for that to work.
    """
    lessons_path = os.path.join(BASE, "memory/semantic/lessons.jsonl")
    if not os.path.exists(lessons_path):
        return False
    target = f"lesson_{cid}"
    try:
        for line in open(lessons_path):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("id") == target:
                return True
    except OSError:
        return False
    return False


def stage(claim, conditions, source="learn", importance=7):
    os.makedirs(CANDIDATES, exist_ok=True)
    cid = pattern_id(claim, conditions)
    now = datetime.datetime.now().isoformat()
    candidate = {
        "id": cid,
        "key": f"manual_{cid[:6]}",
        "name": f"manual_{cid[:6]}",
        "claim": claim,
        "conditions": sorted(conditions),
        "evidence_ids": [now],
        "cluster_size": 1,
        # Manual lessons skip the promotion threshold — they're author-attested,
        # not pattern-extracted. Set salience high enough that retrieval ranks
        # them alongside auto-promoted entries.
        "canonical_salience": 8.0,
        "staged_at": now,
        "status": "staged",
        "decisions": [{"ts": now, "action": "staged", "reviewer": source}],
        "rejection_count": 0,
    }
    path = os.path.join(CANDIDATES, f"{cid}.json")
    with open(path, "w") as f:
        json.dump(candidate, f, indent=2)
    return cid, path


def main():
    p = argparse.ArgumentParser(
        description="Teach the agent a lesson in one command.")
    p.add_argument("claim", help="The lesson, phrased as a rule or principle.")
    p.add_argument("--rationale", default=None,
                   help="Why this lesson holds. Recommended. If omitted, a "
                        "timestamp-only rationale is used.")
    p.add_argument("--conditions", nargs="*", default=None,
                   help="Optional trigger keywords. Inferred from claim words "
                        "if omitted.")
    p.add_argument("--provisional", action="store_true",
                   help="Graduate as provisional (probationary) — safer for "
                        "experimental rules.")
    p.add_argument("--stage-only", action="store_true",
                   help="Stage the candidate but don't auto-graduate. Useful "
                        "if you want a reviewer to see it first.")
    args = p.parse_args()

    claim = args.claim.strip()
    if len(claim) < 20:
        print(f"ERROR: claim too short ({len(claim)} chars, need >=20). "
              f"Heuristic check would reject this.", file=sys.stderr)
        sys.exit(2)

    conditions = args.conditions
    if conditions is None:
        # Infer conditions from ALL content words in the claim (stopwords
        # stripped by word_set). No truncation — truncation broke id
        # determinism for long claims and drifted from the auto-dream path
        # in ways Codex caught. Fixed list here is the stable signature.
        conditions = sorted(word_set(claim))

    cid, path = stage(claim, conditions)
    print(f"staged candidate {cid}")
    print(f"  path: {path}")
    print(f"  conditions: {conditions}")

    if args.stage_only:
        print("\n(stopping here — run graduate.py to accept)")
        return

    rationale = args.rationale or f"manual via learn.py at {datetime.datetime.now().isoformat()}"
    grad_args = [
        sys.executable,
        os.path.join(BASE, "tools", "graduate.py"),
        cid,
        "--rationale", rationale,
        "--reviewer", "learn.py",
    ]
    if args.provisional:
        grad_args.append("--provisional")
    result = subprocess.run(grad_args, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"\nERROR: graduation failed (exit {result.returncode})",
              file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        # Decide whether the staged file is safe to delete:
        #   graduate.py's flow is (a) heuristic_check (b) append_lesson
        #   (c) render_lessons (d) mark_graduated.
        # Safe to delete only when we KNOW we're in state (a) — a clean
        # heuristic rejection, nothing written downstream. That's exit
        # code 2 per graduate.py:94. For any other nonzero exit (1,
        # crash, signal, unhandled exception), we can't be sure the
        # lesson wasn't partially written, so preserve the staged file
        # for manual inspection and a retry via graduate.py.
        lesson_written = _lesson_already_appended(cid)
        is_heuristic_reject = (result.returncode == 2 and not lesson_written)
        if os.path.isfile(path) and is_heuristic_reject:
            try:
                os.remove(path)
                print(f"(cleaned up orphaned candidate at {path})",
                      file=sys.stderr)
            except OSError:
                pass
        elif lesson_written:
            print(
                f"(preserved staged file {path} — lesson_{cid} already in "
                f"lessons.jsonl; re-run graduate.py to complete the move)",
                file=sys.stderr)
        else:
            print(
                f"(preserved staged file {path} — graduation exited {result.returncode} "
                f"pre-append; inspect or re-run graduate.py, then delete "
                f"manually if unrecoverable)",
                file=sys.stderr)
        sys.exit(result.returncode)
    print("\n" + result.stdout.strip())


if __name__ == "__main__":
    main()

"""Staging-only dream cycle. Mechanical work, no reasoning.

Responsibilities (in order):
  1. load episodic entries
  2. cluster + extract → structured patterns
  3. stage candidates (lifecycle metadata baked in)
  4. heuristic prefilter (length + exact-duplicate; obvious junk goes to rejected/)
  5. decay old episodes + archive stale workspace
  6. write REVIEW_QUEUE.md summary so the next host session sees the backlog

Never:
  - subjective validation (host agent reviews via CLI tools)
  - promotion to LESSONS.md (graduate.py does that)
  - git commit (unattended repo writes are dangerous on a host hook)
"""
import json, os
from promote import cluster_and_extract, write_candidates
from validate import heuristic_check
from review_state import mark_rejected, write_review_queue_summary
from decay import decay_old_entries
from archive import archive_stale_workspace

ROOT = os.path.abspath(os.path.dirname(__file__))
EPISODIC = os.path.join(ROOT, "episodic/AGENT_LEARNINGS.jsonl")
CANDIDATES = os.path.join(ROOT, "candidates")
SEMANTIC = os.path.join(ROOT, "semantic")
REVIEW_QUEUE = os.path.join(ROOT, "working/REVIEW_QUEUE.md")
PROMOTION_THRESHOLD = 7.0
CLUSTER_SIMILARITY = 0.3


def _load_entries():
    if not os.path.exists(EPISODIC):
        return []
    entries = []
    for line in open(EPISODIC):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _write_entries(entries):
    with open(EPISODIC, "w") as f:
        for e in entries:
            f.write(json.dumps(e) + "\n")


def _heuristic_prefilter(candidates_dir, semantic_dir):
    """Move obvious junk (too-short, exact duplicate) to rejected/ automatically.

    Anything subjective — "is this really a useful lesson?" — is the host
    agent's call, not this function's.
    """
    if not os.path.isdir(candidates_dir):
        return 0
    lessons_path = os.path.join(semantic_dir, "LESSONS.md")
    existing = open(lessons_path).read() if os.path.exists(lessons_path) else ""
    rejected = 0
    for fname in sorted(os.listdir(candidates_dir)):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(candidates_dir, fname)
        if not os.path.isfile(path):
            continue
        try:
            with open(path) as f:
                cand = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        check = heuristic_check(cand, existing)
        if not check["passed"]:
            reason = ", ".join(check["reasons"])
            # Record the specific lesson(s) that triggered the duplicate
            # rejection so write_candidates can check whether THIS blocker
            # is still there, not just whether LESSONS.md as a whole changed.
            mark_rejected(cand["id"], "heuristic_prefilter", reason,
                          candidates_dir,
                          duplicate_claims=check.get("duplicates", []))
            rejected += 1
    return rejected


def run_dream_cycle():
    entries = _load_entries()
    if not entries:
        # Still refresh the review queue — candidates may have been staged in
        # a previous cycle and the host agent loads REVIEW_QUEUE.md into every
        # session via build_context, so a stale/missing file hides real work.
        pending = write_review_queue_summary(CANDIDATES, REVIEW_QUEUE)
        print(f"dream cycle: no entries (queue has {pending} pending)")
        return

    patterns = cluster_and_extract(entries, threshold=CLUSTER_SIMILARITY)
    promotable = {k: p for k, p in patterns.items()
                  if p.get("canonical_salience", 0) >= PROMOTION_THRESHOLD}

    staged = write_candidates(promotable, CANDIDATES)
    prefiltered = _heuristic_prefilter(CANDIDATES, SEMANTIC)

    kept, archived = decay_old_entries(
        entries, archive_dir=os.path.join(ROOT, "episodic/snapshots"))
    _write_entries(kept)
    archive_stale_workspace(
        working_dir=os.path.join(ROOT, "working"),
        archive_dir=os.path.join(ROOT, "episodic/snapshots"))

    pending = write_review_queue_summary(CANDIDATES, REVIEW_QUEUE)

    print(
        f"dream cycle: patterns={len(patterns)} staged={staged} "
        f"prefiltered_out={prefiltered} pending_review={pending} "
        f"archived={len(archived)} kept={len(kept)}"
    )


if __name__ == "__main__":
    run_dream_cycle()

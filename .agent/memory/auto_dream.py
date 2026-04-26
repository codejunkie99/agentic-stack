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
import json, os, sys
from promote import cluster_and_extract, write_candidates
from validate import heuristic_check
from review_state import mark_rejected, write_review_queue_summary
from decay import decay_old_entries
from archive import archive_stale_workspace

_HARNESS = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "harness"))
if _HARNESS not in sys.path:
    sys.path.insert(0, _HARNESS)
from lesson_store import render_dedup_text

ROOT = os.path.abspath(os.path.dirname(__file__))
EPISODIC = os.path.join(ROOT, "episodic/AGENT_LEARNINGS.jsonl")
CANDIDATES = os.path.join(ROOT, "candidates")
SEMANTIC = os.path.join(ROOT, "semantic")
REVIEW_QUEUE = os.path.join(ROOT, "working/REVIEW_QUEUE.md")
PROMOTION_THRESHOLD = 7.0
CLUSTER_SIMILARITY = 0.3


def _load_entries(report_malformed=False):
    """Load episodic entries from the JSONL log.

    Skips malformed lines so a single bad append (interrupted writer, manual
    edit, partial flush) can't break the whole pipeline. When
    ``report_malformed`` is True, returns ``(entries, malformed)`` where
    ``malformed`` is a list of ``(line_number, raw_line)`` tuples — this lets
    the caller log a stderr warning so we don't lose visibility into
    corruption.
    """
    if not os.path.exists(EPISODIC):
        return ([], []) if report_malformed else []
    entries = []
    malformed = []
    with open(EPISODIC) as fh:
        for lineno, raw in enumerate(fh, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                malformed.append((lineno, raw.rstrip("\n")))
                continue
    if report_malformed:
        return entries, malformed
    return entries


def _write_entries(entries, path=None):
    """Atomically rewrite the episodic log.

    The episodic log can be appended to by host hooks at any moment, so a
    direct truncate-and-write is dangerous: a crash, disk-full, or concurrent
    append mid-rewrite can leave us with a half-written file (or empty file)
    and zero record of the prior state.

    Strategy:
      1. Snapshot the current file to ``<path>.bak`` so we have one
         revision of recovery if both the new write AND the rename
         somehow corrupt the live file.
      2. Write the new contents to ``<path>.tmp``, fsync, then
         ``os.replace`` it onto the live path. ``os.replace`` is atomic
         on POSIX and Windows — readers either see the old file or the
         new file, never a half-written one.
      3. If anything raises mid-write, clean up the temp file. The
         original is untouched (we never opened it for writing) and the
         ``.bak`` from step 1 is also intact.
    """
    target = path if path is not None else EPISODIC
    tmp = target + ".tmp"
    bak = target + ".bak"

    # Step 1: snapshot prior state to .bak (best-effort; if there's no live
    # file yet, there's nothing to back up).
    if os.path.exists(target):
        try:
            with open(target, "rb") as src, open(bak, "wb") as dst:
                dst.write(src.read())
                dst.flush()
                os.fsync(dst.fileno())
        except OSError as e:
            # If we can't make a backup, surface the failure rather than
            # silently rewriting without one.
            raise OSError(f"could not snapshot {target} to {bak}: {e}") from e

    # Step 2: write new contents to a temp file, then atomically replace.
    try:
        with open(tmp, "w") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, target)
    except BaseException:
        # Step 3: cleanup. Original file is intact (we never touched it for
        # writing) and .bak still mirrors prior state. Re-raise so the caller
        # sees the failure.
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except OSError:
            pass
        raise


def _heuristic_prefilter(candidates_dir, semantic_dir):
    """Move obvious junk (too-short, exact duplicate) to rejected/ automatically.

    Anything subjective — "is this really a useful lesson?" — is the host
    agent's call, not this function's.
    """
    if not os.path.isdir(candidates_dir):
        return 0
    lessons_path = os.path.join(semantic_dir, "LESSONS.md")
    existing = render_dedup_text()
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
    entries, malformed = _load_entries(report_malformed=True)
    if malformed:
        # Don't crash on bad lines, but don't lose visibility either: the
        # next hook run will reload from the live file, so the host needs
        # to know corruption is sitting there.
        sample = "; ".join(f"L{n}: {ln[:80]}" for n, ln in malformed[:3])
        print(
            f"dream cycle: WARNING {len(malformed)} malformed JSONL line(s) "
            f"in {EPISODIC} (skipped). Sample: {sample}",
            file=sys.stderr,
        )
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

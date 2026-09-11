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
import contextlib, json, os
from promote import cluster_and_extract, write_candidates
from validate import heuristic_check
from review_state import mark_rejected, write_review_queue_summary
from decay import decay_old_entries
from archive import archive_stale_workspace

# fcntl is POSIX-only. On Windows the dream cycle is best-effort: concurrent
# writers there are rare (no shutdown hook = no parallel exits), and the lack
# of locking matches the existing _episodic_io.py fallback.
try:
    import fcntl  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — Windows
    fcntl = None  # type: ignore[assignment]

ROOT = os.path.abspath(os.path.dirname(__file__))
EPISODIC = os.path.join(ROOT, "episodic/AGENT_LEARNINGS.jsonl")
CANDIDATES = os.path.join(ROOT, "candidates")
SEMANTIC = os.path.join(ROOT, "semantic")
REVIEW_QUEUE = os.path.join(ROOT, "working/REVIEW_QUEUE.md")
PROMOTION_THRESHOLD = 7.0
CLUSTER_SIMILARITY = 0.3
# Cluster only the most recent entries. Clustering is pairwise, so its cost
# grows quadratically with the episodic file (29k entries ≈ 50 s even with
# the token index in cluster.py; unindexed it was ≈ 160 s). Candidates
# persist across cycles via their lifecycle records (_find_prior in
# promote.py), so entries that age out of the window keep every decision,
# rejection count, and graduation state they already staged.
DREAM_WINDOW_ENTRIES = 10_000


@contextlib.contextmanager
def _episodic_locked():
    """Hold an exclusive flock on AGENT_LEARNINGS.jsonl for a SHORT window.

    The lock exists for the read-modify-write of the episodic file itself:
    an `append_jsonl()` call that lands between a read and the truncate-
    rewrite is silently truncated away. Callers must therefore hold it only
    around file I/O — never around clustering, which is O(n²) on ~30k
    entries (minutes). A dream that holds the lock across its whole cycle
    starves every harness hook into its 60 s timeout and drops telemetry.

    Yields the open file descriptor so callers can read/write without
    racing on a second open(). On Windows (no fcntl) yields None and
    falls back to the historical best-effort behavior.
    """
    if fcntl is None:
        yield None
        return
    os.makedirs(os.path.dirname(EPISODIC), exist_ok=True)
    fd = os.open(EPISODIC, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield fd
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _claim_cycle_lock():
    """Try-lock a dedicated lockfile for the WHOLE cycle (not the episodic
    file). Prevents detached dream instances from piling up when several
    sessions stop around the same time: the second dream exits at once
    instead of burning minutes of CPU duplicating the first.

    Returns an fd to release/close, or None if another dream is running
    (or on Windows, where concurrent shutdown hooks are rare).
    """
    if fcntl is None:
        return None, True
    path = os.path.join(ROOT, ".dream.lock")
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return fd, True
    except BlockingIOError:
        os.close(fd)
        return None, False


def _load_entries_locked(fd):
    """Read all entries from the locked fd, or fall back to plain read on
    Windows (fd is None when fcntl is unavailable).
    """
    entries = []
    if fd is None:
        if not os.path.exists(EPISODIC):
            return entries
        with open(EPISODIC) as f:
            stream = f.read()
    else:
        os.lseek(fd, 0, os.SEEK_SET)
        chunks = []
        while True:
            buf = os.read(fd, 65536)
            if not buf:
                break
            chunks.append(buf)
        stream = b"".join(chunks).decode("utf-8", errors="replace")
    for line in stream.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _write_entries_locked(fd, entries):
    """Truncate-and-rewrite under the same lock _load_entries_locked used.

    Holding one fd across read+write is what makes the operation atomic
    against concurrent `append_jsonl()` calls.
    """
    payload = "".join(json.dumps(e) + "\n" for e in entries).encode("utf-8")
    if fd is None:
        # Windows: best-effort, matches _episodic_io fallback.
        with open(EPISODIC, "w") as f:
            f.write(payload.decode("utf-8"))
        return
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, payload)


# Compatibility shims for any external caller that still imports the
# pre-refactor names. Internal callers in run_dream_cycle use the locked
# helpers directly so the lock spans the full cycle.
def _load_entries():
    with _episodic_locked() as fd:
        return _load_entries_locked(fd)


def _write_entries(entries):
    with _episodic_locked() as fd:
        _write_entries_locked(fd, entries)


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
    lock_fd, won = _claim_cycle_lock()
    if not won:
        print("dream cycle: deferred (another dream is running)")
        return
    try:
        # Snapshot read under a SHORT lock, then release before any
        # clustering: live append_jsonl() callers must never queue behind
        # minutes of O(n²) work.
        with _episodic_locked() as fd:
            entries = _load_entries_locked(fd)
        if not entries:
            # Still refresh the review queue — candidates may have been staged
            # in a previous cycle and the host agent loads REVIEW_QUEUE.md
            # into every session via build_context, so a stale/missing file
            # hides real work.
            pending = write_review_queue_summary(CANDIDATES, REVIEW_QUEUE)
            print(f"dream cycle: no entries (queue has {pending} pending)")
            return

        patterns = cluster_and_extract(
            entries[-DREAM_WINDOW_ENTRIES:], threshold=CLUSTER_SIMILARITY)
        promotable = {k: p for k, p in patterns.items()
                      if p.get("canonical_salience", 0) >= PROMOTION_THRESHOLD}

        staged = write_candidates(promotable, CANDIDATES)
        prefiltered = _heuristic_prefilter(CANDIDATES, SEMANTIC)

        kept, archived = decay_old_entries(
            entries, archive_dir=os.path.join(ROOT, "episodic/snapshots"))

        if archived:
            # Merge under a SHORT lock: entries appended while we clustered
            # must survive the rewrite, so re-read and drop only what decay
            # marked (matched by canonical JSON, never by position).
            drop = {json.dumps(e, sort_keys=True) for e in archived}
            with _episodic_locked() as fd:
                current = _load_entries_locked(fd)
                kept = [e for e in current
                        if json.dumps(e, sort_keys=True) not in drop]
                _write_entries_locked(fd, kept)
        else:
            kept = entries

        archive_stale_workspace(
            working_dir=os.path.join(ROOT, "working"),
            archive_dir=os.path.join(ROOT, "episodic/snapshots"))

        pending = write_review_queue_summary(CANDIDATES, REVIEW_QUEUE)
    finally:
        if lock_fd is not None:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    print(
        f"dream cycle: patterns={len(patterns)} staged={staged} "
        f"prefiltered_out={prefiltered} pending_review={pending} "
        f"archived={len(archived)} kept={len(kept)}"
    )


if __name__ == "__main__":
    run_dream_cycle()

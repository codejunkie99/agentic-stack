"""Cross-platform locked append for episodic JSONL writes.

POSIX `write(2)` in O_APPEND mode is atomic for payloads up to PIPE_BUF
(4 KB on Linux, 512 B minimum per POSIX). Most episodic entries fit,
but failure entries with reflection + context + detail can exceed that,
and two harness hooks writing from the same process (or from two Pi
sessions on the same repo) can interleave bytes mid-line. Silent
corruption is worse than a visible error because every downstream
reader (`auto_dream.py`, `cluster.py`, `context_budget.py`,
`show.py`) skips `JSONDecodeError` lines without surfacing the loss.

This module serializes appends with `fcntl.flock(LOCK_EX)` on POSIX.
On platforms without `fcntl` (native Windows Python) the lock is a
no-op and behavior matches the pre-lock baseline. WSL, git-bash via
Cygwin, macOS, and Linux all provide `fcntl`.
"""
import json
import os

try:
    import fcntl  # POSIX
    _HAVE_FLOCK = True
except ImportError:
    _HAVE_FLOCK = False


def append_jsonl(path: str, entry: dict) -> dict:
    """Serialize `entry` to one JSON line and append to `path`.

    Uses `open(..., "ab")` (append-binary) to bypass Python's text-mode
    buffering and guarantee a single `write(2)` per call. `fcntl.flock`
    provides cross-process mutual exclusion on POSIX.
    """
    payload = (json.dumps(entry) + "\n").encode("utf-8")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "ab") as f:
        if _HAVE_FLOCK:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        try:
            f.write(payload)
            f.flush()
            # Durability must finish before the flock drops. auto_dream
            # rewrites this file under the same lock as soon as it can
            # acquire it, so a later fsync in the caller can sync the
            # wrong generation.
            os.fsync(f.fileno())
        finally:
            if _HAVE_FLOCK:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return entry


def _first_matching_action(raw: bytes, match_action: str) -> dict | None:
    """First JSON object whose action equals `match_action`.

    File order is the canonical order. Blank lines and corrupt lines
    are skipped. A row with an empty timestamp does not count.
    """
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(row, dict) or row.get("action") != match_action:
            continue
        timestamp = row.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            return row
    return None


def append_jsonl_once(path: str, entry: dict, *, match_action: str) -> dict:
    """Append `entry` unless `match_action` is already present.

    The read and the optional append share one `LOCK_EX` on `path`, the
    same flock `append_jsonl` and `auto_dream` already take. This is
    episodic serialization, not a candidate-directory lock. No second
    lock file is created.

    Returns the earliest existing row with that action, or `entry` when
    this call appended it. Older duplicate rows are left in place.

    Without `fcntl` the check-and-append is best-effort, matching the
    pre-lock baseline. `O_APPEND` keeps the write at end of file.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a+b") as handle:
        if _HAVE_FLOCK:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            handle.seek(0)
            existing = _first_matching_action(handle.read(), match_action)
            if existing is not None:
                return existing
            payload = (json.dumps(entry) + "\n").encode("utf-8")
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
            return entry
        finally:
            if _HAVE_FLOCK:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

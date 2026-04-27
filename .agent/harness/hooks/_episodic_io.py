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
        finally:
            if _HAVE_FLOCK:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
    return entry

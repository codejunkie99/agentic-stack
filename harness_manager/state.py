"""install.json: the authoritative record of what's installed in a project.

Atomic write via temp-file + rename, with fcntl advisory lock on POSIX.
Read-modify-write semantics (unlike .agent/memory/episodic/AGENT_LEARNINGS.jsonl
which is append-only). Codex review of PR #19 specifically called out that
the _episodic_io flock pattern is the wrong abstraction for install.json
because of read-modify-write — this module uses the right one.
"""
import json
import os
import tempfile
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX
    _HAVE_FLOCK = True
except ImportError:
    _HAVE_FLOCK = False


SCHEMA_VERSION = 1


def install_state_path(target_root: Path | str) -> Path:
    """Return the path where install.json lives for a given project."""
    return Path(target_root) / ".agent" / "install.json"


def load(target_root: Path | str) -> dict | None:
    """Load install.json for a project. Returns None if absent."""
    p = install_state_path(target_root)
    if not p.is_file():
        return None
    with open(p, "r", encoding="utf-8") as f:
        if _HAVE_FLOCK:
            fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(f)
        finally:
            if _HAVE_FLOCK:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def empty(target_root: Path | str, agentic_stack_version: str) -> dict:
    """Return a fresh install.json doc."""
    return {
        "schema_version": SCHEMA_VERSION,
        "agentic_stack_version": agentic_stack_version,
        "abs_target": str(Path(target_root).resolve()),
        "installed_at": _iso_now(),
        "adapters": {},
    }


def save(target_root: Path | str, doc: dict) -> None:
    """Atomically write install.json. fcntl-locked on POSIX.

    Atomic-replace via tempfile + os.rename in the same directory ensures
    readers never see a torn write. The flock is for cross-process
    serialization of read-modify-write callers.
    """
    p = install_state_path(target_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(doc, indent=2) + "\n").encode("utf-8")

    # Lock-file pattern: take an exclusive lock on a sibling .lock file
    # so concurrent writers serialize. Atomic rename is the actual
    # commit. Don't lock install.json itself — the rename would replace
    # the locked inode mid-flight.
    lock_path = p.with_suffix(p.suffix + ".lock")
    with open(lock_path, "a+") as lock_f:
        if _HAVE_FLOCK:
            fcntl.flock(lock_f.fileno(), fcntl.LOCK_EX)
        try:
            fd, tmp = tempfile.mkstemp(
                dir=str(p.parent), prefix=".install.json.", suffix=".tmp"
            )
            try:
                with os.fdopen(fd, "wb") as tf:
                    tf.write(payload)
                    tf.flush()
                    os.fsync(tf.fileno())
                os.replace(tmp, p)
            except Exception:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
        finally:
            if _HAVE_FLOCK:
                fcntl.flock(lock_f.fileno(), fcntl.LOCK_UN)


def upsert_adapter(
    target_root: Path | str,
    adapter_name: str,
    entry: dict,
    agentic_stack_version: str,
) -> None:
    """Read-modify-write to add or replace one adapter entry."""
    doc = load(target_root) or empty(target_root, agentic_stack_version)
    doc["adapters"][adapter_name] = entry
    doc["installed_at"] = _iso_now()
    save(target_root, doc)


def remove_adapter(target_root: Path | str, adapter_name: str) -> bool:
    """Drop an adapter from install.json. Returns True if present, False if not."""
    doc = load(target_root)
    if doc is None or adapter_name not in doc.get("adapters", {}):
        return False
    del doc["adapters"][adapter_name]
    doc["installed_at"] = _iso_now()
    save(target_root, doc)
    return True


def _iso_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

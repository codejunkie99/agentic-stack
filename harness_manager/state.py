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
    _HAVE_MSVCRT = False
except ImportError:
    _HAVE_FLOCK = False
    try:
        import msvcrt  # Windows
        _HAVE_MSVCRT = True
    except ImportError:
        _HAVE_MSVCRT = False


SCHEMA_VERSION = 1


def install_state_path(target_root: Path | str) -> Path:
    """Return the path where install.json lives for a given project."""
    return Path(target_root) / ".agent" / "install.json"


def brain_present(target_root: Path | str) -> bool:
    """True if .agent/ has the distinctive agentic-stack brain layout.

    Checking for `.agent/` alone false-positives on projects that use
    `.agent/` for unrelated purposes (some repos adopt the convention
    generically). We require the characteristic subdir triple that
    only the agentic-stack brain template installs: memory/, skills/,
    and protocols/. If all three are directories, the brain template
    was dropped here at some point.

    NOTE: brain-present is NECESSARY but NOT SUFFICIENT for legacy-
    install detection — a user could clone the agentic-stack repo
    itself, or copy the brain template into a repo, without ever
    installing an adapter. Use `legacy_unregistered_adapters` when
    you need to actually gate against a pre-v0.9 install.
    """
    agent = Path(target_root) / ".agent"
    if not agent.is_dir():
        return False
    return (
        (agent / "memory").is_dir()
        and (agent / "skills").is_dir()
        and (agent / "protocols").is_dir()
    )


def legacy_unregistered_adapters(target_root: Path | str) -> list[str]:
    """Detect pre-v0.9 install(s): returns the list of adapter signals.

    Returns [] when the project is NOT a legacy install — either
    install.json exists (already tracked), or the brain isn't present
    (fresh repo), or the brain is present but no adapter signals are
    on disk (brain-only template, nothing to migrate).

    Returns a sorted list of adapter names when the project needs
    migration via `doctor`. Caller gates installs on truthiness.

    We require BOTH a distinctive brain layout AND at least one
    adapter signal. Brain-only (e.g. cloning agentic-stack itself,
    or copying the template into a fresh repo before any adapter
    install) is NOT a legacy install — there's nothing to migrate,
    and gating would deadlock the user since doctor synthesizes
    nothing when no signals exist.
    """
    p = install_state_path(target_root)
    if p.is_file():
        return []
    if not brain_present(target_root):
        return []
    # Lazy import: doctor imports state, so inverse would cycle.
    from . import doctor as doctor_mod
    # STRONG signals only. Weak signals (plain CLAUDE.md / AGENTS.md /
    # run.py) are ambiguous even in a brain-present repo: users may
    # have the brain template from cloning agentic-stack AND their own
    # AGENTS.md. Gating on weak signals there false-refuses. Weak-only
    # adapters (hermes, standalone-python) won't auto-gate on upgrade
    # from pre-v0.9, but `./install.sh doctor` (which DOES consider
    # weak signals) is the documented path for legacy migration.
    return sorted(
        name
        for name, signals in doctor_mod.DETECT_SIGNALS.items()
        if any(
            (Path(target_root) / f).exists()
            for f, strength in signals
            if strength == "strong"
        )
    )


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
    readers never see a torn write.

    NOTE: this function takes the writer lock for its own duration only.
    For correct read-modify-write callers (upsert_adapter / remove_adapter),
    use those — they hold the lock around BOTH the read and the save so
    concurrent writers can't lose updates.
    """
    p = install_state_path(target_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with _lock(p):
        _save_locked(p, doc)


def _save_locked(p: Path, doc: dict) -> None:
    """Inner save: caller already holds the lock. tempfile + atomic rename."""
    payload = (json.dumps(doc, indent=2) + "\n").encode("utf-8")
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), prefix=".install.json.", suffix=".tmp")
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


class _lock:
    """Context manager: take an exclusive flock on a sibling .lock file.

    Don't lock install.json itself — the atomic rename would replace
    the locked inode mid-flight, leaving us holding a lock on a deleted
    file while the new install.json sits unlocked.
    """

    def __init__(self, install_json_path: Path):
        self.install_json_path = install_json_path
        self.lock_path = install_json_path.with_suffix(install_json_path.suffix + ".lock")
        self.lock_f = None

    def __enter__(self):
        self.install_json_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_f = open(self.lock_path, "a+")
        if _HAVE_FLOCK:
            fcntl.flock(self.lock_f.fileno(), fcntl.LOCK_EX)
        elif _HAVE_MSVCRT:
            # Windows: lock 1 byte at offset 0 of the lock sidecar.
            # LK_LOCK blocks until acquired (vs LK_NBLCK which would
            # raise immediately). Byte-range locking is the only
            # cross-process locking primitive msvcrt exposes, but a
            # 1-byte span on the sidecar file is enough for our
            # read-modify-write semantics here.
            self.lock_f.seek(0)
            msvcrt.locking(self.lock_f.fileno(), msvcrt.LK_LOCK, 1)
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.lock_f is not None:
            if _HAVE_FLOCK:
                fcntl.flock(self.lock_f.fileno(), fcntl.LOCK_UN)
            elif _HAVE_MSVCRT:
                try:
                    self.lock_f.seek(0)
                    msvcrt.locking(self.lock_f.fileno(), msvcrt.LK_UNLCK, 1)
                except OSError:
                    # Unlock can fail if the handle is already closed
                    # by a crashed caller; the OS releases the lock on
                    # process exit anyway.
                    pass
            self.lock_f.close()


def _load_no_lock(p: Path) -> dict | None:
    """Read install.json. Caller holds the lock OR is fine with eventual consistency."""
    if not p.is_file():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def upsert_adapter(
    target_root: Path | str,
    adapter_name: str,
    entry: dict,
    agentic_stack_version: str,
) -> None:
    """Read-modify-write to add or replace one adapter entry.

    Lock is held around the ENTIRE read-modify-write so concurrent
    `install.sh add ...` invocations cannot both read the same old
    document and produce a lost update.
    """
    p = install_state_path(target_root)
    with _lock(p):
        doc = _load_no_lock(p) or empty(target_root, agentic_stack_version)
        doc["adapters"][adapter_name] = entry
        doc["installed_at"] = _iso_now()
        _save_locked(p, doc)


def remove_adapter(target_root: Path | str, adapter_name: str) -> bool:
    """Drop an adapter from install.json. Returns True if present, False if not.

    Same locking discipline as upsert_adapter: lock spans the read+write.
    """
    p = install_state_path(target_root)
    with _lock(p):
        doc = _load_no_lock(p)
        if doc is None or adapter_name not in doc.get("adapters", {}):
            return False
        del doc["adapters"][adapter_name]
        doc["installed_at"] = _iso_now()
        _save_locked(p, doc)
        return True


def _iso_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

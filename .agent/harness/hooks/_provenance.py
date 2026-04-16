"""Shared provenance helpers for episodic entries. Cached per-process."""
import os, subprocess

AGENT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

_CACHED_COMMIT = None
_CACHED_RUN_ID = None


def run_id():
    global _CACHED_RUN_ID
    if _CACHED_RUN_ID is None:
        _CACHED_RUN_ID = os.environ.get("AGENT_RUN_ID", f"pid-{os.getpid()}")
    return _CACHED_RUN_ID


def commit_sha():
    global _CACHED_COMMIT
    if _CACHED_COMMIT is None:
        try:
            out = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True, text=True, timeout=2,
                cwd=AGENT_ROOT,
            )
            _CACHED_COMMIT = out.stdout.strip() if out.returncode == 0 else ""
        except Exception:
            _CACHED_COMMIT = ""
    return _CACHED_COMMIT


def build_source(skill):
    return {"skill": skill, "run_id": run_id(), "commit_sha": commit_sha()}

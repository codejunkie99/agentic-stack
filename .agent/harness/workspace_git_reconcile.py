#!/usr/bin/env python3
"""SessionStart hook: reconcile WORKSPACE.md 'Current step' against git reality.

Catches drift class observed 2026-05-02: branch listed as 'awaiting merge'
in WORKSPACE.md while merge commit already on master, going un-noticed for
multiple sessions.

Detection rules (advisory; warns to stderr, does not block):
  1. Branch named in WORKSPACE 'Current step' no longer exists locally OR remotely
     → likely already merged + branch deleted; WORKSPACE needs reconcile.
  2. WORKSPACE status text contains 'awaiting merge' AND a merge commit referencing
     that branch appears in `git log master --oneline -50`
     → already merged; WORKSPACE needs reconcile.

Fail-OPEN on any error.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
REPO_ROOT_DEFAULT = AGENT_ROOT.parent

BRANCH_LINE_RE = re.compile(r"^Branch:\s*`([^`]+)`", re.MULTILINE)
CURRENT_STEP_BLOCK_RE = re.compile(
    r"##\s*Current step\s*\n+\*\*([^*]+)\*\*", re.MULTILINE
)


def _repo_root() -> Path:
    override = os.environ.get("WORKSPACE_RECONCILE_REPO")
    return Path(override) if override else REPO_ROOT_DEFAULT


def _git(args: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True, check=False
        )
    except (FileNotFoundError, OSError):
        return ""
    return result.stdout if result.returncode == 0 else ""


def _parse_workspace(workspace_path: Path) -> tuple[str | None, str | None]:
    """Return (branch_name, current_step_status_block) or (None, None)."""
    if not workspace_path.exists():
        return None, None
    text = workspace_path.read_text(encoding="utf-8", errors="replace")
    branch_match = BRANCH_LINE_RE.search(text)
    step_match = CURRENT_STEP_BLOCK_RE.search(text)
    branch = branch_match.group(1).strip() if branch_match else None
    status = step_match.group(1).strip() if step_match else None
    return branch, status


def _branch_exists(branch: str, repo: Path) -> bool:
    out = _git(["branch", "-a", "--format=%(refname:short)"], repo)
    refs = {line.strip() for line in out.splitlines() if line.strip()}
    if branch in refs:
        return True
    return any(ref.endswith("/" + branch) for ref in refs)


def _merge_commit_on_master(branch: str, repo: Path) -> str | None:
    out = _git(["log", "master", "--oneline", "-50"], repo)
    for line in out.splitlines():
        if "Merge" in line and branch in line:
            return line.strip()
    return None


def main() -> int:
    repo = _repo_root()
    workspace = repo / ".agent/memory/working/WORKSPACE.md"
    branch, status = _parse_workspace(workspace)
    if not branch:
        return 0  # nothing to check

    warnings = []
    awaiting_merge = bool(status and "awaiting merge" in status.lower())

    merge_commit = _merge_commit_on_master(branch, repo)
    if awaiting_merge and merge_commit:
        warnings.append(
            f"WORKSPACE drift: status says 'awaiting merge' for branch `{branch}` "
            f"but merge commit already on master: `{merge_commit}`. "
            f"Reconcile WORKSPACE.md 'Current step'."
        )
    elif not _branch_exists(branch, repo):
        warnings.append(
            f"WORKSPACE drift: branch `{branch}` from 'Current step' no longer "
            f"exists locally or on remote. Likely merged + deleted. "
            f"Reconcile WORKSPACE.md."
        )

    for w in warnings:
        print(f"[workspace-git-reconcile] WARNING: {w}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"workspace_git_reconcile error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)

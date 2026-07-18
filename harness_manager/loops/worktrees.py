"""Creation and refusal-safe cleanup of loop-owned Git worktrees."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class WorktreeError(RuntimeError):
    """Raised when worktree identity or cleanup safety cannot be proven."""


@dataclass(frozen=True)
class OwnedWorktree:
    repository: str
    path: Path
    branch: str
    base_commit: str


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise WorktreeError("Git executable not found") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown Git error"
        raise WorktreeError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout


def repository_identity(target_root: Path) -> tuple[Path, str]:
    target = Path(target_root).resolve()
    try:
        repository = Path(_git(target, "rev-parse", "--show-toplevel").strip()).resolve()
        common_raw = _git(target, "rev-parse", "--git-common-dir").strip()
    except (OSError, WorktreeError) as exc:
        raise WorktreeError(f"target is not a usable Git repository: {target}") from exc
    common = Path(common_raw)
    if not common.is_absolute():
        common = target / common
    try:
        identity = str(common.resolve(strict=True))
    except OSError as exc:
        raise WorktreeError(f"Git repository common directory is unreadable: {common}") from exc
    return repository, identity


def _safe_root(target_root: Path, candidate: Path) -> Path:
    repository, _ = repository_identity(target_root)
    root = candidate.expanduser().resolve()
    dangerous = {Path(os.path.abspath(os.sep)), repository, repository.parent}
    if root in dangerous:
        raise WorktreeError(f"unsafe worktree root: {root}")
    return root


def worktree_root(target_root: Path, override: str | None = None) -> Path:
    repository, _ = repository_identity(target_root)
    if override is None:
        candidate = repository.parent / ".agentic-stack-worktrees" / repository.name
    else:
        if not isinstance(override, str) or not override.strip():
            raise WorktreeError("unsafe empty worktree root override")
        candidate = Path(override)
    return _safe_root(repository, candidate)


def _portable_name(value: str, field: str) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise WorktreeError(f"{field} must be a safe portable identifier")
    return value


def create_worktree(
    target_root: Path,
    loop_name: str,
    run_id: str,
    root: Path | None = None,
) -> OwnedWorktree:
    repository, identity = repository_identity(target_root)
    loop_name = _portable_name(loop_name, "loop_name")
    run_id = _portable_name(run_id, "run_id")
    owner_root = worktree_root(repository) if root is None else _safe_root(repository, Path(root))
    path = (owner_root / run_id).resolve()
    if path == owner_root or owner_root not in path.parents:
        raise WorktreeError(f"unsafe worktree path: {path}")
    if path.exists():
        raise WorktreeError(f"worktree path already exists: {path}")
    branch = f"agentic-loop/{loop_name}/{run_id}"
    base_commit = _git(repository, "rev-parse", "HEAD").strip()
    owner_root.mkdir(parents=True, exist_ok=True)
    _git(repository, "worktree", "add", "-b", branch, str(path), base_commit)
    owned = OwnedWorktree(identity, path, branch, base_commit)
    _verify_registered(repository, owned)
    return owned


def _registered_worktrees(repository: Path) -> dict[Path, dict[str, str]]:
    records: dict[Path, dict[str, str]] = {}
    current: dict[str, str] = {}
    for line in _git(repository, "worktree", "list", "--porcelain").splitlines() + [""]:
        if not line:
            if "worktree" in current:
                records[Path(current["worktree"]).resolve()] = dict(current)
            current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    return records


def _verify_registered(repository: Path, owned: OwnedWorktree) -> None:
    _, identity = repository_identity(repository)
    if identity != owned.repository:
        raise WorktreeError("worktree repository identity does not match checkpoint")
    path = owned.path.resolve()
    record = _registered_worktrees(repository).get(path)
    if record is None:
        raise WorktreeError(f"worktree path is not registered: {path}")
    if record.get("branch") != f"refs/heads/{owned.branch}":
        raise WorktreeError("registered worktree branch does not match checkpoint")


def _nul_paths(output: str) -> set[str]:
    return {value for value in output.split("\0") if value}


def changed_paths(owned: OwnedWorktree) -> list[str]:
    path = owned.path.resolve()
    repository, identity = repository_identity(path)
    if identity != owned.repository:
        raise WorktreeError("worktree repository identity does not match checkpoint")
    _verify_registered(repository, owned)
    paths = set()
    paths |= _nul_paths(_git(path, "diff", "--name-only", "-z", owned.base_commit, "HEAD", "--"))
    paths |= _nul_paths(_git(path, "diff", "--name-only", "-z", "--"))
    paths |= _nul_paths(_git(path, "diff", "--cached", "--name-only", "-z", "--"))
    paths |= _nul_paths(_git(path, "ls-files", "--others", "--exclude-standard", "-z", "--"))
    return sorted(paths)


def cleanup_worktree(
    target_root: Path,
    owned: OwnedWorktree,
    *,
    allow_dirty: bool = False,
) -> None:
    repository, identity = repository_identity(target_root)
    path = owned.path.resolve()
    default_root = worktree_root(repository)
    dangerous = {
        Path(os.path.abspath(os.sep)),
        repository,
        repository.parent,
        default_root,
    }
    if path in dangerous:
        raise WorktreeError(f"unsafe worktree cleanup target: {path}")
    if identity != owned.repository:
        raise WorktreeError("worktree repository identity does not match checkpoint")
    _verify_registered(repository, owned)
    dirty = changed_paths(owned)
    if dirty and not allow_dirty:
        raise WorktreeError(f"owned worktree is dirty: {', '.join(dirty)}")
    arguments = ["worktree", "remove"]
    if allow_dirty:
        arguments.append("--force")
    arguments.append(str(path))
    _git(repository, *arguments)
    _git(repository, "branch", "-d", owned.branch)

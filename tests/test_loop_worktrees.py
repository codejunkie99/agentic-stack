from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from harness_manager.loops.worktrees import (
    OwnedWorktree,
    WorktreeError,
    changed_paths,
    cleanup_worktree,
    create_worktree,
    repository_identity,
    worktree_root,
)


def git(root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )
    if check and result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.name", "Loop Test")
    git(root, "config", "user.email", "loop@example.test")
    (root / "README.md").write_text("base\n", encoding="utf-8")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "base")
    return root


def test_create_worktree_records_identity_branch_and_base(repo: Path):
    owned = create_worktree(repo, "ci-sweeper", "run-123", root=repo.parent / "owned")
    assert owned.path.is_dir()
    assert owned.base_commit == git(repo, "rev-parse", "HEAD").strip()
    assert owned.branch == "agentic-loop/ci-sweeper/run-123"
    assert owned.repository == repository_identity(repo)[1]


def test_cleanup_rejects_unregistered_path(repo: Path):
    _, identity = repository_identity(repo)
    path = repo.parent / "not-registered" / "run-x"
    path.mkdir(parents=True)
    owned = OwnedWorktree(identity, path, "agentic-loop/test/run-x", "deadbeef")
    with pytest.raises(WorktreeError, match="registered"):
        cleanup_worktree(repo, owned)
    assert path.exists()


def test_dirty_worktree_requires_explicit_override(repo: Path):
    owned = create_worktree(repo, "ci-sweeper", "run-dirty", root=repo.parent / "owned")
    (owned.path / "result.txt").write_text("dirty", encoding="utf-8")
    assert changed_paths(owned) == ["result.txt"]
    with pytest.raises(WorktreeError, match="dirty"):
        cleanup_worktree(repo, owned)
    cleanup_worktree(repo, owned, allow_dirty=True)
    assert not owned.path.exists()


def test_clean_registered_worktree_is_removed(repo: Path):
    owned = create_worktree(repo, "ci-sweeper", "run-clean", root=repo.parent / "owned")
    cleanup_worktree(repo, owned)
    assert str(owned.path) not in git(repo, "worktree", "list", "--porcelain")
    assert not owned.path.exists()


@pytest.mark.parametrize("kind", ["root", "repository", "parent", "default_root"])
def test_dangerous_override_or_cleanup_target_is_rejected(repo: Path, kind: str):
    if kind == "root":
        with pytest.raises(WorktreeError, match="unsafe"):
            worktree_root(repo, "/")
    elif kind == "repository":
        with pytest.raises(WorktreeError, match="unsafe"):
            worktree_root(repo, str(repo))
    elif kind == "parent":
        with pytest.raises(WorktreeError, match="unsafe"):
            worktree_root(repo, str(repo.parent))
    else:
        _, identity = repository_identity(repo)
        unsafe = worktree_root(repo)
        owned = OwnedWorktree(identity, unsafe, "agentic-loop/test/run", "deadbeef")
        with pytest.raises(WorktreeError, match="unsafe"):
            cleanup_worktree(repo, owned)


def test_repository_identity_rejects_non_git_target(tmp_path: Path):
    with pytest.raises(WorktreeError, match="Git repository"):
        repository_identity(tmp_path)

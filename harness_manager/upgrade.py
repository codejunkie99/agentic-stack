"""Project-local .agent infrastructure upgrade."""
from __future__ import annotations

import fnmatch
import shutil
import sys
from pathlib import Path
from typing import Callable

from . import skill_manifest


def upgrade(
    target_root: Path | str,
    stack_root: Path | str,
    *,
    dry_run: bool = False,
    yes: bool = False,
    log: Callable[[str], None] | None = None,
) -> int:
    """Copy safe skeleton-owned .agent files into an installed project."""
    if log is None:
        log = print
    target_root = Path(target_root)
    stack_root = Path(stack_root)
    src_agent = stack_root / ".agent"
    dst_agent = target_root / ".agent"
    if not dst_agent.is_dir():
        print(f"error: {dst_agent} not found; install agentic-stack first", file=sys.stderr)
        return 2

    actions = _plan(src_agent, dst_agent)
    if not actions:
        log(f"{target_root}: .agent infrastructure already current")
    else:
        log(f"{'would update' if dry_run else 'updating'} {len(actions)} .agent file(s):")
        for src, dst in actions:
            log(f"  {'~' if dst.exists() else '+'} {dst.relative_to(target_root)}")

    if dry_run:
        log("dry run; no files changed")
        return 0

    if not yes and sys.stdin.isatty():
        answer = input("apply upgrade? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            log("aborted; no files changed")
            return 0
    if not yes and not sys.stdin.isatty():
        print("error: upgrade needs confirmation; re-run with --yes or --dry-run", file=sys.stderr)
        return 2

    for src, dst in actions:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    skill_manifest.sync_manifest(target_root, log=log)
    return 0


def _plan(src_agent: Path, dst_agent: Path) -> list[tuple[Path, Path]]:
    actions: list[tuple[Path, Path]] = []
    for rel in _infrastructure_files(src_agent):
        src = src_agent / rel
        dst = dst_agent / rel
        if _needs_copy(src, dst):
            actions.append((src, dst))

    src_index = src_agent / "skills" / "_index.md"
    dst_index = dst_agent / "skills" / "_index.md"
    if src_index.is_file() and _needs_copy(src_index, dst_index):
        actions.append((src_index, dst_index))

    src_skills = src_agent / "skills"
    dst_skills = dst_agent / "skills"
    for skill_md in sorted(src_skills.glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        if skill_dir.name.startswith("loop-"):
            continue
        if (dst_skills / skill_dir.name).exists():
            continue
        for src in sorted(p for p in skill_dir.rglob("*") if p.is_file() and not _ignored(p)):
            rel = src.relative_to(src_agent)
            actions.append((src, dst_agent / rel))
    actions.extend(_new_loop_assets(src_agent, dst_agent))
    return actions


def _new_loop_assets(src_agent: Path, dst_agent: Path) -> list[tuple[Path, Path]]:
    """Plan add-only bundled loop contracts, runtime ignore, and seed skills."""
    actions: list[tuple[Path, Path]] = []
    src_loops = src_agent / "loops"
    dst_loops = dst_agent / "loops"
    if src_loops.is_dir():
        for src in sorted(p for p in src_loops.rglob("*") if p.is_file()):
            dst = dst_loops / src.relative_to(src_loops)
            if not dst.exists():
                actions.append((src, dst))

    runtime_ignore = src_agent / "runtime" / ".gitignore"
    dst_runtime_ignore = dst_agent / "runtime" / ".gitignore"
    if runtime_ignore.is_file() and not dst_runtime_ignore.exists():
        actions.append((runtime_ignore, dst_runtime_ignore))

    src_skills = src_agent / "skills"
    dst_skills = dst_agent / "skills"
    for skill_dir in sorted(src_skills.glob("loop-*")):
        if not skill_dir.is_dir() or (dst_skills / skill_dir.name).exists():
            continue
        for src in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
            actions.append((src, dst_skills / src.relative_to(src_agent)))
    return actions


def _infrastructure_files(src_agent: Path) -> list[Path]:
    rels: list[Path] = []
    for base in ("harness",):
        root = src_agent / base
        if root.is_dir():
            rels.extend(p.relative_to(src_agent) for p in root.rglob("*.py") if not _ignored(p))
    for base in ("memory", "tools"):
        root = src_agent / base
        if root.is_dir():
            rels.extend(p.relative_to(src_agent) for p in root.glob("*.py") if not _ignored(p))
    return sorted(rels)


def _ignored(path: Path) -> bool:
    parts = set(path.parts)
    if "__pycache__" in parts:
        return True
    return any(fnmatch.fnmatch(path.name, pattern) for pattern in ("*.pyc", "*.pyo"))


def _needs_copy(src: Path, dst: Path) -> bool:
    if not dst.is_file():
        return True
    try:
        return src.read_bytes() != dst.read_bytes()
    except OSError:
        return True

"""Project-local .agent infrastructure upgrade."""
from __future__ import annotations

import fnmatch
import json
import shutil
import sys
from pathlib import Path
from typing import Callable

from . import skill_manifest


_AGENTS_BLOCK_START = "<!-- agentic-stack:portable-brain:start -->"
_AGENTS_BLOCK_END = "<!-- agentic-stack:portable-brain:end -->"


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
    agents_block_update = _agents_block_needs_update(
        src_agent / "AGENTS.md", dst_agent / "AGENTS.md"
    )
    action_count = len(actions) + int(agents_block_update)
    if not action_count:
        log(f"{target_root}: .agent infrastructure already current")
    else:
        log(f"{'would update' if dry_run else 'updating'} {action_count} .agent file(s):")
        for src, dst in actions:
            log(f"  {'~' if dst.exists() else '+'} {dst.relative_to(target_root)}")
        if agents_block_update:
            dst_agents = dst_agent / "AGENTS.md"
            log(f"  {'~' if dst_agents.exists() else '+'} {dst_agents.relative_to(target_root)} (managed block)")

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
    if agents_block_update:
        _merge_agents_block(src_agent / "AGENTS.md", dst_agent / "AGENTS.md")

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
            actions.append((src, dst_agent / src.relative_to(src_agent)))
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
    rels.extend(_managed_artifact_files(src_agent))
    return sorted(set(rels))


def _managed_artifact_files(src_agent: Path) -> list[Path]:
    """Return safe, registry-owned files that upgrades must refresh."""
    registry_rel = Path("config/extracted-artifacts.json")
    registry_path = src_agent / registry_rel
    if not registry_path.is_file():
        return []
    try:
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [registry_rel]

    rels = [registry_rel]
    for artifact in registry.get("artifacts", []):
        if not isinstance(artifact, dict) or artifact.get("sourceState") != "managed":
            continue
        path = artifact.get("path")
        if not isinstance(path, str):
            continue
        try:
            rel = Path(path).relative_to(".agent")
        except ValueError:
            continue
        source = src_agent / rel
        try:
            source.resolve().relative_to(src_agent.resolve())
        except ValueError:
            continue
        if source.is_file() and not _ignored(source):
            rels.append(rel)
    return rels


def _managed_agents_block(path: Path) -> str | None:
    if not path.is_file():
        return None
    text = path.read_text(encoding="utf-8")
    start = text.find(_AGENTS_BLOCK_START)
    end = text.find(_AGENTS_BLOCK_END, start + len(_AGENTS_BLOCK_START))
    if start < 0 or end < 0:
        return None
    return text[start : end + len(_AGENTS_BLOCK_END)]


def _agents_block_needs_update(src: Path, dst: Path) -> bool:
    source_block = _managed_agents_block(src)
    if source_block is None:
        return False
    return _managed_agents_block(dst) != source_block


def _merge_agents_block(src: Path, dst: Path) -> None:
    """Update only the portable-brain block and preserve local instructions."""
    source_block = _managed_agents_block(src)
    if source_block is None:
        raise ValueError(f"managed portable-brain block is missing from {src}")
    if not dst.is_file():
        shutil.copy2(src, dst)
        return

    current = dst.read_text(encoding="utf-8")
    start = current.find(_AGENTS_BLOCK_START)
    end = current.find(_AGENTS_BLOCK_END, start + len(_AGENTS_BLOCK_START))
    if start >= 0 and end >= 0:
        end += len(_AGENTS_BLOCK_END)
        updated = current[:start] + source_block + current[end:]
    else:
        updated = current.rstrip() + "\n\n" + source_block + "\n"
    dst.write_text(updated, encoding="utf-8")


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

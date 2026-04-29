"""
Capability-based runtime detection for deckster-slide-generator.

The workflow fork is based on what the runtime can do, not on hardcoded
product names. `supports_subagents` is the primary switch between the
sequential and orchestrated paths.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


TRUE_VALUES = {"1", "true", "yes", "on"}


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def detect_skill_root(anchor: str | Path | None = None) -> Path:
    """Locate the skill root in sandbox, local, or mirrored worktree setups."""
    explicit = os.getenv("DECKSTER_SKILL_ROOT")
    candidates = []
    if explicit:
        candidates.append(Path(explicit))

    candidates.append(Path("/mnt/skills/user/deckster-slide-generator"))

    start = Path(anchor or __file__).resolve().parent
    if start.name == "scripts":
        candidates.extend([start.parent, start.parent.parent])
    candidates.append(Path.cwd())

    for candidate in candidates:
        if (candidate / "scripts" / "bcg_template.py").exists():
            return candidate

    return start.parent if start.name == "scripts" else start


@dataclass(frozen=True)
class RuntimeCapabilities:
    runtime_family: str
    workflow_mode: str
    supports_subagents: bool
    supports_local_fs: bool
    supports_workspace_persistence: bool
    supports_rendered_image_review: bool
    has_libreoffice: bool
    has_poppler: bool
    visual_qa_ready: bool
    skill_root: Path
    scripts_dir: Path

    def as_dict(self) -> dict:
        payload = asdict(self)
        payload["skill_root"] = str(self.skill_root)
        payload["scripts_dir"] = str(self.scripts_dir)
        return payload


def detect_runtime_capabilities(anchor: str | Path | None = None) -> RuntimeCapabilities:
    skill_root = detect_skill_root(anchor=anchor)
    is_sandbox = str(skill_root).startswith("/mnt/skills")

    runtime_family = os.getenv("DECKSTER_RUNTIME_FAMILY")
    if not runtime_family:
        runtime_family = "claude_chat" if is_sandbox else "local"

    explicit_mode = os.getenv("DECKSTER_WORKFLOW_MODE")
    default_subagents = explicit_mode == "orchestrated"
    supports_subagents = _env_flag("DECKSTER_SUPPORTS_SUBAGENTS", default=default_subagents)
    workflow_mode = explicit_mode or ("orchestrated" if supports_subagents else "sequential")

    supports_local_fs = _env_flag("DECKSTER_SUPPORTS_LOCAL_FS", default=not is_sandbox)
    supports_workspace_persistence = _env_flag(
        "DECKSTER_SUPPORTS_WORKSPACE_PERSISTENCE",
        default=not is_sandbox,
    )
    supports_rendered_image_review = _env_flag(
        "DECKSTER_SUPPORTS_RENDERED_IMAGE_REVIEW",
        default=True,
    )

    has_libreoffice = shutil.which("libreoffice") is not None
    has_poppler = (
        shutil.which("pdftoppm") is not None
        or shutil.which("pdf2image") is not None
    )
    visual_qa_ready = supports_rendered_image_review and has_libreoffice and has_poppler

    return RuntimeCapabilities(
        runtime_family=runtime_family,
        workflow_mode=workflow_mode,
        supports_subagents=supports_subagents,
        supports_local_fs=supports_local_fs,
        supports_workspace_persistence=supports_workspace_persistence,
        supports_rendered_image_review=supports_rendered_image_review,
        has_libreoffice=has_libreoffice,
        has_poppler=has_poppler,
        visual_qa_ready=visual_qa_ready,
        skill_root=skill_root,
        scripts_dir=skill_root / "scripts",
    )

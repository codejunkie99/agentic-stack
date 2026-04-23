"""One-screen read-only view of installed adapters.

Same content as the manage menu's header pane in the v1.0 vision —
shipped here as a discrete subcommand instead of a TUI element.
"""
from pathlib import Path
from typing import Callable

from . import state as state_mod


def show(target_root: Path | str, log: Callable[[str], None] | None = None) -> int:
    if log is None:
        log = print
    target_root = Path(target_root).resolve()
    doc = state_mod.load(target_root)

    if doc is None:
        log(f"no install.json at {target_root / '.agent/install.json'}.")
        log("run `./install.sh <adapter>` to install one,")
        log("or `./install.sh doctor` to detect existing adapters.")
        return 0

    adapters = doc.get("adapters", {})
    log(f"project:  {target_root}")
    log(f"brain:    .agent/  ({_brain_summary(target_root)})")
    log(f"version:  agentic-stack {doc.get('agentic_stack_version', '?')}")
    log(f"updated:  {doc.get('installed_at', '?')}")
    log("")
    log(f"adapters installed ({len(adapters)}):")
    if not adapters:
        log("  (none)")
        return 0
    for name in sorted(adapters):
        entry = adapters[name]
        primitive = entry.get("brain_root_primitive", "")
        prim_str = f"  primitive: {primitive}" if primitive else ""
        synth = "  (synthesized)" if entry.get("_synthesized") else ""
        log(f"  • {name}{prim_str}{synth}")
    return 0


def _brain_summary(target_root: Path) -> str:
    """Quick stats: skill count, episodic line count, lesson count."""
    parts = []
    skills_dir = target_root / ".agent" / "skills"
    if skills_dir.is_dir():
        n = sum(1 for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
        parts.append(f"{n} skills")
    epi = target_root / ".agent" / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
    if epi.is_file():
        try:
            n = sum(1 for _ in epi.open("r", encoding="utf-8", errors="ignore"))
            parts.append(f"{n} episodic")
        except OSError:
            pass
    lessons = target_root / ".agent" / "memory" / "semantic" / "lessons.jsonl"
    if lessons.is_file():
        try:
            n = sum(1 for _ in lessons.open("r", encoding="utf-8", errors="ignore"))
            parts.append(f"{n} lessons")
        except OSError:
            pass
    return ", ".join(parts) if parts else "uninitialized"

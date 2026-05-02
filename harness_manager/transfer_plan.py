"""Transfer intent parsing and adapter preview planning."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


VALID_TARGETS = ("codex", "cursor", "windsurf", "terminal")
DEFAULT_SCOPES = ("preferences", "accepted_lessons", "skills")
SENSITIVE_SCOPES = ("working", "episodic", "candidates", "data_layer", "flywheel")
VALID_SCOPES = DEFAULT_SCOPES + SENSITIVE_SCOPES

TARGET_ALIASES = {
    "codex": "codex",
    "openai": "codex",
    "cursor": "cursor",
    "windsurf": "windsurf",
    "cascade": "windsurf",
    "terminal": "terminal",
    "term": "terminal",
    "shell": "terminal",
    "agents.md": "terminal",
    "agents": "terminal",
    "all": "all",
    "every": "all",
    "everything": "all",
}

SCOPE_ALIASES = {
    "preference": "preferences",
    "preferences": "preferences",
    "prefs": "preferences",
    "lesson": "accepted_lessons",
    "lessons": "accepted_lessons",
    "semantic": "accepted_lessons",
    "memory": "accepted_lessons",
    "memories": "accepted_lessons",
    "skill": "skills",
    "skills": "skills",
    "working": "working",
    "workspace": "working",
    "episodic": "episodic",
    "episode": "episodic",
    "episodes": "episodic",
    "log": "episodic",
    "logs": "episodic",
    "history": "episodic",
    "candidate": "candidates",
    "candidates": "candidates",
    "data": "data_layer",
    "dashboard": "data_layer",
    "flywheel": "flywheel",
    "trace": "flywheel",
    "traces": "flywheel",
}

OPERATION_ALIASES = {
    "curl": "generate-curl",
    "command": "generate-curl",
    "paste": "generate-curl",
    "share": "generate-curl",
    "export": "generate-curl",
    "another": "generate-curl",
    "remote": "generate-curl",
    "apply": "apply-here",
    "install": "apply-here",
    "here": "apply-here",
    "current": "apply-here",
    "local": "apply-here",
    "both": "both",
}


@dataclass(frozen=True)
class AdapterAction:
    target: str
    src: str
    dst: str
    merge_policy: str
    kind: str = "file"


@dataclass(frozen=True)
class TransferPlan:
    intent: str
    targets: tuple[str, ...]
    operation: str
    scopes: tuple[str, ...]
    sensitive_scopes: tuple[str, ...]
    adapter_actions: tuple[AdapterAction, ...]
    warnings: tuple[str, ...]


def _tokens(text: str) -> list[str]:
    lowered = text.casefold().replace("/", " ").replace(",", " ")
    raw = [t.strip(" .:;()[]{}'\"") for t in lowered.split()]
    return [t for t in raw if t]


def normalize_targets(values: Iterable[str]) -> tuple[str, ...]:
    selected: list[str] = []
    for value in values:
        key = value.casefold().strip()
        target = TARGET_ALIASES.get(key, key)
        if target == "all":
            return VALID_TARGETS
        if target not in VALID_TARGETS:
            continue
        if target not in selected:
            selected.append(target)
    return tuple(selected)


def detect_targets(intent: str) -> tuple[str, ...]:
    return normalize_targets(_tokens(intent))


def normalize_scopes(values: Iterable[str] | None) -> tuple[str, ...]:
    if values is None:
        return DEFAULT_SCOPES
    selected: set[str] = set()
    for value in values:
        key = value.casefold().strip().replace("-", "_")
        scope = SCOPE_ALIASES.get(key, key)
        if scope not in VALID_SCOPES:
            continue
        selected.add(scope)
    if not selected:
        return DEFAULT_SCOPES
    return tuple(scope for scope in VALID_SCOPES if scope in selected)


def detect_scopes(intent: str) -> tuple[str, ...]:
    selected = normalize_scopes(_tokens(intent))
    return selected if selected != ("accepted_lessons",) else DEFAULT_SCOPES


def detect_operation(intent: str) -> str:
    found = []
    for token in _tokens(intent):
        op = OPERATION_ALIASES.get(token)
        if op and op not in found:
            found.append(op)
    if "both" in found:
        return "both"
    if "apply-here" in found and "generate-curl" in found:
        return "both"
    if found:
        return found[0]
    return "generate-curl"


def build_plan(
    intent: str,
    stack_root: Path | str,
    targets: Iterable[str] | None = None,
    scopes: Iterable[str] | None = None,
    operation: str | None = None,
) -> TransferPlan:
    stack_root = Path(stack_root)
    warnings: list[str] = []

    target_list = normalize_targets(targets) if targets is not None else detect_targets(intent)
    if not target_list:
        target_list = VALID_TARGETS
        warnings.append("No target detected; defaulting to all supported targets.")

    scope_list = normalize_scopes(scopes) if scopes is not None else detect_scopes(intent)
    sensitive = tuple(scope for scope in scope_list if scope in SENSITIVE_SCOPES)
    if sensitive:
        warnings.append(
            "Sensitive scopes selected: "
            + ", ".join(sensitive)
            + ". The wizard must confirm these before export."
        )

    op = operation or detect_operation(intent)
    actions = tuple(_adapter_actions_for_targets(stack_root, target_list))
    return TransferPlan(
        intent=intent,
        targets=target_list,
        operation=op,
        scopes=scope_list,
        sensitive_scopes=sensitive,
        adapter_actions=actions,
        warnings=tuple(warnings),
    )


def _adapter_actions_for_targets(stack_root: Path, targets: Iterable[str]) -> list[AdapterAction]:
    actions: list[AdapterAction] = []
    for target in targets:
        if target == "terminal":
            actions.append(
                AdapterAction(
                    target="terminal",
                    src="AGENTS.md",
                    dst="AGENTS.md",
                    merge_policy="merge_or_alert",
                )
            )
            continue
        manifest_path = stack_root / "adapters" / target / "adapter.json"
        if not manifest_path.is_file():
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("files", []):
            actions.append(
                AdapterAction(
                    target=target,
                    src=str(entry["src"]),
                    dst=str(entry["dst"]),
                    merge_policy=str(entry.get("merge_policy", "overwrite")),
                )
            )
        link = manifest.get("skills_link")
        if isinstance(link, dict):
            actions.append(
                AdapterAction(
                    target=target,
                    src=str(link["target"]),
                    dst=str(link["dst"]),
                    merge_policy=str(link.get("fallback", "symlink")),
                    kind="skills_link",
                )
            )
    return actions

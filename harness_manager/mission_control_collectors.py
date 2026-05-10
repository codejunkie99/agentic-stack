"""Payload collectors for the local Mission Control web UI."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import dashboard_tui


API_PATHS = {
    "/api/status",
    "/api/adapters",
    "/api/doctor",
    "/api/memory/summary",
    "/api/handoff",
    "/api/command-center",
    "/api/command-recipes",
    "/api/brain",
    "/api/brain/lessons",
    "/api/brain/candidates",
    "/api/harnesses",
    "/api/harnesses/codex",
    "/api/trust",
    "/api/trust/verify",
    "/api/runs",
    "/api/skills",
    "/api/skills/example",
    "/api/protocols",
    "/api/protocols/permissions",
    "/api/data-flywheel",
    "/api/ops/events",
    "/api/settings",
}

DOMAINS = [
    "Command Center",
    "Command Recipes",
    "Brain",
    "Harnesses",
    "Trust",
    "Runs",
    "Skills",
    "Protocols",
    "Handoff",
    "Data Flywheel",
    "Ops Console",
    "Settings",
]

OPS_EVENT_LOG = "mission-control-events.jsonl"


def build_payloads(target_root: Path | str, stack_root: Path | str) -> dict[str, dict[str, Any]]:
    """Collect the compact API payloads used by the Mission Control UI."""
    model = dashboard_tui.collect_dashboard(target_root, stack_root)
    memory = model["memory"]
    payloads = {
        "/api/status": {
            "project": model["project"],
            "version": model["version"],
            "installed_at": model["installed_at"],
            "score": model["score"],
            "warnings": model["warnings"],
            "failures": model["failures"],
            "brain_summary": model["brain_summary"],
            "installed_adapters": len(model["installed"]),
            "available_adapters": len(model["available"]),
            "lessons": memory["lessons"],
            "skills": model["skills"]["count"],
            "instances": model["instances"]["count"],
        },
        "/api/adapters": {
            "installed": model["installed"],
            "available": model["available"],
            "rows": model["adapters"],
            "verify": model["verify"],
        },
        "/api/doctor": {
            "score": model["score"],
            "warnings": model["warnings"],
            "failures": model["failures"],
            "checks": model["checks"],
            "adapters": model["adapters"],
        },
        "/api/memory/summary": {
            "episodes": memory["episodes"],
            "failures": memory["failures"],
            "lessons": memory["lessons"],
            "accepted": memory["accepted"],
            "provisional": memory["provisional"],
            "candidates": memory["candidates"],
            "candidate_counts": memory["candidate_counts"],
            "accepted_items": memory["accepted_items"][:8],
            "rejected_items": memory["rejected_items"][:8],
            "skills": model["skills"],
            "team": model["team"],
            "instances": model["instances"],
        },
        "/api/handoff": {
            "ready": model["transfer"]["ready"],
            "detail": model["transfer"]["detail"],
            "project": model["project"],
            "commands": [
                "./install.sh status",
                "./install.sh doctor",
                "./install.sh dashboard --plain",
                "./install.sh transfer export",
            ],
            "summary": {
                "score": model["score"],
                "version": model["version"],
                "brain": model["brain_summary"],
                "adapters": model["installed"],
                "lessons": memory["lessons"],
            },
        },
    }
    phase_payloads = _phase_a_payloads(model, target_root, stack_root)
    handoff_overlay = phase_payloads.pop("/api/handoff")
    handoff_overlay["domain_summary"] = handoff_overlay.pop("summary", "")
    payloads["/api/handoff"].update(handoff_overlay)
    payloads.update(phase_payloads)
    return payloads




def _candidate_detail(counts: dict[str, Any]) -> str:
    return (
        f"{counts.get('staged', 0)} staged, "
        f"{counts.get('graduated', 0)} graduated, "
        f"{counts.get('rejected', 0)} rejected"
    )


def _read_jsonl_with_lines(path: Path) -> list[tuple[int, dict[str, Any]]]:
    rows: list[tuple[int, dict[str, Any]]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return rows
    for line_no, line in enumerate(lines, 1):
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append((line_no, payload))
    return rows


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _bounded_excerpt(path: Path, limit: int = 400) -> tuple[str, int]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", 0
    excerpt = text[:limit]
    return excerpt, len(text.splitlines())


def _lesson_objects(target: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    path = target / ".agent" / "memory" / "semantic" / "lessons.jsonl"
    stats = {"accepted": 0, "provisional": 0, "rejected": 0}
    objects: list[dict[str, Any]] = []
    for line_no, item in _read_jsonl_with_lines(path):
        lesson_status = str(item.get("status", "provisional"))
        if lesson_status in stats:
            stats[lesson_status] += 1
        evidence = item.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        payload = {
            **item,
            "lesson_status": lesson_status,
            "source_path": str(path),
            "source_line": line_no,
            "evidence_count": len(evidence),
            "evidence": evidence,
        }
        objects.append(
            _control_object(
                f"lesson-{item.get('id', line_no)}",
                "lesson",
                str(item.get("id", f"lesson {line_no}")),
                lesson_status,
                str(item.get("claim") or item.get("summary") or "lesson"),
                _source(api="/api/brain/lessons", path=path),
                payload,
            )
        )
    return objects, stats


def _candidate_objects(target: Path) -> tuple[list[dict[str, Any]], dict[str, int]]:
    root = target / ".agent" / "memory" / "candidates"
    specs = [
        ("staged", root, "warn"),
        ("graduated", root / "graduated", "pass"),
        ("rejected", root / "rejected", "fail"),
    ]
    flow = {"staged": 0, "graduated": 0, "rejected": 0}
    objects: list[dict[str, Any]] = []
    for state, folder, status in specs:
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.json")):
            item = _read_json_object(path)
            if item is None:
                continue
            flow[state] += 1
            candidate_state = str(item.get("status") or state)
            payload = {
                **item,
                "candidate_state": state,
                "source_path": str(path),
                "source_line": 1,
            }
            objects.append(
                _control_object(
                    f"candidate-{item.get('id', path.stem)}",
                    "candidate",
                    str(item.get("id", path.stem)),
                    status if candidate_state == state else candidate_state,
                    str(item.get("claim") or item.get("summary") or "candidate"),
                    _source(api="/api/brain/candidates", path=path),
                    payload,
                )
            )
    return objects, flow


def _phase_a_payloads(
    model: dict[str, Any],
    target_root: Path | str,
    stack_root: Path | str,
) -> dict[str, dict[str, Any]]:
    target = Path(target_root).resolve()
    stack = Path(stack_root).resolve()
    memory = model["memory"]
    status = _overall_status(model["failures"], model["warnings"])

    command_objects = [
        _control_object(
            "command-health",
            "status",
            "Health score",
            status,
            f"{model['score']}% with {model['failures']} failures and {model['warnings']} warnings",
            _source(api="/api/status", path=target / ".agent" / "install.json"),
            {
                "score": model["score"],
                "warnings": model["warnings"],
                "failures": model["failures"],
            },
        ),
        _control_object(
            "command-project",
            "project",
            "Project",
            "pass",
            str(target),
            _source(path=target),
            {"project": model["project"], "installed_at": model["installed_at"]},
        ),
        _control_object(
            "command-brain",
            "brain",
            "Brain summary",
            "pass" if memory["accepted"] else "warn",
            model["brain_summary"],
            _source(api="/api/brain", path=target / ".agent" / "memory"),
            {
                "lessons": memory["lessons"],
                "accepted": memory["accepted"],
                "candidates": memory["candidates"],
            },
        ),
    ]

    lesson_objects, lesson_stats = _lesson_objects(target)
    if not lesson_objects:
        lesson_objects.append(
            _empty_object(
                "lesson-empty",
                "lesson",
                "No accepted lessons",
                "warn",
                target / ".agent" / "memory" / "semantic" / "lessons.jsonl",
            )
        )

    candidate_objects, candidate_flow = _candidate_objects(target)
    candidate_objects.insert(
        0,
        _control_object(
            "candidate-counts",
            "candidate_summary",
            "Candidate counts",
            "pass" if memory["candidates"] == 0 else "warn",
            _candidate_detail(candidate_flow),
            _source(api="/api/brain/candidates", path=target / ".agent" / "memory" / "candidates"),
            {
                **candidate_flow,
                "candidate_state": "summary",
                "source_path": str(target / ".agent" / "memory" / "candidates"),
            },
        ),
    )
    brain_stats = {
        **lesson_stats,
        "candidates": sum(candidate_flow.values()),
        "candidate_flow": candidate_flow,
    }

    adapter_objects = _adapter_objects(model, target, stack)
    if not adapter_objects:
        adapter_objects.append(
            _empty_object("adapter-empty", "adapter", "No adapters detected", "warn", target / ".agent" / "install.json")
        )
    codex_objects = [item for item in adapter_objects if item["label"] == "codex"]
    if not codex_objects:
        codex_objects = [
            _control_object(
                "adapter-codex",
                "adapter",
                "codex",
                "warn",
                "codex adapter not installed",
                _source(api="/api/harnesses/codex", path=target / ".agent" / "install.json"),
                {"name": "codex", "installed": False},
            )
        ]
    recipe_objects = _command_recipe_objects(model, target, adapter_objects)

    check_objects = _check_objects(model, target)
    verify_objects = _verify_objects(model, stack)
    trust_objects = check_objects + verify_objects
    trust_stats = _status_stats(trust_objects)

    run_objects = _run_objects(model, target)
    if not run_objects:
        run_objects.append(
            _empty_object("run-empty", "run", "No active runs", "warn", target / ".agent" / "runtime" / "instances.json")
        )

    skill_objects = _skill_objects(model, target)
    if not skill_objects:
        skill_objects.append(_empty_object("skill-empty", "skill", "No skills installed", "warn", target / ".agent" / "skills"))
    example_skill_objects = [item for item in skill_objects if item["label"] == "example"]
    if not example_skill_objects:
        example_skill_objects = [
            _control_object(
                "skill-example",
                "skill",
                "example",
                "warn",
                "example skill not installed",
                _source(api="/api/skills/example", path=target / ".agent" / "skills" / "example" / "SKILL.md"),
                {"name": "example", "installed": False},
            )
        ]

    protocol_objects = _protocol_objects(target)
    if not protocol_objects:
        protocol_objects = [
            _empty_object("protocol-empty", "protocol", "No protocols installed", "warn", target / ".agent" / "protocols")
        ]
    permission_objects = [item for item in protocol_objects if item["label"] == "permissions"]
    if not permission_objects:
        permission_objects = [
            _control_object(
                "protocol-permissions",
                "protocol",
                "permissions",
                "warn",
                "permissions protocol not found",
                _source(api="/api/protocols/permissions", path=target / ".agent" / "protocols" / "permissions.md"),
                {"name": "permissions", "installed": False},
            )
        ]

    handoff_objects = [
        _control_object(
            "handoff-readiness",
            "handoff",
            "Transfer readiness",
            "pass" if model["transfer"]["ready"] else "warn",
            str(model["transfer"]["detail"]),
            _source(api="/api/handoff", command="./install.sh transfer export"),
            model["transfer"],
        ),
        _control_object(
            "handoff-commands",
            "command",
            "Handoff commands",
            "pass",
            "status, doctor, dashboard, and transfer export commands are available",
            _source(api="/api/handoff"),
            {
                "commands": [
                    "./install.sh status",
                    "./install.sh doctor",
                    "./install.sh dashboard --plain",
                    "./install.sh transfer export",
                ]
            },
        ),
    ]

    flywheel_objects, flywheel_stats = _flywheel_objects(model, target, candidate_flow)

    ops_objects, ops_stats = _ops_event_objects(target)

    settings_objects = [
        _control_object(
            "setting-target-root",
            "setting",
            "Target root",
            "pass",
            str(target),
            _source(path=target),
            {"key": "target_root", "value": str(target), "readonly": True},
        ),
        _control_object(
            "setting-stack-root",
            "setting",
            "Stack root",
            "pass",
            str(stack),
            _source(path=stack),
            {"key": "stack_root", "value": str(stack), "readonly": True},
        ),
        _control_object(
            "setting-network",
            "setting",
            "Network binding",
            "pass",
            "defaults to 127.0.0.1:8787",
            _source(command="agentic-stack mission-control --host 127.0.0.1 --port 8787"),
            {"host": "127.0.0.1", "port": 8787, "readonly": True},
        ),
    ]

    command_stats = _command_center_stats(
        model,
        status,
        brain_stats,
        adapter_objects,
        trust_objects,
        candidate_flow,
        ops_stats,
    )
    command_objects.extend(_command_center_signal_objects(command_stats, target, model))
    command_objects = _sort_actionable(command_objects)

    return {
        "/api/command-center": _domain_payload(
            "Command Center",
            status,
            "Live local project state",
            command_objects,
            stats=command_stats,
        ),
        "/api/command-recipes": _domain_payload(
            "Command Recipes",
            "pass",
            "Copy-only local commands for audits, handoff, exports, and adapter repair",
            recipe_objects,
        ),
        "/api/brain": _domain_payload("Brain", "pass" if lesson_stats["accepted"] else "warn", model["brain_summary"], lesson_objects + candidate_objects, stats=brain_stats),
        "/api/brain/lessons": _domain_payload("Brain", "pass" if lesson_stats["accepted"] else "warn", "Accepted lessons", lesson_objects, stats=lesson_stats),
        "/api/brain/candidates": _domain_payload("Brain", "pass" if memory["candidates"] == 0 else "warn", "Memory candidate queue", candidate_objects),
        "/api/harnesses": _domain_payload("Harnesses", _objects_status(adapter_objects), "Installed and available harness adapters", adapter_objects),
        "/api/harnesses/codex": _domain_payload("Harnesses", _objects_status(codex_objects), "Codex harness adapter", codex_objects),
        "/api/trust": _domain_payload("Trust", _objects_status(trust_objects), "Doctor checks and harness verification", trust_objects, stats=trust_stats),
        "/api/trust/verify": _domain_payload("Trust", _objects_status(verify_objects), "Harness verification matrix", verify_objects, stats=_status_stats(verify_objects)),
        "/api/runs": _domain_payload("Runs", _objects_status(run_objects), "Runtime instances", run_objects),
        "/api/skills": _domain_payload("Skills", _objects_status(skill_objects), "Installed skills", skill_objects),
        "/api/skills/example": _domain_payload("Skills", _objects_status(example_skill_objects), "Example skill", example_skill_objects),
        "/api/protocols": _domain_payload("Protocols", _objects_status(protocol_objects), "Installed operating protocols", protocol_objects),
        "/api/protocols/permissions": _domain_payload("Protocols", _objects_status(permission_objects), "Permissions protocol", permission_objects),
        "/api/handoff": _domain_payload("Handoff", _objects_status(handoff_objects), "Next operator transfer package", handoff_objects),
        "/api/data-flywheel": _domain_payload("Data Flywheel", _objects_status(flywheel_objects), "Artifacts and learned signals", flywheel_objects, stats=flywheel_stats),
        "/api/ops/events": _domain_payload("Ops Console", "pass", "Persistent local browser event stream", ops_objects, stats=ops_stats),
        "/api/settings": _domain_payload("Settings", "pass", "Read-only local control-plane settings", settings_objects),
    }


def record_ops_event(target_root: Path | str, event: dict[str, Any]) -> dict[str, Any]:
    """Append one Mission Control UI/API event to the local project event log."""
    target = Path(target_root).resolve()
    event_log = _ops_event_log(target)
    event_log.parent.mkdir(parents=True, exist_ok=True)
    incoming = event if isinstance(event, dict) else {}
    payload = incoming.get("payload", {})
    if not isinstance(payload, dict):
        payload = {"value": payload}
    row = {
        "id": str(incoming.get("id") or f"ops-{uuid.uuid4().hex[:12]}"),
        "time": str(incoming.get("time") or _now_iso()),
        "type": str(incoming.get("type") or "event"),
        "payload": payload,
        "persistent": True,
        "source": "mission-control",
    }
    with event_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=True, sort_keys=True) + "\n")
    return row


def _control_object(
    identifier: str,
    kind: str,
    label: str,
    status: str,
    summary: str,
    source: dict[str, Any],
    payload: Any,
) -> dict[str, Any]:
    normalized = _normalize_status(status)
    return {
        "id": identifier,
        "kind": kind,
        "label": label,
        "status": normalized,
        "summary": summary,
        "source": source,
        "payload": _with_action_metadata(kind, label, normalized, summary, source, payload),
    }


def _domain_payload(
    domain: str,
    status: str,
    summary: str,
    objects: list[dict[str, Any]],
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "domain": domain,
        "status": _normalize_status(status),
        "summary": summary,
        "objects": objects,
    }
    if stats is not None:
        payload["stats"] = stats
    return payload


def _source(
    *,
    api: str | None = None,
    path: Path | str | None = None,
    command: str | None = None,
) -> dict[str, Any]:
    source: dict[str, Any] = {"type": "local"}
    if api:
        source["api"] = api
    if path is not None:
        source["path"] = str(path)
    if command:
        source["command"] = command
    return source


def _empty_object(identifier: str, kind: str, label: str, status: str, path: Path | str) -> dict[str, Any]:
    return _control_object(
        identifier,
        kind,
        label,
        status,
        "No matching local object was found.",
        _source(path=path),
        {"empty": True},
    )


def _with_action_metadata(
    kind: str,
    label: str,
    status: str,
    summary: str,
    source: dict[str, Any],
    payload: Any,
) -> Any:
    if not isinstance(payload, dict):
        return payload
    enriched = dict(payload)
    source_file = source.get("path") or source.get("api") or source.get("command") or "local"
    enriched.setdefault("source_file", source_file)
    if source.get("path") and not enriched.get("source_path"):
        enriched["source_path"] = source["path"]
    if not enriched.get("evidence"):
        enriched["evidence"] = _payload_evidence(enriched, source, summary)
    commands = _related_commands_for(kind, label, enriched)
    enriched.setdefault("related_commands", commands)
    enriched.setdefault("health_impact", _health_impact_for(status, kind))
    enriched.setdefault("next_action", _next_action_for(kind, status, commands))
    return enriched


def _payload_evidence(payload: dict[str, Any], source: dict[str, Any], summary: str) -> list[Any]:
    evidence = payload.get("evidence")
    if isinstance(evidence, list) and evidence:
        return evidence
    source_paths = payload.get("source_paths")
    if isinstance(source_paths, list) and source_paths:
        return source_paths
    if payload.get("source_path"):
        line = payload.get("source_line")
        suffix = f":{line}" if line else ""
        return [f"{payload['source_path']}{suffix}"]
    if source.get("path"):
        return [source["path"]]
    if source.get("command"):
        return [source["command"]]
    return [summary]


def _related_commands_for(kind: str, label: str, payload: dict[str, Any]) -> list[str]:
    commands: list[str] = []
    command = payload.get("command")
    if isinstance(command, str) and command:
        commands.append(command)
    payload_commands = payload.get("commands")
    if isinstance(payload_commands, list):
        commands.extend(str(item) for item in payload_commands if item)
    name = str(payload.get("name") or label)
    if kind == "adapter":
        if payload.get("installed"):
            commands.extend([f"./install.sh --reconfigure {name}", "./install.sh doctor"])
        else:
            commands.extend([f"./install.sh add {name}", "./install.sh doctor"])
    elif kind in {"check", "verify"}:
        commands.extend(["./install.sh doctor", "./install.sh dashboard --plain"])
    elif kind in {"lesson", "candidate", "candidate_summary", "brain"}:
        commands.extend(["python3 .agent/memory/memory_search.py --status", "./install.sh dashboard --plain"])
    elif kind in {"artifact", "flow"}:
        commands.append("python3 .agent/tools/data_layer_export.py --window 30d --bucket day")
    elif kind == "handoff":
        commands.append("./install.sh transfer export --print-curl")
    elif kind in {"status", "project", "setting"}:
        commands.append("./install.sh status")
    elif not commands:
        commands.append("./install.sh status")
    return _dedupe(commands)


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _health_impact_for(status: str, kind: str) -> str:
    if kind == "command_recipe":
        return "No direct health change; this is a copy-only operator recipe."
    if status == "fail":
        return "Blocks a clean handoff until the failing source is fixed."
    if status == "warn":
        return "Reduces readiness and should be reviewed before handoff."
    return "No immediate health impact."


def _next_action_for(kind: str, status: str, commands: list[str]) -> str:
    if kind == "command_recipe":
        return "Copy the command; Mission Control does not execute it."
    if status == "pass":
        return "Keep monitoring this source."
    if commands:
        return f"Inspect the source, then run {commands[0]}."
    return "Inspect the source and resolve the warning."


def _command_recipe_objects(
    model: dict[str, Any],
    target: Path,
    adapter_objects: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    installed = list(map(str, model.get("installed", [])))
    available = list(map(str, model.get("available", [])))
    install_candidates = [name for name in available if name not in set(installed)]
    install_adapter = install_candidates[0] if install_candidates else (available[0] if available else "<adapter>")
    repair_adapter = _repair_adapter_name(adapter_objects, installed, install_adapter)
    recipes = [
        (
            "recipe-doctor",
            "Doctor audit",
            "audit",
            "./install.sh doctor",
            "Run the read-only project audit.",
        ),
        (
            "recipe-status",
            "Status summary",
            "status",
            "./install.sh status",
            "Print installed adapters, brain state, and project status.",
        ),
        (
            "recipe-verify",
            "Verify matrix",
            "verify",
            "./install.sh dashboard --plain",
            "Render the terminal dashboard with harness verification rows.",
        ),
        (
            "recipe-transfer-export",
            "Transfer export",
            "handoff",
            './install.sh transfer export --intent "handoff current project" --print-curl',
            "Build a portable handoff bundle and print the import command.",
        ),
        (
            "recipe-transfer-import",
            "Transfer import",
            "handoff",
            "./install.sh transfer import --payload-file transfer.txt --sha256 <digest> --target codex",
            "Import a reviewed transfer bundle into this project.",
        ),
        (
            "recipe-data-layer-export",
            "Data-layer export",
            "data-layer-export",
            "python3 .agent/tools/data_layer_export.py --window 30d --bucket day",
            "Generate local dashboard exports from shared agent activity.",
        ),
        (
            f"recipe-adapter-install-{install_adapter}",
            f"Install adapter: {install_adapter}",
            "adapter-install",
            f"./install.sh add {install_adapter}",
            "Add another harness adapter without re-running onboarding.",
        ),
        (
            f"recipe-adapter-repair-{repair_adapter}",
            f"Repair adapter: {repair_adapter}",
            "adapter-repair",
            f"./install.sh --reconfigure {repair_adapter}",
            "Re-apply adapter files when verification reports drift.",
        ),
    ]
    objects: list[dict[str, Any]] = []
    for identifier, label, category, command, summary in recipes:
        payload = {
            "category": category,
            "command": command,
            "copy_only": True,
            "description": summary,
            "target_root": str(target),
        }
        objects.append(
            _control_object(
                identifier,
                "command_recipe",
                label,
                "pass",
                summary,
                _source(api="/api/command-recipes", command=command),
                payload,
            )
        )
    return objects


def _repair_adapter_name(adapter_objects: list[dict[str, Any]], installed: list[str], fallback: str) -> str:
    for item in adapter_objects:
        payload = item.get("payload", {})
        if isinstance(payload, dict) and payload.get("parity_gaps"):
            return str(payload.get("name") or item.get("label") or fallback)
    return installed[0] if installed else fallback


def _adapter_objects(model: dict[str, Any], target: Path, stack: Path) -> list[dict[str, Any]]:
    file_map = dashboard_tui._adapter_file_map(stack)
    row_by_name = {
        str(row.get("name")): row
        for row in model.get("adapters", [])
        if isinstance(row, dict) and row.get("name") is not None
    }
    installed = set(map(str, model.get("installed", [])))
    missing = set(map(str, model.get("available", [])))
    names = sorted(set(file_map) | installed | missing | set(row_by_name))
    objects: list[dict[str, Any]] = []
    for name in names:
        expected_files = file_map.get(name, [])
        missing_files = [rel for rel in expected_files if not (target / rel).exists()]
        is_installed = name in installed
        row = row_by_name.get(name, {})
        parity_gaps: list[str] = []
        if is_installed and missing_files:
            parity_gaps.append("install tracking exists but adapter files are missing")
        if not is_installed:
            parity_gaps.append("adapter is available but not installed")
        payload = {
            **row,
            "name": name,
            "installed": is_installed,
            "available": name in file_map or name in missing,
            "expected_files": expected_files,
            "missing_files": missing_files,
            "parity_gaps": parity_gaps,
            "source_path": str(target / ".agent" / "install.json"),
        }
        status = row.get("status") or ("warn" if parity_gaps else "pass")
        objects.append(
            _control_object(
                f"adapter-{name}",
                "adapter",
                name,
                str(status),
                str(row.get("detail") or ("; ".join(parity_gaps) if parity_gaps else "adapter ready")),
                _source(api="/api/harnesses", path=target / ".agent" / "install.json"),
                payload,
            )
        )
    return objects


def _check_objects(model: dict[str, Any], target: Path) -> list[dict[str, Any]]:
    path_by_label = {
        ".agent directory": target / ".agent",
        "agent map": target / ".agent" / "AGENTS.md",
        "personal preferences": target / ".agent" / "memory" / "personal" / "PREFERENCES.md",
        "install tracking": target / ".agent" / "install.json",
        "review queue": target / ".agent" / "memory" / "working" / "REVIEW_QUEUE.md",
        "team brain": target / ".agent" / "memory" / "team",
    }
    objects: list[dict[str, Any]] = []
    for index, row in enumerate(model.get("checks", [])):
        if not isinstance(row, dict):
            continue
        label = str(row.get("label", f"check {index + 1}"))
        status = str(row.get("status", "warn"))
        source_path = path_by_label.get(label, target / ".agent")
        payload = {
            **row,
            "severity": _severity(status),
            "explanation": _trust_explanation(label, status, str(row.get("detail", ""))),
            "source_paths": [str(source_path)],
        }
        objects.append(
            _control_object(
                f"check-{index + 1}",
                "check",
                label,
                status,
                str(row.get("detail", "")),
                _source(api="/api/trust", path=source_path),
                payload,
            )
        )
    return objects


def _verify_objects(model: dict[str, Any], stack: Path) -> list[dict[str, Any]]:
    objects: list[dict[str, Any]] = []
    for index, row in enumerate(model.get("verify", [])):
        if not isinstance(row, dict):
            continue
        harness = str(row.get("harness", f"harness {index + 1}"))
        status = _verify_row_status(row)
        payload = {
            **row,
            "severity": _severity(status),
            "explanation": _verify_explanation(row),
            "source_paths": [str(stack / "adapters" / harness)],
        }
        objects.append(
            _control_object(
                f"verify-{harness}",
                "verify",
                harness,
                status,
                _verify_row_summary(row),
                _source(api="/api/trust/verify", path=stack / "adapters"),
                payload,
            )
        )
    return objects


def _run_objects(model: dict[str, Any], target: Path) -> list[dict[str, Any]]:
    path = target / ".agent" / "runtime" / "instances.json"
    active_id = model["instances"].get("active_instance")
    objects: list[dict[str, Any]] = []
    for index, item in enumerate(model["instances"].get("items", [])):
        if not isinstance(item, dict):
            continue
        identifier = str(item.get("id", f"run {index + 1}"))
        state = str(item.get("state", item.get("status", "recorded")))
        active = identifier == active_id
        payload = {
            **item,
            "state": state,
            "active": active,
            "stale": state not in {"running", "active"} and not active,
            "source_path": str(path),
        }
        objects.append(
            _control_object(
                f"run-{identifier}",
                "run",
                identifier,
                state,
                state,
                _source(api="/api/runs", path=path),
                payload,
            )
        )
    return objects


def _skill_objects(model: dict[str, Any], target: Path) -> list[dict[str, Any]]:
    skills_dir = target / ".agent" / "skills"
    manifest = skills_dir / "_manifest.jsonl"
    approved_text = _safe_read_text(target / ".agent" / "memory" / "team" / "APPROVED_SKILLS.md")
    objects: list[dict[str, Any]] = []
    for name in model["skills"].get("names", []):
        skill_path = skills_dir / str(name) / "SKILL.md"
        text = _safe_read_text(skill_path)
        issues: list[str] = []
        if not skill_path.is_file():
            issues.append("SKILL.md missing")
        if text and not text.lstrip().startswith("#"):
            issues.append("SKILL.md should start with a heading")
        payload = {
            "name": name,
            "skill_path": str(skill_path),
            "valid": skill_path.is_file() and not issues,
            "approved": str(name) in approved_text,
            "issues": issues,
            "manifest_source": str(manifest),
        }
        objects.append(
            _control_object(
                f"skill-{name}",
                "skill",
                str(name),
                "pass" if payload["valid"] else "warn",
                "skill is available" if payload["valid"] else "; ".join(issues),
                _source(api="/api/skills", path=skill_path),
                payload,
            )
        )
    return objects


def _protocol_objects(target: Path) -> list[dict[str, Any]]:
    protocol_dir = target / ".agent" / "protocols"
    objects: list[dict[str, Any]] = []
    if not protocol_dir.is_dir():
        return objects
    for path in sorted(protocol_dir.glob("*.md")):
        name = path.stem
        excerpt, line_count = _bounded_excerpt(path)
        objects.append(
            _control_object(
                f"protocol-{name}",
                "protocol",
                name,
                "pass",
                f"{path.name} is installed",
                _source(api=f"/api/protocols/{name}", path=path),
                {
                    "name": name,
                    "path": str(path),
                    "source_path": str(path),
                    "line_count": line_count,
                    "excerpt": excerpt,
                },
            )
        )
    return objects


def _flywheel_objects(
    model: dict[str, Any],
    target: Path,
    candidate_flow: dict[str, int],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    memory = model["memory"]
    recent_artifacts = _recent_learning_artifacts(target)
    dashboard_payload = {
        **model["data"],
        "source_path": model["data"]["dashboard"],
        "exists": bool(model["data"]["exists"]),
    }
    memory_payload = {
        "accepted": memory["accepted"],
        "candidates": sum(candidate_flow.values()),
        "candidate_counts": candidate_flow,
        "recent_artifacts": recent_artifacts,
    }
    objects = [
        _control_object(
            "flywheel-dashboard",
            "artifact",
            "Dashboard export",
            "pass" if model["data"]["exists"] else "warn",
            str(model["data"]["dashboard"]),
            _source(api="/api/data-flywheel", path=model["data"]["dashboard"]),
            dashboard_payload,
        ),
        _control_object(
            "flywheel-memory",
            "flow",
            "Memory flow",
            "pass" if memory["accepted"] else "warn",
            f"{memory['accepted']} accepted, {sum(candidate_flow.values())} candidate signals",
            _source(api="/api/data-flywheel", path=target / ".agent" / "memory"),
            memory_payload,
        ),
    ]
    stats = {
        "candidate_flow": candidate_flow,
        "recent_artifacts": len(recent_artifacts),
        "dashboard_exists": bool(model["data"]["exists"]),
    }
    return objects, stats


def _ops_event_objects(target: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    event_log = _ops_event_log(target)
    rows = _read_jsonl_with_lines(event_log)[-50:]
    objects: list[dict[str, Any]] = []
    for line_no, row in rows:
        event_type = str(row.get("type") or "event")
        payload = {
            **row,
            "persistent": True,
            "source_path": str(event_log),
            "source_line": line_no,
        }
        objects.append(
            _control_object(
                f"ops-{row.get('id', line_no)}",
                "event",
                event_type,
                _ops_event_status(event_type),
                _ops_event_summary(payload),
                _source(api="/api/ops/events", path=event_log),
                payload,
            )
        )
    if not objects:
        objects.append(
            _control_object(
                "ops-empty",
                "event",
                "No persistent events",
                "pass",
                "Browser actions will be appended to the local ops log.",
                _source(api="/api/ops/events", path=event_log),
                {"type": "empty", "payload": {}, "persistent": False},
            )
        )
    stats = {
        "events": len(rows),
        "displayed": len(objects),
        "log_path": str(event_log),
        "persistent": event_log.is_file(),
    }
    return objects, stats


def _ops_event_log(target: Path) -> Path:
    return target / ".agent" / "runtime" / OPS_EVENT_LOG


def _ops_event_status(event_type: str) -> str:
    lowered = event_type.lower()
    if "error" in lowered or "fail" in lowered:
        return "fail"
    if "warn" in lowered:
        return "warn"
    return "pass"


def _ops_event_summary(payload: dict[str, Any]) -> str:
    event_payload = payload.get("payload", {})
    if event_payload:
        return json.dumps(event_payload, ensure_ascii=True, sort_keys=True)[:160]
    return str(payload.get("type") or "event")


def _command_center_stats(
    model: dict[str, Any],
    status: str,
    brain_stats: dict[str, Any],
    adapter_objects: list[dict[str, Any]],
    trust_objects: list[dict[str, Any]],
    candidate_flow: dict[str, int],
    ops_stats: dict[str, Any],
) -> dict[str, Any]:
    memory = model["memory"]
    parity_gaps = []
    for item in adapter_objects:
        payload = item.get("payload", {})
        if not isinstance(payload, dict):
            continue
        for gap in payload.get("parity_gaps", []):
            parity_gaps.append({"adapter": item.get("label"), "gap": gap})
    domain_statuses = [
        ("Command Center", status),
        ("Brain", "pass" if brain_stats.get("accepted") else "warn"),
        ("Harnesses", _objects_status(adapter_objects)),
        ("Trust", _objects_status(trust_objects)),
        ("Handoff", "pass" if model["transfer"]["ready"] else "warn"),
        ("Data Flywheel", "pass" if model["data"]["exists"] else "warn"),
    ]
    failing_domains = [
        {"domain": domain, "status": _normalize_status(domain_status)}
        for domain, domain_status in domain_statuses
        if _normalize_status(domain_status) != "pass"
    ]
    return {
        "failing_domains": failing_domains,
        "adapter_parity": {
            "installed": len(model.get("installed", [])),
            "available": len(model.get("available", [])),
            "parity_gaps": parity_gaps,
            "gap_count": len(parity_gaps),
        },
        "memory_queue": {
            "accepted": brain_stats.get("accepted", 0),
            "provisional": brain_stats.get("provisional", 0),
            "rejected": brain_stats.get("rejected", 0),
            "candidates": sum(candidate_flow.values()),
            "candidate_flow": candidate_flow,
            "raw_candidates": memory.get("candidates", 0),
        },
        "recent_events": {
            "events": ops_stats.get("events", 0),
            "displayed": ops_stats.get("displayed", 0),
            "log_path": ops_stats.get("log_path"),
        },
        "handoff_ready": bool(model["transfer"]["ready"]),
    }


def _command_center_signal_objects(
    stats: dict[str, Any],
    target: Path,
    model: dict[str, Any],
) -> list[dict[str, Any]]:
    failing_domains = stats["failing_domains"]
    adapter_parity = stats["adapter_parity"]
    memory_queue = stats["memory_queue"]
    recent_events = stats["recent_events"]
    handoff_ready = bool(stats["handoff_ready"])
    return [
        _control_object(
            "command-failing-domains",
            "domain_summary",
            "Failing domains",
            _status_from_domain_list(failing_domains),
            _failing_domain_summary(failing_domains),
            _source(api="/api/command-center", path=target / ".agent"),
            {"domains": failing_domains, "commands": ["./install.sh doctor", "./install.sh dashboard --plain"]},
        ),
        _control_object(
            "command-adapter-parity",
            "adapter_summary",
            "Adapter parity",
            "warn" if adapter_parity["gap_count"] else "pass",
            f"{adapter_parity['installed']} installed, {adapter_parity['gap_count']} parity gaps",
            _source(api="/api/harnesses", path=target / ".agent" / "install.json"),
            {**adapter_parity, "commands": ["./install.sh doctor", "./install.sh manage"]},
        ),
        _control_object(
            "command-memory-queue",
            "memory_summary",
            "Memory queue",
            "warn" if memory_queue["candidates"] else "pass",
            f"{memory_queue['accepted']} accepted, {memory_queue['candidates']} candidates",
            _source(api="/api/brain/candidates", path=target / ".agent" / "memory"),
            {**memory_queue, "commands": ["python3 .agent/memory/memory_search.py --status"]},
        ),
        _control_object(
            "command-recent-events",
            "event_summary",
            "Recent events",
            "pass",
            f"{recent_events['events']} persisted browser/API events",
            _source(api="/api/ops/events", path=target / ".agent" / "runtime" / OPS_EVENT_LOG),
            {**recent_events, "commands": ["./install.sh mission-control"]},
        ),
        _control_object(
            "command-handoff-ready",
            "handoff_summary",
            "Handoff readiness",
            "pass" if handoff_ready else "warn",
            str(model["transfer"]["detail"]),
            _source(api="/api/handoff", command="./install.sh transfer export --print-curl"),
            {
                "ready": handoff_ready,
                "detail": model["transfer"]["detail"],
                "commands": ["./install.sh transfer export --print-curl"],
            },
        ),
    ]


def _status_from_domain_list(domains: list[dict[str, Any]]) -> str:
    statuses = {item.get("status") for item in domains}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _failing_domain_summary(domains: list[dict[str, Any]]) -> str:
    if not domains:
        return "All control-plane domains are green."
    return ", ".join(f"{item['domain']}:{item['status']}" for item in domains)


def _sort_actionable(objects: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rank = {"fail": 0, "warn": 1, "pass": 2}
    return sorted(objects, key=lambda item: (rank.get(str(item.get("status")), 3), str(item.get("label", ""))))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _severity(status: str) -> str:
    normalized = _normalize_status(status)
    if normalized == "fail":
        return "high"
    if normalized == "warn":
        return "medium"
    return "low"


def _trust_explanation(label: str, status: str, detail: str) -> str:
    if _normalize_status(status) == "pass":
        return f"{label} is present and usable."
    if detail:
        return f"{label} needs attention: {detail}."
    return f"{label} needs attention before this project can be fully trusted."


def _verify_explanation(row: dict[str, Any]) -> str:
    failures: list[str] = []
    warnings: list[str] = []
    for key, value in row.items():
        if not isinstance(value, dict):
            continue
        status = value.get("status")
        detail = value.get("detail", "")
        if status == "fail":
            failures.append(f"{key}: {detail}")
        elif status == "warn":
            warnings.append(f"{key}: {detail}")
    if failures:
        return "Failing checks: " + "; ".join(failures)
    if warnings:
        return "Warnings: " + "; ".join(warnings)
    return "All verification checks pass."


def _status_stats(objects: list[dict[str, Any]]) -> dict[str, int]:
    stats = {"pass": 0, "warn": 0, "fail": 0}
    for item in objects:
        status = _normalize_status(str(item.get("status", "warn")))
        stats[status] = stats.get(status, 0) + 1
    return stats


def _recent_learning_artifacts(target: Path) -> list[dict[str, Any]]:
    paths = [
        target / ".agent" / "memory" / "semantic" / "lessons.jsonl",
        target / ".agent" / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl",
        target / ".agent" / "memory" / "working" / "REVIEW_QUEUE.md",
    ]
    paths.extend(sorted((target / ".agent" / "memory" / "candidates").glob("*.json")))
    out: list[dict[str, Any]] = []
    for path in paths:
        if path.is_file():
            out.append(
                {
                    "path": str(path),
                    "name": path.name,
                    "lines": len(_safe_read_text(path).splitlines()),
                }
            )
    return out[:8]


def _overall_status(failures: int, warnings: int) -> str:
    if failures:
        return "fail"
    if warnings:
        return "warn"
    return "pass"


def _objects_status(objects: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status")) for item in objects}
    if "fail" in statuses:
        return "fail"
    if "warn" in statuses:
        return "warn"
    return "pass"


def _normalize_status(status: str) -> str:
    value = str(status).lower()
    if value in {"pass", "ok", "running", "ready", "active", "accepted"}:
        return "pass"
    if value in {"fail", "failed", "error", "rejected"}:
        return "fail"
    return "warn" if value else "warn"


def _verify_row_status(row: dict[str, Any]) -> str:
    values = [value.get("status") for value in row.values() if isinstance(value, dict)]
    if any(value == "fail" for value in values):
        return "fail"
    if any(value == "warn" for value in values):
        return "warn"
    return "pass"


def _verify_row_summary(row: dict[str, Any]) -> str:
    parts = []
    for key, value in row.items():
        if isinstance(value, dict):
            parts.append(f"{key}: {value.get('status', 'warn')}")
    return ", ".join(parts) or "verification row"

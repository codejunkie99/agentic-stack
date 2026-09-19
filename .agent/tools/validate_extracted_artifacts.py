"""Validate the portable brain extracted-artifact registry and workflow contracts."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from collections import Counter
from pathlib import Path


ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,62}[a-z0-9]$")
SEMVER_RE = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+$")
ARTIFACT_TYPES = {"protocol", "skill", "tool", "workflow-template", "template", "schema"}
SOURCE_STATES = {"managed", "local-extension", "project-native"}
SCOPES = {"global", "project", "component", "local"}
STATUSES = {"drafted", "validated", "evaluated", "accepted", "active", "superseded", "archived"}
SIDE_EFFECTS = {"none": 0, "local-write": 1, "remote-read": 2, "remote-write": 3, "destructive": 4}
MEMORY_SCOPES = {"global", "project", "component", "local", "session", "effective", "requested"}
REQUIRED_SCENARIOS = {
    "valid-input",
    "missing-input",
    "stale-input",
    "permission-denied",
    "tool-failure",
    "project-overlay",
    "lower-capability-model",
    "repeat-run",
}
REQUIRED_ARTIFACTS = {
    "fleet-management",
    "fleet-manifest-schema",
    "portable-brain-system",
    "profile-layering",
    "tooling-extraction",
    "workflow-templates",
    "workflow-template-schema",
    "extract-repetitive-work",
    "validate-extracted-artifacts",
}


def _load_object(path: Path, label: str, errors: list[str]) -> dict:
    if not path.is_file():
        errors.append(f"{label} does not exist: {path}")
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        errors.append(f"{label} is not valid JSON: {error.msg}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return value


def _non_empty_strings(value: object) -> bool:
    return isinstance(value, list) and bool(value) and all(
        isinstance(item, str) and item.strip() for item in value
    )


def _valid_timestamp(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    try:
        dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def validate_workflow(
    workflow: dict,
    registry_ids: set[str],
    repo_root: Path,
    label: str = "workflow",
) -> list[str]:
    errors: list[str] = []
    required = {
        "schemaVersion", "id", "name", "scope", "version", "status", "description",
        "identity", "parameters", "preconditions", "steps", "permissions", "budget",
        "memory", "evidence", "completion", "rollback", "handoff", "evaluation", "provenance",
    }
    for key in sorted(required - set(workflow)):
        errors.append(f"{label} is missing required section: {key}")

    workflow_id = workflow.get("id")
    if not isinstance(workflow_id, str) or ID_RE.fullmatch(workflow_id) is None:
        errors.append(f"{label} has invalid id: {workflow_id}")
    if workflow.get("schemaVersion") != 1:
        errors.append(f"{label} schemaVersion must be 1")
    if workflow.get("scope") not in SCOPES:
        errors.append(f"{label} has invalid scope: {workflow.get('scope')}")
    if not isinstance(workflow.get("version"), str) or SEMVER_RE.fullmatch(workflow["version"]) is None:
        errors.append(f"{label} has invalid semantic version: {workflow.get('version')}")
    if workflow.get("status") not in STATUSES:
        errors.append(f"{label} has invalid status: {workflow.get('status')}")
    if not isinstance(workflow.get("description"), str) or len(workflow["description"].strip()) < 20:
        errors.append(f"{label} description must have at least 20 characters")

    identity = workflow.get("identity")
    identity_keys = {"requiresProfile", "requiresProject", "requiresComponent"}
    if not isinstance(identity, dict) or any(not isinstance(identity.get(key), bool) for key in identity_keys):
        errors.append(f"{label} identity must define three boolean requirements")

    parameters = workflow.get("parameters")
    if not isinstance(parameters, list):
        errors.append(f"{label} parameters must be an array")
        parameters = []
    parameter_names: list[str] = []
    for index, parameter in enumerate(parameters, start=1):
        if not isinstance(parameter, dict):
            errors.append(f"{label} parameter {index} must be an object")
            continue
        name = parameter.get("name")
        parameter_names.append(str(name))
        if not isinstance(name, str) or re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) is None:
            errors.append(f"{label} parameter {index} has invalid name: {name}")
        if parameter.get("type") not in {"string", "integer", "number", "boolean", "array", "object"}:
            errors.append(f"{label} parameter {name} has invalid type")
        if not isinstance(parameter.get("required"), bool) or not isinstance(parameter.get("sensitive"), bool):
            errors.append(f"{label} parameter {name} must define required and sensitive booleans")
        if not isinstance(parameter.get("description"), str) or len(parameter["description"].strip()) < 3:
            errors.append(f"{label} parameter {name} needs a description")
    for name, count in Counter(parameter_names).items():
        if count > 1:
            errors.append(f"{label} has duplicate parameter: {name}")

    evidence = workflow.get("evidence")
    required_evidence = set(evidence.get("required", [])) if isinstance(evidence, dict) else set()
    if not isinstance(evidence, dict) or not _non_empty_strings(evidence.get("required")):
        errors.append(f"{label} evidence must define a non-empty required list")
    if not isinstance(evidence, dict) or not isinstance(evidence.get("store"), str) or not evidence.get("store"):
        errors.append(f"{label} evidence must define a store")

    preconditions = workflow.get("preconditions")
    if not isinstance(preconditions, list) or not preconditions:
        errors.append(f"{label} must define at least one precondition")
        preconditions = []
    precondition_ids: list[str] = []
    for index, precondition in enumerate(preconditions, start=1):
        if not isinstance(precondition, dict):
            errors.append(f"{label} precondition {index} must be an object")
            continue
        precondition_id = precondition.get("id")
        precondition_ids.append(str(precondition_id))
        for key in ("id", "check", "onFailure", "evidence"):
            if not isinstance(precondition.get(key), str) or not precondition[key]:
                errors.append(f"{label} precondition {index} has invalid {key}")
        if precondition.get("sideEffect") != "none":
            errors.append(f"{label} precondition {precondition_id} must have no side effect")
        if precondition.get("evidence") not in required_evidence:
            errors.append(f"{label} precondition evidence is not workflow-required: {precondition.get('evidence')}")
    for value, count in Counter(precondition_ids).items():
        if count > 1:
            errors.append(f"{label} has duplicate precondition id: {value}")

    permissions = workflow.get("permissions")
    maximum = permissions.get("maximumSideEffect") if isinstance(permissions, dict) else None
    if maximum not in SIDE_EFFECTS:
        errors.append(f"{label} has invalid maximum side effect: {maximum}")
        maximum_rank = -1
    else:
        maximum_rank = SIDE_EFFECTS[maximum]
    if not isinstance(permissions, dict) or not isinstance(permissions.get("requiresApprovalFor"), list):
        errors.append(f"{label} permissions must define requiresApprovalFor")
    if not isinstance(permissions, dict) or not isinstance(permissions.get("forbids"), list):
        errors.append(f"{label} permissions must define forbids")

    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append(f"{label} must define at least one step")
        steps = []
    step_ids: list[str] = []
    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            errors.append(f"{label} step {index} must be an object")
            continue
        step_id = step.get("id")
        step_ids.append(str(step_id))
        for key in ("id", "use", "onFailure"):
            if not isinstance(step.get(key), str) or not step[key]:
                errors.append(f"{label} step {index} has invalid {key}")
        for key in ("with", "produces", "requiredEvidence"):
            if not isinstance(step.get(key), list) or not all(isinstance(item, str) for item in step[key]):
                errors.append(f"{label} step {step_id} has invalid {key}")
        side_effect = step.get("sideEffect")
        if side_effect not in SIDE_EFFECTS:
            errors.append(f"{label} step {step_id} has invalid side effect: {side_effect}")
        elif SIDE_EFFECTS[side_effect] > maximum_rank:
            errors.append(f"{label} step {step_id} exceeds workflow permission: {side_effect}")
        for item in step.get("requiredEvidence", []):
            if item not in required_evidence:
                errors.append(f"{label} step evidence is not workflow-required: {step_id} -> {item}")
        use = step.get("use", "")
        match = re.match(r"^(protocol|skill|tool|workflow|template|human):([^#]+)", use)
        if not match:
            errors.append(f"{label} step {step_id} has invalid use reference: {use}")
        else:
            kind, artifact_id = match.groups()
            if kind in {"protocol", "tool", "workflow", "template"} and artifact_id not in registry_ids:
                errors.append(f"{label} step {step_id} references unregistered artifact: {artifact_id}")
            if kind == "skill" and not (repo_root / ".agent/skills" / artifact_id / "SKILL.md").is_file():
                errors.append(f"{label} step {step_id} references missing skill: {artifact_id}")
    for value, count in Counter(step_ids).items():
        if count > 1:
            errors.append(f"{label} has duplicate step id: {value}")

    budget = workflow.get("budget")
    for key in ("maxToolCalls", "maxInputTokens", "maxWallMinutes"):
        if not isinstance(budget, dict) or not isinstance(budget.get(key), int) or budget[key] < 1:
            errors.append(f"{label} budget has invalid {key}")

    memory = workflow.get("memory")
    for direction in ("reads", "writes"):
        refs = memory.get(direction) if isinstance(memory, dict) else None
        if not isinstance(refs, list):
            errors.append(f"{label} memory must define {direction}")
            continue
        for ref in refs:
            if not isinstance(ref, dict) or ref.get("scope") not in MEMORY_SCOPES or not isinstance(ref.get("name"), str) or not ref.get("name"):
                errors.append(f"{label} memory {direction} has an invalid reference")

    completion = workflow.get("completion")
    if not isinstance(completion, dict) or not _non_empty_strings(completion.get("allOf")):
        errors.append(f"{label} completion must define non-empty allOf conditions")

    rollback = workflow.get("rollback")
    if not isinstance(rollback, dict) or bool(rollback.get("strategy")) == bool(rollback.get("notApplicable")):
        errors.append(f"{label} rollback must define exactly one of strategy or notApplicable")

    handoff = workflow.get("handoff")
    if not isinstance(handoff, dict) or not _non_empty_strings(handoff.get("required")):
        errors.append(f"{label} handoff must define required content")
    if not isinstance(handoff, dict) or not isinstance(handoff.get("ownerActions"), list):
        errors.append(f"{label} handoff must define ownerActions")

    evaluation = workflow.get("evaluation")
    scenarios = set(evaluation.get("scenarios", [])) if isinstance(evaluation, dict) else set()
    for scenario in sorted(REQUIRED_SCENARIOS - scenarios):
        errors.append(f"{label} evaluation omits required scenario: {scenario}")
    if not isinstance(evaluation, dict) or evaluation.get("requiresIndependentContext") is not True:
        errors.append(f"{label} evaluation must require independent context")
    if not isinstance(evaluation, dict) or evaluation.get("requiresLowerCapabilityModel") is not True:
        errors.append(f"{label} evaluation must require a lower-capability model")

    provenance = workflow.get("provenance")
    if not isinstance(provenance, dict) or not isinstance(provenance.get("author"), str) or not provenance.get("author"):
        errors.append(f"{label} provenance must define author")
    if not isinstance(provenance, dict) or not _non_empty_strings(provenance.get("sources")):
        errors.append(f"{label} provenance must define sources")
    else:
        for source in provenance["sources"]:
            source_path = repo_root / source.split("#", maxsplit=1)[0]
            if source.startswith(".agent/") and not source_path.is_file():
                errors.append(f"{label} provenance source does not exist: {source}")
    if not isinstance(provenance, dict) or not _valid_timestamp(provenance.get("observedAt")):
        errors.append(f"{label} provenance observedAt must be an ISO timestamp")
    if isinstance(provenance, dict) and "supersedes" not in provenance:
        errors.append(f"{label} provenance must define supersedes")

    return errors


def validate_registry(registry_path: Path, repo_root: Path) -> list[str]:
    errors: list[str] = []
    registry = _load_object(registry_path, "artifact registry", errors)
    if registry.get("schemaVersion") != 1:
        errors.append("artifact registry schemaVersion must be 1")
    if not _valid_timestamp(registry.get("observedAt")):
        errors.append("artifact registry observedAt must be an ISO timestamp")
    artifacts = registry.get("artifacts")
    if not isinstance(artifacts, list):
        return errors + ["artifact registry artifacts must be an array"]

    ids: list[str] = []
    paths: list[str] = []
    by_id: dict[str, dict] = {}
    for index, artifact in enumerate(artifacts, start=1):
        if not isinstance(artifact, dict):
            errors.append(f"artifact {index} must be an object")
            continue
        artifact_id = artifact.get("id")
        ids.append(str(artifact_id))
        paths.append(str(artifact.get("path")))
        by_id[str(artifact_id)] = artifact
        if not isinstance(artifact_id, str) or ID_RE.fullmatch(artifact_id) is None:
            errors.append(f"artifact {index} has invalid id: {artifact_id}")
        if artifact.get("type") not in ARTIFACT_TYPES:
            errors.append(f"artifact {artifact_id} has invalid type: {artifact.get('type')}")
        if artifact.get("scope") not in SCOPES:
            errors.append(f"artifact {artifact_id} has invalid scope: {artifact.get('scope')}")
        if not isinstance(artifact.get("version"), str) or SEMVER_RE.fullmatch(artifact["version"]) is None:
            errors.append(f"artifact {artifact_id} has invalid version")
        if artifact.get("status") not in STATUSES:
            errors.append(f"artifact {artifact_id} has invalid status")
        if not isinstance(artifact.get("owner"), str) or not artifact.get("owner"):
            errors.append(f"artifact {artifact_id} has no owner")
        path = artifact.get("path")
        if not isinstance(path, str) or not path.startswith(".agent/"):
            errors.append(f"artifact {artifact_id} path must be inside .agent")
        elif artifact.get("status") == "active" and not (repo_root / path).is_file():
            errors.append(f"active artifact does not exist: {artifact_id} -> {path}")
        if not _non_empty_strings(artifact.get("triggers")):
            errors.append(f"artifact {artifact_id} needs triggers")
        if artifact.get("sourceState") not in SOURCE_STATES:
            errors.append(f"artifact {artifact_id} has invalid sourceState")
        if artifact.get("sourceState") == "local-extension" and not artifact.get("upstreamTarget"):
            errors.append(f"local extension has no upstream target: {artifact_id}")

    for value, count in Counter(ids).items():
        if count > 1:
            errors.append(f"duplicate artifact id: {value}")
    for value, count in Counter(paths).items():
        if count > 1:
            errors.append(f"duplicate artifact path: {value}")
    for artifact_id in sorted(REQUIRED_ARTIFACTS - set(ids)):
        errors.append(f"required extracted artifact is unregistered: {artifact_id}")

    registry_ids = set(ids)
    for artifact_id, artifact in by_id.items():
        if artifact.get("type") != "workflow-template" or not isinstance(artifact.get("path"), str):
            continue
        workflow_path = repo_root / artifact["path"]
        workflow = _load_object(workflow_path, f"workflow {artifact_id}", errors)
        schema_ref = workflow.get("$schema")
        if not isinstance(schema_ref, str) or not (workflow_path.parent / schema_ref).resolve().is_file():
            errors.append(f"workflow {artifact_id} schema reference does not exist: {schema_ref}")
        errors.extend(validate_workflow(workflow, registry_ids, repo_root, f"workflow {artifact_id}"))
        for field in ("id", "scope", "version", "status"):
            if workflow.get(field) != artifact.get(field):
                errors.append(
                    f"workflow {artifact_id} {field} differs from registry: "
                    f"{workflow.get(field)} != {artifact.get(field)}"
                )

    for artifact_id, artifact in by_id.items():
        if artifact.get("type") != "schema" or not isinstance(artifact.get("path"), str):
            continue
        _load_object(repo_root / artifact["path"], f"schema {artifact_id}", errors)

    agents_path = repo_root / ".agent/AGENTS.md"
    agents_text = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else ""
    for protocol_id in (
        "fleet-management",
        "portable-brain-system",
        "profile-layering",
        "tooling-extraction",
        "workflow-templates",
    ):
        if f"protocols/{protocol_id}.md" not in agents_text:
            errors.append(f"portable brain map does not register protocol: {protocol_id}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate extracted portable-brain artifacts and workflow templates."
    )
    parser.add_argument(
        "--registry",
        default=".agent/config/extracted-artifacts.json",
        help="Artifact registry path relative to the repository root.",
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root. Defaults to the current directory.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable output.")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    registry_path = Path(args.registry)
    if not registry_path.is_absolute():
        registry_path = repo_root / registry_path
    errors = validate_registry(registry_path, repo_root)
    if args.json:
        print(json.dumps({"status": "PASS" if not errors else "FAIL", "errors": errors}, indent=2))
    elif errors:
        print("FAIL: extracted portable-brain artifacts")
        for error in errors:
            print(f"- {error}")
    else:
        print("PASS: extracted portable-brain artifacts and workflow templates")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

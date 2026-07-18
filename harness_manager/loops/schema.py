"""Strict validators for portable agentic-loop JSON contracts."""

from __future__ import annotations

import json
import re
import string
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Callable

SCHEMA_VERSION = 1
AUTONOMY_LEVELS = {"L1", "L2", "L3"}
CAPABILITIES = {"workspace_write", "network_read", "external_write"}
PLACEHOLDERS = {"prompt", "task", "target", "run_id", "attempt"}

_LOOP_KEYS = {
    "schema_version",
    "name",
    "description",
    "autonomy",
    "executor",
    "checker",
    "state_file",
    "isolation",
    "instructions",
    "verification",
    "limits",
    "approval",
    "tags",
}
_LOOP_REQUIRED = _LOOP_KEYS - {"checker", "verification"}
_LIMIT_KEYS = {
    "max_attempts",
    "max_runtime_seconds",
    "max_output_chars",
    "estimated_token_budget",
    "stagnation_threshold",
}
_PROFILE_KEYS = {
    "adapter",
    "command",
    "timeout_seconds",
    "mutates_workspace",
    "capabilities",
    "usage_source",
}
_LOOP_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_FORMATTER = string.Formatter()


class ContractError(ValueError):
    """Raised when a loop contract fails closed validation."""


def _object(raw: object, source: str, field: str) -> dict:
    if not isinstance(raw, dict):
        raise ContractError(f"{source}: {field} must be an object")
    if not all(isinstance(key, str) for key in raw):
        raise ContractError(f"{source}: {field} keys must be strings")
    return raw


def _exact_keys(
    raw: dict,
    source: str,
    field: str,
    allowed: set[str],
    required: set[str] | None = None,
) -> None:
    required = allowed if required is None else required
    unknown = sorted(set(raw) - allowed)
    missing = sorted(required - set(raw))
    if unknown:
        raise ContractError(f"{source}: {field} has unknown field(s): {', '.join(unknown)}")
    if missing:
        raise ContractError(f"{source}: {field} missing required field(s): {', '.join(missing)}")


def _schema_version(raw: object, source: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw != SCHEMA_VERSION:
        raise ContractError(f"{source}: schema_version must be {SCHEMA_VERSION}")
    return raw


def _text(raw: object, source: str, field: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ContractError(f"{source}: {field} must be a non-empty string")
    return raw


def _boolean(raw: object, source: str, field: str) -> bool:
    if not isinstance(raw, bool):
        raise ContractError(f"{source}: {field} must be a boolean")
    return raw


def _positive_int(raw: object, source: str, field: str) -> int:
    if isinstance(raw, bool) or not isinstance(raw, int) or raw <= 0:
        raise ContractError(f"{source}: {field} must be a positive integer")
    return raw


def _string_list(raw: object, source: str, field: str) -> list[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) and item for item in raw):
        raise ContractError(f"{source}: {field} must be an array of non-empty strings")
    return list(raw)


def _validate_placeholders(value: str, source: str, field: str) -> None:
    try:
        parsed = list(_FORMATTER.parse(value))
    except ValueError as exc:
        raise ContractError(f"{source}: {field} has invalid placeholder syntax") from exc
    for _, name, format_spec, conversion in parsed:
        if name is None:
            continue
        if name not in PLACEHOLDERS or format_spec or conversion:
            raise ContractError(f"{source}: {field} has unsupported placeholder {{{name}}}")


def _command(raw: object, source: str, field: str) -> list[str]:
    command = _string_list(raw, source, field)
    if not command:
        raise ContractError(f"{source}: {field} command must not be empty")
    for index, argument in enumerate(command):
        _validate_placeholders(argument, source, f"{field}[{index}] placeholder")
    return command


def safe_relative_path(value: str, source: str, field: str) -> Path:
    """Return a normalized project-relative path or fail closed."""
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ContractError(f"{source}: {field} must be a non-empty relative path")
    posix = PurePosixPath(value)
    windows = PureWindowsPath(value)
    if (
        value == "."
        or posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or "\\" in value
        or any(part in {"", ".", ".."} for part in posix.parts)
    ):
        raise ContractError(f"{source}: {field} must stay within the target project")
    return Path(*posix.parts)


def _limits(raw: object, source: str, field: str) -> dict:
    value = _object(raw, source, field)
    _exact_keys(value, source, field, _LIMIT_KEYS)
    return {key: _positive_int(value[key], source, f"{field}.{key}") for key in sorted(_LIMIT_KEYS)}


def validate_loop(raw: object, source: str) -> dict:
    value = _object(raw, source, "loop")
    _exact_keys(value, source, "loop", _LOOP_KEYS, _LOOP_REQUIRED)
    version = _schema_version(value["schema_version"], source)
    name = _text(value["name"], source, "name")
    if not _LOOP_NAME.fullmatch(name):
        raise ContractError(f"{source}: name contains unsafe characters")
    autonomy = _text(value["autonomy"], source, "autonomy")
    if autonomy not in AUTONOMY_LEVELS:
        raise ContractError(f"{source}: autonomy must be one of {sorted(AUTONOMY_LEVELS)}")

    isolation = _object(value["isolation"], source, "isolation")
    _exact_keys(isolation, source, "isolation", {"mode", "base"})
    mode = _text(isolation["mode"], source, "isolation.mode")
    if mode not in {"current", "worktree"}:
        raise ContractError(f"{source}: isolation.mode must be current or worktree")

    instructions = _object(value["instructions"], source, "instructions")
    _exact_keys(instructions, source, "instructions", {"initial", "retry", "check"})
    normalized_instructions = {}
    for key in ("initial", "retry", "check"):
        text = _text(instructions[key], source, f"instructions.{key}")
        _validate_placeholders(text, source, f"instructions.{key} placeholder")
        normalized_instructions[key] = text

    verification = None
    if "verification" in value:
        verifier = _object(value["verification"], source, "verification")
        _exact_keys(verifier, source, "verification", {"command", "timeout_seconds"})
        verification = {
            "command": _command(verifier["command"], source, "verification.command"),
            "timeout_seconds": _positive_int(
                verifier["timeout_seconds"], source, "verification.timeout_seconds"
            ),
        }

    checker = value.get("checker")
    if checker is not None:
        checker = _text(checker, source, "checker")
    executor = _text(value["executor"], source, "executor")
    if autonomy in {"L2", "L3"}:
        if verification is None:
            raise ContractError(f"{source}: {autonomy} loop requires verification")
        if checker is None:
            raise ContractError(f"{source}: {autonomy} loop requires checker")
        if checker == executor:
            raise ContractError(f"{source}: checker must be distinct from executor")
        if mode != "worktree":
            raise ContractError(f"{source}: {autonomy} loop requires worktree isolation")

    approval = _object(value["approval"], source, "approval")
    _exact_keys(
        approval,
        source,
        "approval",
        {"before_first_mutating_run", "before_external_write"},
    )
    tags = _string_list(value["tags"], source, "tags")
    if len(tags) != len(set(tags)):
        raise ContractError(f"{source}: tags must be unique")

    normalized = {
        "schema_version": version,
        "name": name,
        "description": _text(value["description"], source, "description"),
        "autonomy": autonomy,
        "executor": executor,
        "state_file": safe_relative_path(value["state_file"], source, "state_file").as_posix(),
        "isolation": {"mode": mode, "base": _text(isolation["base"], source, "isolation.base")},
        "instructions": normalized_instructions,
        "limits": _limits(value["limits"], source, "limits"),
        "approval": {
            "before_first_mutating_run": _boolean(
                approval["before_first_mutating_run"], source, "approval.before_first_mutating_run"
            ),
            "before_external_write": _boolean(
                approval["before_external_write"], source, "approval.before_external_write"
            ),
        },
        "tags": tags,
    }
    if checker is not None:
        normalized["checker"] = checker
    if verification is not None:
        normalized["verification"] = verification
    return normalized


def validate_profiles(raw: object, source: str) -> dict:
    value = _object(raw, source, "harnesses")
    _exact_keys(value, source, "harnesses", {"schema_version", "profiles"})
    profiles = _object(value["profiles"], source, "profiles")
    if not profiles:
        raise ContractError(f"{source}: profiles must not be empty")
    normalized = {}
    for name in sorted(profiles):
        if not _LOOP_NAME.fullmatch(name):
            raise ContractError(f"{source}: profile name {name!r} is invalid")
        profile = _object(profiles[name], source, f"profiles.{name}")
        _exact_keys(profile, source, f"profiles.{name}", _PROFILE_KEYS)
        capabilities = _string_list(
            profile["capabilities"], source, f"profiles.{name}.capabilities"
        )
        unknown_capabilities = sorted(set(capabilities) - CAPABILITIES)
        if unknown_capabilities:
            raise ContractError(
                f"{source}: profiles.{name}.capabilities has unknown values: "
                f"{', '.join(unknown_capabilities)}"
            )
        if len(capabilities) != len(set(capabilities)):
            raise ContractError(f"{source}: profiles.{name}.capabilities must be unique")
        mutates = _boolean(
            profile["mutates_workspace"], source, f"profiles.{name}.mutates_workspace"
        )
        if name == "checker" and mutates:
            raise ContractError(f"{source}: checker profile must be non-mutating")
        if name == "checker" and "external_write" in capabilities:
            raise ContractError(f"{source}: checker profile cannot use external_write")
        normalized[name] = {
            "adapter": _text(profile["adapter"], source, f"profiles.{name}.adapter"),
            "command": _command(profile["command"], source, f"profiles.{name}.command"),
            "timeout_seconds": _positive_int(
                profile["timeout_seconds"], source, f"profiles.{name}.timeout_seconds"
            ),
            "mutates_workspace": mutates,
            "capabilities": capabilities,
            "usage_source": _text(
                profile["usage_source"], source, f"profiles.{name}.usage_source"
            ),
        }
    return {"schema_version": _schema_version(value["schema_version"], source), "profiles": normalized}


def validate_constraints(raw: object, source: str) -> dict:
    value = _object(raw, source, "constraints")
    keys = {
        "schema_version",
        "deny_paths",
        "allow_paths",
        "max_changed_files",
        "external_writes_require_approval",
    }
    _exact_keys(value, source, "constraints", keys)
    return {
        "schema_version": _schema_version(value["schema_version"], source),
        "deny_paths": _string_list(value["deny_paths"], source, "deny_paths"),
        "allow_paths": _string_list(value["allow_paths"], source, "allow_paths"),
        "max_changed_files": _positive_int(
            value["max_changed_files"], source, "max_changed_files"
        ),
        "external_writes_require_approval": _boolean(
            value["external_writes_require_approval"],
            source,
            "external_writes_require_approval",
        ),
    }


def validate_budget(raw: object, source: str) -> dict:
    value = _object(raw, source, "budget")
    _exact_keys(value, source, "budget", {"schema_version"} | _LIMIT_KEYS)
    return {
        "schema_version": _schema_version(value["schema_version"], source),
        **_limits({key: value[key] for key in _LIMIT_KEYS}, source, "budget"),
    }


def _load_json(path: Path, label: str) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"{label}: contract file not found: {path}") from exc
    except OSError as exc:
        raise ContractError(f"{label}: cannot read contract file: {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"{label}: invalid JSON in {path}: {exc.msg}") from exc


def load_contracts(target_root: Path, loop_name: str) -> dict[str, dict]:
    """Load and cross-check one loop and its fixed sibling contracts."""
    root = Path(target_root)
    if not isinstance(loop_name, str) or not _LOOP_NAME.fullmatch(loop_name):
        raise ContractError("loop_name must be a safe portable name")
    loops_dir = root / ".agent" / "loops"
    specs: tuple[tuple[str, str, Callable[[object, str], dict]], ...] = (
        ("loop", f"{loop_name}.json", validate_loop),
        ("profiles", "harnesses.json", validate_profiles),
        ("constraints", "constraints.json", validate_constraints),
        ("budget", "budget.json", validate_budget),
    )
    contracts = {}
    for key, filename, validator in specs:
        path = loops_dir / filename
        contracts[key] = validator(_load_json(path, filename), filename)

    loop = contracts["loop"]
    if loop["name"] != loop_name:
        raise ContractError(f"{loop_name}.json: name must match its filename")
    profiles = contracts["profiles"]["profiles"]
    if loop["executor"] not in profiles:
        raise ContractError(f"{loop_name}.json: executor profile does not exist")
    checker_name = loop.get("checker")
    if checker_name is not None:
        if checker_name not in profiles:
            raise ContractError(f"{loop_name}.json: checker profile does not exist")
        checker = profiles[checker_name]
        if checker["mutates_workspace"]:
            raise ContractError(f"{loop_name}.json: checker profile must be non-mutating")
        if "external_write" in checker["capabilities"]:
            raise ContractError(f"{loop_name}.json: checker profile cannot use external_write")
    return contracts

from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_manager.loops.schema import (
    ContractError,
    load_contracts,
    safe_relative_path,
    validate_budget,
    validate_constraints,
    validate_loop,
    validate_profiles,
)


def valid_loop() -> dict:
    return {
        "schema_version": 1,
        "name": "ci-sweeper",
        "description": "Fix one CI regression.",
        "autonomy": "L2",
        "executor": "maker",
        "checker": "checker",
        "state_file": ".agent/runtime/loops/ci-sweeper-state.json",
        "isolation": {"mode": "worktree", "base": "HEAD"},
        "instructions": {
            "initial": "Fix {task}.",
            "retry": "Use feedback for attempt {attempt}.",
            "check": "Review it.",
        },
        "verification": {
            "command": ["python3", "-m", "pytest"],
            "timeout_seconds": 30,
        },
        "limits": {
            "max_attempts": 3,
            "max_runtime_seconds": 60,
            "max_output_chars": 10000,
            "estimated_token_budget": 5000,
            "stagnation_threshold": 2,
        },
        "approval": {
            "before_first_mutating_run": True,
            "before_external_write": True,
        },
        "tags": ["ci"],
    }


def valid_profiles() -> dict:
    return {
        "schema_version": 1,
        "profiles": {
            "maker": {
                "adapter": "custom",
                "command": ["agent", "run", "{prompt}"],
                "timeout_seconds": 30,
                "mutates_workspace": True,
                "capabilities": ["workspace_write"],
                "usage_source": "none",
            },
            "checker": {
                "adapter": "custom",
                "command": ["agent", "review", "{prompt}"],
                "timeout_seconds": 30,
                "mutates_workspace": False,
                "capabilities": [],
                "usage_source": "none",
            },
        },
    }


def valid_constraints() -> dict:
    return {
        "schema_version": 1,
        "deny_paths": [".env", "**/secrets/**"],
        "allow_paths": [],
        "max_changed_files": 10,
        "external_writes_require_approval": True,
    }


def valid_budget() -> dict:
    return {
        "schema_version": 1,
        "max_attempts": 5,
        "max_runtime_seconds": 7200,
        "max_output_chars": 250000,
        "estimated_token_budget": 250000,
        "stagnation_threshold": 3,
    }


def test_valid_loop_is_normalized():
    loop = validate_loop(valid_loop(), "test.json")
    assert loop["name"] == "ci-sweeper"
    assert loop["isolation"]["mode"] == "worktree"
    assert loop == json.loads(json.dumps(loop, sort_keys=True))


@pytest.mark.parametrize(
    "path", ["../outside", "/tmp/outside", "C:\\outside", "\\\\server\\share"]
)
def test_state_path_cannot_escape_project(path):
    raw = valid_loop()
    raw["state_file"] = path
    with pytest.raises(ContractError, match="state_file"):
        validate_loop(raw, "bad.json")


def test_safe_relative_path_rejects_empty_and_parent_components():
    for value in ("", ".", "safe/../outside"):
        with pytest.raises(ContractError, match="output"):
            safe_relative_path(value, "bad.json", "output")


def test_l2_requires_verifier_checker_and_worktree():
    for field in ("checker", "verification"):
        raw = valid_loop()
        raw.pop(field)
        with pytest.raises(ContractError, match=field):
            validate_loop(raw, "bad.json")
    raw = valid_loop()
    raw["isolation"]["mode"] = "current"
    with pytest.raises(ContractError, match="worktree"):
        validate_loop(raw, "bad.json")


def test_checker_must_be_distinct():
    raw = valid_loop()
    raw["checker"] = raw["executor"]
    with pytest.raises(ContractError, match="distinct"):
        validate_loop(raw, "bad.json")


def test_unknown_fields_fail_closed_at_nested_levels():
    raw = valid_loop()
    raw["max_atempts"] = 3
    with pytest.raises(ContractError, match="unknown"):
        validate_loop(raw, "bad.json")
    raw = valid_loop()
    raw["limits"]["max_atempts"] = 3
    with pytest.raises(ContractError, match="unknown"):
        validate_loop(raw, "bad.json")


def test_positive_integers_reject_bools():
    raw = valid_loop()
    raw["limits"]["max_attempts"] = True
    with pytest.raises(ContractError, match="max_attempts"):
        validate_loop(raw, "bad.json")


def test_commands_must_be_non_empty_string_arrays():
    for command in ("pytest", [], ["pytest", 2]):
        raw = valid_loop()
        raw["verification"]["command"] = command
        with pytest.raises(ContractError, match="command"):
            validate_loop(raw, "bad.json")


@pytest.mark.parametrize("value", ["{unknown}", "{prompt!r}", "{attempt:03d}"])
def test_unknown_or_formatted_placeholders_are_rejected(value):
    raw = valid_profiles()
    raw["profiles"]["maker"]["command"] = ["agent", value]
    with pytest.raises(ContractError, match="placeholder"):
        validate_profiles(raw, "harnesses.json")


def test_checker_profile_must_be_read_only():
    raw = valid_profiles()
    raw["profiles"]["checker"]["mutates_workspace"] = True
    with pytest.raises(ContractError, match="checker"):
        validate_profiles(raw, "harnesses.json")
    raw = valid_profiles()
    raw["profiles"]["checker"]["capabilities"] = ["external_write"]
    with pytest.raises(ContractError, match="external_write"):
        validate_profiles(raw, "harnesses.json")


def test_profiles_constraints_and_budget_are_strict():
    assert validate_profiles(valid_profiles(), "harnesses.json")["schema_version"] == 1
    assert validate_constraints(valid_constraints(), "constraints.json")["max_changed_files"] == 10
    assert validate_budget(valid_budget(), "budget.json")["max_attempts"] == 5
    for validator, raw in (
        (validate_profiles, valid_profiles()),
        (validate_constraints, valid_constraints()),
        (validate_budget, valid_budget()),
    ):
        raw["surprise"] = True
        with pytest.raises(ContractError, match="unknown"):
            validator(raw, "bad.json")


def test_load_contracts_uses_only_fixed_loop_directory_files(tmp_path: Path):
    loops = tmp_path / ".agent" / "loops"
    loops.mkdir(parents=True)
    documents = {
        "ci-sweeper.json": valid_loop(),
        "harnesses.json": valid_profiles(),
        "constraints.json": valid_constraints(),
        "budget.json": valid_budget(),
    }
    for name, document in documents.items():
        (loops / name).write_text(json.dumps(document), encoding="utf-8")

    contracts = load_contracts(tmp_path, "ci-sweeper")

    assert set(contracts) == {"loop", "profiles", "constraints", "budget"}
    with pytest.raises(ContractError, match="loop_name"):
        load_contracts(tmp_path, "../outside")


def test_load_contracts_reports_invalid_json(tmp_path: Path):
    loops = tmp_path / ".agent" / "loops"
    loops.mkdir(parents=True)
    (loops / "ci-sweeper.json").write_text("{", encoding="utf-8")
    with pytest.raises(ContractError, match="JSON"):
        load_contracts(tmp_path, "ci-sweeper")

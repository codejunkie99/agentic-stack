from __future__ import annotations

import json
from pathlib import Path

import pytest

from harness_manager.loops.policy import (
    check_changed_paths,
    estimate_tokens,
    evaluate_breaker,
    normalize_failure,
)
from harness_manager.loops.storage import (
    CheckpointError,
    append_event,
    checkpoint_path,
    is_paused,
    list_checkpoints,
    load_checkpoint,
    runtime_dir,
    save_checkpoint,
    set_pause_all,
)


def test_checkpoint_write_is_atomic_and_round_trips(tmp_path: Path):
    run = {
        "schema_version": 1,
        "run_id": "run-1",
        "status": "created",
        "task": "secret task",
    }
    save_checkpoint(tmp_path, run)
    assert load_checkpoint(tmp_path, "run-1") == run
    assert not list(runtime_dir(tmp_path).glob("*.tmp"))


def test_save_requires_matching_safe_run_id(tmp_path: Path):
    with pytest.raises(CheckpointError, match="run_id"):
        save_checkpoint(tmp_path, {"run_id": "../escape"})
    with pytest.raises(CheckpointError, match="run_id"):
        checkpoint_path(tmp_path, "/absolute")
    with pytest.raises(CheckpointError, match="serialize checkpoint"):
        save_checkpoint(tmp_path, {"run_id": "run-1", "other": {1, 2}})


def test_event_excludes_sensitive_fields(tmp_path: Path):
    payload = {
        "run_id": "run-1",
        "event": "maker_finished",
        "task": "secret",
        "prompt": "secret",
    }
    append_event(tmp_path, payload)
    event = json.loads((runtime_dir(tmp_path) / "events.jsonl").read_text())
    assert event == {"run_id": "run-1", "event": "maker_finished"}
    assert payload["task"] == "secret"


def test_event_write_failure_is_reported(tmp_path: Path):
    destination = runtime_dir(tmp_path)
    destination.parent.mkdir(parents=True)
    destination.write_text("not a directory", encoding="utf-8")
    with pytest.raises(CheckpointError, match="event"):
        append_event(tmp_path, {"run_id": "run-1", "event": "started"})


def test_corrupt_checkpoint_is_preserved_and_rejected(tmp_path: Path):
    path = runtime_dir(tmp_path) / "run-1.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(CheckpointError, match="corrupt"):
        load_checkpoint(tmp_path, "run-1")
    assert path.read_text(encoding="utf-8") == "{broken"


def test_list_checkpoints_and_global_pause(tmp_path: Path):
    save_checkpoint(tmp_path, {"run_id": "run-2", "status": "done"})
    save_checkpoint(tmp_path, {"run_id": "run-1", "status": "paused"})
    assert [item["run_id"] for item in list_checkpoints(tmp_path)] == ["run-1", "run-2"]
    assert not is_paused(tmp_path)
    set_pause_all(tmp_path, True)
    assert is_paused(tmp_path)
    set_pause_all(tmp_path, False)
    assert not is_paused(tmp_path)


def test_repeated_failure_trips_stagnation():
    attempts = [
        {"outcome": "failed", "verifier_output": "FAILED at /tmp/a/test.py:123"},
        {"outcome": "failed", "verifier_output": "FAILED at /tmp/b/test.py:456"},
    ]
    decision = evaluate_breaker(
        attempts, limits={"stagnation_threshold": 2}, counters={}
    )
    assert decision.stop and decision.reason == "stagnation"


def test_breaker_checks_pause_and_hard_limits_before_stagnation():
    limits = {
        "max_attempts": 3,
        "max_runtime_seconds": 60,
        "max_output_chars": 1000,
        "estimated_token_budget": 100,
        "stagnation_threshold": 2,
    }
    cases = (
        ({"paused": True}, "paused"),
        ({"attempts": 3}, "attempt_budget"),
        ({"runtime_seconds": 60}, "runtime_budget"),
        ({"estimated_tokens": 100}, "token_budget"),
        ({"output_chars": 1000}, "output_budget"),
    )
    attempts = [
        {"outcome": "failed", "verifier_output": "same"},
        {"outcome": "failed", "verifier_output": "same"},
    ]
    for counters, reason in cases:
        assert evaluate_breaker(attempts, limits, counters).reason == reason


def test_failure_normalization_and_token_estimation(tmp_path: Path):
    text = f"2026-07-18T12:13:14Z FAIL {tmp_path}/test.py:123 id 123456789"
    normalized = normalize_failure(text, tmp_path)
    assert str(tmp_path) not in normalized
    assert "2026-07-18" not in normalized
    assert ":123" not in normalized
    assert "123456789" not in normalized
    assert estimate_tokens("abc", "de") == 2


def test_deny_path_and_allow_path_fail_closed():
    policy = {
        "deny_paths": ["auth/**"],
        "allow_paths": ["src/**"],
        "max_changed_files": 3,
    }
    assert check_changed_paths(["auth/token.py"], policy).reason == "deny_path"
    assert check_changed_paths(["docs/readme.md"], policy).reason == "outside_allowlist"
    assert not check_changed_paths(["src/main.py"], policy).stop


@pytest.mark.parametrize("path", ["../escape", "/absolute", "C:\\escape", "a/../../b"])
def test_changed_paths_reject_escape(path: str):
    decision = check_changed_paths(
        [path], {"deny_paths": [], "allow_paths": [], "max_changed_files": 3}
    )
    assert decision.stop and decision.reason == "path_escape"


def test_changed_path_count_and_recursive_glob_compatibility():
    policy = {
        "deny_paths": ["**/secrets/**"],
        "allow_paths": [],
        "max_changed_files": 1,
    }
    assert check_changed_paths(["app/secrets/key.txt"], policy).reason == "deny_path"
    assert check_changed_paths(["a.txt", "b.txt"], policy).reason == "changed_file_limit"

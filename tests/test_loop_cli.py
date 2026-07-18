from __future__ import annotations

import json
from pathlib import Path

from harness_manager.loops import commands
from harness_manager.loops.runner import start_run

from test_loop_runner import install_target


def test_validate_json_is_one_object_and_invalid_contract_is_exit_2(tmp_path: Path, capsys):
    target = install_target(tmp_path)
    assert commands.run(["validate", str(target), "--json"], default_target=target, stack_root=tmp_path) == 0
    output = capsys.readouterr().out
    assert json.loads(output)["loop"] == "ci-sweeper"
    (target / ".agent" / "loops" / "ci-sweeper.json").write_text("{", encoding="utf-8")
    assert commands.run(["validate", str(target)], default_target=target, stack_root=tmp_path) == 2


def test_run_status_resume_stop_and_audit(tmp_path: Path, capsys):
    target = install_target(tmp_path)
    assert commands.run(
        ["run", "ci-sweeper", "do it", str(target), "--approved", "--json"],
        default_target=target,
        stack_root=tmp_path,
    ) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "completed"
    run_id = result["run_id"]
    assert commands.run(["status", str(target), "--json"], default_target=target, stack_root=tmp_path) == 0
    assert run_id in capsys.readouterr().out
    assert commands.run(["audit", str(target), "--strict"], default_target=target, stack_root=tmp_path) == 0
    assert commands.run(["stop", run_id, str(target)], default_target=target, stack_root=tmp_path) == 0


def test_init_never_overwrites_without_force_and_force_keeps_runtime(tmp_path: Path, capsys):
    stack = tmp_path / "stack"
    source = stack / ".agent" / "loops"
    source.mkdir(parents=True)
    (source / "example.json").write_text("source", encoding="utf-8")
    target = tmp_path / "target"
    (target / ".agent" / "loops").mkdir(parents=True)
    (target / ".agent" / "loops" / "example.json").write_text("user", encoding="utf-8")
    runtime = target / ".agent" / "runtime" / "loops" / "state.json"
    runtime.parent.mkdir(parents=True)
    runtime.write_text("keep", encoding="utf-8")
    assert commands.run(["init", str(target)], default_target=target, stack_root=stack) == 0
    assert (target / ".agent" / "loops" / "example.json").read_text() == "user"
    assert commands.run(["init", str(target), "--force"], default_target=target, stack_root=stack) == 0
    assert (target / ".agent" / "loops" / "example.json").read_text() == "source"
    assert runtime.read_text() == "keep"


def test_approval_pause_maps_to_successful_command_with_reason(tmp_path: Path, capsys):
    target = install_target(tmp_path)
    assert commands.run(["run", "ci-sweeper", "do it", str(target)], default_target=target, stack_root=tmp_path) == 0
    output = capsys.readouterr().out
    assert "awaiting_approval" in output

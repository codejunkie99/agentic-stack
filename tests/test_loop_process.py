from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from harness_manager.loops.process import expand_command, run_profile


def values(tmp_path: Path, **overrides: str) -> dict[str, str]:
    base = {
        "prompt": "hello",
        "task": "",
        "target": str(tmp_path),
        "run_id": "r1",
        "attempt": "1",
    }
    base.update(overrides)
    return base


def test_expansion_is_per_argument_and_never_uses_shell(tmp_path: Path):
    result = run_profile(
        profile={
            "command": [
                sys.executable,
                "-c",
                "import sys; print(sys.argv[1])",
                "{prompt}",
            ],
            "timeout_seconds": 5,
        },
        values=values(tmp_path, prompt="hello; touch owned"),
        cwd=tmp_path,
        max_output_chars=1000,
    )
    assert result.status == "completed"
    assert result.stdout.strip() == "hello; touch owned"
    assert not (tmp_path / "owned").exists()


def test_sleeping_child_times_out_and_is_gone(tmp_path: Path):
    pid_file = tmp_path / "pid"
    script = tmp_path / "sleep.py"
    script.write_text(
        "import os, pathlib, time\n"
        f"pathlib.Path({str(pid_file)!r}).write_text(str(os.getpid()))\n"
        "time.sleep(60)\n",
        encoding="utf-8",
    )
    result = run_profile(
        {"command": [sys.executable, str(script)], "timeout_seconds": 1},
        values(tmp_path),
        tmp_path,
        1000,
    )
    assert result.timed_out and result.status == "timed_out"
    pid = int(pid_file.read_text(encoding="utf-8"))
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_output_is_counted_fully_but_retained_is_bounded(tmp_path: Path):
    result = run_profile(
        {
            "command": [sys.executable, "-c", "import sys; sys.stdout.write('x' * 10000)"],
            "timeout_seconds": 5,
        },
        values(tmp_path),
        tmp_path,
        100,
    )
    assert result.output_chars == 10000
    assert len(result.stdout) <= 100
    assert "omitted" in result.stdout
    assert result.stdout.startswith("x") and result.stdout.endswith("x")


def test_unknown_executable_is_a_structured_start_failure(tmp_path: Path):
    result = run_profile(
        {"command": ["agentic-stack-command-that-does-not-exist"], "timeout_seconds": 5},
        values(tmp_path),
        tmp_path,
        100,
    )
    assert result.status == "failed_to_start"
    assert result.exit_code is None
    assert result.error
    assert not result.timed_out


def test_expand_command_requires_all_values():
    assert expand_command(["agent", "{run_id}"], {"run_id": "r1"}) == ["agent", "r1"]
    with pytest.raises(KeyError):
        expand_command(["agent", "{missing}"], {})

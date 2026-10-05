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


def test_progress_arrives_before_exit_and_decodes_split_utf8(tmp_path):
    gate = tmp_path / 'continue'
    chunks = []
    script = ("import os, time, pathlib\n"
              "os.write(1, b'\\xf0\\x9f')\ntime.sleep(.05)\nos.write(1, b'\\x8c\\xb2')\n"
              f"while not pathlib.Path({str(gate)!r}).exists(): time.sleep(.01)\n"
              "print(' complete')\n")
    def progress(channel, text):
        chunks.append((channel, text))
        if '🌲' in text:
            gate.touch()
    result = run_profile({'command': [sys.executable, '-c', script], 'timeout_seconds': 3},
                         {}, tmp_path, 1000, on_output=progress)
    assert result.status == 'completed'
    assert result.stdout == '🌲 complete\n'
    assert ''.join(text for channel, text in chunks if channel == 'stdout') == result.stdout


def test_failed_progress_observer_still_drains_both_pipes(tmp_path):
    def broken(*args):
        raise ValueError('observer failed')
    result = run_profile({'command': [sys.executable, '-c', "import sys;sys.stdout.write('x'*100000);sys.stderr.write('y'*100000)"],
                          'timeout_seconds': 3}, {}, tmp_path, 1000, on_output=broken)
    assert result.status == 'completed'
    assert result.output_chars == 200000


@pytest.mark.skipif(os.name != 'posix', reason='POSIX owned process groups')
def test_exited_launcher_cannot_leave_a_pipe_holding_descendant(tmp_path: Path):
    import time
    pid_file = tmp_path/'descendant.pid'
    child = tmp_path/'descendant.py'
    child.write_text('import time\ntime.sleep(30)\n')
    launcher = tmp_path/'launcher.py'
    launcher.write_text(
        'import subprocess,sys,pathlib\n'
        f'p=subprocess.Popen([sys.executable,{str(child)!r}])\n'
        f'pathlib.Path({str(pid_file)!r}).write_text(str(p.pid))\n'
    )
    started = time.monotonic()
    result = run_profile({'command': [sys.executable, str(launcher)], 'timeout_seconds': 5}, values(tmp_path), tmp_path, 1000)
    assert result.status == 'completed'
    assert time.monotonic() - started < 3
    # The descendant must have been killed; a briefly unreaped zombie is also
    # terminal, but cannot hold the capture pipe or continue work.
    pid = int(pid_file.read_text())
    import subprocess
    status = subprocess.run(['ps', '-o', 'stat=', '-p', str(pid)], capture_output=True, text=True).stdout.strip()
    assert not status or status.startswith('Z')

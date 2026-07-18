"""Shell-free, bounded execution for configured command-line harnesses."""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

_OMISSION = "\n... <output omitted> ...\n"


@dataclass(frozen=True)
class ProcessResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    output_chars: int
    duration_seconds: float
    timed_out: bool = False
    error: str | None = None


class _BoundedCapture:
    def __init__(self, limit: int) -> None:
        self.limit = limit
        self.head_limit = limit // 2
        self.tail_limit = limit - self.head_limit
        self.head = ""
        self.tail = ""
        self.count = 0

    def add(self, chunk: str) -> None:
        self.count += len(chunk)
        remaining = chunk
        if len(self.head) < self.head_limit:
            take = self.head_limit - len(self.head)
            self.head += remaining[:take]
            remaining = remaining[take:]
        if remaining and self.tail_limit:
            self.tail = (self.tail + remaining)[-self.tail_limit :]

    def render(self) -> str:
        retained = self.head + self.tail
        if self.count <= self.limit:
            return retained
        available = self.limit - len(_OMISSION)
        if available <= 0:
            return _OMISSION[: self.limit]
        head_size = available // 2
        tail_size = available - head_size
        return self.head[:head_size] + _OMISSION + self.tail[-tail_size:]


def expand_command(command: list[str], values: dict[str, str]) -> list[str]:
    """Expand each configured argument independently without a shell."""
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty argument list")
    if not all(isinstance(argument, str) for argument in command):
        raise TypeError("command arguments must be strings")
    return [argument.format_map(values) for argument in command]


def _read_stream(stream: TextIO, capture: _BoundedCapture) -> None:
    try:
        while True:
            chunk = stream.read(8192)
            if not chunk:
                return
            capture.add(chunk)
    finally:
        stream.close()


def _stop_owned_process(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGTERM)
        else:
            process.terminate()
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=0.5)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    process.wait()


def run_profile(
    profile: dict,
    values: dict[str, str],
    cwd: Path,
    max_output_chars: int,
) -> ProcessResult:
    """Run one profile with bounded retained output and full character counts."""
    if isinstance(max_output_chars, bool) or not isinstance(max_output_chars, int) or max_output_chars <= 0:
        raise ValueError("max_output_chars must be a positive integer")
    argv = expand_command(profile["command"], values)
    timeout = profile["timeout_seconds"]
    started = time.monotonic()
    try:
        process = subprocess.Popen(
            argv,
            cwd=Path(cwd),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except FileNotFoundError as exc:
        return ProcessResult(
            status="failed_to_start",
            exit_code=None,
            stdout="",
            stderr="",
            output_chars=0,
            duration_seconds=time.monotonic() - started,
            error=str(exc),
        )

    assert process.stdout is not None
    assert process.stderr is not None
    stdout = _BoundedCapture(max_output_chars)
    stderr = _BoundedCapture(max_output_chars)
    readers = (
        threading.Thread(target=_read_stream, args=(process.stdout, stdout), daemon=True),
        threading.Thread(target=_read_stream, args=(process.stderr, stderr), daemon=True),
    )
    for reader in readers:
        reader.start()

    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_owned_process(process)
    for reader in readers:
        reader.join()

    duration = time.monotonic() - started
    if timed_out:
        status = "timed_out"
    elif process.returncode == 0:
        status = "completed"
    else:
        status = "failed"
    return ProcessResult(
        status=status,
        exit_code=process.returncode,
        stdout=stdout.render(),
        stderr=stderr.render(),
        output_chars=stdout.count + stderr.count,
        duration_seconds=duration,
        timed_out=timed_out,
    )

"""Shell-free, bounded execution for configured command-line harnesses."""

from __future__ import annotations

import codecs
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Callable

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


def _read_stream(stream: BinaryIO, capture: _BoundedCapture, name: str, on_output) -> None:
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    try:
        while True:
            # read1 returns available pipe bytes without waiting for 8 KB or EOF.
            raw = stream.read1(8192)
            chunk = decoder.decode(raw, final=not raw)
            if chunk:
                capture.add(chunk)
                if on_output is not None:
                    try:
                        on_output(name, chunk)
                    except Exception:
                        # Optional progress reporting must not stop draining pipes.
                        on_output = None
            if not raw:
                return
    finally:
        stream.close()


def _stop_owned_process(process: subprocess.Popen[bytes]) -> None:
    if os.name != 'posix' and process.poll() is not None:
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
    cancel_event: threading.Event | None = None,
    *,
    on_output: Callable[[str, str], None] | None = None,
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
        threading.Thread(target=_read_stream, args=(process.stdout, stdout, "stdout", on_output), daemon=True),
        threading.Thread(target=_read_stream, args=(process.stderr, stderr, "stderr", on_output), daemon=True),
    )
    for reader in readers:
        reader.start()

    timed_out = False
    cancelled = False
    try:
        if cancel_event is None:
            process.wait(timeout=timeout)
        else:
            deadline = started + timeout
            while process.poll() is None:
                if cancel_event.wait(0.1):
                    cancelled = True
                    _stop_owned_process(process)
                    break
                if time.monotonic() >= deadline:
                    raise subprocess.TimeoutExpired(argv, timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _stop_owned_process(process)
    except BaseException:
        _stop_owned_process(process)
        raise
    for reader in readers:
        reader.join(timeout=0.2)
    if any(reader.is_alive() for reader in readers):
        # A launcher may exit while a descendant still holds its pipe open.
        _stop_owned_process(process)
        for reader in readers:
            reader.join(timeout=1)

    duration = time.monotonic() - started
    if cancelled:
        status = "cancelled"
    elif timed_out:
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

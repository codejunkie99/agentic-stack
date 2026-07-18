"""Atomic local checkpoints and privacy-safe loop events."""

from __future__ import annotations

import json
import os
import re
import tempfile
from pathlib import Path

RUNTIME_REL = Path(".agent/runtime/loops")
EVENT_FIELDS = {
    "run_id",
    "loop",
    "event",
    "timestamp",
    "duration_seconds",
    "attempt",
    "exit_code",
    "decision",
    "reason",
    "status",
    "changed_paths",
    "counters",
}

_RUN_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
_PAUSE_FILE = "_pause-all.json"


class CheckpointError(RuntimeError):
    """Raised when durable local loop state cannot be read or written."""


def runtime_dir(target_root: Path) -> Path:
    return Path(target_root) / RUNTIME_REL


def _run_id(value: object) -> str:
    if not isinstance(value, str) or not _RUN_ID.fullmatch(value):
        raise CheckpointError("run_id must be a safe portable identifier")
    return value


def checkpoint_path(target_root: Path, run_id: str) -> Path:
    return runtime_dir(target_root) / f"{_run_id(run_id)}.json"


def _json_text(payload: object, context: str) -> str:
    try:
        return json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    except (TypeError, ValueError) as exc:
        raise CheckpointError(f"cannot serialize {context}: {exc}") from exc


def _atomic_text(destination: Path, text: str) -> Path:
    temporary: Path | None = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
        return destination
    except OSError as exc:
        raise CheckpointError(f"cannot atomically write {destination}: {exc}") from exc
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def save_checkpoint(target_root: Path, payload: dict) -> Path:
    if not isinstance(payload, dict):
        raise CheckpointError("checkpoint payload must be an object")
    run_id = _run_id(payload.get("run_id"))
    text = _json_text(payload, "checkpoint")
    return _atomic_text(checkpoint_path(target_root, run_id), text)


def load_checkpoint(target_root: Path, run_id: str) -> dict:
    path = checkpoint_path(target_root, run_id)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CheckpointError(f"checkpoint not found: {run_id}") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"checkpoint is unreadable or corrupt: {path}") from exc
    if not isinstance(payload, dict) or payload.get("run_id") != run_id:
        raise CheckpointError(f"checkpoint is corrupt: {path}")
    return payload


def list_checkpoints(target_root: Path) -> list[dict]:
    root = runtime_dir(target_root)
    if not root.is_dir():
        return []
    checkpoints = []
    for path in sorted(root.glob("*.json")):
        if path.name.startswith("_"):
            continue
        checkpoints.append(load_checkpoint(target_root, path.stem))
    return checkpoints


def append_event(target_root: Path, payload: dict) -> None:
    if not isinstance(payload, dict):
        raise CheckpointError("event payload must be an object")
    event = {key: payload[key] for key in EVENT_FIELDS if key in payload}
    if "run_id" in event:
        _run_id(event["run_id"])
    text = _json_text(event, "event")
    path = runtime_dir(target_root) / "events.jsonl"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise CheckpointError(f"cannot append event audit record: {exc}") from exc


def set_pause_all(target_root: Path, paused: bool) -> None:
    if not isinstance(paused, bool):
        raise CheckpointError("paused must be a boolean")
    _atomic_text(
        runtime_dir(target_root) / _PAUSE_FILE,
        _json_text({"paused": paused}, "pause state"),
    )


def is_paused(target_root: Path) -> bool:
    path = runtime_dir(target_root) / _PAUSE_FILE
    if not path.exists():
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CheckpointError(f"pause state is unreadable or corrupt: {path}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("paused"), bool):
        raise CheckpointError(f"pause state is corrupt: {path}")
    return payload["paused"]

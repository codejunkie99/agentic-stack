"""Deterministic budget, stagnation, and changed-path policy decisions."""

from __future__ import annotations

import fnmatch
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath

_ISO_TIMESTAMP = re.compile(
    r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"
)
_ABSOLUTE_DIRECTORY = re.compile(r"(?<![\w.])(?:[A-Za-z]:)?/(?:[^\s:]+/)+")
_LINE_NUMBER = re.compile(r":\d+(?::\d+)?\b")
_LONG_ID = re.compile(r"\b\d{6,}\b")
_WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Decision:
    stop: bool
    reason: str | None = None
    detail: str | None = None


def normalize_failure(text: str, target_root: Path | None = None) -> str:
    normalized = str(text)
    if target_root is not None:
        root = str(Path(target_root).resolve())
        normalized = normalized.replace(root, "<target>")
    normalized = _ISO_TIMESTAMP.sub("<timestamp>", normalized)
    normalized = _ABSOLUTE_DIRECTORY.sub("<path>/", normalized)
    normalized = _LINE_NUMBER.sub(":<line>", normalized)
    normalized = _LONG_ID.sub("<id>", normalized)
    return _WHITESPACE.sub(" ", normalized).strip()


def estimate_tokens(*texts: str) -> int:
    return math.ceil(sum(len(str(text)) for text in texts) / 4)


def _limit_reached(counters: dict, limits: dict, counter: str, limit: str) -> bool:
    return limit in limits and counters.get(counter, 0) >= limits[limit]


def evaluate_breaker(attempts: list[dict], limits: dict, counters: dict) -> Decision:
    if counters.get("paused", False):
        return Decision(True, "paused", "global or run pause is active")
    checks = (
        ("attempts", "max_attempts", "attempt_budget"),
        ("runtime_seconds", "max_runtime_seconds", "runtime_budget"),
        ("estimated_tokens", "estimated_token_budget", "token_budget"),
        ("output_chars", "max_output_chars", "output_budget"),
    )
    for counter, limit, reason in checks:
        if _limit_reached(counters, limits, counter, limit):
            return Decision(True, reason, f"{counter} reached {limits[limit]}")

    threshold = limits.get("stagnation_threshold")
    if isinstance(threshold, int) and not isinstance(threshold, bool) and threshold > 0:
        recent = attempts[-threshold:]
        if len(recent) == threshold and all(item.get("outcome") == "failed" for item in recent):
            signatures = [normalize_failure(item.get("verifier_output", "")) for item in recent]
            if signatures[0] and len(set(signatures)) == 1:
                return Decision(True, "stagnation", "repeated equivalent verifier failure")
    return Decision(False)


def _unsafe_changed_path(path: object) -> bool:
    if not isinstance(path, str) or not path or "\x00" in path or "\\" in path:
        return True
    posix = PurePosixPath(path)
    windows = PureWindowsPath(path)
    return (
        posix.is_absolute()
        or windows.is_absolute()
        or bool(windows.drive)
        or any(part == ".." for part in posix.parts)
    )


def _matches(path: str, pattern: str) -> bool:
    candidate = PurePosixPath(path)
    return candidate.match(pattern) or fnmatch.fnmatchcase(path, pattern)


def check_changed_paths(paths: list[str], constraints: dict) -> Decision:
    for path in paths:
        if _unsafe_changed_path(path):
            return Decision(True, "path_escape", str(path))
    max_files = constraints.get("max_changed_files", 0)
    if len(paths) > max_files:
        return Decision(True, "changed_file_limit", f"{len(paths)} changed files")
    deny = constraints.get("deny_paths", [])
    allow = constraints.get("allow_paths", [])
    for path in paths:
        if any(_matches(path, pattern) for pattern in deny):
            return Decision(True, "deny_path", path)
        if allow and not any(_matches(path, pattern) for pattern in allow):
            return Decision(True, "outside_allowlist", path)
    return Decision(False)

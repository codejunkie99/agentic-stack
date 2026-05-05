"""Local Trust Console data collectors.

This module is intentionally stdlib-only and file-backed. It normalizes the
existing `.agent/` data layer so plain CLI output, JSON output, and the TUI all
read the same facts.
"""
from __future__ import annotations

import datetime as _dt
import json
import os
from pathlib import Path
from typing import Any


SUPPORTED_HARNESSES = (
    "claude-code",
    "cursor",
    "windsurf",
    "opencode",
    "openclaw",
    "hermes",
    "pi",
    "standalone-python",
    "antigravity",
)

ADAPTER_FILES = {
    "claude-code": ["CLAUDE.md", ".claude/settings.json"],
    "cursor": [".cursor/rules/agentic-stack.mdc"],
    "windsurf": [".windsurfrules"],
    "opencode": ["AGENTS.md", "opencode.json"],
    "openclaw": [".openclaw-system.md"],
    "hermes": ["AGENTS.md"],
    "pi": ["AGENTS.md", ".pi/skills"],
    "standalone-python": ["run.py"],
    "antigravity": ["ANTIGRAVITY.md"],
}

TEAM_FILES = {
    "CONVENTIONS.md": "# Team Conventions\n\n",
    "REVIEW_RULES.md": "# Team Review Rules\n\n",
    "DEPLOYMENT_LESSONS.md": "# Team Deployment Lessons\n\n",
    "INCIDENTS.md": "# Team Incident Learnings\n\n",
    "APPROVED_SKILLS.md": "# Approved Skills\n\n",
}


def _now() -> str:
    return _dt.datetime.now().isoformat()


def _as_path(value: str | os.PathLike[str] | None) -> Path:
    return Path(value or os.getcwd()).expanduser().resolve()


def _read_text(path: Path) -> str:
    try:
        return path.read_text()
    except OSError:
        return ""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return rows, errors
    for line_no, line in enumerate(lines, 1):
        raw = line.strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append({"path": str(path), "line": line_no, "error": str(exc)})
            continue
        if isinstance(payload, dict):
            rows.append(payload)
        else:
            errors.append({"path": str(path), "line": line_no, "error": "JSONL row is not an object"})
    return rows, errors


def find_agent_root(start: str | os.PathLike[str] | None = None) -> Path | None:
    """Return the nearest `.agent` directory at or above start."""
    cur = _as_path(start)
    if cur.name == ".agent" and cur.is_dir():
        return cur
    if (cur / ".agent").is_dir():
        return cur / ".agent"
    for parent in cur.parents:
        candidate = parent / ".agent"
        if candidate.is_dir():
            return candidate
    return None


def _project_root(project_root: str | os.PathLike[str] | None = None) -> Path:
    start = _as_path(project_root)
    agent = find_agent_root(start)
    if agent:
        return agent.parent
    return start


def _agent_root(project_root: str | os.PathLike[str] | None = None) -> Path:
    root = _project_root(project_root)
    return root / ".agent"


def _status(status: str, label: str, detail: str = "", severity: str = "info") -> dict[str, str]:
    return {"status": status, "label": label, "detail": detail, "severity": severity}


def _file_check(path: Path, label: str, required: bool = True) -> dict[str, str]:
    if path.exists():
        return _status("pass", label, str(path), "info")
    if required:
        return _status("fail", label, f"missing: {path}", "error")
    return _status("warn", label, f"missing: {path}", "warning")


def _count_json_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for item in path.iterdir() if item.is_file() and item.suffix == ".json")


def _load_candidates(agent: Path) -> tuple[dict[str, int], list[dict[str, Any]], list[dict[str, str]]]:
    candidates_dir = agent / "memory" / "candidates"
    counts = {
        "staged": _count_json_files(candidates_dir),
        "graduated": _count_json_files(candidates_dir / "graduated"),
        "rejected": _count_json_files(candidates_dir / "rejected"),
    }
    rejected: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for path in sorted((candidates_dir / "rejected").glob("*.json")):
        payload = _read_json(path)
        if isinstance(payload, dict):
            payload.setdefault("_path", str(path))
            rejected.append(payload)
        else:
            errors.append({"path": str(path), "error": "invalid JSON"})
    return counts, rejected, errors


def _load_lessons(agent: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    path = agent / "memory" / "semantic" / "lessons.jsonl"
    return _load_jsonl(path)


def _load_skills(agent: Path) -> tuple[list[str], list[dict[str, Any]]]:
    path = agent / "skills" / "_manifest.jsonl"
    rows, errors = _load_jsonl(path)
    names = [str(row.get("name", "?")) for row in rows if isinstance(row, dict)]
    return names, errors


def _review_queue(agent: Path) -> dict[str, Any]:
    path = agent / "memory" / "working" / "REVIEW_QUEUE.md"
    text = _read_text(path)
    pending = 0
    oldest = ""
    for line in text.splitlines():
        if line.startswith("**Pending:**"):
            try:
                pending = int(line.split(":", 1)[1].strip())
            except ValueError:
                pending = 0
        if line.startswith("**Oldest staged:**"):
            oldest = line.split(":", 1)[1].strip()
    return {"path": str(path), "exists": path.exists(), "pending": pending, "oldest_staged": oldest}


def _adapter_text(project: Path, harness: str) -> str:
    parts = []
    for rel in ADAPTER_FILES.get(harness, []):
        path = project / rel
        if path.is_file():
            parts.append(_read_text(path))
        elif path.is_dir():
            parts.append(str(path))
    return "\n".join(parts).lower()


def _adapter_installed(project: Path, harness: str) -> dict[str, str]:
    files = ADAPTER_FILES.get(harness, [])
    if not files:
        return _status("fail", "installed", "unknown harness", "error")
    missing = [rel for rel in files if not (project / rel).exists()]
    if not missing:
        return _status("pass", "installed", ", ".join(files), "info")
    return _status("fail", "installed", "missing: " + ", ".join(missing), "error")


def _contains(text: str, *needles: str) -> bool:
    return all(needle.lower() in text for needle in needles)


def _harness_row(project: Path, harness: str) -> dict[str, Any]:
    text = _adapter_text(project, harness)
    installed = _adapter_installed(project, harness)
    if installed["status"] == "fail":
        missing = _status("fail", "", "adapter file missing", "error")
        return {
            "harness": harness,
            "installed": installed,
            "memory": missing,
            "skills": missing,
            "recall": missing,
            "reflect": missing,
            "permissions": missing,
        }
    memory_ok = _contains(text, ".agent", "preferences.md", "lessons.md")
    skills_ok = "skill" in text
    recall_ok = "recall.py" in text
    reflect_ok = "memory_reflect.py" in text or "episodic" in text
    permissions_ok = "permissions.md" in text
    return {
        "harness": harness,
        "installed": installed,
        "memory": _status("pass" if memory_ok else "warn", "memory", "references personal and semantic memory" if memory_ok else "missing memory references", "warning" if not memory_ok else "info"),
        "skills": _status("pass" if skills_ok else "warn", "skills", "references skills" if skills_ok else "missing skill-loading reference", "warning" if not skills_ok else "info"),
        "recall": _status("pass" if recall_ok else "warn", "recall", "references recall.py" if recall_ok else "missing recall.py instruction", "warning" if not recall_ok else "info"),
        "reflect": _status("pass" if reflect_ok else "warn", "reflect", "references reflection logging" if reflect_ok else "missing memory_reflect.py instruction", "warning" if not reflect_ok else "info"),
        "permissions": _status("pass" if permissions_ok else "warn", "permissions", "references permissions.md" if permissions_ok else "missing permissions.md reference", "warning" if not permissions_ok else "info"),
    }


def verify_harnesses(
    harness: str | None = None,
    project_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    project = _project_root(project_root)
    harnesses = [harness] if harness else list(SUPPORTED_HARNESSES)
    rows = [_harness_row(project, item) for item in harnesses if item in SUPPORTED_HARNESSES]
    return {"project_root": str(project), "harnesses": rows}


def team_status(project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    agent = _agent_root(project_root)
    team_dir = agent / "memory" / "team"
    files: dict[str, dict[str, Any]] = {}
    for name in TEAM_FILES:
        path = team_dir / name
        files[name] = {
            "exists": path.exists(),
            "path": str(path),
            "size": path.stat().st_size if path.exists() else 0,
        }
    return {"exists": team_dir.is_dir(), "path": str(team_dir), "files": files}


def team_init(project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    agent = _agent_root(project_root)
    team_dir = agent / "memory" / "team"
    team_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    existing = 0
    for name, content in TEAM_FILES.items():
        path = team_dir / name
        if path.exists():
            existing += 1
            continue
        path.write_text(content)
        created += 1
    return {"path": str(team_dir), "created": created, "existing": existing, "files": list(TEAM_FILES)}


def collect_health(project_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    project = _project_root(project_root)
    agent = project / ".agent"
    checks = [
        _file_check(agent, ".agent directory"),
        _file_check(agent / "AGENTS.md", "agent map"),
        _file_check(agent / "memory" / "personal" / "PREFERENCES.md", "personal preferences"),
        _file_check(agent / "memory" / "working" / "WORKSPACE.md", "working memory", required=False),
        _file_check(agent / "memory" / "working" / "REVIEW_QUEUE.md", "review queue", required=False),
        _file_check(agent / "memory" / "semantic" / "lessons.jsonl", "semantic lessons", required=False),
        _file_check(agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl", "episodic log", required=False),
        _file_check(agent / "protocols" / "permissions.md", "permissions"),
        _file_check(agent / "skills" / "_manifest.jsonl", "skills manifest"),
    ]

    episodes, episode_errors = _load_jsonl(agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl")
    lessons, lesson_errors = _load_lessons(agent)
    candidate_counts, rejected, candidate_errors = _load_candidates(agent)
    skill_names, skill_errors = _load_skills(agent)
    accepted = [row for row in lessons if row.get("status") == "accepted"]
    provisional = [row for row in lessons if row.get("status") == "provisional"]
    failures = [row for row in episodes if row.get("result") == "failure"]
    json_errors = episode_errors + lesson_errors + candidate_errors + skill_errors
    for err in json_errors:
        checks.append(_status("warn", "data parse", f"{err.get('path')}: {err.get('error')}", "warning"))
    review = _review_queue(agent)
    if review["pending"] > 10:
        checks.append(_status("warn", "review backlog", f"{review['pending']} pending candidates", "warning"))
    team = team_status(project)
    if not team["exists"]:
        checks.append(_status("warn", "team brain", "not initialized; run agentic-stack team init", "warning"))

    failed = sum(1 for item in checks if item["status"] == "fail")
    warned = sum(1 for item in checks if item["status"] == "warn")
    score = max(0, 100 - failed * 18 - warned * 6)

    registry = _read_json(agent / "runtime" / "instances.json")
    instances = registry if isinstance(registry, dict) else {"version": 1, "active_instance": None, "instances": []}
    return {
        "generated_at": _now(),
        "project_root": str(project),
        "agent_root": str(agent),
        "score": score,
        "checks": checks,
        "memory": {
            "episodic": {
                "count": len(episodes),
                "failures": len(failures),
                "errors": episode_errors,
            },
            "lessons": {
                "accepted": len(accepted),
                "provisional": len(provisional),
                "total": len(lessons),
                "errors": lesson_errors,
            },
            "candidates": dict(candidate_counts, errors=candidate_errors),
            "review_queue": review,
        },
        "skills": {"count": len(skill_names), "names": skill_names, "errors": skill_errors},
        "team": team,
        "instances": {
            "active_instance": instances.get("active_instance"),
            "count": len(instances.get("instances", [])),
            "items": instances.get("instances", []),
        },
    }


def memory_learned(project_root: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    lessons, _errors = _load_lessons(_agent_root(project_root))
    return [row for row in lessons if row.get("status") == "accepted"]


def memory_rejected(project_root: str | os.PathLike[str] | None = None) -> list[dict[str, Any]]:
    _counts, rejected, _errors = _load_candidates(_agent_root(project_root))
    return rejected


def memory_why(
    identifier: str,
    project_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    agent = _agent_root(project_root)
    lessons, errors = _load_lessons(agent)
    target = None
    for lesson in lessons:
        aliases = {
            str(lesson.get("id", "")),
            str(lesson.get("source_candidate", "")),
            str(lesson.get("claim", "")),
        }
        if identifier in aliases:
            target = lesson
            break
    if target is None:
        for path in (agent / "memory" / "candidates").glob("**/*.json"):
            payload = _read_json(path)
            if isinstance(payload, dict) and identifier in {str(payload.get("id", "")), path.stem}:
                target = payload
                break
    if target is None:
        return {"found": False, "identifier": identifier, "lesson": None, "evidence": [], "errors": errors}
    evidence_ids = {str(item) for item in target.get("evidence_ids", [])}
    episodes, episode_errors = _load_jsonl(agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl")
    evidence = [
        row for row in episodes
        if str(row.get("id", "")) in evidence_ids or str(row.get("timestamp", "")) in evidence_ids
    ]
    return {
        "found": True,
        "identifier": identifier,
        "lesson": target,
        "evidence": evidence,
        "errors": errors + episode_errors,
    }

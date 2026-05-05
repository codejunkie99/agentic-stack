"""Interactive agentic-stack dashboard.

This is the human front door for an already-installed project. It keeps the
existing verb-style commands available for scripts, but gives terminal users a
single place to inspect health, adapters, harness verification, memory, team
brain, skills, instances, transfer, and local dashboard exports.
"""
from __future__ import annotations

import os
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import doctor as doctor_mod
from . import schema as schema_mod
from . import state as state_mod
from . import status as status_mod


SECTIONS = (
    "Overview",
    "Adapters",
    "Doctor",
    "Verify",
    "Memory",
    "Team Brain",
    "Skills",
    "Instances",
    "Transfer",
    "Data",
)

TEAM_FILES = {
    "CONVENTIONS.md": "# Team Conventions\n\n",
    "REVIEW_RULES.md": "# Team Review Rules\n\n",
    "DEPLOYMENT_LESSONS.md": "# Team Deployment Lessons\n\n",
    "INCIDENTS.md": "# Team Incident Learnings\n\n",
    "APPROVED_SKILLS.md": "# Approved Skills\n\n",
}


def _logical_path(path: Path | str) -> Path:
    return Path(os.path.abspath(str(path)))


def _count_lines(path: Path) -> int:
    if not path.is_file():
        return 0
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _count_candidate_files(path: Path) -> int:
    if not path.is_dir():
        return 0
    try:
        return sum(1 for p in path.glob("*.json") if p.is_file())
    except OSError:
        return 0


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
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
            errors.append({"path": str(path), "line": line_no, "error": "row is not an object"})
    return rows, errors


def _candidate_counts(path: Path) -> dict[str, int]:
    staged = _count_candidate_files(path)
    graduated = _count_candidate_files(path / "graduated")
    rejected = _count_candidate_files(path / "rejected")
    return {
        "staged": staged,
        "graduated": graduated,
        "rejected": rejected,
        "total": staged + graduated + rejected,
    }


def _load_json_objects(path: Path) -> list[dict[str, Any]]:
    if not path.is_dir():
        return []
    rows: list[dict[str, Any]] = []
    for item in sorted(path.glob("*.json")):
        payload = _read_json(item)
        if isinstance(payload, dict):
            payload.setdefault("_path", str(item))
            rows.append(payload)
    return rows


def _status_from_adapter(status: str) -> str:
    return {"green": "pass", "yellow": "warn", "red": "fail"}.get(status, "warn")


def _status_word(status: str) -> str:
    return {"pass": "ok", "warn": "warn", "fail": "fail"}.get(status, status)


def _check(status: str, label: str, detail: str) -> dict[str, str]:
    return {"status": status, "label": label, "detail": detail}


def _available_adapters(stack_root: Path) -> list[str]:
    try:
        return sorted(name for name, _ in schema_mod.discover_all(stack_root) if name != "_shared")
    except OSError:
        return []


def _adapter_file_map(stack_root: Path) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for name, manifest in schema_mod.discover_all(stack_root):
        files: list[str] = []
        for item in manifest.get("files") or []:
            if isinstance(item, dict) and isinstance(item.get("dst"), str):
                files.append(item["dst"])
        skills_link = manifest.get("skills_link")
        if isinstance(skills_link, dict) and isinstance(skills_link.get("dst"), str):
            files.append(skills_link["dst"])
        if files:
            out[name] = files
    return out


def _adapter_text(project: Path, files: list[str]) -> str:
    parts: list[str] = []
    for rel in files:
        path = project / rel
        if path.is_file():
            parts.append(_read_text(path))
        elif path.is_dir():
            parts.append(str(path))
    return "\n".join(parts).lower()


def _contains(text: str, *needles: str) -> bool:
    return all(needle.lower() in text for needle in needles)


def _verify_status(status: str, detail: str = "") -> dict[str, str]:
    return {"status": status, "detail": detail}


def _verify_rows(target_root: Path, stack_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for name, files in sorted(_adapter_file_map(stack_root).items()):
        missing = [rel for rel in files if not (target_root / rel).exists()]
        if missing:
            installed = _verify_status("fail", "missing: " + ", ".join(missing))
            missing_cell = _verify_status("fail", "adapter file missing")
            rows.append(
                {
                    "harness": name,
                    "installed": installed,
                    "memory": missing_cell,
                    "skills": missing_cell,
                    "recall": missing_cell,
                    "reflect": missing_cell,
                    "permissions": missing_cell,
                }
            )
            continue
        text = _adapter_text(target_root, files)
        rows.append(
            {
                "harness": name,
                "installed": _verify_status("pass", ", ".join(files)),
                "memory": _verify_status(
                    "pass" if _contains(text, ".agent", "preferences.md", "lessons.md") else "warn",
                    "memory references present",
                ),
                "skills": _verify_status("pass" if "skill" in text else "warn", "skills reference present"),
                "recall": _verify_status("pass" if "recall.py" in text else "warn", "recall reference present"),
                "reflect": _verify_status(
                    "pass" if "memory_reflect.py" in text or "episodic" in text else "warn",
                    "reflection reference present",
                ),
                "permissions": _verify_status(
                    "pass" if "permissions.md" in text else "warn",
                    "permissions reference present",
                ),
            }
        )
    return rows


def _adapter_rows(target_root: Path, doc: dict[str, Any] | None) -> list[dict[str, str]]:
    if not doc:
        return []
    rows: list[dict[str, str]] = []
    for name in sorted((doc.get("adapters") or {}).keys()):
        entry = doc["adapters"][name]
        status, details = doctor_mod._audit_adapter(target_root, name, entry)
        rows.append(
            {
                "name": name,
                "status": _status_from_adapter(status),
                "detail": details[0] if details else "installed",
            }
        )
    return rows


def _load_skill_names(agent: Path) -> tuple[list[str], list[dict[str, Any]]]:
    rows, errors = _load_jsonl(agent / "skills" / "_manifest.jsonl")
    names = [str(row.get("name")) for row in rows if isinstance(row.get("name"), str)]
    if names:
        return names, errors
    skills_dir = agent / "skills"
    if skills_dir.is_dir():
        names = sorted(p.name for p in skills_dir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    return names, errors


def _team_status(agent: Path) -> dict[str, Any]:
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


def team_init(target_root: Path | str) -> dict[str, Any]:
    target = _logical_path(target_root)
    team_dir = target / ".agent" / "memory" / "team"
    team_dir.mkdir(parents=True, exist_ok=True)
    created = 0
    existing = 0
    for name, content in TEAM_FILES.items():
        path = team_dir / name
        if path.exists():
            existing += 1
            continue
        path.write_text(content, encoding="utf-8")
        created += 1
    return {"path": str(team_dir), "created": created, "existing": existing, "files": list(TEAM_FILES)}


def _instances_status(agent: Path) -> dict[str, Any]:
    payload = _read_json(agent / "runtime" / "instances.json")
    if not isinstance(payload, dict):
        return {"active_instance": None, "count": 0, "items": []}
    items = payload.get("instances")
    if not isinstance(items, list):
        items = payload.get("items")
    if not isinstance(items, list):
        items = []
    return {
        "active_instance": payload.get("active_instance"),
        "count": len(items),
        "items": [item for item in items if isinstance(item, dict)],
    }


def memory_why(identifier: str, target_root: Path | str) -> dict[str, Any]:
    target = _logical_path(target_root)
    agent = target / ".agent"
    lessons, lesson_errors = _load_jsonl(agent / "memory" / "semantic" / "lessons.jsonl")
    found: dict[str, Any] | None = None
    for lesson in lessons:
        aliases = {
            str(lesson.get("id", "")),
            str(lesson.get("source_candidate", "")),
            str(lesson.get("claim", "")),
        }
        if identifier in aliases:
            found = lesson
            break
    if found is None:
        for path in sorted((agent / "memory" / "candidates").glob("**/*.json")):
            payload = _read_json(path)
            if isinstance(payload, dict) and identifier in {str(payload.get("id", "")), path.stem}:
                found = payload
                break
    if found is None:
        return {"found": False, "identifier": identifier, "lesson": None, "evidence": [], "errors": lesson_errors}

    evidence_ids = {str(item) for item in found.get("evidence_ids", [])}
    episodes, episode_errors = _load_jsonl(agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl")
    evidence = [
        row for row in episodes
        if str(row.get("id", "")) in evidence_ids or str(row.get("timestamp", "")) in evidence_ids
    ]
    return {
        "found": True,
        "identifier": identifier,
        "lesson": found,
        "evidence": evidence,
        "errors": lesson_errors + episode_errors,
    }


def collect_dashboard(
    target_root: Path | str,
    stack_root: Path | str,
) -> dict[str, Any]:
    target = _logical_path(target_root)
    stack = Path(stack_root)
    agent = target / ".agent"
    doc = state_mod.load(target)
    installed = sorted((doc.get("adapters") or {}).keys()) if doc else []
    available = _available_adapters(stack)
    missing = sorted(name for name in available if name not in installed)
    lessons, lesson_errors = _load_jsonl(agent / "memory" / "semantic" / "lessons.jsonl")
    accepted_lessons = [row for row in lessons if row.get("status") == "accepted"]
    provisional_lessons = [row for row in lessons if row.get("status") == "provisional"]
    episodes, episode_errors = _load_jsonl(agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl")
    failed_episodes = [row for row in episodes if row.get("result") == "failure"]
    candidate_counts = _candidate_counts(agent / "memory" / "candidates")
    rejected_candidates = _load_json_objects(agent / "memory" / "candidates" / "rejected")
    skill_names, skill_errors = _load_skill_names(agent)
    team = _team_status(agent)
    instances = _instances_status(agent)

    checks = [
        _check("pass" if agent.is_dir() else "fail", ".agent directory", "present" if agent.is_dir() else "missing"),
        _check(
            "pass" if (agent / "AGENTS.md").is_file() else "fail",
            "agent map",
            ".agent/AGENTS.md present" if (agent / "AGENTS.md").is_file() else ".agent/AGENTS.md missing",
        ),
        _check(
            "pass" if (agent / "memory" / "personal" / "PREFERENCES.md").is_file() else "warn",
            "personal preferences",
            "configured" if (agent / "memory" / "personal" / "PREFERENCES.md").is_file() else "not configured",
        ),
        _check(
            "pass" if doc is not None else "warn",
            "install tracking",
            ".agent/install.json present" if doc is not None else "install.json missing",
        ),
        _check(
            "pass" if (agent / "memory" / "working" / "REVIEW_QUEUE.md").is_file() else "warn",
            "review queue",
            "present" if (agent / "memory" / "working" / "REVIEW_QUEUE.md").is_file() else "missing",
        ),
        _check(
            "pass" if team["exists"] else "warn",
            "team brain",
            "initialized" if team["exists"] else "not initialized",
        ),
    ]
    for err in lesson_errors + episode_errors + skill_errors:
        checks.append(_check("warn", "data parse", f"{err.get('path')}: {err.get('error')}"))
    adapters = _adapter_rows(target, doc)
    verify = _verify_rows(target, stack)
    warnings = sum(1 for row in checks + adapters if row["status"] == "warn")
    failed_checks = sum(1 for row in checks + adapters if row["status"] == "fail")
    score = max(0, min(100, 100 - failed_checks * 18 - warnings * 7))

    data_dir = agent / "data-layer"
    dashboard_html = data_dir / "dashboard.html"
    return {
        "project": str(target),
        "version": (doc or {}).get("agentic_stack_version", __version__),
        "installed_at": (doc or {}).get("installed_at", "?"),
        "score": score,
        "warnings": warnings,
        "failures": failed_checks,
        "checks": checks,
        "adapters": adapters,
        "verify": verify,
        "installed": installed,
        "available": missing,
        "brain_summary": status_mod._brain_summary(target),
        "memory": {
            "episodes": len(episodes),
            "failures": len(failed_episodes),
            "lessons": len(lessons),
            "accepted": len(accepted_lessons),
            "provisional": len(provisional_lessons),
            "accepted_items": accepted_lessons,
            "rejected_items": rejected_candidates,
            "candidates": candidate_counts["total"],
            "candidate_counts": candidate_counts,
        },
        "team": team,
        "skills": {"count": len(skill_names), "names": skill_names},
        "instances": instances,
        "transfer": {
            "ready": agent.is_dir(),
            "detail": "ready" if agent.is_dir() else ".agent/ missing",
        },
        "data": {
            "dashboard": str(dashboard_html),
            "exists": dashboard_html.is_file(),
        },
    }


def _clip(text: object, width: int) -> str:
    value = str(text)
    if width <= 0:
        return ""
    if len(value) <= width:
        return value
    if width == 1:
        return value[:1]
    return value[: width - 1] + "~"


def _rule(width: int) -> str:
    return "-" * max(24, min(width, 78))


def _plural(count: int, noun: str) -> str:
    suffix = "" if count == 1 else "s"
    return f"{count} {noun}{suffix}"


def _nav_lines(model: dict[str, Any], selected: str = "Overview") -> list[str]:
    adapter_count = len(model["installed"])
    memory = model["memory"]
    team_detail = "ready" if model["team"]["exists"] else "missing"
    instance_detail = f"{model['instances']['count']} total"
    nav = [
        ("Overview", f"{model['score']}%  {_plural(model['warnings'], 'warning')}"),
        ("Adapters", f"{adapter_count} installed"),
        ("Doctor", f"{len(model['checks'])} checks"),
        ("Verify", f"{len(model['verify'])} harnesses"),
        ("Memory", f"{_plural(memory['lessons'], 'lesson')}, {_plural(memory['candidates'], 'candidate')}"),
        ("Team Brain", team_detail),
        ("Skills", _plural(model["skills"]["count"], "skill")),
        ("Instances", instance_detail),
        ("Transfer", model["transfer"]["detail"]),
        ("Data", "ready" if model["data"]["exists"] else "not exported"),
    ]
    return [f"  {'>' if name == selected else ' '} {name:<12} {detail}" for name, detail in nav]


def _overview_lines(model: dict[str, Any]) -> list[str]:
    lines = [
        "Overview",
        "",
        "  Brain",
    ]
    for check in model["checks"][:6]:
        lines.append(f"  {_status_word(check['status']):<4} {check['label']:<22} {check['detail']}")
    lines.extend(["", "  Adapters"])
    if model["adapters"]:
        for row in model["adapters"][:5]:
            lines.append(f"  {_status_word(row['status']):<4} {row['name']:<22} {row['detail']}")
    else:
        lines.append("  warn no adapters installed")
    if model["available"]:
        lines.append(f"  info {len(model['available'])} adapters available to add")
    memory = model["memory"]
    lines.extend(
        [
            "",
            "  Memory",
            f"  info {_plural(memory['episodes'], 'episode')}, {_plural(memory['lessons'], 'lesson')}, {_plural(memory['candidates'], 'candidate')}",
            "",
            "Actions",
            "  > Open adapter manager",
            "    Inspect verify matrix",
            "    Inspect team brain",
            "    Run doctor audit",
            "    Open transfer wizard",
        ]
    )
    return lines


def _adapter_lines(model: dict[str, Any]) -> list[str]:
    lines = ["Adapters", "", "Installed"]
    if model["adapters"]:
        for row in model["adapters"]:
            lines.append(f"  {_status_word(row['status']):<4} {row['name']:<22} {row['detail']}")
    else:
        lines.append("  warn none installed")
    lines.extend(["", "Available"])
    if model["available"]:
        for name in model["available"][:12]:
            lines.append(f"  add  {name}")
    else:
        lines.append("  ok   all available adapters installed")
    lines.extend(["", "Enter opens the adapter manager."])
    return lines


def _doctor_lines(model: dict[str, Any]) -> list[str]:
    lines = ["Doctor", ""]
    for check in model["checks"]:
        lines.append(f"  {_status_word(check['status']):<4} {check['label']:<22} {check['detail']}")
    if model["adapters"]:
        lines.extend(["", "Adapter wiring"])
        for row in model["adapters"]:
            lines.append(f"  {_status_word(row['status']):<4} {row['name']:<22} {row['detail']}")
    return lines


def _cell(status: str) -> str:
    return {"pass": "ok", "warn": "warn", "fail": "fail"}.get(status, status)


def _verify_lines(model: dict[str, Any]) -> list[str]:
    lines = [
        "Verify",
        "",
        "  harness              install memory skills recall reflect permissions",
    ]
    for row in model["verify"]:
        lines.append(
            "  "
            f"{row['harness']:<20}"
            f"{_cell(row['installed']['status']):<8}"
            f"{_cell(row['memory']['status']):<7}"
            f"{_cell(row['skills']['status']):<7}"
            f"{_cell(row['recall']['status']):<7}"
            f"{_cell(row['reflect']['status']):<8}"
            f"{_cell(row['permissions']['status'])}"
        )
    return lines


def _memory_lines(model: dict[str, Any]) -> list[str]:
    memory = model["memory"]
    counts = memory["candidate_counts"]
    lines = [
        "Memory",
        "",
        f"  episodes:   {memory['episodes']}",
        f"  failures:   {memory['failures']}",
        f"  lessons:    {memory['lessons']} ({memory['accepted']} accepted, {memory['provisional']} provisional)",
        f"  candidates: {memory['candidates']} ({counts['staged']} staged, {counts['graduated']} graduated, {counts['rejected']} rejected)",
        "",
        "Accepted",
    ]
    accepted = memory["accepted_items"][:6]
    if accepted:
        for lesson in accepted:
            lines.append(f"  {lesson.get('id', '?')}: {lesson.get('claim', '')}")
    else:
        lines.append("  none")
    lines.append("")
    lines.append("Rejected")
    rejected = memory["rejected_items"][:6]
    if rejected:
        for item in rejected:
            lines.append(f"  {item.get('id', '?')}: {item.get('claim', '')}")
    else:
        lines.append("  none")
    lines.extend(["", "Use memory_why(<id>) to inspect supporting evidence."])
    return lines


def _team_lines(model: dict[str, Any]) -> list[str]:
    team = model["team"]
    lines = [
        "Team Brain",
        "",
        f"  path: {team['path']}",
        f"  status: {'initialized' if team['exists'] else 'missing'}",
        "",
        "Files",
    ]
    for name, meta in team["files"].items():
        lines.append(f"  {_status_word('pass' if meta['exists'] else 'warn'):<4} {name:<24} {'present' if meta['exists'] else 'missing'}")
    lines.extend(["", "Enter initializes missing team brain files."])
    return lines


def _skills_lines(model: dict[str, Any]) -> list[str]:
    lines = ["Skills", "", f"  loaded: {model['skills']['count']}", ""]
    names = model["skills"]["names"]
    if names:
        for name in names[:16]:
            lines.append(f"  - {name}")
    else:
        lines.append("  none")
    return lines


def _instances_lines(model: dict[str, Any]) -> list[str]:
    inst = model["instances"]
    lines = [
        "Instances",
        "",
        f"  active: {inst.get('active_instance') or 'none'}",
        f"  count:  {inst.get('count', 0)}",
        "",
    ]
    items = inst.get("items", [])
    if items:
        for item in items[:12]:
            lines.append(
                f"  {item.get('id', '?'):<18} state={item.get('state', '?')} pid={item.get('worker_pid') or '-'}"
            )
    else:
        lines.append("  no managed instances")
    return lines


def _transfer_lines(model: dict[str, Any]) -> list[str]:
    return [
        "Transfer",
        "",
        f"  status: {model['transfer']['detail']}",
        "",
        "Enter opens the transfer wizard.",
        "Script shortcut: ./install.sh transfer",
    ]


def _data_lines(model: dict[str, Any]) -> list[str]:
    state = "present" if model["data"]["exists"] else "not generated"
    return [
        "Data",
        "",
        f"  dashboard.html: {state}",
        f"  path: {model['data']['dashboard']}",
        "",
        "Generate local dashboard exports from the data-layer skill.",
    ]


def _section_lines(section: str, model: dict[str, Any]) -> list[str]:
    if section == "Adapters":
        return _adapter_lines(model)
    if section == "Doctor":
        return _doctor_lines(model)
    if section == "Verify":
        return _verify_lines(model)
    if section == "Memory":
        return _memory_lines(model)
    if section == "Team Brain":
        return _team_lines(model)
    if section == "Skills":
        return _skills_lines(model)
    if section == "Instances":
        return _instances_lines(model)
    if section == "Transfer":
        return _transfer_lines(model)
    if section == "Data":
        return _data_lines(model)
    return _overview_lines(model)


def render_plain(
    target_root: Path | str,
    stack_root: Path | str,
    width: int = 78,
    section: str = "Overview",
) -> str:
    model = collect_dashboard(target_root, stack_root)
    width = max(48, width)
    selected = section if section in SECTIONS else "Overview"
    header = f"agentic-stack dashboard".ljust(max(1, width - 11)) + f"health {model['score']}%"
    version = f"agentic-stack v{model['version']}"
    lines = [
        _clip(header, width),
        _clip(f"{model['project']}  {version}", width),
        _rule(width),
        "",
        *_nav_lines(model, selected),
        "",
        _rule(width),
        "",
        *[_clip(line, width) for line in _section_lines(selected, model)],
        "",
        _rule(width),
        "up/down move   enter open   r refresh   q quit",
    ]
    return "\n".join(lines) + "\n"


def _addstr(stdscr: Any, y: int, x: int, text: str, attr: int = 0) -> None:
    try:
        stdscr.addstr(y, x, text, attr)
    except Exception:
        pass


def _draw(stdscr: Any, section_idx: int, target_root: Path, stack_root: Path, curses_mod: Any) -> None:
    model = collect_dashboard(target_root, stack_root)
    height, width = stdscr.getmaxyx()
    section = SECTIONS[section_idx]
    stdscr.erase()
    _addstr(stdscr, 0, 0, _clip(f"agentic-stack dashboard  health {model['score']}%", width - 1), curses_mod.A_BOLD)
    _addstr(stdscr, 1, 0, _clip(f"{model['project']}  agentic-stack v{model['version']}", width - 1))
    _addstr(stdscr, 2, 0, "-" * max(0, width - 1))

    rail_w = min(20, max(14, width // 4))
    for idx, name in enumerate(SECTIONS):
        marker = ">" if idx == section_idx else " "
        detail = ""
        if name == "Overview":
            detail = f"{model['score']}%"
        elif name == "Adapters":
            detail = str(len(model["installed"]))
        elif name == "Verify":
            detail = str(len(model["verify"]))
        elif name == "Memory":
            detail = str(model["memory"]["lessons"])
        elif name == "Team Brain":
            detail = "ok" if model["team"]["exists"] else "!"
        elif name == "Skills":
            detail = str(model["skills"]["count"])
        elif name == "Instances":
            detail = str(model["instances"]["count"])
        _addstr(stdscr, 4 + idx, 1, _clip(f"{marker} {name:<10} {detail}", rail_w - 2))

    content_x = rail_w + 1
    content_w = max(10, width - content_x - 1)
    y = 4
    for line in _section_lines(section, model):
        if y >= height - 2:
            break
        attr = curses_mod.A_BOLD if line in SECTIONS or line in {"Actions", "Installed", "Available"} else 0
        _addstr(stdscr, y, content_x, _clip(line, content_w), attr)
        y += 1

    footer = "up/down move  enter open  r refresh  q quit"
    _addstr(stdscr, height - 1, 0, _clip(footer, width - 1))
    stdscr.refresh()


def _pause() -> None:
    try:
        input("\nPress Enter to return to the dashboard...")
    except EOFError:
        pass


def _show_memory_why(target_root: Path) -> None:
    try:
        identifier = input("Lesson/candidate id to explain (blank to cancel): ").strip()
    except EOFError:
        return
    if not identifier:
        return
    payload = memory_why(identifier, target_root)
    if not payload["found"]:
        print(f"not found: {identifier}")
        _pause()
        return
    lesson = payload["lesson"] or {}
    print()
    print(f"id: {lesson.get('id', identifier)}")
    print(f"claim: {lesson.get('claim', '')}")
    print(f"status: {lesson.get('status', '?')}")
    print(f"evidence: {len(payload['evidence'])}")
    for row in payload["evidence"][:5]:
        print(f"- {row.get('id') or row.get('timestamp') or '?'} {row.get('action') or row.get('event') or ''}")
    _pause()


def _open_section(section: str, target_root: Path, stack_root: Path) -> None:
    if section in ("Overview", "Adapters"):
        from . import manage_tui

        manage_tui.run(target_root=target_root, stack_root=stack_root)
        _pause()
    elif section == "Doctor":
        doctor_mod.audit(target_root)
        _pause()
    elif section == "Memory":
        _show_memory_why(target_root)
    elif section == "Team Brain":
        result = team_init(target_root)
        print(f"team brain initialized: created={result['created']} existing={result['existing']}")
        print(result["path"])
        _pause()
    elif section == "Transfer":
        from . import transfer_tui

        transfer_tui.run([], target_root=target_root, stack_root=stack_root)
        _pause()


def _run_interactive(stdscr: Any, target: Path, stack: Path, curses_mod: Any) -> None:
    try:
        curses_mod.curs_set(0)
    except Exception:
        pass
    stdscr.keypad(True)
    section_idx = 0
    while True:
        _draw(stdscr, section_idx, target, stack, curses_mod)
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return
        if key in (ord("j"), curses_mod.KEY_DOWN):
            section_idx = min(len(SECTIONS) - 1, section_idx + 1)
        elif key in (ord("k"), curses_mod.KEY_UP):
            section_idx = max(0, section_idx - 1)
        elif key == ord("r"):
            continue
        elif key in (10, 13, curses_mod.KEY_ENTER):
            section = SECTIONS[section_idx]
            curses_mod.endwin()
            try:
                _open_section(section, target, stack)
            finally:
                stdscr.clear()


def run(target_root: Path | str, stack_root: Path | str, plain: bool = False) -> int:
    target = _logical_path(target_root)
    stack = Path(stack_root)
    if plain or not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stdout.write(render_plain(target, stack))
        return 0
    try:
        import curses
    except ImportError:
        sys.stdout.write(render_plain(target, stack))
        return 0

    def _main(stdscr: Any) -> None:
        _run_interactive(stdscr, target, stack, curses)

    curses.wrapper(_main)
    return 0

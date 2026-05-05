"""Interactive agentic-stack dashboard.

This is the human front door for an already-installed project. It keeps the
existing verb-style commands available for scripts, but gives terminal users a
single place to inspect health, adapters, memory, transfer, and local dashboard
exports.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from . import __version__
from . import doctor as doctor_mod
from . import schema as schema_mod
from . import state as state_mod
from . import status as status_mod


SECTIONS = ("Overview", "Adapters", "Doctor", "Memory", "Transfer", "Data")


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
        return sum(1 for p in path.glob("**/*.json") if p.is_file())
    except OSError:
        return 0


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
            "pass" if (agent / "memory" / "team").is_dir() else "warn",
            "team brain",
            "initialized" if (agent / "memory" / "team").is_dir() else "not initialized",
        ),
    ]
    adapters = _adapter_rows(target, doc)
    warnings = sum(1 for row in checks + adapters if row["status"] == "warn")
    failures = sum(1 for row in checks + adapters if row["status"] == "fail")
    score = max(0, min(100, 100 - failures * 18 - warnings * 7))

    data_dir = agent / "data-layer"
    dashboard_html = data_dir / "dashboard.html"
    return {
        "project": str(target),
        "version": (doc or {}).get("agentic_stack_version", __version__),
        "installed_at": (doc or {}).get("installed_at", "?"),
        "score": score,
        "warnings": warnings,
        "failures": failures,
        "checks": checks,
        "adapters": adapters,
        "installed": installed,
        "available": missing,
        "brain_summary": status_mod._brain_summary(target),
        "memory": {
            "episodes": _count_lines(agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"),
            "lessons": _count_lines(agent / "memory" / "semantic" / "lessons.jsonl"),
            "candidates": _count_candidate_files(agent / "memory" / "candidates"),
        },
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


def _nav_lines(model: dict[str, Any]) -> list[str]:
    adapter_count = len(model["installed"])
    memory = model["memory"]
    nav = [
        ("Overview", f"{model['score']}%  {_plural(model['warnings'], 'warning')}"),
        ("Adapters", f"{adapter_count} installed"),
        ("Doctor", f"{len(model['checks'])} checks"),
        ("Memory", f"{_plural(memory['lessons'], 'lesson')}, {_plural(memory['candidates'], 'candidate')}"),
        ("Transfer", model["transfer"]["detail"]),
        ("Data", "ready" if model["data"]["exists"] else "not exported"),
    ]
    return [f"  {'>' if idx == 0 else ' '} {name:<12} {detail}" for idx, (name, detail) in enumerate(nav)]


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


def _memory_lines(model: dict[str, Any]) -> list[str]:
    memory = model["memory"]
    return [
        "Memory",
        "",
        f"  episodes:   {memory['episodes']}",
        f"  lessons:    {memory['lessons']}",
        f"  candidates: {memory['candidates']}",
        "",
        "Use semantic lessons for durable rules and candidates for reviewable memory.",
    ]


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
    if section == "Memory":
        return _memory_lines(model)
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
    header = f"agentic-stack dashboard".ljust(max(1, width - 11)) + f"health {model['score']}%"
    version = f"agentic-stack v{model['version']}"
    lines = [
        _clip(header, width),
        _clip(f"{model['project']}  {version}", width),
        _rule(width),
        "",
        *_nav_lines(model),
        "",
        _rule(width),
        "",
        *[_clip(line, width) for line in _section_lines(section, model)],
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
        elif name == "Memory":
            detail = str(model["memory"]["lessons"])
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


def _open_section(section: str, target_root: Path, stack_root: Path) -> None:
    if section in ("Overview", "Adapters"):
        from . import manage_tui

        manage_tui.run(target_root=target_root, stack_root=stack_root)
        _pause()
    elif section == "Doctor":
        doctor_mod.audit(target_root)
        _pause()
    elif section == "Transfer":
        from . import transfer_tui

        transfer_tui.run([], target_root=target_root, stack_root=stack_root)
        _pause()


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
        try:
            curses.curs_set(0)
        except Exception:
            pass
        stdscr.keypad(True)
        section_idx = 0
        while True:
            _draw(stdscr, section_idx, target, stack, curses)
            key = stdscr.getch()
            if key in (ord("q"), 27):
                return
            if key in (ord("j"), curses.KEY_DOWN):
                section_idx = min(len(SECTIONS) - 1, section_idx + 1)
            elif key in (ord("k"), curses.KEY_UP):
                section_idx = max(0, section_idx - 1)
            elif key == ord("r"):
                continue
            elif key in (10, 13, curses.KEY_ENTER):
                section = SECTIONS[section_idx]
                curses.endwin()
                try:
                    _open_section(section, target, stack)
                finally:
                    stdscr.clear()

    curses.wrapper(_main)
    return 0

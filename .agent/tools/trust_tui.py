"""Read-only stdlib TUI for the agentic-stack Trust Console."""
from __future__ import annotations

import os
import sys
import time
from typing import Any

import trust_model


SECTIONS = ("Doctor", "Memory", "Verify", "Team Brain", "Skills", "Instances")


def _clip(text: object, width: int) -> str:
    s = str(text)
    if width <= 0:
        return ""
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: width - 1] + "~"


def _safe_curs_set(curses_module: Any, visibility: int) -> bool:
    try:
        curses_module.curs_set(visibility)
    except Exception:
        return False
    return True


def _plain_lines(project_root: str | None = None) -> list[str]:
    health = trust_model.collect_health(project_root)
    lines = [
        f"agentic-stack Trust Console  project={health['project_root']}  health={health['score']}%",
        "",
        "Doctor",
    ]
    for check in health["checks"]:
        marker = {"pass": "PASS", "warn": "WARN", "fail": "FAIL"}.get(check["status"], check["status"].upper())
        lines.append(f"  {marker:4} {check['label']} - {check['detail']}")
    memory = health["memory"]
    lines.extend([
        "",
        "Memory",
        f"  episodes={memory['episodic']['count']} failures={memory['episodic']['failures']}",
        f"  lessons accepted={memory['lessons']['accepted']} provisional={memory['lessons']['provisional']}",
        f"  candidates staged={memory['candidates']['staged']} graduated={memory['candidates']['graduated']} rejected={memory['candidates']['rejected']}",
        "",
        "Next steps",
        "  agentic-stack memory why <lesson-id>",
        "  agentic-stack verify --all",
        "  agentic-stack team init",
    ])
    return lines


def render_plain(project_root: str | None = None) -> str:
    return "\n".join(_plain_lines(project_root)) + "\n"


def _draw_doctor(stdscr: Any, y: int, x: int, width: int, health: dict[str, Any]) -> int:
    stdscr.addstr(y, x, "Doctor", getattr(stdscr, "A_BOLD", 0) if hasattr(stdscr, "A_BOLD") else 0)
    y += 2
    for check in health["checks"][: max(0, stdscr.getmaxyx()[0] - y - 3)]:
        status = check["status"].upper()
        line = f"{status:4} {check['label']} - {check['detail']}"
        stdscr.addstr(y, x, _clip(line, width))
        y += 1
    return y


def _draw_memory(stdscr: Any, y: int, x: int, width: int, health: dict[str, Any]) -> int:
    memory = health["memory"]
    stdscr.addstr(y, x, "Memory")
    y += 2
    rows = [
        ("episodes", memory["episodic"]["count"]),
        ("failures", memory["episodic"]["failures"]),
        ("accepted lessons", memory["lessons"]["accepted"]),
        ("provisional lessons", memory["lessons"]["provisional"]),
        ("staged candidates", memory["candidates"]["staged"]),
        ("rejected candidates", memory["candidates"]["rejected"]),
    ]
    for label, value in rows:
        stdscr.addstr(y, x, _clip(f"{label:22} {value}", width))
        y += 1
    return y


def _draw_verify(stdscr: Any, y: int, x: int, width: int, project_root: str | None) -> int:
    matrix = trust_model.verify_harnesses(project_root=project_root)
    stdscr.addstr(y, x, "Verify")
    y += 2
    stdscr.addstr(y, x, _clip("harness          install memory skills recall reflect perms", width))
    y += 1
    for row in matrix["harnesses"][: max(0, stdscr.getmaxyx()[0] - y - 3)]:
        line = (
            f"{row['harness']:<16}"
            f"{row['installed']['status']:<8}"
            f"{row['memory']['status']:<7}"
            f"{row['skills']['status']:<7}"
            f"{row['recall']['status']:<7}"
            f"{row['reflect']['status']:<8}"
            f"{row['permissions']['status']}"
        )
        stdscr.addstr(y, x, _clip(line, width))
        y += 1
    return y


def _draw_team(stdscr: Any, y: int, x: int, width: int, health: dict[str, Any]) -> int:
    team = health["team"]
    stdscr.addstr(y, x, "Team Brain")
    y += 2
    stdscr.addstr(y, x, f"path: {_clip(team['path'], max(1, width - 6))}")
    y += 1
    stdscr.addstr(y, x, f"exists: {team['exists']}")
    y += 2
    for name, meta in team["files"].items():
        status = "present" if meta["exists"] else "missing"
        stdscr.addstr(y, x, _clip(f"{name:<24} {status}", width))
        y += 1
    return y


def _draw_skills(stdscr: Any, y: int, x: int, width: int, health: dict[str, Any]) -> int:
    stdscr.addstr(y, x, "Skills")
    y += 2
    stdscr.addstr(y, x, f"loaded: {health['skills']['count']}")
    y += 2
    for name in health["skills"]["names"][: max(0, stdscr.getmaxyx()[0] - y - 3)]:
        stdscr.addstr(y, x, _clip(f"- {name}", width))
        y += 1
    return y


def _draw_instances(stdscr: Any, y: int, x: int, width: int, health: dict[str, Any]) -> int:
    inst = health["instances"]
    stdscr.addstr(y, x, "Instances")
    y += 2
    stdscr.addstr(y, x, f"active: {inst.get('active_instance') or 'none'}")
    y += 1
    stdscr.addstr(y, x, f"count: {inst.get('count', 0)}")
    y += 2
    for row in inst.get("items", [])[: max(0, stdscr.getmaxyx()[0] - y - 3)]:
        stdscr.addstr(y, x, _clip(f"{row.get('id')} state={row.get('state')} pid={row.get('worker_pid')}", width))
        y += 1
    return y


def _draw(stdscr: Any, section: int, project_root: str | None) -> None:
    health = trust_model.collect_health(project_root)
    h, w = stdscr.getmaxyx()
    stdscr.erase()
    header = f"agentic-stack Trust Console  health={health['score']}%  project={health['project_root']}"
    stdscr.addstr(0, 0, _clip(header, w - 1))
    stdscr.addstr(1, 0, "-" * max(0, w - 1))
    rail_w = min(18, max(12, w // 5))
    for idx, name in enumerate(SECTIONS):
        marker = ">" if idx == section else " "
        stdscr.addstr(3 + idx, 1, _clip(f"{marker} {name}", rail_w - 2))
    content_x = rail_w + 1
    content_w = max(10, w - content_x - 1)
    y = 3
    if SECTIONS[section] == "Doctor":
        _draw_doctor(stdscr, y, content_x, content_w, health)
    elif SECTIONS[section] == "Memory":
        _draw_memory(stdscr, y, content_x, content_w, health)
    elif SECTIONS[section] == "Verify":
        _draw_verify(stdscr, y, content_x, content_w, project_root)
    elif SECTIONS[section] == "Team Brain":
        _draw_team(stdscr, y, content_x, content_w, health)
    elif SECTIONS[section] == "Skills":
        _draw_skills(stdscr, y, content_x, content_w, health)
    else:
        _draw_instances(stdscr, y, content_x, content_w, health)
    footer = "up/down move  r refresh  q quit  ? help"
    stdscr.addstr(h - 1, 0, _clip(footer, w - 1))
    stdscr.refresh()


def run(project_root: str | None = None, plain: bool = False) -> int:
    if plain or not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stdout.write(render_plain(project_root))
        return 0
    try:
        import curses
    except ImportError:
        sys.stdout.write(render_plain(project_root))
        return 0

    def _main(stdscr: Any) -> None:
        _safe_curs_set(curses, 0)
        stdscr.keypad(True)
        section = 0
        while True:
            _draw(stdscr, section, project_root)
            key = stdscr.getch()
            if key in (ord("q"), 27):
                return
            if key in (ord("j"), curses.KEY_DOWN):
                section = min(len(SECTIONS) - 1, section + 1)
            elif key in (ord("k"), curses.KEY_UP):
                section = max(0, section - 1)
            elif key == ord("r"):
                time.sleep(0.05)
            elif key == ord("?"):
                stdscr.erase()
                stdscr.addstr(0, 0, "agentic-stack Trust Console help")
                stdscr.addstr(2, 0, "This TUI is read-only in v1.")
                stdscr.addstr(3, 0, "Use explicit CLI commands for memory decisions:")
                stdscr.addstr(5, 2, "python3 .agent/tools/graduate.py <id> --rationale ...")
                stdscr.addstr(6, 2, "python3 .agent/tools/reject.py <id> --reason ...")
                stdscr.addstr(8, 0, "Press any key to return.")
                stdscr.refresh()
                stdscr.getch()

    curses.wrapper(_main)
    return 0

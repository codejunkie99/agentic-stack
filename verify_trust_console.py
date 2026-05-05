#!/usr/bin/env python3
"""Regression checks for the local Trust Console data layer and CLI.

Runs directly, not through pytest:

    python3 verify_trust_console.py
"""
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, ".agent", "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _write_json(path, payload):
    _write(path, json.dumps(payload, indent=2) + "\n")


def _fixture_project():
    root = tempfile.mkdtemp(prefix="agentic-stack-trust-")
    agent = os.path.join(root, ".agent")
    _write(os.path.join(agent, "AGENTS.md"), "# Agent map\n")
    _write(os.path.join(agent, "memory", "personal", "PREFERENCES.md"), "# Preferences\n")
    _write(os.path.join(agent, "memory", "working", "WORKSPACE.md"), "# Workspace\n")
    _write(os.path.join(agent, "memory", "working", "REVIEW_QUEUE.md"), "# Review Queue\n\n_No pending candidates._\n")
    _write(os.path.join(agent, "protocols", "permissions.md"), "# Permissions\n")
    _write(
        os.path.join(agent, "skills", "_manifest.jsonl"),
        json.dumps({"name": "debug-investigator"}) + "\n"
        + json.dumps({"name": "memory-manager"}) + "\n",
    )
    _write(
        os.path.join(agent, "memory", "episodic", "AGENT_LEARNINGS.jsonl"),
        json.dumps({
            "timestamp": "2026-05-05T10:00:00",
            "result": "success",
            "action": "proactive-recall: timestamps",
            "reflection": "Used UTC timestamp lesson.",
        }) + "\n"
        + json.dumps({
            "timestamp": "2026-05-05T11:00:00",
            "result": "failure",
            "action": "deploy",
            "reflection": "Deploy failed.",
        }) + "\n",
    )
    lesson = {
        "id": "lesson_utc",
        "claim": "Always serialize timestamps in UTC",
        "conditions": ["timestamp", "utc"],
        "evidence_ids": ["2026-05-05T10:00:00"],
        "status": "accepted",
        "accepted_at": "2026-05-05T10:01:00",
        "reviewer": "learn.py",
        "rationale": "avoids cross-region bugs",
        "source_candidate": "utc-candidate",
    }
    _write(os.path.join(agent, "memory", "semantic", "lessons.jsonl"), json.dumps(lesson) + "\n")
    _write(os.path.join(agent, "memory", "semantic", "LESSONS.md"), "- Always serialize timestamps in UTC\n")
    _write_json(os.path.join(agent, "memory", "candidates", "rejected", "bad.json"), {
        "id": "bad",
        "claim": "Too specific to keep",
        "status": "rejected",
        "decisions": [{"decision": "rejected", "reason": "too narrow"}],
    })
    _write_json(os.path.join(agent, "memory", "candidates", "pending.json"), {
        "id": "pending",
        "claim": "Pending review",
        "status": "staged",
    })
    _write(os.path.join(root, ".gitignore"), ".agent/memory/.index/\n")
    _write(
        os.path.join(root, "CLAUDE.md"),
        "Read .agent/AGENTS.md, PREFERENCES.md, LESSONS.md, permissions.md. "
        "Run recall.py before risky work. Use memory_reflect.py after actions. "
        "Skill loading via .agent/skills/_manifest.jsonl.\n",
    )
    _write_json(os.path.join(root, ".claude", "settings.json"), {"hooks": {}})
    _write(
        os.path.join(root, ".openclaw-system.md"),
        "Read .agent/AGENTS.md and PREFERENCES.md and LESSONS.md and permissions.md.\n",
    )
    # AGENTS.md exists but opencode.json does NOT — exercises the all-files install rule.
    _write(os.path.join(root, "AGENTS.md"), "Read .agent/PREFERENCES.md and LESSONS.md and permissions.md.\n")
    return root


def main():
    failures = []

    def check(name, condition, detail=""):
        mark = PASS if condition else FAIL
        print(f"  {mark} {name}" + (f" - {detail}" if detail and not condition else ""))
        if not condition:
            failures.append(name)

    import trust_model

    project = _fixture_project()

    print("\n1. collect_health returns normalized local monitoring data")
    health = trust_model.collect_health(project)
    check("agent root detected", health["agent_root"].endswith(".agent"), health.get("agent_root", ""))
    check("health score is numeric", isinstance(health["score"], int), repr(health.get("score")))
    check("episodic count is collected", health["memory"]["episodic"]["count"] == 2)
    check("lesson count is collected", health["memory"]["lessons"]["accepted"] == 1)
    check("candidate count is collected", health["memory"]["candidates"]["staged"] == 1)
    check("rejected count is collected", health["memory"]["candidates"]["rejected"] == 1)
    check("skills are loaded", health["skills"]["count"] == 2)
    check("team missing is reported", health["team"]["exists"] is False)

    print("\n2. memory why resolves accepted lesson evidence")
    why = trust_model.memory_why("lesson_utc", project)
    check("why returns lesson", why["found"] is True)
    check("why includes evidence id", "2026-05-05T10:00:00" in why["lesson"]["evidence_ids"])
    check("why includes matching evidence entry", len(why["evidence"]) == 1)

    print("\n3. verify_harnesses reports adapter conformance")
    matrix = trust_model.verify_harnesses(project_root=project)
    by_name = {row["harness"]: row for row in matrix["harnesses"]}
    check("claude-code installed", by_name["claude-code"]["installed"]["status"] == "pass")
    check("claude-code recall pass", by_name["claude-code"]["recall"]["status"] == "pass")
    check("openclaw missing recall warning", by_name["openclaw"]["recall"]["status"] == "warn")
    check(
        "opencode partial install reports fail",
        by_name["opencode"]["installed"]["status"] == "fail"
        and "opencode.json" in by_name["opencode"]["installed"]["detail"],
        by_name["opencode"]["installed"],
    )
    check("hermes single-file install passes", by_name["hermes"]["installed"]["status"] == "pass")

    print("\n4. team init creates explicit team brain files")
    init = trust_model.team_init(project)
    check("team init creates files", init["created"] >= 5)
    team = trust_model.team_status(project)
    check("team status exists after init", team["exists"] is True)
    check("team conventions present", "CONVENTIONS.md" in team["files"])

    print("\n5. CLI returns JSON diagnostics")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "agentic_stack_cli.py"), "doctor", "--json", "--project", project],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    check("doctor --json exits 0", proc.returncode == 0, proc.stderr)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        payload = {}
        check("doctor --json emits parseable JSON", False, str(exc))
    else:
        check("doctor --json includes score", isinstance(payload.get("score"), int), proc.stdout[:200])

    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "agentic_stack_cli.py"), "verify", "--all", "--json", "--project", project],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    check("verify --all --json exits 0", proc.returncode == 0, proc.stderr)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        check("verify --json emits parseable JSON", False, str(exc))
    else:
        check("verify --json includes harnesses", len(payload.get("harnesses", [])) >= 3)

    broken = tempfile.mkdtemp(prefix="agentic-stack-broken-")
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, "agentic_stack_cli.py"), "doctor", "--json", "--project", broken],
        capture_output=True,
        text=True,
        cwd=HERE,
    )
    check("doctor --json exits 1 on missing .agent", proc.returncode == 1, f"rc={proc.returncode}")
    try:
        payload = json.loads(proc.stdout)
        check("doctor --json broken still emits parseable payload", isinstance(payload.get("score"), int))
    except json.JSONDecodeError as exc:
        check("doctor --json broken emits parseable JSON", False, str(exc))

    print("\n6. TUI tolerates terminals without cursor visibility support")
    import trust_tui

    class FakeCurses:
        class error(Exception):
            pass

        @staticmethod
        def curs_set(_visibility):
            raise FakeCurses.error("unsupported terminal")

    try:
        trust_tui._safe_curs_set(FakeCurses, 0)
    except Exception as exc:
        check("safe cursor update ignores curses errors", False, str(exc))
    else:
        check("safe cursor update ignores curses errors", True)

    print("\n7. Glyph fallback adapts to stdout encoding")

    class _FakeStream:
        def __init__(self, encoding):
            self.encoding = encoding

    ascii_glyphs = trust_tui._select_glyphs(stream=_FakeStream("ascii"))
    utf8_glyphs = trust_tui._select_glyphs(stream=_FakeStream("utf-8"))
    none_glyphs = trust_tui._select_glyphs(stream=_FakeStream(None))
    check("ASCII encoding falls back to ASCII glyphs", ascii_glyphs == trust_tui._STATUS_GLYPH_ASCII)
    check("UTF-8 encoding uses Unicode glyphs", utf8_glyphs == trust_tui._STATUS_GLYPH_UNICODE)
    check("None encoding falls back to ASCII glyphs", none_glyphs == trust_tui._STATUS_GLYPH_ASCII)

    if failures:
        print(f"\n{len(failures)} failure(s)")
        return 1
    print("\nall pass")
    return 0


if __name__ == "__main__":
    sys.exit(main())

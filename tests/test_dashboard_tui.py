import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FakeCurses:
    A_BOLD = 1
    KEY_DOWN = 258
    KEY_UP = 259
    KEY_ENTER = 343

    def __init__(self):
        self.cursor_values = []
        self.endwin_count = 0

    def curs_set(self, value):
        self.cursor_values.append(value)

    def endwin(self):
        self.endwin_count += 1


class FakeScreen:
    def __init__(self, keys, height=32, width=100):
        self.keys = list(keys)
        self.height = height
        self.width = width
        self.keypad_enabled = None
        self.clear_count = 0
        self.current = {}
        self.snapshots = []

    def getmaxyx(self):
        return self.height, self.width

    def keypad(self, enabled):
        self.keypad_enabled = enabled

    def erase(self):
        self.current = {}

    def clear(self):
        self.clear_count += 1
        self.current = {}

    def addstr(self, y, x, text, attr=0):
        self.current[(y, x)] = text

    def refresh(self):
        self.snapshots.append(dict(self.current))

    def getch(self):
        if self.keys:
            return self.keys.pop(0)
        return ord("q")


class DashboardTuiTest(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        agent = root / ".agent"
        (agent / "memory" / "personal").mkdir(parents=True)
        (agent / "memory" / "semantic").mkdir(parents=True)
        (agent / "memory" / "episodic").mkdir(parents=True)
        (agent / "memory" / "candidates").mkdir(parents=True)
        (agent / "memory" / "candidates" / "graduated").mkdir(parents=True)
        (agent / "memory" / "candidates" / "rejected").mkdir(parents=True)
        (agent / "memory" / "team").mkdir(parents=True)
        (agent / "runtime").mkdir(parents=True)
        (agent / "skills" / "example").mkdir(parents=True)
        (agent / "protocols").mkdir(parents=True)
        (root / ".agents" / "skills").mkdir(parents=True)
        (root / "AGENTS.md").write_text(
            "Use .agent/memory/personal/PREFERENCES.md and .agent/memory/semantic/LESSONS.md.\n"
            "Load skills, call .agent/tools/recall.py, log with .agent/tools/memory_reflect.py, "
            "and follow .agent/protocols/permissions.md.\n",
            encoding="utf-8",
        )
        (agent / "AGENTS.md").write_text("# Agentic Stack\n", encoding="utf-8")
        (agent / "protocols" / "permissions.md").write_text("# Permissions\n", encoding="utf-8")
        (agent / "memory" / "personal" / "PREFERENCES.md").write_text(
            "# Preferences\n\n- Keep output direct.\n",
            encoding="utf-8",
        )
        (agent / "memory" / "semantic" / "lessons.jsonl").write_text(
            json.dumps(
                {
                    "id": "lesson_1",
                    "status": "accepted",
                    "claim": "Use local checks.",
                    "evidence_ids": ["episode_1"],
                }
            )
            + "\n"
            + json.dumps({"id": "lesson_2", "status": "provisional", "claim": "Review before deploy."})
            + "\n",
            encoding="utf-8",
        )
        (agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl").write_text(
            json.dumps({"id": "episode_1", "event": "installed", "result": "success"}) + "\n",
            encoding="utf-8",
        )
        (agent / "memory" / "candidates" / "candidate_1.json").write_text(
            json.dumps({"id": "candidate_1", "claim": "Prefer the dashboard.", "status": "staged"}) + "\n",
            encoding="utf-8",
        )
        (agent / "memory" / "candidates" / "rejected" / "candidate_2.json").write_text(
            json.dumps({"id": "candidate_2", "claim": "Use a hidden command.", "status": "rejected"}) + "\n",
            encoding="utf-8",
        )
        (agent / "skills" / "example" / "SKILL.md").write_text(
            "# Example\n",
            encoding="utf-8",
        )
        (agent / "skills" / "_manifest.jsonl").write_text(
            json.dumps({"name": "example", "description": "Example skill"}) + "\n",
            encoding="utf-8",
        )
        for name in ("CONVENTIONS.md", "REVIEW_RULES.md", "DEPLOYMENT_LESSONS.md", "INCIDENTS.md", "APPROVED_SKILLS.md"):
            (agent / "memory" / "team" / name).write_text(f"# {name}\n", encoding="utf-8")
        (agent / "runtime" / "instances.json").write_text(
            json.dumps(
                {
                    "active_instance": "worker-a",
                    "instances": [
                        {"id": "worker-a", "state": "running", "worker_pid": 1234},
                        {"id": "worker-b", "state": "stopped", "worker_pid": None},
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        (agent / "install.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "agentic_stack_version": "0.13.0",
                    "installed_at": "2026-05-06T00:00:00Z",
                    "adapters": {
                        "codex": {
                            "files_written": [],
                            "files_overwritten": [],
                            "file_results": [],
                            "post_install_results": [],
                        }
                    },
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def run_cli(self, cwd: Path, *args: str):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["AGENTIC_STACK_ROOT"] = str(ROOT)
        return subprocess.run(
            ["python3", "-m", "harness_manager.cli", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_plain_dashboard_renders_main_sections(self):
        from harness_manager import dashboard_tui

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            rendered = dashboard_tui.render_plain(project, ROOT, width=76)

        self.assertIn("agentic-stack dashboard", rendered)
        self.assertIn("> Overview", rendered)
        self.assertIn("Adapters", rendered)
        self.assertIn("Doctor", rendered)
        self.assertIn("Verify", rendered)
        self.assertIn("Memory", rendered)
        self.assertIn("Team Brain", rendered)
        self.assertIn("Skills", rendered)
        self.assertIn("Instances", rendered)
        self.assertIn("Transfer", rendered)
        self.assertIn("Data", rendered)
        self.assertIn("codex", rendered)
        self.assertIn("2 lessons", rendered)

    def test_verify_section_renders_harness_matrix(self):
        from harness_manager import dashboard_tui

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            rendered = dashboard_tui.render_plain(project, ROOT, width=96, section="Verify")

        self.assertIn("Verify", rendered)
        self.assertIn("harness", rendered)
        self.assertIn("install", rendered)
        self.assertIn("memory", rendered)
        self.assertIn("skills", rendered)
        self.assertIn("recall", rendered)
        self.assertIn("reflect", rendered)
        self.assertIn("permissions", rendered)
        self.assertIn("codex", rendered)

    def test_team_skills_instances_sections_render(self):
        from harness_manager import dashboard_tui

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            team = dashboard_tui.render_plain(project, ROOT, width=96, section="Team Brain")
            skills = dashboard_tui.render_plain(project, ROOT, width=96, section="Skills")
            instances = dashboard_tui.render_plain(project, ROOT, width=96, section="Instances")

        self.assertIn("Team Brain", team)
        self.assertIn("CONVENTIONS.md", team)
        self.assertIn("APPROVED_SKILLS.md", team)
        self.assertIn("Skills", skills)
        self.assertIn("example", skills)
        self.assertIn("Instances", instances)
        self.assertIn("worker-a", instances)
        self.assertIn("running", instances)

    def test_memory_section_renders_learned_rejected_and_why(self):
        from harness_manager import dashboard_tui

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            rendered = dashboard_tui.render_plain(project, ROOT, width=96, section="Memory")
            why = dashboard_tui.memory_why("lesson_1", project)

        self.assertIn("Accepted", rendered)
        self.assertIn("lesson_1", rendered)
        self.assertIn("candidates: 2 (1 staged, 0 graduated, 1 rejected)", rendered)
        self.assertIn("Rejected", rendered)
        self.assertIn("candidate_2", rendered)
        self.assertTrue(why["found"])
        self.assertEqual(why["lesson"]["id"], "lesson_1")
        self.assertEqual(len(why["evidence"]), 1)

    def test_dashboard_cli_plain_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            result = self.run_cli(project, "dashboard", str(project), "--plain")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agentic-stack dashboard", result.stdout)
        self.assertIn("codex", result.stdout)

    def test_dash_alias_plain_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            result = self.run_cli(project, "dash", str(project), "--plain")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agentic-stack dashboard", result.stdout)

    def test_bare_installed_project_stays_script_safe_without_tty(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            result = self.run_cli(project)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("open dashboard", result.stdout)

    def test_interactive_dashboard_keypress_navigation(self):
        from harness_manager import dashboard_tui

        curses = FakeCurses()
        screen = FakeScreen(
            [
                curses.KEY_DOWN,
                curses.KEY_DOWN,
                ord("r"),
                curses.KEY_UP,
                ord("q"),
            ]
        )
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)

            dashboard_tui._run_interactive(screen, project, ROOT, curses)

        self.assertEqual(curses.cursor_values, [0])
        self.assertTrue(screen.keypad_enabled)
        headings = [snapshot.get((4, 21)) for snapshot in screen.snapshots]
        self.assertEqual(headings, ["Overview", "Adapters", "Doctor", "Doctor", "Adapters"])

    def test_interactive_dashboard_enter_opens_selected_section(self):
        from harness_manager import dashboard_tui

        curses = FakeCurses()
        screen = FakeScreen([curses.KEY_DOWN, curses.KEY_ENTER, ord("q")])
        opened = []
        original_open_section = dashboard_tui._open_section

        def fake_open_section(section, target_root, stack_root):
            opened.append((section, target_root, stack_root))

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.make_project(project)
            try:
                dashboard_tui._open_section = fake_open_section
                dashboard_tui._run_interactive(screen, project, ROOT, curses)
            finally:
                dashboard_tui._open_section = original_open_section

        self.assertEqual(opened, [("Adapters", project, ROOT)])
        self.assertEqual(curses.endwin_count, 1)
        self.assertEqual(screen.clear_count, 1)


if __name__ == "__main__":
    unittest.main()

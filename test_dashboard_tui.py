import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


class DashboardTuiTest(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        agent = root / ".agent"
        (agent / "memory" / "personal").mkdir(parents=True)
        (agent / "memory" / "semantic").mkdir(parents=True)
        (agent / "memory" / "episodic").mkdir(parents=True)
        (agent / "memory" / "candidates").mkdir(parents=True)
        (agent / "skills" / "example").mkdir(parents=True)
        (agent / "protocols").mkdir(parents=True)
        (agent / "AGENTS.md").write_text("# Agentic Stack\n", encoding="utf-8")
        (agent / "memory" / "personal" / "PREFERENCES.md").write_text(
            "# Preferences\n\n- Keep output direct.\n",
            encoding="utf-8",
        )
        (agent / "memory" / "semantic" / "lessons.jsonl").write_text(
            json.dumps({"id": "lesson_1", "status": "accepted", "claim": "Use local checks."}) + "\n",
            encoding="utf-8",
        )
        (agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl").write_text(
            json.dumps({"event": "installed"}) + "\n",
            encoding="utf-8",
        )
        (agent / "skills" / "example" / "SKILL.md").write_text(
            "# Example\n",
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
        self.assertIn("Memory", rendered)
        self.assertIn("Transfer", rendered)
        self.assertIn("Data", rendered)
        self.assertIn("codex", rendered)
        self.assertIn("1 lesson", rendered)

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


if __name__ == "__main__":
    unittest.main()

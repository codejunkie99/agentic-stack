import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BrainIntegrationTest(unittest.TestCase):
    def run_cli(self, cwd: Path, *args: str, env: dict[str, str] | None = None):
        merged = os.environ.copy()
        merged["PYTHONPATH"] = str(ROOT)
        merged["AGENTIC_STACK_ROOT"] = str(ROOT)
        if env:
            merged.update(env)
        return subprocess.run(
            [sys.executable, "-m", "harness_manager.cli", *args],
            cwd=cwd,
            env=merged,
            text=True,
            capture_output=True,
            check=False,
        )

    def fake_brain(self, root: Path) -> tuple[Path, Path]:
        log = root / "brain-argv.jsonl"
        fake = root / "brain"
        fake.write_text(
            """#!/usr/bin/env python3
import json, os, sys
with open(os.environ["BRAIN_FAKE_LOG"], "a", encoding="utf-8") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
cmd = sys.argv[1] if len(sys.argv) > 1 else ""
if cmd == "doctor":
    print("Ready. fake brain.")
elif cmd == "ask":
    print("Matches:\\n- fake memory")
elif cmd == "note":
    print("Saved.")
elif cmd == "log":
    print("Recent notes:\\n- fake memory")
else:
    print("fake brain " + " ".join(sys.argv[1:]))
""",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        return fake, log

    def test_missing_brain_binary_has_install_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = {
                "PATH": str(Path(tmp) / "empty"),
                "AGENTIC_STACK_BRAIN_BIN": "",
            }

            result = self.run_cli(Path(tmp), "brain", "status", env=env)

            self.assertEqual(result.returncode, 2)
            self.assertIn("brain CLI not found", result.stderr)
            self.assertIn("brew install codejunkie99/tap/brain", result.stderr)

    def test_configured_missing_brain_binary_does_not_traceback(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-brain"
            env = {"AGENTIC_STACK_BRAIN_BIN": str(missing)}

            result = self.run_cli(Path(tmp), "brain", "status", env=env)

            self.assertEqual(result.returncode, 2)
            self.assertIn(str(missing), result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_brain_onboard_passes_project_dir_and_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            fake, log = self.fake_brain(root)
            env = {
                "AGENTIC_STACK_BRAIN_BIN": str(fake),
                "BRAIN_FAKE_LOG": str(log),
            }

            result = self.run_cli(
                project,
                "brain",
                "onboard",
                str(project),
                "--agents",
                "codex,cursor",
                "--yes",
                "--reconfigure",
                env=env,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(
                calls[-1],
                [
                    "onboard",
                    "--project-dir",
                    str(project),
                    "--agents",
                    "codex,cursor",
                    "--yes",
                    "--reconfigure",
                ],
            )

    def test_global_confirm_flags_only_apply_to_brain_onboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            fake, log = self.fake_brain(root)
            env = {
                "AGENTIC_STACK_BRAIN_BIN": str(fake),
                "BRAIN_FAKE_LOG": str(log),
            }

            status = self.run_cli(project, "brain", "status", "--yes", "--reconfigure", env=env)
            onboard = self.run_cli(project, "brain", "onboard", "--yes", "--reconfigure", env=env)

            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertEqual(onboard.returncode, 0, onboard.stderr)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(calls[-2], ["doctor"])
            self.assertEqual(Path(calls[-1][2]).resolve(), project.resolve())
            self.assertEqual(
                calls[-1][:2] + calls[-1][3:],
                ["onboard", "--project-dir", "--agents", "none", "--yes", "--reconfigure"],
            )

    def test_brain_bridge_forwards_ask(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake, log = self.fake_brain(root)
            env = os.environ.copy()
            env["AGENTIC_STACK_BRAIN_BIN"] = str(fake)
            env["BRAIN_FAKE_LOG"] = str(log)

            result = subprocess.run(
                ["python3", str(ROOT / ".agent" / "tools" / "brain_bridge.py"), "ask", "auth", "pkce"],
                cwd=root,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("fake memory", result.stdout)
            calls = [json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(calls[-1], ["ask", "auth pkce"])

    def test_brain_skill_is_registered(self):
        manifest = (ROOT / ".agent" / "skills" / "_manifest.jsonl").read_text(encoding="utf-8")
        rows = [json.loads(line) for line in manifest.splitlines() if line.strip()]
        brain = next(row for row in rows if row["name"] == "brain")

        self.assertIn("long-term memory", brain["triggers"])
        self.assertTrue((ROOT / ".agent" / "skills" / "brain" / "SKILL.md").is_file())
        self.assertIn("## brain", (ROOT / ".agent" / "skills" / "_index.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

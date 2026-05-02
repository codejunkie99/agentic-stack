import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from harness_manager.transfer_bundle import encode_bundle, export_bundle


ROOT = Path(__file__).resolve().parent


class TransferCliTest(unittest.TestCase):
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

    def make_agent(self, root: Path):
        agent = root / ".agent"
        (agent / "memory" / "personal").mkdir(parents=True)
        (agent / "memory" / "semantic").mkdir(parents=True)
        (agent / "skills").mkdir(parents=True)
        (agent / "memory" / "personal" / "PREFERENCES.md").write_text(
            "# Preferences\n\n- Prefer terse responses.\n",
            encoding="utf-8",
        )
        (agent / "memory" / "semantic" / "lessons.jsonl").write_text(
            json.dumps({"id": "lesson_cli", "claim": "Use UTC.", "conditions": ["time"], "status": "accepted"}) + "\n",
            encoding="utf-8",
        )
        (agent / "skills" / "_index.md").write_text("# Skills\n", encoding="utf-8")
        return agent

    def test_transfer_help(self):
        result = self.run_cli(ROOT, "transfer", "--help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("agentic-stack transfer", result.stdout)
        self.assertIn("export", result.stdout)
        self.assertIn("import", result.stdout)

    def test_bare_transfer_refuses_non_tty(self):
        result = self.run_cli(ROOT, "transfer")

        self.assertEqual(result.returncode, 2)
        self.assertIn("interactive", result.stderr)

    def test_export_prints_curl_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            self.make_agent(work)

            result = self.run_cli(
                work,
                "transfer",
                "export",
                "--target",
                "codex",
                "--scope",
                "preferences",
                "--print-curl",
                "--json",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("curl -fsSL", result.stdout)
            payload = json.loads(result.stdout.splitlines()[-1])
            self.assertEqual(payload["targets"], ["codex"])
            self.assertIn("payload", payload)
            self.assertIn("sha256", payload)

    def test_import_payload_applies_bundle(self):
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
            src = Path(src_tmp)
            dst = Path(dst_tmp)
            agent = self.make_agent(src)
            payload, digest = encode_bundle(export_bundle(agent, targets=["terminal"], scopes=["preferences", "accepted_lessons"]))

            result = self.run_cli(
                dst,
                "transfer",
                "import",
                "--payload",
                payload,
                "--sha256",
                digest,
                "--target",
                "terminal",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("imported transfer bundle", result.stdout)
            self.assertTrue((dst / ".agent" / "memory" / "personal" / "PREFERENCES.md").exists())
            self.assertTrue((dst / ".agent" / "memory" / "semantic" / "LESSONS.md").exists())

    def test_import_codex_into_fresh_project_copies_full_brain(self):
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
            src = Path(src_tmp)
            dst = Path(dst_tmp)
            agent = self.make_agent(src)
            payload, digest = encode_bundle(export_bundle(agent, targets=["codex"], scopes=["preferences"]))

            result = self.run_cli(
                dst,
                "transfer",
                "import",
                "--payload",
                payload,
                "--sha256",
                digest,
                "--target",
                "codex",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((dst / ".agent" / "AGENTS.md").exists())
            self.assertTrue((dst / "AGENTS.md").exists())
            self.assertTrue((dst / ".agents" / "skills").exists())


if __name__ == "__main__":
    unittest.main()

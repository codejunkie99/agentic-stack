import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class UpgradeManifestDoctorTest(unittest.TestCase):
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

    def make_brain(self, root: Path) -> Path:
        agent = root / ".agent"
        (agent / "harness" / "hooks").mkdir(parents=True)
        (agent / "memory" / "personal").mkdir(parents=True)
        (agent / "memory" / "candidates").mkdir(parents=True)
        (agent / "memory" / "semantic").mkdir(parents=True)
        (agent / "memory" / "episodic").mkdir(parents=True)
        (agent / "memory" / "working").mkdir(parents=True)
        (agent / "protocols").mkdir(parents=True)
        (agent / "skills").mkdir(parents=True)
        (agent / "tools").mkdir(parents=True)
        (agent / "AGENTS.md").write_text("# Brain\n", encoding="utf-8")
        return agent

    def manifest_rows(self, project: Path) -> list[dict]:
        manifest = project / ".agent" / "skills" / "_manifest.jsonl"
        return [
            json.loads(line)
            for line in manifest.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def test_sync_manifest_upserts_skill_frontmatter_and_preserves_extras(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            agent = self.make_brain(project)
            skill_dir = agent / "skills" / "diagram"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                """---
name: diagram
version: 2026-05-09
triggers: ["diagram", "flowchart"]
tools: [bash, mcp.diagram.draw]
preconditions: [".agent exists"]
constraints: ["keep it readable"]
category: visualization
---

# Diagram
""",
                encoding="utf-8",
            )
            (agent / "skills" / "_manifest.jsonl").write_text(
                json.dumps({"name": "other", "triggers": ["keep"]}) + "\n"
                + json.dumps({"name": "diagram", "version": "old", "feature_flag": "diagram"}) + "\n",
                encoding="utf-8",
            )

            result = self.run_cli(project, "sync-manifest", project)

            self.assertEqual(result.returncode, 0, result.stderr)
            rows = {row["name"]: row for row in self.manifest_rows(project)}
            self.assertEqual(rows["diagram"]["version"], "2026-05-09")
            self.assertEqual(rows["diagram"]["triggers"], ["diagram", "flowchart"])
            self.assertEqual(rows["diagram"]["tools"], ["bash", "mcp.diagram.draw"])
            self.assertEqual(rows["diagram"]["category"], "visualization")
            self.assertEqual(rows["diagram"]["feature_flag"], "diagram")
            self.assertEqual(rows["other"]["triggers"], ["keep"])

    def test_upgrade_copies_infrastructure_and_new_skills_without_touching_user_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            agent = self.make_brain(project)
            (project / "CLAUDE.md").write_text("user claude\n", encoding="utf-8")
            (project / ".claude").mkdir()
            (project / ".claude" / "settings.json").write_text('{"user": true}\n', encoding="utf-8")
            (agent / "harness" / "hooks" / "claude_code_post_tool.py").write_text("old hook\n", encoding="utf-8")
            (agent / "memory" / "auto_dream.py").write_text("old dream\n", encoding="utf-8")
            (agent / "tools" / "skill_loader.py").write_text("old loader\n", encoding="utf-8")
            (agent / "memory" / "personal" / "PREFERENCES.md").write_text("user prefs\n", encoding="utf-8")
            (agent / "memory" / "candidates" / "candidate.json").write_text("user candidate\n", encoding="utf-8")
            custom_skill = agent / "skills" / "debug-investigator"
            custom_skill.mkdir()
            (custom_skill / "SKILL.md").write_text("user debug skill\n", encoding="utf-8")
            (agent / "skills" / "_manifest.jsonl").write_text("", encoding="utf-8")
            (agent / "skills" / "_index.md").write_text("# old index\n", encoding="utf-8")

            result = self.run_cli(project, "upgrade", project, "--yes")

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((project / "CLAUDE.md").read_text(encoding="utf-8"), "user claude\n")
            self.assertEqual((project / ".claude" / "settings.json").read_text(encoding="utf-8"), '{"user": true}\n')
            self.assertEqual((agent / "memory" / "personal" / "PREFERENCES.md").read_text(encoding="utf-8"), "user prefs\n")
            self.assertEqual((agent / "memory" / "candidates" / "candidate.json").read_text(encoding="utf-8"), "user candidate\n")
            self.assertEqual((custom_skill / "SKILL.md").read_text(encoding="utf-8"), "user debug skill\n")
            self.assertEqual(
                (agent / "harness" / "hooks" / "claude_code_post_tool.py").read_text(encoding="utf-8"),
                (ROOT / ".agent" / "harness" / "hooks" / "claude_code_post_tool.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (agent / "memory" / "auto_dream.py").read_text(encoding="utf-8"),
                (ROOT / ".agent" / "memory" / "auto_dream.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                (agent / "tools" / "skill_loader.py").read_text(encoding="utf-8"),
                (ROOT / ".agent" / "tools" / "skill_loader.py").read_text(encoding="utf-8"),
            )
            self.assertTrue((agent / "skills" / "tldraw" / "SKILL.md").is_file())
            rows = {row["name"]: row for row in self.manifest_rows(project)}
            self.assertIn("tldraw", rows)
            self.assertIn("draw", rows["tldraw"]["triggers"])
            self.assertIn("tldraw", (agent / "skills" / "_index.md").read_text(encoding="utf-8"))

    def test_doctor_warns_for_missing_and_unwired_claude_hook_files(self):
        from harness_manager import doctor

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            agent = self.make_brain(project)
            (project / "CLAUDE.md").write_text("use .agent\n", encoding="utf-8")
            (project / ".claude").mkdir()
            (project / ".claude" / "settings.json").write_text(
                json.dumps(
                    {
                        "hooks": {
                            "PostToolUse": [
                                {
                                    "hooks": [
                                        {
                                            "type": "command",
                                            "command": "python3 \"$CLAUDE_PROJECT_DIR/.agent/harness/hooks/missing.py\"",
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ),
                encoding="utf-8",
            )
            (agent / "harness" / "hooks" / "orphan.py").write_text("# orphan\n", encoding="utf-8")
            entry = {
                "files_written": ["CLAUDE.md", ".claude/settings.json"],
                "files_overwritten": [],
                "file_results": [],
                "post_install_results": [],
            }

            status, lines = doctor._audit_adapter(project, "claude-code", entry)

            self.assertEqual(status, doctor.YELLOW)
            detail = "\n".join(lines)
            self.assertIn("missing hook command file", detail)
            self.assertIn(".agent/harness/hooks/missing.py", detail)
            self.assertIn("orphaned hook files", detail)
            self.assertIn(".agent/harness/hooks/orphan.py", detail)


if __name__ == "__main__":
    unittest.main()

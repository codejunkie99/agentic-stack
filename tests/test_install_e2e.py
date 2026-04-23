"""End-to-end install + doctor + remove against a temp project.

Specifically verifies the #18 fix: claude-code adapter installs with
$CLAUDE_PROJECT_DIR substituted into hook command paths, so hooks
resolve correctly regardless of cwd.

Run: python3 -m unittest tests.test_install_e2e -v
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness_manager import doctor as doctor_mod  # noqa: E402
from harness_manager import install as install_mod  # noqa: E402
from harness_manager import remove as remove_mod  # noqa: E402
from harness_manager import schema as schema_mod  # noqa: E402
from harness_manager import state as state_mod  # noqa: E402


def _adapter_manifest(name: str) -> tuple[dict, Path]:
    p = REPO_ROOT / "adapters" / name / "adapter.json"
    return schema_mod.validate(p), p.parent


class TestEndToEndInstallFlow(unittest.TestCase):
    def setUp(self):
        self.target = Path(tempfile.mkdtemp(prefix="hm-e2e-"))
        self.target_stack_brain_backup = REPO_ROOT / ".agent" / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl"
        self._brain_snapshot = self.target_stack_brain_backup.read_bytes() if self.target_stack_brain_backup.is_file() else None

    def tearDown(self):
        # Revert any episodic logging the install may have triggered against
        # the source brain.
        if self._brain_snapshot is not None:
            self.target_stack_brain_backup.write_bytes(self._brain_snapshot)
        for cache in [
            REPO_ROOT / ".agent" / "memory" / "__pycache__",
            REPO_ROOT / ".agent" / "harness" / "__pycache__",
            REPO_ROOT / ".agent" / "harness" / "hooks" / "__pycache__",
            REPO_ROOT / "harness_manager" / "__pycache__",
            REPO_ROOT / "tests" / "__pycache__",
        ]:
            shutil.rmtree(cache, ignore_errors=True)
        shutil.rmtree(self.target, ignore_errors=True)

    def _install(self, adapter_name: str):
        manifest, adapter_dir = _adapter_manifest(adapter_name)
        install_mod.install(
            manifest=manifest,
            target_root=self.target,
            adapter_dir=adapter_dir,
            stack_root=REPO_ROOT,
            log=lambda _: None,  # silent in test
        )

    # ---- #18 regression test ------------------------------------------

    def test_18_claude_code_settings_substitutes_brain_root(self):
        """The whole point of v0.9.0: cwd-stable hook commands."""
        self._install("claude-code")
        settings_path = self.target / ".claude" / "settings.json"
        self.assertTrue(settings_path.is_file(), "settings.json was not written")
        content = settings_path.read_text(encoding="utf-8")

        # Placeholder must be gone.
        self.assertNotIn(
            "{{BRAIN_ROOT}}",
            content,
            "{{BRAIN_ROOT}} placeholder leaked into installed settings.json",
        )
        # Actual primitive must be present in both hook commands.
        self.assertIn(
            "$CLAUDE_PROJECT_DIR/.agent/harness/hooks/claude_code_post_tool.py",
            content,
            "PostToolUse hook missing $CLAUDE_PROJECT_DIR substitution",
        )
        self.assertIn(
            "$CLAUDE_PROJECT_DIR/.agent/memory/auto_dream.py",
            content,
            "Stop hook missing $CLAUDE_PROJECT_DIR substitution",
        )
        # Relative-path form must NOT be present (the bug).
        relative_pattern = re.compile(
            r'"command":\s*"python3 \.agent/'
        )
        self.assertIsNone(
            relative_pattern.search(content),
            "settings.json still contains the buggy relative-path hook command",
        )

    # ---- install.json shape -------------------------------------------

    def test_install_json_well_formed(self):
        self._install("claude-code")
        doc = state_mod.load(self.target)
        self.assertIsNotNone(doc)
        self.assertEqual(doc["schema_version"], 1)
        self.assertIn("claude-code", doc["adapters"])
        entry = doc["adapters"]["claude-code"]
        self.assertEqual(
            sorted(entry["files_written"]),
            sorted(["CLAUDE.md", ".claude/settings.json"]),
        )
        self.assertEqual(entry["brain_root_primitive"], "$CLAUDE_PROJECT_DIR")

    # ---- multi-adapter -----------------------------------------------

    def test_install_three_adapters_independent(self):
        self._install("cursor")
        self._install("claude-code")
        self._install("pi")
        doc = state_mod.load(self.target)
        self.assertEqual(
            sorted(doc["adapters"].keys()),
            sorted(["cursor", "claude-code", "pi"]),
        )
        # pi has skills_link
        self.assertIn("skills_link", doc["adapters"]["pi"])
        # claude-code has primitive
        self.assertEqual(
            doc["adapters"]["claude-code"]["brain_root_primitive"],
            "$CLAUDE_PROJECT_DIR",
        )
        # cursor is simple
        self.assertEqual(
            doc["adapters"]["cursor"]["files_written"],
            [".cursor/rules/agentic-stack.mdc"],
        )

    # ---- pi skills_link + from_stack ---------------------------------

    def test_pi_install_creates_symlink_and_syncs_hook(self):
        self._install("pi")
        # AGENTS.md
        self.assertTrue((self.target / "AGENTS.md").is_file())
        # memory-hook.ts (adapter-local file)
        self.assertTrue((self.target / ".pi" / "extensions" / "memory-hook.ts").is_file())
        # pi_post_tool.py (from_stack: true — synced from agentic-stack source)
        self.assertTrue(
            (self.target / ".agent" / "harness" / "hooks" / "pi_post_tool.py").is_file(),
            "from_stack file pi_post_tool.py was not synced",
        )
        # skills symlink
        skills_dst = self.target / ".pi" / "skills"
        self.assertTrue(skills_dst.is_symlink() or skills_dst.is_dir())
        if skills_dst.is_symlink():
            self.assertTrue(skills_dst.resolve().is_dir())

    # ---- doctor green path -------------------------------------------

    def test_doctor_all_green_after_fresh_install(self):
        self._install("cursor")
        self._install("claude-code")
        rc = doctor_mod.audit(self.target, log=lambda _: None)
        self.assertEqual(rc, 0, "doctor returned non-zero on a fresh install")

    # ---- doctor red on missing file ----------------------------------

    def test_doctor_red_when_tracked_file_deleted(self):
        self._install("cursor")
        # Delete the file cursor installed
        (self.target / ".cursor" / "rules" / "agentic-stack.mdc").unlink()
        rc = doctor_mod.audit(self.target, log=lambda _: None)
        self.assertEqual(rc, 1, "doctor should return 1 when a tracked file is missing")

    # ---- remove --yes is idempotent and clean ------------------------

    def test_remove_deletes_files_and_updates_install_json(self):
        self._install("cursor")
        rc = remove_mod.remove(self.target, "cursor", yes=True, log=lambda _: None)
        self.assertEqual(rc, 0)
        self.assertFalse(
            (self.target / ".cursor" / "rules" / "agentic-stack.mdc").exists()
        )
        doc = state_mod.load(self.target)
        self.assertNotIn("cursor", doc["adapters"])

    def test_remove_unknown_adapter_returns_nonzero(self):
        # No install.json yet
        rc = remove_mod.remove(self.target, "cursor", yes=True, log=lambda _: None)
        self.assertEqual(rc, 1)

    # ---- idempotency -------------------------------------------------

    def test_install_twice_no_dup_state(self):
        self._install("cursor")
        self._install("cursor")
        doc = state_mod.load(self.target)
        # Single entry, replaced not appended.
        self.assertEqual(list(doc["adapters"].keys()), ["cursor"])


if __name__ == "__main__":
    unittest.main(verbosity=2)

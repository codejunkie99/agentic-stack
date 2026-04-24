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


def _concurrent_upsert_worker(args):
    """Module-level worker for the concurrency test (Py3.14 spawn needs picklable)."""
    target, idx = args
    sys.path.insert(0, str(REPO_ROOT))
    from harness_manager import state as st
    st.upsert_adapter(target, f"a{idx:02d}", {"installed_at": "x"}, "0.9.0")


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

    # ---- regression tests from codex pre-PR review --------------------

    def test_remove_preserves_pre_existing_user_files(self):
        """Codex P1: files_overwritten must NOT be deleted by remove."""
        # Simulate a user who already had .claude/settings.json with their
        # own content — install (overwrite policy) replaces it; remove
        # MUST NOT delete it (the user's original is gone, but neither
        # should we delete what we left).
        custom_settings = self.target / ".claude" / "settings.json"
        custom_settings.parent.mkdir(parents=True, exist_ok=True)
        custom_settings.write_text('{"user": "custom"}', encoding="utf-8")

        self._install("claude-code")
        # claude-code's settings.json has merge_policy: overwrite, so
        # it replaced the file. Track it as files_overwritten, NOT files_written.
        doc = state_mod.load(self.target)
        entry = doc["adapters"]["claude-code"]
        self.assertIn(".claude/settings.json", entry["files_overwritten"])
        self.assertNotIn(".claude/settings.json", entry["files_written"])

        # Now remove. The pre-existing file should NOT be deleted.
        rc = remove_mod.remove(self.target, "claude-code", yes=True, log=lambda _: None)
        self.assertEqual(rc, 0)
        self.assertTrue(
            custom_settings.exists(),
            "remove deleted .claude/settings.json which pre-existed install — "
            "this destroys user data",
        )

    def test_merge_alert_recorded_in_install_json(self):
        """Codex P1: merge-alerted adapters must record they need manual merge."""
        # Plant a pre-existing AGENTS.md without .agent/ reference (e.g. user's
        # own Aider AGENTS.md). Install openclaw — its AGENTS.md uses
        # merge_or_alert, so it leaves the existing alone but records the alert.
        existing_agents = self.target / "AGENTS.md"
        existing_agents.write_text(
            "# my own AGENTS.md\nSome unrelated rules.\n", encoding="utf-8"
        )
        self._install("openclaw")
        doc = state_mod.load(self.target)
        entry = doc["adapters"]["openclaw"]
        # The user's AGENTS.md was preserved, AND we recorded the alert.
        self.assertIn("AGENTS.md", entry["files_alerted"])
        self.assertNotIn("AGENTS.md", entry["files_written"])

    def test_doctor_yellow_when_merge_alert_unresolved(self):
        """Codex P1: doctor must flag yellow if merge_alert hasn't been resolved."""
        existing_agents = self.target / "AGENTS.md"
        existing_agents.write_text(
            "# my own AGENTS.md\nNo .agent reference here.\n", encoding="utf-8"
        )
        self._install("openclaw")
        # Doctor should return 0 (yellow is not red), but the audit text
        # should mention the unresolved merge.
        log_lines = []
        rc = doctor_mod.audit(self.target, log=log_lines.append)
        self.assertEqual(rc, 0)  # yellow ≠ red
        all_text = "\n".join(log_lines)
        self.assertIn("merge required", all_text)
        self.assertIn("AGENTS.md", all_text)

    def test_doctor_green_when_merge_alert_resolved(self):
        """Once user merges the snippet (file references .agent/), doctor goes green."""
        existing_agents = self.target / "AGENTS.md"
        existing_agents.write_text(
            "# my own AGENTS.md\nNo reference yet.\n", encoding="utf-8"
        )
        self._install("openclaw")
        # User merges the snippet — append a .agent/ reference.
        existing_agents.write_text(
            existing_agents.read_text() + "\nSee .agent/AGENTS.md for the brain.\n",
            encoding="utf-8",
        )
        log_lines = []
        rc = doctor_mod.audit(self.target, log=log_lines.append)
        self.assertEqual(rc, 0)
        all_text = "\n".join(log_lines)
        self.assertNotIn("merge required", all_text)

    def test_openclaw_agent_name_matches_legacy_cksum(self):
        """Codex P1: openclaw agent name must match the bash cksum algorithm.

        Pre-v0.9.0 install.sh derived the suffix as:
          printf '%s' "$ABS" | cksum | awk '{print $1}'  → suffix = N % 1000000
        v0.9.0 must produce the SAME name for the SAME path, otherwise upgrade
        installs create duplicate openclaw agents.
        """
        from harness_manager.post_install import _openclaw_agent_name, _posix_cksum
        # Spot check: an absolute path, what the bash would have produced.
        # Hand-verify against `printf '%s' '/Users/foo/myproject' | cksum | awk '{print $1}'`
        # → 4089408017, mod 1_000_000 → 408017, padded → "408017"
        # Basename "myproject" lowercased → "myproject"
        # Final agent name → "myproject-408017"
        self.assertEqual(
            _openclaw_agent_name("/Users/foo/myproject"),
            "myproject-408017",
            "openclaw agent name diverged from legacy cksum-based formula",
        )
        # Also verify the cksum primitive itself matches POSIX cksum(1).
        self.assertEqual(_posix_cksum(b"/Users/foo/myproject"), 4089408017)

    def test_openclaw_sanitizer_matches_legacy_bash(self):
        """Codex P2: sanitizer must use ASCII-only [a-z0-9._-] and regex collapse.

        The pre-v0.9.0 bash was:
          tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '-' | sed 's/-\\{2,\\}/-/g; s/^-//; s/-$//'

        Edge cases that broke the early Python implementation:
        - Non-ASCII letters (str.isalnum() preserves them; tr does not)
        - Runs of dashes (str.replace("--","-") is single-pass; sed regex collapses fully)
        """
        from harness_manager.post_install import _openclaw_agent_name
        # Hand-derived expectations, lowercased basename + cksum-based suffix.
        # We only assert the basename portion (suffix is path-dependent).
        # Non-ASCII test: "café" → bash would have produced "caf-" (ç → -)
        # and the sanitizer would strip the trailing dash → "caf".
        name = _openclaw_agent_name("/tmp/café")
        self.assertTrue(
            name.startswith("caf-"),
            f"non-ASCII char ç should sanitize to '-' (then stripped or kept), "
            f"got name '{name}'",
        )
        self.assertNotIn("é", name)  # accents must be gone, not preserved
        # Run-of-dashes test: "a----b" basename
        name = _openclaw_agent_name("/tmp/a----b")
        self.assertTrue(
            name.startswith("a-b-"),
            f"runs of dashes should collapse to single '-', got name '{name}'",
        )

    def test_doctor_yellow_when_openclaw_register_was_skipped(self):
        """Codex P1: doctor must NOT report red for adapters whose register
        post_install was binary_missing at install time. The fallback hint
        is the documented behavior, not a bug.
        """
        # Install openclaw — but openclaw binary is not in PATH on this box,
        # so post_install will record status: binary_missing.
        # (We rely on the test environment NOT having openclaw on PATH,
        # OR the install simulating it — for this assertion, we just check
        # that whatever status was recorded, doctor handles all branches
        # correctly.)
        self._install("openclaw")
        doc = state_mod.load(self.target)
        entry = doc["adapters"]["openclaw"]
        results = entry.get("post_install_results", [])
        if not results:
            self.skipTest("openclaw didn't record post_install_results — skip")
        register = next(
            (r for r in results if r.get("action") == "openclaw_register_workspace"),
            None,
        )
        if register is None or register.get("status") in ("ok", "already_exists"):
            self.skipTest("openclaw was actually registered ok — different code path")
        # Status is binary_missing or failed. Doctor must NOT mark red just
        # because the agent isn't in ~/.openclaw/openclaw.json — the install
        # never registered it, so absence is expected.
        log_lines = []
        rc = doctor_mod.audit(self.target, log=log_lines.append)
        all_text = "\n".join(log_lines)
        # Yellow allowed (rc=0), red is the bug we're guarding against.
        self.assertEqual(
            rc, 0,
            f"doctor should not return red when openclaw registration was "
            f"skipped at install time. log:\n{all_text}",
        )

    def test_reinstall_preserves_installer_ownership(self):
        """Codex P1: re-installing an adapter must NOT reclassify our own files
        as user-owned, otherwise remove leaves them behind on upgrade.
        """
        # First install: we create CLAUDE.md fresh.
        self._install("claude-code")
        doc1 = state_mod.load(self.target)
        self.assertIn("CLAUDE.md", doc1["adapters"]["claude-code"]["files_written"])

        # Second install: CLAUDE.md exists (we wrote it), but we still own it.
        # The re-install should NOT move it to files_overwritten.
        self._install("claude-code")
        doc2 = state_mod.load(self.target)
        entry = doc2["adapters"]["claude-code"]
        self.assertIn(
            "CLAUDE.md",
            entry["files_written"],
            "reinstall reclassified installer-owned CLAUDE.md as user-owned; "
            "remove will now leave it behind",
        )
        self.assertNotIn("CLAUDE.md", entry["files_overwritten"])

        # Sanity: remove on the re-installed adapter still cleans up our files.
        rc = remove_mod.remove(self.target, "claude-code", yes=True, log=lambda _: None)
        self.assertEqual(rc, 0)
        self.assertFalse((self.target / "CLAUDE.md").exists())

    def test_remove_does_not_reverse_skipped_post_install(self):
        """Codex P2: remove must NOT reverse post_install actions that never
        succeeded at install time. Reversing a never-completed openclaw
        registration could delete a manually-created agent.
        """
        # Construct an install.json directly with a synthetic post_install
        # result that recorded binary_missing. Then run remove with --yes
        # and verify the reverse list is empty (no openclaw subprocess call).
        from harness_manager import post_install as pi_mod

        # Plant a fake adapter entry where openclaw_register_workspace was
        # recorded as binary_missing.
        state_mod.upsert_adapter(
            self.target,
            "openclaw",
            {
                "installed_at": "x",
                "files_written": [],
                "files_overwritten": [],
                "files_alerted": [],
                "file_results": [],
                "post_install_results": [
                    {
                        "action": "openclaw_register_workspace",
                        "status": "binary_missing",
                        "agent_name": "would-be-agent-name",
                    }
                ],
            },
            "0.9.0",
        )

        # Spy on pi_mod.reverse to ensure it is NOT called for the
        # binary_missing entry.
        original_reverse = pi_mod.reverse
        called_with = []
        def _spy(action, target_root, **kwargs):
            called_with.append(action)
            return original_reverse(action, target_root, **kwargs)
        pi_mod.reverse = _spy
        try:
            rc = remove_mod.remove(self.target, "openclaw", yes=True, log=lambda _: None)
            self.assertEqual(rc, 0)
            self.assertEqual(
                called_with, [],
                f"remove called reverse() for an unsuccessful post_install: {called_with}. "
                f"This could delete a manually-created openclaw agent."
            )
        finally:
            pi_mod.reverse = original_reverse

    def test_remove_preserves_pre_existing_skills_link_dir(self):
        """Codex P1: if user already had .agents/skills/ before installing
        codex, remove must NOT delete it (we adopted, didn't create).
        """
        # Plant a pre-existing user-owned .agents/skills directory with
        # custom content.
        user_skills = self.target / ".agents" / "skills"
        user_skills.mkdir(parents=True, exist_ok=True)
        (user_skills / "user-skill").mkdir()
        (user_skills / "user-skill" / "SKILL.md").write_text(
            "---\nname: user-skill\ndescription: my own\n---\n", encoding="utf-8"
        )

        # Install codex — adopts the existing dir via rsync.
        self._install("codex")
        doc = state_mod.load(self.target)
        entry = doc["adapters"]["codex"]
        self.assertTrue(
            entry.get("skills_link_pre_existed"),
            "skills_link_pre_existed should be True when target dir was present pre-install",
        )

        # Remove codex. The skills_link dst should NOT be deleted.
        rc = remove_mod.remove(self.target, "codex", yes=True, log=lambda _: None)
        self.assertEqual(rc, 0)
        self.assertTrue(
            user_skills.exists(),
            "remove deleted .agents/skills/ which pre-existed install — destroys user data",
        )

    def test_remove_deletes_installer_created_skills_link(self):
        """Sanity check: when WE created the skills_link, remove DOES delete it."""
        # Fresh project, no pre-existing .agents/skills.
        self._install("codex")
        doc = state_mod.load(self.target)
        entry = doc["adapters"]["codex"]
        self.assertFalse(
            entry.get("skills_link_pre_existed", False),
            "skills_link_pre_existed should be False on fresh install",
        )
        rc = remove_mod.remove(self.target, "codex", yes=True, log=lambda _: None)
        self.assertEqual(rc, 0)
        skills_dst = self.target / ".agents" / "skills"
        self.assertFalse(
            skills_dst.exists() and not skills_dst.is_symlink(),
            "remove failed to clean up installer-created skills_link",
        )

    def test_openclaw_reverse_uses_stored_agent_name_not_recompute(self):
        """Codex P2: openclaw reverse must use the agent_name recorded at
        install time, not recompute from current target_root. Otherwise a
        renamed/moved project tries to remove the wrong agent and orphans
        the original.
        """
        from harness_manager import post_install as pi_mod
        # Plant an install.json with a synthetic openclaw entry whose
        # recorded agent_name does NOT match what _openclaw_agent_name
        # would compute now (simulates: project was renamed after install).
        recorded_name = "old-name-123456"
        state_mod.upsert_adapter(
            self.target,
            "openclaw",
            {
                "installed_at": "x",
                "files_written": [],
                "files_overwritten": [],
                "files_alerted": [],
                "file_results": [],
                "post_install_results": [
                    {
                        "action": "openclaw_register_workspace",
                        "status": "ok",
                        "agent_name": recorded_name,
                    }
                ],
            },
            "0.9.0",
        )

        # Spy on what name reverse() actually receives.
        seen = {"agent_name": None}
        original = pi_mod.openclaw_unregister_workspace
        def _spy(target_root, **kwargs):
            seen["agent_name"] = kwargs.get("agent_name") or pi_mod._openclaw_agent_name(target_root)
            # Don't actually invoke openclaw — just record what would be called.
            return {"action": "openclaw_unregister_workspace", "status": "ok",
                    "agent_name": seen["agent_name"]}
        pi_mod.ACTIONS["openclaw_register_workspace"] = (
            pi_mod.openclaw_register_workspace, _spy
        )
        try:
            rc = remove_mod.remove(self.target, "openclaw", yes=True, log=lambda _: None)
            self.assertEqual(rc, 0)
            self.assertEqual(
                seen["agent_name"],
                recorded_name,
                f"remove called openclaw unregister with '{seen['agent_name']}' "
                f"but install.json recorded '{recorded_name}'. A renamed project "
                f"would orphan the original openclaw agent.",
            )
        finally:
            pi_mod.ACTIONS["openclaw_register_workspace"] = (
                pi_mod.openclaw_register_workspace, original
            )

    def test_doctor_synthesis_populates_files_written(self):
        """Codex P1: doctor's first-run synthesis on a pre-v0.9 project must
        seed files_written from the adapter manifest, otherwise:
          - remove becomes a no-op (files stay on disk forever)
          - subsequent add reclassifies our own files as user-owned
        """
        # Simulate a pre-v0.9 install: drop the files the old install.sh
        # would have written, but no install.json. Brain triple
        # (memory/skills/protocols) is required so state.brain_present
        # returns True — doctor's synthesis gates on that to avoid
        # writing bogus install.json in random repos that happen to
        # contain a common filename.
        (self.target / ".cursor" / "rules").mkdir(parents=True)
        (self.target / ".cursor" / "rules" / "agentic-stack.mdc").write_text("rules", encoding="utf-8")
        (self.target / ".agent").mkdir()
        (self.target / ".agent" / "AGENTS.md").write_text("brain", encoding="utf-8")
        (self.target / ".agent" / "memory").mkdir()
        (self.target / ".agent" / "skills").mkdir()
        (self.target / ".agent" / "protocols").mkdir()

        self.assertIsNone(state_mod.load(self.target), "no install.json yet")

        # Synthesize via doctor's pre-v0.9 path. We bypass the input() prompt
        # by calling _audit_pre_v090 directly with stdin not-a-tty (the
        # function honors that — but we need to sim the Y answer). Easier:
        # invoke through a monkey-patched input.
        import builtins
        from unittest.mock import patch
        orig_input = builtins.input
        builtins.input = lambda *a, **kw: "y"
        try:
            with patch("sys.stdin.isatty", return_value=True):
                rc = doctor_mod.audit(self.target, log=lambda _: None)
        finally:
            builtins.input = orig_input
        self.assertEqual(rc, 0)

        doc = state_mod.load(self.target)
        self.assertIsNotNone(doc, "doctor failed to synthesize install.json")
        self.assertIn("cursor", doc["adapters"])
        cursor_entry = doc["adapters"]["cursor"]
        # Conservative migration: detected file goes to files_overwritten
        # (we don't know whether it pre-existed user content). User can
        # re-install for strict ownership tracking.
        self.assertIn(
            ".cursor/rules/agentic-stack.mdc",
            cursor_entry["files_overwritten"],
            "synthesis must populate files_overwritten conservatively so "
            "remove never destroys content we can't prove we created",
        )
        self.assertTrue(cursor_entry.get("_synthesized"))

    def test_doctor_synthesis_skips_merge_or_alert_files(self):
        """Synthesis must NOT claim ownership of merge_or_alert files
        (e.g., AGENTS.md) — those may be user-owned content that the old
        install.sh deliberately preserved.
        """
        # Pre-v0.9 codex install: AGENTS.md exists (was the user's own file
        # the old install.sh skipped); .agents/skills exists (old install.sh
        # always created this).
        self.target.mkdir(parents=True, exist_ok=True)
        (self.target / "AGENTS.md").write_text("user's own AGENTS.md", encoding="utf-8")
        (self.target / ".agents" / "skills").mkdir(parents=True)
        (self.target / ".agent").mkdir(exist_ok=True)
        (self.target / ".agent" / "AGENTS.md").write_text("brain", encoding="utf-8")
        (self.target / ".agent" / "memory").mkdir()
        (self.target / ".agent" / "skills").mkdir()
        (self.target / ".agent" / "protocols").mkdir()

        import builtins
        from unittest.mock import patch
        orig_input = builtins.input
        builtins.input = lambda *a, **kw: "y"
        try:
            with patch("sys.stdin.isatty", return_value=True):
                rc = doctor_mod.audit(self.target, log=lambda _: None)
        finally:
            builtins.input = orig_input
        self.assertEqual(rc, 0)

        doc = state_mod.load(self.target)
        codex_entry = doc["adapters"].get("codex")
        if codex_entry is None:
            self.skipTest("detection didn't pick up codex from .agents/skills alone")
        # AGENTS.md is merge_or_alert in codex's manifest → must be in
        # files_alerted, NOT files_written. Otherwise remove would delete
        # the user's AGENTS.md.
        self.assertNotIn("AGENTS.md", codex_entry["files_written"])
        # And the skills_link should be claimed (old install.sh always
        # created it).
        self.assertIn("skills_link", codex_entry)

    def test_openclaw_agent_name_platform_specific(self):
        """Codex P2: openclaw agent name uses cksum on POSIX, SHA1 on Windows.

        Both legacy install scripts (install.sh + install.ps1) used
        different hash functions; we must match each per-platform to keep
        upgrade installs from registering a second agent.
        """
        from harness_manager.post_install import _openclaw_agent_name
        import platform as _plat

        name = _openclaw_agent_name("/Users/foo/myproject")
        if _plat.system() == "Windows":
            # SHA1[:6] hex
            self.assertRegex(
                name,
                r"^myproject-[0-9a-f]{6}$",
                f"on Windows, agent name suffix should be 6 hex chars (SHA1[:6]), got '{name}'",
            )
        else:
            # cksum mod 1_000_000, zero-padded 6 decimal digits
            self.assertRegex(
                name,
                r"^myproject-\d{6}$",
                f"on POSIX, agent name suffix should be 6 decimal digits (cksum), got '{name}'",
            )
            # Hand-verified pre-v0.9 install.sh value
            self.assertEqual(name, "myproject-408017")

    def test_remove_preserves_shared_agents_md(self):
        """Codex P1: a multi-adapter repo where another adapter still
        depends on AGENTS.md must NOT see it deleted by remove.
        """
        # Install codex first — writes AGENTS.md (merge_or_alert; we create
        # it because target is fresh).
        self._install("codex")
        doc = state_mod.load(self.target)
        codex_entry = doc["adapters"]["codex"]
        self.assertIn("AGENTS.md", codex_entry["files_written"])

        # Add hermes — its AGENTS.md merge_policy is merge_or_alert; existing
        # AGENTS.md already references .agent/ (codex's content) → left_alone.
        self._install("hermes")
        doc = state_mod.load(self.target)
        hermes_entry = doc["adapters"]["hermes"]
        # hermes recorded AGENTS.md in file_results as left_alone, NOT in files_written.
        hermes_results = {r["dst"]: r["result"] for r in hermes_entry["file_results"]}
        self.assertEqual(hermes_results.get("AGENTS.md"), "left_alone")

        # Now remove codex. AGENTS.md is in codex's files_written, but hermes
        # depends on it. The shared check must preserve it.
        rc = remove_mod.remove(self.target, "codex", yes=True, log=lambda _: None)
        self.assertEqual(rc, 0)
        self.assertTrue(
            (self.target / "AGENTS.md").exists(),
            "remove deleted AGENTS.md while another adapter (hermes) still depends on it",
        )

    def test_state_lock_prevents_lost_update(self):
        """Codex P2: concurrent upsert_adapter must not lose entries.

        Spawn N processes that each upsert a distinct adapter. With the lock
        held around the read-modify-write, all N entries land in install.json.
        Without the lock (the bug codex caught), some are lost.
        """
        import multiprocessing as mp

        # Need an installed brain for state.upsert_adapter to write under.
        self._install("cursor")
        # Pre-clean: collapse to a known starting state.
        doc = state_mod.load(self.target)
        doc["adapters"] = {}
        state_mod.save(self.target, doc)

        n = 20
        with mp.Pool(n) as pool:
            pool.map(_concurrent_upsert_worker, [(str(self.target), i) for i in range(n)])

        doc = state_mod.load(self.target)
        names = sorted(doc["adapters"].keys())
        self.assertEqual(
            len(names),
            n,
            f"lost-update under concurrency: expected {n} adapters, got {len(names)}: {names}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

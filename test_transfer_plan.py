import unittest
from pathlib import Path

from harness_manager.transfer_plan import (
    DEFAULT_SCOPES,
    VALID_TARGETS,
    build_plan,
    normalize_scopes,
    normalize_targets,
)


ROOT = Path(__file__).resolve().parent


class TransferPlanTest(unittest.TestCase):
    def test_detects_codex_curl_transfer_defaults(self):
        plan = build_plan("move my memory into Codex as a curl command", ROOT)

        self.assertEqual(plan.targets, ("codex",))
        self.assertEqual(plan.operation, "generate-curl")
        self.assertEqual(
            plan.scopes,
            ("preferences", "accepted_lessons", "skills", "working", "episodic", "candidates"),
        )
        self.assertEqual(plan.sensitive_scopes, ("working", "episodic", "candidates"))
        self.assertIn("AGENTS.md", [a.dst for a in plan.adapter_actions])
        self.assertIn(".agents/skills", [a.dst for a in plan.adapter_actions])

    def test_detects_multiple_targets_and_apply_here(self):
        plan = build_plan("install this in Cursor and Windsurf here", ROOT)

        self.assertEqual(plan.targets, ("cursor", "windsurf"))
        self.assertEqual(plan.operation, "apply-here")
        self.assertIn(".cursor/rules/agentic-stack.mdc", [a.dst for a in plan.adapter_actions])
        self.assertIn(".windsurfrules", [a.dst for a in plan.adapter_actions])

    def test_all_target_expands_to_every_supported_target(self):
        self.assertEqual(normalize_targets(["all"]), tuple(VALID_TARGETS))

    def test_unknown_target_defaults_to_all_with_warning(self):
        plan = build_plan("transfer my memory", ROOT)

        self.assertEqual(plan.targets, tuple(VALID_TARGETS))
        self.assertIn("No target detected", plan.warnings[0])

    def test_sensitive_scopes_are_explicit_and_warned(self):
        scopes = normalize_scopes(["preferences", "episodic", "working"])
        plan = build_plan("move episodic logs and working memory into terminal", ROOT, scopes=scopes)

        self.assertEqual(plan.targets, ("terminal",))
        self.assertEqual(plan.scopes, ("preferences", "working", "episodic"))
        self.assertEqual(plan.sensitive_scopes, ("working", "episodic"))
        self.assertTrue(any("Sensitive scopes selected" in warning for warning in plan.warnings))

    def test_terminal_preview_is_agents_md_only(self):
        plan = build_plan("transfer preferences to a plain terminal", ROOT)

        self.assertEqual(plan.targets, ("terminal",))
        self.assertEqual([a.dst for a in plan.adapter_actions], ["AGENTS.md"])
        self.assertEqual(plan.adapter_actions[0].merge_policy, "merge_or_alert")

    def test_history_alias_selects_episodic_scope(self):
        plan = build_plan("move history into codex", ROOT)

        self.assertEqual(plan.targets, ("codex",))
        self.assertIn("episodic", plan.scopes)
        self.assertEqual(plan.sensitive_scopes, ("episodic",))


if __name__ == "__main__":
    unittest.main()

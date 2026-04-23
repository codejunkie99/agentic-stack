"""Validate every adapters/<name>/adapter.json against the schema.

Run: python3 -m unittest tests.test_adapter_manifests
Or:  python3 tests/test_adapter_manifests.py
"""
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from harness_manager.schema import (  # noqa: E402
    ManifestError,
    discover_all,
    validate_dict,
)


class TestSchemaValidation(unittest.TestCase):
    """Programmatic checks: handcrafted good and bad manifests."""

    def _good_minimal(self) -> dict:
        return {
            "name": "minimal",
            "description": "minimal adapter for testing",
            "files": [
                {"src": "AGENTS.md", "dst": "AGENTS.md"}
            ],
        }

    def test_minimal_manifest_validates(self):
        m = self._good_minimal()
        self.assertEqual(validate_dict(m, "test"), m)

    def test_full_manifest_validates(self):
        m = {
            "name": "claude-code",
            "description": "Claude Code with hooks",
            "brain_root_primitive": "$CLAUDE_PROJECT_DIR",
            "files": [
                {
                    "src": "settings.json",
                    "dst": ".claude/settings.json",
                    "merge_policy": "overwrite",
                    "substitute": True,
                },
                {
                    "src": "CLAUDE.md",
                    "dst": "CLAUDE.md",
                    "merge_policy": "overwrite",
                },
            ],
            "skills_link": {
                "target": ".agent/skills",
                "dst": ".pi/skills",
                "fallback": "rsync_with_delete",
            },
            "post_install": ["openclaw_register_workspace"],
        }
        self.assertEqual(validate_dict(m, "test")["name"], "claude-code")

    def test_from_stack_field_accepted(self):
        m = self._good_minimal()
        m["files"][0]["from_stack"] = True
        validate_dict(m, "test")

    def test_missing_required_name(self):
        m = self._good_minimal()
        del m["name"]
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("missing required field 'name'", str(ctx.exception))

    def test_missing_required_files(self):
        m = self._good_minimal()
        del m["files"]
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("missing required field 'files'", str(ctx.exception))

    def test_empty_files_list_rejected(self):
        m = self._good_minimal()
        m["files"] = []
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("at least one entry", str(ctx.exception))

    def test_path_traversal_rejected(self):
        m = self._good_minimal()
        m["files"][0]["src"] = "../etc/passwd"
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("'..' path components not allowed", str(ctx.exception))

    def test_absolute_path_rejected(self):
        m = self._good_minimal()
        m["files"][0]["dst"] = "/etc/passwd"
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("absolute paths not allowed", str(ctx.exception))

    def test_invalid_merge_policy(self):
        m = self._good_minimal()
        m["files"][0]["merge_policy"] = "yolo"
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("merge_policy", str(ctx.exception))

    def test_unknown_post_install_action(self):
        m = self._good_minimal()
        m["post_install"] = ["wipe_disk"]
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("unknown action 'wipe_disk'", str(ctx.exception))

    def test_unknown_top_level_field_rejected(self):
        m = self._good_minimal()
        m["secret_handshake"] = True
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("unknown top-level field", str(ctx.exception))

    def test_brain_root_primitive_must_start_with_dollar(self):
        m = self._good_minimal()
        m["brain_root_primitive"] = "CLAUDE_PROJECT_DIR"  # missing $
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("must be a shell env var", str(ctx.exception))

    def test_invalid_name_with_spaces(self):
        m = self._good_minimal()
        m["name"] = "has spaces"
        with self.assertRaises(ManifestError) as ctx:
            validate_dict(m, "test")
        self.assertIn("alphanumeric", str(ctx.exception))


class TestRealAdapterManifests(unittest.TestCase):
    """Walks adapters/ and validates every adapter.json that exists.

    During the migration window, adapters without adapter.json are
    silently skipped — discover_all() doesn't require all 10 adapters
    to be migrated. After full migration, this test will naturally
    cover all 10.
    """

    def test_all_present_adapter_jsons_validate(self):
        manifests = discover_all(REPO_ROOT)
        # Don't fail if there are zero migrated adapters yet — that's
        # a valid intermediate state during Step 2 of the implementation.
        for name, manifest in manifests:
            self.assertEqual(
                manifest["name"],
                name,
                f"adapter '{name}' has manifest name='{manifest['name']}'; mismatch",
            )

    def test_discover_returns_sorted(self):
        manifests = discover_all(REPO_ROOT)
        names = [n for n, _ in manifests]
        self.assertEqual(
            names, sorted(names), "discover_all should return sorted by adapter name"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)

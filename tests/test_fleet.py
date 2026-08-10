import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from harness_manager import doctor, fleet


ROOT = Path(__file__).resolve().parents[1]


class FleetTest(unittest.TestCase):
    def write_manifest(self, root: Path, workspaces: list[dict], exclusions=None) -> Path:
        path = root / "agentic-stack.fleet.json"
        path.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "profile": "okai",
                    "fleetRoot": ".",
                    "workspaces": workspaces,
                    "exclusions": exclusions or [],
                }
            ),
            encoding="utf-8",
        )
        return path

    def managed_workspace(self, root: Path, name: str = "app") -> Path:
        workspace = root / name
        (workspace / ".git").mkdir(parents=True)
        agent = workspace / ".agent"
        (agent / "memory" / "personal").mkdir(parents=True)
        (agent / "memory" / "semantic").mkdir(parents=True)
        (agent / "memory" / "episodic").mkdir(parents=True)
        (agent / "memory" / "working").mkdir(parents=True)
        (agent / "skills").mkdir(parents=True)
        (agent / "protocols").mkdir(parents=True)
        (agent / "tools").mkdir(parents=True)
        (agent / "AGENTS.md").write_text("# Local brain\n", encoding="utf-8")
        (agent / "install.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "agentic_stack_version": "old",
                    "adapters": {},
                }
            ),
            encoding="utf-8",
        )
        (agent / "skills" / "_manifest.jsonl").write_text("", encoding="utf-8")
        (agent / "protocols" / "project-local.md").write_text(
            "# Preserve me\n", encoding="utf-8"
        )
        return workspace

    def managed_row(self) -> dict:
        return {
            "id": "sample-app",
            "path": "app",
            "mode": "managed",
            "displayName": "Sample App",
            "repositories": ["app"],
            "adapters": ["codex"],
            "rationale": "",
        }

    def test_manifest_rejects_an_unassigned_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.managed_workspace(root)
            (root / "orphan" / ".git").mkdir(parents=True)
            manifest_path = self.write_manifest(root, [self.managed_row()])

            _manifest, errors = fleet.load_manifest(manifest_path)

            self.assertIn("Git repository is not assigned or excluded: orphan", errors)
            self.assertIn("top-level directory is not a workspace or exclusion: orphan", errors)

    def test_manifest_rejects_two_owners_for_one_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.managed_workspace(root)
            second = {
                "id": "second",
                "path": "app/sub",
                "mode": "pending",
                "displayName": "Second",
                "repositories": ["app"],
                "adapters": [],
                "rationale": "waiting",
            }
            (root / "app" / "sub").mkdir()
            manifest_path = self.write_manifest(root, [self.managed_row(), second])

            _manifest, errors = fleet.load_manifest(manifest_path)

            self.assertTrue(any("multiple workspace owners" in error for error in errors), errors)

    def test_brain_symlinks_resolve_to_one_workspace_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.managed_workspace(root)
            child = workspace / "child"
            (child / ".git").mkdir(parents=True)
            (child / ".agent").symlink_to("../.agent")
            row = self.managed_row()
            row["repositories"] = ["app", "app/child"]
            manifest_path = self.write_manifest(root, [row])

            _manifest, errors = fleet.load_manifest(manifest_path)

            self.assertEqual(errors, [])
            self.assertEqual(fleet.discover_brain_roots(root), [workspace])

    def test_upgrade_is_verified_idempotent_and_preserves_local_protocol(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.managed_workspace(root)
            manifest_path = self.write_manifest(root, [self.managed_row()])
            manifest, errors = fleet.load_manifest(manifest_path)
            self.assertEqual(errors, [])
            self.assertIsNotNone(manifest)

            result = fleet.upgrade_fleet(manifest, ROOT, dry_run=False, yes=True, log=lambda _line: None)

            self.assertEqual(result, 0)
            self.assertEqual(
                (workspace / ".agent" / "protocols" / "project-local.md").read_text(encoding="utf-8"),
                "# Preserve me\n",
            )
            profile = json.loads(
                (workspace / ".agent" / "config" / "profile.json").read_text(encoding="utf-8")
            )
            self.assertEqual(profile["profile"], "okai")
            self.assertEqual(profile["projectId"], "sample-app")
            status, lines = doctor._audit_portable_brain(workspace)
            self.assertEqual(status, doctor.GREEN, lines)

            messages = []
            second = fleet.upgrade_fleet(
                manifest, ROOT, dry_run=True, yes=False, log=messages.append
            )
            self.assertEqual(second, 0)
            self.assertTrue(any("would update 0 managed file(s)" in line for line in messages), messages)

    def test_failed_verification_rolls_back_every_touched_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            workspace = self.managed_workspace(root)
            manifest_path = self.write_manifest(root, [self.managed_row()])
            manifest, errors = fleet.load_manifest(manifest_path)
            self.assertEqual(errors, [])
            original_agents = (workspace / ".agent" / "AGENTS.md").read_bytes()

            with mock.patch.object(
                fleet.doctor,
                "_audit_portable_brain",
                return_value=(doctor.RED, ["forced failure"]),
            ):
                result = fleet.upgrade_fleet(
                    manifest, ROOT, dry_run=False, yes=True, log=lambda _line: None
                )

            self.assertEqual(result, 1)
            self.assertEqual((workspace / ".agent" / "AGENTS.md").read_bytes(), original_agents)
            self.assertFalse((workspace / ".agent" / "config" / "profile.json").exists())
            self.assertFalse(
                (workspace / ".agent" / "tools" / "validate_extracted_artifacts.py").exists()
            )


if __name__ == "__main__":
    unittest.main()

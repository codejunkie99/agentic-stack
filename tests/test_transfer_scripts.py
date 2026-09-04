import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TransferScriptsTest(unittest.TestCase):
    def test_bootstrap_scripts_exist(self):
        sh = ROOT / "scripts" / "import-transfer.sh"
        ps1 = ROOT / "scripts" / "import-transfer.ps1"

        self.assertTrue(sh.exists())
        self.assertTrue(ps1.exists())
        self.assertIn("agentic-stack transfer import", sh.read_text(encoding="utf-8"))
        self.assertIn("transfer import", ps1.read_text(encoding="utf-8"))

    def test_windsurf_manifest_installs_modern_and_legacy_rules(self):
        manifest = json.loads((ROOT / "adapters" / "windsurf" / "adapter.json").read_text(encoding="utf-8"))
        dsts = {entry["dst"] for entry in manifest["files"]}

        self.assertIn(".windsurf/rules/agentic-stack.md", dsts)
        self.assertIn(".windsurfrules", dsts)
        self.assertTrue((ROOT / "adapters" / "windsurf" / ".windsurf" / "rules" / "agentic-stack.md").exists())

    def test_cursor_manifest_installs_cavecrew_stack(self):
        from harness_manager import install, schema

        adapter_dir = ROOT / "adapters" / "cursor"
        manifest = schema.validate(adapter_dir / "adapter.json")
        expected = {
            ".cursor/agents/cavecrew-builder.md",
            ".cursor/agents/cavecrew-investigator.md",
            ".cursor/agents/cavecrew-reviewer.md",
            ".cursor/rules/caveman.mdc",
            ".cursor/rules/fable-grok-subagents.mdc",
            ".cursor/skills/cavecrew/SKILL.md",
            ".cursor/skills/cavecrew/LICENSE",
            ".cursor/skills/caveman/SKILL.md",
            ".cursor/skills/caveman/LICENSE",
        }
        entries = {entry["dst"]: entry for entry in manifest["files"]}

        self.assertTrue(expected.issubset(entries))
        for path in expected:
            self.assertTrue(entries[path].get("from_stack"), path)

        with tempfile.TemporaryDirectory() as target:
            install.install(manifest, target, adapter_dir, ROOT, log=lambda _line: None)
            for path in expected:
                self.assertTrue((Path(target) / path).is_file(), path)

    def test_formula_packages_scripts_directory(self):
        formula = (ROOT / "Formula" / "agentic-stack.rb").read_text(encoding="utf-8")

        self.assertIn('"scripts"', formula)

    def test_formula_targets_the_current_version_and_smokes_loop_validation(self):
        from harness_manager import __version__

        formula = (ROOT / "Formula" / "agentic-stack.rb").read_text(encoding="utf-8")

        # Derived from __version__ so a version bump that forgets the formula
        # fails here instead of shipping brew users the previous tarball.
        self.assertIn(f"refs/tags/v{__version__}.tar.gz", formula)
        # Literal on purpose: the hash is release evidence, not something a
        # bump can compute, so it must be updated deliberately per release.
        self.assertIn("a128f83f9734dd4341e9b9b22084944ab791b1d1321c4d0e5e3d60cbbc30e22c", formula)
        self.assertIn('"loop", "validate"', formula)

    def test_doctor_detects_modern_windsurf_rule(self):
        doctor = (ROOT / "harness_manager" / "doctor.py").read_text(encoding="utf-8")

        self.assertIn('.windsurf/rules/agentic-stack.md', doctor)


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


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

    def test_formula_packages_scripts_directory(self):
        formula = (ROOT / "Formula" / "agentic-stack.rb").read_text(encoding="utf-8")

        self.assertIn('"scripts"', formula)

    def test_doctor_detects_modern_windsurf_rule(self):
        doctor = (ROOT / "harness_manager" / "doctor.py").read_text(encoding="utf-8")

        self.assertIn('.windsurf/rules/agentic-stack.md', doctor)


if __name__ == "__main__":
    unittest.main()

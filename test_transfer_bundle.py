import json
import tempfile
import unittest
from pathlib import Path

from harness_manager.transfer_bundle import (
    BundleSecurityError,
    decode_payload,
    encode_bundle,
    export_bundle,
    import_bundle,
    scan_text_for_secrets,
)


class TransferBundleTest(unittest.TestCase):
    def make_agent(self, root: Path):
        agent = root / ".agent"
        (agent / "memory" / "personal").mkdir(parents=True)
        (agent / "memory" / "semantic").mkdir(parents=True)
        (agent / "memory" / "working").mkdir(parents=True)
        (agent / "memory" / "episodic").mkdir(parents=True)
        (agent / "memory" / "candidates" / "pending").mkdir(parents=True)
        (agent / "skills" / "deploy-checklist").mkdir(parents=True)
        (agent / "memory" / "personal" / "PREFERENCES.md").write_text(
            "# Preferences\n\n- Use concise explanations.\n",
            encoding="utf-8",
        )
        (agent / "memory" / "semantic" / "lessons.jsonl").write_text(
            "\n".join(
                [
                    json.dumps({"id": "lesson_keep", "claim": "Serialize timestamps in UTC.", "conditions": ["timestamp"], "status": "accepted"}),
                    json.dumps({"id": "lesson_skip", "claim": "Draft idea.", "conditions": [], "status": "provisional"}),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (agent / "skills" / "_index.md").write_text("# Skills\n", encoding="utf-8")
        (agent / "skills" / "deploy-checklist" / "SKILL.md").write_text(
            "---\nname: deploy-checklist\n---\nCheck deploys.\n",
            encoding="utf-8",
        )
        (agent / "memory" / "working" / "WORKSPACE.md").write_text(
            "# Workspace\n\nCurrent task context.\n",
            encoding="utf-8",
        )
        (agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl").write_text(
            json.dumps({"event": "debugged importer", "ts": "2026-05-02T00:00:00Z"}) + "\n",
            encoding="utf-8",
        )
        (agent / "memory" / "candidates" / "pending" / "candidate.json").write_text(
            json.dumps({"id": "candidate_keep", "claim": "Review before accepting."}) + "\n",
            encoding="utf-8",
        )
        return agent

    def test_export_encode_decode_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(Path(tmp))

            bundle = export_bundle(agent, targets=["codex"], scopes=["preferences", "accepted_lessons", "skills"])
            payload, digest = encode_bundle(bundle)
            decoded = decode_payload(payload, digest)

            self.assertEqual(decoded["targets"], ["codex"])
            self.assertEqual(decoded["scopes"], ["preferences", "accepted_lessons", "skills"])
            self.assertEqual(decoded["lessons"][0]["id"], "lesson_keep")
            self.assertNotIn("lesson_skip", json.dumps(decoded))
            paths = {f["path"] for f in decoded["files"]}
            self.assertIn(".agent/memory/personal/PREFERENCES.md", paths)
            self.assertIn(".agent/skills/deploy-checklist/SKILL.md", paths)

    def test_digest_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(Path(tmp))
            payload, _digest = encode_bundle(export_bundle(agent, targets=["codex"], scopes=["preferences"]))

            with self.assertRaises(ValueError):
                decode_payload(payload, "0" * 64)

    def test_import_merges_preferences_and_lessons_idempotently(self):
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
            src_agent = self.make_agent(Path(src_tmp))
            dst = Path(dst_tmp)
            (dst / ".agent" / "memory" / "personal").mkdir(parents=True)
            (dst / ".agent" / "memory" / "semantic").mkdir(parents=True)
            (dst / ".agent" / "memory" / "personal" / "PREFERENCES.md").write_text(
                "# Preferences\n\n- Existing local preference.\n",
                encoding="utf-8",
            )

            bundle = export_bundle(src_agent, targets=["terminal"], scopes=["preferences", "accepted_lessons", "skills"])
            first = import_bundle(bundle, dst)
            second = import_bundle(bundle, dst)

            prefs = (dst / ".agent" / "memory" / "personal" / "PREFERENCES.md").read_text(encoding="utf-8")
            self.assertIn("Existing local preference", prefs)
            self.assertEqual(prefs.count("## Imported Preferences"), 1)
            lessons_rows = [
                json.loads(line)
                for line in (dst / ".agent" / "memory" / "semantic" / "lessons.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            self.assertEqual([row["id"] for row in lessons_rows], ["lesson_keep"])
            self.assertTrue((dst / ".agent" / "memory" / "semantic" / "LESSONS.md").exists())
            self.assertTrue((dst / ".agent" / "skills" / "deploy-checklist" / "SKILL.md").exists())
            self.assertEqual(first["lessons_imported"], 1)
            self.assertEqual(second["lessons_imported"], 0)

    def test_secret_scan_blocks_private_keys_and_tokens(self):
        self.assertTrue(scan_text_for_secrets("OPENAI_API_KEY=sk-proj-abcdef1234567890"))
        self.assertTrue(scan_text_for_secrets("-----BEGIN PRIVATE KEY-----\nsecret\n-----END PRIVATE KEY-----"))

    def test_export_rejects_secret_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            agent = self.make_agent(Path(tmp))
            (agent / "memory" / "personal" / "PREFERENCES.md").write_text(
                "OPENAI_API_KEY=sk-proj-abcdef1234567890",
                encoding="utf-8",
            )

            with self.assertRaises(BundleSecurityError):
                export_bundle(agent, targets=["codex"], scopes=["preferences"])

    def test_export_and_import_full_memory_scopes(self):
        with tempfile.TemporaryDirectory() as src_tmp, tempfile.TemporaryDirectory() as dst_tmp:
            src_agent = self.make_agent(Path(src_tmp))
            dst = Path(dst_tmp)

            bundle = export_bundle(
                src_agent,
                targets=["codex"],
                scopes=["working", "episodic", "candidates"],
            )
            paths = {entry["path"] for entry in bundle["files"]}

            self.assertIn(".agent/memory/working/WORKSPACE.md", paths)
            self.assertIn(".agent/memory/episodic/AGENT_LEARNINGS.jsonl", paths)
            self.assertIn(".agent/memory/candidates/pending/candidate.json", paths)

            import_bundle(bundle, dst)

            self.assertTrue((dst / ".agent" / "memory" / "working" / "WORKSPACE.md").exists())
            self.assertTrue((dst / ".agent" / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl").exists())
            self.assertTrue((dst / ".agent" / "memory" / "candidates" / "pending" / "candidate.json").exists())


if __name__ == "__main__":
    unittest.main()

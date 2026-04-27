import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPORTER = ROOT / ".agent" / "tools" / "data_flywheel_export.py"


class DataFlywheelExportTest(unittest.TestCase):
    def run_export(self, work: Path, *args: str):
        return subprocess.run(
            ["python3", str(EXPORTER), "--agent-root", str(work / ".agent"), *args],
            cwd=work,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_exports_trace_context_eval_and_training_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            flywheel = work / ".agent" / "flywheel"
            flywheel.mkdir(parents=True)
            (flywheel / "approved-runs.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "raw-run-123",
                                "created_at": "2026-04-25T10:00:00Z",
                                "project": "openclaw-real-estate",
                                "domain": "real_estate",
                                "workflow": "lead_intake",
                                "harness": "openclaw",
                                "instruction": "Extract CRM fields.",
                                "input_summary": "Redacted lead.",
                                "input_redacted": "[REDACTED] buyer asks for a weekend showing",
                                "output_summary": "CRM fields and follow-up.",
                                "output_approved": "CRM fields plus approved follow-up.",
                                "human_review": {"status": "accepted", "review_notes": "Looks good."},
                                "redaction_status": "passed",
                                "pii_level": "none",
                                "raw_input_stored": False,
                                "context_tokens_before": 4200,
                                "context_tokens_after": 900,
                                "stable_rules": ["Separate facts from assumptions."],
                                "human_approval_required_for": ["client-facing messages"],
                                "failure_modes": ["unsupported_inference"],
                            }
                        ),
                        json.dumps(
                            {
                                "id": "rejected-run",
                                "created_at": "2026-04-25T11:00:00Z",
                                "domain": "real_estate",
                                "workflow": "lead_intake",
                                "input_redacted": "[REDACTED]",
                                "output_approved": "Rejected output.",
                                "human_review": {"status": "rejected"},
                                "redaction_status": "passed",
                                "pii_level": "none",
                            }
                        ),
                        "{broken",
                    ]
                )
            )

            result = self.run_export(work, "--date", "2026-04-25")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("metrics=", result.stdout)

            out = work / ".agent" / "flywheel" / "exports" / "2026-04-25"
            self.assertTrue((out / "trace-records.jsonl").exists())
            self.assertTrue((out / "training-examples.jsonl").exists())
            self.assertTrue((out / "eval-cases.jsonl").exists())
            self.assertTrue((out / "context-cards" / "real_estate" / "lead_intake.md").exists())

            traces = [json.loads(line) for line in (out / "trace-records.jsonl").read_text().splitlines()]
            training = [json.loads(line) for line in (out / "training-examples.jsonl").read_text().splitlines()]
            evals = [json.loads(line) for line in (out / "eval-cases.jsonl").read_text().splitlines()]
            metrics = json.loads((out / "flywheel-metrics.json").read_text())
            all_output = "\n".join(
                [
                    (out / "trace-records.jsonl").read_text(),
                    (out / "training-examples.jsonl").read_text(),
                    (out / "eval-cases.jsonl").read_text(),
                    (out / "context-cards" / "real_estate" / "lead_intake.md").read_text(),
                ]
            )

            self.assertEqual(len(traces), 2)
            self.assertEqual(len(training), 1)
            self.assertEqual(len(evals), 1)
            self.assertEqual(metrics["total_traces"], 2)
            self.assertEqual(metrics["trainable_traces"], 1)
            self.assertEqual(metrics["input_quality"]["malformed_lines"], 1)
            self.assertFalse(traces[0]["raw_input_stored"])
            self.assertNotIn("raw-run-123", all_output)
            self.assertIn("Separate facts from assumptions.", all_output)

    def test_succeeds_with_missing_input(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / ".agent").mkdir()
            result = self.run_export(work, "--date", "2026-04-25")
            self.assertEqual(result.returncode, 0, result.stderr)
            metrics = json.loads(
                (work / ".agent" / "flywheel" / "exports" / "2026-04-25" / "flywheel-metrics.json").read_text()
            )
            self.assertEqual(metrics["privacy_model"], "local_only_redacted_by_default")
            self.assertTrue(metrics["input_quality"]["missing"])


if __name__ == "__main__":
    unittest.main()

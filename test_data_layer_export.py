import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXPORTER = ROOT / ".agent" / "tools" / "data_layer_export.py"


class DataLayerExportTest(unittest.TestCase):
    def run_export(self, work: Path, *args: str):
        return subprocess.run(
            ["python3", str(EXPORTER), "--agent-root", str(work / ".agent"), *args],
            cwd=work,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_exports_cross_harness_dashboard_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            episodic = work / ".agent" / "memory" / "episodic"
            data_layer = work / ".agent" / "data-layer"
            episodic.mkdir(parents=True)
            data_layer.mkdir(parents=True)

            (episodic / "AGENT_LEARNINGS.jsonl").write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "timestamp": "2026-04-25T10:00:00Z",
                                "skill": "claude-code",
                                "action": "debug failing test",
                                "result": "success",
                                "tokens_in_estimate": 1000,
                                "tokens_out_estimate": 250,
                                "cost_estimate_usd": 0.05,
                                "source": {
                                    "skill": "claude-code",
                                    "profile": "default",
                                    "run_id": "raw-run-id",
                                },
                            }
                        ),
                        "{broken",
                    ]
                )
            )
            (data_layer / "cron-runs.jsonl").write_text(
                json.dumps(
                    {
                        "id": "cron_daily_report",
                        "started_at": "2026-04-25T08:00:00Z",
                        "finished_at": "2026-04-25T08:05:00Z",
                        "harness": "codex",
                        "name": "daily report",
                        "workflow": "daily_report",
                        "status": "success",
                        "agent_id": "raw-agent-id",
                        "tokens_in_estimate": 500,
                        "tokens_out_estimate": 200,
                        "cost_estimate_usd": 0.02,
                    }
                )
                + "\n"
            )
            (data_layer / "category-rules.json").write_text(
                json.dumps(
                    {
                        "default_category": "uncategorized",
                        "rules": [
                            {"category": "coding", "harnesses": ["claude-code"]},
                            {"category": "admin", "run_types": ["cron"]},
                        ],
                    }
                )
            )

            result = self.run_export(work, "--window", "all", "--bucket", "hour", "--date", "2026-04-25")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("dashboard_html=", result.stdout)

            out = work / ".agent" / "data-layer" / "exports" / "2026-04-25"
            self.assertTrue((out / "dashboard.html").exists())
            self.assertTrue((out / "daily-report.md").exists())
            self.assertTrue((out / "dashboard-report.json").exists())
            self.assertTrue((out / "cron-timeline.csv").exists())
            self.assertTrue((out / "kpi-summary.csv").exists())

            summary = json.loads((out / "dashboard-summary.json").read_text())
            self.assertEqual(summary["counts"]["agent_events"], 1)
            self.assertEqual(summary["counts"]["cron_runs"], 1)
            self.assertEqual(summary["counts"]["harnesses"], 2)
            self.assertEqual(summary["resources"]["tokens_total_estimate"], 1950)
            self.assertEqual(summary["data_quality"]["episodic"]["malformed_lines"], 1)

            agent_events = (out / "agent-events.jsonl").read_text()
            cron_runs = (out / "cron-runs.jsonl").read_text()
            self.assertNotIn("raw-run-id", agent_events)
            self.assertNotIn("raw-agent-id", cron_runs)
            self.assertIn('"category":"coding"', agent_events)
            self.assertIn('"category":"admin"', cron_runs)

            timeline = json.loads((out / "cron-timeline.json").read_text())
            self.assertEqual(timeline[0]["started_at"], "2026-04-25T08:00:00Z")
            self.assertEqual(timeline[0]["finished_at"], "2026-04-25T08:05:00Z")
            kpis = json.loads((out / "kpi-summary.json").read_text())
            self.assertIn("cron_runs_per_day", {row["kpi"] for row in kpis})
            dashboard_html = (out / "dashboard.html").read_text()
            self.assertIn("Cron Gantt", dashboard_html)
            self.assertIn("KPI Summary", dashboard_html)

    def test_succeeds_with_empty_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / ".agent").mkdir()
            result = self.run_export(work, "--date", "2026-04-25")
            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (work / ".agent" / "data-layer" / "exports" / "2026-04-25" / "dashboard-summary.json").read_text()
            )
            self.assertEqual(summary["privacy_model"], "local_only")
            self.assertTrue(summary["data_quality"]["episodic"]["missing"])


if __name__ == "__main__":
    unittest.main()

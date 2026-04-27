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
            self.assertTrue((out / "dashboard.tui.txt").exists())
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
            dashboard_tui = (out / "dashboard.tui.txt").read_text()
            self.assertIn("Terminal Dashboard", dashboard_tui)
            self.assertIn("Top Harnesses", dashboard_tui)
            self.assertIn("◇", dashboard_tui)
            self.assertNotIn("\x1b[", dashboard_tui)

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

    def test_default_command_prints_terminal_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            episodic = work / ".agent" / "memory" / "episodic"
            episodic.mkdir(parents=True)
            (episodic / "AGENT_LEARNINGS.jsonl").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-04-25T10:00:00Z",
                        "skill": "codex",
                        "action": "ship dashboard",
                        "result": "success",
                        "workflow": "release",
                        "tokens_in_estimate": 1200,
                        "tokens_out_estimate": 400,
                        "cost_estimate_usd": 0.08,
                        "source": {"skill": "codex", "run_id": "raw-run-id"},
                    }
                )
                + "\n"
            )

            result = self.run_export(work, "--window", "all", "--date", "2026-04-25")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("agentic-stack Data Layer", result.stdout)
            self.assertIn("Terminal Dashboard", result.stdout)
            self.assertIn("◇", result.stdout)
            self.assertIn("◆", result.stdout)
            self.assertIn("Agent events", result.stdout)
            self.assertIn("codex", result.stdout)
            self.assertIn("release", result.stdout)
            self.assertIn("dashboard_html=", result.stdout)
            self.assertNotIn("raw-run-id", result.stdout)

    def test_natural_language_request_sets_window_and_bucket(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / ".agent").mkdir()

            result = self.run_export(
                work,
                "--date",
                "2026-04-25",
                "show",
                "me",
                "the",
                "last",
                "7",
                "days",
                "by",
                "hour",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (work / ".agent" / "data-layer" / "exports" / "2026-04-25" / "dashboard-summary.json").read_text()
            )
            self.assertEqual(summary["request"], "show me the last 7 days by hour")
            self.assertEqual(summary["window"], "7d")
            self.assertEqual(summary["bucket"], "hour")
            self.assertIn("Request", result.stdout)
            self.assertIn("show me the last 7 days by hour", result.stdout)

    def test_explicit_flags_override_natural_language_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            (work / ".agent").mkdir()

            result = self.run_export(
                work,
                "--date",
                "2026-04-25",
                "--window",
                "all",
                "--bucket",
                "month",
                "show",
                "me",
                "the",
                "last",
                "7",
                "days",
                "by",
                "hour",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            summary = json.loads(
                (work / ".agent" / "data-layer" / "exports" / "2026-04-25" / "dashboard-summary.json").read_text()
            )
            self.assertEqual(summary["request"], "show me the last 7 days by hour")
            self.assertEqual(summary["window"], "all")
            self.assertEqual(summary["bucket"], "month")

    def test_data_layer_skill_is_injected_dashboard_surface(self):
        skill = (ROOT / ".agent" / "skills" / "data-layer" / "SKILL.md").read_text()
        index = (ROOT / ".agent" / "skills" / "_index.md").read_text()
        manifest = (ROOT / ".agent" / "skills" / "_manifest.jsonl").read_text()

        self.assertIn("what did my agents do", skill)
        self.assertIn("python3 .agent/tools/data_layer_export.py show me last 7 days by hour", skill)
        self.assertIn("what did my agents do", index)
        self.assertIn('"show me the dashboard"', manifest)


if __name__ == "__main__":
    unittest.main()

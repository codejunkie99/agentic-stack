import importlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def make_project(root: Path) -> None:
    agent = root / ".agent"
    (agent / "memory" / "personal").mkdir(parents=True)
    (agent / "memory" / "semantic").mkdir(parents=True)
    (agent / "memory" / "episodic").mkdir(parents=True)
    (agent / "memory" / "candidates" / "rejected").mkdir(parents=True)
    (agent / "memory" / "working").mkdir(parents=True)
    (agent / "memory" / "team").mkdir(parents=True)
    (agent / "skills" / "example").mkdir(parents=True)
    (agent / "runtime").mkdir(parents=True)
    (agent / "protocols").mkdir(parents=True)
    (root / "AGENTS.md").write_text(
        "Use .agent/memory/personal/PREFERENCES.md and .agent/tools/recall.py.\n",
        encoding="utf-8",
    )
    (agent / "AGENTS.md").write_text("# Agentic Stack\n", encoding="utf-8")
    (agent / "protocols" / "permissions.md").write_text("# Permissions\n", encoding="utf-8")
    (agent / "memory" / "personal" / "PREFERENCES.md").write_text(
        "# Preferences\n\n- Keep output direct.\n",
        encoding="utf-8",
    )
    (agent / "memory" / "working" / "REVIEW_QUEUE.md").write_text("# Queue\n", encoding="utf-8")
    (agent / "memory" / "semantic" / "lessons.jsonl").write_text(
        json.dumps({"id": "lesson_1", "status": "accepted", "claim": "Use local checks."}) + "\n",
        encoding="utf-8",
    )
    (agent / "memory" / "episodic" / "AGENT_LEARNINGS.jsonl").write_text(
        json.dumps({"id": "episode_1", "event": "installed", "result": "success"}) + "\n",
        encoding="utf-8",
    )
    (agent / "memory" / "candidates" / "rejected" / "candidate_2.json").write_text(
        json.dumps({"id": "candidate_2", "claim": "Use a hidden command.", "status": "rejected"}) + "\n",
        encoding="utf-8",
    )
    (agent / "skills" / "example" / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    for name in ("CONVENTIONS.md", "REVIEW_RULES.md", "DEPLOYMENT_LESSONS.md", "INCIDENTS.md", "APPROVED_SKILLS.md"):
        (agent / "memory" / "team" / name).write_text(f"# {name}\n", encoding="utf-8")
    (agent / "runtime" / "instances.json").write_text(
        json.dumps({"active_instance": "worker-a", "instances": [{"id": "worker-a", "state": "running"}]}) + "\n",
        encoding="utf-8",
    )
    (agent / "install.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "agentic_stack_version": "0.15.0",
                "installed_at": "2026-05-08T00:00:00Z",
                "adapters": {
                    "codex": {
                        "files_written": [],
                        "files_overwritten": [],
                        "file_results": [],
                        "post_install_results": [],
                    }
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


class MissionControlTest(unittest.TestCase):
    def run_cli(self, cwd: Path, *args: str):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(ROOT)
        env["AGENTIC_STACK_ROOT"] = str(ROOT)
        return subprocess.run(
            ["python3", "-m", "harness_manager.cli", *args],
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_api_payloads_expose_mvp_surfaces(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            payloads = mission_control.build_payloads(project, ROOT)

        self.assertIn("/api/status", payloads)
        self.assertIn("/api/adapters", payloads)
        self.assertIn("/api/doctor", payloads)
        self.assertIn("/api/memory/summary", payloads)
        self.assertEqual(Path(payloads["/api/status"]["project"]).resolve(), project.resolve())
        self.assertEqual(payloads["/api/status"]["score"], 100)
        self.assertIn("codex", payloads["/api/adapters"]["installed"])
        self.assertEqual(payloads["/api/memory/summary"]["accepted"], 1)
        self.assertGreaterEqual(len(payloads["/api/doctor"]["checks"]), 1)

    def test_phase_a_payloads_expose_all_control_plane_domains(self):
        from harness_manager import mission_control

        expected_paths = [
            "/api/command-center",
            "/api/brain",
            "/api/brain/lessons",
            "/api/brain/candidates",
            "/api/harnesses",
            "/api/harnesses/codex",
            "/api/trust",
            "/api/trust/verify",
            "/api/runs",
            "/api/skills",
            "/api/skills/example",
            "/api/protocols",
            "/api/protocols/permissions",
            "/api/handoff",
            "/api/data-flywheel",
            "/api/ops/events",
            "/api/settings",
            "/api/command-recipes",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            payloads = mission_control.build_payloads(project, ROOT)

        for path in expected_paths:
            self.assertIn(path, payloads)
            self.assertIn("objects", payloads[path])
        self.assertEqual(payloads["/api/command-center"]["domain"], "Command Center")
        self.assertEqual(payloads["/api/brain"]["domain"], "Brain")
        self.assertEqual(payloads["/api/command-recipes"]["domain"], "Command Recipes")
        self.assertEqual(payloads["/api/settings"]["objects"][0]["kind"], "setting")
        for payload in payloads.values():
            for item in payload.get("objects", []):
                self.assertIn("id", item)
                self.assertIn("kind", item)
                self.assertIn("label", item)
                self.assertIn("status", item)
                self.assertIn("summary", item)
                self.assertIn("source", item)
                self.assertIn("payload", item)

    def test_phase_c_command_recipes_are_copy_only(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            payloads = mission_control.build_payloads(project, ROOT)

        recipes = payloads["/api/command-recipes"]["objects"]
        recipe_ids = {item["id"] for item in recipes}
        self.assertIn("recipe-doctor", recipe_ids)
        self.assertIn("recipe-status", recipe_ids)
        self.assertIn("recipe-verify", recipe_ids)
        self.assertIn("recipe-transfer-export", recipe_ids)
        self.assertIn("recipe-transfer-import", recipe_ids)
        self.assertIn("recipe-data-layer-export", recipe_ids)
        self.assertTrue(any(item["payload"]["category"] == "adapter-install" for item in recipes))
        self.assertTrue(any(item["payload"]["category"] == "adapter-repair" for item in recipes))
        for item in recipes:
            self.assertEqual(item["kind"], "command_recipe")
            self.assertTrue(item["payload"]["copy_only"])
            self.assertIn("command", item["payload"])
            self.assertNotIn("execute", item["payload"])

    def test_phase_c_persistent_ops_events_are_recorded(self):
        from harness_manager import mission_control
        from harness_manager import mission_control_collectors

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            event = mission_control_collectors.record_ops_event(
                project,
                {"type": "inspector", "payload": {"id": "lesson_1"}},
            )
            payloads = mission_control.build_payloads(project, ROOT)

            event_log = project / ".agent" / "runtime" / "mission-control-events.jsonl"
            self.assertTrue(event_log.is_file())
            persisted = [json.loads(line) for line in event_log.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(persisted[-1]["id"], event["id"])
            self.assertEqual(persisted[-1]["type"], "inspector")
            ops = payloads["/api/ops/events"]
            self.assertIn("stats", ops)
            self.assertGreaterEqual(ops["stats"]["events"], 1)
            persisted_event = next(item for item in ops["objects"] if item["payload"].get("type") == "inspector")
            self.assertTrue(persisted_event["payload"]["persistent"])

    def test_phase_c_action_metadata_and_dense_command_center(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            payloads = mission_control.build_payloads(project, ROOT)

        command_center = payloads["/api/command-center"]
        self.assertIn("stats", command_center)
        for key in ("failing_domains", "adapter_parity", "memory_queue", "recent_events", "handoff_ready"):
            self.assertIn(key, command_center["stats"])
        self.assertIsInstance(command_center["stats"]["failing_domains"], list)
        self.assertIn("installed", command_center["stats"]["adapter_parity"])

        for path in ("/api/brain", "/api/harnesses", "/api/trust", "/api/command-recipes"):
            item = payloads[path]["objects"][0]
            self.assertIn("health_impact", item["payload"])
            self.assertIn("related_commands", item["payload"])
            self.assertIn("next_action", item["payload"])
            self.assertIsInstance(item["payload"]["related_commands"], list)

    def test_phase_c_ui_exposes_recipes_persistent_ops_and_action_drawer(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            html = mission_control.render_page(project, ROOT)

        self.assertIn('data-domain="Command Recipes"', html)
        self.assertIn('data-panel="Command Recipes"', html)
        self.assertIn('data-copy-api="/api/command-recipes"', html)
        self.assertIn('id="action-drawer"', html)
        self.assertIn('id="inspector-evidence"', html)
        self.assertIn('id="inspector-next-action"', html)
        self.assertIn('id="bottom-ops-console"', html)
        self.assertIn("function persistOpsEvent", html)
        self.assertIn("fetch('/api/ops/events'", html)

    def test_mission_control_beta_defaults_off_in_onboarding_yes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT)
            result = subprocess.run(
                ["python3", str(ROOT / "onboard.py"), str(project), "--yes"],
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Mission Control beta", result.stdout)
            self.assertIn("turn it off", result.stdout)
            features = json.loads((project / ".agent" / "memory" / ".features.json").read_text(encoding="utf-8"))
            self.assertEqual(features["mission_control"], {"enabled": False, "beta": True})

    def test_phase_b_uses_split_mission_control_modules(self):
        for name in (
            "harness_manager.mission_control_server",
            "harness_manager.mission_control_collectors",
            "harness_manager.mission_control_render",
            "harness_manager.mission_control_static",
        ):
            importlib.import_module(name)
        static = importlib.import_module("harness_manager.mission_control_static")

        facade = ROOT / "harness_manager" / "mission_control.py"
        render = ROOT / "harness_manager" / "mission_control_render.py"
        source = facade.read_text(encoding="utf-8")
        render_source = render.read_text(encoding="utf-8")
        self.assertLessEqual(len(source.splitlines()), 80)
        self.assertNotIn("def _phase_a_payloads", source)
        self.assertNotIn("def _client_script", source)
        self.assertNotIn("class Handler", source)
        self.assertTrue(hasattr(static, "styles"))
        self.assertIn("--accent-good", static.styles())
        self.assertNotIn("--accent-good", render_source)

    def test_phase_b_brain_collector_exposes_sources_and_evidence(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)
            agent = project / ".agent"
            lessons_path = agent / "memory" / "semantic" / "lessons.jsonl"
            lessons_path.write_text(
                "\n".join(
                    [
                        json.dumps(
                            {
                                "id": "lesson_1",
                                "status": "accepted",
                                "claim": "Use local checks.",
                                "evidence": ["AGENTS.md", ".agent/memory/personal/PREFERENCES.md"],
                            }
                        ),
                        json.dumps({"id": "lesson_2", "status": "provisional", "claim": "Review warnings."}),
                        json.dumps({"id": "lesson_3", "status": "rejected", "claim": "Ignore failures."}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            (agent / "memory" / "candidates" / "candidate_1.json").write_text(
                json.dumps({"id": "candidate_1", "claim": "Promote stable behavior.", "status": "staged"}) + "\n",
                encoding="utf-8",
            )
            (agent / "memory" / "candidates" / "graduated").mkdir(exist_ok=True)
            (agent / "memory" / "candidates" / "graduated" / "candidate_3.json").write_text(
                json.dumps({"id": "candidate_3", "claim": "Keep verified facts.", "status": "graduated"}) + "\n",
                encoding="utf-8",
            )

            payloads = mission_control.build_payloads(project, ROOT)

        brain = payloads["/api/brain"]
        self.assertEqual(brain["stats"]["accepted"], 1)
        self.assertEqual(brain["stats"]["provisional"], 1)
        self.assertEqual(brain["stats"]["rejected"], 1)
        lesson = next(item for item in brain["objects"] if item["id"] == "lesson-lesson_1")
        self.assertEqual(lesson["payload"]["source_line"], 1)
        self.assertTrue(lesson["payload"]["source_path"].endswith("lessons.jsonl"))
        self.assertEqual(lesson["payload"]["evidence_count"], 2)
        self.assertEqual(lesson["payload"]["lesson_status"], "accepted")
        candidate = next(item for item in payloads["/api/brain/candidates"]["objects"] if item["id"] == "candidate-candidate_1")
        self.assertEqual(candidate["payload"]["candidate_state"], "staged")
        self.assertTrue(candidate["payload"]["source_path"].endswith("candidate_1.json"))

    def test_phase_b_trust_collector_explains_warnings_and_failures(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            payloads = mission_control.build_payloads(project, ROOT)

        trust = payloads["/api/trust"]
        self.assertIn("stats", trust)
        self.assertGreaterEqual(trust["stats"]["pass"], 1)
        self.assertGreaterEqual(trust["stats"]["fail"], 1)
        for item in trust["objects"]:
            self.assertIn("severity", item["payload"])
            self.assertIn("explanation", item["payload"])
            self.assertIn("source_paths", item["payload"])
            self.assertIsInstance(item["payload"]["source_paths"], list)

    def test_phase_b_domain_collectors_expose_real_local_details(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)
            agent = project / ".agent"
            (agent / "memory" / "candidates" / "candidate_1.json").write_text(
                json.dumps({"id": "candidate_1", "claim": "Promote stable behavior.", "status": "staged"}) + "\n",
                encoding="utf-8",
            )

            payloads = mission_control.build_payloads(project, ROOT)

        codex = next(item for item in payloads["/api/harnesses"]["objects"] if item["label"] == "codex")
        self.assertTrue(codex["payload"]["installed"])
        self.assertIn("expected_files", codex["payload"])
        self.assertIn("missing_files", codex["payload"])
        self.assertIn("parity_gaps", codex["payload"])

        run = next(item for item in payloads["/api/runs"]["objects"] if item["id"] == "run-worker-a")
        self.assertTrue(run["payload"]["active"])
        self.assertEqual(run["payload"]["state"], "running")
        self.assertIn("stale", run["payload"])
        self.assertTrue(run["payload"]["source_path"].endswith("instances.json"))

        skill = next(item for item in payloads["/api/skills"]["objects"] if item["label"] == "example")
        self.assertTrue(skill["payload"]["skill_path"].endswith("SKILL.md"))
        self.assertTrue(skill["payload"]["valid"])
        self.assertIn("approved", skill["payload"])
        self.assertIn("issues", skill["payload"])
        self.assertIn("manifest_source", skill["payload"])

        protocol = next(item for item in payloads["/api/protocols"]["objects"] if item["label"] == "permissions")
        self.assertTrue(protocol["payload"]["source_path"].endswith("permissions.md"))
        self.assertGreaterEqual(protocol["payload"]["line_count"], 1)
        self.assertLessEqual(len(protocol["payload"]["excerpt"]), 400)

        flywheel = payloads["/api/data-flywheel"]
        self.assertIn("candidate_flow", flywheel["stats"])
        self.assertEqual(flywheel["stats"]["candidate_flow"]["staged"], 1)
        artifact = next(item for item in flywheel["objects"] if item["id"] == "flywheel-memory")
        self.assertIn("recent_artifacts", artifact["payload"])

    def test_render_page_is_clean_mission_control_ui(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            html = mission_control.render_page(project, ROOT)

        self.assertIn("Agentic Stack Mission Control", html)
        self.assertIn("Overview", html)
        self.assertIn("Memory", html)
        self.assertIn("Adapters", html)
        self.assertIn("Trust", html)
        self.assertIn("Handoff", html)
        self.assertIn("--accent-good", html)
        self.assertNotIn("draggable", html.lower())
        self.assertNotIn("widget-grid", html)

    def test_render_page_exposes_interactive_workspace_controls(self):
        from harness_manager import mission_control

        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            html = mission_control.render_page(project, ROOT)

        self.assertIn('role="tablist"', html)
        self.assertIn('data-tab="Overview"', html)
        self.assertIn('data-panel="Memory"', html)
        self.assertIn('data-panel="Handoff"', html)
        self.assertIn('id="mission-search"', html)
        self.assertIn('id="refresh-now"', html)
        self.assertIn('id="auto-refresh"', html)
        self.assertIn('id="inspector"', html)
        self.assertIn('data-inspect-kind="memory"', html)
        self.assertIn('data-inspect-kind="adapter"', html)
        self.assertIn('data-inspect-kind="check"', html)
        self.assertIn('data-copy-kind="command"', html)
        self.assertIn('data-copy-api="/api/status"', html)
        self.assertIn('navigator.clipboard.writeText', html)
        self.assertIn('prefers-reduced-motion: reduce', html)
        self.assertIn('function switchTab', html)
        self.assertIn('function refreshData', html)
        self.assertIn('function applyFilter', html)

    def test_render_page_exposes_phase_a_control_plane_shell(self):
        from harness_manager import mission_control

        domains = [
            "Command Center",
            "Brain",
            "Harnesses",
            "Trust",
            "Runs",
            "Skills",
            "Protocols",
            "Handoff",
            "Data Flywheel",
            "Ops Console",
            "Settings",
        ]
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            make_project(project)

            html = mission_control.render_page(project, ROOT)

        self.assertIn('class="control-plane"', html)
        self.assertIn('class="command-rail"', html)
        self.assertIn('class="telemetry-strip"', html)
        self.assertIn('id="ops-console"', html)
        for domain in domains:
            self.assertIn(f'data-domain="{domain}"', html)
            self.assertIn(f'data-panel="{domain}"', html)
        self.assertIn('data-inspect-kind="skill"', html)
        self.assertIn('data-inspect-kind="protocol"', html)
        self.assertIn('data-inspect-kind="run"', html)
        self.assertIn('data-inspect-kind="setting"', html)
        self.assertIn('data-copy-api="/api/command-center"', html)
        self.assertIn('function logEvent', html)
        self.assertIn('function renderOpsEvent', html)

    def test_cli_snapshot_writes_mission_control_html(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            make_project(project)
            snapshot = Path(tmp) / "mission-control.html"

            result = self.run_cli(
                project,
                "mission-control",
                str(project),
                "--snapshot",
                str(snapshot),
                "--no-open",
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("mission control snapshot:", result.stdout)
            self.assertTrue(snapshot.is_file())
            self.assertIn("Agentic Stack Mission Control", snapshot.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()

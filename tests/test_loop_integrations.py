from __future__ import annotations

import json
from pathlib import Path

from harness_manager.loops.schema import load_contracts
from harness_manager.loops.storage import collect_summary
from harness_manager.upgrade import upgrade
from harness_manager import dashboard_tui, mission_control_collectors, status


ROOT = Path(__file__).resolve().parents[1]


def make_installed_project(tmp_path: Path) -> Path:
    target = tmp_path / "installed"
    agent = target / ".agent"
    for name in ("harness", "memory", "tools", "skills"):
        (agent / name).mkdir(parents=True)
    return target


def test_bundled_loop_assets_validate_and_skills_have_frontmatter():
    loops = ROOT / ".agent" / "loops"
    if not loops.is_dir():
        raise AssertionError("bundled loop assets are missing")
    for path in sorted(loops.glob("*.json")):
        json.loads(path.read_text(encoding="utf-8"))
    for skill in sorted((ROOT / ".agent" / "skills").glob("loop-*/SKILL.md")):
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\n") and "name:" in text and "triggers:" in text


def test_upgrade_adds_missing_loop_assets_but_preserves_authored_contract(tmp_path: Path):
    target = make_installed_project(tmp_path)
    authored = target / ".agent" / "loops" / "ci-sweeper.json"
    authored.parent.mkdir(parents=True)
    authored.write_text('{"user": "owned"}', encoding="utf-8")
    assert upgrade(target, ROOT, yes=True) == 0
    assert authored.read_text(encoding="utf-8") == '{"user": "owned"}'
    assert (target / ".agent" / "loops" / "daily-triage.json").exists()
    assert (target / ".agent" / "runtime" / ".gitignore").exists()


def test_upgrade_does_not_copy_runtime_children_or_overwrite_loop_skills(tmp_path: Path):
    target = make_installed_project(tmp_path)
    skill = target / ".agent" / "skills" / "loop-triage"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("user skill", encoding="utf-8")
    runtime_child = ROOT / ".agent" / "runtime" / "loops" / "should-not-ship.json"
    runtime_child.parent.mkdir(parents=True, exist_ok=True)
    runtime_child.write_text("runtime", encoding="utf-8")
    try:
        assert upgrade(target, ROOT, yes=True) == 0
        assert (skill / "SKILL.md").read_text(encoding="utf-8") == "user skill"
        assert not (target / ".agent" / "runtime" / "loops" / "should-not-ship.json").exists()
    finally:
        runtime_child.unlink(missing_ok=True)


def test_read_only_integrations_surface_loop_state_without_private_fields(tmp_path: Path, capsys):
    target = make_installed_project(tmp_path)
    loops = target / ".agent" / "loops"
    loops.mkdir(parents=True)
    source = ROOT / ".agent" / "loops"
    for name in ("ci-sweeper.json", "harnesses.json", "constraints.json", "budget.json"):
        (loops / name).write_text((source / name).read_text(encoding="utf-8"), encoding="utf-8")
    runtime = target / ".agent" / "runtime" / "loops"
    runtime.mkdir(parents=True)
    (runtime / "run-1.json").write_text(
        json.dumps({"run_id": "run-1", "loop_name": "ci-sweeper", "status": "completed", "task": "secret"}),
        encoding="utf-8",
    )
    (runtime / "events.jsonl").write_text(
        '{"run_id":"run-1","loop":"ci-sweeper","event":"completed","task":"secret"}\nnot json\n',
        encoding="utf-8",
    )
    summary = collect_summary(target)
    assert summary["valid"] == 1
    assert summary["latest"] == {"run_id": "run-1", "loop": "ci-sweeper", "status": "completed", "reason": None}
    status.show(target, log=print)
    assert "loops:" in capsys.readouterr().out
    plain = dashboard_tui.render_plain(target, ROOT)
    assert "Loops" in plain
    payload = mission_control_collectors.build_payloads(target, ROOT)["/api/runs"]
    serialized = json.dumps(payload)
    assert "secret" not in serialized and "task" not in serialized
    assert "run-1" in serialized

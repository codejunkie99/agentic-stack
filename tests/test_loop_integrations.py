from __future__ import annotations

import json
from pathlib import Path

from harness_manager.loops.schema import load_contracts
from harness_manager.upgrade import upgrade


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

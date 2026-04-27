"""Smoke test for bcg_conditional_propagate post-install action.

Verifies that when source `.agent/config.json` has `bcg_adapter:
"enabled"`, a fresh install of the claude-code adapter propagates:
- 16 BCG consulting agents from adapters/bcg/agents/ -> target/.claude/agents/
- 1 BCG slash command from adapters/bcg/commands/ -> target/.claude/commands/
- 16 BCG agent-memory stubs from adapters/bcg/agent-memory-templates/
  -> target/.claude/agent-memory/ (copy-if-missing)

When `bcg_adapter: "disabled"` (default), none of the above propagate.

Top-level placement matches upstream pattern (test_data_flywheel_export.py,
test_data_layer_export.py); `tests/` is gitignored as of v0.9.1 (f1c362d).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STACK_ROOT = Path(__file__).resolve().parent


def _run_install(target: Path, adapter: str = "claude-code") -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(STACK_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "harness_manager.cli", adapter, str(target), "--yes"],
        cwd=str(STACK_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _set_config(value: str) -> None:
    cfg_path = STACK_ROOT / ".agent" / "config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["bcg_adapter"] = value
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")


def test_bcg_propagation_when_enabled():
    original_cfg = (STACK_ROOT / ".agent" / "config.json").read_text()
    try:
        _set_config("enabled")
        with tempfile.TemporaryDirectory(prefix="825-bcg-enabled-") as tmp:
            target = Path(tmp)
            result = _run_install(target)
            assert result.returncode == 0, (
                f"install failed (rc={result.returncode}):\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

            agents_dir = target / ".claude" / "agents"
            commands_dir = target / ".claude" / "commands"
            memory_dir = target / ".claude" / "agent-memory"

            assert agents_dir.is_dir(), "no .claude/agents/ created"
            agent_count = len(list(agents_dir.glob("*.md")))
            assert agent_count >= 21, (
                f"expected 5 SDLC + 16 BCG = 21 agents, got {agent_count}\n"
                f"install stdout:\n{result.stdout}"
            )

            bcg_agent = agents_dir / "partner-strategy.md"
            assert bcg_agent.is_file(), "partner-strategy.md (BCG) missing"

            assert commands_dir.is_dir(), "no .claude/commands/ created"
            assert (commands_dir / "sync-harness.md").is_file(), \
                "sync-harness.md (BCG slash command) missing"

            assert memory_dir.is_dir(), "no .claude/agent-memory/ created"
            memory_count = len(list(memory_dir.glob("*.md")))
            assert memory_count == 16, (
                f"expected 16 BCG agent-memory stubs, got {memory_count}"
            )
    finally:
        (STACK_ROOT / ".agent" / "config.json").write_text(original_cfg)


def test_no_bcg_propagation_when_disabled():
    original_cfg = (STACK_ROOT / ".agent" / "config.json").read_text()
    try:
        _set_config("disabled")
        with tempfile.TemporaryDirectory(prefix="825-bcg-disabled-") as tmp:
            target = Path(tmp)
            result = _run_install(target)
            assert result.returncode == 0, (
                f"install failed (rc={result.returncode}):\n"
                f"STDOUT:\n{result.stdout}\n"
                f"STDERR:\n{result.stderr}"
            )

            agents_dir = target / ".claude" / "agents"
            assert agents_dir.is_dir(), "no .claude/agents/ created"
            agent_count = len(list(agents_dir.glob("*.md")))
            assert agent_count == 5, (
                f"expected exactly 5 SDLC agents (no BCG), got {agent_count}\n"
                f"install stdout:\n{result.stdout}"
            )

            commands_dir = target / ".claude" / "commands"
            assert not commands_dir.exists() or not list(commands_dir.glob("*.md")), \
                "BCG commands should not propagate when adapter disabled"

            memory_dir = target / ".claude" / "agent-memory"
            assert not memory_dir.exists() or not list(memory_dir.glob("*.md")), \
                "BCG agent-memory should not propagate when adapter disabled"
    finally:
        (STACK_ROOT / ".agent" / "config.json").write_text(original_cfg)


if __name__ == "__main__":
    test_bcg_propagation_when_enabled()
    print("PASS: bcg propagation when enabled")
    test_no_bcg_propagation_when_disabled()
    print("PASS: no bcg propagation when disabled")

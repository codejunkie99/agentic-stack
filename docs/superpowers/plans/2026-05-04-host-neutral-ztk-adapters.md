# Host-Neutral ztk Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide one ztk policy CLI that native-hook hosts and instruction-only hosts can share.

**Architecture:** `.agent/harness/ztk_policy.py` normalizes host tool events and evaluates `.agent/protocols` policy. `.agent/tools/ztk.py` exposes `pre-tool`, native hook adapters, `exec`, and `recall`. Adapter folders install the host-specific glue.

**Tech Stack:** Python standard library, JSON hook configs, shell/PowerShell installers, pytest.

---

### Task 1: Shared Policy Core

**Files:**
- Create: `.agent/harness/ztk_policy.py`
- Modify: `.agent/tools/claude_pre_tool_use.py`
- Test: `tests/test_ztk_policy.py`, `tests/test_claude_pre_tool_use.py`

- [x] Write failing tests for normalized shell events, Codex hook events, and Claude output compatibility.
- [x] Implement `evaluate_event`, `claude_output`, and `codex_output`.
- [x] Update the Claude hook script to call the shared policy.
- [x] Run focused pytest and verify the red-to-green cycle.

### Task 2: ztk CLI

**Files:**
- Create: `.agent/tools/ztk.py`
- Test: `tests/test_ztk_policy.py`

- [x] Add `pre-tool`, `claude-hook`, `codex-hook`, `exec`, and `recall` commands.
- [x] Ensure `ztk exec` evaluates policy before subprocess execution.
- [x] Add a test proving denied commands are not executed.

### Task 3: Host Adapters

**Files:**
- Create: `adapters/codex/`
- Modify: `adapters/opencode/opencode.json`
- Modify: `install.sh`, `install.ps1`
- Test: `tests/test_ztk_policy.py`

- [x] Add Codex `AGENTS.md`, `.codex/config.toml`, and `.codex/hooks.json`.
- [x] Update OpenCode to use the current `permission` key.
- [x] Teach installers to install `codex`.

### Task 4: Documentation

**Files:**
- Create: `docs/adapter-capabilities.md`
- Create: `docs/per-harness/codex.md`
- Modify: `README.md`, per-harness docs, adapter READMEs/rules

- [x] Document the researched host capability matrix with official sources.
- [x] Describe native hook, native permission, and wrapper-only support tiers.
- [x] Update quickstart and supported harness tables.

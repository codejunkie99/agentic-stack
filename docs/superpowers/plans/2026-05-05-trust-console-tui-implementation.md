# Trust Console TUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first local Trust Console data layer and TUI/CLI front door for agentic-stack.

**Architecture:** Add a Python stdlib model layer that reads existing `.agent/` files and returns normalized health, memory, verification, and team-brain data. Add a root CLI dispatcher that preserves legacy adapter install shorthand while exposing `doctor`, `memory`, `verify`, `team`, and `tui` commands. Keep the TUI read-only and backed by the same model used for JSON/plain output.

**Tech Stack:** Python 3 stdlib, file-backed JSON/Markdown data, existing shell installer, Homebrew formula wrapper.

---

### Task 1: Trust Model Tests

**Files:**
- Create: `verify_trust_console.py`

- [x] **Step 1: Write failing tests**

Create `verify_trust_console.py` with tempfile fixtures that assert:
- `trust_model.collect_health()` reports memory, candidates, lessons, skills, adapters, and team status.
- `trust_model.memory_why()` resolves a lesson by id and includes evidence ids.
- `trust_model.verify_harnesses()` catches missing recall instructions.
- `agentic_stack_cli.py doctor --json --project <fixture>` returns JSON.

- [x] **Step 2: Run tests and verify RED**

Run: `python3 verify_trust_console.py`
Expected: FAIL with missing `trust_model` or missing CLI file.

### Task 2: Model Layer

**Files:**
- Create: `.agent/tools/trust_model.py`

- [x] **Step 1: Implement minimal model**

Implement:
- `find_agent_root(start)`
- `collect_health(project_root=None)`
- `memory_learned(project_root=None)`
- `memory_rejected(project_root=None)`
- `memory_why(identifier, project_root=None)`
- `verify_harnesses(harness=None, project_root=None)`
- `team_status(project_root=None)`
- `team_init(project_root=None)`

- [x] **Step 2: Run tests and verify GREEN for model behavior**

Run: `python3 verify_trust_console.py`
Expected: remaining failures only for CLI commands until Task 3.

### Task 3: CLI and TUI

**Files:**
- Create: `.agent/tools/trust_tui.py`
- Create: `agentic_stack_cli.py`

- [x] **Step 1: Implement command dispatcher**

Add commands:
- `doctor [--json] [--project]`
- `memory learned|rejected|why`
- `verify [--all|harness] [--json] [--project]`
- `team status|init`
- `tui`
- `install <adapter>`
- legacy `<adapter>` shorthand that dispatches to `install.sh`

- [x] **Step 2: Implement read-only stdlib TUI**

Use `curses` when TTY is available. Fall back to plain `doctor` output when
non-TTY, curses is unavailable, or `--plain` is passed.

- [x] **Step 3: Run tests and verify GREEN**

Run: `python3 verify_trust_console.py`
Expected: PASS.

### Task 4: Packaging and Docs

**Files:**
- Modify: `Formula/agentic-stack.rb`
- Modify: `README.md`

- [x] **Step 1: Update Homebrew formula**

Install `agentic_stack_cli.py` plus new `.agent/tools/trust_model.py` and
`.agent/tools/trust_tui.py`, and make `bin/agentic-stack` execute the Python
dispatcher.

- [x] **Step 2: Update README**

Document:
- `agentic-stack doctor`
- `agentic-stack tui`
- `agentic-stack memory learned`
- `agentic-stack verify --all`
- `agentic-stack team status`

- [x] **Step 3: Verify commands**

Run:
- `python3 verify_trust_console.py`
- `python3 agentic_stack_cli.py doctor --json`
- `python3 agentic_stack_cli.py verify --all --json`
- `python3 agentic_stack_cli.py team status`

Expected: all pass or return useful local status without crashing.

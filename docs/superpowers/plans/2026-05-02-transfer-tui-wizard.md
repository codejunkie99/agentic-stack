# Transfer TUI Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `agentic-stack transfer` as an onboarding-style TUI wizard that exports/imports portable `.agent` memory bundles and wires Codex, Cursor, Windsurf, or terminal adapters.

**Architecture:** Add pure transfer planning and bundle modules under `harness_manager/`, then wrap them with an onboarding-style wizard that reuses `onboard_ui.py` and `onboard_widgets.py`. Route the new `transfer` verb through `harness_manager.cli`, use existing adapter manifests for installation, and add shell/PowerShell import bootstrap scripts.

**Tech Stack:** Python stdlib, existing `harness_manager`, existing onboarding TUI primitives, unittest, bash, PowerShell.

---

### Task 1: Transfer Planning

**Files:**
- Create: `harness_manager/transfer_plan.py`
- Create: `test_transfer_plan.py`

- [x] **Step 1: Write failing tests for target, operation, and scope parsing**

Cover Codex/Cursor/Windsurf/terminal aliases, `all`, curl/export/apply intent, default scopes, sensitive scope opt-in, and adapter preview paths from manifests.

- [x] **Step 2: Run `python3 -m unittest test_transfer_plan.py -v` and verify it fails because `harness_manager.transfer_plan` is missing**

- [x] **Step 3: Implement `transfer_plan.py` with dataclasses, deterministic keyword parsing, target normalization, default scope selection, and manifest-backed adapter preview**

- [x] **Step 4: Run `python3 -m unittest test_transfer_plan.py -v` and verify it passes**

### Task 2: Bundle Export/Import

**Files:**
- Create: `harness_manager/transfer_bundle.py`
- Create: `test_transfer_bundle.py`

- [x] **Step 1: Write failing tests for bundle round-trip, digest verification, preferences merge, accepted lesson idempotency, and secret scan blocking**

- [x] **Step 2: Run `python3 -m unittest test_transfer_bundle.py -v` and verify it fails because `harness_manager.transfer_bundle` is missing**

- [x] **Step 3: Implement canonical JSON, gzip/base64 payloads, SHA-256 digests, safe file allowlisting, export from `.agent`, and import into temp projects**

- [x] **Step 4: Run `python3 -m unittest test_transfer_bundle.py -v` and verify it passes**

### Task 3: CLI and Wizard

**Files:**
- Create: `harness_manager/transfer_tui.py`
- Modify: `harness_manager/cli.py`
- Create: `test_transfer_cli.py`

- [x] **Step 1: Write failing tests for non-interactive `transfer --help`, `transfer export`, `transfer import`, and non-TTY wizard refusal**

- [x] **Step 2: Run `python3 -m unittest test_transfer_cli.py -v` and verify it fails because the verb is absent**

- [x] **Step 3: Add the `transfer` verb, argparse routing, non-interactive export/import helpers, and onboarding-style wizard flow**

- [x] **Step 4: Run `python3 -m unittest test_transfer_cli.py -v` and verify it passes**

### Task 4: Bootstrap Scripts and Windsurf Modernization

**Files:**
- Create: `scripts/import-transfer.sh`
- Create: `scripts/import-transfer.ps1`
- Create: `adapters/windsurf/.windsurf/rules/agentic-stack.md`
- Modify: `adapters/windsurf/adapter.json`
- Modify: `adapters/windsurf/README.md`
- Modify: `docs/per-harness/windsurf.md`
- Modify: `Formula/agentic-stack.rb`
- Create: `test_transfer_scripts.py`

- [x] **Step 1: Write failing tests that assert scripts exist, Windsurf manifest installs both modern and legacy rule files, and Formula packages scripts**

- [x] **Step 2: Run `python3 -m unittest test_transfer_scripts.py -v` and verify expected failures**

- [x] **Step 3: Add import bootstrap scripts, add modern Windsurf rule file, update manifest/docs, and ensure Formula packages `scripts`**

- [x] **Step 4: Run `python3 -m unittest test_transfer_scripts.py -v` and verify it passes**

### Task 5: Full Verification

**Files:**
- All touched code and docs

- [x] **Step 1: Run focused transfer tests**

Command:

```bash
python3 -m unittest test_transfer_plan.py test_transfer_bundle.py test_transfer_cli.py test_transfer_scripts.py -v
```

- [x] **Step 2: Run existing relevant regression tests**

Command:

```bash
python3 -m unittest test_memory_search.py test_data_layer_export.py test_data_flywheel_export.py -v
```

- [x] **Step 3: Run repository smoke checks**

Command:

```bash
python3 -m harness_manager.cli transfer --help
python3 -m harness_manager.cli transfer export --target codex --print-curl --yes
git diff --check
```

- [x] **Step 4: Commit implementation**

Command:

```bash
git add docs/superpowers/plans/2026-05-02-transfer-tui-wizard.md harness_manager/transfer_plan.py harness_manager/transfer_bundle.py harness_manager/transfer_tui.py harness_manager/cli.py scripts/import-transfer.sh scripts/import-transfer.ps1 adapters/windsurf/.windsurf/rules/agentic-stack.md adapters/windsurf/adapter.json adapters/windsurf/README.md docs/per-harness/windsurf.md Formula/agentic-stack.rb test_transfer_plan.py test_transfer_bundle.py test_transfer_cli.py test_transfer_scripts.py
git commit -m "feat: add transfer tui wizard"
```

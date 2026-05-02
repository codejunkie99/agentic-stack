# Transfer TUI Wizard Design

## Status

Approved direction: `agentic-stack transfer` opens a TUI wizard that matches the existing onboarding wizard style. The generated curl command is an output of the wizard, not the primary interface.

## Problem

Users want to move their agentic-stack memory and setup instructions across Codex, Cursor, Windsurf, and plain terminal environments without learning each tool's memory and rules file conventions. A one-line curl command is useful for moving the bundle into another project or machine, but the decision process is too sensitive for a raw command: users need to see what memory will move, which target harness files will be installed, and what will be merged before anything writes to disk.

## Research Findings

- Codex reads `AGENTS.md` guidance before work and supports layered global/project instruction discovery. Required team guidance should live in `AGENTS.md` or checked-in docs, not in generated Codex memory files.
- Codex skills are discovered from `.agents/skills` along the current directory to repository root path, and symlinked skill folders are supported.
- Codex memories are generated local state under `~/.codex/memories/`; importing agentic-stack memory should not edit those files.
- Cursor supports project rules in `.cursor/rules/*.mdc` with frontmatter, and root `AGENTS.md` is also supported for simple project instructions.
- Windsurf supports root and nested `AGENTS.md` files, workspace rules in `.windsurf/rules/*.md`, and generated/local memories. Durable shareable guidance should be represented as rules or `AGENTS.md`, not auto-generated Windsurf memories.
- Current `origin/master` already includes the manifest-driven `harness_manager/`, adapter manifests, and a Codex adapter. The transfer feature should build on that architecture instead of extending the older bash case statement installer.

Primary sources checked:

- <https://developers.openai.com/codex/guides/agents-md>
- <https://developers.openai.com/codex/memories>
- <https://developers.openai.com/codex/skills>
- <https://docs.cursor.com/en/context>
- <https://docs.windsurf.com/windsurf/cascade/memories>
- <https://docs.windsurf.com/windsurf/cascade/agents-md>

## Goals

1. Add an onboarding-style transfer TUI wizard launched by `agentic-stack transfer`.
2. Let users describe the transfer in natural language, then confirm or edit the parsed target and scope.
3. Export a portable, signed memory bundle that can be imported through a generated curl command.
4. Apply the transfer locally when requested, using the existing harness manager adapter installation path.
5. Preserve privacy by default: accepted lessons and preferences transfer; episodic logs, working memory, rejected candidates, and raw traces stay out unless explicitly selected.
6. Keep merge behavior transparent and reversible through preview, checksums, and existing git workflows.

## Non-Goals

- Do not write directly into `~/.codex/memories/`, Windsurf auto-generated memory files, Cursor generated memories, or any other tool-owned generated memory store.
- Do not build a hosted sync service.
- Do not require an LLM call for intent parsing in v1.
- Do not transfer secrets, raw shell history, raw prompts, unredacted run traces, or ignored runtime indexes.
- Do not replace the existing onboarding wizard.

## User Experience

Command:

```bash
agentic-stack transfer
```

The command opens a terminal wizard using the same visual language as `onboard.py`:

- `print_banner()` header with the agentic-stack wordmark.
- `intro()` section title for the transfer flow.
- `note()` blocks for explanations, warnings, and previews.
- `ask_text()`, `ask_select()`, `ask_multiselect()`, and `ask_confirm()` controls.
- `step_done()` collapsed summaries after each answer.
- `outro()` final result block with generated commands and verification steps.

The wizard is sequential, not full-screen. Each step should feel like the onboarding wizard: one focused question or preview at a time, a muted vertical rail, purple/blue/green/orange status colors, and no new TUI framework.

### Step 1: Intent

The user types a natural-language request, for example:

- `move my memory into Codex`
- `make this work in Cursor and Windsurf`
- `transfer preferences and lessons to another terminal`

The parser detects:

- targets: `codex`, `cursor`, `windsurf`, `terminal`, `all`
- operation: `apply-here`, `generate-curl`, `both`
- scope hints: `preferences`, `lessons`, `skills`, `working`, `episodic`

If parsing is uncertain, the wizard defaults to `all` targets only after showing a warning and requiring confirmation.

### Step 2: Target

The user edits detected targets through a multi-select list:

- Codex
- Cursor
- Windsurf
- Terminal / AGENTS.md only

`all` selects every target. The wizard shows exactly which adapter manifests will run.

### Step 3: Scope

Default selected:

- `.agent/memory/personal/PREFERENCES.md`
- accepted rows from `.agent/memory/semantic/lessons.jsonl`
- rendered semantic fallback from `.agent/memory/semantic/LESSONS.md` only when `lessons.jsonl` is missing
- `.agent/skills/` metadata and skill folders, excluding runtime stores

Default unselected:

- `.agent/memory/working/WORKSPACE.md`
- `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
- staged/rejected candidates
- `.agent/data-layer/`
- `.agent/flywheel/`
- `.agent/memory/.index/`
- skill-local runtime stores such as tldraw snapshots

Selecting a sensitive scope opens a privacy confirmation pane that explains the consequence and shows record counts.

### Step 4: Privacy

The wizard performs deterministic checks before export:

- file allowlist validation
- max bundle size check
- secret pattern scan for common tokens and private keys
- JSONL parse validation for structured memory
- redaction status check for flywheel records if a future version allows them

If a high-risk item is detected, the default action is to exclude it. The user can override only for files inside `.agent/` and only after a confirmation prompt.

### Step 5: Preview

The preview is the most important screen. It shows:

- files to create
- files to merge
- files to leave alone
- adapters to install
- skills link strategy for Codex: `.agents/skills -> .agent/skills`
- generated bundle digest
- generated curl command
- local apply command equivalent

No files are written before this screen is confirmed.

### Step 6: Apply

The user chooses one:

- `Apply here now`
- `Generate curl command`
- `Both`

The final screen shows:

- success or failure status for each action
- copied/generated curl command
- verification commands
- artifact path for the bundle manifest

Example final command:

```bash
curl -fsSL https://raw.githubusercontent.com/codejunkie99/agentic-stack/vX.Y.Z/scripts/import-transfer.sh | sh -s -- --target codex --payload '<base64-gz-json>' --sha256 '<digest>'
```

## Architecture

The feature has four layers:

1. Onboarding-style TUI orchestration.
2. Deterministic intent parsing and transfer planning.
3. Bundle export/import.
4. Adapter application through `harness_manager`.

### TUI Layer

Add a new module:

- `harness_manager/transfer_tui.py`

Responsibilities:

- render the onboarding-style transfer wizard
- manage sequential step state
- call pure planning/export/import functions
- show progress or status notes for operations over one second
- preserve terminal cursor visibility around arrow-key widgets

Toolkit: reuse the existing stdlib onboarding UI primitives in `onboard_ui.py` and `onboard_widgets.py`. If sharing those modules directly would create awkward imports, extract common display and input helpers into a small shared module and keep onboarding behavior unchanged. Do not add Textual, curses, Rich, prompt-toolkit, or any other new runtime TUI dependency for v1. The core import/export modules must remain dependency-light so non-interactive commands can run in CI and scripts.

### Planning Layer

Add:

- `harness_manager/transfer_plan.py`

Responsibilities:

- parse natural-language intent with deterministic keyword rules
- normalize target aliases
- define selected memory scopes
- produce a previewable transfer plan
- compute the files each target will install by reading existing adapter manifests

Intent parsing is intentionally simple in v1. The parser should prefer conservative uncertainty over pretending to understand ambiguous input.

### Bundle Layer

Add:

- `harness_manager/transfer_bundle.py`

Bundle format:

```json
{
  "schema_version": 1,
  "created_at": "2026-05-02T00:00:00Z",
  "source": {
    "agentic_stack_version": "0.13.0",
    "project_name": "example"
  },
  "targets": ["codex"],
  "scopes": ["preferences", "accepted_lessons", "skills"],
  "files": [
    {
      "path": ".agent/memory/personal/PREFERENCES.md",
      "encoding": "utf-8",
      "content_b64": "..."
    }
  ],
  "lessons": [
    {
      "id": "lesson_...",
      "claim": "...",
      "conditions": ["..."],
      "status": "accepted"
    }
  ],
  "warnings": []
}
```

Transport encoding:

- canonical JSON
- gzip
- base64url or shell-safe base64
- SHA-256 digest over compressed bytes

Import behavior:

- create `.agent/` if missing by using the agentic-stack template
- merge preferences under an `## Imported Preferences` section if the destination preferences file has custom content
- append accepted lessons idempotently into `lessons.jsonl`
- run `render_lessons.py` after lesson import
- copy or sync selected skills into `.agent/skills/`
- never overwrite `.agent/protocols/permissions.md`

### Curl Bootstrap Layer

Add:

- `scripts/import-transfer.sh`
- `scripts/import-transfer.ps1`

Responsibilities:

- decode payload
- verify digest
- locate or fetch agentic-stack
- call the Python importer
- install selected adapters through `harness_manager`

The shell and PowerShell scripts must fail closed: digest mismatch, unsupported schema, invalid target, or secret scan failure returns non-zero and writes no memory files.

## CLI Surface

Interactive:

```bash
agentic-stack transfer
```

Non-interactive support for generated scripts and tests:

```bash
agentic-stack transfer --intent "move my memory into Codex" --target codex --print-curl
agentic-stack transfer import --payload-file bundle.txt --sha256 <digest> --target codex
agentic-stack transfer export --target codex --scope preferences --scope accepted-lessons --json
```

Non-interactive commands are supporting surfaces, not the main UX.

## Adapter Behavior

### Codex

Install or merge:

- `AGENTS.md`
- `.agents/skills` symlink or sync from `.agent/skills`

Do not edit `~/.codex/memories/`.

### Cursor

Install:

- `.cursor/rules/agentic-stack.mdc`

If root `AGENTS.md` is already shared by another adapter and references `.agent/`, leave it alone.

### Windsurf

Preferred modern target:

- `.windsurf/rules/agentic-stack.md`

Legacy compatibility:

- keep `.windsurfrules` support until a later breaking release

The wizard should preview both if the current adapter manifest still installs `.windsurfrules`.

### Terminal

Install or merge:

- `AGENTS.md`

No tool-specific hooks.

## Packaging

The implementation must preserve the current dependency posture:

- Do not add a new runtime dependency for the wizard.
- Update Homebrew Formula packaging only to include any new Python modules and scripts.
- Keep core import/export code usable without the interactive wizard for scripts and tests.
- On non-TTY shells, never try to start the interactive wizard; print usage and suggest the non-interactive flags.
- On terminals without raw-key support, show an actionable error with fallback commands.

## Error Handling

- Ctrl-C or Escape exits without writing unless an apply operation has already begun.
- Apply operations write through temp files and atomic rename where possible.
- Import records a local manifest under `.agent/transfer/imports/`.
- Export records a local manifest under `.agent/transfer/exports/`.
- If adapter installation fails after memory import succeeds, the final screen must show partial success and the exact recovery command.
- Digest mismatch aborts before decode/import.
- Unsupported schema aborts with an upgrade hint.

## Testing

Unit tests:

- intent parsing
- target alias normalization
- scope defaults
- bundle canonicalization and digest verification
- preferences merge
- accepted lesson idempotency
- secret scan exclusion
- adapter plan preview

Integration tests:

- export then import into a temp repo for Codex
- export then import into a temp repo for Cursor
- export then import into a temp repo for Windsurf
- generated curl script path with a local file URL or fixture server
- non-TTY fallback behavior

TUI tests:

- wizard flow moves through every step
- cancellation before apply writes nothing
- preview note reflects selected targets and scopes
- collapsed step summaries render selected values
- final outro shows generated commands

Packaging tests:

- Homebrew formula test exercises `agentic-stack transfer --help` or a non-interactive export path
- PowerShell dispatch recognizes the transfer verb

## Resolved Implementation Decisions

1. Use the same stdlib, clack-style terminal UI as the onboarding wizard.
2. Generate a PowerShell-native transfer command on Windows instead of asking users to run `curl | sh`.
3. Modernize the Windsurf adapter inside this feature by adding `.windsurf/rules/agentic-stack.md`, while preserving `.windsurfrules` as a legacy compatibility output until a later breaking release.

## Success Criteria

- Running `agentic-stack transfer` opens an onboarding-style wizard in an interactive terminal.
- A user can export preferences, accepted lessons, and skills to a generated curl command.
- Pasting the curl command in a fresh project installs the selected adapter and imports memory into `.agent/`.
- Codex sees root `AGENTS.md` and `.agents/skills`.
- Cursor sees `.cursor/rules/agentic-stack.mdc`.
- Windsurf sees either modern `.windsurf/rules/agentic-stack.md` or the existing legacy `.windsurfrules`, with the chosen behavior shown in preview.
- No generated tool memory stores are edited directly.
- Non-sensitive scopes are default; sensitive scopes require explicit opt-in.

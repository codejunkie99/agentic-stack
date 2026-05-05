# agentic-stack Trust Console TUI Design

Date: 2026-05-05
Status: proposed
Owner: product/design

## Summary

The next agentic-stack product surface should be a TUI-first Trust Console:
a local terminal interface for inspecting agent memory, verifying harness
conformance, and separating personal knowledge from team knowledge.

The product promise is:

> Know what your agent remembers. Prove each harness respects it. Share the
> right lessons with your team.

The first version should stay local, fast, and scriptable. It should feel
closer to OpenClaw's terminal tooling than a web dashboard: compact status
views, strong `doctor` semantics, clear command help, JSON output for CI, and
an optional interactive `tui` mode for daily inspection.

## Inspiration

OpenClaw's CLI provides the design reference:

- `openclaw doctor` is the model for guided health checks and repairs.
- `openclaw status --json` is the model for pasteable and machine-readable
  diagnostics.
- `openclaw memory status/search/index` is the model for a memory-specific
  command family.
- `openclaw tui` is the model for a gateway-connected terminal workspace.
- Its command copy is concise, operational, and memorable without hiding the
  task.

agentic-stack should borrow the operating pattern, not the implementation:
local-first, terminal-native, status-oriented, and safe by default.

## Goals

- Give users a clear one-command view of whether `.agent/` is healthy.
- Make memory inspectable: accepted lessons, rejected candidates, evidence,
  stale queues, recent changes, and recall influence.
- Turn adapter support into a conformance standard that can be tested per
  harness.
- Introduce a team-brain layer without mixing team lessons into personal
  preferences.
- Preserve the existing lightweight install story and avoid requiring Node,
  Electron, or a daemon for the first milestone.

## Non-Goals

- No web UI in this milestone.
- No cloud sync.
- No multi-user permission server.
- No unattended promotion of memories.
- No dependency-heavy TUI framework unless the implementation plan shows a
  clear reason.

## Command Surface

The install wrapper should evolve from only adapter installation into a real
CLI front door:

```bash
agentic-stack install claude-code
agentic-stack doctor
agentic-stack tui
agentic-stack memory status
agentic-stack memory learned
agentic-stack memory rejected
agentic-stack memory why <lesson-id>
agentic-stack memory diff --since 2026-05-01
agentic-stack verify claude-code
agentic-stack verify cursor
agentic-stack verify opencode
agentic-stack team status
```

For backward compatibility, existing adapter shorthand should continue to
work:

```bash
agentic-stack claude-code --yes
```

Internally, this can dispatch to `install claude-code`.

## TUI Layout

The interactive TUI should use a stable three-pane terminal layout:

```text
agentic-stack Trust Console        project: /repo             health: 92%
----------------------------------------------------------------------------
  Doctor       Memory                           Selected: utc-timestamps
  Memory       ┌─ Overview ────────────────────────────────────────────────┐
  Verify       │ accepted  rejected  pending  episodes  stale queues       │
  Team Brain   │    12        4        1       348          0              │
  Skills       └───────────────────────────────────────────────────────────┘
  Settings

               ┌─ Lessons ─────────────────────┬─ Evidence ───────────────┐
               │ utc-timestamps        accepted │ source: learn.py         │
               │ deploy-approval       accepted │ rationale: ...          │
               │ flaky-test-triage     rejected │ evidence ids: 3         │
               └────────────────────────────────┴─────────────────────────┘

----------------------------------------------------------------------------
↑↓ move  enter open  / search  r refresh  j/k next  q quit  ? help
```

The design should be dense and operational:

- left rail for sections
- top status line for project, active instance, and health score
- main area for tables and summaries
- right or bottom detail panel for evidence and next actions
- fixed footer for keyboard help

## Section Design

### Doctor

Purpose: answer "is this brain healthy enough to trust?"

Shows:

- `.agent/` found or missing
- personal preferences present
- working memory present
- review queue age and count
- accepted lessons count
- candidate lifecycle counts
- malformed JSONL or candidate files
- hook configuration status
- adapter files present by harness
- ignored derived files present in `.gitignore`
- stale active instance or worker registry issues

Actions:

- refresh
- open detail
- run safe repair where available
- print pasteable report
- export JSON

### Memory

Purpose: answer "what did the agent learn, why, and what changed?"

Views:

- Overview
- Learned
- Rejected
- Pending
- Timeline
- Diff
- Why

`memory why <lesson-id>` must show:

- claim
- conditions
- source
- reviewer
- rationale
- evidence ids
- decision history
- render location
- whether it is shared, team, or personal

### Verify

Purpose: answer "does this harness actually use the brain?"

Initial checks should be deterministic and local:

- expected adapter file exists
- adapter file contains startup instructions
- adapter references `.agent/AGENTS.md`
- adapter references `PREFERENCES.md`
- adapter references `LESSONS.md`
- adapter references `permissions.md`
- adapter tells the harness to run `recall.py` before high-risk work
- adapter tells the harness to write reflections after significant actions

Later checks can add active harness probes where possible.

The TUI should present a matrix:

```text
harness       installed  memory  skills  recall  reflect  permissions
claude-code   pass       pass    pass    pass    pass     pass
cursor        pass       pass    pass    warn    warn     n/a
openclaw      pass       pass    pass    pass    warn     varies
```

### Team Brain

Purpose: answer "what knowledge is shared with the team, and what stays local?"

Proposed layout:

```text
.agent/memory/team/
  CONVENTIONS.md
  REVIEW_RULES.md
  DEPLOYMENT_LESSONS.md
  INCIDENTS.md
  APPROVED_SKILLS.md
```

Rules:

- `personal/` remains local-user preference memory.
- `team/` contains reviewed shared knowledge intended for Git.
- `semantic/` remains distilled learned memory.
- Team files are read before semantic lessons but after personal preferences
  when building context, so user preferences can still override team defaults.
- The TUI clearly labels each memory item as personal, team, semantic, or
  episodic.

## Data Flow

The TUI should not invent a parallel data store.

It reads from existing files:

- `.agent/AGENTS.md`
- `.agent/memory/personal/PREFERENCES.md`
- `.agent/memory/working/REVIEW_QUEUE.md`
- `.agent/memory/semantic/lessons.jsonl`
- `.agent/memory/semantic/LESSONS.md`
- `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
- `.agent/memory/candidates/**`
- `.agent/skills/_manifest.jsonl`
- `.agent/protocols/permissions.md`
- adapter files in the project root

It can call existing tools:

- `show.py`
- `list_candidates.py`
- `recall.py`
- `memory_search.py`
- `graduate.py`
- `reject.py`
- `reopen.py`

New shared logic should live in reusable modules, not inside terminal drawing
code. The same collectors should power:

- human TUI
- plain text reports
- JSON output
- future web UI

## Implementation Shape

The first implementation should stay Python-first because the repo already
ships a Python onboarding wizard, Python memory tooling, and a Homebrew wrapper
that installs Python files into `pkgshare`.

Recommended split:

```text
agentic_stack_cli.py          # main command router
.agent/tools/trust_model.py   # collectors and normalized health models
.agent/tools/trust_tui.py     # interactive terminal surface
.agent/tools/verify.py        # conformance checks
.agent/tools/team.py          # team-brain status/init helpers
```

The current `agentic-stack <adapter>` shorthand remains valid. New commands
route through `agentic_stack_cli.py`.

If a richer TUI framework is introduced later, it should consume the same
`trust_model.py` data model.

## TUI Interaction Rules

Follow these rules from the terminal-ui guide:

- Batch terminal output instead of flickering clear/redraw loops.
- Always provide escape routes: `q`, `esc`, and `ctrl-c`.
- Show progress for operations that can take more than one second.
- Support non-TTY fallback with plain text output.
- Support `--json` for every diagnostic command.
- Use color semantically: green pass, amber warning, red failure, blue active.
- Restore terminal state on exit.
- Use stable dimensions so changing table content does not shift the layout.

## Error Handling

- Missing `.agent/`: show install guidance and exit non-zero for `doctor`,
  but keep `agentic-stack install <adapter>` available.
- Malformed JSONL: report exact file and line where possible; do not delete.
- Corrupt candidates: report as quarantined or unreadable; do not silently skip
  in the TUI.
- Unknown harness: list supported harnesses and suggest `verify --all`.
- Non-TTY: render plain text, not an interactive screen.
- CI: default to non-interactive and JSON-friendly behavior.

## Testing

Add focused tests around the model layer before terminal rendering:

- doctor detects missing required files
- doctor detects stale review queue
- memory model loads accepted and rejected decisions
- `why` resolves lesson metadata and evidence references
- verify matrix catches missing recall instructions
- team status distinguishes personal, team, semantic, and episodic memory
- CLI preserves backward-compatible `agentic-stack claude-code --yes`
- non-TTY commands do not attempt interactive rendering

Terminal rendering can be verified with snapshot-style text tests for plain
mode first. Interactive key handling can be narrower: smoke-test startup,
navigation, and quit behavior.

## First Milestone

Ship a useful non-daemon TUI:

- `agentic-stack doctor`
- `agentic-stack doctor --json`
- `agentic-stack tui`
- `agentic-stack memory learned`
- `agentic-stack memory rejected`
- `agentic-stack memory why <id>`
- `agentic-stack verify --all`
- `agentic-stack team status`

This milestone should feel complete even without the later web dashboard.

## V1 Decisions

- `team/` is created only by `agentic-stack team init` in v1. Onboarding can
  mention Team Brain, but it should not create shared team files without an
  explicit user action.
- `tui` is read-only for memory lifecycle decisions in v1. Graduation,
  rejection, and reopening remain explicit CLI commands so review actions stay
  auditable and easy to reproduce.
- The default release uses a Python stdlib TUI. A richer optional TUI
  dependency can be considered later only if it consumes the same model layer
  and does not weaken the Homebrew/install simplicity.

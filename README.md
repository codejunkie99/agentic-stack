# agentic-stack

**Keep one portable memory-and-skills layer across coding-agent harnesses, so switching tools doesn't reset how your agent works.**

A portable `.agent/` folder (memory + skills + protocols) that plugs into Claude Code, Cursor, Windsurf, OpenCode, OpenClaw, Hermes, Pi Coding Agent, Codex, Antigravity, or a DIY Python loop — and keeps its knowledge when you switch.

It also includes a local data layer so you can monitor the whole suite of
agents from one place: harness activity, cron runs, active agents, token/cost
estimates, KPI summaries, user-defined resource categories, and
screenshot-ready daily dashboards.

<p align="center">
  <img src="docs/data-layer.svg" alt="agentic-stack data layer dashboard flow" width="880"/>
</p>

And it can turn approved, redacted runs into local flywheel artifacts:
trace records, context cards, eval cases, training-ready JSONL, and readiness
metrics without training a model or sending telemetry.

<p align="center">
  <img src="docs/demo.gif" alt="agentic-stack demo" width="880"/>
</p>

<p align="center">
  <img src="docs/diagram.svg" alt="agentic-stack architecture" width="880"/>
</p>

### New in v0.11.2 — natural dashboard access

Patch release. The data-layer skill is now the injected dashboard surface: a
model can decide to show the dashboard when a user asks naturally, without
making people remember exporter flags.

- **Injected dashboard skill.** The `data-layer` skill now triggers on plain
  phrases like "show me the dashboard" and "what did my agents do", then shows
  the terminal dashboard directly in the coding tool.
- **Natural-language exporter.** Users and agents can run
  `python3 .agent/tools/data_layer_export.py show me last 7 days by hour`;
  the exporter maps that to the right window and bucket while keeping explicit
  flags available for scripts.
- **Onboarding-style terminal view.** The dashboard now borrows the same
  rail, marker, and summary style as the onboarding flow, and still saves a
  plain `dashboard.tui.txt` beside `dashboard.html`, CSV, JSON, and
  `daily-report.md`.

See [CHANGELOG.md](CHANGELOG.md) for the full list.

### v0.11.0 — data layer + data flywheel

Added two local-first data capabilities for teams running multiple agent
harnesses against the same `.agent/` brain.

- **`data-layer` seed skill.** Generate local dashboard exports across Claude
  Code, Hermes, OpenClaw, Codex, Cursor, OpenCode, and custom loops:
  harness events, cron timelines, KPI summaries, token/cost estimates,
  categories, `dashboard.html`, and `daily-report.md`. The skill also acts as
  the injected natural-language surface for showing the terminal dashboard.
- **`data-flywheel` seed skill.** Export approved, redacted runs into trace
  records, context cards, eval cases, training-ready JSONL, and flywheel
  metrics. It is local-only and model-agnostic; it prepares artifacts but
  does not train models or call external APIs.

### v0.10.0 — design-md skill + Python 3.9 fix

Added the `design-md` seed skill for root `DESIGN.md` / Google Stitch
workflows, and fixed the Python 3.9 crash that hit macOS-default brew users
on first run.

### v0.9.1 — pi adapter fixes + tz correctness

Closed the gap between v0.9.0 and a working pi adapter, plus a timezone
sweep across every Python writer/reader so the dream cycle stops drifting
against the UTC decay window.

### v0.9.0 — harness manager

<p align="center">
  <img src="docs/harness-manager.svg" alt="harness manager v0.9.0" width="880"/>
</p>

Manifest-driven adapter system: every harness is now declared by an
`adapter.json`, applied by a shared Python backend, and managed via
verb subcommands or an interactive TUI. Cross-platform (POSIX +
Windows) with concurrent-write protection, pre-v0.9 migration via
`./install.sh doctor`, and shared-file ownership tracking so removing
one adapter never orphans another.

[![GitHub release](https://img.shields.io/github/v/release/codejunkie99/agentic-stack)](https://github.com/codejunkie99/agentic-stack/releases)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
Made by https://x.com/Av1dlive

## Quickstart

### macOS / Linux

```bash
# tap + install (one-time — both lines required)
brew tap codejunkie99/agentic-stack https://github.com/codejunkie99/agentic-stack
brew install agentic-stack

# drop the brain into any project — the onboarding wizard runs automatically
cd your-project
agentic-stack claude-code
# or: cursor | windsurf | opencode | openclaw | hermes | pi | codex | standalone-python | antigravity
```

### Windows (PowerShell)

```powershell
# clone + run the native installer
git clone https://github.com/codejunkie99/agentic-stack.git
cd agentic-stack
.\install.ps1 claude-code C:\path\to\your-project
```

### Already installed?

```bash
brew update && brew upgrade agentic-stack
```

### Clone instead?

```bash
git clone https://github.com/codejunkie99/agentic-stack.git
cd agentic-stack && ./install.sh claude-code         # mac / linux / git-bash
# or on Windows PowerShell: .\install.ps1 claude-code
# adapters: claude-code | cursor | windsurf | opencode | openclaw | hermes | pi | codex | standalone-python | antigravity
```

### Once installed: manage what's wired

After the first `./install.sh <adapter>`, manage your project with
verb-style subcommands (works with both `install.sh` and `install.ps1`):

```bash
./install.sh add cursor          # add a second adapter (Claude Code + Cursor in same repo)
./install.sh status              # one-screen view: which adapters, brain stats
./install.sh doctor              # read-only audit; green / yellow / red per adapter
./install.sh manage              # interactive TUI: header pane + menu loop for add/remove/audit
./install.sh remove cursor       # confirm prompt + delete; no quarantine, no undo
```

Bare `./install.sh` (no arguments) opens a **multi-select wizard** on
a fresh project — check every harness you actually use, hit enter,
each one gets installed. The wizard auto-detects harnesses already on
disk and pre-checks them. On a project that already has an
`install.json`, bare `./install.sh` lists what's still installable.
In non-TTY shells (CI), it prints usage and exits with code 2.

Upgrading from pre-v0.9? Run `./install.sh doctor` first — it
synthesizes `install.json` from on-disk adapter signals so the new
backend can track them. Installing on top without migration would
orphan the prior installs.

## Onboarding wizard

If you ran bare `./install.sh` (no adapter name), the wizard starts
with a **multi-select harness step**: it lists all 10 adapters, pre-
checks any it detects on disk, and installs each one you confirm with
space + enter. After the install(s), the preferences flow runs.

If you ran `./install.sh <adapter>` directly, only the preferences
flow runs.

Either way, the preferences step populates
`.agent/memory/personal/PREFERENCES.md` — the **first file your AI reads
at the start of every session** — and writes a feature-toggle file at
`.agent/memory/.features.json`.

Six preference questions (each skippable with Enter):

| Question | Default |
|---|---|
| What should I call you? | *(skip)* |
| Primary language(s)? | `unspecified` |
| Explanation style? | `concise` |
| Test strategy? | `test-after` |
| Commit message style? | `conventional commits` |
| Code review depth? | `critical issues only` |

Plus one **Optional features** step (opt-in, off by default):

| Feature | Default |
|---|---|
| Enable FTS memory search `[BETA]` | `no` |
| Enable tldraw visual canvas `[BETA]` | `no` |

**Flags:**

```bash
agentic-stack claude-code --yes          # accept all defaults, beta off (CI/scripted)
agentic-stack claude-code --reconfigure  # re-run the wizard on an existing project
```

Edit `.agent/memory/personal/PREFERENCES.md` any time to refine your
conventions, or `.agent/memory/.features.json` to flip feature toggles.

## Review protocol (host-agent CLI)

The nightly `auto_dream.py` cycle only **stages** candidate lessons. It
does not mark anything accepted or modify semantic memory. Your host
agent does the review in-session:

```bash
# list pending candidates, sorted by priority
python3 .agent/tools/list_candidates.py

# accept with rationale (required)
python3 .agent/tools/graduate.py <id> --rationale "evidence holds, matches PREFERENCES"

# reject with reason (required); preserves decision history
python3 .agent/tools/reject.py <id> --reason "too specific to generalize"

# requeue a previously-rejected candidate
python3 .agent/tools/reopen.py <id>
```

Graduated lessons land in `semantic/lessons.jsonl` (source of truth) and
are rendered to `semantic/LESSONS.md`. Rejected candidates retain full
decision history so recurring churn is visible, not fresh.

See [`docs/architecture.md`](docs/architecture.md) for the full lifecycle.

---

## What this is

Every guide shows the folder structure. This repo gives you the folder
structure **plus the files that actually go inside**: a working portable
brain with nine seed skills, four memory layers, enforced permissions, a
nightly staging cycle, host-agent review tools, and adapters for multiple
harnesses.

- **Memory** — `working/`, `episodic/`, `semantic/`, `personal/`. Each
  layer has its own retention policy. Query-aware retrieval (salience ×
  relevance); nightly compression into reviewable candidates.
- **Review protocol** — `auto_dream.py` stages candidate lessons
  mechanically. Your host agent reviews them via CLI tools
  (`graduate.py`, `reject.py`, `reopen.py`) and commits decisions with
  a required rationale. No unattended reasoning, no provider coupling.
- **Skills** — progressive disclosure. A lightweight manifest always
  loads; full `SKILL.md` files only load when triggers match the task.
  Every skill ships with a self-rewrite hook. The bundled `design-md`
  skill teaches agents to use a root `DESIGN.md` as the visual source of
  truth for UI and Google Stitch workflows.
- **Protocols** — typed tool schemas, a `permissions.md` that the
  pre-tool-call hook enforces, and a delegation contract for sub-agents.
- **Data layer** — local-only dashboard exports across every harness sharing
  `.agent/`: agent events, cron timelines, KPI summaries, tokens/cost
  estimates, task categories, harness mix, `dashboard.html`, and daily report
  handoff.
- **Data flywheel** — approved, redacted runs can become trace records,
  context cards, eval cases, training-ready JSONL, and readiness metrics
  without training a model or sending telemetry.

## Releases & changelog

Per-version release notes live in [CHANGELOG.md](CHANGELOG.md). The
latest release, what broke, what's new, upgrade path, all there.

## Memory search `[BETA]`

Opt-in FTS5 keyword search over all memory documents:

```bash
# enable during onboarding (or set manually in .agent/memory/.features.json)
python3 .agent/memory/memory_search.py "deploy failure"
python3 .agent/memory/memory_search.py --status
python3 .agent/memory/memory_search.py --rebuild
```

Falls back to **ripgrep** (`rg`) if installed, then to `grep` — both
restricted to `.md` / `.jsonl` so source files never pollute results.
The index is stored at `.agent/memory/.index/` and gitignored.

## Repo layout

```
.agent/                         # the portable brain (same across harnesses)
├── AGENTS.md                   # the map
├── harness/                    # conductor + hooks (standalone path)
│   └── hooks/
│       ├── claude_code_post_tool.py  # rich PostToolUse logging (v0.8+)
│       ├── pre_tool_call.py    # permissions enforcement
│       ├── post_execution.py   # log_execution() entry point
│       └── on_failure.py       # failure write + repeated-failure rewrite flag
├── memory/                     # working / episodic / semantic / personal
│   ├── auto_dream.py           # staging-only dream cycle
│   ├── cluster.py              # content clustering + pattern extraction
│   ├── promote.py              # stage candidates
│   ├── validate.py             # heuristic prefilter (length + exact duplicate)
│   ├── review_state.py         # candidate lifecycle + decision log
│   ├── render_lessons.py       # lessons.jsonl → LESSONS.md
│   └── memory_search.py        # [BETA] FTS5 search (opt-in)
├── skills/                     # _index.md + _manifest.jsonl + SKILL.md files
├── protocols/                  # permissions + tool schemas + delegation
│   └── hook_patterns.json      # user-owned high/medium-stakes regex (v0.8+)
└── tools/                      # host-agent CLI + memory_reflect + skill_loader
    ├── learn.py                # one-shot lesson teaching (stage + graduate)
    ├── recall.py               # surface lessons relevant to an intent
    ├── show.py                 # colorful brain-state dashboard
    ├── data_layer_export.py    # local cross-harness dashboard/data export
    ├── data_flywheel_export.py # approved runs -> traces/cards/evals/JSONL
    ├── list_candidates.py
    ├── graduate.py
    ├── reject.py
    └── reopen.py

adapters/                       # one small shim per harness, each with adapter.json manifest
├── claude-code/   (CLAUDE.md + settings.json hooks — $CLAUDE_PROJECT_DIR wired, closes #18)
├── cursor/        (.cursor/rules/*.mdc)
├── windsurf/      (.windsurfrules)
├── opencode/      (AGENTS.md + opencode.json)
├── openclaw/      (AGENTS.md + system-prompt include; auto-registers per-project agent)
├── hermes/        (AGENTS.md)
├── pi/            (AGENTS.md + .pi/skills symlink)
├── codex/         (AGENTS.md + .agents/skills symlink)
├── standalone-python/  (DIY conductor entrypoint)
└── antigravity/   (ANTIGRAVITY.md)

harness_manager/                # v0.9.0 manifest-driven Python backend
├── schema.py                   # adapter.json validator (path-safe on POSIX + Windows)
├── install.py                  # applies file entries per merge_policy
├── state.py                    # install.json read/write with fcntl/msvcrt locking
├── doctor.py                   # read-only audit + pre-v0.9 migration synthesis
├── remove.py                   # safe uninstall with shared-file detection + ownership handoff
├── post_install.py             # named built-ins (openclaw_register_workspace)
├── manage_tui.py               # interactive menu loop for add/remove/audit
└── cli.py                      # argparse dispatcher for install.sh / install.ps1

docs/                           # architecture, getting-started, per-harness
schemas/data-layer/             # local dashboard/event schemas
examples/data-layer/            # sanitized data-layer shapes
schemas/flywheel/               # data-flywheel artifact schemas
examples/flywheel/              # sanitized approved-run examples
install.sh                      # mac / linux / git-bash installer (thin Python dispatcher)
install.ps1                     # Windows PowerShell installer (thin Python dispatcher)
Formula/agentic-stack.rb        # Homebrew formula
CHANGELOG.md                    # per-version release notes (v0.1.0 onward)
onboard.py                      # onboarding wizard entry point
onboard_features.py             # .features.json read/write
onboard_ui.py                   # ANSI palette, banner, clack-style layout
onboard_widgets.py              # arrow-key prompts (text, select, confirm)
onboard_render.py               # answers → PREFERENCES.md content
onboard_write.py                # atomic file write with backup
test_claude_code_hook.py        # hook validation suite (54 checks)
verify_codex_fixes.py           # v0.8.0 regression checks (33 checks)
```

## Supported harnesses

| Harness | Config file it reads | Hook support |
|---|---|---|
| **Claude Code** | `CLAUDE.md` + `.claude/settings.json` | yes (PostToolUse, Stop) |
| **Cursor** | `.cursor/rules/*.mdc` | no (manual reflect calls) |
| **Windsurf** | `.windsurfrules` | no (manual reflect calls) |
| **OpenCode** | `AGENTS.md` + `opencode.json` | partial (permission rules) |
| **OpenClaw** | `AGENTS.md` (auto-injected) + per-project `openclaw agents add --workspace` | varies by fork |
| **Hermes Agent** | `AGENTS.md` (agentskills.io compatible) | partial (own memory) |
| **Pi Coding Agent** | `AGENTS.md` + `.pi/skills/` + `.pi/extensions/` | yes (`tool_result` event) |
| **Codex** | `AGENTS.md` + `.agents/skills/` | no (manual reflect calls) |
| **Standalone Python** | `run.py` (any LLM) | yes (full control) |
| **Antigravity** | `ANTIGRAVITY.md` | yes (system context) |

## Seed skills

- **skillforge** — creates new skills from recurring patterns
- **memory-manager** — runs reflection cycles, surfaces candidate lessons
- **git-proxy** — all git ops, with safety constraints
- **debug-investigator** — reproduce → isolate → hypothesize → verify
- **deploy-checklist** — the fence between staging and production
- **design-md** — uses Google Stitch-style `DESIGN.md` files as portable
  design-system context for UI, frontend, and component work
- **data-layer** — exports local dashboard data, cron timelines, KPIs, and
  daily reports across harnesses
- **data-flywheel** — approved runs into context cards, evals, redacted traces,
  training-ready JSONL, and flywheel metrics
- **tldraw** — opt-in beta skill for live canvas diagrams with a local
  snapshot store under `.agent/skills/tldraw/`

## How it compounds

1. Skills log every action to episodic memory.
2. `auto_dream.py` clusters recurring patterns into candidate lessons.
3. The host agent reviews candidates with `graduate.py` / `reject.py`.
4. Graduated lessons append to `lessons.jsonl`; `LESSONS.md` re-renders.
5. Future sessions load query-relevant accepted lessons automatically.
6. `on_failure` flags skills that fail 3+ times in 14 days for rewrite.
7. `git log .agent/memory/` becomes the agent's autobiography.
8. Data-layer exports turn local activity into dashboard-ready monitoring.
9. Approved, redacted runs can be exported into `.agent/flywheel/` artifacts
   for retrieval, evals, prompt shrinking, and optional future adapters.

## Export approved runs into a data flywheel

Put sanitized human-approved runs in:

```text
.agent/flywheel/approved-runs.jsonl
```

Then run:

```bash
python3 .agent/tools/data_flywheel_export.py
```

Outputs land in `.agent/flywheel/exports/<date>/`:

- `trace-records.jsonl`
- `training-examples.jsonl`
- `eval-cases.jsonl`
- `context-cards/<domain>/<workflow>.md`
- `flywheel-metrics.json`

This is local-only and model-agnostic. It creates training-ready artifacts; it
does not train a model.

See [docs/data-flywheel.md](docs/data-flywheel.md).

## Run the staging cycle nightly

```bash
crontab -e
0 3 * * * python3 /path/to/project/.agent/memory/auto_dream.py >> /path/to/project/.agent/memory/dream.log 2>&1
```

`auto_dream.py` resolves its paths absolutely and performs only mechanical
file operations (cluster, stage, prefilter, decay). No git commits, no
network, no reasoning — safe to run unattended.

## Monitor your agent suite

Generate a local dashboard for all harnesses writing to the same `.agent/`
brain:

```bash
python3 .agent/tools/data_layer_export.py --window 30d --bucket day
```

Or let the injected `data-layer` skill pass the user's words through:

```bash
python3 .agent/tools/data_layer_export.py show me last 7 days by hour
```

Outputs land in `.agent/data-layer/exports/<date>/`, including
`dashboard.html`, `dashboard.tui.txt`, and `daily-report.md`. The command also
prints the onboarding-style terminal dashboard directly inside your coding tool.
Optional local inputs let you add scheduled runs and categories:

```text
.agent/data-layer/cron-runs.jsonl
.agent/data-layer/category-rules.json
.agent/data-layer/harness-events.jsonl
```

Use this to track crons by day, active agents, token/cost estimates by
hour/day/week/month, harness mix across Claude/Hermes/OpenClaw/Codex/etc.,
success/error rates, run cadence, workflow breadth, and user-defined categories
like personal, admin, work, financial, and coding. The data layer is local-only;
screenshot delivery requires explicit user approval and a user-configured
channel.

See [docs/data-layer.md](docs/data-layer.md).

## License

Apache 2.0 — see [LICENSE](LICENSE).

## Credits

Based on the article **["The Agentic Stack"](https://x.com/Av1dlive/status/2044453102703841645?s=20)**
by [@AV1DLIVE](https://twitter.com/AV1DLIVE) — follow for updates and collabs.
Coded using Minimax-M2.7 in the Claude Code harness; PR review by Macroscope and Codex.
Patterns from Gstack, Claude Code's memory system, and conversations in the
agent-engineering community. Built with the hypothesis that
**harness-agnosticism is the point**.

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=codejunkie99/agentic-stack&type=Date)](https://star-history.com/#codejunkie99/agentic-stack&Date)

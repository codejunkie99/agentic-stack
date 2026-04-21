# agentic-stack

**Keep one portable memory-and-skills layer across coding-agent harnesses, so switching tools doesn't reset how your agent works.**

A portable `.agent/` folder (memory + skills + protocols) that plugs into Claude Code, Cursor, Windsurf, OpenCode, OpenClaw, Hermes, Pi Coding Agent, or a DIY Python loop — and keeps its knowledge when you switch.

<p align="center">
  <img src="docs/demo.gif" alt="agentic-stack demo" width="880"/>
</p>

<p align="center">
  <img src="docs/diagram.svg" alt="agentic-stack architecture" width="880"/>
</p>

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
# or: cursor | windsurf | opencode | openclaw | hermes | pi | standalone-python
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
# adapters: claude-code | cursor | windsurf | opencode | openclaw | hermes | pi | standalone-python
```

## Onboarding wizard

After the adapter is installed, a terminal wizard populates
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
brain with five seed skills, four memory layers, enforced permissions, a
nightly staging cycle, host-agent review tools, and adapters for eight
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
  Every skill ships with a self-rewrite hook.
- **Protocols** — typed tool schemas, a `permissions.md` that the
  pre-tool-call hook enforces, and a delegation contract for sub-agents.

## What's new in v0.7.0

- **Three host-agent tools that make the brain usable from day one.**
  - `learn.py` — teach the agent a rule in one command:
    `python3 .agent/tools/learn.py "Always serialize timestamps in UTC" --rationale "past cross-region bugs"`.
    Stages + graduates + renders in one step. Idempotent. Cleans up staged
    files on heuristic reject; preserves on crashes so retries work.
  - `recall.py` — surface graduated lessons relevant to what you're about
    to do: `python3 .agent/tools/recall.py "add a created_at column"`.
    Returns ranked lexical-overlap hits with per-entry source labels.
    Merges `lessons.jsonl` and seed bullets in `LESSONS.md` so graduating
    your first lesson doesn't hide the seeds. Logs every recall to
    episodic memory for audit.
  - `show.py` — colorful dashboard of brain state (episodes, candidates,
    lessons, failing skills, 14d activity sparkline). `--json` / `--plain`
    / `NO_COLOR` flags.
- **Adapter wiring for recall across all 8 harnesses.** Every adapter
  (`claude-code`, `cursor`, `windsurf`, `opencode`, `openclaw`, `hermes`,
  `pi`, `standalone-python`) now instructs the model to run
  `recall.py "<intent>"` before deploy / migration / timestamp / debug /
  refactor work, and to surface results in a `Consulted lessons before
  acting:` block.
- **Seed UTC lesson ships pre-graduated.** New installs see proactive
  recall return a real hit on first try — no setup ceremony for the
  demo path. Stored at `.agent/memory/semantic/lessons.jsonl`.
- **Reliability fixes.**
  - `pattern_id` canonicalizes conditions (casefold, unicode-whitespace
    collapse, zero-width strip, dedupe, sort) — so the same logical set
    always yields the same id.
  - `validate.heuristic_check` now requires ≥3 content words in a claim
    (blocks junk like `!!!abc` that passed the raw-length gate).
  - `graduate.py` retry path is idempotent: re-renders `LESSONS.md`,
    honors original reviewer/rationale from `lessons.jsonl` to keep
    stores in sync, refuses retries against legacy rows missing
    metadata.
  - `render_lessons` + `append_lesson` now hold an advisory exclusive
    flock on `lessons.jsonl`. Concurrent writers serialize; `LESSONS.md`
    can no longer be stale relative to `lessons.jsonl`. Atomic rewrite
    via temp file + rename.

## What's new in v0.6.0

- **Pi Coding Agent adapter.** `./install.sh pi` drops `AGENTS.md` and
  symlinks `.pi/skills` to `.agent/skills` so pi sees the full brain
  with zero duplication. Safe to install alongside hermes/opencode
  (they all read `AGENTS.md`; we skip the overwrite if one exists).
- **OpenClient → OpenClaw.** Adapter renamed across the board.
  Installed file changed: `.openclient-system.md` → `.openclaw-system.md`.
  Breaking for existing OpenClient users — re-run `./install.sh openclaw`.

## What's new in v0.5.0

- **Host-agent review protocol.** Python handles filing (cluster, stage,
  heuristic prefilter, decay). The host agent handles reasoning via
  `list_candidates.py` / `graduate.py` / `reject.py` / `reopen.py`.
  Graduation requires `--rationale` so rubber-stamping is structurally
  impossible.
- **Structured `lessons.jsonl` as source of truth.** `LESSONS.md` is
  rendered from it. Hand-curated content above the sentinel is
  preserved across renders; legacy bullets auto-migrate on first run.
- **Content clustering.** Proper single-linkage Jaccard with bridge
  merging. Pattern IDs derived from canonical claim + conditions, stable
  across cluster-membership changes.
- **[BETA] FTS5 memory search.** Opt-in full-text search over all
  `.md` / `.jsonl` memory documents. Default **off**; enable during
  onboarding or edit `.agent/memory/.features.json` directly.
- **Windows-native installer.** `install.ps1` runs natively in
  PowerShell; `install.sh` continues to work under Git Bash / WSL.


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
└── tools/                      # host-agent CLI + memory_reflect + skill_loader
    ├── learn.py                # one-shot lesson teaching (stage + graduate)
    ├── recall.py               # surface lessons relevant to an intent
    ├── show.py                 # colorful brain-state dashboard
    ├── list_candidates.py
    ├── graduate.py
    ├── reject.py
    └── reopen.py

adapters/                       # one small shim per harness
├── claude-code/   (CLAUDE.md + settings.json hooks)
├── cursor/        (.cursor/rules/*.mdc)
├── windsurf/      (.windsurfrules)
├── opencode/      (AGENTS.md + opencode.json)
├── openclaw/      (system-prompt include)
├── hermes/        (AGENTS.md)
├── pi/            (AGENTS.md + .pi/skills symlink)
└── standalone-python/  (DIY conductor entrypoint)

docs/                           # architecture, getting-started, per-harness
install.sh                      # mac / linux / git-bash installer
install.ps1                     # Windows PowerShell installer
onboard.py                      # onboarding wizard entry point
onboard_features.py             # .features.json read/write
onboard_ui.py                   # ANSI palette, banner, clack-style layout
onboard_widgets.py              # arrow-key prompts (text, select, confirm)
onboard_render.py               # answers → PREFERENCES.md content
onboard_write.py                # atomic file write with backup
```

## Supported harnesses

| Harness | Config file it reads | Hook support |
|---|---|---|
| **Claude Code** | `CLAUDE.md` + `.claude/settings.json` | yes (PostToolUse, Stop) |
| **Cursor** | `.cursor/rules/*.mdc` | no (manual reflect calls) |
| **Windsurf** | `.windsurfrules` | no (manual reflect calls) |
| **OpenCode** | `AGENTS.md` + `opencode.json` | partial (permission rules) |
| **OpenClaw** | system-prompt include | varies by fork |
| **Hermes Agent** | `AGENTS.md` (agentskills.io compatible) | partial (own memory) |
| **Pi Coding Agent** | `AGENTS.md` + `.pi/skills/` | no (extension system) |
| **Standalone Python** | `run.py` (any LLM) | yes (full control) |

## Seed skills

- **skillforge** — creates new skills from recurring patterns
- **memory-manager** — runs reflection cycles, surfaces candidate lessons
- **git-proxy** — all git ops, with safety constraints
- **debug-investigator** — reproduce → isolate → hypothesize → verify
- **deploy-checklist** — the fence between staging and production

## How it compounds

1. Skills log every action to episodic memory.
2. `auto_dream.py` clusters recurring patterns into candidate lessons.
3. The host agent reviews candidates with `graduate.py` / `reject.py`.
4. Graduated lessons append to `lessons.jsonl`; `LESSONS.md` re-renders.
5. Future sessions load query-relevant accepted lessons automatically.
6. `on_failure` flags skills that fail 3+ times in 14 days for rewrite.
7. `git log .agent/memory/` becomes the agent's autobiography.

## Run the staging cycle nightly

```bash
crontab -e
0 3 * * * python3 /path/to/project/.agent/memory/auto_dream.py >> /path/to/project/.agent/memory/dream.log 2>&1
```

`auto_dream.py` resolves its paths absolutely and performs only mechanical
file operations (cluster, stage, prefilter, decay). No git commits, no
network, no reasoning — safe to run unattended.

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

# agentic-stack

Follow me on : [@AV1DLIVE](https://twitter.com/AV1DLIVE) for updates/collabs on projects

[![GitHub release](https://img.shields.io/github/v/release/codejunkie99/agentic-stack)](https://github.com/codejunkie99/agentic-stack/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

> **One brain, many harnesses.** A portable `.agent/` folder (memory + skills
> + protocols) that plugs into Claude Code, Cursor, Windsurf, OpenCode,
> OpenClient, Hermes, or a DIY Python loop — and keeps its knowledge when
> you switch.

<p align="center">
  <img src="docs/demo.gif" alt="agentic-stack demo" width="880"/>
</p>

<p align="center">
  <img src="docs/diagram.svg" alt="agentic-stack architecture" width="880"/>
</p>


Based on the article:
**["The Agentic Stack"](https://x.com/Av1dlive/status/2044453102703841645?s=20)** · by [@AV1DLIVE](https://twitter.com/AV1DLIVE)

---

## What this is

Every guide shows the folder structure. This repo gives you the folder
structure **plus the files that actually go inside** — a working portable
brain with five seed skills, four memory layers, enforced permissions, a
nightly dream cycle, and adapters for seven harnesses.

- **Memory** — `working/`, `episodic/`, `semantic/`, `personal/`. Each
  layer has its own retention policy. Salience-scored retrieval; nightly
  compression.
- **Skills** — progressive disclosure. A lightweight manifest always loads;
  full `SKILL.md` files only load when triggers match the task. Every
  skill ships with a self-rewrite hook.
- **Protocols** — typed tool schemas, a `permissions.md` that the
  pre-tool-call hook enforces, and a delegation contract for sub-agents.

## Quickstart

```bash
# tap + install (one-time — both lines required)
brew tap codejunkie99/agentic-stack https://github.com/codejunkie99/agentic-stack
brew install agentic-stack

# drop the brain into any project — the onboarding wizard runs automatically
cd your-project
agentic-stack claude-code
# or: cursor | windsurf | opencode | openclient | hermes | standalone-python
```

> **Already installed? Update to the latest version:**
> ```bash
> brew update && brew upgrade agentic-stack
> ```

> **Clone instead?**
> ```bash
> git clone https://github.com/codejunkie99/agentic-stack.git
> cd agentic-stack && ./install.sh claude-code
> ```

## Onboarding wizard

After the adapter is installed, a colorful terminal wizard runs automatically
and populates `.agent/memory/personal/PREFERENCES.md` — the **first file your
AI reads at the start of every session**.

It asks six questions with arrow-key selection, each skippable with Enter:

| Question | Default |
|---|---|
| What should I call you? | *(skip)* |
| Primary language(s)? | `unspecified` |
| Explanation style? | `concise` |
| Test strategy? | `test-after` |
| Commit message style? | `conventional commits` |
| Code review depth? | `critical issues only` |

**Flags:**

```bash
agentic-stack claude-code --yes          # accept all defaults silently (CI / scripted)
agentic-stack claude-code --reconfigure  # re-run the wizard on an existing project
```

Edit `.agent/memory/personal/PREFERENCES.md` any time to add or refine your
conventions — the agent re-reads it fresh every session.

## Repo layout

```
.agent/                         # the portable brain (same across all harnesses)
├── AGENTS.md                   # the map
├── harness/                    # dumb conductor + hooks (standalone path)
├── memory/                     # working / episodic / semantic / personal
├── skills/                     # _index.md + _manifest.jsonl + SKILL.md files
├── protocols/                  # permissions + tool schemas + delegation
└── tools/                      # skill loader, memory reflect, budget tracker

adapters/                       # one small shim per harness
├── claude-code/   (CLAUDE.md + settings.json hooks)
├── cursor/        (.cursor/rules/*.mdc)
├── windsurf/      (.windsurfrules)
├── opencode/      (AGENTS.md + opencode.json)
├── openclient/    (system-prompt include)
├── hermes/       (AGENTS.md)
└── standalone-python/  (DIY conductor entrypoint)

docs/                           # architecture, getting-started, per-harness
examples/                       # minimal first_run.py
install.sh                      # one-command adapter install + wizard trigger
onboard.py                      # onboarding wizard entry point
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
| **OpenClient** | system-prompt include | varies by fork |
| **Hermes Agent** | `AGENTS.md` (agentskills.io compatible) | partial (own memory) |
| **Standalone Python** | `run.py` (any LLM) | yes (full control) |

## Seed skills

- **skillforge** — creates new skills from recurring patterns
- **memory-manager** — runs reflection cycles, promotes lessons
- **git-proxy** — all git ops, with safety constraints
- **debug-investigator** — reproduce → isolate → hypothesize → verify
- **deploy-checklist** — the fence between staging and production

## How it compounds

1. Skills log every action to episodic memory.
2. `memory-manager` detects recurring patterns, promotes them to semantic.
3. `on_failure` flags skills that fail 3+ times in 14 days for rewrite.
4. Self-rewrite hooks on each skill update `KNOWLEDGE.md` conservatively.
5. `git log .agent/memory/` becomes the agent's autobiography.

See [`docs/architecture.md`](docs/architecture.md) for the full picture.

## Run the dream cycle nightly

```bash
crontab -e
0 3 * * * python3 /path/to/project/.agent/memory/auto_dream.py >> /path/to/project/.agent/memory/dream.log 2>&1
```

`auto_dream.py` resolves its own paths absolutely, so no `cd` is needed — cron runs it correctly regardless of working directory.

## License

MIT — see [LICENSE](LICENSE).

## Credits

Design adapted from the author's article on building an agentic stack, plus
patterns from Gstack, Claude Code's memory system, and conversations in
the agent-engineering community. Built with the hypothesis that
**harness-agnosticism is the point**.

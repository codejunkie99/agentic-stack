# Pi Coding Agent adapter

[Pi Coding Agent](https://github.com/badlogic/pi-mono) by Mario Zechner
is a minimalist terminal coding harness with multi-provider LLM support
and a TypeScript extension system. Our adapter layers the portable
`.agent/` brain on top so you keep one knowledge base even if you later
swap harnesses. For shell commands that must be checked before execution,
use `python3 .agent/tools/ztk.py exec -- <command>`.

## Install
```bash
./install.sh pi
```

Or on Windows PowerShell:
```powershell
.\install.ps1 pi C:\path\to\your-project
```

Then install pi itself:
```bash
npm install -g @mariozechner/pi-coding-agent
```

## What it wires up
- **`AGENTS.md`** — pi reads this natively as workspace-level context.
  Points at `.agent/`. Skipped if `AGENTS.md` already exists (e.g. from
  the hermes or opencode adapter — pi reads the same file).
- **`.pi/skills/`** → symlink to `.agent/skills/`. Pi scans this path at
  startup. Customize under `.agent/skills/`; pi sees it immediately via
  `/reload`.
- **`.pi/extensions/memory-hook.ts`** — project-local TypeScript
  extension auto-discovered by pi at startup. It:
  - Logs `bash`, `edit`, and `write` tool results directly to
    `AGENT_LEARNINGS.jsonl` (no Python subprocess per call — all
    scoring is inline TypeScript).
  - Skips `read`/`find`/`ls`/`grep` and noise-level bash calls to keep
    the episodic log signal-rich.
  - Runs `auto_dream.py` when the session ends (quit, new session, or
    resume) — mirrors Claude Code's `Stop` hook.

## Coexisting with other adapters
Pi, hermes, and opencode all read `AGENTS.md`. You can install any
combination — only the first one to run writes the root `AGENTS.md`;
subsequent installs skip it.

## Verify
Start pi and run any bash command or edit a file. Then:

```bash
tail -1 .agent/memory/episodic/AGENT_LEARNINGS.jsonl
```

You should see a JSON entry with `"skill": "pi"`. The `action` field
reflects the tool that ran and the `reflection` field is what the dream
cycle clusters on.

In pi, ask "what's in my LESSONS file?" — it should read
`.agent/memory/semantic/LESSONS.md`.

## Optional
- Drop `.pi/SYSTEM.md` at project root to replace pi's default system
  prompt entirely.
- Prompt templates go in `.pi/prompts/`.
- For a fallback dream cycle (e.g. if you kill pi rather than quitting
  cleanly), add a cron entry:
  ```
  0 3 * * * python3 /path/to/project/.agent/memory/auto_dream.py \
    >> /path/to/project/.agent/memory/dream.log 2>&1
  ```

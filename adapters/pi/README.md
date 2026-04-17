# Pi Coding Agent adapter

[Pi Coding Agent](https://github.com/badlogic/pi-mono) by Mario Zechner
is a minimalist terminal coding harness with multi-provider LLM support
and an extension system. Our adapter layers the portable `.agent/` brain
on top so you keep one knowledge base even if you later swap harnesses.

## Install
```bash
./install.sh pi
```

Then install pi itself:
```bash
npm install -g @mariozechner/pi-coding-agent
```

## What it wires up
- `AGENTS.md` — pi reads this natively as workspace-level context.
  Points at `.agent/`. **Skipped if `AGENTS.md` already exists**
  (e.g. from the hermes or opencode adapter — pi reads the same file,
  so you don't need a second copy).
- `.pi/skills/` → symlink to `.agent/skills/`. Pi scans this path at
  startup. Symlink means there's one source of truth; customize under
  `.agent/skills/` and pi sees it immediately.
- `.pi/` directory is created even if empty — ready for optional pi
  extensions, prompt templates, and `.pi/SYSTEM.md` overrides.

## Coexisting with other adapters
Pi, hermes, and opencode all read `AGENTS.md`. You can install any
combination — only the first one to run writes the root `AGENTS.md`;
subsequent installs are no-ops on that file.

## Verify
In pi: ask "what's in my LESSONS file?" — it should read
`.agent/memory/semantic/LESSONS.md`.

## Optional
If pi's default system prompt doesn't fit your workflow, drop a
`.pi/SYSTEM.md` at project root. Pi uses it as a complete override.

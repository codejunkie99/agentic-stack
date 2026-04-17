# Pi Coding Agent setup

[Pi Coding Agent](https://github.com/badlogic/pi-mono) (by Mario
Zechner) is a minimalist terminal coding harness with 15+ LLM providers
and a TypeScript extension system. Our adapter layers the portable
`.agent/` brain on top so you keep one knowledge base across harnesses.

## What the adapter installs
- `AGENTS.md` at project root (pi reads this natively). Skipped if one
  already exists, since pi/hermes/opencode share this file.
- `.pi/` directory
- `.pi/skills` symlinked to `.agent/skills` (falls back to copy on
  platforms without symlinks, e.g. Windows without developer mode)

## Install
```bash
./install.sh pi
npm install -g @mariozechner/pi-coding-agent
pi
```

## How it works
- Pi loads `AGENTS.md` (or `CLAUDE.md`) from `~/.pi/agent/` and walks
  the current directory up to the filesystem root, aggregating
  context.
- Skills at `.pi/skills/<name>/SKILL.md` use the same frontmatter-plus
  -body shape as agentskills.io and our `.agent/skills/` layout.
- Pi extensions live in `.pi/extensions/` (TypeScript, optional).

## Troubleshooting
- If pi doesn't see your skills, run `pi skills list` — it should
  print entries from `.pi/skills/`. If the directory is a broken
  symlink, re-run `./install.sh pi` to rebuild.
- On Windows without symlink support, the installer copies
  `.agent/skills/` instead. Changes to `.agent/skills/` won't
  propagate — re-run the installer to sync.
- Pi's multi-provider gateway is independent of the brain. The
  portable `.agent/` doesn't care which model you use.

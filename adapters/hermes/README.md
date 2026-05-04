# Hermes Agent adapter

[Hermes Agent](https://github.com/nousresearch/hermes-agent) by Nous
Research is an open-source agent with its own persistent memory layer
and agentskills.io-compatible skill support. Our adapter layers the
portable `.agent/` files on top for shared memory and skills. Hermes does
not expose Claude Code's `PreToolUse` hook, so permission enforcement is
best-effort prompt discipline here.

## Install
```bash
cp adapters/hermes/AGENTS.md ./AGENTS.md
```

Or:
```bash
./install.sh hermes
```

## What it wires up
- `AGENTS.md` — Hermes reads this natively as workspace-level context;
  we point it at `.agent/`.
- Skills in `.agent/skills/` use the same frontmatter-plus-body shape
  Hermes expects. Browse via `/skills` in the Hermes CLI.

## Optional: mirror into Hermes's own memory
Hermes has its own `MEMORY.md` / `USER.md` / `SOUL.md` files. They are
complementary, not replacements. If you want high-signal lessons
visible inside Hermes's built-in persistence, symlink:

```bash
ln -s .agent/memory/personal/PREFERENCES.md USER.md
```

## Verify
In Hermes: "What's in my LESSONS file?" — it should read
`.agent/memory/semantic/LESSONS.md`.

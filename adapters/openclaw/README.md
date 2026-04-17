# OpenClaw adapter

## Install
OpenClaw doesn't have a project-root convention file the way Claude Code
or Cursor does. Two options:

**Option A (recommended):** Point OpenClaw at the config file:

```bash
cp adapters/openclaw/config.md ./.openclaw-system.md
# then configure OpenClaw to load this as its system prompt
```

**Option B:** Paste the contents of `config.md` into OpenClaw's system
prompt settings directly.

Or:
```bash
./install.sh openclaw
```

## What it wires up
A system-prompt include that instructs the agent to treat `.agent/` as
authoritative on every session.

## Verify
Ask "Read my lessons file." — it should open `.agent/memory/semantic/LESSONS.md`.

## Notes
OpenClaw varies by version; some forks support `.openclaw/` folders,
others use a single config file. Check your version's docs for where to
point the system prompt.

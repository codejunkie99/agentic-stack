# Antigravity adapter

## Install
```bash
./install.sh antigravity
```

## What it wires up
The Antigravity adapter drops `ANTIGRAVITY.md` into the project root. This file provides
the system context needed for the agent to utilize the portable brain in `.agent/`.

## Verify
Ask the agent "What's in your lessons file?" — it should read
`.agent/memory/semantic/LESSONS.md`.

## Notes
The Antigravity ruleset ensures that the agent is aware of the `agentic-stack`
protocols and memory management tools, enabling knowledge persistence across sessions.
It is designed to be compatible with any agent that respects root-level instruction
files similar to `CLAUDE.md`.

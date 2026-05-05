# OpenClaw adapter

OpenClaw auto-injects `AGENTS.md` (and `SOUL.md`, `MEMORY.md`, etc.) from
the **workspace root** into the system prompt. The only catch: OpenClaw's
default workspace is `~/.openclaw/workspace`, not the project you ran
`install.sh` from. So wiring the brain is two things:

1. Drop an `AGENTS.md` at the project root that points at `.agent/`.
2. Register a project-scoped OpenClaw agent whose workspace IS the project.

`./install.sh openclaw` does both automatically.

## Install
```bash
./install.sh openclaw
```

What it drops into `$TARGET`:
- `AGENTS.md` — auto-injected by OpenClaw (skipped if you already have one
  that references `.agent/`)
- `.openclaw-system.md` — backward-compat include for forks that take a
  `--system-prompt-file` flag
- A registered OpenClaw agent named `<basename>-<hash>` with
  `--workspace <abs-path>`

If `openclaw` isn't on PATH, the installer still writes the files and
prints the exact `openclaw agents add` command to run later.

## Run
```bash
openclaw --agent <basename>-<hash>
```

The exact agent name is printed at the end of the install.

## Verify
Ask "Read my lessons file." — the agent should open
`.agent/memory/semantic/LESSONS.md`.

## If AGENTS.md already exists in your project
The installer won't overwrite it. It detects whether the existing file
already references `.agent/`:
- Already references `.agent/` → leaves it alone.
- Doesn't → prints a snippet you can paste in to wire the brain.

## Notes
OpenClaw varies by version; older forks may not support `agents add` or
may expect a different flag. The `.openclaw-system.md` file is provided
as a fallback you can point at with `--system-prompt-file` or paste into
settings directly. Check your version's docs.

# OpenClaw setup

## What the adapter installs
- `AGENTS.md` at project root — OpenClaw auto-injects this from the
  workspace. Skipped if an existing `AGENTS.md` already references
  `.agent/`; a mergeable snippet is printed if not.
- `.openclaw-system.md` at project root — backward-compat include for
  older forks / `--system-prompt-file` flows.
- A registered OpenClaw agent named `<basename>-<hash>` with
  `--workspace <abs-path-of-project>` so OpenClaw treats the project
  (not `~/.openclaw/workspace`) as the workspace.

## Install
```bash
./install.sh openclaw
```

Then:
```bash
openclaw --agent <basename>-<hash>
```

The exact agent name is printed at the end of the install output.

## How it works
OpenClaw reads its workspace bootstrap files (`AGENTS.md`, `SOUL.md`,
`MEMORY.md`, `TOOLS.md`, `IDENTITY.md`, `USER.md`, `HEARTBEAT.md`,
`BOOTSTRAP.md`) verbatim into the system prompt. The installed
`AGENTS.md` tells the agent to consult `.agent/` — memory, skills,
protocols — on every session.

OpenClaw's default workspace is `~/.openclaw/workspace`, not the current
directory. The installer registers a per-project agent
(`openclaw agents add <name> --workspace <abs-path>`) so the workspace
resolves to the project and the `.agent/` brain is visible.

## If `openclaw` isn't on PATH
The installer still writes `AGENTS.md` and `.openclaw-system.md`, then
prints the exact `openclaw agents add` command to run once you've
installed OpenClaw.

## Re-running `install.sh`
Safe. The `.agent/` brain is left alone if present. `AGENTS.md` is
re-detected (no overwrite). Re-registering the same agent name against
the same workspace is a no-op for compatible OpenClaw versions; older
versions may error — that's surfaced in the install output.

OpenClaw does not provide ztk with a hard pre-tool gate in this adapter.
Use `python3 .agent/tools/ztk.py exec -- <command>` for shell commands
that must be checked by `.agent/protocols/permissions.md`.

## Troubleshooting
- Agent runs but ignores `.agent/`: confirm the agent's workspace with
  `openclaw agents list` or `openclaw config edit`. It should match the
  absolute path of your project.
- `openclaw agents add` fails: your OpenClaw version may not support
  `--workspace`. Fall back to `.openclaw-system.md` via
  `--system-prompt-file .openclaw-system.md`.
- You see `AGENTS.md already references .agent/ — leaving alone`: that's
  intentional. An earlier install (or another adapter) already wired it.

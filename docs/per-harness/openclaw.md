# OpenClaw setup

## What the adapter installs
- `.openclaw-system.md` at project root (to be used as the system prompt)

## Install
```bash
./install.sh openclaw
```

Then configure OpenClaw to load `.openclaw-system.md` as its system
prompt. The exact steps vary by OpenClaw fork/version — check the docs.

## How it works
OpenClaw doesn't enforce a project-root convention file; instead, you
paste the system prompt include (or point the config at it). The content
mirrors the other adapters: read `.agent/` first, respect permissions,
log after actions.

## Troubleshooting
- If the agent doesn't follow the instructions, make sure the file is
  actually being loaded (some forks require an explicit path, not auto-
  discovery).

# OpenCode setup

## What the adapter installs
- `AGENTS.md` at project root (pointing at `.agent/`)
- `opencode.json` with instruction list and permission rules

## Install
```bash
./install.sh opencode
```

## How it works
OpenCode natively reads `AGENTS.md` and the `instructions` array in
`opencode.json`. Current OpenCode configs use the `permission` key; ztk
installs native deny/ask rules for common risky shell commands and keeps
`ztk exec` available for checks that need the shared `.agent/protocols`
policy engine.

## Troubleshooting
- If `opencode.json` is rejected, check the schema URL at the top matches
  your OpenCode version.
- The permission syntax uses glob-style matching. Test denies with
  `opencode --dry-run` first.

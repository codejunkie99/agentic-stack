# OpenCode adapter

## Install
```bash
cp adapters/opencode/AGENTS.md ./AGENTS.md
cp adapters/opencode/opencode.json ./opencode.json
```

Or:
```bash
./install.sh opencode
```

## What it wires up
- `AGENTS.md` — OpenCode reads this natively; we point it at `.agent/`.
- `opencode.json` — declares instruction files and `permission` rules
  (deny force push, ask before any push).

## Verify
Run OpenCode and ask "What's in my preferences file?" — it should read
`.agent/memory/personal/PREFERENCES.md`.

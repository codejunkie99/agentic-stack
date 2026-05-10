# copilot-cli adapter

Wires the portable `.agent/` brain into
[GitHub Copilot CLI](https://docs.github.com/copilot/concepts/agents/about-copilot-cli)
via the `AGENTS.md`, `.github/instructions/`, hook, and skills paths.

## What it installs

| File | Purpose |
|---|---|
| `.github/instructions/agentic-stack.instructions.md` | Instruction file loaded automatically by Copilot CLI on every session |
| `.github/hooks/agentic-stack.json` | Hook config for tool-use logging and session-end dream cycles |
| `AGENTS.md` | Primary project instructions that point Copilot CLI at the portable `.agent/` brain |
| `.github/skills/` | Mirror of `.agent/skills/` for native skill discovery |

## Why `.github/instructions/` instead of `.github/copilot-instructions.md`

Copilot CLI reads instructions from multiple locations. The
`.github/instructions/**/*.instructions.md` glob is designed for composable,
modular instruction sets — multiple files can coexist without merge conflicts.
Using a dedicated file in this directory avoids clobbering any existing
`.github/copilot-instructions.md` that may contain project-specific
instructions unrelated to the agentic-stack brain.

## Install

```bash
./install.sh copilot-cli
```

On Windows PowerShell:

```powershell
.\install.ps1 copilot-cli C:\path\to\your-project
```

## Verify

```
copilot
> What instructions do you have?
```

Expected: the response mentions `.agent/AGENTS.md`, `PREFERENCES.md`,
`LESSONS.md`, `permissions.md`, and the `.github/hooks/agentic-stack.json`
hook wiring.

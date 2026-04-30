# Copilot CLI setup

[GitHub Copilot CLI](https://docs.github.com/copilot/concepts/agents/about-copilot-cli)
reads instructions from `.github/instructions/**/*.instructions.md` among
other locations. Our adapter installs a single instruction file that wires the
portable `.agent/` brain so Copilot CLI picks up your memory, skills, and
protocols automatically.

## What the adapter installs
- `.github/instructions/agentic-stack.instructions.md` — instruction file
  loaded by Copilot CLI on every session. Contains the startup read order,
  recall workflow, memory discipline, and hard rules.

## Install
```bash
./install.sh copilot-cli
```

On Windows PowerShell:
```powershell
.\install.ps1 copilot-cli C:\path\to\your-project
```

## How it works
- Copilot CLI scans `.github/instructions/` for `*.instructions.md` files at
  session start. The adapter places `agentic-stack.instructions.md` there so
  the brain is loaded alongside any other instruction files the project may
  have.
- The instruction file points Copilot CLI at `.agent/AGENTS.md`,
  `PREFERENCES.md`, `LESSONS.md`, and `permissions.md` in the standard
  agentic-stack read order.
- No hooks or extensions are installed. Copilot CLI does not currently expose
  a hook system like Claude Code's PostToolUse, so memory logging uses the
  manual `recall.py` and `memory_reflect.py` workflow.

## Verify
```
copilot
> What instructions do you have?
```

Expected:
- The response mentions `.agent/AGENTS.md`
- The response references the startup read order from the instruction file

You can also check with the `/instructions` slash command:
```
/instructions
```

This lists all loaded instruction files, and should include
`.github/instructions/agentic-stack.instructions.md`.

## Troubleshooting
- If Copilot CLI does not pick up the instructions, ensure you're launching
  `copilot` from the project root (or a subdirectory of it). The CLI searches
  upward from cwd to the git root.
- Run `/instructions` to see which instruction files are loaded. If the file
  is missing, verify it exists at `.github/instructions/agentic-stack.instructions.md`.
- If you also have a `.github/copilot-instructions.md`, both files are loaded —
  they compose, not conflict. The adapter intentionally uses the modular
  `instructions/` directory to avoid overwriting your existing instructions.
- On Windows, use `python` instead of `python3` if `python3` is not on PATH.
  The instruction file includes a note about this.

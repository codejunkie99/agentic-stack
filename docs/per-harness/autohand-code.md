# Autohand Code CLI setup

[Autohand Code CLI](https://github.com/autohandai/code-cli) reads
`AGENTS.md` as project instructions and discovers project skills from
`.autohand/skills/`. Our adapter layers the portable `.agent/` brain on
top so you keep one knowledge base even if you later swap harnesses.

## What the adapter installs
- `AGENTS.md` at project root. Skipped if one already exists, since
  Autohand, pi, hermes, opencode, and Codex can share the same file.
- `.autohand/skills/` symlinked to `.agent/skills/` when possible.
  Falls back to copying / merging on platforms without symlink support.

## Install
```bash
./install.sh autohand-code
autohand
```

On Windows PowerShell:
```powershell
.\install.ps1 autohand-code C:\path\to\your-project
autohand
```

## How it works
- Autohand loads `AGENTS.md` as repository guidance. The adapter file
  points it at `.agent/AGENTS.md`, `PREFERENCES.md`, `LESSONS.md`, and
  `permissions.md`.
- Autohand scans `.autohand/skills/` for project-level skills. The
  adapter mirrors `.agent/skills/` there so portable skills are visible
  without duplication.
- The adapter intentionally does not install Autohand hooks. Manual
  `recall.py` and `memory_reflect.py` calls remain the stable
  cross-platform path.

## Verify
```bash
autohand "Summarize the current instructions."
autohand "What's in my lessons file?"
```

Expected:
- the first command mentions `.agent/AGENTS.md`
- the second reads `.agent/memory/semantic/LESSONS.md`

## Troubleshooting
- If Autohand does not pick up `AGENTS.md`, restart it from the
  repository root and run the `Summarize the current instructions` check
  again.
- If skills are missing, inspect `.autohand/skills/`. On filesystems
  without symlink support, the installer copies / merges the directory
  instead; re-run the installer after updating `.agent/skills/`.

# Codex setup

[Codex](https://developers.openai.com/codex/) reads `AGENTS.md` natively
and scans `.agents/skills/` for repository-scoped skills. Our adapter
layers the portable `.agent/` brain on top so you keep one knowledge
base even if you later swap harnesses.

## What the adapter installs
- `AGENTS.md` at project root. Skipped if one already exists, since
  codex, pi, hermes, and opencode can all share the same file.
- `.agents/skills/` symlinked to `.agent/skills/` when possible. Falls
  back to copying / merging on platforms without symlink support.
- `.codex/config.toml` with `codex_hooks = true`.
- `.codex/hooks.json` routing supported hooks to `python3 .agent/tools/ztk.py`.

## Install
```bash
npm install -g @openai/codex
./install.sh codex
codex
```

On Windows PowerShell:
```powershell
npm install -g @openai/codex
.\install.ps1 codex C:\path\to\your-project
codex
```

## How it works
- Codex loads `AGENTS.md` before starting work. The adapter file points
  it at `.agent/AGENTS.md`, `PREFERENCES.md`, `LESSONS.md`, and
  `permissions.md`.
- Codex scans `.agents/skills/` from the current working directory up to
  the repository root. The adapter mirrors `.agent/skills/` there so the
  portable skills are visible without duplication.
- Codex hooks cover Bash, `apply_patch`, and MCP tool calls, with documented
  coverage gaps. ztk uses native hooks where available and `ztk exec` as the
  fallback for policy-covered shell commands.

## Verify
```bash
codex --ask-for-approval never "Summarize the current instructions."
codex --ask-for-approval never "What's in my lessons file?"
```

Expected:
- the first command mentions `.agent/AGENTS.md`
- the second reads `.agent/memory/semantic/LESSONS.md`

## Troubleshooting
- If Codex does not pick up `AGENTS.md`, restart it from the repository
  root and run the `Summarize the current instructions` check again.
- If hooks do not fire, confirm `.codex/config.toml` includes
  `codex_hooks = true` and the project `.codex/` layer is trusted.
- Codex `PreToolUse` can deny but cannot safely ask for approval. ztk maps
  approval-required decisions to deny at `PreToolUse` time.
- If skills are missing, inspect `.agents/skills/`. On filesystems
  without symlink support, the installer copies / merges the directory
  instead; re-run the installer after updating `.agent/skills/`.
- On Windows, the native sandbox is the default and works fine for this
  adapter. If your workflow needs Linux-native tooling, run Codex inside
  WSL2 instead.

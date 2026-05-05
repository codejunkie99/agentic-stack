# Codex adapter

## Install
```bash
./install.sh codex
```

Or on Windows PowerShell:
```powershell
.\install.ps1 codex C:\path\to\your-project
```

## What it wires up
- `AGENTS.md` — Codex reads this natively as project instructions. If
  `AGENTS.md` already exists (for example from the pi, hermes, or
  opencode adapters), the installer leaves it in place.
- `.agents/skills/` → `.agent/skills/` — Codex scans `.agents/skills/`
  for repository skills. The installer creates a symlink when possible
  and falls back to copying / merging when symlinks are unavailable.

## Verify
Run Codex in the project and ask:

```bash
codex --ask-for-approval never "Summarize the current instructions."
```

It should mention `.agent/AGENTS.md` and the portable memory files.

Then ask:

```bash
codex --ask-for-approval never "What's in my lessons file?"
```

It should read `.agent/memory/semantic/LESSONS.md`.

## Notes
- This adapter does **not** install Codex hooks. Codex hooks are still
  experimental, and the official docs note they are currently disabled
  on Windows. The adapter therefore relies on manual `recall.py` and
  `memory_reflect.py` calls, like the Cursor and Windsurf paths.
- If `.agents/skills/` is a copied directory rather than a symlink,
  re-run the installer after editing `.agent/skills/` to sync updates.

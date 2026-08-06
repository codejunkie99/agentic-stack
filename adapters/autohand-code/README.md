# Autohand Code CLI adapter

[Autohand Code CLI](https://github.com/autohandai/code-cli) reads
`AGENTS.md` for project instructions and discovers project skills from
`.autohand/skills/`. This adapter layers the portable `.agent/` brain on
top so Autohand can share the same memory, skills, and protocols as the
other harnesses.

## Install
```bash
./install.sh autohand-code
```

Or on Windows PowerShell:
```powershell
.\install.ps1 autohand-code C:\path\to\your-project
```

## What it wires up
- `AGENTS.md` — Autohand reads this as project instructions. If another
  adapter already installed `AGENTS.md`, this adapter leaves it in place.
- `.autohand/skills/` → `.agent/skills/` — Autohand scans this path for
  project-level skills. The installer creates a symlink when possible
  and falls back to copying / merging when symlinks are unavailable.

## Verify
Run Autohand in the project and ask:

```bash
autohand "Summarize the current instructions."
```

It should mention `.agent/AGENTS.md` and the portable memory files.

Then ask:

```bash
autohand "What's in my lessons file?"
```

It should read `.agent/memory/semantic/LESSONS.md`.

## Notes
- This adapter does not install Autohand hooks. It relies on the same
  manual `recall.py` and `memory_reflect.py` calls used by the Cursor
  and Windsurf paths.
- If `.autohand/skills/` is a copied directory rather than a symlink,
  re-run the installer after editing `.agent/skills/` to sync updates.

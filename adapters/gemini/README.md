# Gemini Adapter

Wires the agentic-stack portable brain into Google Gemini CLI projects.

## What gets installed

| File | Policy | Purpose |
|---|---|---|
| `gemini.md` | overwrite | Session startup instructions for Gemini |
| `.gemini/skills/` | symlink/rsync | Mirror of `.agent/skills/` for Gemini skill discovery |

## Install

```powershell
# Windows
.\install.ps1 gemini C:\path\to\your-project

# macOS/Linux
./install.sh gemini /path/to/your-project
```

## Add to an existing project

```powershell
.\install.ps1 add gemini C:\path\to\your-project
```

## Verify

Ask Gemini: *"Read your project instructions and summarize what memory files are available."*
It should describe the `.agent/` brain layers.

## Notes

- Gemini CLI reads `gemini.md` from the project root at session start.
- `.gemini/skills/` mirrors `.agent/skills/` — always edit skills in `.agent/skills/`.
- No hook support yet (Gemini CLI does not expose PostToolUse events); use manual
  `memory_reflect.py` calls after significant actions.

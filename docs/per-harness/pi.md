# Pi Coding Agent setup

[Pi Coding Agent](https://github.com/badlogic/pi-mono) (by Mario
Zechner) is a minimalist terminal coding harness with 15+ LLM providers
and a TypeScript extension system. Our adapter layers the portable
`.agent/` brain on top so you keep one knowledge base across harnesses.
For shell commands that must be checked before execution, use
`python3 .agent/tools/ztk.py exec -- <command>`.

## What the adapter installs
| Path | What |
|------|------|
| `AGENTS.md` | Root-level context file pi reads natively. Skipped if one already exists (pi / hermes / opencode share this file). |
| `.pi/skills` | Symlink → `.agent/skills`. Falls back to copy on platforms without symlink support (e.g. Windows without developer mode). |
| `.pi/extensions/memory-hook.ts` | Project-local extension auto-discovered by pi at startup. Logs `bash`/`edit`/`write` tool results to `.agent/memory/episodic/AGENT_LEARNINGS.jsonl` and runs `auto_dream.py` on session end. |

## Install
```bash
./install.sh pi
npm install -g @mariozechner/pi-coding-agent
pi
```

On Windows PowerShell:
```powershell
.\install.ps1 pi C:\path\to\your-project
npm install -g @mariozechner/pi-coding-agent
pi
```

## How episodic logging works
The extension subscribes to pi's `tool_result` event (the equivalent of
Claude Code's `PostToolUse`). It:

1. **Filters** — only `bash`, `edit`, `write` are logged. `read`, `find`,
   `ls`, `grep` are skipped (noise). Routine low-importance bash calls
   (cat, echo, ls, grep) are also skipped.
2. **Scores** — importance (1–10) and pain_score are computed inline from
   the command / path using the same regex patterns as
   `claude_code_post_tool.py`. User-defined patterns in
   `.agent/protocols/hook_patterns.json` are also loaded.
3. **Writes** — a structured JSONL entry is appended directly via
   `fs.appendFileSync`. No Python subprocess is spawned per tool call.
4. **Dreams** — on session shutdown (quit / new session / resume) the
   extension runs `python3 .agent/memory/auto_dream.py` to cluster and
   stage episodic entries. This mirrors Claude Code's `Stop` hook.

## Verify
After installing, run pi and execute any bash command. Then:

```bash
tail -1 .agent/memory/episodic/AGENT_LEARNINGS.jsonl
```

You should see a JSON entry with `"skill": "pi"` and an `action` derived
from the tool that just ran.

In pi: ask "what's in my LESSONS file?" — it should read
`.agent/memory/semantic/LESSONS.md`.

## Troubleshooting
- **Skills not visible** — run `pi skills list`. If `.pi/skills` is a
  broken symlink, re-run `./install.sh pi` to rebuild it.
- **AGENT_LEARNINGS.jsonl stays empty** — check that the extension
  loaded: pi's startup header lists loaded extensions. If
  `memory-hook.ts` is absent, re-run `./install.sh pi`. If it's listed
  but entries are missing, make sure you ran `bash`/`edit`/`write` tools
  (read-only sessions produce no entries by design).
- **Dream cycle never runs** — the extension runs `auto_dream.py` on
  `session_shutdown`. If you killed pi with SIGKILL instead of a clean
  exit, the shutdown event won't fire. Add a fallback cron for those
  cases:
  ```bash
  crontab -e
  # add:
  0 3 * * * python3 /path/to/project/.agent/memory/auto_dream.py \
    >> /path/to/project/.agent/memory/dream.log 2>&1
  ```
- **Windows without symlink support** — the installer copies
  `.agent/skills/` instead. Changes to `.agent/skills/` won't propagate
  automatically; re-run `.\install.ps1 pi` to sync.

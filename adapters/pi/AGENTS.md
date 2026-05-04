# AGENTS.md — Pi Coding Agent adapter for agentic-stack

[Pi Coding Agent](https://github.com/badlogic/pi-mono) reads `AGENTS.md`
(or `CLAUDE.md`) natively as workspace-level context. This file points
it at the portable brain in `.agent/`.

## Startup (read in order)
1. `.agent/AGENTS.md` — the map
2. `.agent/memory/personal/PREFERENCES.md` — user conventions
3. `.agent/memory/semantic/LESSONS.md` — distilled lessons
4. `.agent/protocols/permissions.md` — hard rules

## Skills
Pi scans `.pi/skills/` at startup. The install script symlinks
`.pi/skills` → `.agent/skills` so every skill under the portable brain
is visible to pi without duplication. Customize under `.agent/skills/`;
pi sees it immediately on `/reload`.

## Automatic memory (no manual calls needed)
`.pi/extensions/memory-hook.ts` is installed by the adapter and
auto-discovered by pi at startup. It:

- Logs every `bash`, `edit`, and `write` tool call to
  `.agent/memory/episodic/AGENT_LEARNINGS.jsonl` automatically —
  same signal Claude Code captures via `PostToolUse`.
- Skips `read`, `find`, `ls`, `grep` and low-importance bash calls
  (grep, cat, echo, etc.) to keep the log signal-rich.
- Runs `auto_dream.py` when the session ends (quit / new session /
  resume) so the dream cycle fires without a cron job.

For deploy / ship / migration / schema tasks the extension scores
importance automatically — no manual `memory_reflect.py` calls needed
for individual tool actions.

## Recall before non-trivial tasks
For deploy / ship / migration / schema / timestamp / date / failing test /
debug / refactor, FIRST run:

```bash
python3 .agent/tools/recall.py "<description>"
```

Surface results in a `Consulted lessons before acting:` block and follow
them.

## Memory discipline
- Update `.agent/memory/working/WORKSPACE.md` as you work.
- After significant actions, run
  `python3 .agent/tools/memory_reflect.py <skill> <action> <outcome>`.
- For shell commands covered by `.agent/protocols/permissions.md`, run
  `python3 .agent/tools/ztk.py exec -- <command>`.
- Never delete memory entries; archive only.
- Quick state: `python3 .agent/tools/show.py`.
- Teach a rule in one shot:
  `python3 .agent/tools/learn.py "<rule>" --rationale "<why>"`.

## Hard rules
- No force push to `main`, `production`, `staging`.
- No modification of `.agent/protocols/permissions.md`.

## Pi-specific
- System prompt override: `.pi/SYSTEM.md` replaces pi's default system
  prompt entirely.
- Prompt templates: `.pi/prompts/`.
- TypeScript extensions: `.pi/extensions/` (auto-discovered at startup).

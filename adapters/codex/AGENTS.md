# AGENTS.md — Codex adapter for agentic-stack

Codex reads `AGENTS.md` before doing any work. This file points it at
the portable brain in `.agent/`.

> **Python invocation**: examples below use `python3`. On stock Windows
> only `python` is on PATH; use whichever resolves on your system.

## Startup (read in order)
1. `.agent/AGENTS.md` — the map
2. `.agent/memory/personal/PREFERENCES.md` — user conventions
3. `.agent/memory/semantic/LESSONS.md` — distilled lessons
4. `.agent/protocols/permissions.md` — hard rules

## Skills
Codex scans `.agents/skills/` for repository-scoped skills (per
[OpenAI Codex docs](https://developers.openai.com/codex/skills)). The
install script symlinks or syncs `.agents/skills` from `.agent/skills`
so the portable brain remains the one source of truth. Load a full
`SKILL.md` only when its triggers match the task (progressive
disclosure). Edit skills in `.agent/skills/` — `.agents/skills/` is a
mirror and re-running the installer will sync it back.

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
- Never delete memory entries; archive only.
- Quick state: `python3 .agent/tools/show.py`.
- Teach a rule in one shot:
  `python3 .agent/tools/learn.py "<rule>" --rationale "<why>"`.

## Hard rules
- No force push to `main`, `production`, `staging`.
- No modification of `.agent/protocols/permissions.md`.

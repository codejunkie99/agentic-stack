# AGENTS.md — Hermes Agent adapter for agentic-stack

Hermes Agent (Nous Research) reads `AGENTS.md` as workspace-level context.
This file points it at the portable brain in `.agent/`.

## Startup (read in order)
1. `.agent/AGENTS.md` — the map
2. `.agent/memory/personal/PREFERENCES.md` — user conventions
3. `.agent/memory/semantic/LESSONS.md` — distilled lessons
4. `.agent/protocols/permissions.md` — hard rules

## Skills
Hermes supports the agentskills.io standard. Our skills under
`.agent/skills/<name>/SKILL.md` follow the same frontmatter-plus-body
shape. Use `/skills` in Hermes to browse them; load `SKILL.md` only
when triggers match the current task (progressive disclosure).

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
- Optional: mirror high-signal state into Hermes's own `MEMORY.md` /
  `USER.md` if you want it inside Hermes's runtime persistence layer.

## Hard rules
- No force push to `main`, `production`, `staging`.
- No modification of `.agent/protocols/permissions.md`.

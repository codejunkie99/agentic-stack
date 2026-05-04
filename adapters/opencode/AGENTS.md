# AGENTS.md — OpenCode adapter for agentic-stack

OpenCode natively reads `AGENTS.md` from the project root. This file points
it at the portable brain in `.agent/`.

## Before any action
1. Read `.agent/AGENTS.md` (the map).
2. Read `.agent/memory/personal/PREFERENCES.md`.
3. Read `.agent/memory/semantic/LESSONS.md`.
4. Read `.agent/protocols/permissions.md`.

## Recall before non-trivial tasks
For deploy / ship / migration / schema / timestamp / date / failing test /
debug / refactor, FIRST run:

```bash
python3 .agent/tools/recall.py "<description>"
```

Surface results in a `Consulted lessons before acting:` block and follow
them.

## Skills
- Use `.agent/skills/_index.md` for discovery.
- Load `.agent/skills/<name>/SKILL.md` only when the skill's triggers match.

## Memory
- Update `.agent/memory/working/WORKSPACE.md` as you work.
- After significant actions, run
  `python3 .agent/tools/memory_reflect.py <skill> <action> <outcome>`.
- For shell commands covered by `.agent/protocols/permissions.md`, run
  `python3 .agent/tools/ztk.py exec -- <command>` unless OpenCode's native
  `permission` config already blocks or asks for that exact operation.
- Never delete memory entries. Archive only.
- Quick state: `python3 .agent/tools/show.py`.
- Teach a rule in one shot:
  `python3 .agent/tools/learn.py "<rule>" --rationale "<why>"`.

## Constraints
- Never force push to `main`, `production`, or `staging`.
- Never modify `.agent/protocols/permissions.md`.

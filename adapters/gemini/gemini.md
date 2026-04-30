# Project Instructions (Gemini)

This project uses the **agentic-stack** portable brain. All memory, skills,
and protocols live in `.agent/`.

## Session start — read in this order
1. `.agent/AGENTS.md` — the map of the whole brain
2. `.agent/memory/personal/PREFERENCES.md` — how the user works
3. `.agent/memory/working/REVIEW_QUEUE.md` — pending lessons awaiting review
4. `.agent/memory/semantic/LESSONS.md` — what we've already learned
5. `.agent/protocols/permissions.md` — hard constraints, read before any tool call

## Before every non-trivial action — recall first

For any task involving **deploy**, **ship**, **release**, **migration**,
**schema change**, **supabase**, **edge function**, **timestamp** /
**timezone** / **date**, **failing test**, **debug**, **investigate**, or
**refactor**, run recall FIRST and present the results before acting:

```bash
python .agent/tools/recall.py "<one-line description of what you're about to do>"
```

Show the output in a `Consulted lessons before acting:` block. If a surfaced
lesson would be violated by your intended action, stop and explain why.

## While working

### Skills
Read `.agent/skills/_index.md` and load the full `SKILL.md` for any skill
whose triggers match the task. Don't skip this — skills carry constraints
the permissions file doesn't cover.

### Workspace
Update `.agent/memory/working/WORKSPACE.md` when:
- You start a new task (write the goal and first step)
- Your hypothesis changes
- You complete or abandon a task (clear it so the next session is clean)

### Brain state
Quick overview any time:
```bash
python .agent/tools/show.py
```

### Teaching the agent a new rule
When you discover something that should never happen again:
```bash
python .agent/tools/learn.py "<the rule, phrased as a principle>" \
    --rationale "<why — include the incident that taught you this>"
```

## Memory discipline
- After significant actions, run `python .agent/tools/memory_reflect.py <skill> <action> <outcome>`.
- Never delete memory entries; archive only.
- Skills are in `.gemini/skills/` — this mirrors `.agent/skills/` (edit the originals there).

## Hard rules
- No force push to `main`, `production`, or `staging`.
- No modification of `.agent/protocols/permissions.md`.
- No hand-editing `.agent/memory/semantic/LESSONS.md` — use `graduate.py`.
- If `REVIEW_QUEUE.md` shows pending > 10 or oldest > 7 days, review
  candidates before starting substantive work.

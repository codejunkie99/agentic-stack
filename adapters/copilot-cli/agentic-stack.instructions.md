---
applyTo: "**"
---

# Project Instructions (GitHub Copilot CLI)

This project uses the **agentic-stack** portable brain. All memory, skills,
and protocols live in `.agent/`.

> **Python invocation**: examples below use `python3`. On stock Windows
> only `python` is on PATH; use whichever resolves on your system.

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
python3 .agent/tools/recall.py "<one-line description of what you're about to do>"
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
python3 .agent/tools/show.py
```

### Teaching the agent a new rule
When you discover something that should never happen again:
```bash
python3 .agent/tools/learn.py "<the rule, phrased as a principle>" \
    --rationale "<why — include the incident that taught you this>"
```

### Manual memory logging
After significant actions (major feature, bug fix, rollback, architectural
decision, deploy, migration), log explicitly:
```bash
python3 .agent/tools/memory_reflect.py \
    "<skill-name>" "<action>" "<outcome>" \
    --importance 7 \
    --note "<why this matters for future sessions>"
```

## Review queue
If `.agent/memory/working/REVIEW_QUEUE.md` shows pending > 10 or oldest > 7
days, review candidates before starting substantive work:
```bash
python3 .agent/tools/list_candidates.py
python3 .agent/tools/graduate.py <id> --rationale "..."
python3 .agent/tools/reject.py <id> --reason "..."
```

## Rules that override all defaults
- Never force push to `main`, `production`, or `staging`.
- Never delete episodic or semantic memory entries — archive them.
- Never modify `.agent/protocols/permissions.md` — only humans edit it.
- Never hand-edit `.agent/memory/semantic/LESSONS.md` — use `graduate.py`.

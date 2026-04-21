# Project Instructions (Claude Code)

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

## Manual memory logging — when and how

The PostToolUse hook captures every tool call automatically, but its
reflections are mechanical. For **significant events** you must call
`memory_reflect.py` explicitly with a rich `--note`. These are the entries
the dream cycle promotes into lessons.

### When to log manually
- After completing a major feature or fixing a bug that took real investigation
- After any rollback, incident, or unexpected failure
- After any architectural decision (why you chose approach A over B)
- After discovering a project-specific constraint (e.g. "this table has a
  trigger that fires on every insert — don't bulk insert")
- After a Supabase migration, RLS policy change, or edge function deploy
- Any time you think "I wish I had known this an hour ago"

### How to write a good entry

```bash
# Good: specific, domain-rich, future-oriented
python3 .agent/tools/memory_reflect.py \
    "supabase-migration" \
    "applied add_user_tier_column migration" \
    "migration succeeded; 847 rows backfilled to tier=free" \
    --importance 8 \
    --note "RLS policy on user_profiles must be updated whenever a new column is added that affects row visibility. Missed this, caused 401s in staging for 20 minutes."

# Good: failure with root cause
python3 .agent/tools/memory_reflect.py \
    "edge-function" \
    "deployed notify-on-signup" \
    "deploy failed: missing RESEND_API_KEY in production env" \
    --fail \
    --importance 9 \
    --note "Production env vars for edge functions must be set in supabase secrets, not .env. The .env file is ignored at deploy time."

# Bad: vague, no content words for clustering
python3 .agent/tools/memory_reflect.py \
    "claude-code" "did stuff" "ok" --importance 3
```

### Importance guide
| Value | When |
|---|---|
| 9–10 | Production incident, data migration, rollback, security issue |
| 7–8 | Deploy, schema change, architectural decision, non-obvious constraint |
| 5–6 | Refactor, significant bug fix, API contract change |
| 3–4 | Routine edit, file creation, test run |

## Rules that override all defaults
- Never force push to `main`, `production`, or `staging`.
- Never delete episodic or semantic memory entries — archive them.
- Never modify `.agent/protocols/permissions.md` — only humans edit it.
- Never hand-edit `.agent/memory/semantic/LESSONS.md` — use `graduate.py`.
- If `REVIEW_QUEUE.md` shows pending > 10 or oldest > 7 days, review
  candidates before starting substantive work.

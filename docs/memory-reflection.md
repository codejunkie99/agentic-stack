# Memory reflection — when and how

> Reference doc, loaded on demand by the agent when it's about to log
> a significant event manually. Pointer in `CLAUDE.md` directs here.

## When to log manually (`memory_reflect.py`)

The PostToolUse hook captures every tool call automatically, but its
reflections are mechanical. For **significant events** you must call
`memory_reflect.py` explicitly with a rich `--note`. These entries
are what the dream cycle promotes into lessons.

Trigger conditions:

- Completed a major feature or fixed a bug that took real investigation
- Any rollback, incident, or unexpected failure
- Any architectural decision (why you chose approach A over B)
- Discovered a project-specific constraint (e.g. "this table has a
  trigger that fires on every insert — don't bulk insert")
- Supabase migration, RLS policy change, or edge function deploy
- "I wish I had known this an hour ago"

## How to write a good entry

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

## Importance guide

| Value | When |
|---|---|
| 9–10 | Production incident, data migration, rollback, security issue |
| 7–8  | Deploy, schema change, architectural decision, non-obvious constraint |
| 5–6  | Refactor, significant bug fix, API contract change |
| 3–4  | Routine edit, file creation, test run |

## Teaching a one-shot lesson

When you discover something that should never happen again — and you
already know the rule, you don't need the dream cycle to surface it:

```bash
python3 .agent/tools/learn.py "<the rule, phrased as a principle>" \
    --rationale "<why — include the incident that taught you this>"
```

This stages + graduates a candidate in one shot. Removes the
stage-then-graduate ceremony for the common case.

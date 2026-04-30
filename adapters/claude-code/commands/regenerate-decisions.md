Regenerate `.agent/memory/semantic/DECISIONS.md` from current LESSONS + episodic.

This is the **canonical agentic-stack pattern** for maintaining DECISIONS.md
(per the source article — sporadic regeneration from accumulated experience,
not continuous-write). Run this periodically — e.g., end of each engagement,
end of each major step, or when DECISIONS.md feels stale.

## Steps

1. **Read source material:**
   - `.agent/memory/semantic/LESSONS.md` — distilled patterns
   - `.agent/memory/episodic/AGENT_LEARNINGS.jsonl` — raw experience log
     (focus on entries with `importance >= 7` or `pain_score >= 7` —
     these surface significant events)
   - The current `.agent/memory/semantic/DECISIONS.md` — to preserve
     existing entries (this is regenerate-additive, not regenerate-replace)

2. **Identify the 3-5 most significant architectural or workflow decisions
   that have been made since the last regeneration** (or all-time if
   first run). Criteria:
   - Decisions that would be costly to revisit or re-debate
   - Decisions with clear rationale + alternatives that were considered
   - Decisions that shaped subsequent work (visible across multiple
     episodic entries)

3. **For each decision, write or update an entry in DECISIONS.md:**

   ```markdown
   ## YYYY-MM-DD: <decision title>

   **Decision:** <what was decided>

   **Rationale:** <why this choice over alternatives>

   **Alternatives considered:**
   - <alternative A> — rejected because <reason>
   - <alternative B> — rejected because <reason>

   **Status:** active | superseded-by <link> | retired
   ```

4. **Preserve existing entries.** Do NOT delete or rewrite entries that
   are still active and accurate. Append new entries; mark superseded
   ones with a status update + link to the superseding entry.

5. **Format as markdown.** Sort entries newest-first within DECISIONS.md.
   Only include decisions that would be costly to revisit or re-debate —
   skip routine implementation choices, tactical adjustments, or
   anything already covered by an existing decisions log entry.

## Why this command exists

Per the agentic-stack source article: *"Read memory/semantic/LESSONS.md and
memory/episodic/AGENT_LEARNINGS.jsonl. Identify the 3-5 most significant
architectural or workflow decisions that have been made. For each one,
write an entry in DECISIONS.md..."* This canonical pattern keeps
DECISIONS.md current without requiring agents to manually log every
decision inline as they work — which would pollute prompts and create
inconsistent rationale quality.

The dream cycle (`auto_dream.py`) handles LESSONS.md auto-promotion
canonically. This slash command is the parallel canonical mechanism for
DECISIONS.md.

## When to run

- End of each major engagement step or phase
- When `python3 .agent/tools/show.py` reports DECISIONS.md is stale
  relative to recent episodic activity
- Before merging a feature branch with substantial architectural changes
- When you notice you can't remember WHY a recent change was made the
  way it was (signal that the decision wasn't captured)

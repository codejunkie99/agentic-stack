---
name: memory-manager
description: "Review and maintain project memory while preserving evidence and separate memory layers."
version: 2026-01-01
triggers: ["reflect", "remember", "distill", "what did I learn", "update memory", "compress memory"]
tools: [memory_reflect, bash, git]
preconditions: ["memory/episodic/AGENT_LEARNINGS.jsonl exists"]
constraints: ["do not delete high-salience entries", "do not merge personal into semantic"]
---

# Memory Manager — the skill that reads the filing cabinet

After every major task or failure, call `tools/memory_reflect.py` to log what
happened. Before important decisions, read the top entries from
`memory/semantic/LESSONS.md` and `memory/semantic/DECISIONS.md`.

## When to trigger full consolidation
- On explicit `reflect` trigger from the user.
- When the context window is getting full.
- When episodic memory exceeds ~500 entries.

## Consolidation steps
1. Load top-5 episodic entries by salience score.
2. Detect recurring patterns across the last 100 entries.
3. For patterns appearing ≥3 times, promote to `memory/semantic/LESSONS.md`.
4. Flag any skill with ≥3 failures in 14 days for rewrite (see `on_failure.py`).
5. Archive resolved working context to `memory/episodic/snapshots/`.
6. Commit via git so history is preserved: `git log memory/` is the agent's autobiography.

## Searching memory by keyword

When you need to find a specific memory by topic or keyword (not just the
top-salience entries), use the FTS5 search tool:

```bash
python3 .agent/memory/memory_search.py <query>
```

This indexes all `.md` and `.jsonl` files under `.agent/memory/` and returns
ranked results with context snippets. Falls back to grep if FTS5 is not
available. The index auto-rebuilds when files change.

## Markdown tracks, reflection, knowledge
- Episodes (user track), agent cases, and foresight live as daily-log
  Markdown under `memory/{episodes,cases,foresights}/` — append with
  `tools/track.py add ...`, search with `track.py search`, never hand-delete
  (use `deprecate`).
- Weekly `memory/reflect_episodes.py` merges similar, time-adjacent episodes
  into one consolidated entry and deprecates the originals (audit in
  `reflection_report.jsonl`). Cron it; it is model-free.
- Documents become searchable topic pages with `tools/knowledge.py add` —
  source-backed, Markdown, editable; `knowledge.py search` before answering
  from memory of a doc.
- Durable user facts go through `mem_save_fact` (MCP) or
  `memory/personal/PROFILE.md`; trajectories never do.
- After a few plan runs: `tools/skill_forge.py cluster` then `propose` to
  turn repeated successful cases into candidate skills for review.

## Anti-patterns
- Do not auto-merge `personal/` into `semantic/` — user preferences are not general knowledge.
- Do not delete entries to "clean up" memory. Archive them.
- Do not promote lessons from a single incident. Require recurrence.

## Self-rewrite hook
Every 10 reflections, or when the same type of mistake appears 3+ times
recently, this skill's approach to salience or distillation needs adjustment.
Propose conservative edits and log the diff in `memory/semantic/DECISIONS.md`.

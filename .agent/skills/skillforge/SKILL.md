---
name: skillforge
description: Use proactively when a new capability is needed and a recurring pattern in user work justifies a new skill. Triggers on "create skill", "new skill", "build skill", "new capability", "I keep doing this manually". Constraints: do not duplicate existing skills; always include self-rewrite hook.
version: 2026-01-01
triggers: ["create skill", "new skill", "build skill", "new capability"]
tools: [bash, memory_reflect, git]
constraints: ["do not duplicate existing skills", "always include self-rewrite hook"]
---

# Skillforge — the skill that creates skills

When a new capability is needed:

1. **Check for duplicates.** Read `skills/_index.md`. If a similar skill exists,
   extend it instead of creating a new one.
2. **Check memory.** Read `memory/semantic/LESSONS.md` for related patterns.
3. **Draft the skill.** Create `skills/<name>/SKILL.md` with:
   - YAML frontmatter (name, version, triggers, tools, preconditions, constraints)
   - Plain-language instructions (destinations and fences, not driving directions)
   - A self-rewrite hook at the bottom
4. **Register it.** Add an entry to `skills/_index.md` and append a JSON line
   to `skills/_manifest.jsonl`.
5. **Log it.** Append a record to `memory/semantic/DECISIONS.md` explaining
   why this skill was created.

## What good skills look like
- State the destination ("verify tests pass before commit"), not the exact
  command sequence.
- Include 2–3 examples of correct behavior when it clarifies intent.
- Include 1 example of a failure and what was learned from it.
- Keep the whole file under 100 lines.
- End with a self-rewrite hook that includes the harness-friction trigger
  (see `.agent/protocols/harness-fix-triggers.md`): on any failed
  invocation OR every N uses, in addition to the skill's own pattern
  scan, also check whether harness-shape friction was encountered (skill
  step missing, workflow timing wrong, agent dispatch mismatch,
  agent-memory sparse) and invoke `propose_harness_fix.py` if so.

## Self-rewrite hook
After every 5 skills created, or on any failed creation:
1. Read the last 5 skillforge entries from episodic memory.
2. If better trigger patterns or constraint structures have emerged,
   update this file and the template it implies.
3. If harness-shape friction surfaced (see
   `.agent/protocols/harness-fix-triggers.md`), invoke
   `propose_harness_fix.py` BEFORE updating skillforge — separating
   harness fixes from skill self-evolution keeps the audit trail clean.
4. Commit: `skill-update: skillforge, <one-line reason>`.

# Architecture

Three modules, one principle: the harness is dumb, the knowledge is in files.

## Modules

### Memory — four layers
- **working/** — live task state. Volatile. Archived after 2 days.
- **episodic/** — what happened in prior runs. JSONL, scored by salience.
- **semantic/** — distilled patterns that outlive episodes.
- **personal/** — user-specific preferences. Never merged into semantic.

### Skills — progressive disclosure
- `_index.md` and `_manifest.jsonl` always in context (tiny).
- A full `SKILL.md` loads only when its triggers match the current task.
- Every skill has a self-rewrite hook at the bottom.

### Protocols — contracts with external systems
- `permissions.md` — allow / approval-required / never-allowed.
- `tool_schemas/` — typed interfaces for every external tool.
- `delegation.md` — rules for sub-agent handoff.

## The feedback loops

1. Skills log to episodic memory after every action.
2. Memory-manager detects recurring patterns and promotes them to semantic.
3. Skillforge watches for patterns not yet covered by existing skills.
4. Failures fire `on_failure.py`, which flags skills for rewrite after 3+
   hits in 14 days.
5. Constraint violations inside a skill escalate from local `KNOWLEDGE.md`
   to global `LESSONS.md`.

## Why the separation matters

You can swap the harness for any of the adapters (Claude Code, Cursor,
Windsurf, OpenCode, OpenClaw, Hermes, standalone Python) and lose
nothing. The brain is portable; only the glue changes.

See `diagram.svg` for a visual.

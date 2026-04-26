# Architecture

Four modules, one principle: the harness is dumb, the knowledge and telemetry
are in local files.

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

### Data layer — local visibility across harnesses
- `.agent/tools/data_layer_export.py` normalizes shared episodic memory,
  optional harness events, and optional cron runs.
- `.agent/data-layer/` is private runtime state and exports.
- Exports include JSONL, CSV, KPI summaries, `dashboard.html`, and
  `daily-report.md`.
- The dashboard helps users see harness mix, cron schedules, active agents,
  token/cost estimates, categories, and workflow outcomes across Claude Code,
  Hermes, OpenClaw, Codex, Cursor, OpenCode, and other adapters.

## The feedback loops

1. Skills log to episodic memory after every action.
2. Memory-manager detects recurring patterns and promotes them to semantic.
3. Skillforge watches for patterns not yet covered by existing skills.
4. Failures fire `on_failure.py`, which flags skills for rewrite after 3+
   hits in 14 days.
5. Constraint violations inside a skill escalate from local `KNOWLEDGE.md`
   to global `LESSONS.md`.
6. Data-layer exports turn local activity into screenshot-ready monitoring
   without adding remote telemetry.

## Why the separation matters

You can swap the harness for any of the adapters (Claude Code, Cursor,
Windsurf, OpenCode, OpenClaw, Hermes, Pi, Codex, standalone Python,
Antigravity) and lose nothing. The brain is portable; only the glue
changes. The dashboard works for the same reason: every harness can write to
the same local `.agent/` event stream.

See `diagram.svg` for a visual.

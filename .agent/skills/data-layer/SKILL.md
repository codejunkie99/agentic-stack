---
name: data-layer
version: 2026-04-25
triggers: ["data layer", "dashboard", "agent analytics", "resource usage", "cron monitoring", "daily report", "tokens"]
tools: [bash, git]
preconditions: [".agent exists"]
constraints: ["local-only by default", "do not send screenshots without explicit user approval", "do not commit private .agent/data-layer exports"]
---

# Data Layer - cross-harness monitoring for the portable brain

Use this skill when the user wants to measure agent activity across Claude Code,
Hermes, OpenClaw, Codex, Cursor, OpenCode, Windsurf, Pi, Antigravity, or any
custom loop using `.agent/`.

The goal is local business intelligence for the whole agent suite:

- what harnesses are active
- how many agent events are happening
- when cron/scheduled agents fire
- which crons started/finished and how long they ran
- how many agents are active
- tokens and estimated cost by hour/day/week/month
- resource usage by user-defined category
- workflow success/error rates
- KPI summary rows for cron cadence, run volume, reliability, active agents,
  workflow breadth, token usage, and estimated cost
- screenshot-ready daily resource reports

## Hard Rules

- Stay local-first. Do not add telemetry or remote sync.
- Do not store raw prompts, raw code, client names, emails, phone numbers, or
  unredacted business records in shared examples.
- Do not commit `.agent/data-layer/` exports unless the user explicitly reviewed
  and sanitized them.
- Do not send dashboard screenshots to email, Slack, webhooks, or any other
  channel unless the user explicitly approves the destination.

## Inputs

Default inputs:

```text
.agent/memory/episodic/AGENT_LEARNINGS.jsonl
.agent/data-layer/harness-events.jsonl     optional
.agent/data-layer/cron-runs.jsonl          optional
.agent/data-layer/category-rules.json      optional
```

`AGENT_LEARNINGS.jsonl` is the shared activity log. Optional files let users add
events from harnesses that do not automatically write rich events yet.

## Export

Run:

```bash
python3 .agent/tools/data_layer_export.py --window 30d --bucket day
```

Use `--bucket hour`, `--bucket day`, `--bucket week`, or `--bucket month` for
different chart grains.

Outputs go to:

```text
.agent/data-layer/exports/<YYYY-MM-DD>/
```

Key outputs:

- `agent-events.jsonl/csv`
- `cron-runs.jsonl/csv`
- `cron-timeline.json/csv`
- `activity-series.json/csv`
- `category-summary.json/csv`
- `harness-summary.json/csv`
- `workflow-summary.json/csv`
- `kpi-summary.json/csv`
- `dashboard-summary.json`
- `dashboard-report.json`
- `dashboard.html`
- `daily-report.md`

## Categories

Users can define any categories they want in
`.agent/data-layer/category-rules.json`, for example:

```json
{
  "default_category": "uncategorized",
  "rules": [
    {"category": "coding", "skills": ["debug-investigator", "git-proxy"]},
    {"category": "admin", "run_types": ["cron"]},
    {"category": "financial", "workflows": ["invoice_collection"]},
    {"category": "personal", "workflows": ["calendar_coordination"]},
    {"category": "work", "phases": ["plan", "review", "qa", "ship"]}
  ]
}
```

## Daily Screenshot Report

For daily resource management:

1. Run the exporter from a user-approved cron or scheduled agent.
2. Open `dashboard.html`.
3. Capture the Resource Overview, Activity, Tokens, Cron Runs, Task Categories,
   Harness Mix, Workflow Outcomes, Cron Gantt, and Cron Timeline sections.
4. Send the screenshot only through an explicitly approved channel.

The exporter creates `daily-report.md` as the text summary. It does not send
anything by itself.

## Self-rewrite hook

If exports are confusing twice in a row, improve category rules, schema names,
or dashboard labels before adding heavier dashboard dependencies.

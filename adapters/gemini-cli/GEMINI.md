# Project Instructions (Gemini CLI)

This project uses the **agentic-stack** portable brain. All memory, skills,
and protocols live in `.agent/`.

## Before doing anything

1. Read `.agent/AGENTS.md` — it's the map.
2. Read `.agent/memory/personal/PREFERENCES.md` — how the user works.
3. Read `.agent/memory/semantic/LESSONS.md` — what we've learned.
4. Read `.agent/protocols/permissions.md` — what you can and cannot do.

## Before every non-trivial task — recall first

For any task involving **deploy**, **ship**, **release**, **migration**,
**schema change**, **timestamp** / **timezone** / **date**, **failing test**,
**debug**, **investigate**, or **refactor**, run recall FIRST and present
the surfaced lessons to yourself before acting:

```bash
python3 .agent/tools/recall.py "<one-line description of what you're about to do>"
```

If the output contains a "Consulted lessons for intent:" block with one or
more results, show them in a `Consulted lessons before acting:` block and
adjust your plan to respect them. If a surfaced lesson would be violated by
your intended action, stop and explain.

This is how graduated lessons actually change behavior across harnesses.
Skip it and the system is just files on disk.

## MCP tools

The agentic-stack MCP server is pre-configured in `.gemini/settings.json`.
It exposes these tools:

| Tool | What it does |
|---|---|
| `recall` | Surface graduated lessons relevant to an intent |
| `memory_reflect` | Log a significant event to episodic memory |
| `learn` | Teach the agent a new rule in one shot |
| `agentic_status` | Show brain-state dashboard (episodes, candidates, lessons) |

Use the tools directly when the model decides to; you can also invoke them
via slash commands:

- `/agentic:recall <intent>` — query memory before a task
- `/agentic:learn <rule>` — store a new lesson
- `/agentic:status` — quick brain-state check
- `/agentic:reflect <skill> <action> <outcome>` — log a significant event

## While working

- Consult `.agent/skills/_index.md` and load the full `SKILL.md` for any
  skill whose triggers match the task.
- Update `.agent/memory/working/WORKSPACE.md` as the task evolves.
- Log significant actions to `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
  via `.agent/tools/memory_reflect.py` or the `memory_reflect` MCP tool.
- Quick state check any time: `python3 .agent/tools/show.py`.
- Teach the agent a new rule in one shot:
  `python3 .agent/tools/learn.py "<the rule>" --rationale "<why>"`.

## Visual memory (tldraw, opt-in)

If `.agent/memory/.features.json` has `tldraw.enabled: true`, the `tldraw`
skill is available. It draws on a live canvas at `http://localhost:3030`
via the tldraw MCP server configured in `.mcp.json`. Worthwhile drawings
snapshot into the skill's local store and are recalled with
`python3 .agent/skills/tldraw/store.py list`. Off by default.

## Rules that override defaults

- Never force push to `main`, `production`, or `staging`.
- Never delete episodic or semantic memory entries — archive them.
- Never modify `.agent/protocols/permissions.md`.
- Prefer using the `agentic-stack` tools for all repository-level learning
  and recall chores.

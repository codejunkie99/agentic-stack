---
name: tldraw
version: 2026-04-21
triggers: ["draw", "diagram", "sketch", "wireframe", "flowchart", "mind-map", "mind map", "visualize", "lay out", "architecture diagram", "whiteboard"]
tools: [mcp.tldraw.create_shape, mcp.tldraw.update_shape, mcp.tldraw.delete_shape, mcp.tldraw.get_canvas]
preconditions: ["tldraw MCP server reachable via the harness's MCP config", "user has http://localhost:3030 open"]
constraints: ["call get_canvas before update_shape or delete_shape to discover real ids", "at most 200 shapes per create_shape call", "coordinates within 0..1600 x 0..900 unless the user asks otherwise"]
category: visualization
---

# tldraw — draw on a live canvas

The tldraw MCP server exposes a live canvas at `http://localhost:3030`.
You draw into it; the user watches it fill in. Worthwhile drawings can
be snapshotted to disk and recalled in future sessions via this skill's
local store (`store.py`).

## When this skill loads

Any time the user asks to visualize, diagram, sketch, lay out, or map
something graphically. If they are clearly asking for prose, do not draw.

## Before drawing, once per session

Tell the user:

> Open `http://localhost:3030` to see the canvas.

If any tool returns `No tldraw browser connected`, repeat the hint and
stop until they confirm.

## Opt-in MCP setup

This beta does not install MCP wiring during default adapter setup. After the
user enables `tldraw` in `.agent/memory/.features.json`, they must add the
server to their harness MCP config. Use this local block as the source of truth:

```json
{
  "mcpServers": {
    "tldraw": {
      "command": "npx",
      "args": ["-y", "@tldraw-mcp/server"]
    }
  }
}
```

For Claude Code and Antigravity this usually lives in `.mcp.json`; for Cursor
it usually lives in `.cursor/mcp.json`. If a config already exists, merge the
`tldraw` server entry rather than overwriting the file.

## Tools

| tool | purpose |
|---|---|
| `create_shape({ shapes: [...] })` | add new shapes |
| `update_shape({ updates: [{ id, props }] })` | change shapes by id |
| `delete_shape({ ids: [...] })` | remove shapes |
| `get_canvas()` | return all current shapes |

Always `get_canvas` first when the user says "add to", "next to",
"modify", or refers to something already drawn — you need the real ids.

## Coordinate system

- Origin `(0, 0)` top-left. `+x` right, `+y` down.
- Stay inside `0 <= x <= 1600`, `0 <= y <= 900` unless told otherwise.
- Default sizes: boxes ~160x80, icons ~60x60.

## Shape vocabulary

| type | required | optional |
|---|---|---|
| `geo` | `x, y, w, h` | `geo` (rectangle/ellipse/triangle/diamond/star/...), `color`, `fill`, `text` |
| `text` | `x, y, text` | `color`, `size` (s/m/l/xl) |
| `arrow` | `x, y, end:{x,y}` | `color`, `text` (label) |
| `line` | `x, y, end:{x,y}` | `color` |
| `draw` | `x, y, points:[{x,y}]` | `color` (freehand, at least 2 points) |
| `note` | `x, y, text` | `color` (sticky note) |

Colors: `black, grey, light-violet, violet, blue, light-blue, yellow, orange, green, light-green, red`.
Fills: `none, semi, solid, pattern`.

## Persisting drawings

When a drawing is worth keeping across sessions (architecture decisions,
recurring diagrams, reference material), snapshot it:

```bash
# fetch current shapes via MCP get_canvas and pipe the JSON in
python3 .agent/skills/tldraw/store.py snapshot \
    --label "auth-flow-v1" --tags architecture,auth \
    --note "login + refresh token flow agreed 2026-04-21"
```

The store reads canvas JSON on stdin, writes a snapshot file under
`snapshots/`, appends metadata to `snapshots.jsonl`, and re-renders
`INDEX.md` — all within a single file lock. Later sessions recover a
drawing with `list` / `load`. Use `archive` to retire a snapshot; the
JSONL is append-only semantic, so archived records move to
`snapshots/archive/` rather than being deleted.

## Pitfalls

- `text` shapes need non-empty `text`.
- `arrow.end` is an absolute point, not a delta.
- Split large scenes into multiple `create_shape` calls (<= 200 each).
- Always `get_canvas` before an edit; never assume ids.

## Self-rewrite hook

After any failure, or every 5 uses:
1. Read the last N tldraw-tagged entries from `memory/episodic/AGENT_LEARNINGS.jsonl`.
2. If a constraint was violated (shape cap, id-before-edit rule), escalate
   a candidate lesson to `semantic/LESSONS.md` via `tools/learn.py`.
3. Commit: `skill-update: tldraw, <one-line reason>`.

---
name: tldraw
version: 2026-04-21
triggers: ["draw", "diagram", "sketch", "wireframe", "flowchart", "mind-map", "mind map", "visualize", "lay out", "architecture diagram", "whiteboard"]
tools: [mcp.tldraw.create_shape, mcp.tldraw.update_shape, mcp.tldraw.delete_shape, mcp.tldraw.get_canvas]
preconditions: ["tldraw MCP server reachable via the harness's MCP config", "user has http://localhost:3030 open"]
constraints: ["call get_canvas before update_shape or delete_shape to discover real ids", "at most 200 shapes per create_shape call", "coordinates within 0..1600 x 0..900 unless the user asks otherwise"]
category: visualization
---

# tldraw — draw on a live canvas as working memory

The tldraw MCP server exposes a live canvas at `http://localhost:3030`. You
draw into it; the user watches it fill in. The canvas is the fifth memory
layer (see `memory/visual/`): scratch space for spatial reasoning that can
be snapshotted into persistent visual memory.

## When this skill loads

Any time the user asks to visualize, diagram, sketch, lay out, or map
something graphically. If they are clearly asking for prose, do not draw.

## Before drawing, once per session

Tell the user:

> Open `http://localhost:3030` to see the canvas.

If any tool returns `No tldraw browser connected`, repeat the hint and
stop until they confirm.

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

## Persisting drawings as visual memory

When a drawing is worth keeping across sessions (architecture decisions,
recurring diagrams, reference material), snapshot it:

```bash
# 1. fetch current shapes via MCP get_canvas and pipe the JSON in
python3 .agent/memory/visual/visual_memory.py snapshot \
    --label "auth-flow-v1" --tags architecture,auth \
    --note "login + refresh token flow agreed 2026-04-21"
```

The tool reads the canvas JSON on stdin, writes a snapshot file under
`memory/visual/snapshots/`, appends metadata to `snapshots.jsonl`, and
re-renders `INDEX.md`. Later sessions can `list` / `load` to recover the
drawing. Archive with `archive` when stale — never delete (agentic-stack
memory is append-only).

## Pitfalls

- `text` shapes need non-empty `text`.
- `arrow.end` is an absolute point, not a delta.
- Split large scenes into multiple `create_shape` calls (<= 200 each).
- Always `get_canvas` before an edit; never assume ids.

## Self-rewrite hook

After any failure, or every 5 uses:
1. Read the last N tldraw-tagged entries from `memory/episodic/AGENT_LEARNINGS.jsonl`.
2. If a new failure mode has appeared (browser disconnection, invalid
   shape schema, coordinate drift), append the pattern to `KNOWLEDGE.md`.
3. If a constraint was violated (shape cap, id-before-edit rule), escalate
   a candidate lesson to `semantic/LESSONS.md` via `tools/learn.py`.
4. Commit: `skill-update: tldraw, <one-line reason>`.

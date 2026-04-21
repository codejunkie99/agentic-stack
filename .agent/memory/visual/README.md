# Visual memory

The fifth memory layer. Every other layer is text; this one is pictures.

```
working/   scratchpad for the current task
episodic/  raw experience log
semantic/  distilled lessons
personal/  user preferences
visual/    drawings the agent and user share   <-- you are here
```

Visual memory lives as snapshots of a live tldraw canvas (see the
`tldraw` skill). The canvas itself is ephemeral — the browser tab closes,
the drawing is gone. Snapshots make a specific canvas state durable and
recallable.

## Shape

```
visual/
  README.md             this file
  snapshots.jsonl       source of truth: one metadata record per snapshot
  INDEX.md              rendered view of snapshots.jsonl (human-readable)
  snapshots/
    <id>.json           full canvas state for snapshot <id>
    archive/            archived (never deleted) snapshots
  visual_memory.py      CRUD module + CLI
```

`snapshots.jsonl` is the source of truth. `INDEX.md` is re-rendered from
it; do not hand-edit. This mirrors the `lessons.jsonl` / `LESSONS.md`
pattern in `semantic/`.

## CLI

```bash
# capture the current canvas (shapes JSON on stdin)
<get_canvas output> | python3 .agent/memory/visual/visual_memory.py \
    snapshot --label "auth-flow-v1" --tags architecture,auth \
    --note "agreed login + refresh flow"

# list stored snapshots
python3 .agent/memory/visual/visual_memory.py list [--tag architecture]

# load a snapshot's full shape data
python3 .agent/memory/visual/visual_memory.py load <id>

# archive a stale snapshot (moves to snapshots/archive/, never deletes)
python3 .agent/memory/visual/visual_memory.py archive <id>

# show layer status
python3 .agent/memory/visual/visual_memory.py status
```

The module is also importable:

```python
from visual_memory import snapshot, list_snapshots, load_snapshot, archive_snapshot
```

## Rules

- Append-only. `archive` moves a snapshot into `snapshots/archive/`. Nothing
  is ever deleted from disk.
- Ids are time-sortable so `ls snapshots/` reads chronologically.
- Snapshots are self-contained: a single `<id>.json` carries everything
  needed to restore the canvas. `snapshots.jsonl` is an index over them.

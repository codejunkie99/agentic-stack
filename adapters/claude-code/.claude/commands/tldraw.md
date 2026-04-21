---
description: Open, continue, or snapshot the tldraw visual-memory canvas.
---

You are working with the `tldraw` skill. Load
`.agent/skills/tldraw/SKILL.md` first for the full tool reference.

Execute this flow:

1. Call `mcp__tldraw__get_canvas` to see the current canvas.
2. If the canvas is empty or the user's argument describes something new,
   draw it via `mcp__tldraw__create_shape`.
3. If the user's argument says "save", "snapshot", or "remember this",
   pipe the canvas JSON into visual memory:

   ```bash
   python3 .agent/memory/visual/visual_memory.py snapshot \
       --label "<short-label-from-context>" \
       --tags "<comma,separated,tags>" \
       --note "<why this drawing matters>"
   ```

4. Report back: what is now on the canvas, and whether a snapshot was
   written (include its id).

Remind the user once per session to open `http://localhost:3030`.

User argument: $ARGUMENTS

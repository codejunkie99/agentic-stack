# SWOT / 2x2 Matrix

Use for strategic positioning, prioritization matrices, effort-impact grids, and other four-cell frames where the quadrants materially advance the argument.

## Pattern Variants

The SWOT / 2x2 pattern is available via `render_pattern()`:

- **quadrant_grid** (default) — Four rounded-rectangle quadrants with colored borders, header labels, and bullet content per cell.

Default variant: `quadrant_grid` (`styles/variants/swot_2x2/quadrant_grid.py`)

Data schema:
- quadrants: list of 4 objects, each with:
  - label: str (quadrant name, e.g. "Strengths")
  - items: list[str] (bullet points for that quadrant)

Rules:

- keep each quadrant selective; four overcrowded buckets is worse than one sharper framework
- connect the title to the implication, not just the existence of four boxes
- use card borders instead of thin accent bars when rounded-corner gaps would look sloppy
- avoid SWOT when a sharper decision frame exists
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

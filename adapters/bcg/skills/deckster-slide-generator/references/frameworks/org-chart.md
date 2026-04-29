# Org Chart / Cascade Diagram

Use for organizational hierarchies, alliance-tribe-squad models, cascaded operating models, and other parent-child structures where reporting logic is the message.

## Pattern Variants

The org chart pattern is available via `render_pattern()`:

- **cascade_boxes** (default) — Multi-level hierarchy with connected boxes, connector lines, and optional nested-box sub-variant for division-level grouping.

Default variant: `cascade_boxes` (`styles/variants/org_chart/cascade_boxes.py`)

Data schema:
- root: object with:
  - label: str (top-level entity, e.g. "Group CEO")
- levels: list of lists, each inner list contains objects with:
  - label: str (unit or role name)
  - children: list[str] (optional, sub-units under this node)

Use when:

- the message is about span of control, reporting lines, or cascaded ownership
- the reader needs to see parent-child dependency directly
- a nested-box hierarchy is more truthful than columns or bullets

Rules:

- keep the visible depth limited to what supports the title; three clean levels beats six unreadable ones
- group minor roles if the exact org detail is not the point of the slide
- use dashed borders only for illustrative, future-state, or to-be-defined sub-elements
- use solid borders for confirmed, established units
- if the relationship is sequential rather than hierarchical, use a process pattern instead
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

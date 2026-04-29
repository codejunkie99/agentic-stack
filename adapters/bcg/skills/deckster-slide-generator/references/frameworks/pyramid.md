# Pyramid / Hierarchy Diagram

Use for strategy cascades, value chains, layered capability stacks, and other tiered abstractions where each level builds on the one below it.

## Pattern Variants

The pyramid pattern is available via `render_pattern()`:

- **hierarchy_layers** (default) — Stacked horizontal bars widening from top to bottom, with optional side annotations per layer.

Default variant: `hierarchy_layers` (`styles/variants/pyramid/hierarchy_layers.py`)

Data schema:
- levels: list of objects (top to bottom), each with:
  - label: str (level name)
  - annotation: str (optional, side description explaining the level)

Use when:

- each layer represents a real step-up in level, scope, or dependency
- the reader should see accumulation from broad foundation to narrow top-level aspiration
- you need a hierarchy but not a reporting-line org chart

Rules:

- do not use a pyramid when the relationship is actually sequential or cyclical
- keep labels short and cumulative from bottom to top
- make every layer distinct; if two adjacent layers say the same thing, collapse them
- annotations should explain the level, not restate the label
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

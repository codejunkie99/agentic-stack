# Multi-Column Process Flow

Use for workstream overviews, separation planning, or multi-track roadmaps.

## Pattern Variants

The multi-column process pattern is available via `render_pattern()`:

- **workstream_cards** (default) — Numbered circles with title bars and detail cards below, connected by a horizontal timeline line with dots.

Default variant: `workstream_cards` (`styles/variants/multi_column_process/workstream_cards.py`)

Data schema:
- workstreams: list of objects, each with:
  - label: str (workstream name)
  - bullets: list[str] (detail items for the card)

Runtime note:
- `render_pattern()` normalizes `workstreams` into the variant's internal stage schema automatically; use the doc schema above

Rules:

- use `12pt` as the minimum for narrow cards
- for 3-4 columns, use `12pt`
- for 2 columns, use `14pt`
- keep columns structurally parallel
- use this when the audience should compare steps at the same level, not when the main story is directional flow
- if 5 columns do not fit cleanly at `12pt`, simplify or split the slide
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

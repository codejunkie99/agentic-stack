# Gantt-Style Horizontal Bars

Use when duration, overlap, and schedule are the message — project schedules with overlapping timelines.

## Pattern Variants

The gantt pattern is available via `render_pattern()`:

- **workstream_bars** (default) — Horizontal bars with month/quarter headers, alternating row backgrounds, optional milestone diamonds.

Default variant: `workstream_bars` (`styles/variants/gantt/workstream_bars.py`)

Data schema:
- workstreams: list of objects, each with:
  - name: str (workstream label)
  - start: int (start month, 0-indexed)
  - end: int (end month)
  - milestone: int (optional, month number for gate diamond)
- total_months: int (total timeline span)

Implementation notes:
- month headers sit across the top of the bar area
- alternate row backgrounds for readability
- workstream colors are theme-dynamic via `dark_fills()`
- milestone diamonds sit on top of the bars for gate dates

Rules:

- use when duration, overlap, and schedule are the message
- keep task count selective
- show dependencies or milestones only when they matter to the title
- if the message is just order, prefer a simpler timeline
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

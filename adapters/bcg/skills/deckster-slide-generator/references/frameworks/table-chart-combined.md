# Table + Chart Combined

Use when one slide must show both the exact values and the visual pattern, with each component doing a different job.

## Pattern Variants

The table + chart combined pattern is available via `render_pattern()`:

- **dual_evidence** (default) — Table on the left half for precision, chart on the right half for shape. Each component occupies roughly half the content area.

Default variant: `dual_evidence` (`styles/variants/table_chart/dual_evidence.py`)

Data schema:
- table: object with:
  - rows: list of lists (header + data rows)
  - col_widths: list[float] (optional)
- chart: object with:
  - type: str (e.g. "bar", "line")
  - categories: list[str]
  - series: list of series objects

Rules:

- assign distinct roles to the table and chart; one should provide precision, the other shape
- do not duplicate the exact same message twice
- keep the slide balanced so read order is obvious
- if the table dominates, shrink or simplify the chart; if the chart dominates, trim the table to the essential rows
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

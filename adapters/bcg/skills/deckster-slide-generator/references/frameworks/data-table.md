# Data Table

Use for financial summaries, comparison matrices, and assessment grids where exact values matter more than visual trend-shape.

## Pattern Variants

The data table pattern is available via `render_pattern()`:

- **native_table** (default) — Uses `add_table()` with BCG standard styling: green header row, alternating row stripes, template font.

Default variant: `native_table` (`styles/variants/data_table/native_table.py`)

Data schema:
- rows: list of lists (first row is the header, remaining rows are data)
- headers: optional explicit header row; if omitted, `rows[0]` is treated as the header
- col_widths: list[float] (optional, column widths in inches)
- col_align: list[str] (optional, alignment per column: "left", "center", "right")

Variants by use case:
- Financial summary: left-align labels, right-align numbers
- Maturity/assessment grid: left-align capability names, center-align status fields

Rules:

- `add_table()` applies BCG standard styling automatically: green header row, alternating row stripes, template font (Trebuchet MS for BCG default)
- use tables for precision, not decoration
- keep the column count manageable enough to scan
- align text and numbers intentionally; assessment fields often want centered alignment
- do not place a background card behind the table unless there is a specific contrast issue
- if the main message is the pattern rather than the exact values, add or switch to a chart
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

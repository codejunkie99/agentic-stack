# Horizontal Bar

Use when category labels are long or when a ranked list is easier to scan vertically.

## Pattern Variants

Default variant: `horizontal_bar` (`styles/variants/chart/horizontal_bar.py`)

Data schema:
- categories: list[str] (category labels)
- series: list of objects, each with:
  - name: str (series name)
  - values: list[float]
  - point_colors: list[str] (optional, per-point hex colors for single-series highlight)
- colors: list[str] (optional, series-level colors)
- number_format: str (optional)
- data_labels: bool (optional)
- data_label_position: str (optional, e.g. "outEnd")
- legend: bool (optional, set false for single-series)

Use cases:
- Two-series comparison (e.g. Client vs. Competitor)
- Single-series with highlight on the insight-carrying item

Rules:

- sort descending when rank matters
- highlight only the insight-carrying item on single-series charts
- keep labels readable without wrapping if possible
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

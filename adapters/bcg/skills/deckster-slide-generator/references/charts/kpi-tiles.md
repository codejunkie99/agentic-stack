# KPI Tiles

Use when the evidence is a small set of headline metrics rather than a plotted relationship.

## Pattern Variants

Three KPI variants are available via `render_pattern()`:

- **tile_row** (default) — Row of metric cards with left accent bar, title, big number, and change indicator.
- **big_number_dashboard** — 2-4 equal-weight hero metrics with large value, label, and sublabel. Vertical dividers between metrics.
- **chart_kpi_callout** — Combined layout: chart at top, KPI tile row below, and a bottom callout bar for the takeaway.

Default variant: `tile_row` (`styles/variants/kpi/tile_row.py`)
Alternatives:
- `big_number_dashboard` (`styles/variants/kpi/big_number_dashboard.py`) — hero metrics with large values for executive summaries
- `chart_kpi_callout` (`styles/variants/kpi/chart_kpi_callout.py`) — combined chart + KPI + callout layout

Data schema (tile_row):
- kpis: list of objects, each with:
  - title: str (metric name)
  - value: str (headline number, e.g. "$2.4B")
  - change: str (delta indicator, e.g. "+12%")
  - positive: bool (true for favorable change, drives color)

Data schema (big_number_dashboard):
- metrics: list of objects, each with:
  - value: str (large display number)
  - label: str (metric name)
  - sublabel: str (context line)

Data schema (chart_kpi_callout):
- chart: object (chart config — type, categories, series)
- kpis: list of KPI objects (same as tile_row)
- takeaway: str (callout text)

Rules:

- use 3-6 metrics max
- the title should synthesize the metrics rather than repeat them
- if one metric dominates, highlight it without breaking the grid
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

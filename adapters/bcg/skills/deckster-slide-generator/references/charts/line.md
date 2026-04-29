# Line Chart

Use for trends over time or other ordered sequences.

## Pattern Variants

Default variant: `line` (`styles/variants/chart/line.py`)

Data schema:
- categories: list[str] (time periods or ordered labels)
- series: list of objects, each with:
  - name: str (series name)
  - values: list[float]
  - line_dash: str (optional, e.g. "dash" for target/reference lines)
- colors: list[str] (optional, series-level colors)

Rules:

- keep the number of lines low
- use a dashed line for a target or reference series
- annotate key inflection points instead of labeling every marker
- when two lines start near the same value, use `data_labels=False` and add manual callout annotations to avoid overlapping labels
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

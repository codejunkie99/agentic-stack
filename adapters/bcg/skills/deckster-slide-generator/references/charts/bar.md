# Bar Chart

Use for single-series or lightly grouped categorical comparison.

## Pattern Variants

Default variant: `bar` (`styles/variants/chart/bar.py`)

Data schema:
- categories: list[str] (category labels)
- series: list of objects, each with:
  - name: str (series name)
  - values: list[float]
- number_format: str (optional, e.g. "#,##0")

Use when:

- categories are discrete
- relative magnitude is the core message
- the viewer needs rank or comparison quickly

Do not use when:

- the x-axis is truly time and trend shape matters more
- the goal is share-of-whole
- there are too many series for clean labeling

Rules:

- sort categories if rank is the point
- keep series count low
- annotate the standout bar if one category drives the title
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

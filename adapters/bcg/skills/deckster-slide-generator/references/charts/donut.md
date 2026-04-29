# Donut

Use for a simple share-of-whole message with a limited number of segments.

## Pattern Variants

Default variant: `donut` (`styles/variants/chart/donut.py`)

Data schema:
- categories: list[str] (segment names)
- series: list with one object:
  - name: str (series name)
  - values: list[float] (segment values)
- number_format: str (optional, e.g. '0"%"')
- hole_size: int (optional, donut hole percentage, default 55)
- data_labels: bool (optional)

Rules:

- keep segment count small
- group the rest into `Other` if only a few segments matter
- if exact segment comparison matters, switch to bars or a table
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

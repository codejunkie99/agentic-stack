# Area Chart

Use when cumulative magnitude over time is the message and filled volume helps interpretation.

## Pattern Variants

Default variant: `area` (`styles/variants/chart/area.py`)

Data schema:
- categories: list[str] (time periods)
- series: list of objects, each with:
  - name: str (layer name)
  - values: list[float]

Rules:

- keep the number of layers low
- use only when the filled area helps explain contribution or cumulative volume
- switch to a line chart when the fill adds clutter but no insight
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

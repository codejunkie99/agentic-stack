# Stacked Bar

Use for composition across categories when both total size and mix matter.

## Pattern Variants

Default variant: `stacked_bar` (`styles/variants/chart/stacked_bar.py`)

Data schema:
- categories: list[str] (category labels)
- series: list of objects, each with:
  - name: str (segment name)
  - values: list[float]
- number_format: str (optional, e.g. '0"%"')

Rules:

- keep stack order consistent across categories
- keep segment count low enough to scan
- do not use all-green shades (`197A56`, `29BA74`, `84E387`, `C2DD79`) — adjacent bars become indistinguishable. Span the palette: `03522D`, `3EAD92`, `295E7E`, `D4DF33`
- switch to grouped bars or a table when precision matters more than composition
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

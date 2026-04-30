# 2x2 Scatter Bubble Variant

Use for prioritization matrices where initiatives sit in quadrants and bubble size carries a third variable such as value, NPV, or revenue impact.

## Pattern Variants

The scatter bubble pattern is available via `render_pattern()`:

- **portfolio_matrix** (default) — 2x2 grid with colored quadrant backgrounds, axis labels, sized bubbles with value labels, and external label callouts with leader lines.

Default variant: `portfolio_matrix` (`styles/variants/scatter_bubble/portfolio_matrix.py`)

Data schema:
- quadrant_labels: list[str] (4 labels, e.g. ["Prioritize", "Plan Carefully", "Quick Wins", "Deprioritize"])
- x_axis: str (e.g. "Effort")
- y_axis: str (e.g. "Impact")
- initiatives: list of objects, each with:
  - label: str (initiative name)
  - x: float (0-1, position on x-axis)
  - y: float (0-1, position on y-axis)
  - value: float (drives bubble size)
  - quadrant: int (0-3, for color assignment)

Rules:

- label the standout points directly; do not rely on a legend to explain the only important bubbles
- keep axis labels explicit and behaviorally meaningful
- bubble size should add real value, not decoration
- 8pt internal value labels are correct here; do not "fix" them upward and cause overlap
- for crowded maps, external labels with leader lines are better than forcing larger internal labels
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

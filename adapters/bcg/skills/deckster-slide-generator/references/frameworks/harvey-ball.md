# Harvey Ball Matrix

Use for capability/maturity assessments, readiness heatmaps, and qualitative scorecards where the reader needs relative scoring rather than exact values.

## Pattern Variants

The harvey ball pattern is available via `render_pattern()`:

- **maturity_matrix** (default) — Grid of colored circles with row labels, column headers, and a legend row. Score levels map to theme-dynamic fills.

Default variant: `maturity_matrix` (`styles/variants/harvey_ball/maturity_matrix.py`)

Data schema:
- criteria: list[str] (column headers, e.g. ["Data & Analytics", "Cloud & Infra", "AI/ML"])
- domains: list of objects, each with:
  - name: str (row label)
  - scores: list[int] (0-4 score per criterion)
- legend_labels: list[str] (optional, defaults to ["Not started", "Early", "In progress", "Advanced", "Complete"])

Score scale:
- 0 = not started (gray/outline)
- 1 = low (lime)
- 2 = medium (teal)
- 3 = high (BCG green)
- 4 = full (dark green)

Rules:

- ball size is 0.28" with an outline border
- define the scale once and use it consistently across all rows and columns
- keep row and column counts low enough to scan; if the matrix gets large, split it
- include a visible legend unless the audience already knows the scoring standard
- use Harvey balls for relative maturity, not faux precision or exact numeric claims
- if exact values matter, use a table or chart instead
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

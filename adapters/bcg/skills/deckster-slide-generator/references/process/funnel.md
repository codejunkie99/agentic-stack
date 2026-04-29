# Funnel Journey

Encodes narrowing, filtration, conversion, or progressive reduction. Width encodes quantity.

Use when items pass through stages and quantity decreases at each step. Do not use for equal-weight sequential steps.

Use cases:

- customer friction journey
- conversion funnel
- hiring pipeline
- deal flow

Scales:

- 3-6 stages
- bar height and gap adapt automatically

## Pattern Variants

The funnel pattern is available via `render_pattern()`:

- **narrowing_stages** (default) — Centered horizontal bars that narrow progressively, with labels and metrics on each bar.

Default variant: `narrowing_stages` (`styles/variants/funnel/narrowing_stages.py`)

Data schema:
- stages: list of objects, each with:
  - label: str (stage name)
  - metric: str (e.g. "10,000 visitors")

Rules:

- the width change must be meaningful
- show the major loss points, not every tiny footnote
- labels and metrics should stay readable even as bars narrow
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

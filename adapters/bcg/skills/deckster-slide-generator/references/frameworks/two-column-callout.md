# Two-Column With Callout Box

Use for dense contrast when both columns need supporting detail and the slide still needs one explicit takeaway anchored at the bottom.

## Pattern Variants

The two-column callout pattern is available via `render_pattern()`:

- **callout_comparison** (default) — Two equal-width columns with top accent bars and bullet content, plus a full-width rounded callout box at the bottom for the "so what."

Default variant: `callout_comparison` (`styles/variants/two_column/callout_comparison.py`)

Data schema:
- columns: list of 2 objects, each with:
  - header: str (column title)
  - items: list[str] (bullet points)
- callout: str (takeaway text for the bottom callout box)

Rules:

- use the bottom callout to teach the comparison; it should be the "so what", not a label
- the callout must end at or before 6.50in so it does not collide with the source line at 6.74in
- size the two columns symmetrically unless the title clearly implies unequal weight
- if one side is clearly preferred, consider an arrow or contrast layout instead
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

# Frameworks

Import pattern helpers from the standard API:

```python
from bcg_template import BCGDeck, columns, COLORS, CONTENT_START_Y, text_on, dark_fills
from pattern_variants import render_pattern
```

Title rule:

- use `add_content_slide(title)` so the title inherits master-template formatting
- NEVER create manual textboxes for titles or override title formatting (font, size, color, weight). The master style must be preserved for both BCG default and ee4p templates.

Choose by relationship:

- `org-chart.md`: hierarchy or cascade
- `harvey-ball.md`: qualitative scoring / readiness matrix
- `pyramid.md`: tiered hierarchy
- `swot-2x2.md`: quadrant framing
- `scatter-bubble.md`: impact / effort style positioning
- `data-table.md`: exact tabular evidence
- `table-chart-combined.md`: table plus chart
- `exec-summary-cards.md`: executive summary narrative cards
- `compact-row-list.md`: repeated item rows
- `content-structures.md`: columns, icon rows, grids, and vertical stacks
- `two-column-callout.md`: dense contrast slide with a bottom takeaway

Read next by need:

| Need | Read next |
|---|---|
| hierarchy / org design | `org-chart.md` |
| maturity / readiness scoring | `harvey-ball.md` |
| tiered logic | `pyramid.md` |
| quadrant framing | `swot-2x2.md` or `scatter-bubble.md` |
| exact tabular evidence | `data-table.md` |
| table + chart | `table-chart-combined.md` |
| executive summary narrative cards | `exec-summary-cards.md` |
| repeated rows, columns, grids, stacks | `compact-row-list.md` or `content-structures.md` |
| dense side-by-side evidence with takeaway | `two-column-callout.md` |

General rules:

- match the visual structure to the conceptual relationship
- use theme-aware fills rather than hardcoded white text on dark blocks
- keep the title/action logic stronger than the framework label
- treat the coordinates in the examples as BCG-default reference compositions; under `.ee4p`, preserve the structure but let the active manifest govern bounds

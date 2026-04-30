# Process & Timeline Patterns

All process patterns use `bcg_template.py`.

```python
from bcg_template import (
    BCGDeck,
    columns,
    COLORS,
    CONTENT_START_Y,
    DETAIL_CONTENT_START_Y,
    text_on,
    dark_fills,
)
from pattern_variants import render_pattern
```

Title rule:

- `add_content_slide(title)` should populate the title placeholder with zero formatting overrides
- do not build manual title textboxes unless the pattern explicitly requires an additional banner or annotation

Choose by relationship:

- `multi-column-process.md` for workstream overviews and multi-track roadmaps
- `chevron-flow.md` for sequential phases that feed each other
- `timeline.md` for milestone-based roadmaps with dates
- `stage-gate.md` for approval or checkpoint processes
- `gantt.md` for overlapping workstreams over time
- `funnel.md` for narrowing journeys or conversion logic
- `flywheel.md` for cyclical feedback loops

Read next by pattern:

| Need | Read next |
|---|---|
| workstream overview / multi-track roadmap | `multi-column-process.md` |
| explicit sequential feed-through | `chevron-flow.md` |
| dated milestones | `timeline.md` |
| approvals / checkpoints | `stage-gate.md` |
| overlapping workstreams over time | `gantt.md` |
| narrowing journey | `funnel.md` |
| self-reinforcing cycle | `flywheel.md` |

Use process patterns only when the visual grammar is truly sequential, staged, or cyclical. If the slide is mainly comparative, switch back to the frameworks family.

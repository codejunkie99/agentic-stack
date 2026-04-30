# Timeline With Milestones

Use when timing and milestone order both matter — implementation plans with discrete phases and dates.

## Pattern Variants

The timeline pattern is available via `render_pattern()`:

- **phase_cards** (default) — Horizontal timeline with dots on a green line, phase labels above, detail cards below. Supports an optional summary callout.

Default variant: `phase_cards` (`styles/variants/timeline/phase_cards.py`)

Data schema:
- phases: list of objects, each with:
  - name: str (phase name)
  - date: str (e.g. "Q1 2026")
  - details: list[str] (bullet points for the phase card)
- summary: str (optional, key milestone or summary statement for bottom callout)

Rules:

- use when timing and milestone order both matter
- anchor with real periods if available
- show only milestones that support the decision
- `12pt` is the minimum in timeline cards; for 3-column timelines use `14pt`
- keep bottom summaries clear of the source/footer zone
- each phase description should answer: "What happens in this phase, and what does it produce that the next phase needs?" Make the dependency chain visible.
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

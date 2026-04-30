# Executive Summary (SCQA Layout)

Use for the deck's opening content slide or a top-level synthesis slide. The slide title placeholder carries the core recommendation as an action title. SCQA narrative cards fill the content zone below.

Hard rule:

- never use "Situation", "Complication", "Question", or "Answer" as visible card labels

SCQA is invisible scaffolding. The narrative flow itself should carry the logic.

## Pattern Variants

The executive summary pattern is available via `render_pattern()`:

- **hero_scqa** (default) — Narrative cards stacked in the content zone. The answer/recommendation card is highlighted with an accent fill. The slide title placeholder (set via `add_content_slide(title)`) carries the recommendation.

Default variant: `hero_scqa` (`styles/variants/exec_summary/hero_scqa.py`)

```python
# Correct usage — title goes in the placeholder, NOT a manual header
slide = deck.add_content_slide(
    'A $150M investment yields $380M NPV over 3 years',
    source='Source: BCG analysis')
bounds = content_bounds()
render_pattern(deck, slide, "exec_summary", variant="hero_scqa", data={
    "hero_title": "",  # ignored — title is in the placeholder
    "cards": [
        {"headline": "...", "detail": "..."},
        {"headline": "...", "detail": "..."},
        {"headline": "...", "detail": "..."},
        {"headline": "...", "detail": "..."},  # last card = answer, gets accent fill
    ],
}, bounds=bounds)
```

Data schema:
- hero_title: str (ignored — use add_content_slide title instead)
- cards: list of objects, each with:
  - headline: str (card headline — real narrative content, NOT framework labels)
  - detail: str (supporting detail)

Rules:

- keep the card count low; four is the default because it maps naturally to SCQA
- each card headline should be real narrative content, not a visible framework label
- highlight only the answer or recommendation card (last card gets accent fill automatically)
- do not let cards become paragraph containers
- if the deck already has a different executive-summary structure, keep the SCQA logic invisible there too
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

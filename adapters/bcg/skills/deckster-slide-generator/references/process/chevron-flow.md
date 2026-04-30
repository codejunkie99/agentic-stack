# Chevron Process Flow

Use when the message is a genuine left-to-right progression where each phase feeds the next.

## Pattern Variants

The process flow pattern is available via `render_pattern()`:

- **chevron_arrows** (default) — Connected chevron arrow shapes with detail cards below each phase.
- **numbered_steps** — Numbered circles connected by horizontal lines with title and description below. Cleaner look without chevron shapes.

Default variant: `chevron_arrows` (`styles/variants/process_flow/chevron_arrows.py`)
Alternatives: `numbered_steps` (`styles/variants/process_flow/numbered_steps.py`) — cleaner numbered circles for simpler flows

Data schema:
- stages: list of objects, each with:
  - label: str (phase name, keep concise)
  - details: list[str] (bullet points for the phase card)
  - timeline: str (optional, e.g. "Months 1-3")

Rules:

- use for genuine left-to-right progression
- keep the number of chevrons manageable (3-5 is ideal)
- each phase label should be concise
- `12pt` is acceptable for 5-column narrow cards; use `14pt` when there are only 3 columns
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

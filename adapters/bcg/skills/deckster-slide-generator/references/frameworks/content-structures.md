# Content Structures

Use these for repeated peer items that are not a chart, table, or process flow.

## Three-Column Pillars

Use for 3 equal-weight concepts, capabilities, or workstreams.

Default variant: `pillar_cards` (`styles/variants/column_cards/pillar_cards.py`)
Alternatives: `icon_row` (`styles/variants/column_cards/icon_row.py`) — concise 3-4 item capabilities with descriptive icons

Data schema (pillar_cards):
- items: list of objects, each with:
  - icon: str (icon name)
  - title: str (pillar heading)
  - bullets: list[str] (detail items)

## Icon Row

Use for 3-4 concise capabilities or themes.

Default variant: `icon_row` (`styles/variants/column_cards/icon_row.py`)

Data schema:
- items: list of objects, each with:
  - icon: str (icon name)
  - title: str (heading)
  - description: str (body text)

Rules:

- use descriptive icons, not numeric badges, when the items represent concepts
- keep headers and descriptions similar in length
- if the items become ranked or sequential, switch to vertical stack or process rows

## 2x3 Grid

Use when 6 peer items are truly equal-weight.

Default variant: `two_by_three` (`styles/variants/grid_layout/two_by_three.py`)

Data schema:
- items: list of 6 objects, each with:
  - title: str
  - description: str

Rules:

- a grid implies no order
- if some items are clearly more important, use a vertical stack instead
- keep all headers and descriptions structurally parallel

## Vertical Stack

Use when items are ranked or ordered by importance.

Default variant: `ranked_rows` (`styles/variants/vertical_stack/ranked_rows.py`)

Data schema:
- items: list of objects (in rank order), each with:
  - title: str (header)
  - description: str (body)

## Process Rows Variant

Use when each row is an execution phase with a specific deliverable.

Rules:

- number the rows
- keep the header brief and the detail explicit
- separate rows with thin divider lines
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

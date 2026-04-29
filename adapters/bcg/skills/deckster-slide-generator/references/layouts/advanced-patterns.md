# Advanced Patterns

Use these when the standard family guides are not enough. These are still active guidance, not archival notes.

## Section Divider Rule

Choose one divider style and use it consistently:

- `section_header_box`
- `section_header_line`

Hard rule:

- never add bullets, quotes, or other content to a section divider

`green_left_arrow` is a content layout, not a section divider.

## Blank Canvases

Use blank layouts only for truly custom compositions. Once you choose a blank canvas, all placement is manual.

Runtime variants:

- `blank`
- `blank_green`
- `quote`

## Card Fill Contrast

| Slide background | Card fill | Why |
|---|---|---|
| Gray (standard, `detail=False`) | `WHITE` (FFFFFF) | White cards pop against gray |
| White (detail, `detail=True`) | `LIGHT_BG` (F2F2F2) | Light gray provides subtle separation |
| Green panel | `WHITE` (FFFFFF) | White contrasts against green |
| Blank | `LIGHT_BG` (F2F2F2) | Same as detail |

Omit the `fill_color` parameter on `add_card()` and the engine auto-selects the right fill. Only pass explicit fills for special cases (dark cards for high contrast).

White-on-white is not a subtle effect; it is usually a broken boundary.

## Card Border Rule

Use `line_color=accent_color, line_width=1.5` on rounded rectangles. Do NOT add separate thin accent bars on top of rounded rectangles -- this causes white gaps at rounded corners. For top accents, use `add_card(accent_color=..., accent_position='top')` instead.

For light-fill cards: always use `accent_position='top'`. Left accents on light cards lose their visible boundary.

## Left Accent Bar Rows

Use for repeated rows where a thin vertical accent bar improves scanability.

Default variant: `left_bar_items` (`styles/variants/accent_rows/left_bar_items.py`)

Data schema:
- items: list of objects, each with:
  - icon: str (icon name)
  - title: str
  - description: str
- colors: list[str] (optional, per-row accent colors; defaults to green gradient)

## Timeline / Roadmap Bottom Callout

Timelines often leave dead space below the phases. Add a bottom callout to anchor the slide and reinforce the key message. The callout is a rounded rectangle at y=6.10, h=0.40 with BCG_GREEN border.

## Split Content With Vertical Separator

Use a vertical green separator when two panels need equal visual weight but are conceptually distinct.

Boundary rule:

- stop cards and boxes about 0.15in before the divider
- when in doubt, use a wider `columns(2, gap=0.6)` gutter instead of forcing edge-to-line collisions

## Template-Specific Arrow Variants

BCG runtime layouts such as `left_arrow`, `green_arrow_half`, and `arrow_one_third` remain valid when you are intentionally targeting the built-in template. Treat them as lower-level runtime variants of the normalized framing / contrast families rather than separate semantic concepts.

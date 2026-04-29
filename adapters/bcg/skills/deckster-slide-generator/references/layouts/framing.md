# Framing Layouts

These layouts encode a short framing statement on the accent side and supporting evidence on the main side. The active template manifest owns geometry; use `content_bounds()` for dynamic positioning.

## Green One-Third - Category + Members

Use for capability descriptions, team introductions, single-topic deep dives, and other slides where the left panel names the category and the right side enumerates the specific members of that category.

Default variant: `green_one_third` (`styles/variants/split_panel/green_one_third.py`)

Data schema:
- section_header: str (right panel header, e.g. "Key initiatives")
- items: list of objects, each with:
  - title: str
  - description: str

On the native `green_one_third` and `d_green_one_third` layouts, the left panel is owned by the slide title placeholder. Do not add manual textboxes, bullets, cards, or helper shapes there. `panel_title` and `panel_subtitle` are legacy fallback inputs only when the pattern is rendered outside the native layout.

**Vertical centering applies here too.** Center right-panel content inside the safe content band returned by `content_bounds(...)`, not against the full 7.5" slide height. Use `stack_y_positions(bounds, heights, gap=...)` or `start_y = bounds['y'] + max(0, (bounds['h'] - total_block_height) / 2)`.

Education rule:

- the left panel names the category
- the right panel lists specific members of that category
- if the right-side items could be swapped without the reader noticing, the content is too generic

Template-specific variant:

- `white_one_third` is the same pattern without the green accent; use it only when a neutral left panel is important

## Green Left Arrow - Decision Ask / Framing Thesis

Use for decision asks, context framing, or a short thesis where the proof sits on the right-hand side.

Default variant: `green_left_arrow` (`styles/variants/split_panel/green_left_arrow.py`)

Decision-option variant: `decision_cards` (`styles/variants/split_panel/decision_cards.py`) for 2-4 framed options with one recommended path highlighted.

Data schema:
- arrow_title: str (short framing question or thesis, 3-4 words / 25 chars max). On the native `green_left_arrow` layout this is usually the slide title / left-panel framing text; only pass it separately when manually rendering the pattern outside that layout.
- subheader: str (right panel section header)
- items: list of objects, each with:
  - icon: str (icon name)
  - title: str
  - description: str

The native left arrow layouts reserve the left panel for the layout title placeholder. Do not add manual textboxes, bullets, cards, or other content shapes there.

Gray slice deprecation:

- legacy `gray_slice` guidance now maps here; use `green_left_arrow` instead of reviving `gray_slice`

Font sizes for green_left_arrow:

| Element | Size | Notes |
|---|---|---|
| Subheader | 13-14pt | Bold, on right panel |
| Body / bullets | 12pt default | Use 13-14pt for row titles only when the item count and available space clearly support it |
| Icons | 0.5-0.75" | `add_icon()` size parameter |

Right panel geometry: use `content_bounds('green_left_arrow')` to get dynamic `right_x`, `right_w`, `y`, and `h`. BCG default exposes the right authored-content zone at x~5.2", width ~7.5", with the safe vertical band starting below the title placeholder. If the variant is called with a pre-split right-zone bounds box instead of full slide bounds, keep that zone and do not recompute the split.

**CRITICAL -- Vertical centering (right content zone):**

Compute against the safe band, not the full slide:

`start_y = bounds['y'] + max(0, (bounds['h'] - total_block_height) / 2)`

Preferred helper:

`ys = stack_y_positions(bounds, heights, gap=0.12)`

Do NOT start content at a hardcoded top like `CONTENT_START_Y`, and do NOT center against 7.5". Title-left layouts reserve space above the safe band for the title placeholder.

Rules:

- keep arrow-panel titles to 3-4 words / 25 characters
- keep the arrow/framing side short; the evidence side should do the analytical work
- content on the right panel should be vertically centered or top-stacked inside the safe content band
- the left title panel is reserved for the slide title placeholder; do not place manual content there
- right panel content is naked icon + title + description rows directly on white -- do NOT use rounded rectangles, cards, or fill backgrounds on the right panel. Icons at size=0.5-0.75, color=BCG_GREEN; titles at 13-14pt bold; descriptions at 12pt
- source text on green/arrow layouts must be WHITE (not MED_GRAY), width constrained to the green area (w approximately 3.5")
- do not use these layouts as section dividers

Template-specific runtime variants:

- `left_arrow` keeps the arrow framing but moves the accent treatment to the other side
- `arrow_one_third` and `green_arrow_one_third` are narrower arrow relatives; use only when the template explicitly exposes them and the message still fits the same framing logic

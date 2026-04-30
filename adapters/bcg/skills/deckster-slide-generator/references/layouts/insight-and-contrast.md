# Insight And Contrast Layouts

Use `green_highlight` when the slide needs a main evidence zone plus a distinct interpretation zone. Use `arrow_half` when the structural split itself is the argument.

## Green Highlight - Content + Insight Takeaway

Use when the slide has a finding or voice that deserves its own visual zone instead of a bottom callout.

Default variant (quote): `green_highlight_quote` (`styles/variants/split_panel/green_highlight_quote.py`)
Alternative (structured insights): `green_highlight_insights` (`styles/variants/split_panel/green_highlight_insights.py`)

**Zone boundaries (critical -- content must NOT cross these):**

| Zone | X start | Width | Use for |
|---|---|---|---|
| Left (analysis) | 0.69" | **6.80"** (to ~7.5") | Charts, tables, cards, KPIs -- same patterns as d_title_only |
| Right (insight panel) | **8.20"** | **4.30"** (to ~12.5") | Takeaway quote or structured insights — the green accent background is already provided by the slide master |

Tables and charts on the left MUST set `w=6.80` or less -- never use the full 11.96" content width on this layout, or they will bleed into the green accent panel. When using `render_pattern()`, let the variant own the right-panel geometry.

**CRITICAL — Do NOT draw a green rectangle on the right panel.** The slide master already provides the green accent background on the right side (from ~7.84" onward). Adding `add_rectangle()`, `add_rounded_rectangle()`, or `add_card()` with a green fill in the right zone creates a visible "floating container" artifact — a rounded-corner box on top of the flat green background. Instead, place textboxes, icons, and content elements directly at the `right_x`/`right_w` coordinates using `text_on(COLORS["BCG_GREEN"])` for text contrast. The background is already green.

Hard rule for the right panel:

- pick exactly one format per slide
- do not label the panel "Key Finding", "Key Insight", or "So What"

Valid right-panel formats:

- **Format A (quote)**: one statement or attributed quote at **14-16pt**, attribution at 12pt
- **Format B (structured insights)**: two or three structured insights -- headers at **13-14pt bold**, body at **12pt**

Data schema (quote format):
- quote: str (statement text)
- attribution: str (e.g. "-- Sarah Chen, Chief Digital Officer")

Data schema (structured insights format):
- insights: list of objects, each with:
  - header: str
  - detail: str

Rules:

- the right panel must add interpretation beyond the title
- quotes require attribution
- do not mix quotes and structured insights in the same panel
- if you cannot articulate a distinct takeaway beyond the title, use a standard evidence slide instead

Template-specific variant:

- `d_four_column_green` follows the same logic but allows a wider title area

## Arrow Half - Content Contrast

Use for true contrast: before/after, current/target, problem/solution, cause/effect.

`arrow_half` can also pair content with an image (white arrow panel + image on green right side). Use when evidence needs a supporting photo alongside structured content.

Default variant: `split_cards` (`styles/variants/before_after/split_cards.py`)

Data schema:
- before_label: str (e.g. "Current State")
- after_label: str (e.g. "Target State")
- before_items: list of objects, each with:
  - title: str
  - description: str
- after_items: list of objects, each with:
  - title: str
  - description: str

Zone geometry:
- Left zone: x=0.69", w=5.20" -- white area for current state / problem content
- Right zone: x=7.00", w=5.40" -- the green/accent panel zone

Rules:

- both sides should be structurally parallel -- BOTH sides have LIGHT_BG (F2F2F2) card backgrounds with NO outlines
- label the contrast cleanly: "Current State" on white side, "Target State" on green side
- zone labels are plain textboxes (16pt, bold) placed ABOVE the cards, not inside them
- both left and right cards: LIGHT_BG (F2F2F2) rounded rectangles, no borders
- the visual contrast comes from the layout's accent panel background (green/blue) plus consistent left/right zone geometry, not from card styling differences
- keep the left/right semantics obvious
- do NOT place a full-width takeaway banner that spans both zones on arrow_half layouts. If a takeaway is needed, place it as a callout within ONE zone (typically the left/white side), or use a separate d_title_only slide
- if the contrast is weak, use a simpler two-column framework instead

## Before / After On A Standard Content Slide

Use this when the contrast is the message but you do not want a dedicated layout frame. The before_after/split_cards variant also supports rendering on a standard content slide with two columns, an arrow shape between them, and accent-colored cards.

Rules:

- use `columns(2, gap=1.5)` to leave room for the transition arrow between cards
- label both sides clearly
- always call `render_pattern()` with `bounds=content_bounds()` -- do not hardcode coordinates

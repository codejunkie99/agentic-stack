# Layout Families

Layout guidance describes when to use a semantic family and how to populate it. The active `template.json` remains the source of truth for geometry and placeholder bounds; the references here preserve the authoring logic and Python composition patterns from the legacy skill.

## Quick Reference

| Group | Primary families | Use when |
|---|---|---|
| Full-page (**default**) | `content`, `detail=True` (**default for ~86% of slides**) | default evidence slides, tables, charts, multi-column structures |
| Framing split | `green_left_arrow`, `green_one_third` | decision ask, framing question, category + members |
| Contrast / insight | `green_highlight`, `arrow_half`, `arrow_two_third` | insight panel, before/after, current/target, directional contrast |
| Image split | `green_half`, `green_two_third` | title-led image slides where the image materially supports the message |
| Statement | `big_statement_green`, `big_statement_icon` | high-impact punctuating statement |
| Structural | `title_slide`, `section_divider`, `disclaimer`, `end` | non-content slides |

Template-specific runtime variants that still exist in the built-in template:

- `special_gray`
- `white_one_third`
- `left_arrow`
- `arrow_one_third`
- `green_arrow_half`
- `blank`
- `blank_green`
- `quote`

Use these family guides:

- `framing.md`
- `insight-and-contrast.md`
- `image-led.md`
- `statement.md`
- `detail-mode.md`
- `advanced-patterns.md`

Read next by family:

| Family | Read next |
|---|---|
| framing split | `framing.md` |
| contrast / insight | `insight-and-contrast.md` |
| image-led | `image-led.md` |
| statement | `statement.md` |
| full-page detail workhorse | `detail-mode.md` |
| custom or template-specific edges | `advanced-patterns.md` |

## Slide Dimensions and Key Constants

Slide size: **13.33" x 7.50"** (standard widescreen).

Y-coordinate constants:

| Constant | Value | When to use |
|---|---|---|
| `CONTENT_START_Y` | 2.27" | Standard title slides — content begins below title placeholder |
| `DETAIL_CONTENT_START_Y` | 1.70" | Detail-mode slides (`detail=True`) — smaller title gives more room |
| `CONTENT_START_Y_TIGHT` | 1.65" | Fallback when content overflows at the standard start position |
| `CONTENT_END_Y` | 6.50" | Bottom boundary for body content (before source/footer area) |
| `SOURCE_Y` | 6.74" | Y position for source/footnote text |

Column widths (content area 0.69" to 12.65"):

| Columns | Each width | Gutter |
|---|---|---|
| 2 | 5.83" | 0.31" |
| 3 | 3.78" | 0.31" |
| 4 | 2.76" | 0.31" |
| 5 | 2.14" | 0.31" |

## Split-Layout Vertical Centering (Title-Left Families)

On layouts where the title is in the LEFT panel (not at the top) -- `green_left_arrow`, `left_arrow`, `green_one_third`, `green_half`, `green_two_third` -- the left panel is owned by the layout title placeholder. Do not add manual textboxes, bullets, cards, or overlays there.

- **Right-side authored content:** Calculate total content block height, then `start_y = (7.5 - block_height) / 2`. Do NOT start at `CONTENT_START_Y`.
- **Left-side title panel:** treat it as reserved. The title placeholder already provides the left-panel framing.
- **Image-led families (`green_half`, `green_two_third`):** these are title + image layouts. Do not add body text on either side.

This rule applies to ALL split layouts, not just green_left_arrow. See framing.md for the worked example.

## Slide Creation Rule

**NEVER call `_add_slide_from_layout()` directly.** Always use `deck.add_content_slide(title, layout=...)` — the title placeholder inherits font, size, color, and weight from the master template. Bypassing this loses those inherited properties and produces inconsistent slides.

## Visual Rhythm Rules

- **4-slide rule**: after 3 consecutive `d_title_only` slides, the 4th should use a split layout if the content permits
- **Pivot placement**: the slide immediately after a section divider is prime for `green_one_third` (framework framing) or `green_left_arrow` (section thesis)
- **Bookend**: use a statement layout (`big_statement_icon` or `big_statement_green`) at the deck's emotional peak — typically the recommendation or closing. Limit to 1-2 per deck.

## Multi-Block Arrangement

When a slide has 3+ content blocks (e.g., chart + KPIs + risk list), pair the tallest block with the shortest in the same column so both columns fill the content zone.

Anti-pattern: two short blocks side-by-side on top + third block spanning full width below (creates dead corners). Fix: L-arrangement where each column spans from `CONTENT_START_Y` to near `CONTENT_END_Y`.

## Selection Rules

- if the relationship is hierarchy, do not use equal columns
- if the slide is a decision ask, do not use a peer grid
- if the image is decorative rather than evidentiary, do not choose an image split
- if the slide needs supporting evidence, do not force it into a statement layout
- if the slide is a section break, use a real divider and nothing else
- if the slide is really a pivot question or decision ask, route through the framing family rather than forcing equal columns
- if the slide needs body copy in addition to an image, do not force that copy into `green_half` or `green_two_third`

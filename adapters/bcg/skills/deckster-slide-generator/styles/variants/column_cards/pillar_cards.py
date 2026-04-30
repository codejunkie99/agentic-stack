"""Pillar cards — icon circle + header bar + bullet list per column.

Default column_cards variant. Draws N equal-width columns, each with a
colored icon circle at top, a BCG_GREEN header bar with the item title,
and a bullet list of details below.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render pillar cards in columns.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {
                    "title": str,
                    "icon": str,
                    "bullets": [str, ...],
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    items = data.get("items", [])
    n = len(items)

    if n < 1:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    cols = columns(n, total_width=w, start_x=x0, gutter=0.31)
    fills = dark_fills(n)

    icon_size = 0.65
    icon_circle_size = 0.80
    header_h = 0.40
    body_sz = 12 if n <= 3 else 11

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for i, (cx, cw) in enumerate(cols):
        item = items[i]
        fill = fills[i % len(fills)]

        # Icon circle at top center of column
        icon_cx = cx + cw / 2 - icon_circle_size / 2
        icon_cy = y0
        deck.add_oval(slide, icon_cx, icon_cy,
                      icon_circle_size, icon_circle_size, fill)

        # Icon inside circle
        icon_name = item.get("icon", "lightbulb")
        icon_offset = (icon_circle_size - icon_size) / 2
        deck.add_icon(slide, icon_name,
                      icon_cx + icon_offset, icon_cy + icon_offset,
                      size=icon_size, color=text_on(fill))

        # Header bar below icon circle
        bar_y = y0 + icon_circle_size + 0.15
        deck.add_rectangle(slide, cx, bar_y, cw, header_h, COLORS["BCG_GREEN"])
        deck.add_textbox(slide, item.get("title", ""),
                         cx + 0.10, bar_y,
                         cw - 0.20, header_h,
                         sz=14, color=text_on(COLORS["BCG_GREEN"]),
                         bold=True, align="center", valign="middle")

        # Card body with bullet list
        card_y = bar_y + header_h + 0.10
        card_h = h - (card_y - y0) - 0.05
        deck.add_card(slide, cx, card_y, cw, card_h, fill_color=card_fill)

        # Bullets inside card
        bullets = item.get("bullets", [])
        if bullets:
            deck.add_bullets(slide, bullets,
                             cx + 0.12, card_y + 0.12,
                             cw - 0.24, card_h - 0.24,
                             sz=body_sz, color=card_text, spc_after=4)

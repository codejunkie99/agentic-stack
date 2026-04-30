"""Callout comparison -- two symmetric columns with accent bars and bottom callout.

Each column has a white card with a green accent bar at top, a header,
and bulleted items. A bottom callout box spans full width with the key
takeaway.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a two-column callout comparison.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "left": {"header": str, "items": [str, ...]},
            "right": {"header": str, "items": [str, ...]},
            "callout": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    left = data.get("left", {})
    right = data.get("right", {})
    callout = data.get("callout", "")

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Bottom callout reservation
    callout_h = 0.40 if callout else 0
    callout_gap = 0.15 if callout else 0
    col_area_h = h - callout_h - callout_gap

    cols = columns(2, total_width=w, start_x=x0, gutter=0.31)
    sides = [left, right]

    col_card_fill = card_fill_for_slide()
    col_card_text = text_on(col_card_fill)
    accent = COLORS["BCG_GREEN"]

    for i, (cx, cw) in enumerate(cols):
        side = sides[i]

        # White card background
        deck.add_rectangle(slide, cx, y0, cw, col_area_h, col_card_fill)

        # Accent bar at top
        deck.add_rectangle(slide, cx, y0, cw, 0.05, accent)

        # Header
        deck.add_textbox(slide, side.get("header", ""),
                         cx + 0.20, y0 + 0.20,
                         cw - 0.40, 0.35,
                         sz=16, color=col_card_text, bold=True)

        # Bulleted items
        items = side.get("items", [])
        if items:
            deck.add_bullets(slide, items,
                             cx + 0.20, y0 + 0.65,
                             cw - 0.40, col_area_h - 0.85,
                             sz=14, color=col_card_text, spc_after=6)

    # Bottom callout
    if callout:
        cy = y0 + col_area_h + callout_gap
        callout_fill = card_fill_for_slide()
        deck.add_rounded_rectangle(slide, x0, cy, w, callout_h,
                                   callout_fill,
                                   line_color=accent,
                                   line_width=1.5, radius=8000)
        deck.add_textbox(slide, callout,
                         x0 + 0.20, cy,
                         w - 0.40, callout_h,
                         sz=14, color=text_on(callout_fill),
                         bold=True, valign="middle")

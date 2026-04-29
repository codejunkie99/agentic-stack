"""Ranked rows — numbered vertical rows with badge, header, description, separators.

Each row has a numbered badge on the left, bold header, description text,
and a subtle separator line between rows.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render numbered ranked rows.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {"header": str, "description": str},
                ...
            ],
            "callout": str (optional)
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, card_fill_for_slide

    items = data.get("items", [])
    if not items:
        return
    callout = data.get("callout", "")

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    n = len(items)
    badge_size = 0.40
    gap = 0.08
    callout_gap = 0.10 if callout else 0.0
    callout_h = 0.55 if callout else 0.0
    row_h = (h - gap * (n - 1) - callout_gap - callout_h) / n  # Fill available height evenly
    row_h = min(row_h, 1.20)  # Cap at reasonable max
    sep_color = card_fill_for_slide()
    desc_sz = 12 if row_h >= 1.00 else 11

    for i, item in enumerate(items):
        ry = y0 + i * (row_h + gap)

        # Number badge
        deck.add_number_badge(slide, i + 1,
                              x0, ry + 0.08,
                              size=badge_size,
                              fill_color=COLORS["BCG_GREEN"])

        # Header
        text_x = x0 + badge_size + 0.15
        text_w = w - badge_size - 0.15
        slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
        slide_text = text_on(slide_bg)
        deck.add_textbox(slide, item.get("header", ""),
                         text_x, ry + 0.05,
                         text_w, 0.30,
                         sz=14, color=slide_text, bold=True)

        # Description
        deck.add_textbox(slide, (item.get("description") or item.get("desc") or item.get("detail") or ""),
                         text_x, ry + 0.35,
                         text_w, row_h - 0.45,
                         sz=desc_sz, color=slide_text)

        # Separator line between rows (not after last)
        if i < n - 1:
            sep_y = ry + row_h - 0.02
            deck.add_line(slide, x0, sep_y, w, 0,
                          color=card_fill_for_slide(), width=1)

    if callout:
        callout_y = y0 + n * row_h + gap * (n - 1) + callout_gap
        deck.add_textbox(
            slide,
            callout,
            x0,
            callout_y,
            w,
            callout_h,
            sz=12,
            color=COLORS["BCG_GREEN"],
            bold=True,
            align="left",
            valign="middle",
        )

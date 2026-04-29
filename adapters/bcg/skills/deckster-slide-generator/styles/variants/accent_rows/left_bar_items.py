"""Left bar items — repeating rows with cycling left accent colors.

Renders rows with a colored left accent bar (cycling through dark fills),
an icon, bold title, and description text.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render accent row items.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {"icon": str, "title": str, "description": str},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, card_fill_for_slide

    items = data.get("items", [])
    if not items:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    n = len(items)
    fills = dark_fills(n)
    row_gap = 0.12
    row_h = min(0.85, (h - (n - 1) * row_gap) / n)
    accent_w = 0.08
    icon_size = 0.45

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for i, item in enumerate(items):
        ry = y0 + i * (row_h + row_gap)
        fill = fills[i % len(fills)]

        # Card background
        deck.add_card(slide, x0, ry, w, row_h,
                      fill_color=card_fill,
                      accent_color=fill, accent_position="left")

        # Icon
        icon_name = item.get("icon", "lightbulb")
        icon_x = x0 + accent_w + 0.15
        icon_y = ry + (row_h - icon_size) / 2
        deck.add_icon(slide, icon_name,
                      icon_x, icon_y,
                      size=icon_size, color=fill)

        # Title
        text_x = icon_x + icon_size + 0.12
        text_w = w - (text_x - x0) - 0.15
        deck.add_textbox(slide, item.get("title", ""),
                         text_x, ry + 0.08,
                         text_w, 0.28,
                         sz=14, color=card_text, bold=True)

        # Description
        deck.add_textbox(slide, (item.get("description") or item.get("desc") or item.get("detail") or ""),
                         text_x, ry + 0.38,
                         text_w, row_h - 0.46,
                         sz=12, color=card_text)

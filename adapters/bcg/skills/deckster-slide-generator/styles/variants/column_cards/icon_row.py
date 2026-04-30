"""Icon row — horizontal rows with icon circle, title, and description.

Alternative column_cards variant. Instead of vertical columns, items are
stacked as horizontal rows. Each row has an icon circle on the left,
a bold title, and a description to the right. Works well for 4-6 items
that need more horizontal text space.
"""


def validate(deck, slide, data, bounds, **kwargs):
    items = data.get("items", [])
    if not items:
        return ["provide at least 1 item"]
    if len(items) > 6:
        return ["limit icon_row to 6 items or fewer"]
    issues = []
    for idx, item in enumerate(items, start=1):
        if not item.get("title"):
            issues.append(f"item {idx} is missing a title")
        if not (item.get("description") or item.get("desc") or item.get("detail")):
            issues.append(f"item {idx} is missing a description")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render items as horizontal icon rows.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {
                    "title": str,
                    "description": str,
                    "icon": str,
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, card_fill_for_slide

    items = data.get("items", [])
    n = len(items)

    if n < 1:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    fills = dark_fills(n)

    # Row layout
    row_gap = 0.15
    row_h = min(1.05, (h - (n - 1) * row_gap) / n)
    icon_circle_size = min(0.65, row_h - 0.10)
    icon_display_size = icon_circle_size * 0.70
    text_x = x0 + icon_circle_size + 0.30
    text_w = w - icon_circle_size - 0.40

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    title_sz = 14
    desc_sz = 12
    if n >= 5:
        title_sz = 14
        desc_sz = 12

    # Vertically center the block of rows within bounds
    total_block_h = n * row_h + (n - 1) * row_gap
    start_y = y0 + (h - total_block_h) / 2

    for i, item in enumerate(items):
        fill = fills[i % len(fills)]
        ry = start_y + i * (row_h + row_gap)

        # Card background for the row
        deck.add_card(slide, x0, ry, w, row_h,
                      fill_color=card_fill,
                      accent_color=fill, accent_position="left")

        # Icon circle
        icon_cy = ry + (row_h - icon_circle_size) / 2
        deck.add_oval(slide, x0 + 0.15, icon_cy,
                      icon_circle_size, icon_circle_size, fill)

        # Icon inside circle
        icon_name = item.get("icon", "lightbulb")
        icon_offset = (icon_circle_size - icon_display_size) / 2
        deck.add_icon(slide, icon_name,
                      x0 + 0.15 + icon_offset,
                      icon_cy + icon_offset,
                      size=icon_display_size,
                      color=text_on(fill))

        # Title + description — vertically centered within the row
        title = item.get("title", "")
        desc = (item.get("description") or item.get("desc") or item.get("detail") or "")

        title_h = 0.30
        desc_h = row_h - 0.50 if desc else 0
        gap = 0.08 if desc else 0
        text_block_h = title_h + gap + desc_h
        text_top = ry + (row_h - text_block_h) / 2

        deck.add_textbox(slide, title,
                         text_x, text_top,
                         text_w, title_h,
                         sz=title_sz, color=card_text, bold=True, valign="middle")

        if desc:
            deck.add_textbox(slide, desc,
                             text_x, text_top + title_h + gap,
                             text_w, desc_h,
                             sz=desc_sz, color=card_text)

"""Icon rows -- stacked rows with left accent bar, icon, title, description.

Each row is a card with a left accent bar, an icon, a bold title,
a description, and an optional right-side label badge.
"""


def _estimate_lines(text, chars_per_line):
    text = (text or "").strip()
    if not text:
        return 0
    return max(1, (len(text) + chars_per_line - 1) // chars_per_line)


def validate(deck, slide, data, bounds, **kwargs):
    items = data.get("items", [])
    if not items:
        return ["provide at least 1 item"]
    if len(items) > 5:
        return ["limit icon_rows to 5 items or split the slide"]
    issues = []
    row_gap = 0.05 if len(items) >= 5 else 0.10
    row_h = (bounds["h"] - row_gap * (len(items) - 1)) / len(items)
    desc_w = max(bounds["w"] - 3.95, 4.2)
    desc_cpl = max(int(desc_w * 8.4), 34)
    for idx, item in enumerate(items, start=1):
        desc_lines = _estimate_lines(item.get("description") or item.get("desc") or item.get("detail") or "", desc_cpl)
        if row_h < 0.78 and desc_lines > 2:
            issues.append(f"row {idx} description is too dense for icon_rows; shorten to ~2 lines")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render compact icon rows.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {
                    "icon": str,
                    "title": str,
                    "description": str,
                    "label": str (optional)
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    items = data.get("items", [])
    n = len(items)
    if n == 0:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Adaptive row sizing
    gap = 0.12 if n <= 4 else 0.05
    row_h = min(0.95, (h - gap * (n - 1)) / n)
    icon_size = 0.55 if row_h >= 0.88 else 0.36

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)
    accent = COLORS["BCG_GREEN"]

    y = y0
    for item in items:
        # Card with left accent
        deck.add_card(slide, x0, y, w, row_h,
                      fill_color=card_fill,
                      accent_color=accent,
                      accent_position="left")

        # Icon
        icon_name = item.get("icon", "Strategy")
        deck.add_icon(slide, icon_name,
                      x0 + 0.35, y + (row_h - icon_size) / 2,
                      size=icon_size,
                      color=accent)

        # Title
        title_x = x0 + 0.35 + icon_size + 0.15
        title_h = 0.22 if row_h < 0.85 else 0.26
        title_y = y + 0.08
        deck.add_textbox(slide, item.get("title", ""),
                         title_x, title_y,
                         3.35, title_h,
                         sz=14, color=accent,
                         bold=True, valign="middle")

        # Description (accept "description", "desc", or "detail")
        desc_text = item.get("description") or item.get("desc") or item.get("detail") or ""
        desc_w = w - (title_x - x0) - 0.20
        has_label = bool(item.get("label"))
        if has_label:
            desc_w -= 1.95
        desc_y = title_y + title_h + 0.06
        deck.add_textbox(slide, desc_text,
                         title_x, desc_y,
                         desc_w, max(row_h - (desc_y - y) - 0.10, 0.22),
                         sz=12, color=card_text, valign="top")

        # Optional right-side label
        label = item.get("label", "")
        if label:
            deck.add_label(slide, label,
                           x0 + w - 1.85, y + (row_h - 0.32) / 2,
                           1.65, 0.32, sz=12)

        y += row_h + gap

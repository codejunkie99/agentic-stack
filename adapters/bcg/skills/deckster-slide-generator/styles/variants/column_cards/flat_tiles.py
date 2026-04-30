"""Flat tiles — minimal column cards without icon circles or header bars.

Clean, modern look with just a thin top accent line, bold title, and body text.
No icons, no filled headers — content-first design.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render flat tile column cards.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {"items": [{"header": str, "bullets": [str] or "description": str}]}
        bounds: {"x": float, "y": float, "w": float, "h": float}
    """
    from bcg_template import COLORS, text_on, card_fill_for_slide

    items = data.get("items", [])
    n = len(items)
    if n < 1:
        return

    gap = 0.31
    total_w = bounds.get("w", 11.96)
    x0 = bounds.get("x", 0.69)
    col_w = (total_w - gap * (n - 1)) / n
    cols = [(x0 + i * (col_w + gap), col_w) for i in range(n)]
    card_y = bounds["y"] + 0.10
    card_h = bounds["h"] - 0.20

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for i, (x, w) in enumerate(cols):
        if i >= len(items):
            break
        item = items[i]

        # Light card with thin BCG_GREEN top line
        deck.add_rounded_rectangle(slide, x, card_y, w, card_h,
                                   card_fill,
                                   radius=3000)
        deck.add_rectangle(slide, x + 0.10, card_y, w - 0.20, 0.04,
                           COLORS["BCG_GREEN"])

        # Title
        deck.add_textbox(slide, item.get("header", ""),
                         x + 0.15, card_y + 0.20, w - 0.30, 0.50,
                         sz=14, color=card_text, bold=True)

        # Content
        bullets = item.get("bullets", [])
        description = (item.get("description") or item.get("desc") or item.get("detail") or "")
        body_y = card_y + 0.80

        if bullets:
            deck.add_bullets(slide, bullets,
                             x + 0.15, body_y,
                             w - 0.30, card_h - 1.05,
                             sz=12, color=card_text)
        elif description:
            deck.add_textbox(slide, description,
                             x + 0.15, body_y,
                             w - 0.30, card_h - 1.05,
                             sz=12, color=card_text)

"""Two-by-three grid — 2 rows x 3 columns of equal cards with number badges.

Renders 6 cards in a 2x3 grid. Each card has a numbered circle badge,
bold header, and description text.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a 2x3 grid of cards.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {"header": str, "description": str},
                ...  # 6 items
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    items = data.get("items", [])
    if not items:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    n_cols = 3
    n_rows = 2
    row_gap = 0.25
    badge_size = 0.40

    cols = columns(n_cols, total_width=w, start_x=x0, gutter=0.25)
    row_h = (h - row_gap) / n_rows

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for idx, item in enumerate(items[:6]):
        col = idx % n_cols
        row = idx // n_cols
        cx, cw = cols[col]
        cy = y0 + row * (row_h + row_gap)

        # Card background
        deck.add_card(slide, cx, cy, cw, row_h, fill_color=card_fill)

        # Number badge
        deck.add_number_badge(slide, idx + 1,
                              cx + 0.12, cy + 0.12,
                              size=badge_size,
                              fill_color=COLORS["BCG_GREEN"])

        # Header text
        deck.add_textbox(slide, item.get("header", ""),
                         cx + badge_size + 0.22, cy + 0.12,
                         cw - badge_size - 0.34, 0.35,
                         sz=14, color=card_text, bold=True,
                         valign="middle")

        # Description text
        deck.add_textbox(slide, (item.get("description") or item.get("desc") or item.get("detail") or ""),
                         cx + 0.15, cy + 0.55,
                         cw - 0.30, row_h - 0.65,
                         sz=12, color=card_text)

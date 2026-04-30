"""Numbered steps process flow — numbered circles connected by horizontal lines.

Alternative process_flow variant. Each step is a numbered circle connected
by a horizontal line, with title and description text below. No chevron
shapes — uses circles and lines for a cleaner, more minimal look.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a numbered steps process flow.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [
                {
                    "label": str,
                    "details": [str, ...] or str,
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    stages = data.get("stages", [])
    n = len(stages)

    if n < 2:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Number badge sizing
    badge_size = 0.55 if n <= 5 else 0.45
    badge_y = y0 + 0.20

    cols = columns(n, total_width=w, start_x=x0, gutter=0.31)
    fills = dark_fills(n)

    # Connecting line between badges
    first_cx = cols[0][0] + cols[0][1] / 2
    last_cx = cols[-1][0] + cols[-1][1] / 2
    line_y = badge_y + badge_size / 2
    deck.add_line(slide,
                  first_cx + badge_size / 2 + 0.05, line_y,
                  last_cx - first_cx - badge_size - 0.10, 0,
                  color=COLORS["BCG_GREEN"], width=2.5)

    body_sz = 12 if n <= 4 else 11

    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    slide_text = text_on(slide_bg)
    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for i, (cx, cw) in enumerate(cols):
        stage = stages[i]
        fill = fills[i % len(fills)]
        center_x = cx + cw / 2

        # Numbered circle
        deck.add_number_badge(slide, str(i + 1),
                              center_x - badge_size / 2, badge_y,
                              size=badge_size, fill_color=fill)

        # Title below badge
        title_y = badge_y + badge_size + 0.25
        deck.add_textbox(slide, stage.get("label", ""),
                         cx, title_y, cw, 0.35,
                         sz=14, color=slide_text,
                         bold=True, align="center")

        # Description / detail card below title
        detail_y = title_y + 0.45
        detail_h = h - (detail_y - y0) - 0.10
        deck.add_card(slide, cx, detail_y, cw, detail_h,
                      fill_color=card_fill,
                      accent_color=COLORS["BCG_GREEN"],
                      accent_position="top")

        # Details as bullets or single text
        details = stage.get("details", [])
        if isinstance(details, str):
            deck.add_textbox(slide, details,
                             cx + 0.10, detail_y + 0.15,
                             cw - 0.20, detail_h - 0.25,
                             sz=body_sz, color=card_text)
        elif details:
            deck.add_bullets(slide, details,
                             cx + 0.10, detail_y + 0.15,
                             cw - 0.20, detail_h - 0.25,
                             sz=body_sz, color=card_text, spc_after=4)

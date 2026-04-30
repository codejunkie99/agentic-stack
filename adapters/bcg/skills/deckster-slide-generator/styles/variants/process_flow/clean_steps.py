"""Clean steps — minimal process flow with thin numbered circles and clean lines.

A lighter, more modern alternative to chevron arrows. Uses thin-bordered
circles instead of filled chevrons, with a subtle connecting line.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a clean steps process flow.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {"stages": [{"label": str, "details": [str]}]}
        bounds: {"x": float, "y": float, "w": float, "h": float}
    """
    from bcg_template import COLORS, text_on, card_fill_for_slide

    stages = data.get("stages", [])
    n = len(stages)
    if n < 2:
        return

    gap = 0.31
    total_w = bounds.get("w", 11.96)
    x0 = bounds.get("x", 0.69)
    col_w = (total_w - gap * (n - 1)) / n
    cols = [(x0 + i * (col_w + gap), col_w) for i in range(n)]

    circle_sz = 0.55
    line_y = bounds["y"] + 0.80
    card_y = bounds["y"] + 1.50
    card_h = bounds["h"] - 1.80

    # Connecting line
    first_cx = cols[0][0] + cols[0][1] / 2
    last_cx = cols[-1][0] + cols[-1][1] / 2
    deck.add_line(slide, first_cx, line_y + circle_sz / 2,
                  last_cx - first_cx, 0,
                  color=COLORS.get("OUTLINE", "E0E0E0"), width=1.5)

    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    slide_text = text_on(slide_bg)
    circle_fill = COLORS["WHITE"]
    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for i, (x, w) in enumerate(cols):
        stage = stages[i] if i < len(stages) else {"label": "", "details": []}
        cx = x + w / 2

        # Thin-bordered circle with number
        deck.add_oval(slide,
                      cx - circle_sz / 2, line_y,
                      circle_sz, circle_sz,
                      circle_fill,
                      line_color=COLORS["BCG_GREEN"],
                      line_width=2.0)
        deck.add_textbox(slide, str(i + 1),
                         cx - circle_sz / 2, line_y,
                         circle_sz, circle_sz,
                         sz=16, color=text_on(circle_fill),
                         bold=True, align="center", valign="middle")

        # Label
        deck.add_textbox(slide, stage.get("label", ""),
                         x, line_y + circle_sz + 0.15, w, 0.35,
                         sz=14, color=slide_text,
                         bold=True, align="center")

        # Detail card — clean white with subtle border
        details = stage.get("details", [])
        if details:
            deck.add_rounded_rectangle(slide, x + 0.05, card_y, w - 0.10, card_h,
                                       card_fill,
                                       radius=5000)
            deck.add_bullets(slide, details,
                             x + 0.20, card_y + 0.15,
                             w - 0.40, card_h - 0.30,
                             sz=12, color=card_text)

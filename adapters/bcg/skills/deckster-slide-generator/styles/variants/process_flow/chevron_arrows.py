"""Chevron arrows process flow — connected chevron shapes with detail cards below.

Default process_flow variant. Draws a row of chevron arrow shapes across the
top of the content zone, with rounded-rectangle detail cards below each chevron
containing the phase title and bullet details.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a chevron arrow process flow with detail cards.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [
                {
                    "label": str,
                    "details": [str, ...],   # bullet items
                    "timeline": str (optional)  # e.g. "Months 1-3"
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    stages = data.get("stages", [])
    n = len(stages)

    if n < 2:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Chevron row at top
    chevron_h = 0.60
    labels = [s.get("label", "") for s in stages]
    deck.add_chevron_flow(slide, labels, x0, y0, w, chevron_h)

    # Detail cards below chevrons
    card_top = y0 + chevron_h + 0.30
    card_h = h - chevron_h - 0.30
    # Reserve space for timeline labels at bottom
    has_timelines = any(s.get("timeline") for s in stages)
    if has_timelines:
        card_h -= 0.35

    cols = columns(n, total_width=w, start_x=x0, gutter=0.31)
    body_sz = 12 if n <= 4 else 11

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)
    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    slide_text = text_on(slide_bg)

    for i, (cx, cw) in enumerate(cols):
        stage = stages[i]

        # Card background — no accent bar since the chevron above
        # already provides the color-coded header for this stage.
        deck.add_card(slide, cx, card_top, cw, card_h,
                      fill_color=card_fill)

        # Bullet details directly — the chevron IS the header,
        # so don't repeat the stage label inside the card.
        details = stage.get("details", [])
        if details:
            deck.add_bullets(slide, details,
                             cx + 0.10, card_top + 0.15,
                             cw - 0.20, card_h - 0.30,
                             sz=body_sz, color=card_text, spc_after=4)

        # Timeline label below card
        timeline = stage.get("timeline")
        if timeline:
            deck.add_textbox(slide, timeline,
                             cx, card_top + card_h + 0.08,
                             cw, 0.20,
                             sz=12, color=slide_text,
                             align="center")

"""Workstream cards -- N columns with numbered oval, accent bar, and detail card.

Each column has a numbered oval badge at top, a colored accent bar with the
stage label, a white card with bullet details below, and a horizontal
connecting line running through the badges.
"""


def validate(deck, slide, data, bounds, **kwargs):
    stages = data.get("stages") or data.get("workstreams") or []
    if len(stages) < 2:
        return ["provide at least 2 workstreams/stages"]
    if len(stages) > 6:
        return ["limit workstreams/stages to 6 or fewer"]
    issues = []
    for idx, stage in enumerate(stages, start=1):
        label = stage.get("label") or stage.get("name") or ""
        details = stage.get("details") or stage.get("bullets") or []
        if not label:
            issues.append(f"stage {idx} is missing a label")
        if not details:
            issues.append(f"stage {idx} is missing details")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render a multi-column workstream card layout.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [
                {"label": str, "details": [str, ...]},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    stages = data.get("stages") or data.get("workstreams") or []
    stages = [
        {
            "label": stage.get("label") or stage.get("name") or "",
            "details": stage.get("details") or stage.get("bullets") or [],
        }
        for stage in stages
    ]
    n = len(stages)
    if n < 2:
        raise ValueError("workstream_cards requires at least 2 stages")

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    cols = columns(n, total_width=w, start_x=x0, gutter=0.31)

    accent = COLORS["DARK_GREEN"]
    hub = COLORS["DEEP_GREEN"]
    icon_size = 0.55

    body_sz = 12 if n <= 4 else 10
    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    # Connecting line through badges
    first_cx = cols[0][0] + cols[0][1] / 2
    last_cx = cols[-1][0] + cols[-1][1] / 2
    line_y = y0 + icon_size / 2
    deck.add_line(slide,
                  first_cx + icon_size / 2 + 0.05, line_y,
                  last_cx - first_cx - icon_size - 0.10, 0,
                  color=COLORS["BCG_GREEN"], width=2.5)

    for i, (cx, cw) in enumerate(cols):
        stage = stages[i]
        center_x = cx + cw / 2

        # Numbered oval badge
        deck.add_oval(slide,
                      center_x - icon_size / 2, y0,
                      icon_size, icon_size, hub)
        deck.add_textbox(slide, str(i + 1),
                         center_x - icon_size / 2, y0,
                         icon_size, icon_size,
                         sz=16, color=text_on(hub),
                         bold=True, align="center", valign="middle")

        # Accent bar with label
        bar_y = y0 + icon_size + 0.20
        bar_h = 0.35
        deck.add_rectangle(slide, cx, bar_y, cw, bar_h, accent)
        deck.add_textbox(slide, stage.get("label", ""),
                         cx + 0.10, bar_y, cw - 0.20, bar_h,
                         sz=12, color=text_on(accent),
                         bold=True, valign="middle")

        # Detail card
        card_y = bar_y + bar_h + 0.15
        card_h = h - (card_y - y0) - 0.10
        deck.add_card(slide, cx, card_y, cw, card_h,
                      fill_color=card_fill,
                      accent_color=COLORS["BCG_GREEN"],
                      accent_position="top")

        details = stage.get("details", [])
        if details:
            deck.add_bullets(slide, details,
                             cx + 0.10, card_y + 0.15,
                             cw - 0.20, card_h - 0.30,
                             sz=body_sz, color=card_text, spc_after=4)

    # Bottom connector dots
    dot_y = y0 + h - 0.08
    for cx, cw in cols:
        deck.add_oval(slide,
                      cx + cw / 2 - 0.08, dot_y,
                      0.16, 0.16, accent)

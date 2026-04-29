"""Gate flow -- horizontal phases with colored gates between them.

Each phase gets a gradient header block with gate arrow connectors between
phases, and a detail card below with bullet items.
"""


def validate(deck, slide, data, bounds, **kwargs):
    stages = data.get("stages", [])
    if len(stages) < 2:
        return ["provide at least 2 stages"]
    if len(stages) > 6:
        return ["limit stages to 6 or fewer"]
    issues = []
    for idx, stage in enumerate(stages, start=1):
        if not stage.get("name"):
            issues.append(f"stage {idx} is missing a name")
        if not (stage.get("details") or []):
            issues.append(f"stage {idx} is missing details")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render a stage-gate flow diagram.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [
                {"name": str, "details": [str, ...]},
                ...
            ],
            "gates": [
                {"label": str},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    stages = data.get("stages", [])
    gates = data.get("gates", [])
    n = len(stages)
    if n < 2:
        raise ValueError("gate_flow requires at least 2 stages")

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    cols = columns(n, total_width=w, start_x=x0, gutter=0.31)
    gate_colors = dark_fills(n)

    header_h = 1.05
    card_top = y0 + header_h + 0.24
    card_h = h - header_h - 0.24

    body_sz = 12 if n <= 4 else 11
    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)

    for i, (cx, cw) in enumerate(cols):
        stage = stages[i]
        fill = gate_colors[i % len(gate_colors)]

        # Phase header block
        deck.add_gradient_rectangle(slide, cx, y0, cw, header_h,
                                    fill,
                                    gate_colors[min(i + 1, n - 1)],
                                    angle=0)

        # Phase name in header
        deck.add_textbox(slide, stage.get("name", ""),
                         cx + 0.10, y0 + 0.10, cw - 0.20, 0.32,
                         sz=14, color=text_on(fill),
                         bold=True, align="center", valign="middle")

        # Gate label below phase name (if gate exists for this index)
        if i < len(gates):
            gate_label = gates[i].get("label", "")
            deck.add_textbox(slide, gate_label,
                             cx + 0.10, y0 + 0.58,
                             cw - 0.20, 0.20,
                             sz=12, color=text_on(fill),
                             align="center", valign="middle")

        # Arrow connector between phases
        if i < n - 1:
            next_x = cols[i + 1][0]
            gap_mid = cx + cw + (next_x - cx - cw) / 2
            deck.add_shape(slide, "rightArrow",
                           gap_mid - 0.15, y0 + header_h * 0.30,
                           0.30, 0.40,
                           COLORS["BCG_GREEN"])

        # Detail card below header
        deck.add_card(slide, cx, card_top, cw, card_h,
                      fill_color=card_fill,
                      accent_color=COLORS["BCG_GREEN"],
                      accent_position="top")

        # Bullet details in card
        details = stage.get("details", [])
        if details:
            deck.add_bullets(slide, details,
                             cx + 0.10, card_top + 0.15,
                             cw - 0.20, card_h - 0.30,
                             sz=body_sz, color=card_text, spc_after=4)

"""Quadrant grid -- 2x2 matrix with colored borders and axis labels.

Four rounded-rectangle quadrants arranged in a 2x2 grid, each with a
colored border, header label, and bullet content. Axis labels sit on the
left and bottom edges.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a 2x2 quadrant grid (SWOT or similar).

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "quadrants": [
                {"label": str, "items": [str, ...]},
                ... (exactly 4, in order: TL, TR, BL, BR)
            ],
            "x_axis": str,
            "y_axis": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, card_fill_for_slide

    quadrants = data.get("quadrants", [])
    x_axis = data.get("x_axis", "")
    y_axis = data.get("y_axis", "")
    if len(quadrants) < 4:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Reserve space for axis labels
    y_label_w = 0.40 if y_axis else 0
    x_label_h = 0.30 if x_axis else 0
    grid_x = x0 + y_label_w
    grid_y = y0
    grid_w = w - y_label_w
    grid_h = h - x_label_h

    gap = 0.20
    quad_w = (grid_w - gap) / 2
    quad_h = (grid_h - gap) / 2

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)
    # Use only darker brand colors so quadrant headers stay legible and
    # within the validated BCG palette on light card backgrounds.
    border_colors = [
        COLORS["BCG_GREEN"],
        COLORS["DARK_GREEN"],
        COLORS["DEEP_GREEN"],
        COLORS["MED_GRAY"],
    ]

    # TL=0, TR=1, BL=2, BR=3
    positions = [
        (grid_x, grid_y),
        (grid_x + quad_w + gap, grid_y),
        (grid_x, grid_y + quad_h + gap),
        (grid_x + quad_w + gap, grid_y + quad_h + gap),
    ]

    for i, q in enumerate(quadrants[:4]):
        qx, qy = positions[i]
        deck.add_rounded_rectangle(slide, qx, qy, quad_w, quad_h,
                                   card_fill_for_slide(), radius=5000,
                                   line_color=border_colors[i],
                                   line_width=1.5)
        deck.add_textbox(slide, q.get("label") or q.get("title", ""),
                         qx + 0.15, qy + 0.12, quad_w - 0.30, 0.30,
                         sz=14, color=border_colors[i], bold=True)

        items = q.get("items", [])
        if items:
            deck.add_bullets(slide, items,
                             qx + 0.15, qy + 0.50,
                             quad_w - 0.30, quad_h - 0.65,
                             sz=12, color=card_text, spc_after=4)

    # Axis labels
    if y_axis:
        deck.add_textbox(slide, y_axis,
                         x0, y0, y_label_w, grid_h,
                         sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")),
                         bold=True, align="center", valign="middle",
                         vertical=True)

    if x_axis:
        deck.add_textbox(slide, x_axis,
                         grid_x, grid_y + grid_h,
                         grid_w, x_label_h,
                         sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")),
                         bold=True, align="center")

"""Portfolio matrix -- scatter bubble on a 2x2 background.

Draws a 2x2 tinted background grid with sized circles positioned by
normalized x/y values (0-1). External labels connect via leader lines.
"""

import math


def render(deck, slide, data, bounds, **kwargs):
    """Render a scatter-bubble portfolio matrix.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "items": [
                {"label": str, "x": float, "y": float, "size": float},
                ...
            ],
            "x_label": str,
            "y_label": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    items = data.get("items", [])
    x_label = data.get("x_label", "")
    y_label = data.get("y_label", "")

    if not items:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Reserve margins for axis labels
    label_margin = 0.50
    grid_x = x0 + label_margin
    grid_y = y0
    grid_w = w - label_margin
    grid_h = h - 0.35  # bottom axis label space
    half_w = grid_w / 2
    half_h = grid_h / 2

    # 2x2 tinted background
    quad_bg = [card_fill_for_slide(), card_fill_for_slide(),
               card_fill_for_slide(), card_fill_for_slide()]
    for qi in range(4):
        qx = grid_x + (qi % 2) * half_w
        qy = grid_y + (qi // 2) * half_h
        deck.add_rectangle(slide, qx, qy, half_w, half_h, quad_bg[qi])

    # Grid lines
    deck.add_line(slide, grid_x, grid_y + half_h, grid_w, 0,
                  color=COLORS["MED_GRAY"], width=1.0)
    deck.add_line(slide, grid_x + half_w, grid_y, 0, grid_h,
                  color=COLORS["MED_GRAY"], width=1.0)

    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    slide_text = text_on(slide_bg)

    # Axis labels
    if y_label:
        deck.add_textbox(slide, y_label,
                         x0, grid_y, label_margin - 0.05, grid_h,
                         sz=12, color=slide_text,
                         bold=True, align="center", valign="middle",
                         vertical=True)
    if x_label:
        deck.add_textbox(slide, x_label,
                         grid_x, grid_y + grid_h + 0.08,
                         grid_w, 0.25,
                         sz=12, color=slide_text,
                         bold=True, align="center")

    # Normalize size for radius
    sizes = [it.get("size", 1.0) for it in items]
    min_s = min(sizes) if sizes else 1
    max_s = max(sizes) if sizes else 1
    range_s = max(max_s - min_s, 0.01)

    fills = dark_fills(min(len(items), 6))

    for idx, item in enumerate(items):
        # Position: x=0 is left, x=1 is right; y=0 is top, y=1 is bottom
        ix = item.get("x", 0.5)
        iy = item.get("y", 0.5)
        bx = grid_x + ix * grid_w
        by = grid_y + iy * grid_h

        # Radius from size
        norm_s = (item.get("size", 1.0) - min_s) / range_s
        r = 0.18 + 0.30 * math.sqrt(norm_s)

        fill = fills[idx % len(fills)]
        deck.add_oval(slide, bx - r, by - r, r * 2, r * 2, fill,
                      line_color=COLORS["WHITE"], line_width=1.5)

        # Value label inside bubble
        deck.add_textbox(slide, f"{item.get('size', ''):.0f}",
                         bx - r, by - 0.09, r * 2, 0.18,
                         sz=8, color=text_on(fill),
                         bold=True, align="center", valign="middle")

        # External label with leader line
        center_x = grid_x + grid_w / 2
        center_y = grid_y + grid_h / 2
        dx = bx - center_x
        dy = by - center_y
        ang = math.atan2(dy, dx) if (abs(dx) + abs(dy)) > 0.01 else 0
        cos_a = math.cos(ang)
        sin_a = math.sin(ang)

        lsx = bx + r * cos_a
        lsy = by + r * sin_a
        lex = bx + (r + 0.20) * cos_a
        ley = by + (r + 0.20) * sin_a

        deck.add_line(slide,
                      min(lsx, lex), min(lsy, ley),
                      abs(lex - lsx), abs(ley - lsy),
                      color=COLORS.get("PAGE_NUM", "B0B0B0"), width=0.75)

        lbl_w = 1.20
        lbl_h = 0.20
        lbl_x = lex if cos_a >= 0 else lex - lbl_w
        lbl_align = "left" if cos_a >= 0 else "right"
        deck.add_textbox(slide, item.get("label", ""),
                         lbl_x, ley - lbl_h / 2,
                         lbl_w, lbl_h,
                         sz=8, color=slide_text,
                         bold=True, align=lbl_align)

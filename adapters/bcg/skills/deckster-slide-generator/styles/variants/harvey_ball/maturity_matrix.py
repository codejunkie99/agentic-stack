"""Maturity matrix -- grid of colored ovals with row/column headers and legend.

Uses a 5-level color scale (gray -> LIME -> TEAL -> BCG_GREEN -> DARK_GREEN)
to indicate maturity. Row and column headers label the axes, and a bottom
legend shows the scale.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a Harvey ball maturity matrix.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "rows": [str, ...],          # row labels
            "columns": [str, ...],       # column labels
            "values": [[int, ...], ...]  # 2D grid, 0-4 per cell
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    rows = data.get("rows", [])
    cols = data.get("columns", [])
    values = data.get("values", [])
    n_rows = len(rows)
    n_cols = len(cols)
    if n_rows == 0 or n_cols == 0:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    HARVEY_FILLS = {
        0: COLORS.get("LIGHT_BG", "F2F2F2"),
        1: COLORS.get("LIME", "D4DF33"),
        2: COLORS.get("TEAL", "3EAD92"),
        3: COLORS["BCG_GREEN"],
        4: COLORS["DARK_GREEN"],
    }

    # Layout
    label_w = 3.00
    header_h = 0.45
    legend_h = 0.40

    grid_x = x0 + label_w + 0.15
    grid_y = y0 + header_h + 0.10
    grid_w = w - label_w - 0.15
    grid_h = h - header_h - 0.10 - legend_h - 0.20

    col_w = grid_w / max(n_cols, 1)
    row_h = min(0.55, grid_h / max(n_rows, 1))
    ball_size = 0.28

    # Column headers
    accent = dark_fills(1)[0]
    for ci, col_label in enumerate(cols):
        deck.add_textbox(slide, col_label,
                         grid_x + ci * col_w, y0,
                         col_w, header_h,
                         sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")),
                         bold=True, align="center")

    # Header separator line
    deck.add_line(slide, x0, grid_y - 0.05, w, 0,
                  color=accent, width=1.5)

    # Grid rows
    for ri, row_label in enumerate(rows):
        ry = grid_y + ri * row_h

        # Row label
        deck.add_textbox(slide, row_label,
                         x0, ry, label_w, row_h,
                         sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")), valign="middle")

        # Balls
        row_values = values[ri] if ri < len(values) else []
        for ci in range(n_cols):
            score = row_values[ci] if ci < len(row_values) else 0
            score = max(0, min(4, score))
            bx = grid_x + ci * col_w + col_w / 2 - ball_size / 2
            by = ry + row_h / 2 - ball_size / 2
            fill = HARVEY_FILLS.get(score, COLORS.get("LIGHT_BG", "F2F2F2"))
            deck.add_oval(slide, bx, by, ball_size, ball_size, fill,
                          line_color=COLORS.get("MED_GRAY", "6E6F73"),
                          line_width=0.5)

        # Row separator
        if ri < n_rows - 1:
            deck.add_line(slide, x0, ry + row_h, w, 0,
                          color=card_fill_for_slide(), width=0.5)

    # Legend at bottom
    legend_y = y0 + h - legend_h
    legend_labels = ["Not started", "Early", "In progress", "Advanced", "Complete"]
    legend_spacing = min(2.4, w / 5)

    for li in range(5):
        lx = x0 + li * legend_spacing
        deck.add_oval(slide, lx, legend_y, 0.22, 0.22,
                      HARVEY_FILLS[li],
                      line_color=COLORS.get("MED_GRAY", "6E6F73"),
                      line_width=0.5)
        deck.add_textbox(slide, legend_labels[li],
                         lx + 0.28, legend_y - 0.02,
                         1.80, 0.25,
                         sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

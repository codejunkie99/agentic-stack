"""Green highlight insights — left analysis zone + right panel with structured insights.

Left side is open for agent analysis content. Right side has a green
panel with Format B structured insight rows (header + detail pairs).
"""


def _resolve_panel(bounds):
    """Resolve the right-panel geometry across both full-width and split-zone calls."""
    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    if "right_x" in bounds and "right_w" in bounds:
        return bounds["right_x"], y0, bounds["right_w"], h

    # If the caller already passed the right-panel zone only, trust it.
    if w <= 5.25:
        return x0, y0, w, h

    panel_w = round(w * 0.35, 2)
    panel_x = round(x0 + w - panel_w, 2)
    return panel_x, y0, panel_w, h


def render(deck, slide, data, bounds, **kwargs):
    """Render green highlight with structured insights.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "insights": [
                {"header": str, "detail": str},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on

    insights = data.get("insights", [])
    if not insights:
        return

    panel_color = COLORS["BCG_GREEN"]
    panel_x, panel_y, panel_w, panel_h = _resolve_panel(bounds)

    # Only paint the accent panel when the layout does not already provide one.
    # Split layouts (green_highlight, etc.) have the accent in the slide master;
    # drawing over it causes color mismatches.
    _layout_provides_accent = "right_x" in bounds or "left_x" in bounds
    if not _layout_provides_accent:
        deck.add_rectangle(slide, panel_x, panel_y, panel_w, panel_h, panel_color)

    # Insight rows — vertically centered in the panel
    n = len(insights)
    available_h = max(panel_h - 0.50, 0.80)
    row_h = min(0.98 if n >= 3 else 1.15, available_h / n)
    total_h = row_h * n
    content_y = panel_y + max(0.25, (panel_h - total_h) / 2)
    header_sz = 14
    detail_sz = 12

    for i, insight in enumerate(insights):
        ry = content_y + i * row_h

        # Header
        deck.add_textbox(slide, insight.get("header", ""),
                         panel_x + 0.20, ry,
                         panel_w - 0.40, 0.32,
                         sz=header_sz, color=text_on(panel_color),
                         bold=True)

        # Detail
        deck.add_textbox(slide, insight.get("detail", ""),
                         panel_x + 0.20, ry + 0.34,
                         panel_w - 0.40, row_h - 0.42,
                         sz=detail_sz, color=text_on(panel_color))

        # Separator (not after last)
        if i < n - 1:
            sep_y = ry + row_h - 0.04
            deck.add_line(slide, panel_x + 0.20, sep_y,
                          panel_w - 0.40, 0,
                          color=text_on(panel_color), width=1)

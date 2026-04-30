"""Green highlight quote — left analysis zone + right panel with quote.

Left side is open for the agent to fill with analysis content.
Right side has a green panel with a Format A quote and attribution.
"""


def _resolve_panel(bounds):
    """Resolve the right-panel geometry across both full-width and split-zone calls."""
    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    if "right_x" in bounds and "right_w" in bounds:
        return bounds["right_x"], y0, bounds["right_w"], h

    if w <= 5.25:
        return x0, y0, w, h

    panel_w = round(w * 0.35, 2)
    panel_x = round(x0 + w - panel_w, 2)
    return panel_x, y0, panel_w, h


def render(deck, slide, data, bounds, **kwargs):
    """Render green highlight with quote.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "quote": str,
            "attribution": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on

    quote = data.get("quote", "")
    attribution = data.get("attribution", "")
    if not quote:
        return

    panel_color = COLORS["BCG_GREEN"]
    panel_x, panel_y, panel_w, panel_h = _resolve_panel(bounds)
    # Only paint the accent panel when the layout does not already provide one.
    _layout_provides_accent = "right_x" in bounds or "left_x" in bounds
    if not _layout_provides_accent:
        deck.add_rectangle(slide, panel_x, panel_y, panel_w, panel_h, panel_color)

    quote_len = len(quote.strip())
    if quote_len <= 70 and panel_w >= 4.10:
        quote_sz = 16
    elif quote_len <= 120:
        quote_sz = 15
    else:
        quote_sz = 14
    quote_mark_sz = 44 if quote_sz >= 15 else 40

    # Quote mark / decorative element
    deck.add_textbox(slide, "\u201C",
                     panel_x + 0.15, panel_y + 0.20,
                     0.50, 0.60,
                     sz=quote_mark_sz, color=text_on(panel_color),
                     bold=True)

    # Quote text
    quote_y = panel_y + 0.70
    quote_h = panel_h - 1.45
    deck.add_textbox(slide, quote,
                     panel_x + 0.25, quote_y,
                     panel_w - 0.50, quote_h,
                     sz=quote_sz, color=text_on(panel_color))

    # Attribution
    if attribution:
        attr_y = panel_y + panel_h - 0.60
        deck.add_textbox(slide, "\u2014 " + attribution,
                         panel_x + 0.25, attr_y,
                         panel_w - 0.50, 0.35,
                         sz=12, color=text_on(panel_color),
                         bold=True)

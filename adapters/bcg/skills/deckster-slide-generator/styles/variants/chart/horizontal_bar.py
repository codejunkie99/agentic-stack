"""Horizontal bar chart — horizontal bars with optional highlight color.

Thin wrapper around deck.add_chart() with bar_horizontal type. Supports
a highlight_index to emphasize one bar with a distinct color.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a horizontal bar chart.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "categories": [...],
            "series": [{"name": str, "values": [...]}, ...],
            "colors": [...],
            "number_format": str,
            "highlight_index": int,   # optional: bar index to highlight
            "source": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on

    categories = data.get("categories", [])
    series = data.get("series", [])
    if not categories or not series:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    source = data.get("source", "")
    chart_h = h - 0.30 if source else h

    chart_opts = {}
    if data.get("colors"):
        chart_opts["colors"] = data["colors"]
    if data.get("number_format"):
        chart_opts["number_format"] = data["number_format"]

    # Apply highlight via point_colors on first series
    highlight_idx = data.get("highlight_index")
    if highlight_idx is not None and len(series) == 1:
        n_pts = len(categories)
        base_color = COLORS.get("MED_GRAY", "6E6F73")
        highlight_color = COLORS["BCG_GREEN"]
        point_colors = [
            highlight_color if j == highlight_idx else base_color
            for j in range(n_pts)
        ]
        series[0]["point_colors"] = point_colors

    deck.add_chart(slide, "bar_horizontal", categories, series,
                   x=x0, y=y0, w=w, h=chart_h, **chart_opts)

    if source:
        deck.add_textbox(slide, "Source: " + source,
                         x0, y0 + chart_h + 0.05,
                         w, 0.22,
                         sz=8, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

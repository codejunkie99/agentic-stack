"""Donut chart — doughnut chart with hole_size and data labels.

Thin wrapper around deck.add_chart() with doughnut type. Configures
hole_size and enables data labels by default.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a donut chart.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "categories": [...],
            "series": [{"name": str, "values": [...]}, ...],
            "colors": [...],
            "hole_size": int,         # optional (default 50)
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

    # Center the donut (use smaller of w/h for square aspect)
    side = min(w, chart_h)
    cx = x0 + (w - side) / 2
    cy = y0 + (chart_h - side) / 2

    chart_opts = {
        "data_labels": True,
        "hole_size": data.get("hole_size", 50),
    }
    if data.get("colors"):
        chart_opts["colors"] = data["colors"]

    deck.add_chart(slide, "doughnut", categories, series,
                   x=cx, y=cy, w=side, h=side, **chart_opts)

    if source:
        deck.add_textbox(slide, "Source: " + source,
                         x0, y0 + chart_h + 0.05,
                         w, 0.22,
                         sz=8, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

"""Bar chart — clustered column chart positioned within bounds with source line.

Thin wrapper around deck.add_chart() that places a bar chart within the
given bounds and adds an optional source annotation line below.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a bar chart.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "categories": [...],
            "series": [{"name": str, "values": [...]}, ...],
            "colors": [...],          # optional
            "number_format": str,     # optional
            "source": str             # optional source annotation
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

    deck.add_chart(slide, "bar", categories, series,
                   x=x0, y=y0, w=w, h=chart_h, **chart_opts)

    if source:
        deck.add_textbox(slide, "Source: " + source,
                         x0, y0 + chart_h + 0.05,
                         w, 0.22,
                         sz=8, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

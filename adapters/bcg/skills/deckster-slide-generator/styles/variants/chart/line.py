"""Line chart — line chart with optional dashed reference series.

Thin wrapper around deck.add_chart() with line type. Supports marking
a reference series (e.g., target/benchmark) with a dashed line style.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a line chart.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "categories": [...],
            "series": [{"name": str, "values": [...]}, ...],
            "colors": [...],
            "number_format": str,
            "reference_series": int,  # optional: index of dashed reference line
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

    # Mark reference series as dashed
    ref_idx = data.get("reference_series")
    if ref_idx is not None and 0 <= ref_idx < len(series):
        series[ref_idx]["line_dash"] = "dash"

    chart_opts = {}
    if data.get("colors"):
        chart_opts["colors"] = data["colors"]
    if data.get("number_format"):
        chart_opts["number_format"] = data["number_format"]

    deck.add_chart(slide, "line", categories, series,
                   x=x0, y=y0, w=w, h=chart_h, **chart_opts)

    if source:
        deck.add_textbox(slide, "Source: " + source,
                         x0, y0 + chart_h + 0.05,
                         w, 0.22,
                         sz=8, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

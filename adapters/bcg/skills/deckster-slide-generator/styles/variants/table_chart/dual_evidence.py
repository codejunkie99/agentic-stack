"""Dual evidence -- left-half table plus right-half chart.

Splits the content zone into a left table providing precision and a right
chart providing visual pattern recognition.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a table + chart dual evidence slide.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "table_data": [[str, ...], ...],  # first row = headers
            "chart_type": str,                 # "bar", "line", etc.
            "chart_categories": [str, ...],
            "chart_series": [
                {"name": str, "values": [float, ...]},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS

    table_data = data.get("table_data", [])
    chart_type = data.get("chart_type", "bar")
    chart_categories = data.get("chart_categories", [])
    chart_series = data.get("chart_series", [])

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    gap = 0.31
    left_w = (w - gap) * 0.48
    right_w = w - gap - left_w
    right_x = x0 + left_w + gap

    # Left: table
    if table_data:
        deck.add_table(slide, table_data,
                       x=x0, y=y0, w=left_w, h=h,
                       header=True, sz=12)

    # Right: chart
    if chart_categories and chart_series:
        chart_colors = [COLORS["BCG_GREEN"],
                        COLORS.get("PAGE_NUM", "B0B0B0"),
                        COLORS["TEAL"],
                        COLORS["DARK_GREEN"]]
        deck.add_chart(slide, chart_type,
                       categories=chart_categories,
                       series=chart_series,
                       x=right_x, y=y0, w=right_w, h=h,
                       colors=chart_colors[:len(chart_series)])

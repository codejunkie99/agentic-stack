"""Chart + KPI + callout — chart at top, KPI tile row, callout box at bottom.

Composite pattern that renders a chart in the upper zone, a row of KPI
tiles in the middle, and a callout text box at the bottom.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render chart + KPI tiles + callout.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "chart_type": str,         # e.g. "bar", "line"
            "chart_data": {
                "categories": [...],
                "series": [...],
                "colors": [...],
                "number_format": str
            },
            "kpis": [
                {"title": str, "value": str, "change": str, "positive": bool},
                ...
            ],
            "callout": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    kpis = data.get("kpis", [])
    callout = data.get("callout", "")
    chart_data = data.get("chart_data", {})
    chart_type = data.get("chart_type", "bar")

    # Allocate vertical space
    callout_h = 0.50 if callout else 0
    kpi_h = 1.40 if kpis else 0
    chart_h = h - kpi_h - callout_h - 0.30  # gaps

    # --- Chart zone ---
    if chart_data.get("categories") and chart_data.get("series"):
        chart_options = {}
        if chart_data.get("colors"):
            chart_options["colors"] = chart_data["colors"]
        if chart_data.get("number_format"):
            chart_options["number_format"] = chart_data["number_format"]
        deck.add_chart(slide, chart_type,
                       chart_data["categories"],
                       chart_data["series"],
                       x=x0, y=y0, w=w, h=max(chart_h, 1.50),
                       **chart_options)

    # --- KPI tile row ---
    if kpis:
        kpi_y = y0 + chart_h + 0.15
        n = len(kpis)
        cols = columns(n, total_width=w, start_x=x0, gutter=0.20)
        tile_h = min(kpi_h, 1.30)

        card_fill = card_fill_for_slide()
        card_text = text_on(card_fill)
        accent = COLORS["BCG_GREEN"]

        for i, (cx, cw) in enumerate(cols):
            kpi = kpis[i]
            deck.add_card(slide, cx, kpi_y, cw, tile_h,
                          fill_color=card_fill,
                          accent_color=accent,
                          accent_position="top")

            deck.add_textbox(slide, kpi.get("value", ""),
                             cx + 0.10, kpi_y + 0.12,
                             cw - 0.20, 0.45,
                             sz=22, color=accent, bold=True,
                             align="center", valign="middle")

            deck.add_textbox(slide, kpi.get("title", ""),
                             cx + 0.10, kpi_y + 0.60,
                             cw - 0.20, 0.25,
                             sz=12, color=card_text,
                             align="center")

            change = kpi.get("change", "")
            if change:
                positive = kpi.get("positive", True)
                change_color = COLORS["BCG_GREEN"] if positive else COLORS["NEGATIVE"]
                deck.add_textbox(slide, change,
                                 cx + 0.10, kpi_y + 0.88,
                                 cw - 0.20, 0.22,
                                 sz=12, color=change_color,
                                 bold=True, align="center")

    # --- Callout box ---
    if callout:
        callout_y = y0 + h - callout_h
        deck.add_rounded_rectangle(slide, x0, callout_y, w, callout_h,
                                   card_fill_for_slide(),
                                   radius=5000,
                                   line_color=COLORS["BCG_GREEN"],
                                   line_width=1)
        callout_fill = card_fill_for_slide()
        deck.add_textbox(slide, callout,
                         x0 + 0.15, callout_y,
                         w - 0.30, callout_h,
                         sz=12, color=text_on(callout_fill),
                         valign="middle")

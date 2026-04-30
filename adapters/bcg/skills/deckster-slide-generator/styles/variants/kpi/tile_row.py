"""KPI tile row — 3-4 KPI cards with green accent bar, big value, label, change indicator.

Renders a horizontal row of KPI tiles. Each tile has a green top accent,
a large value, a label below, and a positive/negative change indicator.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render KPI tile row.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "kpis": [
                {
                    "title": str,
                    "value": str,
                    "change": str,
                    "positive": bool
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    kpis = data.get("kpis", [])
    if not kpis:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    n = len(kpis)
    cols = columns(n, total_width=w, start_x=x0, gutter=0.20)
    tile_h = min(h, 1.60)
    compact = tile_h < 1.20

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)
    accent = COLORS["BCG_GREEN"]

    value_y = 0.12 if compact else 0.18
    value_h = 0.36 if compact else 0.55
    value_sz = 22 if compact else 28
    title_y = 0.50 if compact else 0.75
    title_h = 0.22 if compact else 0.30
    title_sz = 12 if compact else 12
    change_y = 0.68 if compact else 1.10
    change_h = 0.18 if compact else 0.25
    change_sz = 10 if compact else 11

    for i, (cx, cw) in enumerate(cols):
        kpi = kpis[i]

        # Card with green accent bar at top
        deck.add_card(slide, cx, y0, cw, tile_h,
                      fill_color=card_fill,
                      accent_color=accent,
                      accent_position="top")

        # Big value
        deck.add_textbox(slide, kpi.get("value", ""),
                         cx + 0.12, y0 + value_y,
                         cw - 0.24, value_h,
                         sz=value_sz, color=accent, bold=True,
                         align="center", valign="middle")

        # Label
        deck.add_textbox(slide, kpi.get("title", ""),
                         cx + 0.12, y0 + title_y,
                         cw - 0.24, title_h,
                         sz=title_sz, color=card_text,
                         align="center", valign="middle")

        # Change indicator
        change = kpi.get("change", "")
        if change:
            positive = kpi.get("positive", True)
            change_color = COLORS["BCG_GREEN"] if positive else COLORS["NEGATIVE"]
            prefix = "+" if positive and not change.startswith("+") else ""
            deck.add_textbox(slide, prefix + change,
                             cx + 0.12, y0 + change_y,
                             cw - 0.24, change_h,
                             sz=change_sz, color=change_color,
                             bold=True, align="center", valign="middle")

"""Narrowing stages funnel -- progressive narrowing bars centered horizontally.

Each bar is narrower than the one above it, encoding quantity reduction.
Label and metric sit on the bar; optional drop_rate shown at right.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a narrowing-stages funnel.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [
                {"label": str, "metric": str, "drop_rate": str (optional)},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns

    stages = data.get("stages", [])
    n = len(stages)
    if n < 2:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Reserve a right-side annotation lane when drop-rate text is present so
    # labels never spill past the authored content zone.
    annotation_w = 1.05 if any(stage.get("drop_rate") for stage in stages[1:]) else 0.0
    annotation_gap = 0.15 if annotation_w else 0.0
    bar_area_w = max(w - annotation_w - annotation_gap, 1.0)

    # Bar sizing
    gap = 0.12 if n <= 4 else 0.08
    bar_h = min(0.70, (h - gap * (n - 1)) / n)

    max_w = bar_area_w * 0.96
    min_w = max_w * 0.35
    width_step = (max_w - min_w) / max(n - 1, 1)

    fills = dark_fills(n)
    slide_mid = x0 + bar_area_w / 2

    for i, stage in enumerate(stages):
        bar_w = max_w - i * width_step
        bx = slide_mid - bar_w / 2
        by = y0 + i * (bar_h + gap)

        deck.add_rounded_rectangle(slide, bx, by, bar_w, bar_h,
                                   fills[i], radius=8000)

        # Label at left portion
        deck.add_textbox(slide, stage.get("label", ""),
                         bx + 0.25, by, bar_w * 0.50, bar_h,
                         sz=14, color=text_on(fills[i]),
                         bold=True, valign="middle")

        # Metric at right portion
        metric = stage.get("metric", "")
        if metric:
            deck.add_textbox(slide, metric,
                             bx + bar_w * 0.55, by, bar_w * 0.40, bar_h,
                             sz=12, color=text_on(fills[i]),
                             align="right", valign="middle")

        # Drop rate annotation outside bar
        drop_rate = stage.get("drop_rate", "")
        if drop_rate and i > 0:
            ann_x = x0 + bar_area_w + annotation_gap
            deck.add_textbox(slide, drop_rate,
                             ann_x, by, annotation_w, bar_h,
                             sz=12, color=COLORS["NEGATIVE"],
                             bold=True, align="left", valign="middle")

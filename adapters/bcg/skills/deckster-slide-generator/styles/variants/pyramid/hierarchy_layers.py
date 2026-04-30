"""Hierarchy layers pyramid -- stacked bars narrowing from bottom to top.

Draws horizontal rounded bars stacked vertically. The bottom layer is widest,
the top narrowest. Right-side annotations explain each layer.
Data layers are provided in bottom-up order.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a pyramid hierarchy diagram.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "layers": [
                {"label": str, "annotation": str},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
        Note: layers are in bottom-up order (index 0 = bottom/widest layer).
    """
    from bcg_template import COLORS, text_on, dark_fills, columns

    layers = data.get("layers", [])
    n = len(layers)
    if n < 2:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Reserve right side for annotations
    bar_zone_w = w * 0.65
    ann_x = x0 + bar_zone_w + 0.25
    ann_w = w - bar_zone_w - 0.25

    gap = 0.10
    level_h = min(1.0, (h - gap * (n - 1)) / n)

    max_w = bar_zone_w
    min_w = max_w * 0.35
    width_step = (max_w - min_w) / max(n - 1, 1)

    fills = dark_fills(n)
    bar_center_x = x0 + bar_zone_w / 2

    # Render top-to-bottom (reverse the bottom-up data for visual stacking)
    for vi in range(n):
        # vi=0 is the top (narrowest), data index is n-1-vi
        data_idx = n - 1 - vi
        layer = layers[data_idx]
        bar_w = min_w + vi * width_step
        bx = bar_center_x - bar_w / 2
        by = y0 + vi * (level_h + gap)

        fill = fills[data_idx % len(fills)]
        deck.add_rounded_rectangle(slide, bx, by, bar_w, level_h,
                                   fill, radius=5000)
        deck.add_textbox(slide, layer.get("label", ""),
                         bx, by, bar_w, level_h,
                         sz=14, color=text_on(fill),
                         bold=True, align="center", valign="middle")

        # Annotation at right
        annotation = layer.get("annotation", "")
        if annotation:
            deck.add_textbox(slide, annotation,
                             ann_x, by, ann_w, level_h,
                             sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")),
                             valign="middle")

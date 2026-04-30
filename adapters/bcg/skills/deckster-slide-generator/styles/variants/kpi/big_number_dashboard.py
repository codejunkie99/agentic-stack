"""Big number dashboard — 2-4 large numbers with labels and sublabels.

Renders large metric values (52pt) side by side with vertical separator
lines between them. Each metric has a main value, label, and sublabel.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render big number dashboard.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "metrics": [
                {
                    "value": str,
                    "label": str,
                    "sublabel": str
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    metrics = data.get("metrics", [])
    if not metrics:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    n = len(metrics)
    cols = columns(n, total_width=w, start_x=x0, gutter=0.40)

    # Vertical center the content block
    block_h = 2.20
    block_y = y0 + (h - block_h) / 2

    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    slide_text = text_on(slide_bg)

    for i, (cx, cw) in enumerate(cols):
        metric = metrics[i]

        # Large value
        deck.add_textbox(slide, metric.get("value", ""),
                         cx, block_y,
                         cw, 1.00,
                         sz=52, color=COLORS["BCG_GREEN"], bold=True,
                         align="center", valign="middle")

        # Label
        deck.add_textbox(slide, metric.get("label", ""),
                         cx, block_y + 1.10,
                         cw, 0.40,
                         sz=14, color=slide_text, bold=True,
                         align="center", valign="top")

        # Sublabel
        sublabel = metric.get("sublabel", "")
        if sublabel:
            deck.add_textbox(slide, sublabel,
                             cx, block_y + 1.55,
                             cw, 0.35,
                             sz=12, color=slide_text,
                             align="center", valign="top")

        # Vertical separator line (not after last)
        if i < n - 1:
            sep_x = cx + cw + 0.18
            deck.add_line(slide, sep_x, block_y + 0.10, 0, block_h - 0.20,
                          color=card_fill_for_slide(), width=1)

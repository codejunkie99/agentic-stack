"""Cascade boxes org chart -- hierarchical parent-child box diagram.

Draws a top root box with vertical/horizontal connector lines to child boxes,
supporting 2-3 levels of hierarchy. Uses dark_fills for level-based coloring.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a cascade box org chart.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "root": {"label": str},
            "children": [
                {
                    "label": str,
                    "children": [{"label": str}, ...] (optional)
                },
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns

    root = data.get("root", {})
    children = data.get("children", [])
    if not root:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    level_fills = dark_fills(3)

    def _add_box(text, bx, by, bw, bh, level):
        fill = level_fills[min(level, 2)]
        sz = 16 if level == 0 else 13 if level == 1 else 11
        deck.add_rounded_rectangle(slide, bx, by, bw, bh, fill,
                                   radius=5000,
                                   line_color=COLORS["WHITE"],
                                   line_width=1.5)
        deck.add_textbox(slide, text, bx, by, bw, bh,
                         sz=sz, color=text_on(fill),
                         bold=(level <= 1),
                         align="center", valign="middle")

    def _connector(px, py, pw, ph, cx, cy, cw):
        """Draw an L-shaped connector from parent bottom to child top."""
        mid_y = py + ph + (cy - py - ph) / 2
        # Vertical from parent center bottom
        deck.add_line(slide, px + pw / 2, py + ph,
                      0, mid_y - py - ph,
                      color=COLORS["MED_GRAY"], width=1)
        # Horizontal to child center
        x1 = min(px + pw / 2, cx + cw / 2)
        x2 = max(px + pw / 2, cx + cw / 2)
        if x2 - x1 > 0.01:
            deck.add_line(slide, x1, mid_y,
                          x2 - x1, 0,
                          color=COLORS["MED_GRAY"], width=1)
        # Vertical down to child top
        deck.add_line(slide, cx + cw / 2, mid_y,
                      0, cy - mid_y,
                      color=COLORS["MED_GRAY"], width=1)

    # Level 0 -- root box centered
    root_w = min(3.0, w * 0.30)
    root_h = 0.55
    root_x = x0 + (w - root_w) / 2
    root_y = y0
    _add_box(root.get("label", ""), root_x, root_y, root_w, root_h, 0)

    n_children = len(children)
    if n_children == 0:
        return

    # Level 1 -- children
    child_h = 0.50
    level1_y = root_y + root_h + 0.60
    child_cols = columns(n_children, total_width=w, start_x=x0, gutter=0.31)

    for i, (cx, cw) in enumerate(child_cols):
        child = children[i]
        _add_box(child.get("label", ""), cx, level1_y, cw, child_h, 1)
        _connector(root_x, root_y, root_w, root_h, cx, level1_y, cw)

        # Level 2 -- grandchildren
        grandchildren = child.get("children", [])
        if grandchildren:
            n_gc = len(grandchildren)
            gc_h = 0.45
            level2_y = level1_y + child_h + 0.55
            gc_gap = 0.06
            gc_w = (cw - gc_gap * max(n_gc - 1, 0)) / max(n_gc, 1)

            for j, gc in enumerate(grandchildren):
                gx = cx + j * (gc_w + gc_gap)
                _add_box(gc.get("label", ""), gx, level2_y, gc_w, gc_h, 2)
                _connector(cx, level1_y, cw, child_h, gx, level2_y, gc_w)

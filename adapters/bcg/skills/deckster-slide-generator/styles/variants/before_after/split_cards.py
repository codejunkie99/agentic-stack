"""Split cards — before/after contrast with LIGHT_BG cards on both sides.

Default before_after variant. Designed for arrow_half layouts where the
layout provides the visual contrast (white left side, green right side).
Both sides use LIGHT_BG card fills with no outlines. Labels distinguish
"Current State" (DARK_GREEN) and "Target State" (text_on green).
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render before/after split cards.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "before_items": [{"title": str, "description": str}, ...],
            "after_items": [{"title": str, "description": str}, ...],
            "before_label": str (default "Current State"),
            "after_label": str (default "Target State"),
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches

        For arrow_half layouts, caller should pass split bounds:
            Left bounds:  {"x": 0.69, "y": 1.70, "w": 5.20, "h": 4.80}
            Right bounds: {"x": 7.00, "y": 1.70, "w": 5.40, "h": 4.80}
        Or pass both zones in kwargs:
            left_bounds={"x": ..., "w": ...}
            right_bounds={"x": ..., "w": ...}
    """
    from bcg_template import COLORS, text_on

    before_items = data.get("before_items", [])
    after_items = data.get("after_items", [])
    before_label = data.get("before_label", "Current State")
    after_label = data.get("after_label", "Target State")

    # Support explicit left/right bounds for split layouts
    left_bounds = kwargs.get("left_bounds")
    right_bounds = kwargs.get("right_bounds")

    if left_bounds and right_bounds:
        lx = left_bounds["x"]
        lw = left_bounds["w"]
        rx = right_bounds["x"]
        rw = right_bounds["w"]
        y0 = left_bounds.get("y", bounds["y"])
        h = left_bounds.get("h", bounds["h"])
    elif all(k in bounds for k in ("left_x", "left_w", "right_x", "right_w")):
        lx = bounds["left_x"]
        lw = bounds["left_w"]
        rx = bounds["right_x"]
        rw = bounds["right_w"]
        y0 = bounds["y"]
        h = bounds["h"]
    else:
        # Default: split bounds evenly with a gap
        lx = bounds["x"]
        lw = bounds["w"] * 0.45
        gap = bounds["w"] * 0.10
        rx = lx + lw + gap
        rw = bounds["w"] - lw - gap
        y0 = bounds["y"]
        h = bounds["h"]

    label_h = 0.35
    card_fill = COLORS.get("LIGHT_BG", "F2F2F2")
    card_text = text_on(card_fill)
    panel_color = COLORS["BCG_GREEN"]

    # Make both columns the same width so they look symmetric.
    # Use the narrower zone's width (minus padding) for both sides.
    # This prevents the left cards from stretching to the arrow tip
    # and looking wider than the right cards.
    pad = 0.20
    usable_lw = lw - pad * 2
    usable_rw = rw - pad * 2
    card_w = min(usable_lw, usable_rw)
    # Center each column within its zone
    l_card_x = lx + (lw - card_w) / 2
    l_card_w = card_w
    r_card_x = rx + (rw - card_w) / 2
    r_card_w = card_w

    # --- Left side: "Current State" ---
    # Detect which side has the accent panel. If the left zone starts
    # near x=0 (inside the accent shape), the left bg is the accent.
    # If it starts at the fly zone margin, the left bg is the slide bg.
    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    left_on_accent = lx < 0.65
    left_bg = panel_color if left_on_accent else slide_bg
    right_bg = slide_bg if left_on_accent else panel_color
    deck.add_textbox(slide, before_label,
                     l_card_x, y0, l_card_w, label_h,
                     sz=16, color=text_on(left_bg), bold=True,
                     bg=left_bg if left_on_accent else None)

    card_y = y0 + label_h + 0.15
    n_before = len(before_items)
    if n_before > 0:
        card_gap = 0.12
        card_h = min(1.0, (h - label_h - 0.15 - (n_before - 1) * card_gap) / n_before)

        for j, item in enumerate(before_items):
            cy = card_y + j * (card_h + card_gap)
            deck.add_rounded_rectangle(slide, l_card_x, cy, l_card_w, card_h,
                                       card_fill, radius=5000)
            deck.add_textbox(slide, item.get("title", ""),
                             l_card_x + 0.15, cy + 0.08,
                             l_card_w - 0.30, 0.35,
                             sz=14, color=card_text, bold=True)
            desc = (item.get("description") or item.get("desc") or item.get("detail") or "")
            if desc:
                deck.add_textbox(slide, desc,
                                 l_card_x + 0.15, cy + 0.45,
                                 l_card_w - 0.30, card_h - 0.55,
                                 sz=12, color=card_text)

    # --- Right side: "Target State" ---
    deck.add_textbox(slide, after_label,
                     r_card_x, y0, r_card_w, label_h,
                     sz=16, color=text_on(right_bg), bold=True,
                     bg=right_bg if not left_on_accent else None)

    card_y = y0 + label_h + 0.15
    n_after = len(after_items)
    if n_after > 0:
        card_gap = 0.12
        card_h = min(1.0, (h - label_h - 0.15 - (n_after - 1) * card_gap) / n_after)

        for j, item in enumerate(after_items):
            cy = card_y + j * (card_h + card_gap)
            deck.add_rounded_rectangle(slide, r_card_x, cy, r_card_w, card_h,
                                       card_fill, radius=5000)
            deck.add_textbox(slide, item.get("title", ""),
                             r_card_x + 0.15, cy + 0.08,
                             r_card_w - 0.30, 0.35,
                             sz=14, color=card_text, bold=True)
            desc = (item.get("description") or item.get("desc") or item.get("detail") or "")
            if desc:
                deck.add_textbox(slide, desc,
                                 r_card_x + 0.15, cy + 0.45,
                                 r_card_w - 0.30, card_h - 0.55,
                                 sz=12, color=card_text)

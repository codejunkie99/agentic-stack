"""Green one-third panel — title-led left panel with right-side numbered items.

On the native `green_one_third` layouts, the left title panel belongs to the
layout placeholder. This variant should render only the right-side supporting
content. When called outside that native layout with a single full-width bounds
box, it falls back to the legacy self-contained panel rendering.
"""


def validate(deck, slide, data, bounds, **kwargs):
    items = data.get("items", [])
    if not items:
        return ["provide at least 1 right-side item"]
    if len(items) > 5:
        return ["limit green_one_third to 5 items or fewer"]
    issues = []
    for idx, item in enumerate(items, start=1):
        if not item.get("title"):
            issues.append(f"item {idx} is missing a title")
        if not (item.get("description") or item.get("desc") or item.get("detail")):
            issues.append(f"item {idx} is missing a description")
    return issues


def _resolve_zones(bounds):
    """Resolve panel/right-side geometry from dynamic split bounds when available."""
    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    if all(k in bounds for k in ("left_x", "left_w", "right_x", "right_w")):
        return {
            "mode": "split",
            "panel_x": bounds["left_x"],
            "panel_w": bounds["left_w"],
            "right_x": bounds["right_x"],
            "right_w": bounds["right_w"],
            "y": y0,
            "h": h,
        }

    panel_w = round(w * 0.30, 2)
    right_x = round(x0 + panel_w + 0.25, 2)
    right_w = round(w - panel_w - 0.25, 2)
    return {
        "mode": "full",
        "panel_x": x0,
        "panel_w": panel_w,
        "right_x": right_x,
        "right_w": right_w,
        "y": y0,
        "h": h,
    }


def render(deck, slide, data, bounds, **kwargs):
    """Render green one-third split panel.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "section_header": str,
            "items": [
                {"title": str, "description": str},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on

    geom = _resolve_zones(bounds)
    panel_title = data.get("panel_title", "")
    panel_subtitle = data.get("panel_subtitle", "")
    section_header = data.get("section_header", "")
    if geom["mode"] == "split" and not section_header and panel_subtitle:
        section_header = panel_subtitle
    items = data.get("items", [])

    panel_x = geom["panel_x"]
    panel_w = geom["panel_w"]
    right_x = geom["right_x"]
    right_w = geom["right_w"]
    y0 = geom["y"]
    h = geom["h"]

    if geom["mode"] == "full":
        deck.add_rectangle(slide, panel_x, y0, panel_w, h, COLORS["BCG_GREEN"])

        # Legacy fallback only: when no split metadata is available, the variant
        # owns the left panel and must paint the framing text itself.
        if panel_title:
            deck.add_textbox(slide, panel_title,
                             panel_x + 0.20, y0 + 0.30,
                             panel_w - 0.40, 0.60,
                             sz=20, color=text_on(COLORS["BCG_GREEN"]),
                             bold=True)

        if panel_subtitle:
            deck.add_textbox(slide, panel_subtitle,
                             panel_x + 0.20, y0 + 1.00,
                             panel_w - 0.40, 0.80,
                             sz=12, color=text_on(COLORS["BCG_GREEN"]))

    # Right side: numbered items
    if not items and not section_header:
        return

    badge_size = 0.36
    header_h = 0.0
    header_gap = 0.0
    if section_header:
        header_h = 0.35
        header_gap = 0.18

    n = len(items)
    item_h = 0.0
    if n > 0:
        available_h = max(h - 0.20 - header_h - header_gap, 0.80)
        item_h = min(0.85, available_h / n)

    total_h = header_h + header_gap + (item_h * n)
    start_y = y0 + max(0.10, (h - total_h) / 2)

    if section_header:
        deck.add_textbox(slide, section_header,
                         right_x, start_y,
                         right_w, header_h,
                         sz=14, color=COLORS["BCG_GREEN"], bold=True)

    rows_y = start_y + header_h + header_gap

    for i, item in enumerate(items):
        iy = rows_y + i * item_h

        # Number badge
        deck.add_number_badge(slide, i + 1,
                              right_x, iy + 0.06,
                              size=badge_size,
                              fill_color=COLORS["BCG_GREEN"])

        # Title
        text_x = right_x + badge_size + 0.12
        text_w = right_w - badge_size - 0.12
        deck.add_textbox(slide, item.get("title", ""),
                         text_x, iy + 0.02,
                         text_w, 0.28,
                         sz=14, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")), bold=True)

        # Description
        deck.add_textbox(slide, (item.get("description") or item.get("desc") or item.get("detail") or ""),
                         text_x, iy + 0.32,
                         text_w, item_h - 0.40,
                         sz=12, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

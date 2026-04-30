"""Green left arrow panel — arrow panel left with icon+title+desc rows on right.

Supports both layout-driven split bounds and legacy full-width bounds.
When the active layout exposes `left_x/right_x` split-zone metadata, the
variant renders only the right-side evidence and relies on the template for
the left framing panel. When called with a single full-width bounds box, it
falls back to the legacy self-contained arrow panel rendering.
"""


def validate(deck, slide, data, bounds, **kwargs):
    items = data.get("items", [])
    if not items:
        return ["provide at least 1 right-side item"]
    if len(items) > 4:
        return ["limit green_left_arrow to 4 items or fewer"]
    issues = []
    for idx, item in enumerate(items, start=1):
        if not item.get("title"):
            issues.append(f"item {idx} is missing a title")
        if not (item.get("description") or item.get("desc") or item.get("detail")):
            issues.append(f"item {idx} is missing a description")
    return issues


def _resolve_geometry(bounds):
    """Resolve panel and right-side geometry across old and new calling styles."""
    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    if "right_x" in bounds and "right_w" in bounds:
        return {
            "mode": "split",
            "x": x0,
            "y": y0,
            "h": h,
            "panel_x": bounds.get("left_x", x0),
            "panel_w": bounds.get("left_w", max(bounds["right_x"] - x0 - 0.25, 0)),
            "arrow_tip": 0.0,
            "right_x": bounds["right_x"],
            "right_w": bounds["right_w"],
        }

    # Some callers pass the already-split right panel directly.
    if w <= 8.25 and x0 >= 3.0:
        return {
            "mode": "right_only",
            "x": x0,
            "y": y0,
            "h": h,
            "panel_x": None,
            "panel_w": 0.0,
            "arrow_tip": 0.0,
            "right_x": x0,
            "right_w": w,
        }

    panel_w = round(w * 0.28, 2)
    arrow_tip = 0.35
    right_x = round(x0 + panel_w + arrow_tip + 0.25, 2)
    right_w = round(w - panel_w - arrow_tip - 0.25, 2)
    return {
        "mode": "full",
        "x": x0,
        "y": y0,
        "h": h,
        "panel_x": x0,
        "panel_w": panel_w,
        "arrow_tip": arrow_tip,
        "right_x": right_x,
        "right_w": right_w,
    }


def render(deck, slide, data, bounds, **kwargs):
    """Render green left arrow split panel.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "arrow_title": str,
            "panel_title": str,
            "subheader": str,
            "items": [
                {"icon": str, "title": str, "description": str},
                ...
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on

    geom = _resolve_geometry(bounds)
    y0 = geom["y"]
    h = geom["h"]
    panel_title = data.get("arrow_title") or data.get("panel_title") or ""
    subheader = data.get("subheader", "")
    items = data.get("items", [])

    if geom["mode"] == "full":
        panel_x = geom["panel_x"]
        panel_w = geom["panel_w"]
        arrow_tip = geom["arrow_tip"]
        deck.add_rectangle(slide, panel_x, y0, panel_w, h, COLORS["BCG_GREEN"])
        deck.add_rectangle(slide, panel_x + panel_w, y0 + h * 0.35,
                           arrow_tip, h * 0.30, COLORS["BCG_GREEN"])
        if panel_title:
            deck.add_textbox(slide, panel_title,
                             panel_x + 0.15, y0 + h * 0.25,
                             panel_w - 0.30, 0.60,
                             sz=18, color=text_on(COLORS["BCG_GREEN"]),
                             bold=True, valign="middle")

    right_x = geom["right_x"]
    right_w = geom["right_w"]

    title_sz = 14
    desc_sz = 12
    subheader_sz = 14
    icon_size = 0.50

    subheader_h = 0.0
    subheader_gap = 0.0
    if subheader:
        subheader_h = 0.30
        subheader_gap = 0.18

    n = len(items)
    row_h = 0.0
    if n > 0:
        available_h = max(h - 0.30 - subheader_h - subheader_gap, 0.80)
        row_h = min(1.05 if n <= 3 else 0.95, available_h / n)
        if row_h < 0.82:
            title_sz = 14
            desc_sz = 12
            subheader_sz = 14
            icon_size = 0.46

    total_block_h = subheader_h + subheader_gap + (row_h * n)
    start_y = y0 + max(0.15, (h - total_block_h) / 2)

    if subheader:
        deck.add_textbox(slide, subheader,
                         right_x, start_y,
                         right_w, subheader_h,
                         sz=subheader_sz, color=COLORS["DARK_GREEN"], bold=True)

    if not items:
        return

    rows_y = start_y + subheader_h + subheader_gap
    for i, item in enumerate(items):
        ry = rows_y + i * row_h

        icon_name = item.get("icon", "lightbulb")
        deck.add_icon(slide, icon_name,
                      right_x, ry + (row_h - icon_size) / 2,
                      size=icon_size, color=COLORS["BCG_GREEN"])

        text_x = right_x + icon_size + 0.12
        text_w = max(right_w - icon_size - 0.12, 0.50)
        deck.add_textbox(slide, item.get("title", ""),
                         text_x, ry + 0.03,
                         text_w, 0.30,
                         sz=title_sz, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")), bold=True)
        deck.add_textbox(slide, (item.get("description") or item.get("desc") or item.get("detail") or ""),
                         text_x, ry + 0.36,
                         text_w, max(row_h - 0.46, 0.20),
                         sz=desc_sz, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")))

"""Decision cards -- framed options with one recommended choice highlighted."""


def _estimate_lines(text, chars_per_line):
    text = (text or "").strip()
    if not text:
        return 0
    return max(1, (len(text) + chars_per_line - 1) // chars_per_line)


def _card_height_needed(option, width):
    title_width = max(width - (2.10 if option.get("recommended") else 0.30), 3.40)
    body_width = max(width - 0.30, 3.60)
    title_lines = _estimate_lines(option.get("title", ""), max(int(title_width * 7.5), 22))
    desc_lines = _estimate_lines(option.get("description", ""), max(int(body_width * 8.6), 26))
    upside_lines = _estimate_lines(option.get("upside", ""), max(int(body_width * 8.6), 26))
    tradeoff_lines = _estimate_lines(option.get("tradeoff", ""), max(int(body_width * 8.6), 26))
    title_h = max(0.22, title_lines * 0.15 + 0.03)
    desc_h = max(0.20, desc_lines * 0.15 + 0.03)
    upside_h = max(0.20, upside_lines * 0.15 + 0.03)
    tradeoff_h = max(0.20, tradeoff_lines * 0.15 + 0.03)
    return 0.12 + title_h + 0.04 + desc_h + 0.04 + upside_h + 0.04 + tradeoff_h + 0.10


def validate(deck, slide, data, bounds, **kwargs):
    options = data.get("options", [])
    if len(options) < 2:
        return ["provide at least 2 options"]
    if len(options) > 4:
        return ["limit decision cards to 4 options"]
    issues = []
    recommended = 0
    for idx, option in enumerate(options, start=1):
        if not option.get("title"):
            issues.append(f"option {idx} is missing a title")
        if not option.get("description"):
            issues.append(f"option {idx} is missing a description")
        if option.get("recommended"):
            recommended += 1
        if len((option.get("description") or "").strip()) > 95:
            issues.append(f"option {idx} description is too long for decision_cards; keep it to one short sentence")
        if len((option.get("upside") or "").strip()) > 90:
            issues.append(f"option {idx} upside is too long for decision_cards; shorten to a single concise line")
        if len((option.get("tradeoff") or "").strip()) > 90:
            issues.append(f"option {idx} tradeoff is too long for decision_cards; shorten to a single concise line")
    if recommended > 1:
        issues.append("mark only one option as recommended")
    subheader = (data.get("subheader") or "").strip()
    subheader_h = 0.28 if subheader else 0.0
    subheader_gap = 0.08 if subheader else 0.0
    available_h = bounds["h"] - subheader_h - subheader_gap
    required = sum(_card_height_needed(option, bounds["w"]) for option in options) + 0.12 * max(len(options) - 1, 0)
    if required > available_h * 1.10:
        issues.append("options exceed the available height; shorten the copy or split the decision")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render right-side decision cards for a green_left_arrow framing slide."""
    from bcg_template import COLORS, text_on, card_fill_for_slide, stack_y_positions

    options = data.get("options", [])
    if not options:
        return

    if "right_x" in bounds and "right_w" in bounds:
        x0 = bounds["right_x"]
        y0 = bounds["y"]
        w = bounds["right_w"]
        h = bounds["h"]
    else:
        x0 = bounds["x"]
        y0 = bounds["y"]
        w = bounds["w"]
        h = bounds["h"]

    subheader = (data.get("subheader") or "").strip()
    subheader_h = 0.28 if subheader else 0.0
    subheader_gap = 0.08 if subheader else 0.0
    card_gap = 0.12
    available_h = h - subheader_h - subheader_gap

    desired = [_card_height_needed(option, w) for option in options]
    total_desired = sum(desired) + card_gap * max(len(options) - 1, 0)
    scale = min(1.0, available_h / max(total_desired, 0.1))
    title_sz = 14 if scale >= 0.90 and len(options) <= 3 else 12
    body_sz = 12 if scale >= 0.90 and len(options) <= 3 else 11
    label_sz = 12

    min_height = 1.12 if len(options) <= 3 else 1.00
    heights = [max(min_height, block * scale) for block in desired]
    total_scaled = sum(heights) + card_gap * max(len(options) - 1, 0)
    if total_scaled > available_h:
        floor = 1.02 if len(options) <= 3 else 0.94
        shrinkable = sum(max(height - floor, 0.0) for height in heights)
        overflow = total_scaled - available_h
        if shrinkable > 0:
            adjusted = []
            for height in heights:
                reducible = max(height - floor, 0.0)
                share = overflow * (reducible / shrinkable) if reducible else 0.0
                adjusted.append(max(floor, height - share))
            heights = adjusted
    card_bounds = {"x": x0, "y": y0 + subheader_h + subheader_gap, "w": w, "h": available_h}
    ys = stack_y_positions(card_bounds, heights, gap=card_gap, align="center")

    if subheader:
        deck.add_textbox(
            slide,
            subheader,
            x0 + 0.10,
            y0,
            w - 0.20,
            subheader_h,
            sz=14,
            bold=True,
            color=text_on(COLORS.get("LIGHT_BG", "F2F2F2")),
        )

    card_fill = card_fill_for_slide()
    card_text = text_on(card_fill)
    highlight = COLORS["BCG_GREEN"]
    neutral = COLORS.get("MED_GRAY", "6E6F73")

    for option, cy, card_h in zip(options, ys, heights):
        recommended = bool(option.get("recommended"))
        accent = highlight if recommended else neutral
        deck.add_card(
            slide,
            x0,
            cy,
            w,
            card_h,
            fill_color=card_fill,
            accent_color=accent,
            accent_position="top",
            line_color=accent if recommended else None,
            line_width=1.5 if recommended else None,
        )

        if recommended:
            deck.add_label(
                slide,
                "RECOMMENDED",
                x0 + w - 1.90,
                cy + 0.06,
                1.80,
                0.28,
                fill_color=highlight,
                text_color=text_on(highlight),
                sz=label_sz,
            )

        title_w = w - (2.15 if recommended else 0.30)
        title_lines = _estimate_lines(option.get("title", ""), max(int(title_w * 7.5), 22))
        body_width = max(w - 0.30, 3.60)
        desc_lines = _estimate_lines(option.get("description", ""), max(int(body_width * 8.6), 26))
        upside_lines = _estimate_lines(option.get("upside", ""), max(int(body_width * 8.6), 26))
        tradeoff_lines = _estimate_lines(option.get("tradeoff", ""), max(int(body_width * 8.6), 26))

        inner_gap = 0.03
        title_h = max(0.22, title_lines * (0.15 if title_sz >= 14 else 0.14) + 0.02)
        body_lh = 0.16 if body_sz >= 12 else 0.15
        desc_h = max(0.20, desc_lines * body_lh + 0.02)
        upside_h = max(0.22, upside_lines * body_lh + 0.02)
        tradeoff_y = cy + 0.08 + title_h + inner_gap + desc_h + inner_gap + upside_h + inner_gap
        tradeoff_h = max(card_h - (tradeoff_y - cy) - 0.06, 0.22)

        deck.add_textbox(
            slide,
            option.get("title", ""),
            x0 + 0.15,
            cy + 0.06,
            title_w,
            title_h,
            sz=title_sz,
            bold=True,
            color=card_text,
        )
        deck.add_textbox(
            slide,
            option.get("description", ""),
            x0 + 0.15,
            cy + 0.08 + title_h + inner_gap,
            w - 0.30,
            desc_h,
            sz=body_sz,
            color=card_text,
        )
        deck.add_textbox(
            slide,
            [("Upside: ", {"bold": True, "color": highlight}), (option.get("upside", ""), {})],
            x0 + 0.15,
            cy + 0.08 + title_h + inner_gap + desc_h + inner_gap,
            w - 0.30,
            upside_h,
            sz=body_sz,
            color=card_text,
        )
        deck.add_textbox(
            slide,
            [("Trade-off: ", {"bold": True, "color": neutral}), (option.get("tradeoff", ""), {})],
            x0 + 0.15,
            tradeoff_y,
            w - 0.30,
            tradeoff_h,
            sz=body_sz,
            color=card_text,
        )

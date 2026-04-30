"""Workstream bars Gantt chart -- horizontal timeline bars with headers.

Draws horizontal bars on a time axis with quarter/month headers, alternating
row backgrounds, milestone diamonds, and duration labels.
"""


def render(deck, slide, data, bounds, **kwargs):
    """Render a Gantt-style workstream bar chart.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "workstreams": [
                {"name": str, "start": int, "end": int},
                ...
            ],
            "milestones": [{"month": int, "label": str}, ...] (optional),
            "total_months": int
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    workstreams = data.get("workstreams", [])
    milestones = data.get("milestones", [])
    total_months = data.get("total_months", 18)
    n = len(workstreams)
    if n < 1:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Layout: left labels + bar area
    label_w = 3.00
    bar_area_x = x0 + label_w + 0.15
    bar_area_w = w - label_w - 0.15

    # Header row — use quarters for long timelines, months for short ones
    header_h = 0.35
    month_w = bar_area_w / total_months
    if total_months > 12:
        # Quarter labels (Q1, Q2, ...) to avoid squished month labels
        n_quarters = (total_months + 2) // 3
        q_w = bar_area_w / n_quarters
        for q in range(n_quarters):
            label = f"Q{q + 1}"
            deck.add_textbox(slide, label,
                             bar_area_x + q * q_w, y0,
                             q_w, header_h,
                             sz=10, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")), align="center")
    else:
        for m in range(total_months):
            label = f"M{m + 1}"
            deck.add_textbox(slide, label,
                             bar_area_x + m * month_w, y0,
                             month_w, header_h,
                             sz=10, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")), align="center")

    # Quarter lines
    for q in range(0, total_months, 3):
        qx = bar_area_x + q * month_w
        deck.add_line(slide, qx, y0, 0, h,
                      color=card_fill_for_slide(), width=0.5)

    # Reserve space for milestones below the workstream rows
    milestone_h = 0.50 if milestones else 0

    # Workstream rows
    start_y = y0 + header_h + 0.15
    avail_h = h - header_h - 0.15 - milestone_h
    gap = 0.10
    bar_h = min(0.38, (avail_h - gap * (n - 1)) / n)

    fills = dark_fills(n)

    for i, ws in enumerate(workstreams):
        row_y = start_y + i * (bar_h + gap)

        # Alternating row background
        if i % 2 == 0:
            deck.add_rectangle(slide, x0, row_y - 0.02,
                               w, bar_h + 0.04, card_fill_for_slide())

        # Row label (accept name or label)
        deck.add_textbox(slide, ws.get("name", ws.get("label", "")),
                         x0, row_y, label_w, bar_h,
                         sz=11, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")), valign="middle")

        # Bar position (accept start/end or start_month/end_month)
        ws_start = ws.get("start", ws.get("start_month", 0))
        ws_end = ws.get("end", ws.get("end_month", total_months))
        bx = bar_area_x + (ws_start / total_months) * bar_area_w
        bw = ((ws_end - ws_start) / total_months) * bar_area_w

        deck.add_rounded_rectangle(slide, bx, row_y, bw, bar_h,
                                   fills[i % len(fills)], radius=4000)

        # Duration label on bar
        duration = f"{ws_end - ws_start}mo"
        deck.add_textbox(slide, duration, bx, row_y, bw, bar_h,
                         sz=10, color=text_on(fills[i % len(fills)]),
                         align="center", valign="middle")

    # Milestones as diamonds — placed BELOW the last workstream row
    if milestones:
        last_row_bottom = start_y + n * (bar_h + gap) - gap + 0.08
        for ms in milestones:
            month = ms.get("month", 0)
            mx_raw = bar_area_x + (month / total_months) * bar_area_w
            mx = min(max(mx_raw, bar_area_x + 0.10), x0 + w - 0.10)
            diamond_y = last_row_bottom + 0.08
            deck.add_shape(slide, "diamond",
                           mx - 0.10, diamond_y, 0.20, 0.20,
                           COLORS["DARK_GREEN"])

            ms_label = ms.get("label", "")
            if ms_label:
                ms_label_w = 1.20 if total_months > 12 else 0.96
                label_x = min(max(mx - ms_label_w / 2, bar_area_x), x0 + w - ms_label_w)
                deck.add_textbox(slide, ms_label,
                                 label_x, diamond_y + 0.22,
                                 ms_label_w, 0.20,
                                 sz=10, color=text_on(COLORS.get("SLIDE_BG", "F2F2F2")),
                                 bold=True, align="center")

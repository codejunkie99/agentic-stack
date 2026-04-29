"""Phase cards timeline — horizontal timeline with dots, labels, and detail cards.

Default timeline variant. Draws a horizontal green line with milestone dots,
phase name labels above, date labels below, and rounded-rectangle detail cards
with bullet content underneath.
"""


def validate(deck, slide, data, bounds, **kwargs):
    phases = data.get("phases", [])
    if len(phases) < 2:
        return ["provide at least 2 phases"]
    if len(phases) > 5:
        return ["limit phase_cards to 5 phases or fewer"]
    issues = []
    for idx, phase in enumerate(phases, start=1):
        if not phase.get("name"):
            issues.append(f"phase {idx} is missing a name")
        if not (phase.get("details") or []):
            issues.append(f"phase {idx} is missing details")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render a timeline with phase cards.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "phases": [
                {
                    "name": str,
                    "date": str (optional),
                    "details": [str, ...],
                },
                ...
            ],
            "summary": str (optional)  # bottom callout text
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, columns, card_fill_for_slide

    phases = data.get("phases", [])
    summary = data.get("summary", "")
    n = len(phases)

    if n < 2:
        return

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # Timeline line position — proportional to content zone height
    line_y = y0 + min(1.10, h * 0.22)
    dot_size = 0.24

    # Horizontal timeline line
    deck.add_line(slide, x0, line_y, w, 0,
                  color=COLORS["DARK_GREEN"], width=3)

    cols = columns(n, total_width=w, start_x=x0, gutter=0.31)
    body_sz = 12 if n <= 3 else 11
    if any(sum(len(str(item)) for item in phase.get("details", [])) > 180 for phase in phases):
        body_sz = 12

    # Card zone below the timeline
    card_top = line_y + min(0.55, h * 0.11)
    card_bottom = y0 + h
    if summary:
        card_bottom -= 0.50
    card_h = card_bottom - card_top

    slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
    slide_text = text_on(slide_bg)
    detail_card_fill = card_fill_for_slide()
    detail_card_text = text_on(detail_card_fill)

    for i, (cx, cw) in enumerate(cols):
        phase = phases[i]

        # Milestone dot on timeline
        dot_x = cx + cw / 2 - dot_size / 2
        dot_y = line_y - dot_size / 2
        deck.add_oval(slide, dot_x, dot_y, dot_size, dot_size,
                      COLORS["DARK_GREEN"])

        # Phase name above timeline
        deck.add_textbox(slide, phase.get("name", ""),
                         cx, line_y - 0.65, cw, 0.40,
                         sz=14, color=slide_text,
                         bold=True, align="center")

        # Date below timeline dot
        date = phase.get("date", "")
        if date:
            deck.add_textbox(slide, date,
                             cx, line_y + 0.20, cw, 0.30,
                             sz=12, color=slide_text,
                             align="center")

        # Detail card
        deck.add_rounded_rectangle(slide, cx, card_top, cw, card_h,
                                   detail_card_fill,
                                   radius=5000,
                                   line_color=COLORS["DARK_GREEN"],
                                   line_width=1.0)

        # Bullet details inside card
        details = phase.get("details", [])
        if details:
            deck.add_bullets(slide, details,
                             cx + 0.10, card_top + 0.10,
                             cw - 0.20, card_h - 0.20,
                             sz=body_sz, color=detail_card_text, spc_after=4)

    # Optional summary callout at bottom
    if summary:
        callout_y = card_bottom + 0.10
        callout_fill = card_fill_for_slide()
        deck.add_rounded_rectangle(slide, x0, callout_y, w, 0.40,
                                   callout_fill,
                                   line_color=COLORS["BCG_GREEN"],
                                   line_width=1.0, radius=8000)
        deck.add_textbox(slide, summary,
                         x0 + 0.15, callout_y, w - 0.30, 0.40,
                         sz=12, color=text_on(callout_fill),
                         valign="middle")

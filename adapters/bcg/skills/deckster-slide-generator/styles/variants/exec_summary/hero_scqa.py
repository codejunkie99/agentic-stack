"""SCQA executive summary -- narrative cards for executive synthesis.

Renders SCQA narrative cards stacked in the content zone.
The last card (answer) gets a BCG_GREEN fill. The slide title
placeholder (set via add_content_slide) carries the recommendation.
"""


def _estimate_lines(text, chars_per_line):
    text = (text or "").strip()
    if not text:
        return 0
    return max(1, (len(text) + chars_per_line - 1) // chars_per_line)


def _card_height_needed(headline, detail, width):
    headline_cpl = max(int(width * 8), 26)
    detail_cpl = max(int(width * 10), 34)
    headline_lines = _estimate_lines(headline, headline_cpl)
    detail_lines = _estimate_lines(detail, detail_cpl)
    return 0.22 + (headline_lines * 0.18) + (detail_lines * 0.16)


def validate(deck, slide, data, bounds, **kwargs):
    cards = data.get("cards", [])
    if not cards:
        return ["provide 3-4 SCQA cards"]
    if len(cards) > 4:
        return ["limit hero_scqa to 4 cards or split the slide"]
    issues = []
    gap = 0.10
    required = 0.0
    for idx, card in enumerate(cards, start=1):
        headline = (card.get("headline") or "").strip()
        detail = (card.get("detail") or "").strip()
        if not headline and not detail:
            issues.append(f"card {idx} is empty")
            continue
        required += _card_height_needed(headline or detail, detail if headline else "", bounds["w"])
    required += gap * max(len(cards) - 1, 0)
    if required > bounds["h"] * 1.10:
        issues.append("cards exceed the available height; shorten copy or split the summary")
    return issues


def render(deck, slide, data, bounds, **kwargs):
    """Render a hero SCQA executive summary.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "hero_title": str,
            "cards": [
                {"headline": str, "detail": str},
                ... (4 cards recommended; last is answer/green)
            ]
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills, columns, card_fill_for_slide

    hero_title = data.get("hero_title", "")
    cards = data.get("cards", [])

    # SCQA invisible scaffolding: strip framework labels if passed as headlines
    _SCQA_LABELS = {"situation", "complication", "question", "answer",
                    "context", "tension", "implication", "recommendation"}
    for card in cards:
        headline = card.get("headline", "").strip()
        if headline.lower().rstrip(":") in _SCQA_LABELS:
            # Framework label used as headline — swap detail into headline
            card["headline"] = card.get("detail", headline)
            card["detail"] = ""

    x0 = bounds["x"]
    y0 = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    # The slide title placeholder carries the action title.
    # The hero_title field is ignored.

    # Narrative cards fill the content zone
    n_cards = len(cards)
    if n_cards == 0:
        return

    cards_top = y0
    avail_h = h
    card_gap = 0.10
    desired = [
        _card_height_needed(card.get("headline", ""), card.get("detail", ""), w)
        for card in cards
    ]
    total_desired = sum(desired) + card_gap * max(n_cards - 1, 0)
    scale = 1.0
    headline_sz = 14
    detail_sz = 12
    if total_desired > avail_h:
        scale = (avail_h - card_gap * max(n_cards - 1, 0)) / max(sum(desired), 0.10)
        headline_sz = 13
        detail_sz = 11
    card_heights = [max(0.78, dh * scale) for dh in desired]
    total_cards_h = sum(card_heights) + card_gap * max(n_cards - 1, 0)
    if n_cards >= 4 or total_cards_h > avail_h * 0.82:
        cursor_y = cards_top
    else:
        cursor_y = cards_top + max(0.0, (avail_h - total_cards_h) / 2)

    for ci, card in enumerate(cards):
        card_h = card_heights[ci]
        cy = cursor_y
        is_answer = (ci == n_cards - 1)
        bg = COLORS["BCG_GREEN"] if is_answer else card_fill_for_slide()
        txt = text_on(bg)

        deck.add_rounded_rectangle(slide, x0, cy, w, card_h,
                                   bg, radius=5000)

        headline = card.get("headline", "")
        detail = card.get("detail", "")

        if detail:
            # Two-textbox card with explicit non-overlapping geometry
            headline_lines = _estimate_lines(headline, max(int((w - 0.40) * 8), 26))
            headline_h = min(max(0.24, headline_lines * 0.17 + 0.04), max(card_h - 0.32, 0.24))
            detail_y = cy + 0.10 + headline_h + 0.04
            detail_h = max(card_h - (detail_y - cy) - 0.10, 0.20)
            deck.add_textbox(slide, headline,
                             x0 + 0.20, cy + 0.10,
                             w - 0.40, headline_h,
                             sz=headline_sz, color=txt, bold=True)
            deck.add_textbox(slide, detail,
                             x0 + 0.20, detail_y,
                             w - 0.40, detail_h,
                             sz=detail_sz, color=txt)
        else:
            # Single-line card: just the headline centered
            deck.add_textbox(slide, headline,
                             x0 + 0.20, cy + 0.08,
                             w - 0.40, card_h - 0.16,
                             sz=headline_sz, color=txt, bold=True, valign="middle")
        cursor_y += card_h + card_gap

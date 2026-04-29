# Detail Template - `detail=True`

**`detail=True` is the default for ALL content slides.** The `add_content_slide()` method uses detail mode automatically — you do not need to pass `detail=True` explicitly.

Every standard layout has a detail counterpart prefixed `d_`. The `d_` stands for `detail`, not `dark`.

- `detail=True` is the default — use it for ~85% of content slides
- `detail=False` is for 2-3 key-message/statement slides per deck only
- if you are unsure, use `detail=True` — it is always safe

Use detail mode when:

- the slide needs smaller titles and a lighter evidence backdrop
- the content is table-, chart-, or appendix-heavy
- you need the extra content height that comes from the smaller title placeholder

```python
slide = deck.add_content_slide("Key transformation areas require immediate action", detail=True)

slide_bg = COLORS.get("SLIDE_BG", "F2F2F2")
deck.add_textbox(slide, "Analysis", 0.69, DETAIL_CONTENT_START_Y, 11.96, 0.3,
                 sz=16, color=text_on(slide_bg), bold=True)

deck.add_card(slide, 0.69, DETAIL_CONTENT_START_Y + 0.5, 5.5, 3.0,
              accent_color=COLORS["BCG_GREEN"], accent_position="top")
card_fill = COLORS.get("LIGHT_BG", "F2F2F2")
deck.add_textbox(slide, "Card content in dark text",
                 0.84, DETAIL_CONTENT_START_Y + 0.7, 5.2, 2.5,
                 sz=14, color=text_on(card_fill))
```

Usable content heights:

| Mode | Content starts | Content ends | Usable height |
|---|---|---|---|
| Standard title | `CONTENT_START_Y` = 2.27" | `CONTENT_END_Y` = 6.50" | 4.23" |
| Detail title (`detail=True`) | `DETAIL_CONTENT_START_Y` = 1.70" | `CONTENT_END_Y` = 6.50" | 4.80" |
| Tight fallback (overflow) | `CONTENT_START_Y_TIGHT` = 1.65" | `CONTENT_END_Y` = 6.50" | 4.85" |

The detail title placeholder is smaller, so content starts higher. If content still overflows in detail mode, fall back to `CONTENT_START_Y_TIGHT` (1.65") for the maximum 4.85" of usable height.

Rules:

- text placed directly on the slide background should use `text_on(COLORS.get('SLIDE_BG', 'F2F2F2'))` — this adapts to both gray and white backgrounds and client templates
- `LIGHT_TEXT` and `WHITE` belong only inside dark-filled or green-filled shapes
- never use white cards on white/detail backgrounds without contrast treatment
- prefer LIGHT_BG card bodies with top accents on detail slides
- mixed decks are fine: standard content slides plus detail backup slides

Bold treatments like accent bars and callout boxes can still be used inside the standard content family when the slide remains evidence-driven.

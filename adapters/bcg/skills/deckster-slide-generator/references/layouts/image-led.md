# Image-Led Layouts

Use these only when the image materially supports the message. Decorative photography is not enough.

## Green Half - Statement + Visual

Fifty-fifty split. The green left panel is owned by the layout title placeholder; the right half is the picture placeholder. Use for transformation themes, vision statements, or big insight + supporting photo where the title itself carries the message.

```python
slide = deck.add_content_slide(
    "AI-first operations will redefine the cost structure",
    layout="green_half",
)
deck.add_stock_image(slide, ["technology", "digital", "innovation"])
```

The left panel is **not** a free text canvas:

- do not add manual textboxes, bullets, cards, or overlays on the green panel
- do not draw rectangles or callout boxes over the title panel
- if the slide needs a subheader, bullets, or explanatory body copy, choose a different family (`content`, `green_highlight`, `green_one_third`, or `green_left_arrow`)

Rules:

- always use `fill_picture()` or `add_stock_image()` for the picture zone
- the slide title placeholder is the only intended text on the green panel
- do not use the layout if the image is decorative rather than evidentiary
- this layout intentionally omits the normal footer/source placeholders; do not manually recreate them

## Green Two-Third - Title + Supporting Visual

Two-thirds green title panel on the left, one-third picture placeholder on the right. Use when the title needs more horizontal room than `green_half`, but the slide is still fundamentally title + image only.

```python
slide = deck.add_content_slide(
    "Digital twin pilot validates 18% yield improvement at full scale",
    layout="green_two_third",
)
deck.add_stock_image(slide, ["strategy", "vision", "leadership"])
```

Rules:

- always use `fill_picture()` or `add_stock_image()` for the image side
- the left green panel is reserved for the title placeholder; do not add manual textboxes, bullets, cards, or other content shapes there
- if the slide needs body copy, route to another family instead of forcing it into `green_two_third`
- use `green_two_third` when the title needs extra width; use `green_half` when the title can stay shorter and the image should carry more weight

## Template-Specific Arrow / Image Variants

Some templates expose runtime layouts such as `left_arrow`, `arrow_two_third`, `green_arrow_half`, or `quote`. These are template-specific relatives of the same image-led logic and are valid only when the active template actually supports them.

Rich content + accent example:

```python
slide = deck.add_content_slide(
    "Cost analysis identifies four categories with highest savings potential",
    layout="arrow_two_third",
)

cols = [(0.69, 3.2), (4.1, 3.2)]
for i, (x, w) in enumerate(cols):
    deck.add_rounded_rectangle(slide, x, CONTENT_START_Y, w, 4.0, COLORS["WHITE"], radius=5000)
    deck.add_rectangle(slide, x, CONTENT_START_Y, w, 0.05, COLORS["BCG_GREEN"])
    card_fill = COLORS.get("WHITE", "FFFFFF")
    deck.add_textbox(slide, headers[i], x + 0.15, CONTENT_START_Y + 0.15, w - 0.3, 0.3,
                     sz=14, color=text_on(card_fill), bold=True)
    deck.add_bullets(slide, items[i], x + 0.15, CONTENT_START_Y + 0.6, w - 0.3, 3.2,
                     sz=14, spc_after=6)
```

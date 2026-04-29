# Statement Layouts

Use sparingly for recommendation peaks, closing messages, or authority / vision moments. These are high-impact punctuation slides, not workhorse evidence slides.

## Big Statement With Icon

Use for a bold statement on white with a reinforcing icon treatment.

```python
slide = deck.add_content_slide(
    "The question is not whether to transform,\nbut how fast we can move",
    layout="big_statement_icon",
)
```

Rules:

- do not add supporting shapes, boxes, or other elements in the title zone
- the title placeholder renders large and sits in the lower half of the slide; avoid placing elements between roughly 3.0in and 5.5in
- if the slide needs supporting evidence, switch to a framing or evidence layout instead

## Big Statement Green

Use for the highest-impact full-green statement slides.

```python
slide = deck.add_content_slide(
    "Move from insight to action:\nthree priorities for the next 90 days",
    layout="big_statement_green",
)
```

Rules:

- keep the message sharp
- do not try to turn this into a content slide
- if supporting context is necessary, use a framing or evidence layout instead

## Template-Specific Statement Variants

`special_gray` is the low-drama relative of these slides. Use it when you need visual differentiation for appendix or methodology content without the intensity of a full statement slide.

```python
slide = deck.add_content_slide(
    "Methodology and data sources underlying the analysis",
    layout="special_gray",
)
```

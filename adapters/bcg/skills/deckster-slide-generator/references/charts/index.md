# Charts

Start from the argument, not the raw data shape.

## Selection Guide

| Relationship | Pattern | Runtime path |
|---|---|---|
| trend over time | line chart | `add_chart(..., "line", ...)` |
| category comparison | clustered bar | `add_chart(..., "bar", ...)` |
| ranked comparison | horizontal bar | `add_chart(..., "bar_horizontal", ...)` |
| part-to-whole | donut / doughnut | `add_chart(..., "doughnut", ...)` |
| composition over time | stacked bar | `add_chart(..., "stacked_bar", ...)` |
| cumulative trends | stacked area | `add_chart(..., "stacked_area", ...)` |
| key metrics summary | KPI tiles / big numbers | shapes + text |
| bridge from start to finish | waterfall | merge path |
| volume plus rate | combo bar + line | merge path |

Read next by pattern:

- line / trend -> `line.md`
- clustered bar -> `bar.md`
- ranked comparison -> `horizontal-bar.md`
- composition -> `stacked-bar.md` or `area.md`
- part-to-whole -> `donut.md`
- KPI-led -> `kpi-tiles.md`
- waterfall -> `waterfall.md`
- combo -> `combo.md`

## Argument Alignment

Choose the chart whose structure proves the claim:

- `X is growing fast` -> line chart
- `we are bigger than competitors` -> sorted horizontal bar
- `three segments make up 80%` -> donut
- `revenue dropped then recovered` -> line with annotated inflection
- `this initiative bridges the gap` -> waterfall

## Teaching Checklist

Every chart slide should lock these decisions before rendering:

- chart type
- insight carrier
- context layer
- label strategy
- axis rule

Every finished chart slide should have:

- a title that states the takeaway
- a clear highlighted point, series, or segment
- context through baseline, target, prior period, or benchmark when needed
- a source line
- a callout box when the chart requires explicit interpretation

## Color Strategy

BCG chart color palette (ordered):

```python
['197A56', '29BA74', '295E7E', '3EAD92', '03522D', 'D4DF33', '575757', 'B0B0B0']
```

- for single-series comparisons, start in gray and highlight the key point in green
- for multiple series, use the ordered BCG palette from dark green through teal / navy
- do not use many similar green shades when the audience needs to distinguish segments quickly

## Slide Density

One chart per slide unless comparing two closely related views.

## Formatting Rules

1. remove chart junk: gridlines, 3D effects, unnecessary borders
2. label directly where possible rather than forcing legend lookup
3. sort bars by value unless the x-axis is chronological
4. round numbers for executive readability
5. use fixed axes when the claim depends on the full-scale context

## Native Chart Path

`add_chart()` produces editable PowerPoint-native charts.

```python
deck.add_chart(
    slide,
    chart_type,
    categories,
    series,
    x=0.69,
    y=CONTENT_START_Y,
    w=11.96,
    h=4.0,
    **options,
)
```

Key options:

- `colors`
- `number_format`
- `data_labels`
- `data_label_position`
- `legend`
- `gap_width`
- `hole_size`
- `smooth`
- `value_axis_min`
- `value_axis_max`

Per-series emphasis:

- `point_colors`
- `line_dash`

Height rules:

- chart only: `h=4.4`
- chart + bottom callout: `h=3.7`
- chart + KPI row: `h≈2.5`

The legend adds ~0.3" to rendered height. Account for this when placing elements below.

Common `number_format` values: `'#,##0'`, `'$#,##0'`, `'0"%"'`, `'0%'`

Source line spec: 10pt, `#6E6F73`, at y=6.74".

## Z-Order Rule

Charts cover any shapes added before them. Always add annotations, callouts, and highlights AFTER `add_chart()`, not before.

```python
# WRONG — callout is hidden behind the chart
deck.add_rounded_rectangle(slide, 0.69, 6.15, 11.96, 0.5, ...)
deck.add_chart(slide, "bar", categories, series)

# RIGHT — callout renders on top of the chart
deck.add_chart(slide, "bar", categories, series)
deck.add_rounded_rectangle(slide, 0.69, 6.15, 11.96, 0.5, ...)
```

## Merge Path

Use the Node / merge path intentionally for chart structures that native charts cannot express cleanly:

- waterfall
- combo bar + line

The merge path is a build implementation detail, not a separate planning workflow.

Read the specific leaf file before implementing either merge-path chart.

# Combo Chart

Use when one chart must show two related measures, usually magnitude plus rate or index.

## Implementation Notes

No dedicated variant file exists for combo — use the chart engine's multi-type chart approach (bar + line overlay with optional secondary value axis). See the merge-path chart infrastructure for shared defaults.

Data schema:
- bar_series: object with name and values (primary measure)
- line_series: object with name and values (secondary measure)
- categories: list[str]
- secondary_axis: bool (whether the line uses a secondary value axis)

Rules:

- keep one dominant message
- use the secondary axis only when it materially helps
- split the visual if the dual-axis chart becomes harder to parse than two slides

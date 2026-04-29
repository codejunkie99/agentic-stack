# Waterfall

Use for bridge logic from a starting point to an ending point.

Preferred implementation is the merge path when native charts cannot express the bridge cleanly. The waterfall is built as a stacked bar with an invisible base series and a visible value series.

## Implementation Notes

- values[0] = start total, values[last] = end total, middle values = deltas
- base series is invisible (matches slide background), value series shows the actual bars
- positive deltas stack above the running total, negative deltas stack below
- bar colors should distinguish positive vs. negative moves

No dedicated variant file exists for waterfall — use the chart engine's stacked bar approach with computed base values. See the merge-path chart infrastructure for shared defaults.

Data schema:
- labels: list[str] (step names including start and end totals)
- values: list[float] (start total, deltas, end total)
- bar_colors: list[str] (hex colors per bar, typically green for positive, red for negative, gray for totals)

Rules:

- order the steps causally
- distinguish positive and negative moves clearly
- use only when the bridge itself is the message

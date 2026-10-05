# Native dashboard design

The dashboard helps a coding-tool user decide what to start, what is running, and what needs review. It is a native SwiftUI macOS workspace, with a quieter navigation rail and a main work column beside project context.

## Research applied

- [Linear: A calmer interface for a product in motion](https://linear.app/now/behind-the-latest-design-refresh), March 2026. Task content receives the strongest hierarchy; navigation and boundaries recede. Applied through restrained borders, compact controls, consistent alignment and no raw collector data in the overview.
- [Nielsen Norman Group: Dashboards](https://www.nngroup.com/articles/dashboards-preattentive/), June 2017. An operational dashboard should communicate actionable state quickly. Applied through running/review counts and a priority queue. Horizontal lengths compare real imported-file counts; no invented usage charts or activity trends.
- [Linear Projects](https://linear.app/docs/projects). Keep project context close to the actual work. Applied through the adjacent agent and knowledge panels, with focused destinations for editing and inspection.

## Interaction contract

Counters filter work or open the relevant workspace. Queue rows open exact task IDs. The composer prepares a real task sheet, where agent, access and knowledge options remain explicit. Project/host-scoped drafts survive navigation and cancel; successful submission clears a matching draft. Terminal arrows launch the selected official CLI. Detailed collectors remain available in a separate diagnostics sheet.

At 800-point content width, both columns remain usable and the dashboard scrolls vertically. At standard desktop width, the queue and context sit side by side with more breathing room. Light and dark appearances use native system colors. Empty states explain a next action; unavailable data is distinct from a real zero.

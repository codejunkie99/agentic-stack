# Flywheel Loop

Encodes cyclical processes, feedback loops, continuous improvement, and iterative cycles. The circular arrangement means each stage feeds the next.

Isomorphism:

- use when the process repeats and each stage reinforces the next
- do not use for one-directional sequences; use chevrons or a timeline instead

Use cases:

- agile sprints
- PDCA cycles
- platform flywheels
- growth loops
- DevOps feedback loops

Scales:

- 3-7 nodes
- metrics shown only for `n <= 4`
- node radius, font size, and arrow size adapt automatically

## Pattern Variants

The flywheel pattern is available via `render_pattern()` with two variants:

- **circular_orbit** (default) — Nodes orbiting a center hub with directional arrows. Best for 3-7 stage cycles.
- **concentric_rings** — Rings radiating outward from a center core. Each ring is a stage layer. Best for 3-6 stages where layering matters more than flow direction.

Default variant: `circular_orbit` (`styles/variants/flywheel/circular_orbit.py`)
Alternatives: `concentric_rings` (`styles/variants/flywheel/concentric_rings.py`) — layered rings when nesting matters more than flow direction

Data schema:
- stages: list of objects, each with:
  - label: str (node label, can use `\n` for line breaks)
  - metric: str (optional, shown only when n <= 4)
- center_message: str (text for the center hub, can use `\n`)

Rules:

- use only for genuinely cyclical logic
- keep each node action-oriented
- allow node radius, label size, and orbit to scale with node count
- avoid it for one-time implementation roadmaps
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

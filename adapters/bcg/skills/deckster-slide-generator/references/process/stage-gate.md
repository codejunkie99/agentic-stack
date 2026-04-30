# Stage Gate Process

Horizontal flow with colored gates for intake or approval processes.

## Pattern Variants

The stage gate pattern is available via `render_pattern()`:

- **gate_flow** (default) — Gradient-filled gate columns with arrows between them and detail cards below each gate.

Default variant: `gate_flow` (`styles/variants/stage_gate/gate_flow.py`)

Data schema:
- gates: list of objects, each with:
  - name: str (gate name)
  - subtitle: str (gate subtitle or criteria)
  - details: list[str] (bullet points for the detail card below the gate)

Runtime note:
- `render_pattern()` accepts the doc schema above directly and normalizes it into the variant's internal `stages` + `gates` structure

Rules:

- use this when gate logic matters more than exact scheduling
- make the gate criteria visible or strongly implied
- avoid it for simple linear sequences with no real approvals or checkpoints
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

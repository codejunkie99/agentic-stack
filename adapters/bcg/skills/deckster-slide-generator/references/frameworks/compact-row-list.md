# Compact Row List

Use for challenge lists, risk registers, capability inventories, or feature lists where each item has the same fields and repetition improves scanability.

## Pattern Variants

The compact row list pattern is available via `render_pattern()`:

- **icon_rows** (default) — Repeated horizontal rows with left accent bar, icon, title, description, and optional category label. Includes a bottom callout bar for a key insight.

Default variant: `icon_rows` (`styles/variants/compact_row_list/icon_rows.py`)

Data schema:
- items: list of objects, each with:
  - icon: str (icon name, e.g. "NutsAndBolts", "People", "DataAnalysis")
  - title: str (item title)
  - desc: str (item description)
  - label: str (optional, category tag displayed at right)
- callout: str (optional, key insight text for the bottom callout bar)

Sizing notes:

- each row is 0.95in tall with 0.12in gaps for four rows
- for five rows, reduce row height to 0.80in and gap to 0.10in
- for six rows, use 0.70in rows and keep titles at 14pt if possible

Rules:

- the bottom callout must end at or before 6.50" to avoid the source line at 6.74"
- keep each row structurally consistent
- use this when repetition improves scanability
- if the list becomes a sequence, switch to a process pattern
- if rows become long narratives, switch to cards or a two-column framework
- always call `render_pattern()` with `bounds=content_bounds()` — do not hardcode coordinates

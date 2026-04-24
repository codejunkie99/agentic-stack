# Generic context

Firm-generic semantic context — consulting-industry frameworks, glossary,
quality standards. Loaded unconditionally at session start (no adapter
toggle required). Useful on BCG engagements, personal projects, and any
analytical work where MECE thinking and pyramid-principle communication
help.

## Files

| File | What's in it |
|---|---|
| `glossary.md` | Consulting terminology (MECE, pyramid, RAID, workstream, hypothesis, …) |
| `frameworks.md` | Analytical frameworks (Issue Tree, Pyramid, 7-S, Value Chain, Driver Tree, Sensitivity, Market Sizing, Pricing) |
| `quality-standards.md` | Output bar: so-what-first, MECE discipline, evidenced claims, sensitivity transparency |

## Firm-specific overlays

When a firm adapter is active (e.g. `bcg_adapter: "enabled"`), its context
is loaded on top of this generic base — see `adapters/bcg/context/` for
BCG-specific additions (firm hierarchy, BCG-attributed frameworks like
the Growth-Share Matrix, engagement process norms).

Generic always loads first; firm-specific is additive. If a firm file
contradicts a generic one, the firm version takes precedence within that
adapter's domain only.

## Provenance

Content in this directory originated in Kenneth Leung's `harness-starter-kit`
(BCG, 2026-04) and was split in Step 8.2.4 from the all-BCG bundle into
(a) firm-generic consulting content here and (b) BCG-specific content in
`adapters/bcg/context/`. The split was driven by user feedback that
frameworks and glossary were useful in personal projects, not only BCG
engagements.

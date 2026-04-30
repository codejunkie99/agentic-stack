---
workflow_id: feature-prototype
name: Single-Feature Prototype (Spike)
team_structure: flat
description: Spike on ONE feature inside an existing app — validate a UX or technical hypothesis without touching production code paths. Single prototype-engineer; coordinated demo-prep at the end.
---

## Purpose

Validate a single feature hypothesis inside an existing codebase. Distinct
from `prototype-app.md` (whole-app prototype, may not have production
context) — this is a feature-spike living inside production code, deliberately
isolated so the spike can be discarded without affecting the main app.

## Trigger phrases

"spike this feature", "prototype the [feature] in our app", "feature spike",
"can we validate [feature] before committing the build", "throwaway prototype
of [feature]".

## Team

| Phase | Agent | Output |
|---|---|---|
| Validate hypothesis | prototype-engineer | `output/feature-prototypes/<slug>/` + HYPOTHESIS.md + LEARNINGS.md |
| Demo prep | engineer or prototype-engineer + `demo-prep` skill | demo package |

## Constraints

- **Isolation:** spike code must live in a path the main app doesn't import
  (e.g., `experiments/`, `prototypes/`, feature-flagged route).
- **No schema changes** to production tables — use a sandbox DB or local
  migrations. If schema change is essential to the hypothesis, escalate
  to production workflow instead.
- **Time-box:** declared upfront. Hard stop at the box.

## Quality gates

- Spike runs end-to-end against the hypothesis
- LEARNINGS.md answers PASS / FAIL / INCONCLUSIVE
- Spike code is clearly marked throwaway (README in spike dir)

## Path-to-production decision

Same as `prototype-app.md`: graduate via production workflow (rebuild),
iterate (another spike), or park.

## Memory write discipline

`memory_reflect` at importance 8, pain 5 at exit with the durable lesson
about what the spike taught the broader codebase.

---
workflow_id: refactor-arc
name: Refactor Arc — internal restructure, no behavior change
team_structure: flat
description: Restructure code without changing observable behavior. No PRD or ADR (no product change), but reviewer panel still applies because internal contracts can break. Distinct from `feature-end-to-end` (new behavior) and `bugfix-arc` (defect fix).
---

## Purpose

Refactor existing code — extract, rename, decompose, dedupe — without changing what users see. Forces test-first discipline so behavior preservation is mechanically verified, not asserted.

Triggers on:

- "refactor X"
- "extract Y into Z"
- "rename W"
- "consolidate duplicate Q"
- "untangle this module"

Does NOT trigger on: behavior changes (route to `feature-end-to-end`), bug fixes (route to `bugfix-arc`).

## Contents

Internal restructure with mechanically verified behavior preservation:

1. **Behavior baseline** — existing tests pass before the refactor starts; if no tests exist for the affected code, write them BEFORE refactoring (characterization tests)
2. **Refactor** — applied incrementally; tests stay green between each step
3. **Diff review** — 4-lens reviewer panel
4. **Merge** — into next release; not a hotfix path

## Team Structure: Flat

- **engineer** — owns the refactor. Writes characterization tests first if coverage is thin. Each step is a separate commit per `superpowers:test-driven-development` discipline (RED is "tests fail at the boundary I'm refactoring across", GREEN is "they pass after my edit", commit per task).
- **reviewer** — general adversarial review.
- **type-design-reviewer** — primary lens for refactors: encapsulation, invariant expression, sum types, interface clarity.
- **performance-reviewer** — if hot path: confirm the refactor isn't slower (microbenchmarks where relevant).

NO product-manager, NO architect, NO designer. Refactor is pure-internal.

## Quality Gates

- All tests pass before AND after every refactor step (no green→red→green within a single commit)
- If pre-refactor coverage <70% on affected code: characterization tests added BEFORE refactor begins
- type-design-reviewer reports: invariants stronger or unchanged (never weaker)
- performance-reviewer reports: no regression beyond noise threshold (specify threshold per refactor)
- No public API contract change (else: this isn't a refactor; route to `feature-end-to-end`)
- Diff under 500 lines per commit; bigger diffs split into multiple commits

## Output Format

- Branch: `refactor/<slug>`
- Commits per step (small, atomic, each green)
- No DECISIONS.md entry unless refactor reveals architectural decision worth durably recording (e.g., "we standardized on X over Y across the module")

## Iteration Discipline

After refactor merged:

```bash
python3 .agent/tools/memory_reflect.py "engineer" \
  "refactor shipped" \
  "<slug>: refactored <module/area> — <n_commits> commits, coverage <pre>% → <post>%, type-design verdict <pass>" \
  --importance 6 --pain 5 \
  --note "DURABLE LESSON: <one sentence — what's the design intuition that emerged? E.g. 'invariants belong in the type, not in the runtime check, when the type system can express them.'> | INVARIANTS STRENGTHENED: <which> | ALMOST BROKE: <where coverage gap nearly let regression through>"
```

importance 6 × pain 5 = 30 → salience 3.0 (cluster-dominant on internal-edit noise; doesn't auto-graduate but accumulates).

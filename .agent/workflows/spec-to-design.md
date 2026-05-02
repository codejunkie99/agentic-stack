---
workflow_id: spec-to-design
name: Spec to Design — PRD to ADR + design pack
team_structure: flat
description: Take a signed-off PRD through architectural decision (ADR) and product-design (wireframes + flows) to a build-ready design pack. Architect produces ADR; designer produces design-pack when UI surface non-trivial. Stops short of implementation. Downstream `feature-end-to-end` consumes the pack.
---

## Purpose

Convert PRD into the design artefacts the engineering team needs before writing code: ADR (system design) + design-pack (UX/UI when relevant). Forces design-then-build per superpowers canonical posture (HARD-GATE: no impl until design approved).

Triggers on:

- "design this feature"
- "ADR for <feature>"
- "wireframe the UI"
- "architect this"
- "what's the design?"

## Contents

- **`docs/adr/YYYY-MM-DD-<slug>.md`** — Architecture Decision Record:
  - Context (why now, what changed)
  - Decision (chosen approach, named explicitly)
  - Component diagram with typed interfaces
  - Data flow (incl. failure branches)
  - Edge-case matrix
  - Test-seam list (where tests will hook)
  - Assumption ledger (what we're betting on)
  - Alternatives considered + rejection reason
- **Design pack** (only when UI surface non-trivial):
  - User-flow diagram
  - Wireframes (markdown ASCII or pointer to Figma)
  - Design-system decisions (component reuse, new patterns)
  - "Looks right + feels right" acceptance criteria

## Team Structure: Flat

- **architect** — owns ADR. Reads PRD, runs `spec-reviewer` skill against PRD on a 0-10 rubric to gate go/no-go. Produces ADR with explicit edge-case matrix and assumption ledger.
- **product-designer** (only if UI surface) — owns design pack. Wireframes + flows + design-system decisions. Adds UX acceptance criteria alongside functional ones.

Both run in parallel; integrate at end-of-arc. No orchestrator — pure flat dispatch.

## Quality Gates

- ADR has non-empty Alternatives Considered section (architect-forced exposure of taste)
- Component diagram names every interface as a typed contract (no "data passes through here")
- Edge-case matrix has ≥5 rows
- Assumption ledger has ≥3 entries each with a falsification test
- spec-reviewer rubric scores ≥7/10 before ADR signed (else: PRD goes back to product-discovery-arc)
- If UI surface: wireframe covers every user story in the PRD; design pack has ≥3 UX acceptance criteria

## Output Format

- `docs/adr/YYYY-MM-DD-<slug>.md` (always)
- `docs/design/YYYY-MM-DD-<slug>/` directory with wireframes + flows (only if UI surface)
- One-line entry appended to `docs/adr/_index.md` if it exists

## Iteration Discipline

After ADR signed off:

```bash
python3 .agent/tools/memory_reflect.py "architect" \
  "ADR signed off" \
  "<slug>: ADR v<N> approved — <n_components> components, <n_edge_cases> edge cases, rubric=<X>/10" \
  --importance 9 --pain 6 \
  --note "DURABLE LESSON: <one sentence — what about this architectural choice transfers? E.g. 'when N services share a write path, queue-mediated decoupling beats direct synchronous calls when latency matters less than throughput.'> | KEY ALTERNATIVES: <which were rejected + why> | RISKS NOTED: <unfalsifiable assumptions, deferred decisions>"
```

importance 9 × pain 6 = 54 → salience 5.4 (dominates cluster; near-graduates).

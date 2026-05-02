---
workflow_id: feature-end-to-end
name: Feature End-to-End — full PDLC arc
team_structure: full
description: Full production-feature PDLC: PRD signed off → ADR + design-pack signed off → parallel FE + BE implementation under TDD → integration → 4-lens reviewer panel → release. Flagship SDLC workflow. Use for production-bound features. Use `prototype-app` instead for throwaway spike work.
---

## Purpose

Ship a production-grade feature end-to-end with full discipline:
brainstorm → spec → design → plan → TDD-build → integrate → review → release.

Distinct from prototype workflows: this one assumes the feature WILL ship and applies the full review panel + verification before completion. Triggers on:

- "build the [feature]"
- "ship the [feature]"
- "production [feature]"
- "let's implement [PRD-slug]"

## Contents

End-to-end production feature delivered to staging or production. Stages:

1. **PRD reference** — must be signed off (`docs/prd/<slug>.md`); otherwise route back to `product-discovery-arc`
2. **ADR + design pack** — must be signed off (`docs/adr/<slug>.md` + optional `docs/design/<slug>/`); otherwise route to `spec-to-design`
3. **Implementation plan** — `planner` skill produces task breakdown at `docs/plans/<slug>.md`
4. **Parallel build** — FE and BE work concurrently under TDD; integration-engineer wires the boundary
5. **Verification** — qa-runner exercises the feature in real runtime
6. **Review panel** — 4 reviewers in parallel: general, security, performance, type-design
7. **Release** — release-manager runs deploy-checklist, ships, writes release notes

## Team Structure: Full

Orchestrator: **product-manager** (or **engineer** if PM not in roster). Coordinates fan-out; does NOT draft content directly.

### Phase 3 — Plan
- **planner** (skill) — produces `docs/plans/<slug>.md`. Hands off to engineering team.

### Phase 4 — Parallel build (TDD per superpowers)
- **frontend-engineer** — UI components + client state + UI tests. Reads design pack.
- **backend-engineer** — API + data layer + business logic + integration tests against fixture.
- **integration-engineer** — wires the boundary AFTER both FE+BE return; writes contract tests.

Both engineers use `superpowers:test-driven-development` skill (Red-Green-Refactor; commit per task).

### Phase 5 — Verification
- **qa-runner** — runs the feature against the acceptance criteria from PRD + ADR. Catches "tests pass but feature doesn't work" gap. Uses `superpowers:verification-before-completion` skill.

### Phase 6 — Reviewer panel (parallel, 4 lenses)
- **reviewer** — general adversarial review (CRITICAL checklist: SQL safety, LLM trust boundary, races, shell injection, enum completeness)
- **security-reviewer** — auth, secrets, input validation, OWASP top-10
- **performance-reviewer** — runtime cost, queries, bundle size, render perf
- **type-design-reviewer** — encapsulation, invariant expression, sum types vs booleans

Each returns severity-ranked findings (critical / warning / info). Critical findings block release.

### Phase 7 — Release
- **release-manager** — runs `deploy-checklist` skill, merges, deploys, writes release notes (audience-sectioned: users / operators / devs), proposes semver bump, logs to `DECISIONS.md`.

## Quality Gates

- PRD signed off + ADR signed off before Phase 3 enters
- Every task in the plan has TDD ordering (test → fail → impl → pass → commit)
- All tests pass on the integration branch (no skipped tests committed)
- qa-runner reports PASS against ≥80% of PRD acceptance criteria; remaining 20% explicitly waived in writing
- Each reviewer (×4) returns no critical findings unaddressed
- deploy-checklist passes
- Release notes have non-empty Users / Operators / Devs sections
- DECISIONS.md has new entry summarizing the feature + version bump

## Output Format

- Branch: `feature/<slug>` merged to master
- Code in repo per ADR component layout
- Tests in repo
- `docs/plans/<slug>.md` (planner)
- `RELEASE-NOTES.md` updated by release-manager
- `DECISIONS.md` entry by release-manager

## Iteration Discipline

After release:

```bash
python3 .agent/tools/memory_reflect.py "release-manager" \
  "feature shipped" \
  "<slug>: v<X.Y.Z> released — <n_commits> commits, <n_review_findings_addressed> findings addressed" \
  --importance 10 --pain 8 \
  --note "DURABLE LESSON: <one sentence — what about this PDLC arc transfers? E.g. 'when FE+BE land in same PR, contract tests at the integration layer catch 80% of cross-team drift.'> | DECISIONS LOG: <key implementation calls — taste, scope cuts, reviewer overrides> | WHAT NEARLY FAILED: <reviewer findings that almost blocked release; gates that fired late>"
```

importance 10 × pain 8 = 80 → salience 8.0 → graduates alone (per Phase L tuning math).

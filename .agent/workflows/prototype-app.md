---
workflow_id: prototype-app
name: Build a Working Prototype App
team_structure: full
description: Top-level workflow for "build a working prototype app" — full SDLC team dispatched in canonical sequence with parallel splits where independent. Output is a runnable prototype with clear hypothesis, validation, and a path-to-production note (whether to graduate the code or rebuild under production discipline).
---

## Purpose

Take a product idea and produce a runnable prototype that validates the
hypothesis. Distinct from production work: a prototype trades
production-grade rigor (full ADR, exhaustive tests, multi-reviewer
parallel panel) for speed-of-validation. The output answers "does this
work at all?" not "is this ready to ship?"

This workflow has two valid execution shapes:

1. **Spike mode (fastest)** — single `prototype-engineer` agent owns
   full stack; skips ADR, design pack, parallel review. Use when:
   time-box is hours not days; hypothesis is binary; throwaway code OK.
2. **Lite-PDLC mode (more rigorous)** — runs the canonical pipeline at
   reduced depth: PM → designer → architect → FE+BE parallel →
   integration → QA → single general reviewer. Skips parallel reviewer
   panel + release-manager. Use when: prototype may graduate to
   production; user-facing surface is non-trivial; hypothesis is
   compound.

The orchestrator (root agent) picks the shape based on the user's
time-box + scope. Default: spike mode unless user signals the
prototype must be salvageable for production.

## Trigger phrases

"build a prototype", "build a working prototype", "spike on", "quick
prototype of", "validate this idea with a prototype", "MVP prototype",
"proof-of-concept app", "demo-able prototype".

## Team — spike mode

Single agent: `prototype-engineer`. Full-stack, throwaway, time-boxed.

| Phase | Agent | Output |
|---|---|---|
| Validate hypothesis | prototype-engineer | `output/prototypes/<slug>/HYPOTHESIS.md` + working code + LEARNINGS.md |

## Team — lite-PDLC mode

| Phase | Agent(s) | Output |
|---|---|---|
| Frame | product-manager | `output/prd/<slug>.md` (lighter than production PRD) |
| Design (only if UI) | product-designer | `output/design/<slug>/wireframes.md` + acceptance.md |
| Architect | architect | `output/adr/<slug>.md` (lighter — focuses on prototype-survivable choices) |
| Implement (parallel) | frontend-engineer + backend-engineer | branches with TDD commits |
| Integrate | integration-engineer | integration tests + cross-boundary report |
| Runtime QA | qa-runner | `output/qa/<slug>-runtime-report.md` |
| Review | reviewer (general only — skip security/perf/type-design panel) | `output/review/<slug>-review.md` |
| Demo prep | engineer + `demo-prep` skill | `output/demo/<slug>/` package |

`release-manager` is NOT in the prototype workflow — prototypes don't
ship through release-manager. If the prototype graduates to production,
re-run `production-feature` workflow against the validated PRD; rebuild
the code under full discipline.

## Quality gates

**Spike mode:**
- Time-box discipline (when box runs out, stop and report partial-but-working)
- LEARNINGS.md must answer the hypothesis (PASS / FAIL / INCONCLUSIVE)
- Demo command must work end-to-end

**Lite-PDLC mode:**
- All canonical gates EXCEPT parallel reviewer panel
- qa-runner runtime report must be PASS or APPROVED-WITH-FIXES
- General reviewer must approve before demo packaging

## Path-to-production decision

After prototype lands and is reviewed by user:

- **Graduate**: re-run `production-feature` workflow against validated
  PRD. Rebuild the code under full discipline. The prototype's value
  was the LEARNINGS, not the code.
- **Iterate**: another spike round on a refined hypothesis.
- **Park**: hypothesis answered, no production path planned. Archive
  in `output/prototypes/<slug>/` with status="parked".

This decision is documented in WORKSPACE.md before the orchestrator
moves on.

## Anti-patterns

- **Skipping the time-box** — prototypes that run longer than agreed
  become production work without the discipline. Stop on time, hand
  back what works.
- **Graduating prototype code directly** — the shortcuts that made it
  fast make it unsafe to ship. Re-build under production workflow.
- **Running full reviewer panel on a spike** — the panel exists for
  production diffs. Cycles spent there are cycles not validating the
  next hypothesis.

## Memory write discipline

At workflow exit (whichever mode), the orchestrator MUST call
`memory_reflect.py` at importance 9, pain 7 with a DURABLE LESSON note
about what the prototype taught — both the answer to the hypothesis
AND any harness-shaped friction encountered (skill ordering off,
agent prompt unclear, workflow contract gap).

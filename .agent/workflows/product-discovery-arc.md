---
workflow_id: product-discovery-arc
name: Product Discovery Arc — idea to validated PRD
team_structure: flat
description: Take a free-form product idea ("we should build X", "users keep asking for Y") through canonical brainstorming + product-discovery to a validated PRD with acceptance criteria and story decomposition. Output is the PRD doc; downstream workflows (`spec-to-design`, `feature-end-to-end`) consume it. Stops short of any architecture or code.
---

## Purpose

Convert a raw product intent into a validated, scoped PRD an architect or designer can act on. Forces disambiguation early so downstream rework is cheap. Triggers on:

- "I want to build X"
- "we should add Y feature"
- "users are asking for Z"
- "PRD for <feature>"
- "scope this idea"
- "should we build this?"

## Contents

PRD document at `docs/prd/YYYY-MM-DD-<slug>.md` containing:

1. **Problem statement** — one paragraph: who hurts, what hurts, evidence
2. **Goal + non-goals** — what success looks like; what's explicitly out of scope
3. **User stories** — 3-7 stories: "As a <user>, I want <capability> so that <outcome>"
4. **Acceptance criteria** — per story, testable conditions for "done"
5. **Risks + open questions** — what we don't know yet
6. **Story breakdown** — ordered list of build-able stories, sized for one engineer week or less

## Team Structure: Flat

Two agents work the arc; no orchestrator (the user is the loop).

- **product-manager** — runs the discovery → spec → story-decomposition pipeline. Uses `superpowers:brainstorming` skill (canonical pattern: explore intent before any design). Writes the PRD body.
- **product-designer** (optional, only if UI surface non-trivial) — sketches user-flow, surfaces UX-shape constraints that affect acceptance criteria. Skipped for backend/CLI/API-only work.

product-manager invokes `superpowers:brainstorming` skill before drafting the PRD; explicit gate from canonical: "Do NOT invoke any implementation skill, write any code, scaffold any project, or take any implementation action until you have presented a design and the user has approved it."

## Quality Gates

- Problem statement names a specific user with specific pain (rejected: "users want better tools")
- Each user story has at least 2 acceptance criteria; each criterion is testable (mechanical or named-reviewer verdict)
- Non-goals section is non-empty (forces explicit scope cuts)
- Story breakdown contains ≥3 and ≤7 stories; each ≤1 engineer-week (rejected: single mega-story)
- User has signed off on the PRD before the arc closes (do NOT auto-graduate to spec-to-design)

## Output Format

- `docs/prd/YYYY-MM-DD-<slug>.md` — the PRD itself
- One-line entry appended to `docs/prd/_index.md` if it exists
- Story breakdown duplicated into `BACKLOG.md` at repo root if user requests

## Iteration Discipline

After PRD signed off, run:

```bash
python3 .agent/tools/memory_reflect.py "product-manager" \
  "PRD signed off" \
  "<slug>: PRD v<N> approved — <n_stories> stories, <n_acceptance_criteria> AC total" \
  --importance 8 --pain 5 \
  --note "DURABLE LESSON: <one sentence — what about this scope/decomposition transfers to future PRDs?> | KEY DECISIONS: <what was scoped out + why> | RISKS LOGGED: <what we explicitly don't know yet>"
```

importance 8 × pain 5 = 40 → cluster canonical, surfaces in dream cycle. Pairs with engagement-blank substrate (Phase K) so PRD lessons accumulate per project.

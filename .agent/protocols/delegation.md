# Delegation Protocol

Rules for when and how to hand work off to a sub-agent.

## When to delegate
- The task has >3 independent sub-tasks that can run in parallel.
- The task requires loading >20k tokens of context the parent doesn't need.
- The task needs a different permissions envelope (e.g., sandboxed research).

## When NOT to delegate
- The task is a single decision or a short sequence of tool calls.
- The context needed by the sub-agent overlaps heavily with the parent's.
- The sub-agent would need to write to memory that the parent is actively editing.

## Handoff contract
Every delegation includes:
1. **Goal** — what success looks like, in one sentence.
2. **Constraints** — what the sub-agent must not do (inherits parent permissions by default).
3. **Return format** — structured output the parent can consume.
4. **Budget** — max tokens, max tool calls, max wall time.

## Memory isolation
- Sub-agents read shared semantic + personal memory.
- Sub-agents write to their own `memory/episodic/` namespace.
- On return, the parent decides which sub-agent learnings to merge.

## Anti-patterns
- "Fan out 10 sub-agents and hope" — each delegation costs context setup.
- Sub-agents that modify the parent's `working/WORKSPACE.md` directly.
- Recursive delegation without a depth limit (hard-cap at 3 levels).

## PDLC → SDLC handoff pipeline

The five subagents in `.claude/agents/` form a sequential pipeline. Each stage
produces artifacts the next stage consumes. No stage skips; any stage can
escalate back when the input is unbuildable.

```
ROOT → product-manager
    Input:    user's free-form feature / product request
    Skills:   product-discovery, requirements-writer, story-decomposer
    Output:   validated problem doc + PRD with acceptance criteria + story list in BACKLOG
    Handoff:  architect (when PRD marked "ready for design")
              OR back to ROOT (when discovery shows the premise is wrong)

product-manager → architect
    Input:    PRD path + references to PRODUCT_CONTEXT + DOMAIN_KNOWLEDGE
    Skills:   spec-reviewer (gate), architect
    Output:   ADR in DECISIONS.md + architecture doc (component diagram, data flow,
              edge-case matrix, test-seam list, assumption ledger)
    Handoff:  engineer (when ADR marked "ready for impl")
              OR back to product-manager (on spec-reviewer verdict: SEND BACK)

architect → engineer
    Input:    ADR id + architecture doc path + PRD path
    Skills:   planner, implementer, test-writer, git-proxy
    Output:   branch with atomic TDD commits + all tests green
    Handoff:  reviewer (when branch pushed)
              OR back to architect (on design gap)
              OR back to debug-investigator (on 3+ same-hypothesis failures)

engineer → reviewer
    Input:    branch name + PR URL + linked ADR + PRD
    Skills:   code-reviewer, debug-investigator
    Output:   verdict (APPROVED / APPROVED WITH FOLLOWUPS / BLOCKED) + cited findings
              at confidence ≥ 80 + systemic-pattern graduation candidates
    Handoff:  release-manager (on APPROVED)
              OR back to engineer (on BLOCKED or APPROVED WITH FOLLOWUPS)

reviewer → release-manager
    Input:    approved PR + linked ADR + PRD
    Skills:   deploy-checklist, release-notes, git-proxy
    Output:   merged PR + deployed artifact + release notes + version bump +
              CHANGELOG entry + release log in DECISIONS.md
    Handoff:  ROOT (with deploy summary + any follow-up items)
              OR back to engineer (on deploy failure after rollback)
```

## Hard rules for the PDLC → SDLC pipeline

1. **Every handoff is logged.** Each subagent calls `memory_reflect.py <name> "<stage>" "<outcome>"` at handoff boundaries. Pain score reflects handoff quality — smooth handoffs score low, escalations score high.
2. **No stage skips.** engineer cannot start without an ADR; release-manager cannot ship without reviewer APPROVED. Skipping breaks the audit trail and the `show.py` sparkline stops being meaningful.
3. **Escalation back is not failure.** If a stage receives an unbuildable input, surface it and route back — this is *data*, not a defect. The escalation itself logs with a higher pain score so the dream cycle can graduate patterns (e.g. "architect repeatedly sends back PM specs that miss X").
4. **No recursive delegation.** A subagent does NOT dispatch another subagent. Subagents return to the root agent, which decides the next dispatch. This keeps the pipeline legible and prevents fan-out blowup.
5. **Pipeline depth ≤ 3.** Root → subagent → (optional) skill invocation. Subagents never dispatch subagents.
6. **Every subagent starts with `show.py`.** First action in every subagent's `## Context you read on start`. Gives 14d activity, pending candidates, failing skills — situational awareness is non-optional.

## Which subagent owns what (quick reference)

| Subagent | Skills it uses | Dispatched by | Writes to |
|---|---|---|---|
| `product-manager` | product-discovery, requirements-writer, story-decomposer | ROOT | `working/WORKSPACE.md`, `BACKLOG.md`, `docs/discovery/`, `docs/specs/` |
| `architect` | spec-reviewer, architect | product-manager (via ROOT) | `semantic/DECISIONS.md`, `docs/architecture/`, `working/WORKSPACE.md` |
| `engineer` | planner, implementer, test-writer, git-proxy | architect (via ROOT) | code files, `episodic/AGENT_LEARNINGS.jsonl`, `working/WORKSPACE.md` |
| `reviewer` | code-reviewer, debug-investigator | engineer (via ROOT) | PR comments, `docs/reviews/`, `episodic/` |
| `release-manager` | deploy-checklist, release-notes, git-proxy | reviewer (via ROOT) | `CHANGELOG.md`, `docs/releases/`, `semantic/DECISIONS.md`, version file |
| `product-designer` | (none — produces design pack) | product-manager (via ROOT) when UI surface non-trivial | `output/design/<slug>/wireframes.md`, `flow.md`, `design-decisions.md`, `acceptance.md` |
| `frontend-engineer` | planner, implementer, test-writer, git-proxy | architect (via ROOT) — parallel sibling to backend-engineer | UI files, `episodic/`, `working/WORKSPACE.md` |
| `backend-engineer` | planner, implementer, test-writer, git-proxy, data-layer | architect (via ROOT) — parallel sibling to frontend-engineer | server files, migrations, `episodic/`, `working/WORKSPACE.md` |
| `prototype-engineer` | (skips planner/test-writer for spike speed) | ROOT directly when prototype-app workflow fires | `output/prototypes/<slug>/`, `HYPOTHESIS.md`, `LEARNINGS.md` |
| `integration-engineer` | planner, implementer, test-writer, git-proxy | frontend+backend completion (via ROOT) | integration test files, `output/integration/<slug>-integration-report.md` |
| `qa-runner` | (none — executes existing artefacts) | integration-engineer OR engineer (via ROOT) | `output/qa/<slug>-runtime-report.md`, `output/qa/<slug>/evidence/` |
| `security-reviewer` | (none — adversarial review) | qa-runner (via ROOT) — parallel sibling to perf + type-design + general reviewer | `output/review/security-review.md` |
| `performance-reviewer` | (none — adversarial review) | qa-runner (via ROOT) — parallel sibling | `output/review/performance-review.md` |
| `type-design-reviewer` | (none — adversarial review) | qa-runner (via ROOT) — parallel sibling | `output/review/type-design-review.md` |

## Prototype-app pipeline (workflow: prototype-app.md)

For "build a working prototype app" — two valid shapes:

### Spike mode (fastest)

```
ROOT → prototype-engineer
    Input:    user hypothesis + time-box
    Skills:   none (skips planner/test-writer/etc by design)
    Output:   working code + HYPOTHESIS.md + LEARNINGS.md + demo command
    Handoff:  ROOT directly (with PASS/FAIL/INCONCLUSIVE on hypothesis)
              OR (optional) demo-prep skill to package for showcase
```

### Lite-PDLC mode (more rigorous, salvageable for production)

```
ROOT → product-manager
    Output:   light PRD

product-manager → product-designer (only if UI surface)
    Output:   wireframes + design-decisions + acceptance

product-designer → architect (or product-manager → architect if no UI)
    Output:   light ADR (focuses on prototype-survivable choices)

architect → frontend-engineer || backend-engineer (parallel)
    Output:   branches with TDD commits

frontend-engineer + backend-engineer → integration-engineer
    Output:   integration tests + cross-boundary report

integration-engineer → qa-runner
    Output:   runtime report (PASS / APPROVED-WITH-FIXES / BLOCKED)

qa-runner → reviewer (general only — skip security/perf/type-design panel)
    Output:   APPROVED / APPROVED-WITH-FIXES

reviewer → demo-prep skill (single agent + skill)
    Output:   output/demo/<slug>/ package
```

`release-manager` is intentionally NOT in the prototype workflow.
Prototypes don't ship through release-manager. If the prototype graduates
to production, re-run the full PDLC → SDLC pipeline against the validated
PRD. Rebuild the code under full discipline; the prototype's value was
the LEARNINGS, not the code.

## Production-feature pipeline (parallel-engineer + reviewer-panel)

When a feature has both UI and API surface and warrants production-grade
rigor, the pipeline fans out at engineer + at reviewer:

```
ROOT → product-manager → product-designer → architect
    (sequential — design before parallel build)

architect → frontend-engineer || backend-engineer (parallel)

frontend-engineer + backend-engineer → integration-engineer
    (sequential — wires the two sides + writes integration tests)

integration-engineer → qa-runner
    (runtime smoke before review)

qa-runner → reviewer-panel (parallel: general + security + performance + type-design)
    (4 lenses, each independent verdict)

reviewer-panel → release-manager
    (when ALL 4 verdicts are APPROVED or APPROVED-WITH-FIXES with no BLOCKERs)
```

Specialist reviewers fire only when their lens applies:
- security-reviewer: any new auth surface, secrets, deps, queries, file ops
- performance-reviewer: any hot-path code, new queries, new deps with bundle impact
- type-design-reviewer: any new type definitions or significant type changes
- general reviewer: always

Skip a specialist when its lens has no signal — overhead > value otherwise.

---
name: team-builder
version: 2026-05-02
description: Use proactively when the user wants to assemble a new agent team for a deliverable that doesn't fit an existing workflow. Walks them through goal elicitation → roster selection → dispatch shape → quality gates → writes a new workflow contract at `.agent/workflows/<slug>.md`. Triggers on "build a team", "assemble a team", "stand up a team", "design a workflow", "new workflow", "team for <deliverable>". Skill produces the contract; the contract orchestrates the agents.
triggers: ["build a team", "build agent team", "assemble a team", "stand up a team", "design a workflow", "new workflow", "team for", "team-builder"]
tools: [bash, memory_reflect]
preconditions: ["adapters/{claude-code,bcg}/agents/ exist with non-empty roster", ".agent/workflows/ exists"]
constraints:
  - never silently fabricate an agent name — must come from existing roster
  - workflow file goes to .agent/workflows/<slug>.md, never elsewhere
  - team_structure must be one of: flat | coordinated | full
  - quality gates must be testable (mechanical assertion or named reviewer verdict), never vague aspiration
  - write the workflow file ONLY after user signs off on the spec
category: meta-orchestration
---

# Team Builder — assemble an agent team into a workflow contract

Goal: turn a goal-shaped request ("we need a team to ship X") into an
explicit `.agent/workflows/<slug>.md` contract that names WHO fires
WHEN, the dispatch shape, the deliverable artefact, and the quality
gates. Skill does NOT execute the team — it authors the contract that
future sessions execute. Per memory `workflows-over-skills`, multi-
agent orchestration belongs in workflow files, not implicit skill-
chains.

## When this fires

- User says: "build a team for <X>", "assemble a team", "stand up a
  team", "design a workflow for <Y>", "we need agents to <Z>"
- User has a goal but no existing workflow file at
  `.agent/workflows/<slug>.md` matches it
- User explicitly invokes `team-builder` or asks to create a new
  workflow

Do NOT fire when:
- An existing workflow at `.agent/workflows/<slug>.md` already covers
  the goal — point the user there
- The task is single-skill (one agent, one phase) — author the skill,
  not a workflow
- The user wants to MODIFY an existing workflow — that's a direct
  edit, not team-builder

## Phases (sequential — do not skip)

### Phase 1 — Goal elicitation

Pin down the deliverable. Without a deliverable shape, agent
selection is guessing.

Ask:
1. **What's the named output?** (deck, code feature, audit report,
   research brief, deployment, …) — must be one concrete artefact,
   not "improve X"
2. **Who's the audience?** (C-suite, internal team, downstream agent,
   open-source community, …)
3. **What does done look like?** (one-paragraph success criterion;
   if user can't write it, the goal isn't ready for a team yet —
   stop and surface that)
4. **What's out of scope?** (forces explicit boundaries — items here
   should NOT show up in the workflow's Quality Gates)

Write the answers to a scratch buffer. Do not proceed to Phase 2
until all four are filled.

### Phase 2 — Roster scan + select

Read the agent rosters:

```bash
ls adapters/claude-code/agents/  # SDLC roster (5 agents typical)
ls adapters/bcg/agents/          # BCG consulting roster (16 agents typical)
```

For each candidate, read the agent's frontmatter (name, role) and
match against the goal. Select the SMALLEST set that covers the
deliverable. Common shapes:

| Goal shape | Typical roster |
|-----------|----------------|
| Code feature | architect + engineer (or frontend-engineer + backend-engineer) + reviewer + qa-runner |
| Consulting deck | framework-lead + case-analyst (×N parallel) + deck-builder + 3-reviewer panel |
| Code prototype | prototype-engineer + qa-runner |
| Research brief | document-researcher + analyst + framework-lead |
| Audit report | analyst + 1-2 reviewer-flavor agents |
| Engagement onboarding | client-onboarding skill + delivery-lead + program-manager |

Reject:
- Adding a 6th agent "for completeness" when 4 cover the deliverable
- Inventing a role not in the roster (route back to Phase 1 and ask
  if the deliverable shape needs a new agent — then propose via
  `propose_harness_fix.py`, do NOT silently invent)

### Phase 3 — Dispatch shape decision

Per memory `workflows-over-skills`, declare `team_structure`:

| Shape | When | Pattern |
|-------|------|---------|
| **flat** | All agents work in parallel, no orchestrator | 2-3 agents, independent work, integration-engineer wires at the end |
| **coordinated** | One orchestrator (framework-lead / program-manager) coordinates fan-out | 4-8 agents, parallel sub-teams, named lead does NOT draft content |
| **full** | Orchestrator + sub-leads + workers + review panel | 8+ agents, multi-phase, distinct review lens (per consulting-deck-builder) |

For the smallest viable team that covers the deliverable, **flat** is
the default. Only escalate to coordinated when 5+ agents need
sequencing, and to full when a review panel is non-trivial (≥3
reviewers with distinct lenses).

### Phase 4 — Quality gates

Draft 4-8 gates. Each gate must be:
- **Testable** — a mechanical assertion (file exists, line count,
  regex match) OR a named reviewer's verdict
- **Specific** — bare "looks good" or "high quality" rejected;
  every gate names what it checks

Reject vague aspirations:
- ❌ "Code is clean and well-tested" → ✅ "All tests pass; reviewer
  agent returned no critical findings"
- ❌ "Deck is compelling" → ✅ "Cover states proposed action in
  one action-voice sentence; partner-strategy reviewer returned
  no critical findings"

Pull from sibling workflow files for inspiration — read 2-3 that
match the goal shape, copy gate patterns that fit, prune those that
don't.

### Phase 5 — Write the contract

Write `.agent/workflows/<slug>.md` with this frontmatter:

```yaml
---
workflow_id: <slug>
name: <Human-readable Workflow Name>
team_structure: <flat | coordinated | full>
description: <one paragraph — what this produces and when to fire>
---
```

Body sections (mirror existing workflow structure):
1. **Purpose** — what the workflow produces; trigger phrases that
   should fire it
2. **Contents** — what the deliverable contains (sections, slide
   counts, code modules, …)
3. **Team Structure** — agents named explicitly, dispatch shape,
   parallelism, roles
4. **Quality Gates** — bulleted, each gate testable
5. **Output Format** — file paths the workflow writes
6. **Iteration Discipline** — `memory_reflect` call at workflow exit

Slug convention: `<deliverable>-<modifier>` (e.g.,
`prototype-app`, `final-recommendations-deck`,
`incident-postmortem`, `quarterly-review`). Lowercase, hyphenated, no
spaces.

After writing the file, surface the path to the user and stop. Do
NOT execute the workflow in the same turn — the user reviews + may
iterate before first execution.

## Output

- New file at `.agent/workflows/<slug>.md`
- Append slug to `.agent/workflows/_index.md` (one-line description
  matching workflow `description` field)
- Stdout summary: workflow path + named team + dispatch shape

## Phase-exit reflection (MANDATORY)

After workflow file written, run:

```bash
python3 .agent/tools/memory_reflect.py "team-builder" \
  "workflow contract authored" \
  "<slug>: team_structure=<shape>, agents=<n>, gates=<n>" \
  --importance 7 --pain 4 \
  --note "DURABLE LESSON: <one sentence — what about this team selection transferred to future workflows? E.g. 'when deliverable is 5+ slides, coordinated > flat to prevent integration drift.'> | DELIVERABLE SHAPE: <named-output>; AUDIENCE: <audience> | TRADE-OFFS: <which agents we ALMOST included but pruned and why>"
```

Importance 7 × pain 4 = 28 → salience 2.8. Won't auto-graduate alone
but dominates its cluster against any file-write noise from authoring
the workflow file. When several workflows authored across sessions,
recurrence saturation lifts the cluster toward the 7.0 graduation
threshold so team-design heuristics promote naturally.

## Examples

**Good run (deliverable = code feature):**

User: "Build a team to ship the new auth flow"

Phase 1 elicitation:
- Output: working OAuth2 login with Google + GitHub providers
- Audience: end-users + future maintainers
- Done: tests green, security-reviewer no critical findings, deployed to staging
- Out of scope: enterprise SSO (separate quarter)

Phase 2: architect (PRD→ADR), backend-engineer (auth service), frontend-engineer (login UI), security-reviewer, qa-runner. 5 agents.

Phase 3: `flat` is wrong (security review must follow implementation). `coordinated` — architect leads, FE+BE parallel, then security-reviewer + qa-runner gate.

Phase 4 gates:
- ADR exists at `docs/adr/`
- Backend auth tests green (`pytest tests/auth/`)
- Frontend login flow renders without console errors (qa-runner)
- security-reviewer: no critical findings
- Deployed to staging URL accessible

Phase 5: `.agent/workflows/oauth-login-feature.md` written. team-builder stops.

**Bad run:**

User: "Make our codebase better"

Phase 1: deliverable not concrete → STOP. "What's the named output?" — user can't answer. Skill surfaces: "this isn't ready for a team yet; refine the goal first." No workflow written.

## Self-rewrite hook

After every 3 workflows produced, or any workflow that's executed
and fails its own gates, read the last 5 team-builder episodes from
episodic memory + the resulting workflow files. If selection
heuristics (which agents pair well, which gates catch real defects,
which dispatch shapes scale) have evolved, update Phase 2/3/4
guidance. Commit: `skill-update: team-builder, <one-line reason>`.

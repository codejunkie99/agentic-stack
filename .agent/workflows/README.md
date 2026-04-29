# Workflows

Generic, shareable workflow definitions. A workflow is a canonical pattern
for producing a named deliverable — it declares the deliverable's contents,
the team composition (which agents/skills collaborate), review lenses,
quality gates, and output format.

Distinct from `.agent/skills/`: skills are reusable capabilities (analyze,
review, assemble); workflows compose skills + agents into a deliverable
recipe (situation-assessment, mid-case-findings-deck, …).

## Current set

Bootstrapped in Step 8.1 from Kenneth Leung's `harness-starter-kit` (BCG).
Each file has frontmatter with `workflow_id`, `name`, `team_structure`,
and `description`. The `sample-` prefix from the source was dropped —
in this repo these are canonical patterns, not samples.

| Workflow | Purpose |
|---|---|
| `situation-assessment.md` | Initial structured client-context + hypothesis + approach doc |
| `issue-tree-hypothesis.md` | MECE decomposition of the case question with supporting hypotheses |
| `mid-case-findings-deck.md` | Mid-engagement synthesis and insight surfacing |
| `final-recommendations-deck.md` | Culminating deliverable — recommendations + value + roadmap |
| `post-meeting-update.md` | Transcript → updates to tracker / RAID / workstream pages |
| `daily-task-tracking.md` | Daily transcript → Jira task pipeline with QA gates |

## team_structure shapes

- **`flat`** — small team, no internal coordination layer:
  framework-lead + 1-2 workers + 1 reviewer. Fan-out is shallow;
  reviewer runs after workers complete.
- **`coordinated`** — multi-worker with internal coherence pass:
  framework-lead leads + 3 named workers (typically case-analyst +
  deck-builder + delivery-lead) + 3 parallel reviewers
  (partner-strategy, partner-analytics, principal-delivery). Lead
  runs internal review before partner-level escalation.
- **`full`** — engagement-scale with N case-analysts (one per
  workstream): framework-lead + case-analyst (×N) + deck-builder +
  delivery-lead + 3 parallel reviewers. Used for final deliverables
  spanning the entire engagement.

## Why this exists

Per Anthropic's official Claude Code subagent docs (2026), auto-
delegation is driven by each subagent's `description:` field as a
trigger phrase. Workflow files are the structural overlay above
individual subagent descriptions: they declare WHICH agents to
dispatch together for a specific deliverable, in what shape, with
what review pattern. Without this layer, the orchestrator has no
table-of-contents for deliverable-shaped work — and defaults to
single-agent execution. With this layer, the orchestrator looks up
the deliverable, reads the workflow, and dispatches the team.

## Status

As of Step 8.3 (2026-04-29), every role reference in every workflow
resolves to a real agent in either `adapters/claude-code/agents/`
(SDLC roster, always installed) or `adapters/bcg/agents/` (BCG
consulting roster, installed only when `.agent/config.json` has
`bcg_adapter: "enabled"`).

The reconciliation evolved across two steps:

**Step 8.2.2 (initial hybrid reconciliation):**
- Three reviewer-lens roles were authored as new BCG agents:
  `partner-strategy`, `partner-analytics`, `principal-delivery`.
- Six worker-role orphan labels were relabeled to canonical roster
  names: `framework-lead`, `case-analyst`, `transcript-analyst`,
  `jira-tracker-analyst` → `analyst`; `delivery-lead` → `program-manager`;
  `io-qa-auditor` → `test-lead`.

**Step 8.3 (2026-04-29 supersession for the deck/case-team workflows):**
The Step 8.2.2 relabeling for `framework-lead`, `case-analyst`,
`delivery-lead`, and `deck-builder` was reversed. Per Anthropic's
official Claude Code subagent docs, **auto-dispatch is driven by
the agent's `description:` field as a trigger phrase** — and
task-specific names like `framework-lead` (vs generic `analyst`)
trigger more reliably because the description can name the task
directly. The four kit-originated worker roles for the case-team
deck workflows were authored as proper BCG agents with reporting
hierarchies. `transcript-analyst`, `jira-tracker-analyst`, and
`io-qa-auditor` retain their relabeling — those are smaller-scale
specialisations not warranted by their use frequency.

See `adapters/bcg/README.md` for the full BCG agent roster and
`.agent/memory/semantic/DECISIONS.md` for the per-step rationale.

## Conventions

- Filenames use kebab-case. The `workflow_id` in frontmatter matches the
  filename stem.
- `team_structure` is one of: `flat`, `coordinated`, `full`.
- Workflow definitions are read-only contracts; instantiating a workflow
  for a specific engagement produces artifacts under
  `.agent/memory/working/` or `context/project/`, not here.

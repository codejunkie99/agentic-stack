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

## Status

Several workflow definitions reference agent roles (e.g. `framework-lead`,
`case-analyst`, `partner-strategy`, `transcript-analyst`, `io-qa-auditor`)
that do not yet exist in `adapters/claude-code/agents/`. Wiring those
agents and/or renaming role references is scheduled for Step 8.2
(agent-tuning).

## Conventions

- Filenames use kebab-case. The `workflow_id` in frontmatter matches the
  filename stem.
- `team_structure` is one of: `flat`, `coordinated`, `full`.
- Workflow definitions are read-only contracts; instantiating a workflow
  for a specific engagement produces artifacts under
  `.agent/memory/working/` or `context/project/`, not here.

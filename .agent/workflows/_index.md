# Workflows — Index

> Eager-loaded at session start (this file only). Individual workflow
> files load on-demand when their matching deliverable surfaces.

A workflow declares the team for a named deliverable: which agents
collaborate, which review lenses apply, what quality gates to pass.
Frontmatter exposes `team_structure` so the dispatching agent knows
fan-out shape before reading the body.

| Workflow | Deliverable | team_structure | Triggers on |
|---|---|---|---|
| `situation-assessment.md` | Initial structured client-context + hypothesis + approach doc | `flat` | "situation assessment", "client context doc", "engagement framing" |
| `issue-tree-hypothesis.md` | MECE decomposition + hypothesis network | `flat` | "issue tree", "MECE decomposition", "hypothesis network" |
| `mid-case-findings-deck.md` | Mid-engagement synthesis deck | `coordinated` | "mid-case findings", "interim deck", "steerco update" |
| `final-recommendations-deck.md` | Final recommendations + value + roadmap | `full` | "final recommendations", "closeout deck", "final deliverable" |
| `proposal-deck.md` | External-facing proposal deck (sells topic + offering to target client) | `coordinated` | "build the proposal", "[topic] pitch deck", "proposal for [client]", "iterate on the proposal storyboard" |
| `post-meeting-update.md` | Transcript → tracker / RAID / workstream updates | `flat` | "post-meeting update", "process this transcript" |
| `daily-task-tracking.md` | Daily transcript → Jira task pipeline | `flat` | "daily task pipeline", "extract tasks from transcript" |

## How to load

When a triggering deliverable surfaces: read the workflow file →
frontmatter declares `team_structure` and the body names agents →
dispatch named subagents via the Agent tool, **in parallel where
declared**. Synthesise results; do NOT draft content in the
orchestrator session when a team is declared. See `README.md` for
team_structure shape details and the rationale for this layer.

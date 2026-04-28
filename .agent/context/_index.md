# Generic Consulting Context — Index

> Eager-loaded at session start (this file only). Individual context
> files load on-demand when their domain surfaces in the task. Same
> progressive-disclosure pattern as `.agent/skills/_index.md`.

## What's available here

| File | What's in it | Load on-trigger |
|---|---|---|
| `glossary.md` | Consulting terminology — case team roles (MDP, Principal, Project Lead, Consultant, Associate), engagement vocabulary (RFP, ToR, SOW, deliverable, baseline, endline), analytical terms (driver tree, sensitivity, cohort) | terminology question · acronym usage · onboarding a new role |
| `frameworks.md` | Issue Tree · Pyramid Principle · MECE · 7-S · Value Chain · Driver Tree · Sensitivity Analysis · Market Sizing · Pricing Taxonomy | analytical task · structuring a problem · "is this MECE" check · sizing exercise |
| `quality-standards.md` | So-what-first · MECE discipline · evidenced claims · sensitivity transparency · action-voice titles | producing any deliverable · pre-review check · "is this ready" question |

## How to load

When a triggering domain surfaces, read the specific file via `Read`.
Do not bulk-read; the budget for eager session-start is small and
these files are reference material, not always-needed.

## Why this is here

Originally these three files were eager-loaded at every session
start (Step 8.2.4 reclassification). The harness conformance audit
(2026-04-28) flagged the eager-load total at 839/500 lines —
generic context contributed 201 lines of always-eager bloat. Same
progressive-disclosure violation we fix on installed projects.
Converted to trigger-load via this index per the audit's slice-3
remediation. See `DECISIONS.md` 2026-04-28 entry for the full
rationale.

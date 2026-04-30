---
name: draft-status-update
version: 2026-04-24
bootstrapped_from: "harness-starter-kit (Kenneth Leung, BCG) — 2026-04-24 import, Step 8.2.3"
description: Use to draft a weekly status update from the action item tracker, RAID log, and workstream pages. Produces a draft for human edit before publish — never auto-publishes. Section order and content follow the formatting conventions in the active firm adapter (e.g. adapters/bcg/protocols/formatting.md). Trigger on weekly-status handoff, not on one-off update requests.
triggers: ["draft weekly status", "draft status update", "this week's update", "weekly status draft", "pull a status update"]
tools: [bash]
preconditions: ["action item tracker exists", "RAID log exists"]
constraints:
  - never publish directly — present draft for human review first
  - executive summary partner-readable in 30 seconds
  - lead with wins, then risks and blockers
  - be specific — names, dates, numbers, not vague statements
category: knowledge-work
---

# Draft Status Update

Generate a draft weekly status update by reading the action tracker, RAID log, and workstream pages. Returns the draft for review — does NOT publish to Confluence.

## Steps
1. Read the action item tracker, RAID log, and all workstream pages
2. Identify items completed, added, or changed status this week
3. Generate the status update following the weekly status format:
   - Executive Summary
   - Workstream Progress
   - Key Decisions This Week
   - New/Updated Risks
   - Action Items Completed
   - Action Items Overdue
   - Next Week Focus
4. Present the draft to the user for edits before publishing

## Guidelines
- The executive summary should be partner-readable in 30 seconds
- Lead with wins, then flag risks and blockers immediately after
- Be specific: names, dates, numbers — not vague statements

## Self-rewrite hook

After every 5 status drafts produced, or the first time a partner /
MDP pushes back on the draft format (section ordering, executive-
summary length, risk framing, win-vs-risk balance), read the last 5
draft-status-update entries from episodic memory. If better section
structures, win-vs-risk heuristics, or specificity rules have
emerged, update this file. Commit:
`skill-update: draft-status-update, <one-line reason>`.

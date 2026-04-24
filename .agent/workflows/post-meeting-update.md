---
workflow_id: post-meeting-update
name: Post-Meeting Document Update
team_structure: flat
description: Process meeting transcript and update all relevant case documents — action item tracker, RAID log, workstream pages
---

## Purpose

After every significant meeting (Steering Committee, workstream check-in, client workshop), ensure that all case documentation reflects the latest decisions, action items, risks, and progress updates. This is the "single source of truth" update workflow.

## Trigger

- A meeting transcript exists in `context/projects/{project}/transcripts/` or on Confluence
- A spec file is created in `specs/{project}/post-meeting-update-{date}.md` referencing the transcript

## Contents (Outputs)

1. **Structured Extraction** — Parsed meeting notes with: attendees, decisions, action items, risks, open questions, summary
2. **Updated Action Item Tracker** — New rows appended, existing statuses updated, deadline changes reflected
3. **Updated RAID Log** — New risks/issues/decisions logged, existing entries updated
4. **Updated Workstream Pages** — Recent findings and status changes added to relevant workstreams
5. **Change Summary** — Log of all modifications made, flagged follow-ups

## Team Structure: Flat

Orchestrator spawns two agents sequentially:

1. **meeting-notes-processor** — Parse raw transcript into structured extraction
   - Identify explicit and implicit action items, decisions, risks
   - Cross-reference against existing tracker to avoid duplicates
   - Flag ambiguities as `[NEEDS CLARIFICATION]`
   - Present extraction for user review before proceeding

2. **post-meeting-updater** — Fan out confirmed extraction to target documents
   - Read each target page before updating
   - Append new rows to trackers (never overwrite)
   - Update statuses of existing items in place
   - Add recent updates to workstream pages
   - Produce change summary on completion

## Review

No formal review panel — user confirms the extraction before updates are applied. The meeting-notes-processor presents a preview, and user approval gates the post-meeting-updater.

## Output Format

- Extraction: structured markdown with tables matching tracker/RAID schemas
- Document updates: in-place modifications to existing markdown files or Confluence pages
- Change summary: bulleted list of all modifications with page references

## Quality Gates

- Every action item has an owner (or flagged "Unassigned") and a deadline (or "TBD")
- Every decision has a D-### ID and owner
- No existing content is deleted — only appended or status-updated
- All ID sequences are correctly incremented (AI-###, R-###, D-###, etc.)
- Ambiguous items are flagged, not silently resolved
- User confirms extraction before any writes execute

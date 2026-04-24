# Daily Task Tracking Workflow {#daily-task-tracking-workflow local-id="bedf67e6a909"}

## Purpose {#purpose local-id="be21fa97bb92"}

This workflow converts daily meeting transcripts into structured, auditable tasks and logs them into **Jira**, with QA validation to ensure outputs faithfully match inputs at each handoff.

## What It Contains {#what-it-contains local-id="e892d8a36e52"}

-   Daily transcript intake (current-day transcripts from specified folders)

-   Task extraction (name, description, due date, owner, app name, transcript association)

-   Jira update (creating/updating Jira issues for extracted tasks)

-   QA validation of Transcript → Tasks and Tasks → Jira alignment

## Team Composition {#team-composition local-id="ee26210cd4f1"}

  ------------------------------------- ------------------------ ---------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------
  Role                                  Agent                    Skill      Responsibility
  Transcript Intake & Task Extraction   `analyst`     analysis   Selects current-day transcript(s) and extracts tasks (primary), plus risks/context (secondary), producing the structured task dataset with evidence traceability
  QA Validator                          `test-lead`          review     Validates that the extracted task dataset is supported by transcript evidence (no hallucinations, no missing evidence, coverage aligns with transcript action items)
  Jira Update                           `analyst`   writing    Ingests the extracted task dataset, normalizes for Jira readiness (without inventing values), deduplicates, and creates/updates Jira issues for the tasks
  QA Validator                          `test-lead`          review     Validates that the Jira update faithfully reflects the extracted task dataset (no drops without reason, no invented fields, correct identity/dedup behavior)
  ------------------------------------- ------------------------ ---------- ----------------------------------------------------------------------------------------------------------------------------------------------------------------------

## Key Constraints for Agents {#key-constraints-for-agents local-id="924cc699d5bb"}

-   Current-day transcript selection is mandatory; fallback to the latest-modified transcript only if no current-day transcript exists

-   Task extraction must preserve evidence traceability (transcript path + anchor + excerpt) for every task

-   No hallucinated owners, due dates, or app names at any stage; unknowns must be explicitly marked (`Unassigned`, `Unknown`, `null`)

-   Jira updates must not rewrite history unless explicitly instructed (e.g., avoid closing/reopening old issues without direction)

-   Every extracted task must appear in Jira or be explicitly marked as skipped with a reason

-   QA verdicts are gating: critical mismatches must be surfaced for correction rather than silently accepted

## Team Structure {#team-structure local-id="b9d19fb37e28"}

`team_structure: flat_structure`

This workflow uses sequential collaboration with QA gates to prevent drift between transcript reality, extracted tasks, and Jira records.

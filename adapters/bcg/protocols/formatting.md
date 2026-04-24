---
description: Standard formatting conventions for all case team documents
globs: "*"
---

# Formatting Standards

## Action Item Tracker Schema
| Column | Description |
|---|---|
| ID | Auto-incremented, format: `AI-###` |
| Description | Clear, specific task statement |
| Owner | Full name from team roster |
| Workstream | Which workstream this belongs to |
| Deadline | YYYY-MM-DD or "TBD" |
| Status | One of the allowed statuses below |
| Date Added | YYYY-MM-DD |
| Source | Meeting date or context where this originated |

## RAID Log Schema
| Column | Description |
|---|---|
| ID | Format: `R-###`, `A-###`, `I-###`, `D-###` by type |
| Type | Risk, Action, Issue, or Decision |
| Description | Clear statement of the item |
| Owner | Full name from team roster |
| Status | One of the allowed statuses below |
| Impact | High, Medium, or Low |
| Date Raised | YYYY-MM-DD |

## Status Values (Fixed Enum)
- **Not Started** — Work has not begun
- **In Progress** — Actively being worked on
- **Complete** — Done and verified
- **Blocked** — Cannot proceed, dependency or issue
- **Closed** — No longer relevant or superseded

## Weekly Status Update Sections
1. Executive Summary (3-5 sentences max)
2. Workstream Progress (one bullet per workstream)
3. Key Decisions This Week
4. New/Updated Risks
5. Action Items Completed
6. Action Items Overdue
7. Next Week Focus

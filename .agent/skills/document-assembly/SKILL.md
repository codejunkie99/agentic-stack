---
name: document-assembly
version: 2026-04-24
bootstrapped_from: "harness-starter-kit (Kenneth Leung, BCG) — 2026-04-24 import, Step 8.1"
description: Use to assemble a final deliverable from per-section drafts — verifies all expected sections, applies canonical order, checks cross-section coherence, generates ToC and metadata, flags placeholders. Mechanical assembly only — does not add new content. Trigger on hand-off from multiple section drafts to a single final document.
triggers: ["assemble document", "compile the deck", "merge section drafts", "final deliverable assembly", "put it all together"]
tools: [bash]
preconditions: ["section drafts exist"]
constraints:
  - assembly is mechanical — never invent new content
  - flag gaps as [PLACEHOLDER: <what is needed>]
  - track source drafts in a trailing comment block
  - respect workflow-defined section dependencies (exec summary last)
category: knowledge-work
---

# Document Assembly Skill

Use this skill to assemble final deliverables from section drafts.

## Assembly Protocol

### Step 1: Collect
Gather all section drafts:
- Verify all expected sections are present
- Check each draft is in the correct output format
- Note any sections still in draft/pending status

### Step 2: Order
Apply the correct document structure:
- Reference the workflow definition for the deliverable type
- Respect dependencies (executive summary last to write, first to appear)
- Apply consistent heading hierarchy

### Step 3: Check Coherence
Before assembling:
- Cross-references between sections are accurate
- Terminology is consistent throughout
- No contradictory claims across sections
- Assumption statements are unified (not repeated or conflicting)

### Step 4: Assemble
Produce the final document:
- Generate table of contents
- Apply consistent formatting throughout
- Add document metadata (version, date, case name, status)
- Mark any [PLACEHOLDER] sections that need completion

## Output Format

```markdown
# [Document Title]
**Case:** [Case Name] | **Version:** v[N] | **Date:** [YYYY-MM-DD] | **Status:** Draft / Final

---
[Table of Contents]

---
[Content sections...]
```

## Rules
- Assembly is mechanical — do not add new content
- Flag all gaps as [PLACEHOLDER: <what is needed>]
- Track which source drafts were used in a comment block at the end

## Self-rewrite hook

After every 5 documents assembled, or the first time a
`[PLACEHOLDER]` turns into a real gap that should have been caught
earlier in the source drafts, read the last 5 document-assembly
entries from episodic memory. If better assembly templates,
source-drift detection patterns, or gap-flagging conventions have
emerged, update this file. Commit:
`skill-update: document-assembly, <one-line reason>`.

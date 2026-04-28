---
name: review
version: 2026-04-24
bootstrapped_from: "harness-starter-kit (Kenneth Leung, BCG) — 2026-04-24 import, Step 8.1"
description: Use to review case/engagement deliverables and produce a structured verdict (approved/revise/reject) with severity-graded findings (critical/warning/info). Distinct from code-reviewer — this skill reviews narrative or analytical documents, not diffs. Every finding must cite a specific location and give an actionable recommendation.
triggers: ["review this deliverable", "partner review", "verdict on", "case review", "review the deck"]
tools: [recall, bash]
preconditions: ["deliverable or draft exists"]
constraints:
  - never produce content — review and flag only
  - every finding cites a specific location (section/slide/page)
  - recommendations are actionable without clarification
  - one issue per finding entry — do not combine
category: knowledge-work
---

# Review Skill

Use this skill to review case deliverables and produce structured verdicts.

## Review Process
1. Read the full deliverable
2. Apply relevant review lens (strategy, analytics, delivery — see partner/principal agents)
3. Identify issues at three severity levels
4. Produce verdict with specific, actionable findings

## Severity Definitions
- **critical** — Blocks approval; must be fixed before next review round
- **warning** — Should be addressed; may pass if justified
- **info** — Improvement suggestion; does not block approval

## Verdict Definitions
- **approved** — No critical or warning findings; may have info items
- **revise** — Has warning findings that must be addressed
- **reject** — Has one or more critical findings; requires significant rework

## Output Format

```yaml
verdict: approved | revise | reject
findings:
  - severity: critical | warning | info
    category: <category>
    location: <section/slide/page reference>
    finding: <what is wrong — specific and evidence-based>
    recommendation: <specific fix — actionable>
overall_comment: <1-2 sentence summary of the overall assessment>
```

## Rules
- Never produce content — only review and flag
- Every finding must cite a specific location in the document
- Recommendations must be specific enough for a maker to act on without asking for clarification
- Do not combine findings — one issue = one entry

## Self-rewrite hook

After every 10 reviews produced, or the first time a critical issue
slips past review and surfaces in production / final delivery (a
false negative — the review missed something that mattered), read
the last 10 review entries from episodic memory. If better severity-
classification rubrics, finding-evidence patterns, or recommendation-
actionability standards have emerged, update this file. Commit:
`skill-update: review, <one-line reason>`.

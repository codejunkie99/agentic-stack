---
workflow_id: proposal-deck
name: Consulting Proposal Deck
team_structure: coordinated
description: External-facing proposal deck that sells a topic / offering to a target client (or generic enterprise audience). Distinct from mid-case-findings (interim synthesis) and final-recommendations (closeout): proposal positions BCG (or firm) as the right partner for work not yet engaged.
---

## Purpose
Produce a proposal deck that converts an audience from "what's this?"
to "let's engage you." Combines topic introduction, case-study proof,
methodology preview, value gap (current vs future state), an MVP
with phased scaling, and the target operating model the client needs
to absorb the change.

Trigger this workflow when the user signals a proposal-shaped task:
"build the HarnessX proposal", "draft the [topic] pitch deck",
"proposal for [client]", "agentic SDLC proposal", "let's iterate on
the proposal storyboard".

## Contents

The 8 canonical sections below are the proposal's spine. Each is
mandatory unless the user explicitly waives it for this engagement
(e.g., "we don't need the approach section because the audience
already knows the methodology"). Document waivers in the storyboard's
Decisions log.

1. **Cover + topic positioning** (1 slide — what we're proposing in
   one action-voice sentence; audience and topic named clearly)
2. **Topic introduction** (1-2 slides — what the topic is, why it
   matters now, why this audience should care; positions on the
   relevant 2026 industry curve)
3. **Case studies, anonymised** (1-3 slides — proof we've done this;
   each citation includes concrete metrics + work shape; client names
   anonymised to "Tier-1 APAC bank" / "leading APAC bank" / "global
   insurer" / etc.)
4. **Approach / methodology** (3-6 slides — OPTIONAL but typically
   included; how we'd execute, distinct from competitors; for
   HarnessX-shaped work this includes the 3-plane framework
   Governance / Harness / Delivery)
5. **From-To / current-vs-future state** (2-3 slides — measurable
   gap; each row says "from X today → to Y after, delta = Z" with
   delta quantified or directionally-quantified; never use "improved"
   without the magnitude)
6. **MVP design + phased scaling** (2-3 slides — Week-1 / Week-N /
   Week-final exit criteria, phased gates with no sliding deadlines;
   typical shape: 10w Design + 10w Pilot + 20w Scale = 40w programme)
7. **Target Operating Model** (1-2 slides — org / role /
   decision-rights shifts the client needs to absorb the change;
   From → To framing across Org structure / Roles / Skills /
   Decision rights / Workflows / Performance management)
8. **Investment + next steps** (1 slide — commercial structure or
   high-level scoping; deeper detail in proposal addendum, not deck)

Total: ~13-18 slides typical. Flexible per topic complexity but
every section above is mandatory unless explicitly waived.

## Team Structure: Coordinated

Per `consulting-deck-builder` Phase 2 delegation contract, the team
fans out as 5-6 parallel case-analysts (one per act-cluster, NOT one
per slide) plus deck-builder + delivery-lead, with framework-lead
orchestrating.

- **framework-lead** leads and coordinates (orchestrator only — does
  not draft slide content):
  - **case-analyst** (×5-6, parallel) — per act-cluster:
    - Cluster 1: Cover + Topic introduction (sections 1-2)
    - Cluster 2: Case studies (section 3)
    - Cluster 3: Approach / methodology (section 4)
    - Cluster 4: From-To / current-vs-future (section 5)
    - Cluster 5: MVP + TOM (sections 6-7)
    - Cluster 6: Investment + next steps (section 8) — may be
      collapsed into Cluster 5 if section 8 is one slide
  - **deck-builder** — Cross-slide structure: action-voice title
    audit, transition flow, MECE check across all 8 sections,
    sticky-note conventions
  - **delivery-lead** — MVP timeline + TOM workplan content
    specifically (within Cluster 5; ensures phased gates have exit
    criteria, owners, no sliding deadlines)
- framework-lead runs internal coherence review before partner
  escalation

Each case-analyst is the SAME agent type with a different prompt
(per-cluster scope). Per HumanLayer 2026 research: task-based parallel
dispatch beats role-based agent zoo.

## Review Panel (independent, parallel)

After framework-lead synthesises consolidated content-draft.md,
dispatch all three reviewers in parallel:

- **partner-strategy** — Strategic positioning, commercial
  credibility, client-readiness; "would a target-audience C-suite buy
  this in 10 minutes?"
- **partner-analytics** — Case-study claims, value quantification,
  methodology rigor, from-to delta defensibility
- **principal-delivery** — MVP feasibility, TOM realism, timeline
  credibility, scaling path believability

Each reviewer reads the consolidated draft and returns a structured
verdict with severity-ranked findings (critical / warning / info).

## Output Format

Per `consulting-deck-builder` skill methodology:
- Phase 1: `output/storyboard.md` (spine + horizontal-MECE check)
- Phase 2: `output/cluster-<N>-content.md` (per cluster, drafted by
  case-analysts in parallel) → `output/content-draft.md`
  (consolidated by deck-builder)
- Phase 2 reviews: `output/review-verdicts.md` (collated by lead)
- Phase 3: `output/<topic>_proposal_v<N>.pptx` (or layout-spec md
  if pptx tools unavailable)

## Quality Gates

- Cover states what we're proposing in one action-voice sentence
- Every case study cites concrete metrics with anonymisation
- From-To has MEASURABLE delta per row (specific number, range, or
  directionally-quantified change — never bare "improvement")
- MVP has Week-1, Week-N, Week-final exit criteria
- TOM names specific org / role / decision-rights changes (not
  vague "transformation")
- Timeline has phased gates with no sliding deadlines
- Final deck readable in 10 minutes by a target-audience C-suite
- No reviewer flagged critical findings unaddressed at Phase 3 exit

## Source Material Discovery (Phase 1 / Phase 2 inputs)

Per `consulting-deck-builder` skill methodology, scour:
- Other proposal decks for the same topic (e.g., prior BCG X
  proposals on agentic SDLC for Tier-1 APAC banks)
- Working / active client decks for case-study anonymisation
  candidates (must scrub brand mentions per BCG protocols at
  `adapters/bcg/protocols/`)
- Web research (`web_search` / `web_fetch`) for third-party
  validation, market sizing, competitive positioning
- Engagement-specific summaries at
  `.agent/memory/client/<active>/summaries/` (lazy-load only —
  never bulk-read raw uploads)

## Iteration Discipline

The workflow does not constrain iteration count. The user may iterate
on storyboard for hours before signing off Phase 1 — that is correct
behaviour for a proposal where positioning matters more than speed.
Each iteration is logged via:

```bash
python3 .agent/tools/memory_reflect.py "consulting-deck-builder" \
  "phase-<N> proposal storyboard v<M>" \
  "<one-line summary of what changed>" \
  --importance 6 \
  --note "workflow=proposal-deck; topic=<topic>; audience=<audience>"
```

This produces the episodic trail the dream cycle clusters into
lessons for the proposal-deck workflow's evolution.

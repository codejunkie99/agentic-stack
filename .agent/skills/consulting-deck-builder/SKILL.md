---
name: consulting-deck-builder
description: Use proactively when work involves building or iterating on a deck with MBB structure. Triggers on "build a deck", "storyboard", "iterate on slides", "structure the storyline", "vertical horizontal logic check". Three-phase methodology: Storyboard (spine + MECE check) → Content (per-slide draft with stickies, all slides at once) → Format. Never skips a phase. Phase 2 dispatches per-act subagents in parallel via the matching workflow contract.
version: 2026-04-30
triggers: ["build a deck", "build pitch deck", "storyboard", "iterate on slides", "structure the storyline", "scrape these resources for the deck", "vertical horizontal logic check", "slide-by-slide build", "what should each slide say"]
tools: [bash, memory_reflect, web_search, web_fetch]
preconditions: ["active_client is set OR engagement scope is otherwise resolved", "raw material exists in client/<active>/raw-uploads or summaries"]
constraints: ["never skip a phase — Storyboard → Content → Format is mandatory ordering", "every slide must pass vertical-logic check before Phase 2 ends", "deck spine must pass horizontal-MECE check before Phase 1 ends", "action-voice titles only — complete sentences with conclusions, never topic titles", "lazy-load — do not bulk-read raw uploads; pull summaries first, raw on-demand", "stickies stay in drafts through Phase 3 — they are not removed, they migrate"]
---

# Consulting Deck Builder — storyboard → content → format

Goal: take a deck-building goal (audience, question, deadline) plus a body
of source material (under `.agent/memory/client/<active>/raw-uploads/`
indexed via `summaries/`) and produce an MBB-quality deck through three
mandatory phases — never skipping, never collapsing.

The skill enforces the discipline that separates a deck from a dump:
**vertical logic** within each slide (claim → 3 supports → evidence) and
**horizontal logic** across slides (MECE — mutually exclusive,
collectively exhaustive). Both checks are gates the agent runs at every
phase boundary, not optional polish at the end.

## When this fires

- User says "build a deck", "storyboard the deck", "iterate on slides"
- Engagement has source material indexed under `client/<active>/` and a
  goal in `briefing.md` that includes a deck deliverable
- An existing deck needs revision and the user explicitly invokes the
  three-phase loop (e.g., "redo the storyboard and re-content from scratch")

## Vertical logic — within a slide

Every slide is a closed argument. Structure:

1. **Title (Key Takeaway).** A complete sentence stating the conclusion.
   Never a topic. Examples:
   - ✅ "UOB proves agentic PDLC delivers 5–6x uplift — ready to replicate"
   - ❌ "UOB Case Study"
   - ❌ "Key Findings"
2. **Three supporting arguments (the body).** Sub-points that explain
   *why* the takeaway is true. E.g., "industry growth", "competitive
   advantage", "financial returns". Two is too few; four+ usually means
   the slide is doing two slides' work.
3. **Data / evidence (the base).** Specific charts, case studies, facts
   that prove each support.

Vertical-logic check: for every slide, can a reader trace
`title → support → evidence` without leaps? If a support isn't proved by
evidence, the slide fails. Mark with a TODO sticky.

## Horizontal logic — across slides

The deck as a whole must be MECE on the question it answers.

- **Mutually exclusive:** every slide says something distinct from every
  other slide. No overlap.
- **Collectively exhaustive:** all slides together fully cover the
  question. No gaps.
- **Pyramid principle:** the deck has a single top-level message;
  3–5 acts each support it; each slide supports its act.

Horizontal-MECE check: list every slide's title in one column. Does each
title answer a different sub-question? Are there sub-questions in the
audience's mind that no slide addresses? If yes, gap. If two slides
answer the same question, redundancy.

## MBB deliverable bar (always-on quality gates)

- **Actionable** — every slide ends with a "so what?" implication
- **Structured** — pyramid principle visible at every level
- **Data-driven** — every claim grounded in source material from
  `summaries/` or web research; no invented facts

## Sticky notation

Stickies are TODOs and annotations that travel with the deck through all
phases. They are an artifact, not pollution — they capture intent and
gaps that the team needs to resolve.

Four types:

```text
[STICKY: CONTENT — what content goes in this tile/box; where it comes from]
[STICKY: LAYOUT — how this should be visualized: chart type, columns, decoration]
[STICKY: TODO — open question, missing data, blocking dependency, needs human input]
[STICKY: COPY_AS_IS — <source-deck>:slide-<N>] — body uses bespoke source formatting; Phase 3 renders title + placeholder; user pastes original
```

Default convention: split (three distinct sticky types per slide as
needed). User can choose per-engagement to merge them into a single
combined sticky if preferred — the skill respects the engagement
preference once stated.

Stickies are NEVER auto-removed. They migrate from Phase 1 (sparse) to
Phase 2 (dense, content-focused) to Phase 3 (residual, layout-focused).
A deck that "looks done" but still has open TODOs is correctly flagged
as not-done.

## Phase 1 — Storyboard (the spine)

Goal: agree the deck's spine before drafting any content.

Steps:

1. **Read briefing.md + INDEX.md.** Confirm the engagement question
   (what does the deck answer?) and the audience (who reads it?).
2. **Read summaries/.** Build a mental index of available material —
   what claims, evidence, examples, frameworks exist across the
   engagement's source corpus. Do not read raw uploads yet.
3. **Draft the storyboard.** Single output file: `output/storyboard.md`.
   Format:
   ```markdown
   # <Engagement> — Storyboard v<N>
   
   ## Top-level message (the single sentence)
   <One sentence the deck delivers as a whole.>
   
   ## Acts (3-5)
   - Act 1: <action-voice act title> — <one-line intent>
   - Act 2: <...>
   - Act 3: <...>
   
   ## Slide map
   
   ### Act 1 — <act title>
   1. <slide title (action-voice, complete sentence)>
      - Intent: <what this slide proves / shows / asks>
      - Source(s): <which summaries inform this — names only, no quotes>
      - [STICKY: TODO if any]
   2. <slide title>
      - Intent: ...
   
   ### Act 2 — ...
   ```
4. **Run horizontal-MECE check on the storyboard.** List every slide
   title. For each act: are titles non-overlapping? Are there gaps in
   coverage? Document MECE compliance at the bottom of `storyboard.md`.
5. **Stop and ask.** Present the storyboard to the user. Ask: spine
   right? acts right? gaps? overlaps? Iterate until user signs off.

Phase 1 exit criterion: user explicitly approves the storyboard AND
the Phase 1 exit `memory_reflect` call has run (importance 8, pain 5,
DURABLE LESSON note). The agent never proceeds to Phase 2 on its own.

### Phase 1 — Iterating on an existing storyboard (delegated)

When Phase 1 is run on an EXISTING storyboard (e.g., user says "redo
Phase 1 on storyboard v2 with the team", or "iterate on the current
spine"), the workflow's team is dispatched in parallel — this is
distinct from cold-draft Phase 1 above.

**Dispatch pattern** (per the matched workflow's team_structure):

1. **framework-lead** orchestrates. Reads existing storyboard +
   workflow `## Contents` (e.g., proposal-deck.md's 8-section
   structure) + briefing.md. Identifies sections where v2 deviates
   from the workflow's canonical structure or where structural
   integrity is weak.

2. **deck-builder** dispatched in parallel — audits action-voice
   titles (every title a complete sentence stating a conclusion),
   transitions across acts, MECE compliance across slides. Returns
   structured findings: ✓ pass / ⚠ weak / ✗ fail per slide.

3. **case-analyst (×N)** dispatched in parallel — one per
   act-cluster. Each validates that the cluster's slides have
   sufficient source-material in `summaries/` to draft content in
   Phase 2. Returns: ✓ source-ready / ⚠ thin / ✗ missing per slide.
   Surfaces gaps where additional research (web_search /
   document-researcher on new uploads) is needed before Phase 2.

4. **delivery-lead** dispatched if workflow has MVP / TOM /
   workplan sections (e.g., proposal-deck does) — validates whether
   the storyboard's MVP and TOM slides have measurable, sequenced,
   ownership-bearing content available.

5. **Optionally** dispatch ONE reviewer at end of Phase 1 to
   challenge the spine before content drafting begins. Recommended
   for proposal-deck (where positioning matters) and final-
   recommendations-deck (where commercial credibility matters).
   Default reviewer: partner-strategy.

6. **Lead synthesises**, surfaces findings to user, proposes
   storyboard v3 (or signs off v2 if findings are minor). Lead does
   NOT redraft entire spine alone — uses the audit findings to
   propose structural changes.

7. **Stop and ask.** Present audit results + proposed v3 to user.

Phase 1 iteration exit criterion: user explicitly approves the
storyboard (v2 unchanged, or v3 produced from team audit).

## Phase 1.5 — Workflow-contract gate (Step 8.4 Gap 10)

Before Phase 2, run an 8-section coverage check against the seeding
workflow file (e.g. `.agent/workflows/final-recommendations-deck.md`).
Each missing or mis-framed section is a fix surfaced BEFORE sign-off,
not after — closes Gap 10 (framework-lead audit firing too late).

8 canonical sections: situation, complication, question, value-gap,
options, recommendation, risks, investment+next-steps. For each: covered?
framed action-voice + value-explicit + From-To? Revise BEFORE Phase 2.

Stops, asks: 8-section reconciliation report; explicit y per gap.

## Phase 2 — Slide content (delegated, parallel, all slides at once)

Goal: draft what every slide says, before any visualization choices.
Phase 2 is parallelized — the lead orchestrates and synthesises but
does NOT draft slides itself. Drafting is delegated to per-act
case-analysts and a deck-builder dispatched via the Agent tool.

### Delegation contract

1. **Look up the workflow.** Match the engagement to a workflow file
   in `.agent/workflows/`:
   - Mid-engagement deck → `mid-case-findings-deck.md`
     (`team_structure: coordinated`)
   - Final deliverable → `final-recommendations-deck.md`
     (`team_structure: full`)
   - Proposal / pitch deck → `proposal-deck.md`
     (`team_structure: coordinated`; 8-section canonical structure)
   - Other deck shapes → check `.agent/workflows/_index.md`

2. **Show the dispatch plan FIRST (mandatory gate).** Before any
   Agent tool calls, present to the user:
   - For each case-analyst dispatch: cluster name, sections owned,
     summaries assigned (specific filenames from `summaries/`), rough
     slide-count budget
   - For deck-builder: which structural concerns (titles / transitions
     / MECE check)
   - For delivery-lead: which sections (MVP / TOM / next steps)
   - For each reviewer: which lens
   The user confirms or edits the plan before any dispatch fires.
   This gate prevents the documented LLM tendency to misassign
   sources or over-fan the dispatch. Single-step delegation without
   prior plan-confirmation is a failure mode.

3. **Dispatch the team in parallel.** Per the workflow's
   team_structure, dispatch via the Agent tool:
   - **N case-analysts in parallel** — one per Act in the storyboard.
     Each case-analyst gets a prompt like: *"You are case-analyst for
     Act <N> of the HarnessX deck. Read storyboard.md for the slide
     map of your assigned act. Read summaries/<files-for-your-act>
     for source material. Draft slide content per the act's slides
     (vertical logic: title → 3 supports → evidence → so what).
     Output as `output/act-<N>-content.md`. Do NOT cross into other
     acts."* Each case-analyst is the SAME agent type (single
     subagent_type, parallel instances per act).
   - **1 deck-builder** — handles cross-slide structural concerns:
     action-voice title check, transition flow, MECE across acts.
     Prompt: *"Read storyboard.md and the in-progress
     output/act-*-content.md files as case-analysts produce them.
     Audit titles for action-voice (complete sentences with
     conclusions, not topics). Audit cross-act flow. Output
     consolidated `output/content-draft.md`."*

4. **Lead orchestrates only.** While case-analysts and deck-builder
   work, the lead does NOT draft slides. The lead:
   - Reads each Agent tool result as it returns
   - Resolves cross-act conflicts surfaced by deck-builder
   - Runs vertical-logic check on the consolidated draft (every
     slide: title → 3 supports → evidence)
   - Runs horizontal-MECE check on the full deck

5. **Dispatch the review panel** (parallel, after workers complete).
   Per workflow's review section:
   - **partner-strategy** — reviews business logic + strategic
     alignment + client-readiness
   - **partner-analytics** — reviews analytical rigor + data accuracy
   - **principal-delivery** — reviews workplan / next-steps
     feasibility
   Each reviewer reads the consolidated `output/content-draft.md`
   and returns a structured verdict with severity-ranked findings.

6. **Stop and ask.** Present the full content draft + 3 review
   verdicts to the user. User reviews ALL slides at once (their
   preference, locked at engagement start). Iterate until user
   signs off.

### Hard rules

- The lead does NOT draft slide content during Phase 2 if the
  workflow declares a team. If you find yourself writing
  `## Slide N — title...` in the orchestrator session instead of
  via Agent tool dispatch, STOP and dispatch.
- N case-analysts are the SAME agent type with different prompts —
  not N different specialised roles. (Per HumanLayer 2026 research:
  task-based parallel dispatch beats role-based agent zoo.)
- Reviewers run AFTER workers complete, not concurrently with them.
  Reviewing in-progress content produces noise, not signal.
- Sticky migration rule unchanged: stickies persist through phase 2,
  refined for content-and-layout focus.

### Output files (Phase 2)

- `output/act-1-content.md` ... `output/act-N-content.md` (per-act,
  drafted by case-analysts in parallel)
- `output/content-draft.md` (consolidated by deck-builder)
- `output/review-verdicts.md` (3 reviewer verdicts collated by lead)

Phase 2 exit criterion: user explicitly approves the consolidated
content-draft.md (and addresses or defers reviewer findings) AND
the Phase 2 exit `memory_reflect` call has run (importance 10, pain 8,
DURABLE LESSON note — auto-graduates as standalone candidate). The
agent never proceeds to Phase 3 on its own.

## Phase 3 — Format + content (visualization)

Goal: render the Phase-2-locked content-draft.md into a deliverable
deck artefact. **Content does not change in Phase 3** — titles,
storyline, body, panel-approved binding decisions are locked. Phase
3 is rendering + speaker-note finalisation + format QA only.

**Rendering engine:** vendored `deckster-slide-generator` (BCG) at
`adapters/bcg/skills/deckster-slide-generator/`. Read its sidecar
`INTEGRATION.md` BEFORE dispatching — it specifies the content-faithful
contract (content-draft.md is read-only; titles verbatim; no add/drop/
merge/reorder; 8 sticky types translate to render hints; `mode=
"content_faithful"` at invocation reverts any deckster rewrite).

Steps:

1. **Pre-flight — clear the 4 Phase 3 entry preconditions** from
   `output/phase-2-complete.md` (Slide 6 metric verify, SC brand-strip,
   Slide 3 rubric spot-check, Slide 7 demo binary). Hard render gates;
   each outcome logged to decisions log.
2. **Speaker-note pass.** Draft against Phase 2's SPEAKER-NOTE
   stickies (cover, transitions, ToC, appendix stubs). Output:
   `**Speaker note (final):**` field appended to each slide block in
   content-draft.md. Deckster receives finalised notes — does not
   generate.
3. **Sticky resolution sweep.** TODO + GATE stickies confirmed
   resolved or block render. BRAND_STRIP stickies trigger deterministic
   find-and-confirm-absent. CONTENT/LAYOUT stay as render hints;
   WAIVER/SCOPE honoured without re-litigation. **COPY_AS_IS stickies**
   flip render mode for that slide — deckster generates a placeholder
   (title + "paste from `<source>`" instruction box + speaker note)
   instead of body content; logged to `phase-3-copy-as-is-log.md` for
   deck-owner pre-delivery checklist.
4. **Dispatch deckster under `mode="content_faithful"`.** Pass
   content-draft.md as authoritative input + resolved precondition
   states. Renders to `output/<engagement-slug>-v<N>.pptx`.
5. **QA pass.** Deckster's `check_deck()` + per-slide PNG + visual
   inspection. Findings that need content change surface to user; no
   auto-correct.
6. **Mandatory disclaimer** on every .pptx delivery (per deckster
   non-negotiable): *"This skill does not connect to or rely on
   additional data sources. Claude may generate errors while creating
   slides that align with your instructions and data input. Please
   review output carefully before use."*
7. **Stop and ask.** User reviews rendered .pptx. Render-only
   iterations; content changes route back to Phase 2.
8. **Phase 3 exit reflection — HARD GATE.** Before declaring Phase 3
   complete, you MUST run the `memory_reflect.py` Phase 3 exit
   template (importance 9, pain 7, with a DURABLE LESSON sentence).
   This is what makes the engagement learning reach the dream cycle's
   canonical-claim step. **Phase 3 is not complete without it** —
   the agent should treat this as the literal final action of the
   phase, not optional polish. The same applies to Phase 1 + Phase 2
   exits.

Phase 3 exit criterion: user explicitly approves the rendered deck
artifact AND the Phase 3 exit `memory_reflect` call has run AND the
post-render decisions-log entry names any sticky that triggered a
late content change.

**Fallback (deckster unavailable):** layout-spec markdown at
`output/<engagement-slug>_v<N>_layout.md` with per-slide instructions
precise enough for a human or later-session pptx tool to build. Same
content-faithful contract applies.

## Iteration discipline (across phases)

- The skill operates in a strict pull-mode. It produces phase output,
  stops, asks. It does not push to the next phase without explicit
  user sign-off.
- If the user asks the skill to "redo Phase 1 from scratch" mid-engagement,
  the skill resets phase state — Phase 2/3 outputs become invalid until
  the new storyboard is approved.
- Every phase output is versioned: `storyboard.md` is overwritten with
  history kept at the bottom; `content-draft.md` and the deck artifact
  use `_v<N>` suffixes when major iterations land.

## Logging discipline (MANDATORY at every phase exit)

The dream cycle (`auto_dream.py` on Stop hook) clusters episodic events
by token similarity, picks the highest-salience event in each cluster
as the canonical claim, and stages clusters above
`canonical_salience >= 7.0` as graduation candidates. Salience formula:
`recency × (pain/10) × (importance/10) × min(recurrence, 3)`.

A long deck-build session writes hundreds of file-edit episodes that
share tokens with the engagement context, so any reflection at default
`importance=5, pain=2` gets buried — the cluster canonical becomes
"Wrote storyboard.md (781 lines)" instead of the lesson learned. Phase-
exit reflections must score high enough to win their cluster:
`importance × pain ≥ 70` is the rule of thumb (caps at 100).

### Phase 1 exit (Storyboard sign-off) — REQUIRED

```bash
python3 .agent/tools/memory_reflect.py "consulting-deck-builder" \
  "phase-1 storyboard signed off" \
  "<engagement-slug>: storyboard v<N> approved — <n_slides> slides, <n_acts> acts" \
  --importance 8 --pain 5 \
  --note "DURABLE LESSON: <one sentence — what about this storyboard structure transfers to future engagements? E.g. '5-act spine works for C-suite proposal decks when Act 1 defines a discipline, Act 2 proves it at scale.'> | DECISIONS LOG: <key binding decisions — title rewrites, MECE waivers, sticky migrations> | WHAT NEARLY FAILED: <if any — what almost broke this phase, e.g. workflow-contract gap, MECE violation that needed late repair>"
```

### Phase 2 exit (Content panel verdict applied) — REQUIRED

```bash
python3 .agent/tools/memory_reflect.py "consulting-deck-builder" \
  "phase-2 content panel-verdict applied" \
  "<engagement-slug>: content draft <n_slides>+<n_appendices> — panel verdict <GO|GO-WITH-FIXES|STOP>; <n_findings_applied> findings applied" \
  --importance 10 --pain 8 \
  --note "DURABLE LESSON: <one sentence on what worked or failed in the parallel-cluster + reviewer-panel pattern — e.g. 'positioning split (lighten main, push detail to appendix) resolves topic-intro vs programme-proposal pull cleanly when the audience is C-suite'> | BINDING DECISIONS: <Pulkit-confirmed final-fix decisions — these become per-engagement feedback memory> | PATTERN OBSERVED: <repeating shape across slides — e.g. cold-transitions cluster at act boundaries, attribution moats need 3 explicit mentions>"
```

### Phase 3 exit (Deck production complete) — REQUIRED

```bash
python3 .agent/tools/memory_reflect.py "consulting-deck-builder" \
  "phase-3 deck produced" \
  "<engagement-slug>: deck v<N> rendered — <n_slides> slides + <n_appendices> appendices, all entry preconditions cleared" \
  --importance 9 --pain 7 \
  --note "DURABLE LESSON: <one sentence on format/visual decisions that transfer — e.g. 'speaker notes carrying moat-protection ammunition matter more than visual polish for partner-in-the-room delivery'> | GATES THAT FIRED: <which Phase 3 entry preconditions caught real problems, which were unnecessary> | DECK-SPECIFIC SOURCING: <surprising sources that made or broke a slide>"
```

### Why importance × pain ≥ 70

| Reflection type             | importance × pain | salience (single, recency=10) | Crosses 7.0? |
|-----------------------------|-------------------|-------------------------------|--------------|
| Default (importance 5, pain 2) | 10            | 1.0                           | no           |
| Old skill (importance 6, pain 2) | 12          | 1.2                           | no           |
| Phase 1 exit (8 × 5 = 40)   | 40                | 4.0                           | no alone, dominates cluster |
| Phase 2 exit (10 × 8 = 80)  | 80                | 8.0                           | yes — graduates alone |
| Phase 3 exit (9 × 7 = 63)   | 63                | 6.3                           | dominates cluster |

Phase 2 exit is set to graduate alone (importance × pain = 80) because
the panel-verdict-applied moment is the engagement's highest-leverage
learning event. Phase 1 and Phase 3 exits are set to win their cluster
(become the canonical claim) without auto-graduating — the dream cycle
will still stage them when surrounding tool-write activity bulks
recurrence above 3.

### What the reflection text should be

**The reflection note is the candidate's claim text** — what the dream
cycle promotes if the candidate clusters. Write the LESSON, not the
ACTIVITY. Bad: "drafted 20 slides for HarnessX deck." Good: "When
storyboard collides with workflow contract late (8-section audit fired
post-v2), 6 structural moves are needed to reconcile — gate the
contract check at v1 instead." The first describes what happened; the
second is a transferable rule.

This produces the episodic trail the dream cycle clusters into lessons,
and the data this skill's self-rewrite hook reads.

## Examples

**Correct.** User says "build the deck for the HarnessX engagement."
Agent reads briefing + INDEX, lists summaries, drafts a 21-slide
storyboard with 3 acts, runs MECE check, presents `output/storyboard.md`.
Stops. Asks.

**Correct.** User reviews storyboard, says "Act 2 is overlapping with
Act 3 on the measurement framing." Agent rewrites Act 2 + Act 3 spine,
reruns MECE, presents v2. Stops.

**Correct.** Storyboard approved. Agent loads summaries for slides
1–8 (Act 1) first since user prefers reviewing in act-batches; **but**
user said all-at-once for this engagement, so agent drafts ALL 21
slides into `content-draft.md` before stopping.

**Failure mode (avoid).** Agent drafts Phase 1 storyboard, sees user
say "looks good," and continues to Phase 2 without explicit sign-off
on the storyboard's MECE compliance. **Wrong.** Sign-off on the
storyboard is sign-off on the spine — the MECE check is a separate
artifact the user must endorse. Re-run MECE check, present, then
proceed.

**Failure mode (avoid).** Phase 2 draft has 8 slides with 4 supports
each and 13 slides with 2 supports. Agent shrugs and presents.
**Wrong.** Run vertical-logic check first; flag every off-count
slide with `[STICKY: TODO — vertical logic: <N> supports, expected 3]`.

**Failure mode (avoid).** User says "ship it" mid Phase 2. Agent
collapses to Phase 3 to be helpful. **Wrong.** Phase 2 content review
is mandatory; "ship it" without per-slide content review means
something is going to be wrong. Confirm: "to skip the content review,
I need explicit confirmation that the content as drafted is what you
want — please scan and confirm or flag the slides you'd want changed."

## Self-rewrite hook

After every 3 decks built (Phase 3 exit reached), or the first time
a phase boundary is overridden by user pushback (e.g., "this MECE
check missed something obvious"), read the last 3
`consulting-deck-builder` entries from episodic memory. If better
phase-output structures, sticky conventions, vertical/horizontal
checks, or trigger patterns have emerged, update this file. Commit:
`skill-update: consulting-deck-builder, <one-line reason>`.

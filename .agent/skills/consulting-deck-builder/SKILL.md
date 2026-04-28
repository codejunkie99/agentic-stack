---
name: consulting-deck-builder
version: 2026-04-28
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

Three types:

```
[STICKY: CONTENT — what content goes in this tile/box; where it comes from]
[STICKY: LAYOUT — how this should be visualized: chart type, columns, decoration]
[STICKY: TODO — open question, missing data, blocking dependency, needs human input]
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

Phase 1 exit criterion: user explicitly approves the storyboard. The
agent never proceeds to Phase 2 on its own.

## Phase 2 — Slide content (all slides at once)

Goal: draft what every slide says, before any visualization choices.

Steps:

1. **For each slide in storyboard order:** load the source material
   referenced in the slide's `Source(s)` line. Pull from
   `summaries/<f>.md` first; only Read raw uploads if the summary is
   insufficient. Optionally use `web_search` / `web_fetch` if the
   storyboard flagged a need for external content.
2. **Draft slide content.** For each slide:
   ```markdown
   ## Slide <N> — <action-voice title>
   
   **Top takeaway (vertical-logic apex):** <complete sentence>
   
   **Support 1 — <one-line claim>**
   - Evidence: <bullet>
   - Evidence: <bullet>
   
   **Support 2 — <one-line claim>**
   - Evidence: ...
   
   **Support 3 — <one-line claim>**
   - Evidence: ...
   
   **So what?:** <implication for the audience>
   
   [STICKY: CONTENT — note about content choice]
   [STICKY: LAYOUT — note about visualization]
   [STICKY: TODO — open question / missing input]
   ```
3. **Output target:** ALL slides in single `output/content-draft.md`,
   in storyboard order. Reviewing all at once is mandatory — see
   constraint below.
4. **Run vertical-logic check on every slide.** For each slide: does
   title follow from supports? Do supports follow from evidence? Are
   there exactly 3 supports (≠ 2, ≠ 4+ unless explicitly justified)?
   Document compliance at end of `content-draft.md`.
5. **Run horizontal-MECE check on the deck.** Re-verify spine still
   holds at content depth. Sometimes content drafting reveals overlaps
   or gaps the storyboard missed — flag with TODO stickies and surface.
6. **Stop and ask.** Present the full content draft. User reviews ALL
   slides at once (their preference, locked at engagement start). Ask:
   what to keep, kill, sharpen, merge. Iterate until user signs off.

Phase 2 exit criterion: user explicitly approves the content draft. The
agent never proceeds to Phase 3 on its own.

## Phase 3 — Format + content (visualization)

Goal: integrate visualization choices with approved content. Stickies
migrate; content does not change without explicit approval.

Steps:

1. **For each slide:** translate `[STICKY: LAYOUT]` notes into concrete
   visualization choices. Chart type, column count, decoration density,
   color cues. Keep `[STICKY: TODO]` and `[STICKY: CONTENT]` stickies
   intact unless resolved.
2. **Output:** `output/<deckname>_v<N>.pptx` if pptx generation tools
   are available; otherwise a layout-spec markdown at
   `output/<deckname>_v<N>_layout.md` with per-slide instructions
   precise enough that a human (or pptx tool in a later session) can
   build the actual deck.
3. **Run final action-voice audit.** Every title is a complete
   sentence stating a conclusion. No topic titles, no hype words, no
   "Section X" placeholders.
4. **Re-run vertical + horizontal checks.** Visualization can break
   logic (a chart that doesn't show what the title claims). Catch.
5. **Stop and ask.** User reviews layout. Iterate until ship.

Phase 3 exit criterion: user explicitly approves the deck artifact.

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

## Logging discipline

After each phase exit (user sign-off):

```bash
python3 .agent/tools/memory_reflect.py "consulting-deck-builder" \
  "phase-<N> approved" "<engagement-slug> phase-<N> signed off" \
  --importance 6 \
  --note "phase: <storyboard|content|format>; deck: <name>; n_slides: <count>; major_changes: <one-line>"
```

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

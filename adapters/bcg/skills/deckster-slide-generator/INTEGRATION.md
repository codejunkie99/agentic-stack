# Deckster Integration Contract — content-faithful Phase 3 rendering

> **This file is the BCG-harness sidecar to `SKILL.md`** (vendored, not
> modified). It specifies how deckster is invoked from the
> `consulting-deck-builder` Phase 3 path — where storyline + per-slide
> content are already locked in `output/content-draft.md` and must NOT
> be regenerated.

## Why this contract exists

Deckster's stock scope is "create new deck from scratch" — it expects
to do its own storyline planning, title drafting, and content
generation. But when invoked downstream of `consulting-deck-builder`
Phase 2, the deck has already been:

- Storyboarded through Phase 1 with action-voice titles
- Content-drafted slide-by-slide through Phase 2 (parallel cluster
  drafts → consolidation → 3-reviewer panel → final-fix pass)
- Locked under user sign-off with binding decisions in the engagement's
  decisions log

Re-running deckster's planning pass against a locked content-draft
would discard hours of work and produce regressions on titles,
positioning, and panel-approved binding decisions. **That cannot
happen.**

## The contract

When deckster is invoked from `consulting-deck-builder` Phase 3:

### 1. content-draft.md is authoritative — read-only input

The skill MUST consume `output/content-draft.md` as the source-of-truth
slide-by-slide contract. For every slide block of the form:

```markdown
### Slide N — <action-voice title>

**Body:** <bullets / supports / evidence>
**Speaker note:** <draft note text>
**Stickies:** [LAYOUT: ...] [CONTENT: ...] [TODO: ...] [TRANSITION: ...]
              [GATE: ...] [WAIVER: ...] [BRAND_STRIP: ...] [SCOPE: ...]
```

Map exactly:
- `### Slide N — <title>` → `add_content_slide(title=<title>, ...)`.
  Title text is verbatim. Deckster's "must be action title, ≤90 chars"
  check still runs as a safety net, but is expected to pass — Phase 1
  already enforced action-voice and Phase 2 already verified character
  counts.
- Body bullets → slide body content. Verbatim. Deckster does NOT
  rewrite, summarise, expand, or re-order.
- Speaker note draft → attach as the slide's notes field.

### 2. Forbidden rewrites

Deckster MUST NOT, when invoked from this path:

- Change any title, even to "improve" action-voice phrasing
- Reorder slides
- Drop slides
- Add slides not present in `content-draft.md` (including no
  auto-generated executive summary, no auto-generated title slide
  beyond what the draft specifies, no transition slides)
- Merge slides (e.g., "this looks redundant — combining 12 and 13")
- Rewrite body content for tone, length, or "fit"
- Change appendix designations (A1-A8 are locked)
- Re-derive the storyline from the briefing — Phase 1 owned that

If deckster's stock heuristics flag a violation of its own rules
(e.g., "title too long"), surface as a finding for user decision.
Do NOT auto-correct.

### 3. Sticky annotations → render-time hints

The 8 sticky types in `content-draft.md` translate to deckster
render hints, not content regeneration triggers:

| Sticky type | Translation |
|---|---|
| `[LAYOUT: <hint>]` | Use the named layout (e.g., "two-column-callout" → `references/frameworks/two-column-callout.md`); Phase 2 specified the visual structure |
| `[CONTENT: <hint>]` | Late-breaking content addition Phase 2 didn't bake in — append/inject as specified |
| `[TODO: <task>]` | DO NOT render as final until the TODO is resolved by user/Phase-3-gate. Block render or render with a visible "DRAFT — TODO" overlay |
| `[TRANSITION: <text>]` | Add to slide's speaker note as the closing transition into the next slide |
| `[GATE: <pre-condition>]` | Hard pre-render gate — render fails if the gate has not been cleared by Phase 3 entry preconditions |
| `[WAIVER: <decision>]` | Already-resolved deviation from the workflow contract — render as drafted; do not re-litigate |
| `[BRAND_STRIP: <names>]` | Verify the listed brand/individual names are NOT present in body, title, or speaker note before render. Hard render-time check |
| `[SCOPE: <hint>]` | Scope clarification for the slide — fold into speaker note unless slide already addresses |

### 4. Phase 3 entry preconditions are a hard gate

Before deckster is invoked at all, the four entry preconditions from
`output/phase-2-complete.md` MUST be cleared. The
`consulting-deck-builder` Phase 3 step verifies these with the user
and only then dispatches deckster:

1. **Slide 6 metric verification gate (CRITICAL).** Verify the three
   headline metrics on Slide 6 against the raw source slide. If any
   metric fails verification, the slide title is revised BEFORE
   deckster is called.
2. **SC brand-strip sweep (BINARY GATE).** Deterministic
   find-and-confirm-absent sweep for SC / Standard Chartered /
   individual names against Slides 17, 19, and Appendices A6, A8.
   One missed reference = no render.
3. **Raw-source spot-check on Slide 3 rubric.** Five-dimension rubric
   verified against the raw source slide for any dimension-label
   divergence.
4. **Slide 7 demo binary resolution.** Vince supplies demo content →
   action-voice title confirmed, slide produced; Vince does not supply
   → slide hidden, Act 2 collapses to 1-slide proof. Deckster is told
   the resolved state at invocation.

Each gate's outcome is captured in the engagement's decisions log
before render.

### 5. Speaker-note pass happens BEFORE deckster, not inside it

The Phase 3 speaker-note stickies on Slides 1/5/8, 18, 8/20, 19, 20,
A5-A8 are drafted by `consulting-deck-builder` Phase 3 as a
text-content task BEFORE deckster is invoked. Deckster receives
finalised speaker notes per slide. It does not generate or rewrite
notes.

## Invocation surface

`consulting-deck-builder` Phase 3 calls deckster like:

```
PHASE_3_DISPATCH(
  rendering_engine="deckster-slide-generator",
  content_source="output/content-draft.md",
  preconditions_cleared=[1, 2, 3, 4],
  speaker_notes_finalised=true,
  mode="content_faithful",  # the contract above
  output_path="output/<engagement-slug>-v<N>.pptx",
)
```

`mode="content_faithful"` is the signal to deckster's host agent that
none of the rewrites in §2 are permitted. The host agent enforces this
by reviewing deckster's planned operations before execution and
reverting any title/order/content change that wasn't a translation of
a sticky.

## What deckster's stock SKILL.md still owns

Everything not listed above. Specifically:
- Visual rendering primitives (`add_content_slide`, `content_bounds`,
  `render_pattern`)
- Color palette + font hierarchy (TITLE 24, SUBHEADER 16, BODY 14,
  LABEL 12)
- Layout pattern selection from `references/layouts/` and
  `references/frameworks/`
- Chart rendering from `references/charts/`
- QA pass via `check_deck()` + per-slide PNG render + visual
  inspection
- Detail-mode default (`detail=True`)
- Disclaimer requirement on every .pptx delivery

## Audit trail

When deckster is invoked under this contract:
1. Log invocation to episodic via `memory_reflect` at importance 9,
   pain 7 (per Phase L's Phase 3 exit template in
   `consulting-deck-builder/SKILL.md`)
2. Record the four entry preconditions' outcomes in the engagement's
   `output/phase-3-precondition-log.md`
3. Append a decisions-log entry naming any sticky that triggered a
   late content change (so the divergence from content-draft.md is
   traceable)

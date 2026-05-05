# Viral-Pattern-Library Protocol

> Schema for a versioned library of short-form viral patterns:
> hooks, formats, retention curves, and per-persona adaptation
> rules. The mechanism that bakes "virality" into the creative
> pipeline at research stage rather than bolting it on at QA.

## Why this exists

Every creative-research output names "trends" — but trends without
metrics, hook taxonomy, or adaptation rules are inspiration boards,
not production inputs. The content strategist needs a library it
can query: which patterns proved out for this persona class?
which hooks correlate with completion vs saves vs shares? what's
the adaptation rule when a pattern lands for one persona and the
strategist wants to lift it for another?

This protocol defines the library schema. The library lives at
`ip-library/viral-patterns/` in target installs.

## Pattern entry schema

Each pattern is one Markdown file at
`ip-library/viral-patterns/<pattern-slug>.md`:

```yaml
---
pattern_slug: <kebab-case>
pattern_name: <human-readable>
hook_class: <from hook taxonomy below>
format: <talking-head | carousel | mock-interview | teardown |
         comparison | reaction | cinematic | thread | newsletter>
typical_duration_range_seconds: [<min>, <max>]
status: candidate | proven | retired
proven_for_personas: [<slug>, ...]   # written by analytics-loop
candidate_evidence:
  - source_url: <competitor or own post URL>
    captured_at: <YYYY-MM-DD>
    metrics:
      views: <integer>
      completion_rate: <float, 0-1, if scrapeable>
      shares: <integer, if scrapeable>
      saves: <integer, if scrapeable>
    notes: <one-line on why this instance counts>
version: <integer; increment on edit>
---
```

### Required body sections

1. **Pattern shape** — 2-5 sentences. What the post DOES, not what
   it's about. Example: "First 1.5s shows a problem (not the topic)
   in close-up; cut to mid-shot of the persona naming the problem
   in one sentence; cuts to three short proof beats; closes on a
   one-line takeaway." Topic-agnostic.
2. **Hook taxonomy class** — see "Hook taxonomy" below. The hook is
   what runs in the first 1-2 seconds. Pattern shape is the whole
   post structure.
3. **Retention curve** — qualitative description: where does the
   pattern keep attention vs lose it? (Pre-hook, hook, beat 1, beat
   2, beat 3, takeaway, CTA.) Identify the at-risk beat.
4. **Per-persona adaptation rules** — for each persona class this
   pattern can run for, name the constraints. What changes (voice,
   visual, angle), what stays (structure, hook class, retention
   curve). This is the field that prevents copy-paste virality.
5. **Anti-patterns / failure modes** — when this pattern fails. What
   makes a producer think they're following the pattern but actually
   isn't.
6. **Citation** — links to ≥ 3 instances of this pattern in the
   wild (competitor accounts, own past posts), with metrics where
   scrapeable.

## Hook taxonomy

The hook is the first 1-2 seconds. Every pattern declares one
`hook_class`. Initial classes (extensible per install):

- `pattern-interrupt` — visually breaks expectation (unusual angle,
  jump-cut, weird object center-frame)
- `bold-claim` — a one-line assertion that demands a "wait, what?"
- `named-problem` — opens by naming a problem the viewer recognizes
  ("Your contractor isn't following up on quotes — here's why")
- `unexpected-ally` — opens with a take from a surprising voice
  ("I'm a [X] and I'm telling you to stop [common-advice]")
- `before-after` — opens on the after-state, then explains how
- `teardown-frame` — opens with "I rebuilt this [thing]" or
  "I read the label on this [thing] so you don't have to"
- `mock-interview` — opens mid-interview, viewer joins late
- `numerical-promise` — "Three [things] every [audience] should
  know" (overused — flag if proposing in 2026+)
- `controversy-opener` — opens with a position the viewer disagrees
  with — high engagement, high risk

Each `hook_class` carries its own retention-curve baseline (set at
classifier-version 1 from the analytics-loop's first quarter of
data; revise on documented evidence).

## Status lifecycle

```
candidate ──proven──▶ proven ──retired──▶ retired
    │                                ▲
    └──── retire (insufficient evidence) ────┘
```

- **candidate** — new entry. Author cited evidence but the pattern
  hasn't proven out for any of our personas yet.
- **proven** — the analytics-loop's pattern-attribution emitted
  this `(format, hook_class)` pair as a proven pattern for ≥ 1
  persona. Status flip is automatic, not editorial.
- **retired** — pattern's proven-for-personas list is empty AND the
  pattern hasn't been used in the last 90 days. Or: the pattern
  has saturated the platform (signal: top-quintile posts using this
  pattern dropped > 50% week-over-week for 2 consecutive windows).
  Retired patterns aren't deleted — they stay queryable for
  historical analysis.

## Write discipline

- New entries: written by the `creative-researcher` agent during
  research stage, status `candidate`. Researcher must include ≥ 3
  citations with metrics.
- Status promotions: written by the analytics-loop based on the
  winner-classification contract. Never written by hand.
- Retirement: also automatic per the lifecycle rules above.
- Edits to pattern shape, retention curve, or adaptation rules:
  bump `version`, append a one-line entry to a `version_log`
  section.

## Read discipline

- Content-strategist agent reads the library at the start of every
  weekly plan. Required: pull the proven patterns for the persona
  in question + 2-3 candidates worth testing.
- Hook-and-script agent reads the relevant pattern file before
  drafting. The script must declare which pattern it implements
  (or note "off-pattern: <one-line reason>").
- Creative-director agent confirms the format choice matches the
  pattern's declared format.

## Cross-persona transferability

When the analytics-loop emits a transferability flag (same
`(format, hook_class)` proven for ≥ 2 personas), the strategist
can lift the pattern. Adaptation rule: keep the pattern shape and
hook class; rewrite voice + visual per the new persona's bible.
Lift attempts that fail in the next analytics window get logged in
the pattern's version_log so the library learns which patterns
generalize.

## Anti-patterns

- **Logging "trends" as patterns.** A trend is a topic
  ("everyone's talking about X"). A pattern is a structure
  ("named-problem hook → 3 short beats → takeaway"). Trends are
  research notes, not library entries.
- **Proven without evidence.** Status promotion happens via the
  analytics-loop only. Hand-promoting "I think this is proven"
  poisons the library.
- **Per-niche taxonomy fragmentation.** The hook taxonomy is
  shared across personas. If a hook genuinely doesn't fit the
  taxonomy, extend the taxonomy (with a version bump), don't fork
  per niche.
- **Pattern shape too topic-specific.** "I read the food label"
  isn't a pattern — it's an instance of `teardown-frame`. The
  pattern has to abstract above topic.

## What this protocol does NOT define

- Specific patterns or hook classes the project ships with — those
  are install-time research outputs.
- Scraping infrastructure for evidence collection — install-specific.
- Composite metric weights — see `analytics-loop.md`.

## Status

Authored 2026-05-05 as part of creative-vertical PR1.

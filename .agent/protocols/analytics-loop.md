# Analytics-Loop Protocol

> KPI schema + winner-classification contract that turns post-publish
> metrics into an automatic priority signal for the next content
> cycle. Generic across short-form-video platforms (TikTok, IG Reels,
> YouTube Shorts) and adjacent surfaces (carousels, threads,
> newsletters).

## Why this exists

Without a canonical metrics shape and a deterministic
winner-classification rule, "what's working" becomes anecdotal. The
content-pipeline workflow's analyze stage needs a contract it can
read mechanically: ingest metrics in this shape, emit a winner-class
in this shape, hand off to the next cycle's strategist.

This protocol defines the contract. Dashboards, scrapers, and
platform-API connectors are install-specific and live in the target.

## KPI schema (per post)

Every published post has a single `analytics.json` file at
`ip-library/personas/<slug>/posts/<YYYY-MM-DD>-<post-slug>/analytics.json`
in the target install. Schema:

```json
{
  "post_slug": "2026-05-12-foreman-rfq-bottleneck",
  "persona_slug": "foreman",
  "platform": "tiktok | instagram-reels | youtube-shorts | x | newsletter | carousel",
  "platform_post_id": "<platform-native id>",
  "url": "https://...",
  "published_at": "2026-05-12T14:00:00Z",
  "format": "talking-head | carousel | mock-interview | teardown | comparison | reaction | cinematic | thread | newsletter",
  "duration_seconds": 47,
  "hook_class": "<from viral-pattern-library taxonomy>",
  "snapshots": [
    {
      "captured_at": "2026-05-12T16:00:00Z",
      "age_minutes": 120,
      "views": 1240,
      "likes": 84,
      "comments": 12,
      "shares": 9,
      "saves": 14,
      "follows_attributed": 3,
      "watch_time_seconds_avg": 23.1,
      "completion_rate": 0.49,
      "rewatch_rate": 0.07,
      "profile_visits": 38,
      "link_clicks": 5,
      "dms_inbound": 1,
      "revenue_attributed_cents": 0
    }
  ]
}
```

Snapshots are append-only; the file accumulates time-series rows.
Cadence is install-specific (typical: 2h, 24h, 7d, 30d).

### Notes

- `hook_class` references a class from the viral-pattern library —
  this is what makes the analytics loop feed back into pattern
  selection (per `viral-pattern-library.md`).
- `revenue_attributed_cents` is best-effort and may stay 0 for
  top-of-funnel posts. Conversion attribution is the install's
  problem, not this protocol's.
- Any field a platform doesn't expose: omit it (don't insert null
  or 0 — that lies). Aggregations downstream must handle absence.

## Winner-classification contract

After the analytics-loop runs over a window (default: rolling 7-day,
configurable in install), it emits a `winners.md` per persona at
`ip-library/personas/<slug>/winners-<YYYY-WW>.md`. Schema:

```yaml
---
persona_slug: <slug>
window_start: <YYYY-MM-DD>
window_end: <YYYY-MM-DD>
posts_in_window: <integer>
classifier_version: 1
---
```

Body sections:

### 1. Top-quintile posts

Posts in the top 20% on a composite score. Composite is the
geometric mean of normalized completion-rate, save-rate, share-rate,
and follows-per-view (geometric so a post can't dominate by spiking
one metric). Normalization is within-persona, within-window — i.e.
each persona is its own baseline.

For each top-quintile post, capture:

- `post_slug`
- `format`
- `hook_class`
- `composite_score`
- `breakout_signal`: which metric drove the classification
  (completion / saves / shares / follows / comments / multiple)
- `commerce_signal`: any of `link_clicks > 0`, `dms_inbound > 0`,
  `revenue_attributed_cents > 0` — surfaces buyer interest

### 2. Bottom-quintile posts

Posts in the bottom 20%. Capture the same fields. The next-cycle
strategist uses this to kill underperforming format/hook
combinations, not to "fix" individual posts.

### 3. Pattern attribution

Roll up the top quintile by `(format, hook_class)` pairs. Pairs that
appear in ≥ 30% of top-quintile posts in the window are flagged as
**proven patterns** for this persona. The next-cycle strategist
should produce ≥ 3 variants per proven pattern in the next plan.

### 4. Cross-persona transferability flags

If the same `(format, hook_class)` pair appears as a proven pattern
for ≥ 2 personas, emit a transferability flag. The strategist can
adapt the pattern across personas (per the viral-pattern-library's
adaptation rules).

### 5. Anomaly notes

Any post outside expected behavior bands gets a one-line note. Bands
are install-defined; common ones: views >> baseline (potential
breakout — flag for boosting), saves >> shares (utility-shaped
content — strong commerce signal), comments >> saves (controversy or
question-rich — flag for engagement-agent follow-up).

## Feedback hooks

Three explicit feedback paths, each named so the content-pipeline
workflow can wire them:

1. **Strategist intake** — `winners.md` is a required input to the
   next content-strategist run for that persona. The strategist's
   plan must reference the proven patterns explicitly or note why
   it's diverging.
2. **Pattern-library write-back** — when a `(format, hook_class)`
   pair becomes proven for the first time, the viral-pattern-library
   gets a write per `viral-pattern-library.md`'s write rules. This
   is what makes the loop self-improving.
3. **Bible-review trigger** — if a persona's bottom quintile is
   ≥ 50% of posts in the window, surface a bible review. The bible
   may be off — voice, worldview, or boundaries are missing the
   audience.

## Anti-patterns

- **Optimizing on views alone.** Views without saves/shares/
  completion is vanity. Composite-only.
- **Acting on a single post.** Single-post results are noise. Wait
  for the window.
- **Hand-editing winners.md.** Classifier output is mechanical.
  Override by editing the input data or the classifier params, not
  the output file.
- **Cross-platform composite.** Different platforms have different
  base rates. Composite is per-platform; cross-platform comparison
  uses normalized rank, not raw composite.

## What this protocol does NOT define

- Platform API integration (install-specific).
- Dashboard layout (install-specific).
- Conversion-funnel attribution model (install-specific).
- Specific composite weights — base implementation is geometric
  mean of four normalized metrics; installs can override but must
  document the override and version-pin the classifier.

## Status

Authored 2026-05-05 as part of creative-vertical PR1.

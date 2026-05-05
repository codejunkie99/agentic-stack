---
workflow_id: content-pipeline
name: Creative Content Pipeline (per-post)
team_structure: full
description: End-to-end production loop for one short-form content piece in the creative vertical. Reads persona-bible + viral-pattern-library + winners.md, produces a platform-ready post with continuity-checked assets, publishes, and feeds analytics back into the next cycle. Distinct from the SDLC pipeline (feature-end-to-end.md) — this workflow is for synthetic-character content, not software features. Consumes protocols persona-bible, ip-library, analytics-loop, viral-pattern-library; dispatches creative-researcher (research stage only) + persona-architect + visual-identity + content-strategist + hook-and-script + creative-director + image-gen + video-gen + editor + realism-review skill + virality-analyst + engagement.
---

## Purpose

Produce ONE short-form post for ONE persona. The workflow exists because creative production has a different shape than software production: characters drift, virality is feedback-driven, and the QA dimension is continuity + realism rather than test-pass. SDLC workflows (feature-end-to-end.md, bugfix-arc.md) don't fit; this is the creative-vertical sibling.

This workflow runs once per post. The persona-creation workflow (separate, runs once at portfolio bootstrap) sits upstream; this workflow assumes the persona exists with an approved bible.

## Trigger phrases

"produce a post for [persona]", "next post for [persona]", "make a [tiktok | reel | short] for [persona]", "ship today's [persona] post", "run content-pipeline for [persona]".

## When NOT to use

- Persona doesn't exist yet — run persona-creation workflow first.
- Persona's bible status is `draft` — promote to `approved` first (drafts can produce, but the analytics-loop won't trust the data).
- Bulk production of N posts — run this workflow N times (in parallel where practical), don't lump posts together.
- Software-feature work — wrong vertical; use feature-end-to-end.md.

## Required upstream artifacts (preconditions)

Before starting, confirm:

- Persona has `bible.md` at the IP library's persona path with `status: approved`.
- Persona has `master-image.prompt.md` + `master-video.prompt.md` (whichever the planned format needs).
- Viral-pattern library exists at `ip-library/viral-patterns/` with at least 3 candidate or proven patterns for this persona class.
- If running a follow-up cycle, `winners-<YYYY-WW>.md` for the persona's most recent window exists. (First cycle exempt.)

If any precondition fails, stop and surface — do not absorb missing inputs.

## Stages

| # | Stage | Owner | Inputs | Output | Exit gate |
|---|---|---|---|---|---|
| C1 | **Pattern selection** | `content-strategist` | bible, viral-pattern-library, latest `winners.md` (if exists) | `post-brief.md` (selected pattern, format, hook_class, target audience moment, target duration) | One pattern explicitly selected; brief names hook_class, format, expected retention curve |
| C2 | **Research brief** | `creative-researcher` (lite mode — single-post intake, not a full niche audit) | post-brief.md | `research-brief.md` (factual scaffolding, examples, 2-3 source links if claims are made) | All factual claims in the brief have a source or a "no-source — opinion" tag |
| C3 | **Hook + script** | `hook-and-script` | post-brief.md, research-brief.md, persona bible voice section | `script.md` with ≥ 3 hook variants + 1 full script + caption-overlay list + CTA variants + shot-list | Script declares which pattern it implements; voice samples blind-tested against bible.voice (if a writer who hasn't read the bible can't predict the persona, fail) |
| C4 | **Creative direction** | `creative-director` | script.md, persona visual style-guide | `creative-brief.md` (format choice, shot list, visual references, B-roll plan, edit notes) | Format matches the pattern's declared format; visual references cite IP library `_APPROVED.md` versions |
| C5 | **Asset generation (parallel)** | `image-gen` + `video-gen` (in parallel where the format needs both) | creative-brief.md, master prompts, reference pack | raw assets at `posts/<post-slug>/assets/` | Generated assets exist for every shot in the shot-list; bible_version pin recorded |
| C6 | **Editing** | `editor` | raw assets, script.md, caption-overlay list | `posts/<post-slug>/final/<platform>.mp4` (per target platform) + `caption.md` + `thumbnail.png` | First 1.5 seconds matches hook plan; captions burned in; per-platform export specs met (resolution, aspect, max length) |
| C7 | **Realism + continuity QA** | `realism-review` skill (run once per generated medium) | final exports, persona reference pack, bible | `continuity-report.md` per `ip-library.md` schema | `verdict: pass` OR explicit manual-review override with one-line justification by human |
| C8 | **Publish** | `editor` (or human, depending on install) — the workflow does NOT auto-publish; it stages | platform-ready exports, caption | platform_post_id captured in analytics.json frontmatter | Post live on platform; AI-disclosure toggle ON per platform's policy; `analytics.json` initialized at `posts/<post-slug>/analytics.json` |
| C9 | **Analyze + feed back** | `virality-analyst` (snapshot capture) + `analytics-loop` (window-end roll-up) | analytics.json snapshots over the install's cadence | updates to `analytics.json`, eventual `winners-<YYYY-WW>.md`, possible promotion of pattern from candidate→proven | Snapshot rows present at the install's declared cadence checkpoints (e.g. 2h, 24h, 7d) |
| C10 | **Engagement loop** | `engagement` | comments + DMs from the post, analytics flags | comment-reply drafts, DM drafts, ideas-from-comments roll-up, lead-list updates | High-signal comments captured as next-cycle content seeds; buyer-signal DMs flagged for monetization workflow (target-install) |

Stages C1-C7 are the pre-publish arc. C8-C10 are the post-publish arc. Most of the value is in C7 (continuity gate) and C9 (feedback) — these are the loops the SDLC sibling workflows don't have.

## Compression rules

- C1 + C2 fold to one stage when the strategist already has the research (e.g. running a known-winning pattern for the Nth time).
- C5's image and video generation run in parallel where independent.
- C9's snapshots are async — workflow exits after C8 with C9 + C10 running on cadence in the background.

What CANNOT compress: C7 (continuity QA), C9-rollup at window end. Both feed downstream loops; skipping either poisons future cycles.

## Pattern selection contract (C1 detail)

The `content-strategist` MUST follow this precedence at C1:

1. **Proven patterns first.** If `winners.md` lists proven `(format, hook_class)` pairs for this persona, default to producing a variant of one of them. Aim: ≥ 3 proven-pattern variants for every 1 candidate-pattern test.
2. **Cross-persona transfer second.** If the viral-pattern-library has a transferability flag matching this persona's class, lift the pattern (per the library's adaptation rules).
3. **Candidate test third.** If neither of the above applies (e.g. cold start), pick a high-evidence candidate pattern. Mark the post as a candidate test in `post-brief.md`.

The strategist's brief MUST declare which precedence tier was chosen and why. Drift away from precedence (e.g. "off-pattern, gut call") gets logged in the brief's footer for the analyst to track.

## Realism + continuity gate (C7 detail)

The `realism-review` skill runs against:

1. The persona's bible (current version).
2. The persona's reference pack (face, wardrobe, environment).
3. The post's final exports.

It emits `continuity-report.md` per the IP-library protocol's drift-check schema. Verdicts:

- `pass` — proceed to C8.
- `fail` — workflow loops back to C5 (regenerate) or C6 (re-edit), NOT to C8. Regeneration uses the report's regeneration instructions. Three fail-loops on the same dimension trigger a bible review (per persona-bible.md).
- `manual-review` — human decides. Override must be justified in a one-line note in the post's directory.

The gate is non-skippable. Compression rules elsewhere don't touch C7.

## Disclosure + platform compliance

The workflow does NOT instruct any agent to suppress AI-content disclosure on any platform. C8 publishes with the platform's AI-disclosure toggle ON per the platform's stated policy. Detection-evasion techniques (watermark stripping, recapture laundering, model rotation, engagement priming) are explicitly OUT OF SCOPE for any agent in this workflow. Realism-review's role is quality and continuity, not evasion.

If a platform's disclosure UX is unclear, the install's human operator decides; the workflow surfaces the question rather than guessing.

## Iteration cookbook

Most feedback shapes after C8 publish:

| Feedback | Re-enter at | Why |
|---|---|---|
| "The post tanked" | C9 first (wait for window), then C1 next cycle | Single-post failure is noise; loop trusts the window. |
| "Face drifted from prior posts" | C7 + C5 | Continuity gate failure or upstream prompt drift. Check IP library's prompt-version-log. |
| "Voice doesn't match bible" | C3 + bible review | Script stage missed the voice anchors. If recurring, bible's voice section under-specifies. |
| "The pattern I picked wasn't right for this persona" | C1 + viral-pattern-library adaptation rules | Pattern's per-persona adaptation rule may need tightening. |
| "Buyer DMs landed but no offer was ready" | C10 + monetization workflow (target-install) | Engagement surfaced a commerce signal; commercial path not wired. |
| "Realism review keeps failing on hands" | C5 (prompt revision) + bible's negative-prompt list | Anatomical artifacts are usually a negative-prompt gap. |
| "Post worked but I can't reproduce the format" | C7 metadata + viral-pattern-library write-back | Format's pattern entry may be missing or under-specified; capture the structure. |

## Quality gates (workflow exit, post-publish day-1)

- All 10 stages signed off in the post's directory (or the post-publish-only stages C9-C10 declared "running on cadence").
- C7 verdict captured.
- AI-disclosure setting recorded in analytics.json.
- post-brief.md cites the precedence tier from C1.
- Pattern attribution will roll up at the next analytics window — no exit gate here, but the rollup is a workflow contract.

## Memory write discipline

`memory_reflect` at workflow exit (C8 ship):

- `importance` based on whether this post was a proven-pattern variant (5), a candidate test (7), or a cross-persona transfer (8).
- `pain` only if a stage looped > 1x.
- Note must capture a DURABLE LESSON about the pattern, the persona's voice, or the platform's behavior — not "produced post X." Closer to "named-problem hook on talking-head landed for foreman; carousel adaptation of same hook tanked — pattern doesn't transfer to static format for this voice."

## Anti-patterns

- **Producing without reading the bible.** Drift compounds silently. C3 + C5 producers MUST open bible.md first.
- **Running C7 as a rubber-stamp.** If the gate never fails, it's not gating. Either prompts are pristine (unlikely) or the reviewer is rubber-stamping.
- **Skipping C9 because "the post obviously worked."** Anecdotal wins poison the analytics loop.
- **Hand-promoting candidate patterns to proven.** Only the analytics-loop promotes. Hand-promotion poisons future precedence-tier decisions.
- **Compressing C1 in cold-start.** First N posts for a fresh persona need explicit pattern selection so the analytics loop has labeled data to roll up. Compressing here costs you the loop.
- **Running multiple personas through one C5 session.** Reference packs are per-persona. Cross-talk = drift.

## Path-forward decision (post-window)

After the analytics window closes:

- **Repeat** — pattern proven again, run a variant next cycle.
- **Iterate** — pattern showed promise but missed; tweak shape per per-persona adaptation rule, retest.
- **Retire** — pattern saturated; mark retired in viral-pattern-library; rotate.
- **Promote candidate** — candidate test cleared the proven-pattern bar; library auto-promotes; strategist queues variants.

Captured in the persona's `winners-<YYYY-WW>.md` rollup; no separate POST-MORTEM.md needed (creative-vertical's loops are weekly, not per-post).

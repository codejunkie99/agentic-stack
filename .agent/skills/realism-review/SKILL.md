---
name: realism-review
description: Use when reviewing AI-generated images or videos for visual realism, character continuity, and platform-native production quality before publishing. Detects glitches (hands, eyes, teeth, anatomical), continuity drift (face, wardrobe, environment, palette, motifs vs the persona's reference pack), text-rendering errors, and logo issues. Emits a continuity-report.md per the ip-library protocol's drift-check schema with a pass/fail/manual-review verdict and concrete regeneration instructions on fail. Triggers on "review this asset for realism", "continuity check on this post", "QA the generated image/video for [persona]", "does this match the bible", "realism review", "C7 stage". Distinct from generic image critique — this skill is the explicit QA gate at content-pipeline stage C7. Out of scope: detection-evasion advice, AI-disclosure suppression, anti-forensic techniques.
version: 2026-05-05
triggers: ["review this asset for realism", "continuity check on this post", "QA the generated image", "QA the generated video", "does this match the bible", "realism review", "C7 stage", "continuity-report", "continuity check"]
tools: [Read, Glob, Grep, Write]
preconditions:
  - "asset(s) to review exist on disk at the post's assets/ or final/ path"
  - "persona has an approved bible at ip-library/personas/<slug>/bible.md"
  - "persona has a reference-pack/ with at least 1 _APPROVED.md entry"
constraints:
  - "verdict is one of pass | fail | manual-review — never blank"
  - "fail verdict requires concrete regeneration instructions (prompt change, reference change, or shot retake)"
  - "skill does NOT advise on detection evasion, watermark stripping, or AI-disclosure suppression"
  - "skill does NOT modify the asset itself — review only"
---

# Realism + Continuity Review

Goal: gate AI-generated assets at the content-pipeline workflow's QA stage (C7) so drift, glitches, and continuity errors don't ship. Output is a `continuity-report.md` next to the asset, conforming to the ip-library protocol's drift-check schema.

## When this fires

- Content-pipeline workflow C7 stage runs on a freshly generated image or video.
- Persona-architect promotes a bible from draft to approved (smoke pass on first generated assets).
- Visual-identity update lands; existing posts re-checked against the new identity to confirm continuity.

## When this does NOT fire

- Reviewing real (non-AI) photography — not the right tool.
- Code review — wrong vertical.
- Detection-evasion review — explicitly refused. This skill is for quality + continuity, not evasion.

## Procedure

### 1. Open the inputs

Read in this order:

1. The asset(s) under review. Note path and medium (image / video).
2. The persona's `bible.md` — note the current version.
3. The persona's `reference-pack/_APPROVED.md` — note which versions are canonical.
4. The persona's `prompts/master-image.prompt.md` (or `master-video.prompt.md`) — prompt used to generate.
5. If the post has prior posts, the most recent published post's final asset for continuity.

If any input is missing, stop and surface — don't review against partial input.

### 2. Run the dimension checklist

For each asset, walk this checklist. Record findings (path: dimension: observed: expected: severity).

Dimensions, with what to check:

| Dimension | What to check |
|---|---|
| **Face — identity** | Does the face match the canonical face-front / face-3q references? Specifically: bone structure, eye spacing, nose shape, chin line. Skin texture / color grading variance is acceptable; identity drift is not. |
| **Face — anatomical** | Eyes (pupils consistent, no extra reflections, both eyes match), teeth (count, alignment, no doubled rows), ears (count, plausible shape), hairline (consistent with reference). |
| **Hands** | Finger count, finger length, knuckle articulation, thumb placement, no fused fingers, no extra fingers. AI's most common failure mode. |
| **Wardrobe** | Matches wardrobe reference pack. Color, cut, layering, accessories. Logos on clothing are correct or absent (no garbled brand text). |
| **Environment** | Setting matches the persona's environment guide. Background objects are coherent (no floating objects, no impossible geometry). |
| **Palette** | Color palette consistent with style-guide. No oversaturation, no off-brand color casts. |
| **Lighting** | Direction + quality match style-guide. Shadow direction physically plausible (single primary light source unless guide says otherwise). |
| **Motifs** | Recurring visual motifs from style-guide present where appropriate (camera framing, props, signature compositions). |
| **Text rendering** | Any visible text — captions burned in, signage, on-screen text — readable, correctly spelled, no AI-jumble. Caption font matches editor's caption-style if specified. |
| **Logos / brand marks** | Any logo visible: either correctly rendered (matches a real brand and persona has authority to show it) OR clearly fictional. No "almost-Coca-Cola" half-rendering. |
| **Anatomy — body** | Limb count, joint positions, proportions plausible. Spine bend physically reasonable. |
| **Continuity with prior posts** | Face / wardrobe / environment continuous with the most recent published post for this persona, allowing for storyline shifts (a new outfit is fine if the worldview supports it). |

For video specifically, also check:

| Video-specific | What to check |
|---|---|
| **Frame-to-frame consistency** | Face / wardrobe doesn't morph mid-clip. Background stays consistent. |
| **Motion plausibility** | Limb motion doesn't break joint constraints. Walks land foot-by-foot. Lip-sync (if voice present) within acceptable lag. |
| **Cut transitions** | Cut points don't expose a different face or environment without narrative reason. |
| **Aspect / resolution** | Matches platform target spec from the editor's export brief. |

### 3. Score severity per finding

Each finding gets one of:

- **CRITICAL** — visible to a casual viewer in normal scroll speed. Asset cannot ship.
- **MAJOR** — visible on a second look or in slow-scroll. Asset SHOULD regenerate; "manual-review" override allowed if other constraints (deadline) force it.
- **MINOR** — visible only on freeze-frame. Note it but does not gate.

### 4. Decide verdict

- **pass** — no CRITICAL, ≤ 1 MAJOR, MINOR findings allowed.
- **fail** — any CRITICAL, OR ≥ 2 MAJOR.
- **manual-review** — exactly 1 MAJOR + deadline pressure cited; human decides. Use sparingly; if `manual-review` fires > 1 time per 5 posts, the bible or the reference pack is under-specifying.

### 5. Write the report

Write `continuity-report.md` at the post's directory, conforming to ip-library's drift-check schema. Required:

```yaml
---
post_slug: <YYYY-MM-DD-<short>>
persona_slug: <slug>
bible_version: <integer — version asset was generated against>
checked_at: <YYYY-MM-DDTHH:MM:SSZ>
verdict: pass | fail | manual-review
---
```

Body sections:

1. **Asset(s) checked** — paths.
2. **Reference set** — which `reference-pack/` versions used.
3. **Findings** — table with columns: dimension | severity | observed | expected.
4. **Regeneration instructions** — REQUIRED if `verdict: fail`. Concrete: change to prompt, reference to add, shot to retake, negative-prompt addition.

### 6. Drift-counter check

Before exiting, check `.agent/memory/working/personas/<slug>/drift-log.md` (in the target install). If THIS report is the third consecutive fail on the same dimension, append a bible-review trigger note per the persona-bible protocol. The bible may be under-specifying; surface to persona-architect.

## What this skill does NOT do

- Modify the asset (review-only).
- Suggest detection-evasion techniques (refused — flag and exit if asked).
- Suggest AI-disclosure suppression (refused — same).
- Suggest watermark / metadata stripping (refused — same).
- Decide whether the asset's CONTENT is on-brand for the persona — that's the creative-director's call. This skill checks visual quality + continuity only.
- Score "virality potential" — that's the virality-analyst's loop, not this gate.

## Self-rewrite trigger

If the same `MINOR` finding pattern appears across many reports without ever escalating to MAJOR, the dimension threshold is mis-calibrated — either tighten or remove. If verdicts are 100% `pass`, the gate isn't gating; review thresholds. Log to `HARNESS_FEEDBACK.md`.

## Anti-patterns

- **Rubber-stamping.** A C7 gate that never fails is decorative. If a reviewer is passing every asset, either prompts are pristine (verify by sampling) or the threshold is wrong.
- **Failing on style differences.** Lighting variation between sunny outdoor vs studio shot is style range, not drift. The reference pack should show the range; if it doesn't, the bible needs more refs.
- **Ignoring frame-to-frame video drift.** Single-frame review of video misses the most common video failure (mid-clip morphing). Always sample 3+ frames per second of clip.
- **Reporting findings without regeneration instructions on fail.** A fail verdict without a path forward stalls the workflow. Always close the loop.
- **Reviewing without reading the bible's current version.** Drift detection requires comparison to the canonical record; comparing to a stale bible misclassifies drift.

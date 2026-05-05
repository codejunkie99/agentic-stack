# Persona-Bible Protocol

> Schema + write-discipline for synthetic-character bibles. Used by any
> creative-vertical workflow that needs a durable, version-controlled
> character record. Generic primitive — no niche, no project values
> baked in.

## Why this exists

Synthetic characters drift. Face changes between assets, voice slips
between scripts, worldview muddles across posts. The fix isn't "be
careful" — it's a single canonical record that every downstream
producer (image-gen, video-gen, scriptwriting, editing) reads before
producing, and that gets versioned when it changes.

This protocol defines the schema. Instances of personas live in target
installs (e.g. `.agent/memory/working/personas/<slug>/bible.md`), not
in the harness.

## Schema

A persona-bible is a single Markdown file with the following frontmatter
and required sections. Missing required sections fail the persona's
exit gate from the persona-creation workflow.

### Frontmatter

```yaml
---
persona_slug: <kebab-case slug, no spaces, no project-name leakage>
persona_name: <display name; subject to name_constraints>
niche: <one-line niche descriptor>
worldview_one_line: <one sentence — what this persona believes, in their voice>
created: <YYYY-MM-DD>
version: <integer; increment on substantive edit>
status: <draft | approved | retired>
name_constraints:
  forbidden_substrings: [<list>]   # e.g. ["AI", "GPT", "synthetic"]
  required_register: <e.g. "first-person, conversational">
canonical_visual_refs:
  - <relative path to approved reference image, version-pinned>
  - ...
voice_anchors:
  - <short verbatim phrase the persona would say>
  - ...
---
```

### Required sections

1. **One-sentence summary** — who this persona is, in one line. If you
   can't write the line, the persona isn't ready.
2. **Audience** — who this persona is for. Be concrete: occupation,
   life-stage, what they care about, what they distrust. Avoid
   demographic generalities.
3. **Worldview** — the persona's beliefs, framed positively. What this
   persona is FOR, not just what they're AGAINST. Three to seven
   bullets. Each bullet must be a sentence the persona could say
   on-camera without breaking character.
4. **Voice** — register, sentence length, vocabulary level, energy,
   pacing, recurring rhetorical moves. Concrete enough that a writer
   could pass a blind voice-match test.
5. **Visual identity (pointer)** — link to the visual-style guide
   produced by the visual-identity stage. Bible holds the pointer +
   version-pin, not the assets themselves (those live in the IP
   library per `ip-library.md`).
6. **Content boundaries — would say / would not say** — explicit list.
   At least 5 "would say" examples + 5 "would not say" examples.
   Drives downstream script and image generation.
7. **Recurring catchphrases / motifs** — the persona's signature lines.
   Three to ten. Used by editor agent to keep voice consistent across
   short-form posts.
8. **Commercial path (pointer)** — link to the persona's monetization
   ladder (lives in target install at
   `.agent/memory/working/personas/<slug>/monetization.md`). Bible
   holds pointer only.

## Write discipline

- Only the `persona-architect` agent (or a human) writes to a bible.
  Image-generation, video-generation, and editor agents READ but never
  WRITE.
- Every substantive edit increments `version` in frontmatter and
  appends a one-line entry to a `version_log` section at the end of
  the file: `vN — YYYY-MM-DD — <what changed> — <who>`.
- Status transitions are explicit: `draft → approved` requires a
  realism-review smoke pass on at least 3 generated assets using the
  current bible; `approved → retired` requires a successor slug or a
  human note.

## Read discipline

- Any creative-vertical agent producing an asset for a persona MUST
  open the persona's bible at the start of the task and confirm:
  - the bible's `version` matches the version the IP library has
    cached prompts against; if not, regenerate prompts before
    producing
  - the asset request is consistent with the persona's content
    boundaries (would-say / would-not-say lists)
  - any visual asset request honors the canonical visual refs

## Drift detection

The `character-continuity` checkpoint (in the content-pipeline
workflow's QA stage) runs against the current bible. Drift findings
write to `.agent/memory/working/personas/<slug>/drift-log.md` in the
target install. Three consecutive drift findings on the same dimension
(face, voice, worldview, motifs) trigger a bible review — either the
bible is under-specifying the dimension, or producers are ignoring it.

## What this protocol does NOT define

- The persona's actual name, niche, or content (target-install
  concern).
- Risk register, banned phrases, avoid topics — explicitly out of
  scope per project decision 2026-05-05.
- Visual asset storage layout (see `ip-library.md`).
- Per-platform formatting (see `content-pipeline.md` workflow).

## Related primitives

- `ip-library.md` — where bibles, prompts, and approved assets live
  on disk.
- `viral-pattern-library.md` — how viral patterns get adapted per
  bible's voice and boundaries.
- `analytics-loop.md` — how performance data feeds back into bible
  revision triggers.
- `content-pipeline.md` workflow — orchestrates bible reads at every
  production stage.

## Status

Authored 2026-05-05 as part of creative-vertical PR1. No prior version.

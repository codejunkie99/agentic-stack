# IP-Library Protocol

> On-disk taxonomy + naming + drift-check contract for
> creative-vertical IP assets (persona bibles, master prompts,
> approved images, video clips, thumbnails, captions, music notes,
> reusable templates).

## Why this exists

Creative production generates a flood of assets. Without a canonical
layout, producers re-roll the same prompts, lose track of which
references were approved, and silently drift the persona's look.
This protocol defines the directory shape, naming convention, and
the drift-check contract so any agent can find the canonical version
of any asset by path alone.

The library lives in target installs at
`.agent/memory/working/ip-library/` (or equivalent path declared in
the install's config). Schema is defined here; instances live there.

## Directory layout

```
ip-library/
├── personas/
│   └── <persona-slug>/
│       ├── bible.md                       # canonical persona record (per persona-bible.md)
│       ├── version-log.md                 # append-only: vN, date, what changed
│       ├── visual/
│       │   ├── reference-pack/            # approved character ref images
│       │   │   ├── face-front-v1.png
│       │   │   ├── face-3q-v1.png
│       │   │   └── _APPROVED.md           # which refs are canonical
│       │   ├── wardrobe/
│       │   ├── environments/
│       │   └── style-guide.md             # palette, lighting, camera, motifs
│       ├── prompts/
│       │   ├── master-image.prompt.md     # base image prompt
│       │   ├── master-video.prompt.md     # base video prompt
│       │   ├── negative.prompt.md         # negative-prompt list
│       │   └── prompt-version-log.md
│       ├── voice/
│       │   ├── tone-samples.md            # short verbatim samples
│       │   ├── catchphrases.md
│       │   └── voice-clone-config.md      # if applicable
│       └── posts/
│           └── <YYYY-MM-DD>-<post-slug>/
│               ├── script.md
│               ├── shot-list.md
│               ├── assets/                # generated raw assets used in this post
│               ├── final/                 # platform-ready exports (tiktok.mp4, reels.mp4, ...)
│               ├── caption.md
│               ├── thumbnail.png
│               ├── continuity-report.md   # output of realism-review skill
│               └── analytics.json         # post-publish metrics, written by analytics-loop
├── viral-patterns/                        # per viral-pattern-library.md
├── shared-templates/                      # cross-persona reusable bits
└── _index.md                              # human-readable map
```

## Naming convention

- All directories: kebab-case, lowercase, no spaces, no caps.
- Persona slugs are stable forever — once `foreman` is a slug, it
  stays `foreman` even if the display name changes. Display name
  rename = bible version bump, not slug change.
- Post directories: `YYYY-MM-DD-<short-slug>`. Date is the post's
  scheduled publish date, not generation date.
- Asset files: `<purpose>-<variant>-v<N>.<ext>`
  (e.g. `face-front-v3.png`, `master-image-v2.prompt.md`).
  Versions monotonically increase. Never overwrite a `vN`.
- `_APPROVED.md` files declare which version is canonical. Producers
  read `_APPROVED.md` first; only fall back to scanning when the
  file is missing.

## Approval contract

An asset is "approved" only when:

1. It appears (with its version pin) in the relevant `_APPROVED.md`.
2. It has a corresponding entry in the persona's `version-log.md`
   referencing the bible version it was approved against.
3. It passed realism-review (a continuity-report.md exists with a
   pass verdict, or it's a manually approved reference asset).

Producers MUST NOT use unapproved assets in published output. The
content-pipeline workflow's QA stage gates on this.

## Drift-check contract

The `character-continuity` checkpoint (run during the content-pipeline
QA stage) compares each new asset against the persona's
`reference-pack/` and emits a `continuity-report.md`. Required fields:

```yaml
---
post_slug: <YYYY-MM-DD-<short-slug>>
persona_slug: <slug>
bible_version: <integer; the bible version asset was generated against>
checked_at: <YYYY-MM-DDTHH:MM:SSZ>
verdict: pass | fail | manual-review
---
```

Body sections:

1. **Asset(s) checked** — list with paths.
2. **Reference set** — which `reference-pack/` versions were used
   for comparison.
3. **Findings** — one row per finding, dimensions: face / wardrobe /
   environment / palette / lighting / motifs / text-rendering /
   anatomical (hands, eyes, teeth) / logo / continuity-with-prior-post.
4. **Regeneration instructions** — if `verdict: fail`, what prompt or
   reference change to make.

Three consecutive fails on the same dimension trigger a bible review
per `persona-bible.md`'s drift-detection clause.

## Read discipline for downstream agents

Any agent producing an asset MUST read, in order:

1. The persona's `bible.md` (current frontmatter version).
2. `prompts/master-*.prompt.md` for the relevant medium.
3. `_APPROVED.md` in the relevant `reference-pack/` to confirm
   which refs are canonical.

Skipping any step = drift risk. The content-pipeline workflow
declares this as a hard precondition on its production stages.

## Write discipline

- Append-only for `version-log.md`, `prompt-version-log.md`,
  `_APPROVED.md`. Never rewrite history.
- Approved assets (anything in `reference-pack/` or marked in
  `_APPROVED.md`) are immutable. To "change" an approved asset,
  add a new version and update `_APPROVED.md` to point at it.
- The IP library is the source of truth. If a producer's local copy
  of a prompt drifts from the library, the library wins.

## What this protocol does NOT define

- Storage backend (local FS, Drive, S3, Notion) — install-specific.
  The schema is portable; the mount point isn't.
- Per-platform export specs — see `content-pipeline.md`.
- Analytics field schema — see `analytics-loop.md`.

## Status

Authored 2026-05-05 as part of creative-vertical PR1.

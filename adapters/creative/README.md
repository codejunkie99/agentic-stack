# Creative Adapter

Optional adapter for the creative-content-production vertical
(synthetic-character short-form content, multi-persona portfolios,
analytics-driven virality loops).

Sibling to `adapters/bcg/` (consulting vertical) and
`adapters/claude-code/` (SDLC roster, always installed).

## When this adapter mounts

This adapter is conditional on `.agent/config.json` having
`creative_adapter: "enabled"`. When disabled (default), no
creative-vertical agents load and no creative skills register.
SDLC + BCG verticals are unaffected either way.

## What's in here

```
adapters/creative/
├── README.md                              (this file)
└── agents/
    └── creative-researcher.md             (PR1)
```

PR1 ships only `creative-researcher`. Subsequent PRs add the rest of
the creative roster:

- `persona-architect` — drafts and maintains persona bibles
- `visual-identity` — defines persona look + master prompts
- `character-continuity` — runs realism-review skill at QA stage
- `content-strategist` — builds weekly content plans, selects
  patterns from the viral-pattern library
- `hook-and-script` — writes short-form scripts
- `creative-director` — converts scripts into shot lists + visual
  plans
- `image-gen` / `video-gen` — produce raw assets per master prompts
- `editor` — assembles platform-ready exports
- `virality-analyst` — runs the analytics-loop, emits winners.md
- `engagement` — drafts replies, surfaces buyer signals

These names match the agents referenced by
`.agent/workflows/content-pipeline.md`. PR1 ships the workflow's
research-stage owner only; downstream stages run via inline
prompts or human operators until subsequent PRs land the full
roster.

## Protocols this adapter relies on

All four are in `.agent/protocols/` (shared, not adapter-scoped):

- `persona-bible.md` — character schema + write discipline
- `ip-library.md` — on-disk asset taxonomy + drift-check contract
- `analytics-loop.md` — KPI schema + winner classification
- `viral-pattern-library.md` — pattern schema + hook taxonomy

And one skill:

- `.agent/skills/realism-review/SKILL.md` — continuity QA gate

## What this adapter does NOT include

- Specific personas, niches, or content (target-install concern).
- Platform integrations (TikTok / IG / YouTube APIs) — install's
  responsibility.
- Detection-evasion or AI-disclosure suppression — explicitly out of
  scope across all creative-vertical primitives.
- Risk register / banned-phrases enforcement (dropped per project
  decision 2026-05-05).

## Status

PR1 — creative-vertical bootstrap. Authored 2026-05-05.

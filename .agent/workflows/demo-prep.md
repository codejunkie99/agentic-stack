---
workflow_id: demo-prep
name: Package a Prototype for Demo / Showcase
team_structure: flat
description: Take a working prototype + LEARNINGS.md and package them for stakeholder showcase — clean README, runnable demo command, talk-track, narrated GIF/screenshots, fallback in case live demo fails. Distinct from production release (release-manager); this is throwaway-grade packaging for a meeting.
---

## Purpose

Make a prototype demoable to a non-technical stakeholder in a meeting. The
prototype already validated the hypothesis (output of `prototype-app.md` or
`feature-prototype.md`); this workflow makes it presentable.

## Trigger phrases

"package the prototype for demo", "prep this for the partner showcase",
"demo prep", "make the prototype demoable", "showcase prep".

## Team

Single agent (engineer or prototype-engineer who built the spike) plus the
`demo-prep` skill.

| Phase | Agent + skill | Output |
|---|---|---|
| Package | engineer/prototype-engineer + `demo-prep` skill | `output/demo/<slug>/` package |

## Demo package contents

- `README.md` — what the prototype does, how to run it (one command), what
  it validates, what it skips
- `demo-script.md` — talk-track for the live demo: narrative arc (3-5 min),
  what to point out, what to avoid clicking
- `screenshots/` — 3-5 hero screenshots in case live demo fails
- `demo.gif` (optional) — narrated screen recording if budget allows
- `q-and-a.md` — anticipated questions + concise answers (limitations,
  scope, what production would change)
- `fallback.md` — what to say if the live demo fails ("here's the GIF,
  here's the rationale, the prototype validated X")

## Quality gates

- One-command demo run from clean clone (`./demo.sh` or equivalent)
- Screenshots cover the golden path
- Talk-track is 3-5 min for the primary audience size
- Q&A covers the top 3 anticipated questions

## Memory write discipline

`memory_reflect` at importance 7, pain 4. Capture lessons about demo
patterns that worked / didn't work for future prototype showcases.

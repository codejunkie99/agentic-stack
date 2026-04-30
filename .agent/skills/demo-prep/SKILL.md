---
name: demo-prep
description: Use proactively when packaging a prototype or feature for stakeholder showcase. Triggers on "prep this for demo", "package the prototype", "make this demoable", "showcase prep", "demo script", "live demo of [thing]". Produces README + demo-script + screenshots + Q&A + fallback. Distinct from production release (release-manager); this is throwaway-grade packaging for a meeting.
version: 2026-04-30
triggers: ["prep this for demo", "package the prototype", "make this demoable", "showcase prep", "demo script", "live demo of"]
tools: [bash, memory_reflect]
preconditions: ["prototype or feature exists at output/prototypes/<slug>/ or similar location", "user has stated the audience and time-budget for the demo"]
constraints: ["never modify the prototype's source code as part of demo prep", "live demo command must run from clean clone in one step", "demo-script time-box is the audience time minus 2 min for Q&A"]
---

# Demo Prep — package a prototype for stakeholder showcase

Goal: take a working prototype and the user's audience + time-budget,
produce a tight package that lets the user (or whoever runs the demo)
walk a stakeholder through the prototype confidently — including a
fallback if the live demo fails.

## When this fires

- User says "prep [prototype] for the partner demo"
- User says "package this for a showcase"
- prototype-engineer or feature-prototype workflow exit signals
  "prototype is validation-passing, demo prep next"

## What it produces

In `output/demo/<prototype-slug>/`:

- `README.md` — what the prototype does, how to run it (one command),
  what it validates, what it explicitly skips
- `demo-script.md` — talk-track for the live demo: 3-5 min narrative
  arc (or whatever the audience time-box minus 2 min for Q&A); what to
  point out, what to avoid clicking, transition language between sections
- `screenshots/` — 3-5 hero screenshots in case live demo fails or
  audience can't see screen
- `q-and-a.md` — anticipated questions + concise answers; covers the
  top 3 likely concerns (limitations, scope, "what would production
  change?")
- `fallback.md` — what to say if the live demo fails ("here's the
  GIF, here's what it validated, here's the path to production")

Optional (if budget allows):
- `demo.gif` — narrated screen recording

## Steps

1. **Read the prototype.** `output/prototypes/<slug>/HYPOTHESIS.md`,
   `LEARNINGS.md`, the code if needed. Confirm the prototype actually
   runs.
2. **Ask user the demo context** (audience, time-budget, format —
   live screenshare / in-room / async record). If user already gave
   this in the trigger, skip.
3. **Write README.md.** Audience-aware. One-command-run. Limits stated
   honestly.
4. **Write demo-script.md.** Time-budgeted talk-track. Each section
   has: spoken intro, what to click, expected reaction, transition.
5. **Capture screenshots.** Run the prototype, capture the golden-path
   surfaces. 3-5 frames.
6. **Write q-and-a.md.** Top 3-5 anticipated questions with concise
   answers. Skip philosophical; focus on practical (cost, scope,
   timeline, what's missing, when can production ship).
7. **Write fallback.md.** "If the live demo fails, here's what to
   say." Honest about the failure path; uses screenshots.
8. **Test the run command from a clean clone.** Document any setup
   friction. The demo command must work first-try.
9. **Stop and ask.** User reviews the package; iterate before the
   actual demo.

## Memory write discipline (at exit)

```bash
python3 .agent/tools/memory_reflect.py "demo-prep" \
  "demo-package produced for <prototype-slug>" \
  "<prototype-slug>: <audience>; time-box <N>min; <demo-format>" \
  --importance 7 --pain 4 \
  --note "DURABLE LESSON: <transferable demo-prep insight — e.g. 'partner audiences want fallback-first language; engineering audiences want scope-honest limits up front'> | WHAT WORKED IN PRIOR DEMOS: <patterns reused> | NEW LEARNING: <if any>"
```

## Self-rewrite hook

After every 3 demo packages produced, re-read the last 3
`demo-prep` episodic entries. If patterns emerged about what
audience-types want, what fallback-format works best, or what live-demo
failure modes to anticipate, update this SKILL.md. Commit:
`skill-update: demo-prep, <one-line reason>`.

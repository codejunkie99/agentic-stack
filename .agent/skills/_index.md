# Skill Registry

Read this file first. Full `SKILL.md` contents load only when a skill's
triggers match. Machine-readable equivalent: `skills/_manifest.jsonl`.
Each entry below is a pointer + trigger phrases — load the full SKILL.md
on match.

## SDLC pipeline

- **planner** — multi-step plans with destinations & fences. Triggers:
  "make a plan", "decompose this task", "writing-plan"
- **product-discovery** — frame the problem before solving. Triggers:
  "what should we build", "discovery", "user research"
- **requirements-writer** — turn discovery into testable requirements.
  Triggers: "requirements doc", "spec out", "BRD / PRD"
- **story-decomposer** — break PRD into atomic implementable stories.
  Triggers: "break down", "user stories", "decompose feature"
- **spec-reviewer** — adversarial pre-build review on requirements.
  Triggers: "review the spec", "spec critique", "is this ready to build"
- **architect** — system architecture decisions. Triggers:
  "architecture", "system design", "component diagram", "ADR"
- **implementer** — write code following plan + tests. Triggers:
  "implement", "build this", "code it"
- **test-writer** — TDD test design + coverage. Triggers:
  "write tests", "test plan", "TDD"
- **code-reviewer** — adversarial review with confidence ≥ 80 filter.
  Triggers: "review the code", "PR review", "code review"
- **release-notes** — audience-sectioned release notes. Triggers:
  "release notes", "changelog entry", "what's in this release"
- **deploy-checklist** — pre-deploy verification gate. Triggers:
  "deploy", "ship", "release", "go live". Constraints: tests pass, no
  unresolved TODOs in diff, human approval for production.
- **demo-prep** — package a prototype for stakeholder showcase.
  Triggers: "prep this for demo", "package the prototype", "make this
  demoable", "showcase prep", "demo script", "live demo of".

## Memory + harness meta

- **skillforge** — create new skills from recurring patterns. Triggers:
  "create skill", "new skill", "I keep doing this manually"
- **memory-manager** — read/score/consolidate memory. Triggers:
  "reflect", "what did I learn", "compress memory"
- **git-proxy** — all git operations with safety. Triggers:
  "commit", "push", "branch", "merge", "rebase". Constraints: never
  force-push to main, tests-before-push.
- **debug-investigator** — systematic reproduce → isolate → hypothesize.
  Triggers: "debug", "why is this failing", "investigate"

## Knowledge work + analysis

- **analysis** — structured analytical decomposition with confidence
  + sensitivity. Triggers: "analyze this", "market sizing",
  "benchmarking", "driver analysis", "scenario analysis"
- **context-search** — retrieve project context with citations.
  Triggers: "find context on", "what do we know about", "pull background"
- **document-assembly** — mechanical assembly from source drafts.
  Triggers: "stitch the doc", "assemble the deck", "merge sections"
- **draft-status-update** — weekly status from action tracker + RAID.
  Triggers: "draft weekly status", "this week's update"
- **review** — adversarial review of any deliverable. Triggers:
  "review this", "find issues", "critique"
- **design-md** — DESIGN.md-driven visual design system work.
  Triggers: "DESIGN.md", "Stitch", "design tokens", "visual design".
  Precondition: DESIGN.md exists at project root.

## Engagement setup

- **client-onboarding** — bootstrap new engagement: scaffold
  client/<slug>/, set active_client, prompt for upload pack.
  Triggers: "new engagement", "start client", "onboard client"
- **document-researcher** — bounded summary per upload + INDEX entry.
  Triggers: "summarize this document", "researcher", "index this upload"

## Deliverable production

- **consulting-deck-builder** — MBB 3-phase deck workflow:
  Storyboard → Content (all slides at once with stickies) → Format.
  Triggers: "build a deck", "storyboard", "iterate on slides",
  "structure the storyline"

## Operations + telemetry

- **data-layer** — local cross-harness activity dashboard.
  Triggers: "show me the dashboard", "what did my agents do",
  "agent analytics", "TUI"
- **data-flywheel** — approved-run export to trace records / context
  cards / eval cases / training-ready JSONL. Triggers:
  "data flywheel", "trace to train", "training traces", "eval cases"

# Skill Registry

Read this file first. Full `SKILL.md` contents load only when a skill's
triggers match the current task. Machine-readable equivalent:
`skills/_manifest.jsonl`.

## skillforge
Creates new skills from observed patterns and recurring tasks.
Triggers: "create skill", "new skill", "I keep doing this manually"

## memory-manager
Reads, scores, and consolidates memory. Runs reflection cycles.
Triggers: "reflect", "what did I learn", "compress memory"

## git-proxy
All git operations with safety constraints.
Triggers: "commit", "push", "branch", "merge", "rebase"
Constraints: never force push to main; run tests before push.

## debug-investigator
Systematic debugging: reproduce, isolate, hypothesize, verify.
Triggers: "debug", "why is this failing", "investigate"

## deploy-checklist
Pre-deployment verification against a structured checklist.
Triggers: "deploy", "ship", "release", "go live"
Constraints: all tests passing, no unresolved TODOs in diff,
requires human approval for production.

## design-md
Uses a root `DESIGN.md` as the portable visual system contract for
Google Stitch workflows. Loads only when `DESIGN.md` exists at the
project root.
Triggers: "DESIGN.md", "design.md", "Google Stitch", "design tokens",
"design system", "visual design"
Preconditions: DESIGN.md exists at project root.
Constraints: prefer DESIGN.md tokens over invented values, do not modify
DESIGN.md unless the user explicitly asks, preserve unknown sections when
an edit IS authorised, validate with `npx @google/design.md lint DESIGN.md`
when available.

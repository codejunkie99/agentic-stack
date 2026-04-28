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

## data-layer
Cross-harness activity monitoring and dashboard exports. Use it as the
injected dashboard surface when users ask naturally.
Triggers: "data layer", "dashboard", "show me the dashboard",
"what did my agents do", "agent analytics", "agent status", "resource usage",
"usage report", "cron monitoring", "daily report", "tokens",
"terminal dashboard", "TUI"
Constraints: local-only by default; no screenshot delivery without explicit user
approval; do not commit private `.agent/data-layer/` exports.

## data-flywheel
Turns approved, redacted runs into reusable local artifacts: trace records,
context cards, eval cases, training-ready JSONL, and flywheel metrics.
Triggers: "data flywheel", "trace to train", "training traces",
"context cards", "eval cases", "approved runs", "vertical intelligence"
Constraints: local-only by default; human-approved runs only; redaction required
before trainable; does not train models.

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

## planner
Turns a spec into task-by-task implementation plan an engineer with zero
codebase context can execute end-to-end.
Triggers: "implementation plan", "break this down", "plan this feature"
Constraints: no placeholders, code shown in every step, TDD ordering.

## product-discovery (PDLC entry)
Validates a problem before any design: named user, named status quo,
narrow wedge, observable behavior, measurable success criteria.
Triggers: "I have an idea", "is this worth building", "help me think through"
Constraints: no implementation until a design is approved; no category users.

## requirements-writer
Turns a validated problem into a spec with given/when/then acceptance,
declared scope mode (Expansion/Selective/Hold/Reduction), and non-goals.
Triggers: "write the spec", "write requirements", "acceptance criteria"
Constraints: no wish words; every requirement traces to a problem line.

## story-decomposer
Splits a feature into independently-shippable, vertically-sliced stories
sized under a week with named dependencies and blast radius.
Triggers: "break into stories", "user stories", "split this feature"
Constraints: INVEST-compliant; no horizontal layer splits; no technical tasks.

## spec-reviewer (PDLC→SDLC gate)
Grades a spec with a 0-10 rubric + "what a 10 looks like" gap statements,
coverage matrix, confidence-filtered gap list, explicit go/no-go verdict.
Triggers: "review the spec", "go/no-go", "is this ready to build"
Constraints: confidence ≥ 80 filter; no "LGTM" without evidence.

## architect
Produces system design: ASCII component diagram with typed interfaces,
data flow with failure branches, edge-case matrix, test-seam list,
assumption ledger.
Triggers: "design the system", "architecture for this", "data flow"
Constraints: no UML-for-UML's-sake; every component has a test seam.

## implementer
Executes a plan task-by-task under strict TDD (Red-Green-Refactor),
one commit per task, fresh subagent per task when available.
Triggers: "implement this plan", "execute the plan", "start coding"
Constraints: Iron Law — no production code before a failing test;
one task per commit; no silent plan edits.

## test-writer
Writes tests that would fail on regression: right pyramid layer, DAMP names,
refactor-resilient, behavioral coverage over line coverage.
Triggers: "write tests", "test coverage", "add regression tests"
Constraints: every test has an assertion; no implementation coupling;
no framework tests.

## code-reviewer (pre-merge)
Adversarial diff review with confidence ≥ 80 filter, severity tiers
(Critical 90-100 / Important 80-89), CRITICAL checklist (SQL/LLM-trust/
race/shell/enum). Also governs review reception — verify before
implementing.
Triggers: "review this code", "check my changes", "code review"
Constraints: no LGTM without checklist; no performative agreement when receiving.

## release-notes
Translates a diff into audience-sectioned notes (users/operators/devs)
with breaking-change upgrade paths and semver-grounded version bump.
Triggers: "write release notes", "update the changelog", "what changed"
Constraints: no misc-fixes bucket; every entry traces to a commit/PR;
breaking changes carry explicit upgrade path.

---

Knowledge-work skills below are bootstrapped from the harness-starter-kit
(Kenneth Leung, BCG) in Step 8.1. They are imported verbatim with minimal
frontmatter; path references and triggers will be adapted to agent-stack
conventions in Step 8.2.

## analysis (knowledge-work)
Structured analytical work on case/engagement questions — sizing,
benchmarking, driver decomposition, scenario analysis, feasibility.
Triggers: "analyze this", "market sizing", "what drives", "is this feasible"
Constraints: every finding has So-What + confidence; assumptions explicit;
top-2–3 sensitivity drivers surfaced.

## review (knowledge-work)
Reviews narrative/analytical deliverables (decks, memos, status updates)
and produces a verdict (approved/revise/reject) with severity-graded
findings. Distinct from code-reviewer, which reviews diffs.
Triggers: "review this deliverable", "verdict on", "partner review"
Constraints: never produces content; every finding cites a location;
one issue per entry.

## document-assembly (knowledge-work)
Mechanical assembly of section drafts into a final deliverable —
section-completeness check, canonical ordering, coherence pass, ToC,
metadata, placeholder flagging.
Triggers: "assemble document", "compile the deck", "merge section drafts"
Constraints: no new content invented; gaps flagged as [PLACEHOLDER: ...];
source drafts tracked in trailing block.

## context-search (knowledge-work)
Retrieves structured project context (client facts, decisions, constraints,
transcripts, frameworks) before analysis or drafting. Not a substitute for
memory recall — this searches project context, not agent memory.
Triggers: "find context on", "what do we know about", "pull the background"
Constraints: read-only; cite sources explicitly; flag gaps as
[CONTEXT GAP: ...]; surface contradictions, never resolve silently.
Paths adapted in Step 8.2.3 to `.agent/memory/client/<active_client>/`
(client-scoped) + `adapters/<firm>/context/` (firm-scoped).

## draft-status-update (knowledge-work)
Drafts a weekly status update from the action tracker, RAID log, and
workstream pages. Produces a draft for human edit — never auto-publishes.
Section order follows firm adapter's formatting conventions
(e.g. `adapters/bcg/protocols/formatting.md`).
Triggers: "draft weekly status", "this week's update", "weekly status draft"
Constraints: never publish directly; executive summary partner-readable
in 30 seconds; wins first, then risks; specificity over vagueness.

## client-onboarding (engagement-setup)
Bootstraps a new engagement: confirms slug, scaffolds
`.agent/memory/client/<slug>/` from `_template/`, sets `active_client`
in `config.json`, initializes `INDEX.md`, and prompts the user to drop
briefing files into `raw-uploads/` for `document-researcher` to summarize.
Never auto-loads raw uploads — INDEX.md is the only eager surface.
Triggers: "new engagement", "start client", "onboard client", "set up engagement"
Constraints: never overwrite existing client/<id>/INDEX.md silently;
never load raw uploads into context.

## document-researcher (engagement-setup)
Summarizes a single document dropped into a client's `raw-uploads/`,
demanding a one-line user description first. Produces a bounded summary
at `summaries/<filename>.md` and appends a Documents-table row to the
client's `INDEX.md`. Drives the lazy-load pattern.
Triggers: "summarize this document", "researcher", "index this upload"
Constraints: mandatory user description; bounded summary length;
never auto-load raw upload content into broader session context.

## consulting-deck-builder (deliverable-production)
Builds an MBB-quality deck through three mandatory phases — Storyboard
(spine + horizontal-MECE check) → Content (per-slide vertical-logic
draft with stickies, all slides at once) → Format (visualization).
Never skips a phase. Action-voice titles only. Stickies (CONTENT /
LAYOUT / TODO) migrate through phases.
Triggers: "build a deck", "storyboard", "iterate on slides",
"structure the storyline", "vertical horizontal logic check"
Constraints: phase boundaries require explicit user sign-off;
every slide passes vertical-logic check; deck spine passes MECE;
lazy-load source material from summaries/ first.

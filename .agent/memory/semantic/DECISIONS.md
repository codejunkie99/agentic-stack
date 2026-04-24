# Major Decisions

> Record architectural or workflow choices that would be costly to re-debate.
> Use this template for each entry:

## YYYY-MM-DD: Decision title
**Decision:** _what was chosen_
**Rationale:** _why, in one or two sentences_
**Alternatives considered:** _what else was on the table and why rejected_
**Status:** active | revisited | superseded

## 2026-01-01: Four-layer memory separation
**Decision:** Split memory into working / episodic / semantic / personal rather than one flat folder.
**Rationale:** Each layer has different retention and retrieval needs. Flat memory breaks at ~6 weeks.
**Alternatives considered:** Flat directory (fails at scale), vector store (over-engineered for single user).
**Status:** active

## 2026-04-23: First PDLC/SDLC skill — `planner` — authored as the template-setter
**Decision:** Write `planner` first of the ten PDLC/SDLC skills, using superpowers `writing-plans` as the primary source and applying the "destinations and fences" transform. Synthesize YAML shape from skillforge (agentic-stack native) with description style from Anthropic's `skill-creator` (pushy, trigger-focused). Skip the skill-creator eval loop for v1.
**Rationale:** The plan (Step 4) designates planner as the template the remaining nine skills inherit from — voice, frontmatter shape, recall-first block, self-rewrite hook. Superpowers-only (no gstack /autoplan pull) keeps v1 focused; cross-reference pulls deferred until real-usage friction surfaces gaps. Eval loop deferred because we have no baseline usage data to compare against — iterate via the dream cycle on real plans instead.
**Alternatives considered:** (a) Start with `product-discovery` as PDLC entry point — rejected because SDLC discipline has more immediate value for Pulkit's current workflow. (b) Run full skill-creator eval loop on v1 — rejected as premature without real plans to evaluate. (c) Blend superpowers + gstack in v1 — rejected to keep the template minimal and the provenance clean.
**Status:** revisited — the superpowers-only scope was reversed same-day (see next entry); core template-setter decision stands.

## 2026-04-23: Step 6 — PDLC/SDLC subagent team + delegation pipeline shipped
**Decision:** Create five Claude Code subagent definitions in `.claude/agents/` (`product-manager`, `architect`, `engineer`, `reviewer`, `release-manager`) following the superpowers + pr-review-toolkit frontmatter conventions (`description` with `<example>` blocks, "You are a [ROLE]" opening, explicit "DOES NOT" lane-markers, scoped tools allowlist, model choice by role reasoning-load — opus for architect/reviewer, sonnet for product-manager/engineer/release-manager). Extend `.agent/protocols/delegation.md` with an explicit PDLC→SDLC handoff pipeline specifying per-stage inputs, skills, outputs, and handoff destinations. Every subagent starts its session by running `python3 .agent/tools/show.py` for situational awareness. Hard rules: no stage skips, no recursive delegation, escalation-back is data (not failure), every handoff logs to episodic with pain score.
**Rationale:** The ten skills shipped in Steps 4–5 are the atomic capabilities; subagents are the organizational unit that binds skills into a pipeline. Without subagent definitions, the skills are invokable only ad-hoc — no enforced PDLC→SDLC ordering, no audit trail across handoffs, no "which stage owns what" mapping. The subagent files become the org chart the dispatcher reads before routing work. Model choice reflects reasoning load: architect and reviewer get opus because design and adversarial review are the highest-reasoning stages; product-manager / engineer / release-manager get sonnet because their work is more execution-flavored (though not trivial). The `show.py` start-of-session convention ensures every dispatched subagent sees the 14d activity sparkline, pending review candidates, and failing skills before touching anything — a non-optional orientation step.
**Alternatives considered:** (a) Flatten into two agents (planner + doer) — rejected because it collapses the PDLC/SDLC distinction and loses the natural review + release boundaries. (b) One agent per skill (ten agents) — rejected because most skills belong in the same job (e.g. planner + implementer + test-writer are all "engineer's work"). Five stages maps cleanly to the plan's PDLC→SDLC arc. (c) No subagents, pure root-agent skill dispatch — rejected because Step 8+ needs the sandbox dry-run to actually dispatch agents, and without agent definitions the subagent_type values have nothing to reference. (d) Let each subagent dispatch sub-subagents (fan-out style) — rejected because it breaks the hard-cap and makes the pipeline illegible; all re-dispatch goes through ROOT instead.
**Status:** active

## 2026-04-23: Step 5 sweep — remaining 9 PDLC/SDLC skills authored in one pass
**Decision:** Draft and ship all nine remaining PDLC/SDLC skills — `product-discovery`, `requirements-writer`, `story-decomposer`, `spec-reviewer`, `architect`, `implementer`, `test-writer`, `code-reviewer`, `release-notes` — in a single Option-C commit, following the template established by `planner` (v2 with gstack `/autoplan` decision principles). Each skill was bootstrapped from its mapped sources per the plan's unified mapping table: superpowers (brainstorming, writing-plans, test-driven-development, executing-plans, subagent-driven-development, receiving-code-review, pr-review-toolkit:code-reviewer, pr-review-toolkit:pr-test-analyzer) + gstack (office-hours, plan-ceo-review, plan-eng-review, plan-design-review, qa, review, codex, document-release, autoplan). The three plan-designated "user-customized" skills (`architect`, `code-reviewer`, `release-notes`) were also drafted by the agent at the user's explicit direction ("I do not have any specifics to add right now — please use best practice and leverage the text and learnings").
**Rationale:** Per Option-C cadence (draft all 6 bootstrappable + ship, then pause for the 3 customized), the user elected to include the 3 customized in the same sweep using best-practice defaults grounded in the source material. The alternative — leaving 3 skills half-written as TODO shells — would have broken the PDLC→SDLC pipeline, blocking Step 6 (subagent definitions) and Step 7 (delegation.md extension). The full template is now locked in across all 10 skills; voice, frontmatter shape, recall-first block, destinations/fences discipline, confidence-≥80 filter (in reviewer skills), decision-classification hooks (Mechanical/Taste/User-Challenge), and self-rewrite hooks are uniform. Future iteration happens on real usage, not on scaffold polish.
**Alternatives considered:** (a) Per-skill approval and per-skill commit (Option A) — rejected because the user explicitly chose Option C for speed. (b) Leave `architect`, `code-reviewer`, `release-notes` as user-fill-later stubs — rejected because the user explicitly declined to hold them for customization. (c) Fetch and paste more verbatim from source skills — rejected because source skills use imperative "driving directions" voice; the agentic-stack template requires "destinations and fences" transform.
**Status:** active

## 2026-04-23: `planner` — pull gstack `/autoplan` decision principles into v1
**Decision:** Add gstack `/autoplan`'s 6 Decision Principles (completeness, boil-lakes, pragmatic, DRY, explicit-over-clever, bias-toward-action) and the Mechanical/Taste/User-Challenge decision classification into `planner/SKILL.md`. Source attribution updated in frontmatter + `_manifest.jsonl`.
**Rationale:** Pulkit flagged the value directly after the v1 ship: these aren't just decomposition heuristics — they're principles that let the planner auto-resolve intermediate choices without stalling, and the classification framework tells the planner *when to decide silently vs surface a choice to the user*. That second part is the genuinely new capability the superpowers source didn't cover. Same-day reversal is appropriate because the cost of the pull is low (~20 lines) and the downstream template (nine more skills) benefits from the richer decision vocabulary from the start.
**Alternatives considered:** (a) Keep superpowers-only and defer — rejected because the nine subsequent skills will inherit from whatever shape `planner` settles into; baking the decision framework in now saves nine later retrofits. (b) Pull the full `/autoplan` pipeline (phases, codex review, etc.) — rejected as out of scope for a `planner` skill; those belong in `spec-reviewer` and a future `auto-review` orchestration if needed.
**Status:** active

## 2026-04-24: Step 8.0 — housekeeping + BCG-adapter scaffold before sandbox install
**Decision:** Split the original "Step 8: sandbox install + end-to-end run" into a preflight (Step 8.0) + import (Step 8.1) + agent-tuning (Step 8.2) + real-case dry-run (Step 8.3) sequence. Step 8.0 lands five scaffold commits:

1. Relocate 5 subagents from repo-root `.claude/agents/` → `adapters/claude-code/agents/`. Extend `install.sh` claude-code branch to copy `$SRC/agents/*.md` → `$TARGET/.claude/agents/`. Symlink `.claude/agents` → `../adapters/claude-code/agents` so fork-local Claude Code sessions see agents through a single source of truth.
2. Create `examples/pdlc-sandbox/` as a tracked throwaway install target with README documenting purpose + gitignored install artifacts (`.agent/`, `.claude/`, `CLAUDE.md`, `memory/`, `output/`).
3. Expand `adapters/bcg/` stub into 11-subdirectory scaffold (`scripts/`, `commands/`, `protocols/`, `templates/`, `context/{firm,frameworks,glossary,industries}/`, `personas/`, `skills/`, `mcp/`) with `.gitkeep` placeholders. Rewrite README to document the ambient-loading model: "BCG context is ambient whenever the adapter is loaded — no need to annotate tasks with 'this is BCG'."
4. Adopt Kenneth Leung's personas pattern (reviewer style overlays — demands, rejection criteria, voice). Split by specificity: `.agent/personas/` generic-shareable + `adapters/bcg/personas/` BCG-private (gitignored except README + `_template.md`).
5. Add `.agent/config.json` toggle with `bcg_adapter` + `active_client` fields (default `"disabled"` + `null`). Document in `.agent/AGENTS.md` Config section. Extend `adapters/claude-code/CLAUDE.md` session-start protocol with a conditional-mount block that reads config.json and mounts `adapters/bcg/` content when enabled.

Smoke-test verified: `./install.sh claude-code examples/pdlc-sandbox --yes` produces all 5 subagents + `.claude/settings.json` + `.agent/` brain + `CLAUDE.md` in target with zero drift; install artifacts correctly gitignored.

**Rationale:** Two structural defects blocked the original Step 8: (a) subagents lived outside the adapter tree so `install.sh` had no path to propagate them — a sandbox install produced zero subagents and the 10-point verification test could not pass; (b) no BCG adapter infrastructure existed, making the planned Step 8.1 import of `harness-starter-kit` homeless. Splitting Step 8 into 8.0 (pre-flight fixes) + 8.1 (import) + 8.2-3 (agent tuning + real-case run) lets each commit stay atomic and testable. The ambient-loading model for BCG context (config flag → CLAUDE.md conditional → agents see merged context → tools/commands register conditionally) resolves the "do I have to prefix tasks?" question: no, because the adapter is enabled-by-default only on the working-project install, and that install's entire posture is BCG-bound.

**Alternatives considered:** (a) Skip 8.0 entirely and jump to the Step 8.1 import from harness-starter-kit — rejected because install.sh was broken (no agent propagation); would have compounded two failure modes at once. (b) Pack 8.0 into a single mega-commit — rejected per `artifact-and-git-cadence` preference for frequent atomic commits + per-approval cadence. (c) Enable BCG adapter by default in the tracked `config.json` — rejected because the fork is a public scaffold shareable with non-BCG users; disabled-by-default + explicit flip on the working-project install keeps the fork generic.

**Status:** active

## 2026-04-24: Step 8.1 — classified import from harness-starter-kit
**Decision:** Import Kenneth Leung's `harness-starter-kit` (BCG) into the agent-stack repo in seven atomic commits, classifying each artifact at the BCG-private / generic boundary per the D2 hybrid-adapter model:

**BCG-private** (→ `adapters/bcg/`, loaded only when `config.json.bcg_adapter = "enabled"`):
- Scripts: `sync-confluence.py`
- Templates: `config.yaml`, `.env.example`, `meeting-notes-template.md`, `weekly-status-template.md`
- Protocols: `atlassian-rules.md` (IP-allowlist workaround + BCG-specific API ID rules)
- Commands: `/sync-harness` (two-path Confluence sync)
- Context: `bcg-firm-context.md`, `case-engagement-process.md`, `bcg-core-frameworks.md`, `consulting-glossary.md`
- BCG-skinned skill: `confluence-access` (bcgx.atlassian.net / BCTAH / Rovo Graph Gateway protocol)

**Generic** (→ `.agent/`, shareable across firms and engagements, bootstrapped verbatim with new `bootstrapped_from:` frontmatter field):
- Skills: `analysis`, `review`, `document-assembly`, `context-search` → `.agent/skills/` under new `category: knowledge-work`
- Workflows: `situation-assessment`, `issue-tree-hypothesis`, `mid-case-findings-deck`, `final-recommendations-deck`, `post-meeting-update`, `daily-task-tracking` → new dir `.agent/workflows/`; `sample-` prefix dropped because these are canonical in our repo, not examples

**Deferred to Step 8.2** (agent-tuning): starter-kit's `.claude/agents/` roster (12 consulting roles — analyst, architect, business-lead, …) and `.claude/agent-memory/`. Blind import would have collided with the existing `adapters/claude-code/agents/` SDLC roster (product-manager, engineer, architect, reviewer, release-manager); tuning needs to reconcile name clashes and decide which to keep as distinct agents vs. fold in. The `formatting.md` rule, `draft-status-update` skill, starter-kit personas, specs, and project-scoped context samples were also deferred — none were in the user-approved 8.1 scope.

**Rationale:** The BCG-vs-generic split is the crux of the adapter model — getting it right now avoids retroactive reclassification later. Content was classified on two concrete signals: (a) does it reference BCG-specific infrastructure (bcgx.atlassian.net, BCTAH space, `@bcg.com` accounts, IP allowlist) — if yes, private; (b) is the pattern transferable to a non-BCG consulting engagement without edits — if yes, generic. Skills `analysis`/`review`/`document-assembly`/`context-search` passed (b) despite originating at BCG; `confluence-access` failed (a) because it hard-codes the BCG Atlassian org's behavior. The `bootstrapped_from:` frontmatter field (new optional field, added to `.agent/skills/_manifest.jsonl`) preserves provenance so future drift between the bootstrapped copy and the upstream source stays traceable.

Verbatim-first import (no path adaptation) was chosen for `context-search` despite its references to paths (`context/projects/{project}/`, `context/account/frameworks/`) that don't exist in agent-stack's layout. The `bootstrapped_from:` marker and an explicit note in the skill's description signal "adapt in Step 8.2" — keeping 8.1 a mechanical classification commit rather than mixing in edits.

**Alternatives considered:** (a) Import as one mega-commit — rejected per `artifact-and-git-cadence` and to keep the boundary auditable per-artifact. (b) Rewrite `context-search` paths immediately during import — rejected; mixes classification with adaptation and makes diff review harder. (c) Leave `confluence-access` under `.agent/skills/` and note it's BCG-flavored — rejected; the file hard-codes bcgx.atlassian.net, BCTAH, and the BCG IP-allowlist protocol, so it can't load on a non-BCG install without failing loudly. (d) Import the starter-kit's full consulting agent roster now — rejected; would collide with the existing SDLC roster and commit us to an unreviewed naming scheme before 8.2 agent-tuning.

**Status:** active

## 2026-04-24: Step 8.2.1 — BCG consulting agent roster + install.sh conditional branch + formatting rule
**Decision:** Stage 1 of a three-stage Step 8.2 (Option C from the pre-work scoping). Four atomic commits:

1. Import 13 starter-kit consulting agents into a new `adapters/bcg/agents/` dir. Rename starter-kit `architect.md` → `program-architect.md` to resolve the name collision with the existing SDLC `adapters/claude-code/agents/architect.md` (both would otherwise land in the same `.claude/agents/` dir at install time, and Claude Code dispatches by agent name). Update the renamed file's `name:` frontmatter and self-reference. Renormalize prose refs to `Architect` (as a role noun) in 5 peer BCG agents — engineering-lead, integration-lead, program-director, program-manager, sme — to `Program Architect` via a word-boundary regex, preserving substring matches like "architectural" and "architecture". Document the BCG-vs-SDLC roster split in `adapters/bcg/README.md`.

2. Extend `install.sh` claude-code branch with a BCG-conditional propagation block. Reads source `.agent/config.json` at install time; when `bcg_adapter == "enabled"`, copies `adapters/bcg/agents/*.md` and `adapters/bcg/commands/*.md` into the target's `.claude/agents/` and `.claude/commands/` dirs (alongside the always-propagated SDLC roster). Uses grep with a JSON-aware regex rather than jq to avoid a runtime dependency. Guards empty globs with nullglob so scaffold-only states don't break.

3. Import `.claude/rules/formatting.md` → `adapters/bcg/protocols/formatting.md` (action-item-tracker schema, RAID log schema, fixed status enum, weekly-status section order). Classified BCG-private because the exact enum values and section ordering are a BCG house-style choice, not a universal consulting standard.

4. Smoke-test (two fresh installs into `/tmp/claude/bcg-smoke-{disabled,enabled}/`) verified:
   - Disabled config → 5 SDLC agents, no BCG content, no `.claude/commands/` dir
   - Enabled config → 18 agents total (5 SDLC + 13 BCG, no collisions because `architect` ≠ `program-architect`), `.claude/commands/sync-harness.md` present
   - Source `.agent/config.json` was temporarily flipped to `enabled` for smoke B and reverted before push (tracked default stays `disabled`)

**Rationale:** Agents and slash commands need install-time propagation (Claude Code discovers them by filesystem at launch) whereas context / protocols / templates / skills load at session-start via the CLAUDE.md conditional — so the install.sh change is necessarily asymmetric and has to be a distinct commit. The `architect` → `program-architect` rename is the clean resolution because the two roles are semantically distinct (SDLC architect = PRD→ADR for one feature; program architect = tech-stack + standards across workstreams), merging them would be wrong, and filesystem-level disambiguation beats install-time ordering tricks. Renormalizing prose `Architect` references in peer BCG agents prevents Claude from ambiguating cross-roster when a BCG agent says "reviewed by the Architect" in running text.

Workflow↔roster reconciliation (e.g., `framework-lead`, `case-analyst`, `delivery-lead`, `partner-strategy`, `partner-analytics`, `principal-delivery`, `transcript-analyst`, `io-qa-auditor`, `jira-tracker-analyst` are referenced in imported workflows but absent from the 13-agent roster) is deferred to Step 8.2.2 — that's a design decision requiring a canonical-role verdict, not a mechanical import.

**Alternatives considered:** (a) Leave both `architect` files, rely on install-ordering — rejected because the second `cp` would silently clobber the first and the user would see only one, varying by adapter order. (b) Namespace agents by directory (`.claude/agents/sdlc/`, `.claude/agents/bcg/`) — rejected because Claude Code does not recursively scan subdirectories. (c) Put BCG agents in `adapters/claude-code/agents/` with a prefix — rejected because that dir is the harness-level generic roster; BCG content belongs under `adapters/bcg/`. (d) Add a runtime dependency on `jq` for the install.sh config read — rejected; grep handles the single flag fine and keeps install.sh portable to stripped-down shells.

**Status:** active

## 2026-04-24: Step 8.2.2 — workflow↔roster reconciliation (hybrid path)
**Decision:** Stage 2 of Step 8.2 (Option C / hybrid from pre-work scoping). Imported workflows referenced nine role labels absent from the 13-agent roster; resolved as follows:

**Authored as new BCG agents** (genuine distinct review lenses, not reducible to existing roles):
- `adapters/bcg/agents/partner-strategy.md` — reviews business logic, strategic direction, client-readiness
- `adapters/bcg/agents/partner-analytics.md` — reviews analytical rigor, data accuracy, MECE discipline
- `adapters/bcg/agents/principal-delivery.md` — reviews workplan feasibility, delivery risk, resourcing

**Relabeled in workflow files** (six orphan labels → canonical roster names, 17 replacements across 5 workflow files):
- `framework-lead` → `analyst`
- `case-analyst` → `analyst`
- `transcript-analyst` → `analyst`
- `jira-tracker-analyst` → `analyst`
- `delivery-lead` → `program-manager`
- `io-qa-auditor` → `test-lead`

Done via Python `\b...\b` regex (macOS `sed` does not support `\b`). Substring matches like "analytical" and "analysis" preserved. Post-commit state: every role reference in every workflow file resolves to a real agent in either the SDLC roster (`adapters/claude-code/agents/`) or the BCG roster (`adapters/bcg/agents/`). Roster after this stage: 5 SDLC + 16 BCG = 21 agents total when adapter enabled.

**Rationale:** The starter-kit workflows used two naming conventions that did not reconcile (13-role program roster vs. ad-hoc per-workflow labels); shipping both as-is would have meant workflow recipes referencing nonexistent agents. Three of the nine orphan labels were distinct review lenses (partner-strategy ≠ partner-analytics ≠ principal-delivery in real BCG practice), so collapsing them into one reviewer agent or into executive-sponsor would blur the review process. Authoring three new agents for those lenses is cheap (~50 lines each) and preserves the workflow design intent. The other six labels were not distinct roles — they were situational aliases for existing roster members; relabeling was lossless.

**Alternatives considered:** (a) Option A: author all 9 missing agents — rejected because 22 agents crowds the roster and treats situational aliases as distinct roles. (b) Option B: relabel all 9 to existing roster members, including the three review lenses — rejected; collapsing partner-strategy / partner-analytics / principal-delivery into `executive-sponsor` or a single `reviewer` loses the review-lens distinction that the workflows rely on at quality gates. (c) Leave the workflow refs as-is and mark them "aspirational" — rejected; unresolved references in canonical workflow definitions are a latent failure mode, not documentation.

**Status:** active

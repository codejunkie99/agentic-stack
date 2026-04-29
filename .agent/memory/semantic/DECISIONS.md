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

## 2026-04-24: Step 8.2.3 — orphans cleanup (paths, status-update skill, agent-memory, personas)
**Decision:** Stage 3 of Step 8.2 — the four items deferred from 8.1 and earlier 8.2 stages. Five commits:

1. **context-search path adaptation.** Rewrote the skill's path table from starter-kit conventions (`context/projects/{project}/...`, `context/account/frameworks/`) to agent-stack conventions — client-scoped paths resolve to `.agent/memory/client/<active_client>/` (D1-Option-B), firm-scoped paths resolve to `adapters/<firm>/context/` when a firm adapter is enabled. Added a new optional `path_adapted_in:` frontmatter field as a pair to `bootstrapped_from:` so drift vs. upstream stays traceable. When no firm adapter is active, firm rows collapse to [CONTEXT GAP] rather than failing on missing paths.

2. **draft-status-update skill bootstrapped** into `.agent/skills/` (5th knowledge-work skill). Verbatim import with `bootstrapped_from:` citing 8.2.3 (not 8.1 — deferred to orphans cleanup). Generic enough for the shared brain: content contract is "structured status update with canonical section order"; the exact section list is delegated to the active firm adapter's formatting protocol.

3. **BCG agent-memory templates** added under new `adapters/bcg/agent-memory-templates/` — 16 per-role stubs (12 imported verbatim, `architect.md` renamed to `program-architect.md` with header line updated to match 8.2.1 agent rename, 3 authored for the 8.2.2 reviewer-lens agents). `install.sh` extended with a copy-if-missing loop (not `cp -R` overwrite) so re-installs preserve in-progress per-agent memory. README.md is excluded from install-time propagation. Smoke-test verified fresh install gets 16 stubs; re-install after seeding preserves the seeded entry.

4. **Firm-generic personas** imported to `.agent/personas/` (not `adapters/bcg/personas/`): `executive-sponsor.md` and `program-director.md`. Both source files are fully firm-generic (no BCG markers, no named individuals), so they matched the `.agent/personas/README.md` rule that firm-generic archetypes live in the shared brain. `sample-` prefix dropped per the naming convention ("named after the archetype, not by sample label"). No filename collision with `adapters/bcg/agents/{executive-sponsor,program-director}.md` because the directories are semantically distinct (agent definition vs. reviewer bar).

**Rationale:** 8.2.3 is the "stop leaving orphans" stage. Every starter-kit artifact we imported in 8.1 or referenced in 8.2 now either lives at its correct home or has been explicitly declined. The context-search paths were the most important to fix because a broken path table in a high-use skill silently produces wrong results (empty searches, not errors). The `cp -if-missing` semantics for agent-memory templates matters because per-role memory is exactly the kind of content that accumulates value over time — clobbering on re-install would destroy it. Placing personas at `.agent/personas/` (not the bcg adapter) is a direct read of the pre-existing README policy: firm-generic archetypes are shareable, and the two starter-kit samples contained zero BCG specificity.

Final roster state after Step 8.2 (8.2.1 + 8.2.2 + 8.2.3):
- **Agents**: 5 SDLC (always installed) + 16 BCG (installed when `bcg_adapter: "enabled"`) = 21 total
- **Skills**: 11 SDLC + 5 knowledge-work (analysis, review, document-assembly, context-search, draft-status-update) = 16 total
- **Workflows**: 6 canonical patterns in `.agent/workflows/`, every role ref resolves to a real agent
- **Personas**: 2 firm-generic (executive-sponsor, program-director) in `.agent/personas/`
- **Agent-memory templates**: 16 per-role stubs in `adapters/bcg/agent-memory-templates/`, install-propagated with preservation
- **BCG adapter content**: scripts (1), commands (1), protocols (2), context (4), templates (3), skills (1 — confluence-access), agents (16), agent-memory-templates (16)

Step 8.3 (real-case dry-run) can now execute against a completed roster.

**Alternatives considered:** (a) Leave context-search paths as starter-kit refs and document the mismatch — rejected; silent-failure surface in a high-use skill. (b) Import draft-status-update to `adapters/bcg/skills/` — rejected; content contract is generic, only the formatting delegate is firm-specific. (c) Skip agent-memory templates entirely (option 3b) — rejected; a populated roster with empty memory scaffolding is a worse UX than a populated roster with 3-line init stubs. (d) Use `cp -R` (overwrite) for agent-memory templates to match the agents/commands propagation pattern — rejected; per-agent memory is the one content type where preservation across re-installs is load-bearing. (e) Import personas to `adapters/bcg/personas/` per my initial plan — rejected after checking content; both samples are firm-generic, and the BCG-personas README explicitly says firm-generic archetypes belong in `.agent/personas/`. The gitignore in `adapters/bcg/personas/` would also have silently dropped them.

**Status:** active

## 2026-04-24: Step 8.2.4 — reclassify consulting frameworks + glossary + quality standards as firm-generic
**Decision:** Re-examined the 8.1 BCG-private classification of `adapters/bcg/context/{firm,frameworks,glossary}/` after user noted the frameworks and glossary are useful in personal projects, not only BCG engagements. Reading the actual content confirmed the content was mixed, not uniformly BCG-proprietary. Re-split along content lines:

**Moved to `.agent/context/` (firm-generic, always-loaded):**
- `glossary.md` — consulting terminology (MECE, Pyramid, Ghost Deck, RAID, Workstream, So What, Straw Man, …). Content is Minto/Porter/generic MBB vocabulary; the previous "BCG / Consulting Terms" header overclaimed. Renamed to "Core Terms".
- `frameworks.md` — Issue Tree, Pyramid Principle (Minto), MECE, 7-S (McKinsey), Value Chain (Porter), Driver Tree, Sensitivity Analysis, Market Sizing (top-down / bottom-up), Pricing Strategy taxonomy. ~80% of the previous BCG-core-frameworks file. All firm-generic.
- `quality-standards.md` — authored new, extracting the generic portions of the BCG firm-context "Quality Standards" section: so-what-first (Pyramid), MECE analytical completeness, evidenced claims + explicit assumptions, sensitivity transparency. Added failure modes for each and a 5-item ready-for-review checklist.

**Kept in `adapters/bcg/context/` (BCG-specific, adapter-only):**
- `frameworks/bcg-matrix.md` — authored new from the ~15 BCG-attributed lines of the previous frameworks file: Growth-Share Matrix (developed by BCG 1970) and BCG's pricing-practice opinion (value-based-first sequencing).
- `firm/bcg-firm-context.md` — BCG hierarchy, team sizing (2–6 consultants), BCG engagement duration (6–12 weeks), BCG title conventions (Partner/MD, Principal/AD, Project Leader, Consultant, Associate), BCG tools (Confluence, PowerPoint). The "Quality Standards" section now references the generic file and retains only the BCG-specific "Ready-for-client = Partner approval" gate, framed as "generic standards are necessary but not sufficient" to make the layering explicit.
- `firm/case-engagement-process.md` — unchanged; BCG-specific.

**CLAUDE.md session-start** rewritten with two layers: step 7 unconditionally loads `.agent/context/` (three files) on every session; the conditional-mount block now loads `adapters/bcg/context/firm/` and `adapters/bcg/context/frameworks/` *on top of* the generic base when `bcg_adapter: "enabled"`. Glossary removed from the conditional list since it's always-loaded now.

Smoke-test verified on fresh targets in `/tmp/claude/824-{disabled,enabled}/`:
- Disabled config: `.agent/context/` with all 4 files present (README + 3 content), 5 SDLC agents, no `.claude/commands/`, no `.claude/agent-memory/` — generic consulting context reaches personal-project installs exactly as intended
- Enabled config: same `.agent/context/` plus 21 agents (5+16), 1 BCG slash command, 16 BCG memory stubs — firm-specific content layers on top
- Source `config.json` was flipped to `"enabled"` for smoke B and reverted before push

**Rationale:** The 8.1 classification put MECE, Pyramid Principle, 7-S, Value Chain, Driver Tree, and consulting glossary terms under `adapters/bcg/` — treating Minto's and Porter's industry-standard frameworks as BCG-proprietary. That was wrong on the merits (the frameworks are industry canon) and wrong on the UX (the generic fork shipped without access to MECE/pyramid guidance unless the BCG adapter was toggled on, which requires BCG-specific Atlassian infrastructure). Splitting along the real content line — generic consulting knowledge vs. BCG-authored content — makes the generic fork useful as a consulting-savvy agent stack independent of BCG, and keeps the BCG adapter honest about what is actually BCG's.

The quality-standards extraction was user-flagged explicitly ("the rigor and so-what level which the bcg firm dir tells about the quality of the work"). The extraction isolates the four generic demands from the one BCG-specific gate (Partner approval as the client-readiness trigger), so both layers stay intact and composable.

**Alternatives considered:** (a) Move all three files (firm-context included) to `.agent/context/` — rejected; `bcg-firm-context.md` is ~95% BCG-specific content (hierarchy titles, team sizing norms, tool choices), shipping it generically would make the public fork look BCG-branded without benefit. (b) Duplicate generic portions into `.agent/context/` and leave originals intact in `adapters/bcg/` — rejected; drift risk over time, and the classification would stay wrong. (c) Keep current classification and have personal projects enable the BCG adapter just for context — rejected; enabling the adapter pulls in Atlassian protocol, sync-harness command, and confluence-access skill, all of which fail on non-BCG infrastructure. Enabling-for-context-only would require a finer-grained toggle per sub-adapter, which is over-engineering.

Final roster state after Step 8.2 (8.2.1 + 8.2.2 + 8.2.3 + 8.2.4):
- **Agents:** 5 SDLC (always) + 16 BCG (adapter-gated) = 21
- **Skills:** 11 SDLC + 5 knowledge-work (analysis, review, document-assembly, context-search, draft-status-update) + 1 BCG-skinned (confluence-access) = 17
- **Workflows:** 6 canonical in `.agent/workflows/`, every role ref resolves
- **Personas:** 2 firm-generic in `.agent/personas/`
- **Agent-memory templates:** 16 per-role stubs in `adapters/bcg/agent-memory-templates/`, install-propagated with preservation
- **Generic context:** 3 always-on files in `.agent/context/` (glossary, frameworks, quality-standards)
- **BCG adapter context:** `firm/` (BCG-specific hierarchy + engagement model) + `frameworks/` (BCG Matrix + pricing opinion)

**Status:** active

## 2026-04-27: Step 8.2.5 — sync fork to upstream v0.11.2 + port BCG to harness_manager

**Decision:** Synced agent-stack fork from base v0.8.0 (`a397568`) to upstream v0.11.2 (`8ba0293`) — 59 commits, 6 tags. Three-way merge with 4 conflict resolutions:

- `install.sh`: took upstream (38-line Python dispatcher) — discarded our 175-line bash with the BCG-conditional propagation block. Block re-introduced as new named post_install action `bcg_conditional_propagate` in `harness_manager/post_install.py`, registered in `harness_manager/schema.py`, wired into `adapters/claude-code/adapter.json`.
- `.agent/skills/_index.md`, `.agent/skills/_manifest.jsonl`: union merge — disjoint skill names (ours' 13 knowledge-work + SDLC + theirs' 3 new: data-flywheel, data-layer, design-md). Inserted theirs' 3 entries between deploy-checklist and planner sections.
- `.agent/memory/semantic/DECISIONS.md`: ours-wins (project history).
- Auto-merged: `.agent/AGENTS.md`, `.gitignore`.

**Architecture preserved:** harness_manager's named-built-in post_install model (codex review flagged DSL creep; named built-ins are the constrained alternative). Extended `post_install.run()` and `post_install.reverse()` to pass `stack_root` via kwargs — non-invasive change because all action functions absorb extra kwargs via `**_kwargs`. BCG action reads source-tree `adapters/bcg/` content because adapter manifests don't ship that content into target's copied `.agent/`. Threaded stack_root through `remove()` signature too so reverse cleanup works on uninstall.

**Behaviour preserved from bash:** agents/commands overwrite-on-install; agent-memory templates copy-if-missing (preserves user-seeded per-agent memory); README.md excluded from agent-memory propagation; gated on source `.agent/config.json` `bcg_adapter == "enabled"`.

**Two upstream regressions discovered + fixed locally** (commit `20e37fc`, candidates to upstream codejunkie99/agentic-stack):
1. `harness_manager/cli.py` uses PEP 604 union syntax (`list[str] | None`) without `from __future__ import annotations` — fails import on Python 3.9.6. The v0.10.0 commit `f0cd73b` "support Python 3.9" added the future import to other harness_manager modules but missed cli.py.
2. `adapters/claude-code/adapter.json` only declared CLAUDE.md + settings.json. The pre-v0.9.0 install.sh did `cp agents/*.md .claude/agents/` automatically; the manifest-driven refactor lost this. Added 5 explicit `files` entries for SDLC agents (architect, engineer, product-manager, release-manager, reviewer).

**Gained from upstream:** harness_manager Python pkg (cli, doctor, install, manage_tui, post_install, remove, schema, state, status), data-layer + data-flywheel + design-md skills, codex adapter, pi adapter rewrite (closes formula crash + decay tz bug per #24), schemas/, top-level test files (test_data_flywheel_export.py, test_data_layer_export.py), new hooks (_episodic_io.py, pi_post_tool.py, _provenance.py, claude_code_post_tool.py, pre_tool_call.py), Windows path-traversal security fix.

**Kept untouched (~92 files):** all of `adapters/bcg/` (16 agents, 16 agent-memory templates, scripts, commands, protocols, context, templates, skills), `.agent/context/` (4 generic-consulting files from 8.2.4), `.agent/personas/` (executive-sponsor, program-director from 8.2.3), all 13 knowledge-work + SDLC skill dirs.

**Smoke-tested via `./install.sh`:** both adapter states on fresh installs in `/tmp/claude-501/825-{disabled,enabled}/`. Disabled → 5 SDLC agents, 0 commands, 0 agent-memory, generic context loaded. Enabled → 21 agents (5+16), 1 BCG slash command (sync-harness.md), 16 BCG agent-memory stubs. Idempotence verified separately: user-seeded MARKER line preserved across re-install.

**Rationale:** v0.9.0's harness_manager refactor is the architectural change that mattered most — install.sh became a thin dispatcher, real logic moved to a manifest-driven Python pkg with named built-in post_install actions. Re-extending the bash with our BCG block and ignoring the new pkg would have stranded us on a deprecated install path that brew formula no longer invokes. Porting to a named post_install action keeps us inside the upstream architecture, makes the BCG conditional reviewable by upstream (if we ever upstream the adapter), and is testable in isolation.

**Alternatives considered:** (a) Cherry-pick selected upstream commits — rejected; the harness_manager refactor is too coupled to its supporting commits to cherry-pick cleanly. (b) Rebase our 8.x onto upstream — rejected; conflict surface identical, but rewrites our publicly-visible 8.x history. (c) Generalize a `firm_overlay` mechanism in harness_manager — rejected as YAGNI; one named action is right-sized for one firm adapter. Refactor when a second firm appears. (d) Move BCG content into `.agent/firms/bcg/` so it gets copied as part of `.agent/` and the action only needs target_root — rejected; breaks the firm-adapter pattern established in Step 8.0 and would require restructuring the entire `adapters/bcg/` tree. Passing stack_root via kwargs is a one-line change with a much smaller blast radius.

**Status:** active

**Operationalized:** weekly upstream-sync cadence (Mon 9:13 local, durable cron `ba87d58c` + auto-memory `upstream_sync_cadence.md`) so this drift doesn't recur. Plan + per-tag classification doc checked into `docs/superpowers/plans/`. Test file at top-level (`test_bcg_conditional_propagate.py`) matching upstream pattern (test_data_flywheel_export.py); `tests/` is gitignored as of upstream's v0.9.1 (f1c362d).

## 2026-04-28: Eager-load surface trim + permissions.md BCG rules justification

**Decision:** Trim CLAUDE.md from 189 → 92 lines by moving `memory_reflect.py` examples + importance guide to `docs/memory-reflection.md`, compressing the conditional-mount section to pointer-style, and tightening BCG/active_client text. Trim AGENTS.md from 114 → 109 lines by compressing the `skill_evolution_mode` description (full behavior moved to `propose_harness_fix.py --help`). Justify the +19-line growth of `protocols/permissions.md` vs upstream — that growth came from Step 8.0 adding "BCG engagement rules" (cross-client write isolation, push-target safety, AGENT_CLIENT env var resolution order). The rules ARE essential — they prevent BCG-client repos from accidentally pushing to personal remotes — so the additions stay.

**Rationale:** First run of `harness_conformance_audit.py` (Step 8.3 slice 1) showed CLAUDE.md 189/120, AGENTS.md 114/110, eager-load total 839/500 — clear violations of the <100-line CLAUDE.md best practice (Effloow / HumanLayer / Anthropic guidance). Pulkit's prompt: "everything should have progressive disclosure — adopt the same thinking here in this repo." The trim re-establishes upstream parity (108-line CLAUDE.md as baseline) while preserving the legitimate BCG additions, with all moved content addressable on-demand via `docs/memory-reflection.md` and `propose_harness_fix.py --help`.

**Alternatives considered:** (a) Leave the bloat and document it — rejected; violates the same progressive-disclosure principle we enforce on installed projects. (b) Move everything to docs/ including BCG conditional-mount rules — rejected; conditional-mount logic IS load-bearing at session-start (the agent must know when to read which files), but the prose explanation can compress. (c) Strip permissions.md back to upstream parity — rejected; the BCG cross-client write rules are non-negotiable safety constraints.

**Status:** active.

**Operationalized:** `harness_conformance_audit.py` wired to detect any future regression. permissions.md mentioned in this entry so the audit's "justified-in-DECISIONS" heuristic stops flagging it.


## 2026-04-29: Step 8.3 Phase 2 dry-run outcome — three new harness gaps surfaced

**Decision:** Conclude Step 8.3 Stage 4 (consulting workflow dry-run) with Phase 2 deck-content build complete and Phase 3 (format production) deferred behind 4 explicit entry preconditions. Capture three new harness-shaped gaps from the post-mortem (Gaps 9/10/11) and route them to Step 8.4 instead of fixing on this branch.

**Outcome of the dry-run:**
- HarnessX engagement (Tier-1 APAC bank C-suite pitch deck on agentic SDLC) ran end-to-end through the BCG pipeline: storyboard v1 → v2 → v3 (framework-lead 8-section audit) → 5 case-analysts in parallel (one per act-cluster) → deck-builder consolidation + delivery-lead review → 3-reviewer partner panel (strategy / analytics / delivery) all returning GO-WITH-FIXES → Pulkit panel decisions applied → Phase 2 final-fix pass.
- Output artefacts: `output/storyboard.md` (v3 + Phase 2 decisions), `output/content-draft.md` (20 main + 8 appendix), `output/phase-2-complete.md` (status note + Phase 3 entry preconditions). 5 cluster files + 5 review files preserved as audit trail.
- Snapshot/diff confirms `in_place` evolution worked as designed: 7 added agent-memory files, 0 modified, 0 removed. No skill self-rewrites during the engagement; no agent file edits. Lock set held — none of the 6 read-only paths were touched.

**Three new gaps (all open, deferred to 8.4):**
1. **Gap 9 — Auto-dream noise on long content sessions.** 13 candidates staged after Phase 2; all are file-write tool-use claims ("Wrote storyboard.md (781 lines)"). None graduate-worthy. Root cause: `auto_dream.py` clusters by token overlap of action text; on long sessions the dominant signal is filename + tool, not insight. Fix: collapse Write/Edit on the same file within a session before clustering, OR weight `memory_reflect.py` reflections higher than tool-use episodes.
2. **Gap 10 — Workflow contract reconciliation runs too late.** `consulting-deck-builder` Phase 1 (Storyboard) had no workflow-contract gate. Framework-lead 8-section audit fired *after* storyboard v2 was complete; identified 3 critical missing/mis-framed sections; v3 then required 6 structural moves. Fix: add Phase 1.5 gate to `consulting-deck-builder` SKILL.md — 8-section coverage check against source workflow file before Phase 2 entry.
3. **Gap 11 — `propose_harness_fix.py` invisible to agents.** HARNESS_FEEDBACK.md empty after 130 episodes despite multiple harness-shaped frictions surfaced during the run. Tool exists and is documented; no skill/protocol names the trigger for invocation. Fix: two-part — (a) explicit trigger list in CLAUDE.md "When to use"; (b) session-end hook prompts "any harness friction to capture?".

**What did NOT regress (validates earlier 8.x decisions):**
- Lock set: 0 attempted writes to any of the 6 read-only paths.
- `in_place` skill evolution: held; `consulting-deck-builder` did not self-rewrite during use, even when its own 3-phase methodology hit edge cases (cold transitions; positioning split). Skill self-rewrite hooks are present but agents preferred surfacing as findings to the user, not auto-editing.
- Lazy-load: 14 indexed briefing files; INDEX.md the only eager surface; raw-uploads loaded on-demand only by `document-researcher`.
- Agent-memory: 4 files for `deck-builder`, 3 for `delivery-lead`. Both correctly used the per-agent memory pattern (project + feedback + user types). The other 5 active agents (case-analysts, framework-lead, 3 partner-panel reviewers) did NOT persist agent-memory — Gap 11 root cause overlap (no rule names when to capture).

**Rationale for deferring 9/10/11 to 8.4:**
- All three are skill/tool-tuning issues, not blockers for Step 8.3's scope (which was "exercise the stack against a real consulting workflow and surface gaps"). 8.3 succeeded at surfacing.
- Step 8.4 was already scoped as `harness-graduate.py` + dream-cycle improvements informed by 8.3 data. Gaps 9/10/11 are exactly that data.
- Fixing 9/10/11 on this branch would expand 8.3 scope beyond the stated capture-and-surface objective and delay merge.

**Status:** active. Step 8.3 complete pending merge; Phase 3 of HarnessX engagement is a Pulkit-driven workstream, not a harness deliverable.

**Operationalized:** Gap log updated (8 entries total — 5 original + Gap 8 closed-on-branch + Gaps 9/10/11 from post-mortem). WORKSPACE.md marks Stages 4 + 5 complete. Step 8.4 plan to address 9/10/11 paired with `harness-graduate.py` design.


## 2026-04-29: Phase K — engagement-blank semantic memory on fresh installs

**Decision:** Fresh installs reset `.agent/memory/semantic/{LESSONS.md, DOMAIN_KNOWLEDGE.md, DECISIONS.md, lessons.jsonl}` from install-time templates after the wholesale `.agent/` copytree. The four files now start as engagement-blank stubs (LESSONS keeps 5 harness-invariant seeds; DOMAIN_KNOWLEDGE + DECISIONS are header-only templates) instead of inheriting the upstream fork's lived-in harness-development semantic content.

**Why this was a leak:** install.py's `shutil.copytree(stack_root / ".agent", target_agent)` shipped fork's 18-line LESSONS (including auto-promoted "serialize timestamps in UTC" — irrelevant for consulting engagements), 220-line DOMAIN_KNOWLEDGE (entirely about agentic-stack architecture), and 265-line DECISIONS (fork's historical ADRs from Step 6 / 8.0 / 8.1 / 8.2.x — engagement has no use for these). When the engagement session started, CLAUDE.md eager-loaded LESSONS.md and the agent read fork's harness-dev lessons as if they were engagement context. Verified empirically on the HarnessX target post-Phase-2: 3 of 4 semantic files byte-identical to fork; engagement had written zero entries.

**Mechanism:** templates live at `harness_manager/templates/semantic/` (sibling to install.py) and are copied to target after the wholesale `.agent/` copytree, inside the existing `if not target_agent.exists()` guard. Reinstalls do NOT re-apply templates — accumulated engagement state (including engagement-graduated lessons) is preserved across reinstall. New helper `_apply_semantic_templates()` in install.py.

**Rationale:** semantic memory is supposed to be where THIS install accumulates ITS lessons. Cross-install graduation (lessons going UP from engagement to fork) is the deferred `harness-graduate.py` flow (Step 8.4). Cross-install propagation DOWN from fork to other installs is the deferred `install.sh --upgrade` (Step 8.5). Neither flow exists yet — so the bootstrap-then-immutable behavior of install.py was effectively shipping fork's semantic state as a one-way leak.

**Alternatives considered:** (a) Move fork's lived semantic to a different directory and put templates at `.agent/memory/semantic/` directly — rejected; touches fork's own brain, risky. (b) Have install.py read from `adapters/_brain/memory/semantic/` instead of fork's `.agent/memory/semantic/` — rejected; introduces a parallel brain root, breaks the single-brain invariant. (c) Leave install.py wholesale-copy and reset semantic in a post_install action — rejected; post_install runs AFTER the install.json is recorded, making the reset a separate auditable event when it's actually part of "what fresh install means." (d) Strip fork's `.agent/memory/semantic/` content to be engagement-blank too — rejected; fork IS doing harness-development, its lived semantic is real and valuable. The leak is the copy mechanism, not fork's content.

**Operationalised:**
- Templates committed at `harness_manager/templates/semantic/{LESSONS.md, DOMAIN_KNOWLEDGE.md, DECISIONS.md, lessons.jsonl}`
- `install.py:_apply_semantic_templates()` overwrites the four files inside the fresh-install guard
- Smoke-tested on `/tmp/k-smoke-*`: install logs "+ .agent/memory/semantic/ (reset to engagement-blank templates)"; verified all 4 files match templates; verified fork-leaked content (UTC-timestamps lesson, agentic-stack architecture treatise) absent from fresh install
- HarnessX target reset manually (one-time): pre-state archived at `<target>/.agent/memory/semantic/.archive/2026-04-29-phase-K-reset/`; templates applied; verified all 4 files match

**Status:** active. Pairs with Phase L (memory-write discipline so engagement-specific lessons accumulate into the now-blank files) and Phase M (graduate.py to clear the noise-only candidate queue). Phase J (sync-target.sh) will need to honour this reset — never overwrite target's semantic during sync.

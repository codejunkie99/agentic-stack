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

## 2026-04-23: `planner` — pull gstack `/autoplan` decision principles into v1
**Decision:** Add gstack `/autoplan`'s 6 Decision Principles (completeness, boil-lakes, pragmatic, DRY, explicit-over-clever, bias-toward-action) and the Mechanical/Taste/User-Challenge decision classification into `planner/SKILL.md`. Source attribution updated in frontmatter + `_manifest.jsonl`.
**Rationale:** Pulkit flagged the value directly after the v1 ship: these aren't just decomposition heuristics — they're principles that let the planner auto-resolve intermediate choices without stalling, and the classification framework tells the planner *when to decide silently vs surface a choice to the user*. That second part is the genuinely new capability the superpowers source didn't cover. Same-day reversal is appropriate because the cost of the pull is low (~20 lines) and the downstream template (nine more skills) benefits from the richer decision vocabulary from the start.
**Alternatives considered:** (a) Keep superpowers-only and defer — rejected because the nine subsequent skills will inherit from whatever shape `planner` settles into; baking the decision framework in now saves nine later retrofits. (b) Pull the full `/autoplan` pipeline (phases, codex review, etc.) — rejected as out of scope for a `planner` skill; those belong in `spec-reviewer` and a future `auto-review` orchestration if needed.
**Status:** active

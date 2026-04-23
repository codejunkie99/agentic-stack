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
**Status:** active

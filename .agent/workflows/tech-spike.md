---
workflow_id: tech-spike
name: Technical Research Spike
team_structure: flat
description: Research a technical approach before committing to it — evaluate a library, prototype a pattern, benchmark options. No user-facing surface; output is a recommendation, not a feature. Single agent (architect or prototype-engineer depending on scope).
---

## Purpose

Answer a single technical question with research + a small experiment. Distinct
from `prototype-app.md` (user-facing app) and `feature-prototype.md` (feature
inside an app) — this is research-shaped, not product-shaped. Output is a
recommendation document, possibly accompanied by throwaway experimental code.

Examples:
- "Should we use Postgres trigram or pgvector for fuzzy search?"
- "Does library X handle our scale, or do we need to roll our own?"
- "What's the fastest way to ingest 50M rows into our schema?"

## Trigger phrases

"tech spike", "research [tech approach]", "evaluate [library]", "benchmark
options for", "prove out [pattern]", "should we use X or Y?".

## Team

Single agent picks based on scope:

- **architect** — when the question is architectural ("should our system
  do X?"). Output: ADR-style document.
- **prototype-engineer** — when the question requires running code to
  answer ("how fast is library X with our data?"). Output: benchmark
  results + recommendation.
- **backend-engineer** or **frontend-engineer** — when the question is
  scoped to one stack layer.

The orchestrator picks one based on the user's question shape.

## Output

- `output/tech-spikes/<slug>/QUESTION.md` — the original question + scope
- `output/tech-spikes/<slug>/RESEARCH.md` — findings (links, notes,
  benchmarks, code samples)
- `output/tech-spikes/<slug>/RECOMMENDATION.md` — what to do, with
  rationale + alternatives considered (this is ADR-shaped)
- (Optional) `output/tech-spikes/<slug>/experiments/` — throwaway code
  if the spike required runnable proof

## Quality gates

- Question is well-formed (binary OR enumerated alternatives)
- Recommendation cites evidence (benchmarks, code, references)
- Alternatives considered (at least one) with reason for rejection
- Recommendation is decisive — "depends" is acceptable but the
  conditional must be explicit

## Memory write discipline

`memory_reflect` at importance 8, pain 5. The recommendation often
graduates to a DECISIONS.md entry via `/regenerate-decisions` — flag
this in the reflection note.

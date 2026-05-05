# agentic-stack Data Flywheel

The data flywheel turns repeated human-approved work in any `.agent/` harness
into reusable local intelligence artifacts.

It is not model training. It is the preparation layer:

```text
approved run
-> redacted trace
-> context card
-> eval case
-> training-ready JSONL
-> optional downstream open-weight SLM/adapter later
```

Agentic-stack is a good place for this because it already gives Claude Code,
Hermes, OpenClaw, Codex, Cursor, OpenCode, Windsurf, Pi, Antigravity, and custom
loops one portable brain. The flywheel adds a private corpus path on top of
that brain.

## What This Adds

- `/data-flywheel` skill instructions
- `.agent/tools/data_flywheel_export.py`
- schemas for approved runs, trace records, context cards, eval cases,
  training examples, and flywheel metrics
- sanitized examples under `examples/flywheel/`
- a local `.agent/flywheel/` convention for private runtime artifacts

## Privacy Model

Local-first by default.

- No network calls.
- No telemetry.
- No model training.
- No raw input storage in exports.
- Raw run IDs are hashed.
- Redaction must pass before an example is marked trainable.
- `.agent/flywheel/` is gitignored and should be treated as private runtime
  state.

Only sanitized examples should be committed.

## Input

Put sanitized, human-approved records in:

```text
.agent/flywheel/approved-runs.jsonl
```

Required shape:

```json
{
  "id": "run_real_estate_lead_001",
  "created_at": "2026-04-25T10:00:00Z",
  "project": "openclaw-real-estate",
  "domain": "real_estate",
  "workflow": "lead_intake",
  "harness": "openclaw",
  "skill": "lead-intake",
  "instruction": "Extract CRM fields and draft a compliant follow-up.",
  "input_redacted": "[REDACTED INBOUND LEAD]",
  "output_approved": "[HUMAN-APPROVED OUTPUT]",
  "human_review": {
    "status": "accepted",
    "edit_distance_estimate": "low",
    "review_notes": "Tone approved after fair-housing check."
  },
  "redaction_status": "passed",
  "pii_level": "none",
  "raw_input_stored": false
}
```

## Export

```bash
python3 .agent/tools/data_flywheel_export.py
```

Outputs:

```text
.agent/flywheel/exports/<YYYY-MM-DD>/
  trace-records.jsonl
  training-examples.jsonl
  eval-cases.jsonl
  context-cards.json
  context-cards/<domain>/<workflow>.md
  context-cards/<domain>/<workflow>.json
  flywheel-metrics.json
  README.md
```

## Readiness Heuristics

These are planning thresholds, not scientific cutoffs:

- 10-25 approved runs: useful first context card
- 25-100 approved runs: first eval set and repeated failure modes
- 100-300 approved runs: compression and routing measurement
- 500-1,500 high-quality examples: narrow adapter experiment candidate
- 2,000-10,000+ examples: broader workflow-family corpus
- 10,000+ clean examples plus negative cases: serious vertical corpus

Good early SLM/adapter candidates are narrow and repetitive:

- lead-intake extraction
- CRM field normalization
- listing-copy compliance flags
- showing-intent classification
- follow-up tone/style drafting
- issue triage tagging
- support-ticket classification
- document checklist extraction

Bad first candidates are broad professional judgment tasks such as "be a full
agent", "be a lawyer", or "run product strategy".

## Relationship To Memory

This does not replace agentic-stack memory.

- Episodic memory answers: what happened?
- Semantic memory answers: what did we learn?
- Context cards answer: what compact workflow rules are reusable?
- Eval cases answer: what must keep working?
- Training examples answer: what could become a dataset later?

The flywheel gives future memory, retrieval, eval, and adapter workflows better
artifacts to work from.

## Model Stance

Model-agnostic. Gemma, Qwen, Llama, Mistral, DeepSeek, or a custom open-weight
model can be downstream targets later. This feature only exports clean local
artifacts; it does not choose or train a model.

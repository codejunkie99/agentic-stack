---
name: data-flywheel
version: 2026-04-25
triggers: ["data flywheel", "trace to train", "training traces", "context cards", "eval cases", "approved runs", "vertical intelligence"]
tools: [bash, git]
preconditions: [".agent exists"]
constraints: ["local-only by default", "human-approved runs only", "redaction required before trainable", "do not train models"]
---

# Data Flywheel - approved runs into reusable intelligence

Use this skill when a user wants to turn repeated human-approved agent work
across Claude Code, Hermes, OpenClaw, Codex, Cursor, or custom `.agent/` loops
into local artifacts for retrieval, evals, prompt shrinking, and optional
future open-weight model/adapters.

The flywheel is:

```text
approved run
-> redacted trace
-> context card
-> eval case
-> training-ready JSONL
-> optional downstream SLM/adapter experiment later
```

This skill creates the harness. It does not train a model.

## Hard Rules

- Use only human-approved runs. Rejected or unknown-review runs can become
  failure-mode notes, not trainable examples.
- Redaction must pass before anything is marked trainable.
- Do not store raw prompts, raw code, client names, addresses, phone numbers,
  emails, secrets, credentials, or unredacted CRM records.
- Keep `.agent/flywheel/` private and gitignored unless the user explicitly
  commits sanitized examples.
- Stay model-agnostic. Mention model families only as downstream examples.

## Inputs

Default local input:

```text
.agent/flywheel/approved-runs.jsonl
```

Each line should be a sanitized run record with:

- `domain`
- `workflow`
- `harness`
- `instruction`
- `input_redacted`
- `output_approved`
- `human_review.status` as `accepted` or `edited`
- `redaction_status: passed`
- `pii_level`
- optional `stable_rules`, `tool_contracts`, `eval_tags`, `failure_modes`

## Export

Run:

```bash
python3 .agent/tools/data_flywheel_export.py
```

Outputs go to:

```text
.agent/flywheel/exports/<YYYY-MM-DD>/
```

Key outputs:

- `trace-records.jsonl`
- `training-examples.jsonl`
- `eval-cases.jsonl`
- `context-cards/<domain>/<workflow>.md`
- `context-cards/<domain>/<workflow>.json`
- `flywheel-metrics.json`

## Readiness Checks

Use these as heuristics, not hard rules:

- 10-25 approved runs: useful first context card
- 25-100 approved runs: first eval set and repeated failure modes
- 100-300 approved runs: context compression and routing measurement
- 500-1,500 high-quality examples: narrow adapter experiment candidate
- 2,000-10,000+ examples: broader workflow-family corpus

## What To Report

When finishing, report:

- traces exported
- trainable examples exported
- eval cases exported
- context cards created
- redaction pass rate
- acceptance rate by workflow
- workflows that should stay frontier-model/manual-review
- workflows that may become SLM/adapter candidates later

## Self-rewrite hook

If users repeatedly ask for the same domain-specific fields, add them to a
local context card or schema example instead of hard-coding them into this
general skill.

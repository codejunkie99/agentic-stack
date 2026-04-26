# Data Flywheel Examples

Sanitized examples for `.agent/tools/data_flywheel_export.py`.

Copy the example shape into your private project-local file:

```text
.agent/flywheel/approved-runs.jsonl
```

Then run:

```bash
python3 .agent/tools/data_flywheel_export.py
```

The export writes trace records, context cards, eval cases, training-ready
JSONL, and flywheel metrics under `.agent/flywheel/exports/<date>/`.

These examples contain no real PII and are shape examples only.

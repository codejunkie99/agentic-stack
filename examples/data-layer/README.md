# Data Layer Examples

Sanitized examples for the local agentic-stack data layer.

Copy example shapes into your private project-local `.agent/data-layer/` folder:

```text
.agent/data-layer/
  harness-events.jsonl
  cron-runs.jsonl
  category-rules.json
```

Then run:

```bash
python3 .agent/tools/data_layer_export.py --window 30d --bucket day
```

The export writes dashboard-ready JSONL, JSON, CSV, `kpi-summary.csv`, a
Gantt-ready `cron-timeline.csv`, `dashboard.html`, `dashboard-report.json`, and
`daily-report.md` under `.agent/data-layer/exports/<date>/`.

The examples contain no real PII and should be treated as shape examples only.

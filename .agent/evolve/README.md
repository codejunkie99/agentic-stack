# evolve/

Gated harness evolution (see `tools/evolve.py --help`).

- `evals/*.json` — task cards `{id, domain, prompt, check}`; `check.type` is
  `contains`, `regex`, or `command` (env `TASK_OUTPUT` = path to the output).
- `runner.json` — how one task runs against an overlay `.agent/`.
- `candidates/<id>/descriptor.json` + `files/` — a proposed harness change.
- `rounds/` — screening records (paired gains, gates, verdicts).
- `genebank.jsonl` — one confirmed harness per (where, pathology) cell.
- `backups/` — pre-install copies of replaced files.

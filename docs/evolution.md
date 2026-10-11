# Harness evolution: seats, candidates, gated screening, gene bank

The policy around a frozen model — prompts, knowledge, runtime strategy,
config — is what evolves. The model does not. Nothing reaches the live
`.agent/` without beating its parent on the same tasks.

## Strategy seats — `harness/seats.py`

| Seat | Question | Default |
|---|---|---|
| memory | what does this turn get to see? | `context_budget.build_context` |
| planning | how is the work approached? | `harness/PLANNING.md` or a built-in frame |
| capability | which tools does this iteration expose? | `protocols/tool_schemas/*` minus `disabled_tools` |
| action | should this step run? | `hooks/pre_tool_call.check_tool_call` |

`harness/seats.json` overrides any seat with `"module:function"`. The
conductor asks the seats and assembles; it holds no strategy of its own.

## Evolver — `tools/evolve.py`

```
diagnose   failures in episodic memory → (skill, pathology) diagnoses with trace events
scaffold   candidate dir: descriptor.json + files/ to edit; where ∈ prompt|knowledge|runtime|config
screen     paired screen on a fixed task sample (same sample for every candidate in the round)
round      screen → survivors get full utility → gene bank update → stagnation / max-rounds stop
install    confirmed candidate → live .agent/, originals backed up under evolve/backups/
genebank   one confirmed harness per (where, pathology) cell with lineage
```

### Screening gates

- **validity**: every attempt has a complete log with an exit code
  (timeouts and launch failures fail the gate).
- **activation**: the candidate's `activation.marker` appears in at least
  one transcript, proving the change actually ran. Without a marker the gate
  is reported as unverified; `--no-activation-gate` is explicit.
- **paired gain**: γ_i = score(candidate, task i) − score(parent, task i);
  t = mean(γ) / (sd(γ) / √n), zero variance → ±∞ or 0 by sign. Pass when
  mean(γ) > 0 and t ≥ 1.96 with n ≥ 2.

### Evals

`evolve/evals/*.json` task cards: `{id, domain, prompt, check}`; checks are
`contains`, `regex`, or `command` (receives `TASK_OUTPUT`). `evolve/runner.json`
says how one task runs against an overlay `.agent/` (`{agent_root}`,
`{prompt}`); it defaults to the standalone conductor and can be any agent
CLI. Utility is pass@1 over cards.

### Gene bank

`evolve/genebank.jsonl`: cell `(where, pathology)` → `harness_id`, `utility`,
`lineage`, round. Competitors are the incumbent and confirmed candidates in
the cell; the higher utility wins, ties keep the incumbent.

## Honest limits

- Utilities are only as good as the task cards. Two cards is a smoke test,
  not evidence.
- Screens run candidates in copied overlays; anything a task writes outside
  `.agent/` leaks between runs.
- The evolver proposes nothing by itself. Diagnoses point at a file; a
  human or the host agent writes the candidate.

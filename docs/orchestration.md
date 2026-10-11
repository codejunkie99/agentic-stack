# Orchestration: DAG plans, agents, personas, campaigns

The host agent plans a goal as a dependency graph, hands each node to a
registered agent, judges the result by evidence, and keeps every record on
disk. Library: `.agent/harness/dag.py`. CLI: `.agent/tools/plan.py`.

## Agent registry — `protocols/agents.json`

One row per agent you can delegate to: `command` (shell-free argv with
`{prompt}` / `{prompt_file}` placeholders; the prompt is also sent on stdin),
`capabilities`, `timeout_seconds`, `mutates_workspace`, `priority`. Presets
ship for Claude Code, Codex, OpenCode, Gemini, Copilot CLI, Pi, Hermes,
OpenClaw, a deterministic `shell` agent, and `custom`. Rows marked
`"verified": false` are best-effort — edit the command to match your install.

## Plan contract

```json
{"name": "release-notes", "goal": "write release notes for v1.2",
 "nodes": [
   {"id": "log",    "task": "git log --oneline v1.1..HEAD", "agent": "shell", "produces": ["log"]},
   {"id": "draft",  "task": "Draft release notes from the log.", "needs": ["research"],
    "depends_on": ["log"], "requires": ["log"], "produces": ["notes"],
    "verify": {"contains": "## "}, "max_attempts": 2},
   {"id": "commit", "task": "Commit docs/RELEASE.md with the notes.", "agent": "claude-code",
    "depends_on": ["draft"], "inputs": {"style": "ref:style_guide_node"}}
 ],
 "limits": {"max_parallel": 1, "max_output_chars": 200000},
 "approval": {"before_mutating_run": true}}
```

- `needs` ⊆ an agent's `capabilities` picks the executor (lowest `priority`
  wins); `agent` pins one. Validation fails if any node has no eligible
  executor.
- `produces` / `requires` are typed hand-offs: every `requires` must be
  produced by an ancestor.
- `inputs: {"name": "ref:<node_id>"}` consumes a node completed in an
  earlier run. Admission needs a `completed` status with an existing output
  file. Node ids are unique across runs; a completed id cannot be redefined.
- Direct dependency outputs are inlined (capped) inside
  `<untrusted-output>` fences; all transitive ancestors' output paths are
  listed; shell nodes get them as `PLAN_DEP_<ID>` environment variables.

## Run lifecycle

```bash
plan.py validate --file plan.json
plan.py new --file plan.json            # → run id, records under .agent/runtime/plans/<run>/
plan.py run <run> [--yes]               # stops at awaiting_approval when a node mutates the workspace
plan.py status <run> | plan.py report <run>
```

Per node and attempt: `prompt.md` (written before dispatch), `output.md`,
`transcript.txt`, `record.json` (verdict + consumed artifacts). Completed
nodes are appended to `registry.jsonl` with their instance handle.

## Completion adjudication

Deterministic and separate from the agent's self-report: non-zero exit,
timeout, empty output, output cut short, a `NEED_INPUT:` /
`MISSING_CREDENTIAL:` line, or a failed `verify` (`contains`, `regex`, or a
`command` with `PLAN_OUTPUT` set) all mean *not accomplished*, with a
category (`missing_user_input`, `missing_credential`, `tool_failure`,
`output_limit`, `verification_failed`). An unaccomplished node loses its
output reference, so no successor can consume it.

## Exception resolution

When attempts run out the node is suspended and
`exceptions/<node>.json` carries: node, agent, restated task, category,
what is missing, evidence, blocked dependents, extra attempts, decision
deadline, and ready-made resolution commands.

```bash
plan.py resolve <run> <node> continue --message "credentials are in .env now"   # one extra attempt
plan.py resolve <run> <node> abandon                                              # dependents skipped
plan.py resolve <run> <node> replan --file successor.json                         # new run, linked
```

A report with no decision before its deadline fails the node on the next
`run` or `status`. Replanning supersedes unfinished nodes; completed nodes
stay referenceable by `ref:`.

## Run report

Counts per status, per-node status / agent / attempts / output path / error,
and the full text of terminal outputs (completed nodes nobody depends on) up
to a cap, each fenced as untrusted data.

## Playbooks and personas

```bash
plan.py playbook save <run> --name release-notes
plan.py new --playbook release-notes --goal "release notes for v1.3"
persona.py new "ops lead who researches incidents and patches code" --name ops-lead
plan.py new --file plan.json --persona ops-lead    # executors restricted to the roster
```

A persona is `personas/<name>/PERSONA.md` (lead role prompt, specialists,
their tools and the checks from `permissions.md`) plus `roster.json`.

## Campaigns (proactivity)

```bash
proactive.py new --target "val_bpb < 1.04" --measure "python3 scripts/measure.py" \
  --on-wake "agentic-stack loop run train 'next round' . --yes" --max-rounds 7 \
  --max-runtime-seconds 7200 --done-regex "val_bpb=1\.0[0-3]"
proactive.py wake <id> --in 1800
* * * * * python3 /path/.agent/tools/proactive.py tick     # model-free monitor
proactive.py decide <id> resubmit --cite <measurement_id>
proactive.py close <id> --report report.md
```

`tick` measures, wakes due campaigns, runs `on_wake` within the remaining
budget (`CAMPAIGN_REMAINING_ROUNDS/SECONDS` in its environment), and wakes
early on `done_regex` / `diverge_regex`. Every decision cites a measurement
younger than an hour. `close` requires a `## Baseline` in the report and
refuses a success claim that the latest measurement contradicts.

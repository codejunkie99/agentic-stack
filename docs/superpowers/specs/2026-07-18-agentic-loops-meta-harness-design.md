# Agentic Loops and Meta Harness Design

**Target release:** agentic-stack v0.19.0
**Date:** 2026-07-18
**Status:** Approved design, pending written-spec review

## Summary

agentic-stack v0.19.0 adds a portable, local-first loop control plane on top of
the existing `.agent/` brain. The new control plane lets a project describe an
agentic loop once, run it through any compatible command-line harness, preserve
state between attempts, verify the result independently, and stop safely when
the loop reaches a budget, policy boundary, repeated failure, or human gate.

The release keeps agentic-stack's existing identity: one portable brain across
many harnesses. It does not replace Codex, Claude Code, OpenCode, Hermes, or the
standalone Python adapter. It supplies the durable state, constraints, budgets,
verification chain, and lifecycle management around those harnesses.

The design adapts the strongest ideas from
[`cobusgreyling/loop-engineering`](https://github.com/cobusgreyling/loop-engineering):
state as a durable spine, staged autonomy, a maker/checker split, mechanical
path gates, circuit breakers, run budgets, and loop-readiness auditing. The
implementation will be original Python integrated with agentic-stack's current
stdlib-only harness manager rather than a copy of the reference project's npm
tools.

## Goals

1. Make recurring and iterative agent work portable across supported harnesses.
2. Provide a real executable meta harness for command-line agents.
3. Preserve loop progress across process interruption and explicit approval.
4. Prevent runaway loops with mechanical attempt, time, output, and budget caps.
5. Separate implementation from verification so a maker cannot approve itself.
6. Make every run locally inspectable without enabling external telemetry.
7. Start with useful, conservative loop patterns that can graduate from report
   mode to narrowly scoped action.
8. Keep installation compatible with raw Python 3 and the current Homebrew
   packaging model.

## Non-goals

- Building another model provider SDK or replacing `.agent/harness/llm.py`.
- Running a persistent operating-system daemon or inventing a new scheduler.
- Automating merges, deployments, releases, or production writes by default.
- Claiming executable support for GUI-only harnesses that have no headless CLI.
- Providing exact token accounting when a harness does not expose usage data.
- Training or fine-tuning a model from loop traces.
- Importing LangGraph, Temporal, or the loop-engineering npm packages.

Recurring cadence remains the responsibility of the host's native automation,
cron, systemd, GitHub Actions, or another scheduler. `agentic-stack loop run`
is a deterministic one-run entrypoint that schedulers can invoke safely.

## Design principles

### Portable contract, native execution

Loop definitions live under `.agent/loops/` and do not embed provider-specific
logic. Executor profiles translate the portable roles into a command-line
harness. Projects can use a bundled profile, override it locally, or supply a
custom command profile.

### Mechanical gates before model judgment

Path rules, process timeouts, attempt caps, verification exit codes, and kill
switches are enforced in Python. An optional checker agent adds semantic review,
but cannot override a failed deterministic verification command.

### Durable state outside conversations

The runner writes an atomic checkpoint after every lifecycle transition.
Restarting a process never requires reconstructing the run from chat history.

### Progressive autonomy

- **L1 — report:** inspect and update loop state; no workspace edits requested.
- **L2 — assist:** allow bounded edits, require deterministic verification and
  human review before external publication or integration.
- **L3 — allowlisted:** permit only explicitly configured low-risk actions after
  all gates pass. v0.19.0 supports the policy level but ships no unattended
  merge, deploy, or release action.

## User-facing commands

All commands work through both `agentic-stack` and `./install.sh`.

### `agentic-stack loop init`

```text
agentic-stack loop init <name> \
  [--pattern daily-triage|ci-sweeper|pr-babysitter|custom] \
  [--harness standalone-python|codex|claude-code|opencode|hermes|custom] \
  [--target <project-dir>] [--force]
```

Creates or previews the portable loop files. Without `--force`, existing loop,
constraint, budget, or profile files are never overwritten. CLI-capable bundled
profiles are marked experimental unless covered by an integration test against
an installed binary. GUI-only adapters receive native-automation guidance
instead of a fake executable profile.

### `agentic-stack loop validate`

```text
agentic-stack loop validate [<name>] [--target <project-dir>] [--json]
```

Validates the schema, referenced executor profiles, command placeholders,
workspace-relative paths, verifier configuration, autonomy rules, and budgets.
Validation performs no agent invocation and no workspace mutation.

### `agentic-stack loop run`

```text
agentic-stack loop run <name> --task <text> \
  [--target <project-dir>] [--yes] [--json]
```

Starts a new bounded run. The default is an interactive confirmation before a
profile capable of workspace mutation is invoked. `--yes` may bypass that
initial confirmation but never bypasses path gates, hard budgets, deterministic
verification, or a configured publish/deploy approval.

Exit codes:

- `0`: completed and all required gates passed.
- `2`: invalid loop, rejected policy, approval required, or escalated run.
- `3`: deterministic verification failed and retry budget was exhausted.
- `4`: harness executable missing or harness process failed to start.
- `130`: interrupted by the user after checkpointing current state.

### `agentic-stack loop resume`

```text
agentic-stack loop resume <run-id> [--target <project-dir>] [--yes] [--json]
```

Loads a paused or interrupted checkpoint, revalidates the current loop and
policy documents, and resumes at the next incomplete phase. It refuses to
resume a completed, cancelled, or schema-incompatible run.

### `agentic-stack loop status`

```text
agentic-stack loop status [<run-id>] [--target <project-dir>] [--json]
```

Shows the latest runs or one run's task, lifecycle state, attempt count,
budgets, most recent verifier result, approval state, and escalation reason.

### `agentic-stack loop stop`

```text
agentic-stack loop stop <run-id>|--all [--target <project-dir>]
```

Marks a run cancelled or writes the project-wide pause flag. It does not send a
signal to an unrelated process. An active runner checks the flag before each
phase and terminates its owned child process cleanly when cancellation is seen.

### `agentic-stack loop cleanup`

```text
agentic-stack loop cleanup <run-id> [--target <project-dir>] [--yes]
```

Removes only the Git worktree and branch recorded as owned by the specified
terminal run. It refuses active runs, unowned paths, path mismatches, dirty
worktrees without a second explicit confirmation, and broad or unresolved
targets. Cleanup never deletes the run checkpoint or event history.

### `agentic-stack loop audit`

```text
agentic-stack loop audit [--target <project-dir>] [--json] [--strict]
```

Produces evidence-backed readiness results across these domains:

- valid loop definitions and state files;
- executor availability;
- deterministic verification;
- maker/checker separation;
- constraints and denylisted paths;
- attempt, runtime, and budget limits;
- escalation and human gates;
- actual completed or escalated run evidence.

The audit reports domain results and missing evidence rather than a decorative
single score. `--strict` exits non-zero when any configured action-capable loop
lacks a required verifier, constraint file, or human gate.

## Files and ownership

```text
.agent/
  loops/
    registry.json
    harnesses.json
    daily-triage.json
    ci-sweeper.json
    pr-babysitter.json
    constraints.json
    budget.json
  runtime/
    .gitignore
    loops/
      pause-all
      events.jsonl
      <run-id>.json
  skills/
    loop-triage/SKILL.md
    loop-verifier/SKILL.md
    loop-constraints/SKILL.md
    loop-guard/SKILL.md
```

Loop templates, default constraints, default budgets, and seed skills are
skeleton-owned. Per-run checkpoints and event logs are runtime-owned and stay
out of source control through `.agent/runtime/.gitignore`, which ignores all
runtime children while retaining the ignore file itself. `agentic-stack
upgrade` may add missing templates and skills but must not overwrite an
existing project loop, executor profile, constraint file, budget file, or
runtime state.

## Loop definition schema

Loop files use JSON so the existing stdlib implementation can parse and validate
them without PyYAML. Schema version 1 has this logical shape:

```json
{
  "schema_version": 1,
  "name": "ci-sweeper",
  "description": "Diagnose and repair one clear CI regression.",
  "autonomy": "L2",
  "executor": "maker",
  "checker": "checker",
  "state_file": ".agent/runtime/loops/ci-sweeper-state.json",
  "isolation": {
    "mode": "worktree",
    "base": "HEAD"
  },
  "instructions": {
    "initial": "Diagnose the task and make the smallest verified fix.",
    "retry": "Use the verifier feedback. Do not repeat the same failed approach.",
    "check": "Review the outcome independently against the task and constraints."
  },
  "verification": {
    "command": ["python3", "-m", "pytest"],
    "timeout_seconds": 900
  },
  "limits": {
    "max_attempts": 3,
    "max_runtime_seconds": 3600,
    "max_output_chars": 200000,
    "estimated_token_budget": 200000,
    "stagnation_threshold": 2
  },
  "approval": {
    "before_first_mutating_run": true,
    "before_external_write": true
  },
  "tags": ["engineering", "ci"]
}
```

Required fields are explicit. Unknown top-level fields fail validation so typos
do not silently disable a safety control. Commands must be non-empty arrays of
strings. Paths must be relative to the target project and cannot traverse with
`..` components.

## Executor profile schema

`harnesses.json` maps role names to process profiles:

```json
{
  "schema_version": 1,
  "profiles": {
    "maker": {
      "adapter": "custom",
      "command": ["my-agent", "run", "{prompt}"],
      "timeout_seconds": 1200,
      "mutates_workspace": true,
      "capabilities": ["workspace_write"],
      "usage_source": "none"
    },
    "checker": {
      "adapter": "custom",
      "command": ["my-agent", "review", "{prompt}"],
      "timeout_seconds": 600,
      "mutates_workspace": false,
      "capabilities": [],
      "usage_source": "none"
    }
  }
}
```

Supported placeholders are `{prompt}`, `{task}`, `{target}`, `{run_id}`, and
`{attempt}`. Expansion happens per argument and never through a shell. The
runner sets a controlled working directory, inherits the user's environment,
and records executable names but redacts argument values from default events.
Known capabilities are `workspace_write`, `network_read`, and `external_write`.
Profiles must declare capabilities explicitly; an `external_write` profile is
always approval-gated in v0.19.0.

A checker must reference a distinct profile name from the maker. It may use the
same underlying binary, but receives separate instructions and a fresh process.
The deterministic verification command remains authoritative even when the
checker returns approval.

## Worktree isolation

L2 and L3 loops default to `isolation.mode = "worktree"`. Before invoking the
maker, the runner creates a dedicated Git worktree and branch from the validated
base revision. Every retry in that run stays in the same isolated worktree so
the maker can build on its prior attempt and verifier feedback. Separate runs
never share a worktree.

The default root is a sibling of the target repository:
`.agentic-stack-worktrees/<project>/<run-id>`. An
`AGENTIC_STACK_WORKTREE_ROOT` override is accepted only after resolving it to an
absolute, non-root path. The checkpoint records the exact repository identity,
branch, worktree path, and base commit before execution.

L1 report loops may use `isolation.mode = "current"` because they request no
workspace edits. An L2 or L3 loop configured for the current workspace requires
an explicit approval on every run and the audit reports the reduced isolation.
Non-Git targets cannot run bundled action-capable patterns; they must use L1 or
provide a custom sandbox outside this release's guarantees.

Completed worktrees are preserved for human inspection. Failed, cancelled, and
escalated worktrees are also preserved for forensics. Only `loop cleanup`
removes a worktree, and only after ownership and dirtiness checks.

## Run checkpoint schema

Every run checkpoint contains:

- schema version and unique run id;
- loop name and a digest of the validated loop contract;
- task and target root;
- lifecycle status and current phase;
- start/update/end timestamps;
- ordered attempts with process and verifier outcomes;
- owned worktree path, branch, repository identity, and base revision;
- accumulated runtime, output characters, and any reported token usage;
- approvals and policy decisions;
- final result or escalation reason.

Checkpoint writes use a temporary sibling plus `os.replace()` so interruption
cannot leave a half-written JSON file. Resume compares the stored contract
digest with the current loop. If safety rules became stricter, the stricter
current rules apply. If the execution contract changed incompatibly, the run
escalates instead of guessing how to continue.

## Lifecycle

```text
created
  -> validating
  -> awaiting_approval (when required)
  -> running_maker
  -> running_verifier
  -> running_checker (when configured)
  -> completed

Retry path:
running_verifier or running_checker
  -> feedback_ready
  -> breaker_check
  -> running_maker

Terminal non-success states:
cancelled | escalated | failed_to_start
```

Before every phase the runner checks, in order:

1. project-wide and run-specific kill switches;
2. elapsed runtime and attempt count;
3. estimated or reported token budget;
4. output-size budget;
5. repeated-failure stagnation;
6. current constraints and approval requirements.

The next maker prompt contains the original task, stable loop instructions,
current constraints, and a compact summary of prior failures. It does not inject
the entire raw transcript. This limits context growth and avoids teaching the
maker to repeat verbose failed traces.

## Verification and checker semantics

The verifier command runs after every maker attempt in the target workspace.
Exit code `0` is a deterministic pass. Any other exit code is a failure whose
bounded stdout/stderr becomes feedback for the next attempt.

When a checker profile is configured, the runner invokes it only after the
deterministic verifier passes. The checker receives the task, constraints,
changed-file list, verifier summary, and maker result summary. Its final
non-empty line must be one of:

```text
APPROVE
REJECT: <actionable reason>
ESCALATE: <reason requiring human judgment>
```

Malformed checker output escalates. `REJECT` consumes another attempt if the
attempt budget remains. `ESCALATE` pauses immediately. `APPROVE` completes only
if every deterministic gate also passed.

## Constraints and path gates

`constraints.json` provides a machine-enforced policy:

```json
{
  "schema_version": 1,
  "deny_paths": [
    ".env",
    ".env.*",
    "**/secrets/**",
    "**/credentials/**",
    "auth/**",
    "payments/**",
    "billing/**",
    "**/migrations/**"
  ],
  "allow_paths": [],
  "max_changed_files": 10,
  "external_writes_require_approval": true
}
```

Before the maker starts, the runner records the isolated worktree baseline.
After each maker process, it obtains changed paths from Git. A denylisted path,
a path outside a non-empty allowlist, or excessive file count escalates before
verification. Because the maker ran in an isolated worktree, a policy violation
does not alter the user's active checkout. Non-Git targets cannot use bundled
action-capable loops because the runner cannot reliably distinguish changes.

The runner does not attempt to sandbox the child process. It is a supervisor,
not an operating-system security boundary. Documentation must state this
plainly. Harness-native sandboxes and approvals remain important.

## Budgets and circuit breaker

Hard limits are enforced locally:

- maximum attempts;
- total wall-clock runtime;
- per-process timeout;
- captured output characters;
- estimated or harness-reported tokens;
- repeated normalized failure signatures.

When exact usage is unavailable, the runner estimates tokens from captured text
and labels the value `estimated`. A budget decision never presents an estimate
as exact billing data.

Failure signatures normalize whitespace, volatile timestamps, absolute target
paths, and long numeric identifiers. If the configured number of consecutive
failures have the same normalized signature, the runner escalates rather than
spending the remaining attempts on the same approach.

## Events and privacy

`.agent/runtime/loops/events.jsonl` is append-only and local. Events include:

- run and loop ids;
- lifecycle transition;
- timestamp and duration;
- attempt number;
- child exit status;
- verifier/checker decision;
- budget counters;
- changed paths;
- escalation category.

Default events do not include task text, prompt text, command arguments, model
output, environment variables, or verifier output. The per-run checkpoint keeps
only the bounded text required for resume and feedback. The existing flywheel
export remains opt-in and continues to require redaction and human approval.

## Bundled patterns

### Daily triage

- L1 report-only.
- Reads current project and loop state.
- Updates a structured local state artifact.
- No checker required because it cannot request workspace mutations.
- Suitable for native schedulers and automation systems.

### CI sweeper

- L2 assisted.
- Handles one clear failure per run.
- Runs in a dedicated Git worktree.
- Maximum three maker attempts.
- Requires a deterministic project test command and checker approval.
- Denylisted paths and external writes always escalate.

### PR babysitter

- L1 by default.
- Reports red CI, conflicts, review comments, and stale responses.
- Does not push, comment, merge, or edit code in the bundled profile.
- Projects may explicitly graduate a copy to L2 after adding connector scopes,
  a verifier, constraints, and human approval.

### Custom evaluator loop

- User supplies maker, optional checker, verification command, and limits.
- Validation refuses L2 or L3 without deterministic verification.
- Serves as the escape hatch for research, documentation, and domain workflows.

## Integration with existing agentic-stack features

### Installation and upgrades

Fresh installations receive the loop runtime modules, schemas, default skills,
and starter templates. Existing projects receive them only through the safe
`agentic-stack upgrade` path. User-authored loops and runtime state are never
overwritten.

### Doctor, status, dashboard, and Mission Control

- `doctor` warns about invalid loop definitions and missing referenced profiles.
- `status` adds a one-line loop summary when loop files exist.
- The terminal dashboard adds recent run and pause-state information.
- Mission Control may consume the same read-only collectors, but v0.19.0 does
  not add mutation endpoints for loop control.

The CLI loop commands are the authoritative management surface for this release.

### Data layer and flywheel

Loop events are a new local input source for the existing data layer. Approved,
redacted completed runs may later feed the flywheel through the existing export
workflow. No automatic training artifact generation occurs during `loop run`.

### External Brain integration

The meta harness can include durable Brain notes in a prompt only when a loop's
skill explicitly requests them. Brain is not required for loop execution, and
the loop runner does not write global memory automatically.

## Error handling

- Missing executable: checkpoint `failed_to_start`, print install/profile
  guidance, exit `4`.
- Invalid JSON or schema: report the exact file and field, perform no invocation,
  exit `2`.
- Child timeout: terminate the owned process, record bounded output, and treat
  it as a failed attempt subject to the breaker.
- Keyboard interrupt: terminate the owned child, atomically checkpoint, exit
  `130`, and allow resume.
- Verifier failure: preserve bounded feedback and retry only when every budget
  and policy gate permits it.
- Checker malformed output: escalate; do not infer approval.
- Checkpoint corruption: retain the corrupt file, refuse resume, and direct the
  user to start a new run. Never silently replace history.
- Event-write failure: checkpoint remains authoritative; warn without changing
  a verified run into success if required audit evidence could not be written.

## Testing strategy

Implementation follows red-green-refactor. The tests use temporary directories
and fake Python harness executables so they need no API key or external agent.

Required coverage:

1. Loop, profile, constraint, and budget schema validation.
2. Safe placeholder expansion without shell evaluation.
3. Successful maker and deterministic verifier lifecycle.
4. Verifier feedback carried into a later successful attempt.
5. Independent checker approve, reject, escalate, and malformed-output paths.
6. Attempt, runtime, process-timeout, output, and token budget enforcement.
7. Repeated-failure stagnation detection.
8. Denylisted path and changed-file-count escalation.
9. Worktree creation, ownership validation, preservation, and safe cleanup.
10. Atomic checkpoints and resume after interruption.
11. Kill switch and cancellation behavior.
12. Privacy-safe default event records.
13. `init`, `validate`, `run`, `resume`, `status`, `stop`, `cleanup`, and `audit` CLI output
    and exit codes.
14. Safe upgrade behavior that preserves project-authored loops and runtime data.
15. Doctor/status/dashboard read-only integration.
16. POSIX installer help, PowerShell help, Homebrew formula packaging, README,
    getting-started documentation, and changelog coverage.
17. Full existing pytest suite regression check.

At least one integration test runs a fake maker that fails verification on its
first attempt, reads the injected verifier feedback on its second attempt,
changes its output, and reaches completion. This proves the implementation is a
real feedback loop rather than a sequence of mocked return values.

## Release plan

This is a minor semantic-version release: v0.19.0.

1. Implement on `codex/agentic-loops-meta-harness` from the current live master.
2. Run focused tests during each red-green cycle.
3. Run the complete pytest suite and documentation/CLI smoke checks.
4. Review the final diff against every requirement in this specification.
5. Commit the feature and release documentation.
6. Integrate to master using the repository's established release workflow.
7. Create and push annotated tag `v0.19.0`.
8. Create the GitHub release from the verified tag.
9. Compute the tag tarball SHA-256 and update the Homebrew formula in a
   follow-up commit, matching the v0.18.0 convention.
10. Push the formula update and verify the remote tag, release, and branch state.

## Acceptance criteria

v0.19.0 is complete only when all of the following are evidenced:

- a project can initialize and validate a portable loop;
- a fake command-line harness completes a maker/verifier feedback cycle;
- a distinct checker can approve, reject, or escalate;
- interrupted or approval-paused runs can resume from an atomic checkpoint;
- constraints, budgets, stagnation, and kill switches stop execution
  mechanically;
- action-capable runs are isolated in owned worktrees and cleanup cannot target
  unrelated directories;
- status and audit explain the current state without exposing prompt contents;
- existing installations can upgrade without losing user-authored loop data;
- current non-loop features retain passing regression coverage;
- README, getting-started docs, changelog, installer help, version metadata, and
  release notes describe the shipped behavior accurately;
- the v0.19.0 tag and GitHub release exist on the requested repository;
- the Homebrew formula points to the v0.19.0 tag with the verified tarball hash.

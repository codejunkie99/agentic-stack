# Agentic Loops and Meta Harness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship agentic-stack v0.19.0 with portable loop definitions, a bounded and resumable meta harness, independent verification, worktree isolation, policy gates, local observability, and safe installed-project upgrades.

**Architecture:** Add a focused `harness_manager.loops` package. Pure schema and policy modules validate local JSON contracts; storage atomically persists checkpoints and privacy-safe events; process and worktree modules own external resources; runner composes those pieces into the maker-verifier-checker lifecycle; commands expose the lifecycle through the existing dispatcher. Bundled `.agent/loops` assets and seed skills make the same contract portable across installed harnesses.

**Tech Stack:** Python 3 standard library, `argparse`, `dataclasses`, JSON/JSONL, `subprocess`, Git worktrees, pytest, existing shell/PowerShell installers, Homebrew formula.

---

## File structure

### New implementation files

- `harness_manager/loops/__init__.py` — public loop package exports and versioned constants.
- `harness_manager/loops/schema.py` — strict JSON loading, path safety, and contract validation.
- `harness_manager/loops/storage.py` — atomic checkpoints, append-only privacy-safe events, run lookup.
- `harness_manager/loops/policy.py` — budgets, failure signatures, path gates, breaker decisions.
- `harness_manager/loops/process.py` — placeholder expansion and bounded child-process execution without a shell.
- `harness_manager/loops/worktrees.py` — isolated Git worktree creation, ownership verification, and cleanup.
- `harness_manager/loops/runner.py` — maker/verifier/checker lifecycle, retries, pause/resume, cancellation.
- `harness_manager/loops/commands.py` — loop subcommand parser and user-facing command handlers.
- `.agent/loops/registry.json` — bundled pattern registry.
- `.agent/loops/harnesses.json` — safe starter executor profiles.
- `.agent/loops/{daily-triage,ci-sweeper,pr-babysitter}.json` — bundled loop contracts.
- `.agent/loops/{constraints,budget}.json` — default mechanical safety and budgets.
- `.agent/runtime/.gitignore` — keeps runtime state local.
- `.agent/skills/{loop-triage,loop-verifier,loop-constraints,loop-guard}/SKILL.md` — portable loop skills.
- `tests/test_loop_schema.py` — schemas and path safety.
- `tests/test_loop_storage_policy.py` — checkpoints, events, budgets, stagnation, path rules.
- `tests/test_loop_process.py` — safe command invocation, output bounds, timeout.
- `tests/test_loop_worktrees.py` — isolated ownership and safe cleanup.
- `tests/test_loop_runner.py` — real fake-harness feedback loops and resume behavior.
- `tests/test_loop_cli.py` — all loop verbs and exit codes.
- `tests/test_loop_integrations.py` — installation, upgrade, doctor/status/dashboard/data-layer integration.

### Existing files modified

- `harness_manager/cli.py` — register and dispatch the `loop` verb.
- `harness_manager/upgrade.py` — add only missing loop assets; preserve user-authored contracts and runtime data.
- `harness_manager/doctor.py` — read-only loop validation warnings/failures.
- `harness_manager/status.py` — compact loop count, pause, and latest-run summary.
- `harness_manager/dashboard_tui.py` — read-only recent-loop section.
- `harness_manager/mission_control_collectors.py` — expose read-only loop objects through the existing runs payload.
- `.agent/tools/data_layer_export.py` — ingest privacy-safe loop events.
- `.agent/skills/_manifest.jsonl` and `.agent/skills/_index.md` — register seed skills.
- `install.sh` and `install.ps1` — document the loop verb in help.
- `Formula/agentic-stack.rb` — package/smoke-test loops; tag hash updated only after tagging.
- `harness_manager/__init__.py` — v0.19.0 version.
- `README.md`, `docs/getting-started.md`, `CHANGELOG.md` — release behavior and operational caveats.

## Task 1: Strict portable loop schemas

**Files:**
- Create: `harness_manager/loops/__init__.py`
- Create: `harness_manager/loops/schema.py`
- Create: `tests/test_loop_schema.py`

- [ ] **Step 1: Write failing schema tests**

Create tests that exercise concrete public functions:

```python
from pathlib import Path
import json
import pytest

from harness_manager.loops.schema import ContractError, load_contracts, validate_loop


def valid_loop():
    return {
        "schema_version": 1,
        "name": "ci-sweeper",
        "description": "Fix one CI regression.",
        "autonomy": "L2",
        "executor": "maker",
        "checker": "checker",
        "state_file": ".agent/runtime/loops/ci-sweeper-state.json",
        "isolation": {"mode": "worktree", "base": "HEAD"},
        "instructions": {"initial": "Fix it.", "retry": "Use feedback.", "check": "Review it."},
        "verification": {"command": ["python3", "-m", "pytest"], "timeout_seconds": 30},
        "limits": {
            "max_attempts": 3,
            "max_runtime_seconds": 60,
            "max_output_chars": 10000,
            "estimated_token_budget": 5000,
            "stagnation_threshold": 2,
        },
        "approval": {"before_first_mutating_run": True, "before_external_write": True},
        "tags": ["ci"],
    }


def test_valid_loop_is_normalized():
    loop = validate_loop(valid_loop(), "test.json")
    assert loop["name"] == "ci-sweeper"
    assert loop["isolation"]["mode"] == "worktree"


@pytest.mark.parametrize("path", ["../outside", "/tmp/outside", "C:\\outside", "\\\\server\\share"])
def test_state_path_cannot_escape_project(path):
    raw = valid_loop()
    raw["state_file"] = path
    with pytest.raises(ContractError, match="state_file"):
        validate_loop(raw, "bad.json")


def test_l2_requires_verifier_checker_and_worktree():
    raw = valid_loop()
    raw.pop("checker")
    with pytest.raises(ContractError, match="checker"):
        validate_loop(raw, "bad.json")


def test_unknown_fields_fail_closed():
    raw = valid_loop()
    raw["max_atempts"] = 3
    with pytest.raises(ContractError, match="unknown"):
        validate_loop(raw, "bad.json")
```

- [ ] **Step 2: Verify the tests fail for the missing module**

Run: `python3 -m pytest tests/test_loop_schema.py -q`

Expected: collection fails with `ModuleNotFoundError: harness_manager.loops`.

- [ ] **Step 3: Implement strict schema validation**

Define these public interfaces in `schema.py`:

```python
SCHEMA_VERSION = 1
AUTONOMY_LEVELS = {"L1", "L2", "L3"}
CAPABILITIES = {"workspace_write", "network_read", "external_write"}
PLACEHOLDERS = {"prompt", "task", "target", "run_id", "attempt"}

class ContractError(ValueError):
    pass

validate_loop(raw: object, source: str) -> dict
validate_profiles(raw: object, source: str) -> dict
validate_constraints(raw: object, source: str) -> dict
validate_budget(raw: object, source: str) -> dict
load_contracts(target_root: Path, loop_name: str) -> dict[str, dict]
safe_relative_path(value: str, source: str, field: str) -> Path
```

Implementation requirements:

- require exact keys and reject unknown keys at every safety-relevant object;
- reject booleans where positive integers are required;
- reject shell-string commands; commands are non-empty string arrays;
- parse placeholders with `string.Formatter` and reject unknown or formatted placeholders;
- require L2/L3 loops to have verification, a distinct checker profile, and worktree isolation unless a per-run approval later overrides current-workspace mode;
- require checker profiles to be non-mutating and exclude `external_write`;
- resolve all files from `<target>/.agent/loops` without following a contract-supplied absolute path;
- return JSON-compatible normalized dictionaries so checkpoints can hash contracts deterministically.

- [ ] **Step 4: Run schema tests green**

Run: `python3 -m pytest tests/test_loop_schema.py -q`

Expected: all schema tests pass.

- [ ] **Step 5: Commit**

```bash
git add harness_manager/loops/__init__.py harness_manager/loops/schema.py tests/test_loop_schema.py
git commit -m "feat(loops): validate portable loop contracts"
```

## Task 2: Atomic storage, policy gates, budgets, and stagnation

**Files:**
- Create: `harness_manager/loops/storage.py`
- Create: `harness_manager/loops/policy.py`
- Create: `tests/test_loop_storage_policy.py`

- [ ] **Step 1: Write failing storage and policy tests**

Cover these behaviors with real temporary files:

```python
def test_checkpoint_write_is_atomic_and_round_trips(tmp_path):
    run = {"schema_version": 1, "run_id": "run-1", "status": "created", "task": "secret task"}
    save_checkpoint(tmp_path, run)
    assert load_checkpoint(tmp_path, "run-1") == run
    assert not list((tmp_path / ".agent/runtime/loops").glob("*.tmp"))


def test_event_excludes_sensitive_fields(tmp_path):
    append_event(tmp_path, {"run_id": "run-1", "event": "maker_finished", "task": "secret", "prompt": "secret"})
    event = json.loads((tmp_path / ".agent/runtime/loops/events.jsonl").read_text())
    assert event == {"run_id": "run-1", "event": "maker_finished"}


def test_corrupt_checkpoint_is_preserved_and_rejected(tmp_path):
    path = runtime_dir(tmp_path) / "run-1.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    with pytest.raises(CheckpointError, match="corrupt"):
        load_checkpoint(tmp_path, "run-1")
    assert path.read_text(encoding="utf-8") == "{broken"


def test_repeated_failure_trips_stagnation():
    attempts = [
        {"outcome": "failed", "verifier_output": "FAILED at /tmp/a/test.py:123"},
        {"outcome": "failed", "verifier_output": "FAILED at /tmp/b/test.py:456"},
    ]
    decision = evaluate_breaker(attempts, limits={"stagnation_threshold": 2}, counters={})
    assert decision.stop and decision.reason == "stagnation"


def test_deny_path_and_allow_path_fail_closed():
    policy = {"deny_paths": ["auth/**"], "allow_paths": ["src/**"], "max_changed_files": 3}
    assert check_changed_paths(["auth/token.py"], policy).reason == "deny_path"
    assert check_changed_paths(["docs/readme.md"], policy).reason == "outside_allowlist"
```

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_loop_storage_policy.py -q`

Expected: import failure for missing storage/policy modules.

- [ ] **Step 3: Implement storage interfaces**

`storage.py` must expose:

```python
RUNTIME_REL = Path(".agent/runtime/loops")
EVENT_FIELDS = {
    "run_id", "loop", "event", "timestamp", "duration_seconds", "attempt",
    "exit_code", "decision", "reason", "status", "changed_paths", "counters",
}

runtime_dir(target_root: Path) -> Path
checkpoint_path(target_root: Path, run_id: str) -> Path
save_checkpoint(target_root: Path, payload: dict) -> Path
load_checkpoint(target_root: Path, run_id: str) -> dict
list_checkpoints(target_root: Path) -> list[dict]
append_event(target_root: Path, payload: dict) -> None
set_pause_all(target_root: Path, paused: bool) -> None
is_paused(target_root: Path) -> bool
```

Use `tempfile.NamedTemporaryFile(dir=destination.parent, delete=False)`, flush,
`os.fsync`, and `os.replace`. Validate run ids against `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$` before path construction. Event filtering must construct a new dictionary from `EVENT_FIELDS`; never mutate and serialize the caller's full payload.
Define `CheckpointError` and preserve unreadable/corrupt source files. Event
append failures must be reported to the runner and cannot be silently converted
into successful audit evidence.

- [ ] **Step 4: Implement policy interfaces**

`policy.py` must expose immutable decisions:

```python
@dataclass(frozen=True)
class Decision:
    stop: bool
    reason: str | None = None
    detail: str | None = None

normalize_failure(text: str, target_root: Path | None = None) -> str
estimate_tokens(*texts: str) -> int  # ceil(total characters / 4)
evaluate_breaker(attempts: list[dict], limits: dict, counters: dict) -> Decision
check_changed_paths(paths: list[str], constraints: dict) -> Decision
```

Check pause/attempt/runtime/token/output limits before stagnation in the runner,
but normalize failure text by removing absolute roots, ISO timestamps, line
numbers, and long ids so equivalent failures compare equal. Use
`PurePosixPath.match` plus `fnmatch.fnmatchcase` for root and recursive glob
compatibility. Reject absolute or `..` changed paths as `path_escape`.

- [ ] **Step 5: Run storage/policy tests green and commit**

Run: `python3 -m pytest tests/test_loop_storage_policy.py -q`

```bash
git add harness_manager/loops/storage.py harness_manager/loops/policy.py tests/test_loop_storage_policy.py
git commit -m "feat(loops): persist runs and enforce policy budgets"
```

## Task 3: Safe bounded subprocess execution

**Files:**
- Create: `harness_manager/loops/process.py`
- Create: `tests/test_loop_process.py`

- [ ] **Step 1: Write failing process tests**

Use temporary Python scripts rather than mocks:

```python
def test_expansion_is_per_argument_and_never_uses_shell(tmp_path):
    result = run_profile(
        profile={"command": [sys.executable, "-c", "import sys; print(sys.argv[1])", "{prompt}"], "timeout_seconds": 5},
        values={"prompt": "hello; touch owned", "task": "", "target": str(tmp_path), "run_id": "r1", "attempt": "1"},
        cwd=tmp_path,
        max_output_chars=1000,
    )
    assert result.stdout.strip() == "hello; touch owned"
    assert not (tmp_path / "owned").exists()


```

Add three separate tests that assert: a sleeping child returns
`timed_out=True` and no longer exists; 10,000 emitted characters produce a
bounded retained string with `output_chars == 10000`; and an unknown executable
returns `status == "failed_to_start"`, `exit_code is None`, and a non-empty
error message.

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_loop_process.py -q`

Expected: import failure for `harness_manager.loops.process`.

- [ ] **Step 3: Implement the process boundary**

```python
@dataclass(frozen=True)
class ProcessResult:
    status: str
    exit_code: int | None
    stdout: str
    stderr: str
    output_chars: int
    duration_seconds: float
    timed_out: bool = False
    error: str | None = None

expand_command(command: list[str], values: dict[str, str]) -> list[str]
run_profile(profile: dict, values: dict[str, str], cwd: Path, max_output_chars: int) -> ProcessResult
```

Invoke `subprocess.Popen(argv, cwd=cwd, text=True, stdout=PIPE, stderr=PIPE,
start_new_session=True)` with no shell. On timeout, terminate the owned process
group on POSIX and the owned process on Windows, wait briefly, then kill only
that group/process. Capture full counts while retaining only the configured
prefix and suffix separated by an omission marker. Convert `FileNotFoundError`
to `failed_to_start`; re-raise programmer errors.

- [ ] **Step 4: Run green and commit**

Run: `python3 -m pytest tests/test_loop_process.py -q`

```bash
git add harness_manager/loops/process.py tests/test_loop_process.py
git commit -m "feat(loops): run harness commands safely"
```

## Task 4: Owned Git worktree isolation and cleanup

**Files:**
- Create: `harness_manager/loops/worktrees.py`
- Create: `tests/test_loop_worktrees.py`

- [ ] **Step 1: Write failing worktree tests**

Create a real temporary Git repository with local user configuration and one
commit. Test:

```python
def test_create_worktree_records_identity_branch_and_base(repo):
    owned = create_worktree(repo, "ci-sweeper", "run-123", root=repo.parent / "owned")
    assert owned.path.is_dir()
    assert owned.base_commit == git(repo, "rev-parse", "HEAD").strip()
    assert owned.branch == "agentic-loop/ci-sweeper/run-123"


```

Add separate cleanup tests that assert: an unregistered path raises
`WorktreeError`; a dirty owned worktree raises unless `allow_dirty=True`; a
clean registered worktree disappears from `git worktree list --porcelain`; and
`/`, the repository, its parent, or the worktree root itself is rejected as an
override/cleanup target.

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_loop_worktrees.py -q`

- [ ] **Step 3: Implement worktree ownership**

```python
@dataclass(frozen=True)
class OwnedWorktree:
    repository: str
    path: Path
    branch: str
    base_commit: str

repository_identity(target_root: Path) -> tuple[Path, str]
worktree_root(target_root: Path, override: str | None = None) -> Path
create_worktree(target_root: Path, loop_name: str, run_id: str, root: Path | None = None) -> OwnedWorktree
changed_paths(owned: OwnedWorktree) -> list[str]
cleanup_worktree(target_root: Path, owned: OwnedWorktree, *, allow_dirty: bool = False) -> None
```

Use argument-array Git commands. Resolve and compare repository common-dir
identity, verify the worktree appears in `git worktree list --porcelain`, verify
branch and path match the checkpoint, and refuse paths equal to `/`, the target
repository, its parent, or the configured worktree root itself. Use `git
worktree remove` and `git branch -d` only after checks; never recursive-delete a
path directly.

- [ ] **Step 4: Run green and commit**

Run: `python3 -m pytest tests/test_loop_worktrees.py -q`

```bash
git add harness_manager/loops/worktrees.py tests/test_loop_worktrees.py
git commit -m "feat(loops): isolate action runs in owned worktrees"
```

## Task 5: Resumable maker-verifier-checker orchestration

**Files:**
- Create: `harness_manager/loops/runner.py`
- Create: `tests/test_loop_runner.py`

- [ ] **Step 1: Write the end-to-end failing feedback-loop test**

Build a fake maker script that reads the prompt from `sys.argv`, writes an
incorrect file on attempt one, detects `VERIFIER FEEDBACK` on attempt two, and
writes the correct file. Use a verifier script that exits non-zero until the
file is correct and a checker script whose last line is `APPROVE`.

Assertions:

```python
result = start_run(target, "ci-sweeper", "make result equal green", approved=True)
assert result["status"] == "completed"
assert len(result["attempts"]) == 2
assert result["attempts"][0]["verifier"]["exit_code"] != 0
assert "VERIFIER FEEDBACK" in result["attempts"][1]["prompt_summary"]
assert result["attempts"][1]["checker"]["decision"] == "APPROVE"
assert Path(result["worktree"]["path"], "result.txt").read_text() == "green"
```

Also add tests for checker `REJECT`, `ESCALATE`, malformed output, initial
approval pause, `resume_run`, Ctrl-C checkpoint simulation, cancellation,
deny-path escalation, token/output/runtime breaker decisions, and contract hash
mismatch on resume. Add an event-write-failure test that proves a run cannot
report ordinary success when its required terminal audit event was not written.

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_loop_runner.py -q`

- [ ] **Step 3: Implement runner lifecycle**

Public API:

```python
new_run_id(now: datetime | None = None) -> str
contract_digest(contracts: dict[str, dict]) -> str
start_run(target_root: Path, loop_name: str, task: str, *, approved: bool = False) -> dict
resume_run(target_root: Path, run_id: str, *, approved: bool = False) -> dict
cancel_run(target_root: Path, run_id: str) -> dict
parse_checker(output: str) -> tuple[str, str | None]
```

Lifecycle implementation order:

1. load and validate contracts;
2. construct and atomically save `created` checkpoint;
3. pause as `awaiting_approval` before any mutating/external-write profile when
   approval is absent;
4. create or reopen the owned worktree;
5. before every phase, check cancellation, pause-all, runtime/output/token
   counters, attempt cap, and stagnation;
6. invoke maker with original task, stable instructions, constraints, and only
   the compact last failure feedback;
7. collect changed paths and apply policy before verification;
8. run deterministic verifier directly through the same bounded process layer;
9. after verifier pass, invoke the distinct checker and parse only its last
   non-empty line;
10. checkpoint and emit filtered event after every transition;
11. complete only on verifier pass plus checker approval (when configured);
12. preserve owned worktree for every terminal status.

Catch `KeyboardInterrupt` only around owned child execution, checkpoint
`interrupted`, re-raise or return an exit-code-mappable result, and never mark it
completed. A resume re-loads current contracts, applies stricter current safety
settings, and refuses incompatible execution fields when the digest changed.

- [ ] **Step 4: Run runner tests green and commit**

Run: `python3 -m pytest tests/test_loop_runner.py -q`

```bash
git add harness_manager/loops/runner.py tests/test_loop_runner.py
git commit -m "feat(loops): orchestrate resumable verified feedback loops"
```

## Task 6: Complete loop CLI surface

**Files:**
- Create: `harness_manager/loops/commands.py`
- Create: `tests/test_loop_cli.py`
- Modify: `harness_manager/cli.py`
- Modify: `install.sh`
- Modify: `install.ps1`

- [ ] **Step 1: Write failing CLI tests**

Run the real module dispatcher in temporary installed projects. Cover:

- `loop init`, no-overwrite, and `--force`;
- `loop validate` text/JSON and invalid-contract exit `2`;
- `loop run` approval pause and approved completion;
- `loop resume`, `status`, `stop <id>`, `stop --all`, `cleanup`, and `audit`;
- dirty cleanup requires a second explicit confirmation even when the first
  command confirmation was accepted;
- missing executable exit `4`, exhausted verification exit `3`, Ctrl-C mapping
  `130` at the command boundary;
- POSIX and PowerShell help include the same verbs.

- [ ] **Step 2: Run CLI tests red**

Run: `python3 -m pytest tests/test_loop_cli.py -q`

- [ ] **Step 3: Implement commands without growing the root dispatcher**

`commands.py` owns its nested parser:

```python
run(argv: list[str], *, default_target: Path, stack_root: Path) -> int
cmd_init(ns: argparse.Namespace, stack_root: Path) -> int
cmd_validate(ns: argparse.Namespace) -> int
cmd_run(ns: argparse.Namespace) -> int
cmd_resume(ns: argparse.Namespace) -> int
cmd_status(ns: argparse.Namespace) -> int
cmd_stop(ns: argparse.Namespace) -> int
cmd_cleanup(ns: argparse.Namespace) -> int
cmd_audit(ns: argparse.Namespace) -> int
```

Add only `"loop"` to `VERBS` and `cmd_loop(args)` to `harness_manager/cli.py`.
Route global `--yes` into loop arguments exactly as the Brain onboarding route
does. JSON output must be one valid JSON object with no banners. Text output
must always include run id and terminal/pause reason.

`init` copies selected skeleton assets with `shutil.copy2`; it never overwrites
unless `--force`, and even `--force` refuses `.agent/runtime`. `audit --strict`
returns non-zero for L2/L3 missing verification, checker, constraints, budgets,
isolation, or run evidence.

- [ ] **Step 4: Run CLI tests green and commit**

Run: `python3 -m pytest tests/test_loop_cli.py -q`

```bash
git add harness_manager/loops/commands.py harness_manager/cli.py install.sh install.ps1 tests/test_loop_cli.py
git commit -m "feat(loops): expose loop lifecycle commands"
```

## Task 7: Portable loop assets and safe upgrades

**Files:**
- Create: `.agent/loops/*.json`
- Create: `.agent/runtime/.gitignore`
- Create: `.agent/skills/loop-*/SKILL.md`
- Modify: `.agent/skills/_manifest.jsonl`
- Modify: `.agent/skills/_index.md`
- Modify: `harness_manager/upgrade.py`
- Modify: `tests/test_upgrade_manifest_doctor.py`
- Create: `tests/test_loop_integrations.py`

- [ ] **Step 1: Write failing asset and upgrade tests**

Assert every bundled JSON file validates, every seed skill has required
frontmatter, fresh install includes assets, and upgrade behavior is asymmetric:

```python
def test_upgrade_adds_missing_loop_assets_but_preserves_authored_contract(tmp_path):
    target = installed_project(tmp_path)
    authored = target / ".agent/loops/ci-sweeper.json"
    authored.parent.mkdir(parents=True)
    authored.write_text('{"user": "owned"}')
    rc = upgrade(target, ROOT, yes=True)
    assert rc == 0
    assert authored.read_text() == '{"user": "owned"}'
    assert (target / ".agent/loops/daily-triage.json").exists()
    assert (target / ".agent/runtime/.gitignore").exists()
```

Also assert runtime children are neither planned nor copied and existing loop
skills are not overwritten.

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_loop_integrations.py tests/test_upgrade_manifest_doctor.py -q`

- [ ] **Step 3: Add bundled contracts and skills**

Assets must match the approved spec:

- `daily-triage`: L1, current workspace, non-mutating profile, no checker;
- `ci-sweeper`: L2, worktree, three attempts, verifier and checker required;
- `pr-babysitter`: L1 report-only, no push/comment/merge capability;
- constraints include deny paths, empty allowlist, ten-file cap, approval for
  external writes;
- budgets set conservative finite defaults;
- harness profiles use the existing standalone Python entrypoint where it is
  actually executable and ship documented custom placeholders for other CLIs
  rather than unverified flags;
- skill frontmatter follows current manifest fields and explicitly requires
  reading contracts/state before acting.

- [ ] **Step 4: Extend safe upgrade planning**

Add a `_new_loop_assets(src_agent, dst_agent)` helper. It returns only source
files whose destination does not exist, limited to `.agent/loops/**`,
`.agent/runtime/.gitignore`, and newly absent loop skill directories. Do not add
loops to `_infrastructure_files`, because that function overwrites changed
destinations by design.

- [ ] **Step 5: Run green and commit**

Run: `python3 -m pytest tests/test_loop_integrations.py tests/test_upgrade_manifest_doctor.py -q`

```bash
git add .agent/loops .agent/runtime/.gitignore .agent/skills/loop-* .agent/skills/_manifest.jsonl .agent/skills/_index.md harness_manager/upgrade.py tests/test_loop_integrations.py tests/test_upgrade_manifest_doctor.py
git commit -m "feat(loops): install portable loop starters"
```

## Task 8: Read-only health, dashboard, Mission Control, and data-layer integration

**Files:**
- Modify: `harness_manager/doctor.py`
- Modify: `harness_manager/status.py`
- Modify: `harness_manager/dashboard_tui.py`
- Modify: `harness_manager/mission_control_collectors.py`
- Modify: `.agent/tools/data_layer_export.py`
- Modify: `tests/test_loop_integrations.py`
- Modify: `tests/test_dashboard_tui.py`
- Modify: `tests/test_mission_control.py`
- Modify: `tests/test_data_layer_export.py`

- [ ] **Step 1: Write failing read-only integration tests**

Create a target with one valid loop and privacy-safe events. Assert:

- doctor reports valid/invalid loop names without writing files;
- status reports loop count, global pause, and latest terminal state;
- dashboard plain output has a `loops` section;
- `/api/runs` includes loop run objects with no task, prompt, command arguments,
  stdout, or stderr;
- data-layer export classifies loop lifecycle events and preserves malformed-line
  quality counts.

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_loop_integrations.py tests/test_dashboard_tui.py tests/test_mission_control.py tests/test_data_layer_export.py -q`

- [ ] **Step 3: Add one shared read-only collector**

Expose `collect_summary(target_root)` from `harness_manager.loops.storage` or a
small read-only helper in `commands.py`. Return only:

```python
{
    "configured": int,
    "valid": int,
    "invalid": list[str],
    "paused": bool,
    "latest": {"run_id": str, "loop": str, "status": str, "reason": str | None} | None,
}
```

Integrations consume this function; they do not duplicate checkpoint parsing or
call mutating loop commands. Data-layer reads `events.jsonl` through its
existing tolerant JSONL reader and hashes run ids in exported public artifacts.

- [ ] **Step 4: Run green and commit**

Run: `python3 -m pytest tests/test_loop_integrations.py tests/test_dashboard_tui.py tests/test_mission_control.py tests/test_data_layer_export.py -q`

```bash
git add harness_manager/doctor.py harness_manager/status.py harness_manager/dashboard_tui.py harness_manager/mission_control_collectors.py .agent/tools/data_layer_export.py tests/test_loop_integrations.py tests/test_dashboard_tui.py tests/test_mission_control.py tests/test_data_layer_export.py
git commit -m "feat(loops): surface local loop health and events"
```

## Task 9: Isolate the legacy Claude hook validation suite

**Files:**
- Modify: `tests/test_claude_code_hook.py`

- [ ] **Step 1: Write a failing isolation assertion**

Add this pytest-only test before changing the fixture setup:

```python
def test_pytest_uses_isolated_agent_tree():
    repository_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    actual = os.path.realpath(PROJECT_ROOT)
    repository_root = os.path.realpath(repository_root)
    expected = os.path.realpath(tempfile.gettempdir())
    assert actual != repository_root
    assert os.path.commonpath([actual, expected]) == expected
```

- [ ] **Step 2: Run only the isolation assertion red**

Run: `python3 -m pytest tests/test_claude_code_hook.py::test_pytest_uses_isolated_agent_tree -q`

Expected: FAIL because `PROJECT_ROOT` is the repository worktree. This focused
test does not invoke hooks and therefore does not pollute memory while proving
the missing isolation.

- [ ] **Step 3: Bind pytest execution to a session-scoped temporary `.agent`**

When pytest is available, add a session-scoped autouse fixture that:

```python
@pytest.fixture(scope="session", autouse=True)
def isolated_agent_tree(tmp_path_factory):
    global PROJECT_ROOT, AGENT_DIR, HOOK_SCRIPT, EPISODIC
    source_root = PROJECT_ROOT
    isolated_root = str(tmp_path_factory.mktemp("claude-hook-project"))
    shutil.copytree(os.path.join(source_root, ".agent"), os.path.join(isolated_root, ".agent"))
    PROJECT_ROOT = isolated_root
    AGENT_DIR = os.path.join(PROJECT_ROOT, ".agent")
    HOOK_SCRIPT = os.path.join(AGENT_DIR, "harness", "hooks", "claude_code_post_tool.py")
    EPISODIC = os.path.join(AGENT_DIR, "memory", "episodic", "AGENT_LEARNINGS.jsonl")
    for rel in ("harness", "memory", "tools"):
        sys.path.insert(0, os.path.join(AGENT_DIR, rel))
    yield
```

Keep standalone `python3 tests/test_claude_code_hook.py` behavior unchanged;
only pytest collection uses the fixture. The session copy intentionally lets
hook-write and dream-cycle tests share their generated temporary evidence.

- [ ] **Step 4: Prove the full legacy test file is green and clean**

Run:

```bash
git status --porcelain > /tmp/agentic-stack-status-before
python3 -m pytest tests/test_claude_code_hook.py -q
git status --porcelain > /tmp/agentic-stack-status-after
diff -u /tmp/agentic-stack-status-before /tmp/agentic-stack-status-after
```

Expected: all hook tests pass and the status snapshots are identical. Confirm
there are no new `.agent/memory/candidates/*.json`, `REVIEW_QUEUE.md`, or
episodic-memory diffs.

- [ ] **Step 5: Commit**

```bash
git add tests/test_claude_code_hook.py
git commit -m "test: isolate hook memory fixtures"
```

## Task 10: Release documentation and v0.19.0 preparation

**Files:**
- Modify: `harness_manager/__init__.py`
- Modify: `README.md`
- Modify: `docs/getting-started.md`
- Modify: `CHANGELOG.md`
- Create: `docs/releases/v0.19.0.md`
- Modify: `tests/test_onboard_ui.py`

- [ ] **Step 1: Write failing version and release-documentation tests**

Assert `__version__ == "0.19.0"`, README/getting-started show init/run/status and
the sandbox caveat, and changelog includes Added/Safety/Migration sections.
Do not change or assert the Homebrew formula in this task; it must remain a
working v0.18.0 formula until the v0.19.0 tag tarball exists.

- [ ] **Step 2: Run tests red**

Run: `python3 -m pytest tests/test_onboard_ui.py tests/test_loop_integrations.py -q`

- [ ] **Step 3: Update docs and release metadata**

Document:

- the maker → deterministic verifier → independent checker lifecycle;
- L1/L2/L3 and why bundled action loops use worktrees;
- exact CLI examples and scheduler boundary;
- local-only event privacy model;
- supervisor-not-sandbox caveat;
- safe upgrade steps for existing projects;
- attribution to the loop-engineering reference without implying code was copied.

Write `docs/releases/v0.19.0.md` as the GitHub release body, including the
feature summary, CLI examples, safety boundaries, upgrade command, full-suite
verification statement, and attribution. Exact counts are added from fresh
Task 11 output in a pre-tag commit.

Set Python package version to `0.19.0`. Leave `Formula/agentic-stack.rb`
byte-for-byte unchanged so master never points a v0.18.0 URL at v0.19.0-only
paths or smoke tests.

- [ ] **Step 4: Run focused tests green and commit**

Run: `python3 -m pytest tests/test_onboard_ui.py tests/test_loop_integrations.py -q`

```bash
git add harness_manager/__init__.py README.md docs/getting-started.md CHANGELOG.md docs/releases/v0.19.0.md tests/test_onboard_ui.py tests/test_loop_integrations.py
git commit -m "chore: prepare v0.19.0 release"
```

## Task 11: Full verification, review, integration, tag, release, and formula hash

**Files:**
- Modify after tag: `Formula/agentic-stack.rb`
- Modify after tag: `CHANGELOG.md`
- Modify after tag: `tests/test_transfer_scripts.py`

- [ ] **Step 1: Verify the bounded test-pollution fix before the full suite**

Confirm Task 9's `tests/test_claude_code_hook.py` session fixture is present.
Capture `git status --porcelain` before and after the full suite and require an
identical diff. No other test file is authorized for pollution-related edits in
this task; if a new writer is discovered, stop and add a separately reviewed,
exact file owner instead of broadening this release step ad hoc.

- [ ] **Step 2: Run complete local verification**

Run all commands fresh:

```bash
python3 -m pytest
python3 -m harness_manager.cli loop validate --target . --json
python3 -m harness_manager.cli loop audit --target . --json
./install.sh loop validate --target .
git diff --check origin/master...HEAD
git status --short
```

Expected: all tests pass; both dispatch paths validate; audit JSON is valid and
explains any lack of real production run evidence without hiding it; diff check
is clean; no generated memory/runtime files remain.

- [ ] **Step 3: Run a real local fake-harness smoke loop**

In a temporary Git repository, install agentic-stack, configure the fake maker,
verifier, and checker used by integration tests, run an L2 loop to two-attempt
completion, inspect status JSON, then run cleanup. Save command outputs for the
release evidence and confirm the active checkout was untouched.

- [ ] **Step 4: Commit exact release evidence before review and tagging**

Replace the general verification statement in `docs/releases/v0.19.0.md` with
the exact fresh test count and smoke-command outcomes from Steps 2 and 3. Commit
only that evidence update as `docs: finalize v0.19.0 release evidence`. This
commit becomes part of `release_sha`; no release-note edit occurs after tagging.

- [ ] **Step 5: Perform independent reviews**

Use the requesting-code-review workflow. Review the full diff for spec
compliance first, then code quality/security. Resolve every material finding and
re-run the full verification set after changes.

- [ ] **Step 6: Refresh and integrate current remote master**

Use the known feature and primary worktrees explicitly:

```bash
FEATURE=/Users/example/Documents/Codex/2026-07-18/codejunkie99-agentic-stack-https-github-com/work/agentic-stack-v0.19.0
PRIMARY=/Users/example/Documents/Codex/2026-07-18/codejunkie99-agentic-stack-https-github-com/repo
git -C "$FEATURE" fetch origin --prune --tags
remote_sha=$(git -C "$FEATURE" rev-parse origin/master)
base_sha=$(git -C "$FEATURE" merge-base HEAD origin/master)
if [ "$base_sha" != "$remote_sha" ]; then
  git -C "$FEATURE" rebase origin/master
fi
cd "$FEATURE"
python3 -m pytest
git -C "$PRIMARY" checkout master
git -C "$PRIMARY" merge --ff-only codex/agentic-loops-meta-harness
release_sha=$(git -C "$PRIMARY" rev-parse HEAD)
test "$release_sha" = "$(git -C "$FEATURE" rev-parse HEAD)"
```

Run the full verification set again from `PRIMARY` after the fast-forward.
Never force-push.

- [ ] **Step 7: Push feature integration and create annotated tag**

Push master first. Create and push the tag only after the remote master SHA is
verified. If branch protection rejects the direct fast-forward, do not create a
tag: push the rebased tip to a fresh uniquely named branch such as
`codex/agentic-loops-meta-harness-release-YYYYMMDDHHMMSS` (never reuse or
force-push an existing remote ref), create the required PR from that branch,
merge it with a merge commit (not squash/rebase), pull that merge into local master with
`--ff-only`, rerun verification, and set `release_sha` to the fetched
`origin/master` commit.

```bash
git -C "$PRIMARY" push origin "$release_sha:refs/heads/master"
remote_master=$(git -C "$PRIMARY" ls-remote origin refs/heads/master | awk '{print $1}')
test "$remote_master" = "$release_sha"
git -C "$PRIMARY" tag -a v0.19.0 "$release_sha" -m "agentic-stack v0.19.0"
git -C "$PRIMARY" push origin refs/tags/v0.19.0
remote_tag=$(git -C "$PRIMARY" ls-remote origin 'refs/tags/v0.19.0^{}' | awk '{print $1}')
test "$remote_tag" = "$release_sha"
```

Do not create the GitHub release unless both assertions pass.

- [ ] **Step 8: Create GitHub release**

Use the release notes committed in the tagged tree:

```bash
gh release create v0.19.0 --verify-tag --title "agentic-stack v0.19.0" --notes-file docs/releases/v0.19.0.md
```

Release notes must describe the loop engine, meta harness, isolation, safety
boundaries, upgrade path, tests, and loop-engineering inspiration.

- [ ] **Step 9: Compute tag tarball hash and update formula**

Download or stream the immutable GitHub tag tarball and compute SHA-256. In one
post-tag change, update `Formula/agentic-stack.rb` URL/hash to v0.19.0, add the
`agentic-stack loop validate` formula smoke test, update
`tests/test_transfer_scripts.py` to assert the v0.19.0 formula behavior, and add
the verified hash to `CHANGELOG.md`. Run:

```bash
python3 -m pytest tests/test_transfer_scripts.py -q
brew audit --strict Formula/agentic-stack.rb
brew test --formula Formula/agentic-stack.rb
```

When Homebrew is unavailable, record that exact limitation and run the pytest
formula assertions plus `ruby -c Formula/agentic-stack.rb`; do not claim a brew
test passed. Commit all post-tag formula changes together as
`chore(formula): bump to v0.19.0`, verify `origin/master` still equals
`release_sha`, fast-forward local master with the formula commit, and push that
new master SHA without rewriting `v0.19.0`. If branch protection rejects this
direct push, push the single formula commit to a fresh uniquely named branch,
open a PR, merge it with a merge commit, and fetch `origin/master`. Verify the
resulting remote master contains the formula change, verify `release_sha` is an
ancestor of remote master, and verify the peeled `v0.19.0` tag still equals
`release_sha`; never move or recreate the tag. The formula change remains one
atomic commit in either path. The formula is therefore installable at every
pushed master commit: v0.18.0 before the tag, v0.19.0 after the formula bump.

- [ ] **Step 10: Final completion audit**

For every acceptance criterion in the design spec, record authoritative
evidence: file, test, command output, remote SHA, release URL, and formula hash.
Only then mark the goal complete.

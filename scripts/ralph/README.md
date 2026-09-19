# Ralph loop

An autonomous agent loop after [snarktank/ralph](https://github.com/snarktank/ralph):
each iteration spawns a fresh agent with clean context that implements exactly one
PRD story, verifies it against the project's quality gates, commits, and records
learnings for the next iteration. Memory between iterations is `git log`,
`prd.json`, and `progress.txt`.

These files are **managed by project-template** (`~/dev-repo/project-template`).
Edit them there and run `python3 sync.py push-ralph --yes`; local edits here are
overwritten by the next sync. Per-run state (`prd.json`, `progress.txt`,
`archive/`, `logs/`, `.last-branch`) is yours and is never touched by sync.

## Run

```bash
cd scripts/ralph
cp prd.json.example prd.json     # first run only: write your stories
./ralph.sh                       # claude, 10 iterations
./ralph.sh --tool claude 25      # bigger budget
```

The loop stops early when an iteration replies `<promise>COMPLETE</promise>`
(every story has `"passes": true`), otherwise after the iteration budget.

## Permissions

By default the claude tool runs headless with `--permission-mode acceptEdits`:
file edits are auto-approved, everything else still honors your configured
permission rules — in headless mode a gated call is denied, and the iteration
records what it could not do. Two ways to widen this deliberately:

- Scoped (preferred): allow the project's gate commands in
  `.claude/settings.json` permissions (build, test, lint, git commit), so the
  default mode can run them unattended.
- Fully autonomous (upstream Ralph behaviour): set
  `RALPH_CLAUDE_FLAGS="--dangerously-skip-permissions"` for the run. That
  removes every safety prompt for anything the agent decides to execute —
  only do this in a repository and environment where you accept that.

`RALPH_CLAUDE_FLAGS` replaces the default flags entirely, so it can also carry
`--model`, `--allowedTools`, etc.

Two gotchas proven in testing:

- **Headless runs may not load the project's `.claude/settings.json`
  allowlist** (untrusted directory, or ralph driven from automation/another
  agent). The iteration then can't run your gates and — correctly — refuses
  to mark the story passed. Fix by passing the allowlist explicitly,
  comma-separated with no spaces:
  `RALPH_CLAUDE_FLAGS='--permission-mode acceptEdits --allowedTools Bash(python3:*),Bash(git:*)' ./ralph.sh`
- **Resuming over a story's own uncommitted work** trips the dirty-tree
  guard (exit 2). That guard protects against dragging unrelated changes
  across branches; when the dirt is the in-flight story on the PRD branch,
  resume with `RALPH_ALLOW_DIRTY=1`.

## Files

| File | Role | Owner |
| --- | --- | --- |
| `ralph.sh` | The loop | template (synced) |
| `PROMPT.md` | Per-iteration instructions | template (synced) |
| `prd.json.example` | PRD shape reference | template (synced) |
| `prd.json` | This run's stories + branch | you / the agent |
| `progress.txt` | Append-only learnings + Codebase Patterns | the agent |
| `archive/` | Previous runs (auto-archived on branch change) | ralph.sh |
| `logs/` | Raw per-iteration output | ralph.sh |

## Relation to `.agent/loops`

agentic-stack ≥ 0.19 ships bounded loop contracts under `.agent/loops`
(ci-sweeper, pr-babysitter, …) with a maker → verifier → checker lifecycle and
hard budgets. The split when both are present: **Ralph owns PRD-driven feature
delivery** — many stories, one branch, open-ended iteration count; **`.agent/loops`
owns narrow recurring maintenance** — one bounded objective per run, scheduler
friendly. Don't wrap one in the other; pick the contract that matches the work.

## Writing a PRD

Keep stories one-iteration small, with observable acceptance criteria. The
agent marks `"passes": true` only after the project's gates are green — a
story too big to finish in one iteration should be split. `branchName` is
where all commits land; changing it archives the previous run.

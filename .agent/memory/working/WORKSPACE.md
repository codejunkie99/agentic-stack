# Workspace (live task state)

> Live "where are we right now" file. Updated when we move between steps,
> hit a blocker, or change direction. For the durable history of *why* we
> did things, see `.agent/memory/semantic/DECISIONS.md`.

## Current step

**Step 8.2.5 — sync fork to upstream `codejunkie99/agentic-stack` (v0.8.0 → v0.11.2)**

Inserted before Step 8.3 (real-case dry-run) because dry-running on a
6-version-stale base is not meaningful. Identified 2026-04-27 when user
asked about the previously-discussed weekly upstream sync — discovered
the cadence was scoped in `DOMAIN_KNOWLEDGE.md` (loop #6) but never
operationalized. Now operationalized: weekly cron + auto-memory entry.

## Why now

- 59 commits behind upstream, last common ancestor `a397568` (v0.8.0)
- 6 new tags upstream: v0.9.0, v0.9.1, v0.10.0, v0.11.0, v0.11.1, v0.11.2
- Major upstream additions worth absorbing: `harness_manager/` Python
  package (replaces bash install), data-layer monitor + dashboard,
  data-flywheel trainer, DESIGN.md skill, codex adapter, pi rewrite,
  Windows path-traversal security fix, Python 3.9 compat
- Step 8.3 dry-run + any further BCG adapter work should land on a
  current base, not a stale fork

## Stage plan (draft — confirm before executing)

- **8.2.5.1** — review-only: per-tag walkthrough (v0.9.0 → v0.11.2),
  classify each upstream change as (a) take as-is, (b) take with
  adaptation, (c) skip / our-version-wins. No code changes; produces a
  classification doc.
- **8.2.5.2** — merge mechanics decision: rebase 8.x work onto upstream,
  vs. merge upstream into master, vs. cherry-pick selected upstream
  commits. Likely **merge** given the divergence size and the fact that
  our 8.x history is a series of dated decisions we don't want to rewrite.
- **8.2.5.3** — execute the merge. Highest-risk file: `install.sh` —
  upstream gutted it to a thin Python dispatcher (`harness_manager/`),
  we extended it for BCG-conditional propagation in 8.2.1 + 8.2.3
  agent-memory copy-if-missing loop. Resolution: port our BCG block into
  `harness_manager/install.py` rather than keeping the bash logic.
- **8.2.5.4** — smoke-test both adapter states (disabled/enabled) on
  fresh installs into `/tmp/claude/825-{disabled,enabled}/`, same
  pattern as 8.2.1 / 8.2.4.
- **8.2.5.5** — log + DECISIONS.md entry + episodic learning.

## Conflict surface (verified via `git merge-tree` dry-run, 2026-04-27)

- **92 files we added** (all of `adapters/bcg/`, `.agent/context/`,
  `.agent/personas/`, 13 knowledge-work skills, BCG agent-memory
  templates, etc.) — kept clean, no upstream collision.
- **58 files upstream added** — gained clean (entire `harness_manager/`
  Python package, `data-layer/` + `data-flywheel/` + `design-md`
  skills, codex adapter, pi rewrite, schemas, examples, docs, hooks).
- **0 files deleted upstream that we still have** — no silent loss risk.

### Real conflicts (4, manual resolution)

| File | Type | Resolution strategy |
|---|---|---|
| `install.sh` | **HARD** — base 114 → ours 175 (+61 BCG block) ← → upstream 38 (-76, stripped to Python dispatcher) | Port BCG block into `harness_manager/install.py`. Real coding task, not just text resolution. |
| `.agent/skills/_index.md` | Soft — disjoint skill lists | Mechanical merge. Ours: 13 knowledge-work + SDLC. Theirs: data-flywheel, data-layer, design-md. No name overlap. |
| `.agent/skills/_manifest.jsonl` | Soft — 20 ours + 8 theirs, no overlap | Mechanical merge. |
| `.agent/memory/semantic/DECISIONS.md` | Soft | Ours-wins (file is our project history). |

### Auto-mergeable (2)

- `.agent/AGENTS.md`, `.gitignore` — git resolves cleanly.

### Lower-risk spot-checks during 8.2.5.3

- `adapters/pi/{AGENTS.md, README.md, adapter.json, memory-hook.ts}` —
  we don't customize pi, take upstream-wins (their #24 rewrite fixes
  formula crash + decay tz bug).
- `adapters/claude-code/{adapter.json, settings.json}` — small upstream
  schema addition. Untouched by us. Take upstream-wins.
- Hook scripts `auto_dream.py`, `decay.py`, `archive.py`, `promote.py`,
  `render_lessons.py`, `review_state.py`, `salience.py`,
  `on_failure.py`, `post_execution.py` — upstream changed, we didn't.
  Clean upstream-wins. Verify memory layer end-to-end after.

## Resolved decisions

- ✅ **Merge, not rebase** — preserves dated 8.x decision history, and
  conflict surface is identical either path.
- ✅ **Take `harness_manager/` Python package wholesale** + port our BCG
  install.sh logic into `harness_manager/install.py`.
- ✅ **Take `data-layer` and `data-flywheel` skills as-is** — additive,
  no name collision, observability surface BCG can opt into later.
- ✅ **Net assessment**: merge is safe and the conflict surface is
  small and bounded. Single load-bearing decision is install.sh →
  harness_manager port.

## Next step

Execute the plan task-by-task:
[`docs/superpowers/plans/2026-04-27-step-8-2-5-upstream-sync.md`](../../../docs/superpowers/plans/2026-04-27-step-8-2-5-upstream-sync.md)

19 tasks across 6 stages (pre-flight → classification → merge →
BCG port → smoke → log+push). Choose execution mode at kickoff:
subagent-driven (recommended — fresh subagent per task with review
between) or inline (executing-plans skill, batched with checkpoints).

## Recurring cadence

- Weekly upstream sync check: every Monday morning. Mechanism:
  `CronCreate` (durable, 7-day TTL, ID `ba87d58c`, fires Mon 9:13 local)
  re-armed each fire, plus auto-memory entry
  `upstream_sync_cadence.md` so the cadence survives session restarts
  beyond the cron's lifetime.

## Recent upstream-sync checks

- 2026-04-27 — base at v0.8.0 (`a397568`); 59 commits behind across 6
  tags through v0.11.2; merge work scoped as Step 8.2.5 (this step).

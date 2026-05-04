# ADR — Transfer Bundle Augment (v1)

**Date:** 2026-05-04
**Status:** Accepted
**Deciders:** architect (this doc), operator (sign-off via OQ-1/2/3 resolution)
**PRD:** `/Users/talwarpulkit/code/sdlc-test-pilot/docs/prd/2026-05-04-transfer-bundle-augment.md`
**Build repo:** `agent-stack` fork, branch `feature/transfer-bundle-augment` (to be created)
**Spec-review score:** 9.2/10 — APPROVED
**Tech-spike anchor:** `output/tech-spikes/2026-05-04-transfer-bundle-vs-graduate/RECOMMENDATION.md`

---

## 1. Context

The fork has four asymmetric state-mutation tools (`install.sh`, `sync-target.sh`, `merge_target_settings.py`, `harness-graduate.py`). None of them snapshot a running install's transferable state and re-land it on another. The PRD documents three pain scenarios (second laptop, teammate onboarding, mid-engagement re-sync) that have all become live with the next consulting engagement firing in 2–3 weeks.

Upstream `codejunkie99/agentic-stack` v0.13.0 ships a `transfer_bundle.py` + `transfer_plan.py` + `import-transfer.sh` family that solves exactly this problem, but uses a different state model (`targets × scopes`) than the fork (six state classes). The PRD scopes a v1 that vendors the upstream modules and adapts them to the fork's model. v1 does NOT vendor the upstream `transfer_tui.py` (deferred to v2). v1 does NOT modify `harness-graduate.py` or its five quality gates.

Operator has resolved the three blocking open questions:
- **OQ-1:** Upstream transfer modules are stdlib-only on `upstream/master`. No `textual` / `prompt_toolkit` runtime dependency. Vendor path safe.
- **OQ-2:** Conflict resolution = flag `CONFLICT`, skip unless `--force`. No silent merge, no per-entry prompt.
- **OQ-3:** `client` class requires explicit `--clients <slug>[,<slug>]`. No slug = no client content shipped. Prevents leaking prior engagements into a teammate handoff.

---

## 2. Decision

**Adopt the upstream transfer-bundle pattern as a vendored fork-side feature, with a fork-specific `STATE_CLASS_MAP` adapter layer that translates the PRD's six state classes into bundle entries, and a `--clients <slug>` allow-list gate on the `client` class.**

Three new tools land in `.agent/tools/`:

1. `transfer_bundle.py` — produce archive from a source install.
2. `transfer_plan.py` — compute and print plan (NEW / OVERWRITE / SKIP / CONFLICT) against a destination.
3. `import-transfer.sh` — wrap plan + confirmation gate + apply.

A single shared module `.agent/tools/_transfer_state_classes.py` defines the canonical state-class → path mapping consumed by all three tools. This is the only place where the fork's six-class model is encoded.

**Why this and not a direct port of upstream's `targets × scopes` model:** the fork has already invested in the six-class model across `install.sh`, `harness-graduate.py`, `sync-target.sh`, and the `.agent/memory/` directory layout. Reframing those tools to upstream's `scopes` would be a multi-week refactor outside the PRD's 4-week budget and would orphan the existing graduate/sync semantics. The adapter layer (state-class map) is ~50 LOC and isolates fork divergence to one file.

---

## 3. Component Diagram with Typed Interfaces

```
                          ┌────────────────────────────────────┐
                          │  _transfer_state_classes.py        │
                          │  (canonical state-class registry)  │
                          │                                    │
                          │  STATE_CLASSES: dict[str, ClassSpec]│
                          └────────────────────────────────────┘
                                  ▲           ▲           ▲
                                  │           │           │
                                  │           │           │
        ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────────┐
        │ transfer_bundle  │   │ transfer_plan    │   │ import-transfer.sh   │
        │ .py              │   │ .py              │   │ (bash wrapper)       │
        │                  │   │                  │   │                      │
        │ build_bundle()   │   │ compute_plan()   │   │ calls transfer_plan  │
        │ → BundleResult   │   │ → TransferPlan   │   │ → confirm prompt     │
        │                  │   │                  │   │ → apply_plan()       │
        └──────────────────┘   └──────────────────┘   └──────────────────────┘
                                          │                       │
                                          └───────┬───────────────┘
                                                  ▼
                                       ┌────────────────────┐
                                       │ apply_plan()       │
                                       │ (in transfer_plan) │
                                       │ → ApplyResult      │
                                       └────────────────────┘
```

### Typed contracts

```python
# _transfer_state_classes.py

@dataclass(frozen=True)
class ClassSpec:
    name: str                          # one of: semantic|personal|working|client|agent_memory|machine_settings
    src_path: str                      # relative to install root, e.g. ".agent/memory/semantic"
    requires_subselector: bool = False # True for `client` (needs --clients slug)
    active_engagement_check: bool = False  # True for `working` (triggers WORKSPACE.md gate)

STATE_CLASSES: dict[str, ClassSpec] = {
    "semantic":         ClassSpec("semantic", ".agent/memory/semantic"),
    "personal":         ClassSpec("personal", ".agent/memory/personal"),
    "working":          ClassSpec("working", ".agent/memory/working", active_engagement_check=True),
    "client":           ClassSpec("client", ".agent/memory/client", requires_subselector=True),
    "agent_memory":     ClassSpec("agent_memory", ".claude/agent-memory"),
    "machine_settings": ClassSpec("machine_settings", ".agent/config.json"),
}
```

```python
# transfer_bundle.py

@dataclass(frozen=True)
class BundleManifest:
    schema_version: int                # bumped on incompatible manifest changes; v1 = 1
    source_hostname: str
    created_at_utc: str                # ISO 8601
    agent_stack_version: str           # from .agent/VERSION or git rev-parse
    classes: list[str]                 # state-class labels included
    client_slugs: list[str] | None     # None unless `client` class included
    file_count: int
    total_bytes: int

@dataclass(frozen=True)
class BundleResult:
    out_path: Path                     # the .tar.gz produced
    manifest: BundleManifest

def build_bundle(
    source_root: Path,
    classes: list[str],                # validated against STATE_CLASSES keys
    client_slugs: list[str] | None,    # required iff "client" in classes (per OQ-3)
    out_path: Path,
) -> BundleResult: ...
```

```python
# transfer_plan.py

class EntryKind(Enum):
    NEW = "NEW"                # path absent on dest
    OVERWRITE = "OVERWRITE"    # dest older than bundle (mtime + sha256 hash compared)
    SKIP = "SKIP"              # dest identical to bundle (sha256 match)
    CONFLICT = "CONFLICT"      # dest newer than bundle OR dest mtime within mtime-skew window AND content differs

@dataclass(frozen=True)
class PlanEntry:
    relpath: str               # path relative to install root
    kind: EntryKind
    src_sha256: str
    dest_sha256: str | None    # None if dest absent
    src_mtime: float
    dest_mtime: float | None

@dataclass(frozen=True)
class TransferPlan:
    bundle_path: Path
    dest_root: Path
    entries: list[PlanEntry]
    active_engagement_detected: bool   # True iff WORKSPACE.md non-empty + has open task block on dest
    has_conflicts: bool                # any entry.kind == CONFLICT
    manifest: BundleManifest

def compute_plan(bundle_path: Path, dest_root: Path) -> TransferPlan: ...

@dataclass(frozen=True)
class ApplyResult:
    written: list[str]
    skipped: list[str]
    conflicts_skipped: list[str]       # CONFLICT entries skipped because --force not set

def apply_plan(plan: TransferPlan, force: bool = False) -> ApplyResult: ...
```

```bash
# import-transfer.sh

# Inputs: --bundle <path> --dest <dir> [--dry-run] [--force] [--yes]
# Behavior:
#   1. Calls: python3 .agent/tools/transfer_plan.py --bundle <p> --dest <d> --emit-json
#   2. Prints human plan to stdout.
#   3. If --dry-run: exit 0 if no conflicts, exit 2 if conflicts present.
#   4. If active_engagement_detected: default prompt = N; require typed `force` or explicit `y`.
#      Else: default prompt = N; require `y`.
#   5. If --yes: auto-confirms (CI/test fixture path). Still rejects CONFLICT entries unless --force.
#   6. On confirm: invokes transfer_plan.apply_plan via `python3 -m`, exits with apply rc.
```

### Active-engagement detection

`is_active_engagement(dest_root: Path) -> bool` lives in `_transfer_state_classes.py`. Returns True if `<dest_root>/.agent/memory/working/WORKSPACE.md` exists, is non-empty, AND contains a non-empty section under any heading matching `^## (Current step|Active|In progress)`. Heuristic; overrideable by `--no-engagement-check`.

### Non-overlap with existing fork tooling

| Existing tool | Direction | Concern | Overlap with this ADR |
|---|---|---|---|
| `install.sh` | upstream → fresh target | First-time install | None. Bundle assumes target already installed. |
| `sync-target.sh` | fork → existing target | Harness primitive updates (skills, hooks, protocols) | Disjoint surface. Sync touches harness code. Bundle touches state. |
| `merge_target_settings.py` | fork → existing target | `.claude/settings.json` smart-merge | Disjoint. Settings file is not in any bundle state class. |
| `harness-graduate.py` | target → fork | Lesson promotion with five quality gates | Explicitly fenced. Bundle ships state, never promotes lessons. |

---

## 4. Data Flow with Failure Branches

### Bundle creation (S1 + S3)

```
operator → transfer_bundle.py --out X --classes Y[,Z…] [--clients slug[,…]]
   │
   ├─[validate classes against STATE_CLASSES keys]
   │     └─ unknown class → exit 2, print valid set, NO output
   │
   ├─[validate `client` requires --clients per OQ-3]
   │     └─ client in classes AND no slug → exit 2, error message
   │     └─ slug given AND client/<slug> dir absent → exit 2
   │
   ├─[walk source paths, hash files (sha256), build manifest]
   │     └─ permission denied → exit 3, partial archive removed
   │     └─ symlink loop → exit 3
   │
   ├─[write tar.gz atomically: out_path.tmp → fsync → rename]
   │     └─ disk full → exit 4, .tmp removed
   │
   └─→ BundleResult printed to stdout (manifest summary), exit 0
```

### Plan + apply (S2 + S4)

```
operator → import-transfer.sh --bundle X --dest D [flags]
   │
   ├─→ transfer_plan.py compute_plan(X, D)
   │     ├─[open archive] → bundle unreadable → exit 5
   │     ├─[validate manifest schema_version] → mismatch → exit 6
   │     ├─[verify dest is install] (.agent/ dir present) → no → exit 7
   │     ├─[for each archive entry: hash + stat dest path]
   │     │     ├─ dest absent → NEW
   │     │     ├─ dest hash == src hash → SKIP
   │     │     ├─ dest mtime < src mtime AND hashes differ → OVERWRITE
   │     │     └─ dest mtime ≥ src mtime AND hashes differ → CONFLICT
   │     ├─[active_engagement_check on dest WORKSPACE.md]
   │     └─→ TransferPlan
   │
   ├─[print plan to stdout — grouped by kind, totals at end]
   │     └─ if --dry-run: exit 0 if no conflicts else exit 2
   │
   ├─[active engagement gate]
   │     └─ active + not --force AND not typed `force` → exit 8 (refused)
   │
   ├─[y/N prompt; default N; --yes auto-confirms]
   │     └─ N or empty → exit 0, no writes
   │
   └─→ apply_plan(plan, force)
         ├─[for each entry NEW or OVERWRITE: extract → temp → fsync → rename]
         │     ├─ failure mid-stream: leave already-written entries in place,
         │     │  emit failed-list to stderr, exit 9 (partial). Operator
         │     │  reruns; sha256 dedup converts re-applied entries to SKIP.
         │     └─ CONFLICT entries: written iff force=True, else added to
         │        ApplyResult.conflicts_skipped
         └─→ ApplyResult printed, exit 0
```

---

## 5. Edge-Case Matrix

| # | Scenario | Expected behavior | Test seam |
|---|---|---|---|
| E1 | `--classes client` without `--clients` slug | Exit 2, error names OQ-3 rule, no archive written | `test_bundle_client_requires_slug` |
| E2 | Destination has newer `WORKSPACE.md` than bundle | Plan tags entry CONFLICT, `[ACTIVE ENGAGEMENT DETECTED]` header printed, default prompt N | `test_plan_conflict_active_engagement` |
| E3 | Bundle includes state class whose path is absent on dest | Entry tagged NEW, parent dirs created during apply | `test_apply_creates_missing_dirs` |
| E4 | Apply interrupted mid-stream (SIGTERM) | Atomic-rename guarantee: per-file all-or-nothing; manifest of written files emitted to stderr; rerun is safe (SKIP via hash) | `test_apply_partial_resume` |
| E5 | Bundle from different agent-stack version (manifest schema mismatch) | Exit 6 before any plan computation; message names expected schema_version | `test_plan_rejects_schema_mismatch` |
| E6 | Symlink in source state class | Followed if intra-install; refused (exit 3) if escapes install root | `test_bundle_rejects_external_symlink` |
| E7 | Source and dest sha256 identical | Entry tagged SKIP regardless of mtime; not written; not counted as conflict | `test_plan_identical_files_skip` |
| E8 | `client/<slugA>/` and `client/<slugB>/` both present, operator passes `--clients slugA` | Bundle contains only `client/slugA/` tree; manifest.client_slugs = ["slugA"] | `test_bundle_client_slug_filter` |
| E9 | `--dry-run` with all NEW entries | Exit 0, no writes, plan printed | `test_dry_run_clean_exit_zero` |
| E10 | `--dry-run` with any CONFLICT entry | Exit 2, no writes, plan printed | `test_dry_run_conflict_exit_two` |
| E11 | Two CONFLICT entries, `--force` set, `y` confirmed | Both written; ApplyResult.conflicts_skipped empty | `test_apply_force_overwrites_conflicts` |

≥5 rows requirement met (11 rows).

---

## 6. Test-Seam List

Engineer hooks tests at these named entry points. Each seam is a function or process boundary that admits a fixture-driven test without mocking transport.

1. **`build_bundle()`** — pure function on filesystem inputs; fixture = `tests/fixtures/install_a/` with seeded six-class state. Asserts on `BundleResult.manifest` and tar.gz contents (extract + diff).
2. **`compute_plan()`** — pure function; fixtures = `install_a/` (source bundle) + `install_b/` (dest tree). Asserts on `TransferPlan.entries[*].kind` distribution.
3. **`apply_plan()`** — fixture = pre-computed plan + dest tree + `tmp_path`; asserts files appear and hashes match.
4. **`is_active_engagement()`** — table-driven test over `WORKSPACE.md` shapes (empty / heading-only / open-task / closed).
5. **`STATE_CLASSES` registry** — schema test: every entry's `src_path` exists in fork's canonical install layout (caught at lint time).
6. **`import-transfer.sh`** — bats-style or `subprocess.run` integration test; fixture installs + bundle artifact; asserts on exit codes for the prompt matrix (default-N, `--yes`, `--dry-run`, `--force`).
7. **Manifest schema validator** — separate `validate_manifest(dict) -> None` raises on missing/extra fields; allows independent schema-version migration tests.
8. **End-to-end timed test (S5)** — pytest fixture that runs install → bundle → plan → apply on a clean target dir; asserts wall-clock < 5 min for teammate scenario, < 10 min for second-laptop scenario.

---

## 7. Assumption Ledger

Each assumption ships with a falsification test. If the test fails post-build, the assumption must be revisited before v1 ships.

1. **A1 — Upstream `transfer_bundle.py` and `transfer_plan.py` on `upstream/master` are stdlib-only.**
   - **Falsification test:** `pip install --no-deps -e .` against a stripped fork checkout that contains only stdlib + the two vendored modules. If imports succeed and the smoke test (build empty bundle, plan against same install) exits 0, A1 holds. If `ModuleNotFoundError` for `textual` / `prompt_toolkit` / `pydantic` / etc., A1 is broken; fork must vendor a stripped copy.
   - **Operator confirmation:** OQ-1 resolution.

2. **A2 — sha256 + mtime is sufficient to disambiguate NEW / OVERWRITE / SKIP / CONFLICT without a content-merge step.**
   - **Falsification test:** seed a target with a file whose mtime is older than bundle but whose content is downstream-edited (simulate via `touch -d`). Run plan. Assert kind=OVERWRITE. Then seed dest mtime newer than bundle, content differs. Assert kind=CONFLICT. If either misclassifies, A2 is broken.
   - **Risk if false:** silent overwrite of newer dest content. Mitigation: refuse to lower mtime granularity below 1s; treat sub-second skew as CONFLICT.

3. **A3 — The PRD's six state classes capture every transferable surface; nothing material lives outside the six paths.**
   - **Falsification test:** run `harness_intent_audit.py` post-apply on a freshly bundled+applied install. If any of the 18 audit checkpoints fails specifically on a path NOT enumerated in `STATE_CLASSES`, A3 is broken — there is a seventh class.
   - **Risk if false:** silent state loss. Surfaces immediately at audit; engineer extends `STATE_CLASSES`.

4. **A4 — `WORKSPACE.md` shape (open-task block under `## Current step` or similar heading) is a reliable proxy for "active engagement".**
   - **Falsification test:** corpus test against `.agent/memory/working/WORKSPACE.md` history (git log) — replay each historic version through `is_active_engagement()` and check the boolean against a manually-labelled ground-truth set of 20 snapshots. False-negative rate must be <10%; false-positive rate must be 0% (we tolerate over-warning, not under-warning).
   - **Risk if false:** safe-default prompt is `y` instead of `N` during a live engagement. Mitigation: when in doubt, classify as active.

---

## 8. Alternatives Considered

### Alt-1 — Direct upstream port without state-class adapter (REJECTED)

Vendor upstream's `targets × scopes` model verbatim and refactor `install.sh`, `sync-target.sh`, and `harness-graduate.py` to consume `scopes`.
**Rejected because:** multi-week refactor outside PRD's 4-week budget; orphans the existing graduate semantics; introduces churn risk against `harness-graduate.py`'s five quality gates which the PRD explicitly fences off. Adapter layer is ~50 LOC and isolates fork divergence.

### Alt-2 — Build native fork-side tool from scratch, ignore upstream (REJECTED)

Write a fresh `transfer.py` matching only fork patterns.
**Rejected because:** loses the >1500 LOC of upstream behavior including atomic apply, manifest schema, plan diffing — proven shipped code. Re-deriving these costs more than the adapter.

### Alt-3 — Defer to v2 and ship `scp`-based recipe in docs only (REJECTED)

Pure documentation play: write a teammate-onboarding markdown that lists the `rsync` invocations.
**Rejected because:** PRD success criteria (S2 plan-before-apply, S4 active-engagement default-N) are not reachable with raw `rsync`. Operator pain documented as "lossy and slow" using exactly this workaround today.

### Alt-4 — Vendor + ship the upstream TUI in v1 (REJECTED)

Include `transfer_tui.py` for an interactive wizard.
**Rejected because:** PRD non-goal explicit ("No TUI wizard in v1"); R2 risk flag on TUI library dependency; OQ-1 concern over `textual` / `prompt_toolkit` runtime. Defer to v2.

### Alt-5 — Conflict resolution as per-entry interactive prompt (OQ-2 option (c)) (REJECTED by operator)

Plan-time prompt for each CONFLICT entry asking source-wins / dest-wins / skip.
**Rejected because:** operator chose option (a) (flag CONFLICT, skip unless `--force`) for predictability and for `--dry-run` to remain meaningful. Per-entry prompts would make `--dry-run` non-equivalent to live apply.

### Alt-6 — `client` class as all-or-nothing toggle (OQ-3 option (i)) (REJECTED by operator)

Include all `client/<slug>/` subdirs whenever `client` in `--classes`.
**Rejected because:** would leak prior engagements into a teammate handoff bundle. Operator chose explicit `--clients <slug>` allow-list (option (ii)).

---

## 9. Build sequence and milestones

Per PRD Section 7. Sequence is contractual; engineer may batch S1+S3 in one PR.

1. **S1 + S3** — `transfer_bundle.py` with `--classes` and `--clients` validation. Implements `_transfer_state_classes.py` registry. 1 week.
2. **S2** — `transfer_plan.py` with `compute_plan()`, `is_active_engagement()`, plan printer. 1 week.
3. **S4** — `import-transfer.sh` + `apply_plan()` + prompt gate + `--dry-run` + `--force`. 1 week.
4. **S5** — quick-start docs at `docs/quickstart/teammate-onboarding.md` and `docs/quickstart/second-laptop.md`; timed e2e fixture. 0.5 week.

---

## 10. Linkages

- **PRD:** `/Users/talwarpulkit/code/sdlc-test-pilot/docs/prd/2026-05-04-transfer-bundle-augment.md`
- **Tech-spike:** `output/tech-spikes/2026-05-04-transfer-bundle-vs-graduate/RECOMMENDATION.md`
- **DECISIONS entry:** appended same date — see `.agent/memory/semantic/DECISIONS.md` `2026-05-04: transfer-bundle augment — adopt with state-class adapter`
- **Branch (to be created):** `feature/transfer-bundle-augment`
- **Index:** `docs/adr/_index.md` (created if absent)

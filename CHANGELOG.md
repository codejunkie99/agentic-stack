# Changelog

All notable changes to this project.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.13.0] — UNRELEASED

Minor release. Adds a `gemini-cli` adapter so the portable brain works with
Google's Gemini CLI via its native MCP server extension mechanism.

### Added
- **`gemini-cli` adapter.** Adds `adapters/gemini-cli/` with an
  `adapter.json` manifest, `GEMINI.md` project context, an MCP server
  bridge (`mcp-server.js` + `mcp-package.json`) that exposes `recall`,
  `memory_reflect`, `learn`, and `agentic_status` as MCP tools, and four
  custom TOML slash commands (`/agentic:recall`, `/agentic:learn`,
  `/agentic:status`, `/agentic:reflect`).
- **Per-harness docs.** Adds `docs/per-harness/gemini-cli.md` covering
  install, MCP server registration, tool reference, slash commands, and
  troubleshooting.
- **Validation suite.** Adds `test_gemini_mcp.py` with 15 checks: manifest
  validation, GEMINI.md wiring, MCP server syntax/imports/tool
  registration, package.json deps/engines, TOML command fields, docs, and
  install/remove cycle.

### Changed
- Supported harness count is now eleven: Claude Code, Cursor, Windsurf,
  OpenCode, OpenClaw, Hermes, Pi, Codex, Standalone Python, Antigravity,
  and Gemini CLI.
- The adapter installs MCP server files into
  `<project>/.gemini/agentic-stack-mcp/` and custom commands into
  `<project>/.gemini/commands/agentic/`. Users must register the MCP
  server in `.gemini/settings.json` manually (documented in the per-harness
  guide and adapter README).

### Fixed
- n/a

### Migration
No migration required. Existing installs are unaffected. The gemini-cli
adapter is purely additive.

## [0.12.0] — 2026-04-27

Minor release. Adds the opt-in `tldraw` seed skill for live canvas diagrams
and a skill-local snapshot store. The feature stays beta and off by default.

### Added
- **`tldraw` seed skill — live canvas diagrams.** Adds
  `.agent/skills/tldraw/SKILL.md` with MCP tool guidance, shape constraints,
  and a self-rewrite hook for diagram, sketch, wireframe, flowchart,
  whiteboard, and architecture visualization prompts.
- **Skill-local snapshot store.** Adds `.agent/skills/tldraw/store.py` with
  `snapshot`, `list`, `load`, and `archive` CLI/API support. Runtime output is
  local and gitignored under `.agent/skills/tldraw/`: `snapshots.jsonl`,
  `snapshots/`, and `INDEX.md`.
- **Opt-in feature flag.** Onboarding now writes a `tldraw` beta feature flag,
  default off. The skill loader skips flagged skills unless
  `.agent/memory/.features.json` explicitly enables them.
- **Manual MCP config source.** Adds `adapters/_shared/tldraw-mcp.json` as the
  canonical tldraw MCP config block users can merge into Claude Code,
  Cursor, or Antigravity after enabling the feature.

### Changed
- Seed skill count is now nine: `skillforge`, `memory-manager`, `git-proxy`,
  `debug-investigator`, `deploy-checklist`, `design-md`, `data-layer`,
  `data-flywheel`, and `tldraw`.
- tldraw persistence is intentionally skill-local storage, not a fifth memory
  layer: it has no dream-cycle, clustering, recall, or semantic-memory
  lifecycle.
- Default adapter installs no longer wire beta tldraw MCP config
  automatically.

### Fixed
- Updated the tldraw validation suite to target
  `.agent/skills/tldraw/store.py` instead of the removed
  `.agent/memory/visual/visual_memory.py`.
- `store.py` renders `INDEX.md` while holding the JSONL lock so concurrent
  snapshots cannot leave the index stale.
- Added coverage for feature-gated skill loading, no default MCP install, path
  traversal rejection, malformed JSONL recovery, same-second snapshot ids, and
  concurrent snapshots.

### Migration
No migration required. Existing installs keep tldraw disabled until users opt
in through onboarding reconfiguration or `.agent/memory/.features.json`.

### Credits
- PR #11 by @Siddharth11Roy, with review fixes and release prep by Codex.

### Release
- Tag `v0.12.0` cut from master.
- GitHub release: <https://github.com/codejunkie99/agentic-stack/releases/tag/v0.12.0>
- `Formula/agentic-stack.rb` bumped to v0.12.0 in a follow-up commit after
  the tag tarball existed and its sha256 could be computed.
- Tarball sha256:
  `cd18a0cf82e027390ef10a102ec4bfed26fc45114f6ce96c0787e5a1cf0dce26`.

## [0.11.2] — 2026-04-26

Patch release. Makes the data-layer dashboard easier to access from coding
tools by turning the injected `data-layer` skill into the natural-language
dashboard surface.

### Added
- **Injected dashboard behavior.** The `data-layer` skill now triggers on plain
  phrases such as "show me the dashboard", "what did my agents do",
  "agent status", and "usage report". When the model decides the user wants
  local agent activity, the skill tells it to render the terminal dashboard
  directly instead of making the user remember flags.
- **Natural-language exporter requests.** The existing exporter now accepts
  requests such as
  `python3 .agent/tools/data_layer_export.py show me last 7 days by hour`.
  It maps common phrases to `--window` and `--bucket`; explicit flags still
  override the natural-language text for scripts and automation.

### Changed
- The terminal dashboard now uses the same rail/marker visual language as the
  onboarding flow while keeping `dashboard.tui.txt` plain text with no ANSI
  escape codes.
- `dashboard-summary.json` records the natural-language request that produced
  the export when one was provided.

### Migration
No migration required. Existing flag-based commands still work.

### Release
- Tag `v0.11.2` cut from master.
- GitHub release: <https://github.com/codejunkie99/agentic-stack/releases/tag/v0.11.2>
- `Formula/agentic-stack.rb` bumped to v0.11.2 in a follow-up commit after
  the tag tarball existed and its sha256 could be computed.
- Tarball sha256:
  `b9eb098466376c13e087dc91a0655d97481dfd13a6f640989384881990eb1e58`.

## [0.11.1] — 2026-04-26

Patch release. Makes the data-layer dashboard visible directly in coding-tool
terminals and adds a visual SVG explainer for the data-layer flow.

### Added
- **Terminal dashboard by default.** The existing
  `python3 .agent/tools/data_layer_export.py --window 30d --bucket day`
  command now prints a compact TUI-style dashboard after writing exports. It
  shows resource numbers, latest bucket activity, top harnesses, top workflows,
  top categories, and artifact paths without requiring a browser.
- **`dashboard.tui.txt`.** The same terminal dashboard is saved next to
  `dashboard.html`, CSV/JSON exports, and `daily-report.md` for agents and
  users who want to inspect or attach a plain-text report.
- **`docs/data-layer.svg`.** README and `docs/data-layer.md` now include a
  visual of the local data-layer flow: input streams, exporter, browser
  dashboard, terminal dashboard, CSV/JSON, and approved handoff.

### Changed
- `dashboard-report.json` now advertises the terminal dashboard artifact.
- Data-layer docs no longer require a separate command to see the terminal
  view; the normal export command prints it.

### Migration
No migration required. Existing data-layer commands still work; they now print
the terminal dashboard in addition to the previous status lines.

### Release
- Tag `v0.11.1` cut from master.
- GitHub release: <https://github.com/codejunkie99/agentic-stack/releases/tag/v0.11.1>
- `Formula/agentic-stack.rb` bumped to v0.11.1 in a follow-up commit after
  the tag tarball existed and its sha256 could be computed.
- Tarball sha256:
  `c0f09417c6caf34ba712d03271177ea2779af50e86a19bf76c10ba5d50bcff3e`.

## [0.11.0] — 2026-04-26

Minor release. Adds two local-first data capabilities: a cross-harness
monitoring/data layer and an approved-run data flywheel. Both stay private by
default, write regenerated runtime artifacts under ignored `.agent/`
subdirectories, and avoid remote telemetry or model training.

### Added
- **`data-layer` seed skill — local cross-harness monitoring.** Adds
  `.agent/skills/data-layer/SKILL.md` and
  `.agent/tools/data_layer_export.py` to export dashboard-ready local data
  across Claude Code, Hermes, OpenClaw, Codex, Cursor, OpenCode, and custom
  loops sharing the same `.agent/` brain. Outputs include agent events, cron
  timelines, KPI summaries, token/cost estimates, category breakdowns,
  `dashboard.html`, and `daily-report.md`. Runtime exports live under
  `.agent/data-layer/`, which is gitignored. Thanks to @danielfoch for PR #25.
- **`data-flywheel` seed skill — approved runs to reusable artifacts.** Adds
  `.agent/skills/data-flywheel/SKILL.md` and
  `.agent/tools/data_flywheel_export.py` to turn human-approved, redacted runs
  into trace records, context cards, eval cases, training-ready JSONL, and
  flywheel metrics. Runtime exports live under `.agent/flywheel/`, which is
  gitignored. The tool is local-only, model-agnostic, and does not train
  models or call external APIs. Thanks to @danielfoch for PR #26.
- Schemas, sanitized examples, tests, README sections, and architecture docs
  for both local data features.

### Changed
- Seed skill count is now eight: `skillforge`, `memory-manager`, `git-proxy`,
  `debug-investigator`, `deploy-checklist`, `design-md`, `data-layer`, and
  `data-flywheel`.
- `docs/architecture.md` now describes five local modules: memory, skills,
  protocols, data layer, and data flywheel.

### Migration
`brew upgrade agentic-stack` is enough. There are no on-disk schema changes.
The new runtime directories, `.agent/data-layer/` and `.agent/flywheel/`, are
private and regenerated; both are gitignored.

### Release
- Tag `v0.11.0` cut from master.
- GitHub release: <https://github.com/codejunkie99/agentic-stack/releases/tag/v0.11.0>
- Superseded by v0.11.1 before the Homebrew formula bump.

### Credits
- PR #25 and PR #26 by @danielfoch.
- Merge conflict resolution, verification, and release prep by Codex.

## [0.10.0] — 2026-04-26

Minor release. Adds the `design-md` seed skill (sixth seed skill in the
brain), and fixes a hard crash on macOS-default Python 3.9 that hit every
brew user on first run.

### Added
- **`design-md` seed skill — DESIGN.md / Google Stitch support.** A new
  portable skill that points coding agents at a root `DESIGN.md` (Google
  Stitch format) as the visual-system source of truth. Loads only when
  `DESIGN.md` exists at the project root; default behavior is read-only on
  the contract file, and validation prefers
  `npx @google/design.md lint DESIGN.md` over hand-checks. Brings the seed
  skill count from five to six. Thanks to @danielfoch for the contribution
  (PR #21). Decision recorded in `.agent/memory/semantic/DECISIONS.md`.

### Fixed
- **Python 3.9 crash on first run (#27).** Every brew user on macOS-default
  Python 3.9 hit `TypeError: unsupported operand type(s) for |: 'type' and
  'type'` immediately after `brew install agentic-stack` because
  `harness_manager/` used PEP 604 union syntax (`Path | str`) that requires
  Python 3.10+ at runtime. Added `from __future__ import annotations`
  (PEP 563) to the eight affected files so all annotations are stored as
  strings and never evaluated at import time. Works on Python 3.7+, which
  covers every macOS-shipped Python in the wild. Zero-cost vs. the
  reporter's suggested `python@3.10` brew dep (~150 MB pull). Thanks to
  @WhoLsJohnGalt for the precise repro and the suggested workaround.

### Migration
`brew upgrade agentic-stack` is enough — no on-disk schema changes. Users
on Python 3.9 who hit #27 on v0.9.x can upgrade and the crash goes away.
Users with existing `.pi/extensions/memory-hook.ts` from v0.9.0 already
got the fixes via `./install.sh pi` after the v0.9.1 upgrade; this release
adds the `design-md` skill on top.

### Release
- Tag `v0.10.0` cut from master.
- GitHub release: <https://github.com/codejunkie99/agentic-stack/releases/tag/v0.10.0>
- `Formula/agentic-stack.rb` bumped to v0.10.0 in a follow-up commit
  (same flow as v0.8.0 → v0.9.0 → v0.9.1): tag first, compute sha256,
  then bump `url` + `sha256` + `version` together so brew always points
  at a real installable artifact.

### Credits
- PR #21 by @danielfoch (design-md skill), with cross-model review fixes
  applied as a follow-up commit.
- Issue #27 by @WhoLsJohnGalt — clean repro of the macOS Python 3.9 crash
  including a working sed-based workaround.

## [0.9.1] — 2026-04-26

Patch release that closes the gap between v0.9.0 and a working pi adapter.
Every brew user on v0.9.0 hit the first bug; the rest are quieter but make
the dream cycle and the cross-harness episodic log actually correct.

### Fixed
- **`agentic-stack pi` crashed for every brew user with `ModuleNotFoundError:
  No module named 'harness_manager'`.** The v0.9.0 Formula didn't include
  `harness_manager/` in `pkgshare.install`, so `install.sh` couldn't dispatch.
  Adds it back.
- **Pi dream cycle never fired.** The `session_shutdown` handler filtered
  on `event.reason`, but Pi's `SessionShutdownEvent` carries no `reason`
  field — verified against `pi-coding-agent` types.d.ts and the emit site
  at `agent-session.js:1638`. The filter rejected every event, so
  `auto_dream.py` never ran. Filter dropped; re-entrancy guard added.
- **Pi edit reflections lost the diff.** Hook accessed `event.input.edits[0]`
  but Pi's `EditToolInput` is flat `{ path, oldText, newText }` (no `edits`
  array — that's MultiEdit on Claude Code). Reflections silently degraded
  to `Edited <path>` with no old/new content. Read the flat fields.
- **`decay.py` crashed comparing aware-UTC entries to naive cutoff.** The
  new `session_shutdown` hook surfaced this on every clean pi exit. Cutoff
  is now `datetime.now(timezone.utc)`; entry timestamps are normalised to
  UTC before comparison.
- **Naive-local Python timestamps drifted against the UTC decay window.**
  Decay's "naive == UTC" assumption was correct only if writers emitted UTC.
  They didn't: `post_execution`, `on_failure`, `learn`, `graduate`,
  `promote`, `review_state`, `render_lessons` all wrote naive-local. Every
  writer now emits aware UTC; every reader (`salience`, `show._human_age`
  / `_daily_counts` / `failing_skills` / `last_dream_cycle`,
  `on_failure._count_recent_failures`, `review_state._age_factor`,
  `archive`) normalises naive timestamps to UTC before comparison.
- **One bad regex in `hook_patterns.json` disabled every user pattern in
  the Pi hook.** Pre-fix used a single combined RegExp per list, caught
  any error, returned null for both. Now per-fragment validation with
  incremental merge — same posture as `claude_code_post_tool.py`'s
  `_filter_valid` / `_build_with_fallback`.
- **`auto_dream` lost entries that landed mid-cycle.** Original `_write_entries`
  had a truncate-before-lock window — `open(path, "w")` truncates BEFORE
  a lock can be taken. The deeper bug: even after fixing the inner race,
  any `append_jsonl()` between `_load_entries()` and `_write_entries(kept)`
  would be truncated away by the rewrite. The cycle now holds a single
  exclusive flock on `AGENT_LEARNINGS.jsonl` across the entire
  read-modify-write window via `_episodic_locked()`. Mutually exclusive
  with `_episodic_io.append_jsonl` (same flock target). POSIX only;
  Windows falls back to historical best-effort behaviour.
- **`_cachedSha` went stale after `git commit` inside a pi session.** TS
  hook cached the SHA per-process for performance, so every entry logged
  after a mid-session commit recorded the pre-commit SHA. Cache, but
  invalidate on bash commands matching `git <subcmd>` for HEAD-moving
  subcommands. Allows option flags between `git` and the subcommand
  (`git -c key=val checkout main`, `git -C path switch dev`).
- **`salience` over-scored future-skewed legacy rows.** Legacy naive-local
  timestamps re-interpreted as UTC could read as a few hours in the future
  during the migration window. `timedelta.days` then went negative and
  recency exceeded the intended cap. Floor age at 0; clamp recency to ≤ 10.
- **`decay` archive filename used local date while cutoff was UTC.**
  `archive_{date}.jsonl` now uses UTC date so a tz-jumping user gets a
  deterministic path.

### Changed
- `adapters/pi/adapter.json` no longer manages
  `.agent/harness/hooks/pi_post_tool.py` via `from_stack`. The TS hook is
  self-contained — all scoring + reflection inline, no Python subprocess
  per tool call. The .py still ships in the brain template under
  `.agent/harness/hooks/` for standalone use.
- `tests/` is now untracked and listed in `.gitignore`. CI never ran
  these (`.github/workflows/ci.yml` runs `test_claude_code_hook.py` +
  `verify_*.py` at repo root). Pull from an older tag if you want the
  unittest suite locally.

### Migration
`brew upgrade agentic-stack` is enough — there are no on-disk schema
changes. Existing pi installs with the v0.9.0 hook get the new logic on
the next `./install.sh pi`. Existing `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`
files with naive-local timestamps continue to work — readers normalise
them at compare time and writers emit UTC going forward.

### Release
- Tag `v0.9.1` cut from master at `d7b70b2`.
- GitHub release: <https://github.com/codejunkie99/agentic-stack/releases/tag/v0.9.1>
- `Formula/agentic-stack.rb` bumped to v0.9.1 in a follow-up commit
  (same flow as v0.8.0 → v0.9.0): tag first, compute sha256, then bump
  `url` + `sha256` + `version` together so brew always points at a real
  installable artifact.
- Tarball sha256:
  `09cc3b8c9ec159cf8b85cf672fc15a29e6bfa9377cc9c59dd270acd441ced568`
  (verify locally with
  `curl -sL https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.9.1.tar.gz | shasum -a 256`)

### Credits
PR #24 by @aliirz; Codex CLI used for an independent second-opinion review
that surfaced the auto_dream window race + the SHA-regex narrowness.

## [0.9.0] — 2026-04-23

### Added
- **Harness manager: manifest-driven adapter system.** Each adapter now
  ships an `adapters/<name>/adapter.json` declaring its files,
  collision policy, optional skills directory mirror, and named
  post-install actions. Adding a new adapter is now a JSON-only PR —
  no Python code, no test wiring, no class registration. Lives in the
  new `harness_manager/` Python package.
- **`./install.sh add <adapter>`** — append an adapter to an existing
  project without re-running the onboarding wizard.
- **`./install.sh remove <adapter>`** — confirmation prompt lists every
  file before deletion. Hard delete (no quarantine, no undo — git is
  the safety net). Reverses post-install actions automatically (e.g.,
  `openclaw agents remove`).
- **`./install.sh doctor`** — read-only audit of installed adapters.
  Verifies tracked files exist, post-install state is valid, `.agent/`
  brain is intact. Exits 0 on green, 1 on red. First run on a
  pre-v0.9.0 project asks before synthesizing `install.json` — never
  silently mutates.
- **`./install.sh status`** — one-screen view of installed adapters,
  brain stats (skills/episodic/lessons), last-updated timestamp.
- **`.agent/install.json`** — authoritative record of what's installed.
  Schema-versioned. Atomic write via tempfile + rename, fcntl-locked
  on POSIX.
- **PowerShell parity from day one.** `install.ps1` is now a 70-line
  thin dispatcher to the same Python backend `install.sh` uses. The
  new `add`/`remove`/`doctor`/`status` verbs behave identically across
  mac/Linux/Windows. Was 270+ lines of duplicated bash-shaped logic.
- `docs/per-harness/standalone-python.md` — gap-fill for the only
  harness that didn't have a per-harness doc.

### Fixed
- **#18** — Claude Code hook commands break when cwd is not the
  project root. `adapters/claude-code/settings.json` template now uses
  `{{BRAIN_ROOT}}` placeholder, which the manifest backend substitutes
  with `$CLAUDE_PROJECT_DIR` at install time. Hook commands resolve
  correctly regardless of which directory Claude Code's cwd points at.
  Thanks to @palamp for the report and the proposal that shaped the
  larger feature.

### Security
- **Manifest path-safety hardening (`harness_manager/schema.py`).** The
  pre-existing path-traversal guard only tokenized on `/` and only
  treated `/`-prefixed paths as absolute, so Windows-style inputs
  (`..\..\outside`, `\\server\share`, `C:\temp\x`, `C:foo`) bypassed
  validation and could let install/remove read or write outside the
  adapter/project roots when run on Windows. Also extended the same
  validation to `skills_link.target` and `skills_link.dst`, which were
  previously only checked for presence — a manifest could otherwise
  point the symlink/rsync into arbitrary filesystem locations on any
  platform. Both POSIX and Windows separators are now normalized
  before traversal detection, and every common absolute-path form
  (POSIX root, Windows root, UNC, drive-letter) is rejected.

### Changed
- `install.sh` shrinks from 175 lines of bash case-statements to 35
  lines of dispatcher. All install logic moved to `harness_manager/`.
  Existing CLI surface preserved: `./install.sh <adapter> [target]
  [--yes|--reconfigure|--force]` works identically.
- `install.ps1` shrinks from 270+ lines to 70.

### Migration
Existing v0.8.x users: `brew upgrade agentic-stack`, then run
`./install.sh doctor` in your project. Doctor detects existing
adapters from filesystem signals and asks before writing `install.json`.
Subsequent doctor runs are read-only.

### Release checklist (post-merge, pre-`brew upgrade`)
The Homebrew Formula (`Formula/agentic-stack.rb`) intentionally still
points at the v0.8.0 tarball in this PR. The v0.9.0 release flow is:

1. Merge this PR to master.
2. Tag `v0.9.0` on master and create the GitHub release.
3. Run `curl -L https://github.com/codejunkie99/agentic-stack/archive/refs/tags/v0.9.0.tar.gz | shasum -a 256` to compute the new sha256.
4. Open a follow-up PR that updates `url`, `sha256`, `version` together,
   and adds `harness_manager` + `install.ps1` to the `pkgshare.install` line.
   This is the same pattern as commit `abaa352` (the v0.8.0 sha256 bump).

Reason for the split: a Formula change that adds `harness_manager/` to
`pkgshare.install` while still pointing at the v0.8.0 tarball would fail
brew install (file-not-found in the staged tarball). Bumping all four
fields together as a follow-up after the tag exists keeps the formula
always pointing at a real, installable artifact.

## [0.8.0] — 2026-04-21

### Added
- **Google Antigravity adapter.** `./install.sh antigravity` drops an
  `ANTIGRAVITY.md` into the project root so Antigravity agents pick up
  the portable brain in `.agent/`. Matches the pattern of the other
  root-instruction harnesses. Brings the supported-harness count to 9.
  Thanks to @smartsastram for the contribution (PR #9).
- **Rich `PostToolUse` episodic logging for Claude Code.** New
  `.agent/harness/hooks/claude_code_post_tool.py` reads the JSON payload
  Claude Code sends via stdin and derives a real action label, importance
  score, and non-empty reflection per tool call. Replaces the old
  hardcoded `post-tool ok` that produced identical entries every session
  and left the dream cycle with nothing to cluster on. Ships with a
  54-test validation suite (`test_claude_code_hook.py`). Thanks to
  @aliirz for the contribution (PR #8).
- **User-owned stack tuning via `hook_patterns.json`.** Drop your own
  high-stakes and medium-stakes command patterns in
  `.agent/protocols/hook_patterns.json` so the hook scores `vercel deploy`,
  `supabase migrate`, etc. correctly for your stack. Ships with empty
  arrays and a `_examples` section; universal patterns stay hardcoded.
- **`on_failure()` severity overrides.** New `importance=` and
  `pain_score=` parameters so a failed production deploy records its real
  severity instead of the flat `importance=7 / pain_score=8` defaults.
  Lets the dream-cycle salience formula actually distinguish a failed
  migration from a failed `ls`.
- **Bash wrapper-aware failure detection.** `_is_success()` now detects
  explicit exit-masking wrappers (`|| true`, `|| :`, `|| exit 0`,
  `; true`) and falls through to stderr-based signal when they are
  present, so masked production failures are still captured. Quoted
  strings and `set +e` are excluded from masking detection to avoid
  false positives on patterns like `echo '... || true ...'` and
  `set +e; grep X log; set -e`.
- **33-check regression verifier.** `verify_codex_fixes.py` validates
  every classification path after 7 rounds of codex review. Named
  `verify_*.py` (not `test_*.py`) to avoid pytest collection side
  effects. Uses a TMPDIR / `$HOME` / repo-local / `VERIFY_TMPDIR`
  fallback chain so it runs in constrained sandboxes.

### Fixed
- **Bash `exit_code=0` no longer second-guessed via stdout.** Commands
  like `grep Error /var/log/app.log` and `cat failures.log` used to be
  recorded as failures because the output contained error-looking
  strings. Exit code is now authoritative for Bash responses.
- **User regex fragments in `hook_patterns.json` can't crash the hook.**
  Each fragment is validated standalone via `re.compile`; invalid ones
  are dropped with a stderr warning. Merged-compile failures (e.g., a
  fragment like `(?i)foo` that validates alone but breaks once embedded)
  fall back to an incremental build that drops only the offending
  fragments, preserving universals and good user fragments.
- **`on_failure` reflection no longer prefixes `str:` for string errors.**
  Only `Exception` objects get a type-name prefix now.

### Changed
- **Wizard version bumped to 0.8.0** in `onboard_render.py`.
- **Wizard outro** now points users at `.agent/protocols/hook_patterns.json`
  so they know they can extend the importance scorer with their stack's
  service names.

## [0.7.2] — 2026-04-20

### Changed
- **README repositioning.** Leads with the actual buyer pain —
  switching coding-agent tools keeps resetting how your agent behaves —
  so the adapter list, wizard, and memory architecture read as proof
  instead of preamble. Follow / coded-using / article framing moved
  into the Credits section.

## [0.7.1] — 2026-04-20

### Changed
- **Relicensed from MIT to Apache 2.0.**

## [0.7.0] — 2026-04-20

### Added
- **`learn.py` host-agent tool.** Teach the agent a rule in one
  command: `python3 .agent/tools/learn.py "Always serialize timestamps
  in UTC" --rationale "past cross-region bugs"`. Stages, graduates, and
  renders in one step. Idempotent. Cleans up staged files on heuristic
  reject; preserves on crashes so retries work.
- **`recall.py` host-agent tool.** Surfaces graduated lessons relevant
  to what you're about to do. Ranked lexical-overlap hits with per-entry
  source labels. Merges `lessons.jsonl` and seed bullets in `LESSONS.md`
  so graduating your first lesson doesn't hide the seeds. Logs every
  recall to episodic memory for audit.
- **`show.py` host-agent tool.** Colorful dashboard of brain state
  (episodes, candidates, lessons, failing skills, 14d activity
  sparkline). `--json` / `--plain` / `NO_COLOR` flags.
- **Adapter wiring for recall across all 8 harnesses.** Every adapter
  (`claude-code`, `cursor`, `windsurf`, `opencode`, `openclaw`,
  `hermes`, `pi`, `standalone-python`) now instructs the model to run
  `recall.py "<intent>"` before deploy / migration / timestamp / debug
  / refactor work, and to surface results in a
  `Consulted lessons before acting:` block.
- **Pre-graduated seed UTC lesson** so new installs see proactive recall
  return a real hit on first try. Stored at
  `.agent/memory/semantic/lessons.jsonl`.

### Fixed
- **Canonical `pattern_id`.** Conditions are casefolded, unicode
  whitespace collapsed, zero-widths stripped, deduped, sorted — the
  same logical set always yields the same id.
- **Stricter heuristic check.** `validate.heuristic_check` now requires
  ≥3 content words in a claim (blocks junk like `!!!abc` that passed
  the raw-length gate).
- **Idempotent `graduate.py` retries.** Re-renders `LESSONS.md`, honors
  original reviewer / rationale from `lessons.jsonl` to keep stores
  in sync, refuses retries against legacy rows missing metadata.
- **Advisory flock on `lessons.jsonl`.** `render_lessons` and
  `append_lesson` now hold an exclusive flock during writes. Concurrent
  writers serialize; `LESSONS.md` can no longer go stale relative to
  `lessons.jsonl`. Atomic rewrite via temp file + rename.

## [0.6.0] — 2026-04-17

### Added
- **Pi Coding Agent adapter.** `./install.sh pi` drops `AGENTS.md` and
  symlinks `.pi/skills` to `.agent/skills` so pi sees the full brain
  with zero duplication. Safe to install alongside `hermes` / `opencode`
  (all read `AGENTS.md`; the installer skips the overwrite if one
  exists).

### Changed
- **BREAKING: `openclient` adapter renamed to `openclaw`.** Installed
  file changed: `.openclient-system.md` → `.openclaw-system.md`.
  Existing OpenClient users: re-run `./install.sh openclaw`.

## [0.5.0] — 2026-04-17

### Added
- **Host-agent review protocol.** Python handles filing (cluster, stage,
  heuristic prefilter, decay). The host agent handles reasoning via
  `list_candidates.py` / `graduate.py` / `reject.py` / `reopen.py`.
  Graduation requires `--rationale` so rubber-stamping is structurally
  impossible. Zero unattended reasoning, zero provider coupling.
- **Structured `lessons.jsonl` as source of truth.** `LESSONS.md` is
  rendered from it. Hand-curated content above the sentinel is preserved
  across renders; legacy bullets auto-migrate on first run.
- **Proper single-linkage clustering with bridge-merge.** Pattern IDs
  derived from canonical claim + conditions, stable across cluster-
  membership changes, distinct for generic-canonical collisions.
- **Query-aware retrieval.** `context_budget` ranks episodes by salience
  × relevance and filters lessons to `status=accepted` only —
  provisional, legacy, and superseded entries never leak into the
  system prompt.
- **[BETA] FTS5 memory search** (`.agent/memory/memory_search.py`).
  Opt-in via onboarding or `.agent/memory/.features.json`. Default off.
  Prefers ripgrep when FTS5 is not available, falls back to grep.
  Restricted to `.md` / `.jsonl` so source files never pollute results.
- **Windows-native installer.** `install.ps1` runs natively under
  PowerShell; `install.sh` continues to work under Git Bash / WSL.

### Fixed
- Batch-sound graduation gate.
- Stable slugs across cluster drift.
- Provisional re-review and supersession semantics.
- `REVIEW_QUEUE` refreshes on every CLI action.
- Heuristic-rejection stamping so unrelated `LESSONS.md` edits do not
  churn.
- Atomic `graduate.py` (semantic write first, candidate move last).
- `.gitignore` ordering so `.agent/memory/.index/` is actually ignored.
- Fallback search restricted to `.md` / `.jsonl`.
- Feature toggle file and `[BETA]` label in onboarding.

## [0.4.0] — 2026-04-16

### Added
- **Interactive onboarding wizard** (`onboard.py`, clack-style UI) that
  auto-fills `PREFERENCES.md` after install. Flags: `--yes` (CI /
  defaults), `--reconfigure` (re-run). Apple-style redesign with 7
  scenes (Memory, Skills, Dream Cycle added).

## [0.3.0] — 2026-04-16

### Fixed
- Cron-safe paths in `auto_dream.py` and `Stop` hook matcher.
- Deny-glob syntax in `settings.json`.

## [0.2.0] — 2026-04-16

### Added
- **Homebrew formula** at `Formula/agentic-stack.rb`.

### Fixed
- `standalone-python` path detection.
- Harness count in README.
- `brew tap` URL in README.

## [0.1.0] — 2026-04-16

### Added
- Initial release. Portable `.agent/` brain folder with adapters for
  Claude Code, Cursor, Windsurf, OpenCode, OpenClient (later OpenClaw),
  Hermes, and standalone Python. Homebrew installer (replaces the
  earlier `npx`-based flow).

[0.8.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.7.2...v0.8.0
[0.7.2]: https://github.com/codejunkie99/agentic-stack/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/codejunkie99/agentic-stack/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/codejunkie99/agentic-stack/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/codejunkie99/agentic-stack/releases/tag/v0.1.0

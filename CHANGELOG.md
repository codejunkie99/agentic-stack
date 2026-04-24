# Changelog

All notable changes to this project.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

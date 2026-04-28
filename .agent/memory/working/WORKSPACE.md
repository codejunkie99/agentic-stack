# Workspace (live task state)

> Live "where are we right now" file. Updated when we move between steps,
> hit a blocker, or change direction. For the durable history of *why* we
> did things, see `.agent/memory/semantic/DECISIONS.md`.

## Current step

**Step 8.3 — real-case dry-run (in progress, 2026-04-27)**

Branch: `feature/step-8-3-real-case-dry-run`. Plan:
`/Users/talwarpulkit/.claude/plans/before-we-go-into-foamy-mccarthy.md`.

## Why now

The roster is complete (5 SDLC + 16 BCG agents, 17 skills + 3 new from
upstream, 6 workflows, generic context, BCG adapter content) and the
install path is current and Python-driven. 8.3 exercises the stack
against a real consulting workflow (pure consulting case, real-but-
redacted briefing) to surface gaps the unit-level smoke tests can't,
and adds the onboarding + write-protection + propagation-capture
scaffolding that was missing.

## Stage plan

- **Stage 1** — branch + WORKSPACE update ✅
- **Stage 2** — build the kit on fork ✅ (9 commits + smoke-test fix)
- **Stage 3** — install + onboard target ✅
  - Target: `~/code/case-dryrun-harnessX-internal/` (own git, fresh)
  - Engagement: HarnessX deck iteration (post-Vince-edit baseline)
  - 14 briefing files indexed under lazy-load with summaries (8 original + 6 new from 04-28)
  - Brain installed cleanly: 21 agents, 26 skills (incl. new `consulting-deck-builder`), 66-file install snapshot baselined at 14:23 on 04-28
- **Stage 3.5 (mid-engagement augment, 2026-04-28)**
  - Vince meeting completed; deck restructured around 3-plane Harness Framework
  - v3 deck retired; v4 post-Vince-edit baselined
  - 6 new files indexed: HarnessX_v4 PDF, BOCHK PDF, Balaji PDF, SC AI SDLC PDF, 04-28 meeting summary md + transcript pdf + mind map png
  - NEW skill `consulting-deck-builder` authored on fork branch — 3-phase storyboard → content → format methodology with vertical/horizontal MBB logic gates and sticky migration. Manually synced to target (Gap 7 surfaced — same root cause as Gap 1).
  - Mission shifted from "revise v3 against 5 quality bars" to "build content per slide using all sources + online research, iterate via consulting-deck-builder skill"
  - `pypdf` installed (Gap 6) so PDF source material extracts cleanly
- **Stage 3.6 — skill conformance audit + linter (2026-04-28)**
  - Audit found 5/26 skills missing self-rewrite hook (analysis,
    context-search, document-assembly, draft-status-update, review)
  - All 5 hooks added — each tailored to that skill's failure mode
  - New `.agent/tools/skill_linter.py` validates frontmatter,
    self-rewrite hook presence, manifest match, index match
  - New `git-hooks/pre-commit` runs linter on staged skill changes
  - Activated locally: `git config core.hooksPath git-hooks`
  - 26/26 skills now conformant; linter verified by passing on its
    own commit
  - Closes Gap 8 ("no structural-conformance enforcement on skills")
- **Stage 4** — run the dry-run case (PENDING — user opens separate Claude Code session in target)
- **Stage 5** — capture, gap log, fix loop (5 entries already)

### Original Stage 2 commit list

- **Stage 2** — build the kit on fork (8 atomic commits):
  - 2a. `skill_evolution_mode` config flag (Philosophy C, in_place default)
  - 2b. Slim 6-path install-side write protection (native `permissions.deny`)
  - 2c. `client-onboarding` skill
  - 2d. `document-researcher` skill
  - 2e. `INDEX.md` template + extend client `_template/`
  - 2f. CLAUDE.md conditional-mount lazy-load fix
  - 2g. `propose-harness-fix.py` capture tool
  - 2h. `snapshot_diff.py` + post_install snapshot hook
- **Stage 3** — install + onboard new tracked target at
  `~/code/case-dryrun-<slug>/` (own git repo). Real-but-redacted briefing
  dropped into `raw-uploads/`. Drive `client-onboarding` end-to-end.
- **Stage 4** — run pure-consulting workflow end-to-end through BCG
  pipeline. Save transcript to `examples/dry-runs/8-3-<slug>.md`.
- **Stage 5** — capture (`snapshot_diff.py --diff`), gap log at
  `docs/superpowers/plans/2026-04-27-step-8-3-gap-log.md`, fix-and-
  reinstall loop on blockers, defer non-blockers to 8.4, graduate
  durable lessons.

## Locked decisions (input to plan)

- **Skill evolution**: Philosophy C hybrid; `skill_evolution_mode: "in_place"` default, `propose_only` opt-in.
- **Read-only set in installs (slim, 6 paths)**: `CLAUDE.md`, `.claude/settings.json`, `.claude/agents/**`, `.agent/protocols/permissions.md`, `.agent/harness/**`, `.agent/AGENTS.md`. Skills + memory + agent-memory stay writable (preserves skillforge + per-skill self-rewrite + dream cycle).
- **Cross-install propagation**: instrument capture in 8.3; `harness-graduate.py` deferred to 8.4; `install.sh --upgrade` deferred to 8.5.
- **Target**: new tracked git project at `~/code/case-dryrun-<slug>/`.
- **Case scope**: pure consulting (situation assessment → issue tree → recommendation deck).
- **Briefing**: user-supplied real-but-redacted, into `<target>/.agent/memory/client/<slug>/raw-uploads/`.
- **Onboarding kit**: full (both new skills + INDEX pattern + lazy-load fix + propose-harness-fix + snapshot/diff).

## Recurring cadence

- Weekly upstream sync check: every Monday morning. Mechanism:
  `CronCreate` (durable, 7-day TTL, ID `ba87d58c`, fires Mon 9:13 local)
  re-armed each fire, plus auto-memory entry `upstream_sync_cadence.md`
  so the cadence survives session restarts beyond the cron's lifetime.

## Recent upstream-sync checks

- 2026-04-27 — base WAS v0.8.0 (`a397568`); 59 commits behind across 6
  tags through v0.11.2. Merged via Step 8.2.5. Base now v0.11.2 + 8.x
  + BCG harness_manager port. Two upstream regressions discovered &
  fixed locally (cli.py future import, claude-code adapter.json SDLC
  agent entries) — candidates to upstream as PRs to codejunkie99.

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
- **Stage 4** — run the dry-run case ✅ (Phase 1 storyboard v3 + Phase 2
  content-draft 20 main + 8 appendices + 3-reviewer panel GO-WITH-FIXES;
  Phase 3 deferred — gated on Slide 6 metric verify, SC brand-strip,
  Slide 3 rubric spot-check, Slide 7 demo binary)
- **Stage 8 — Phase I — vendored deckster + content-faithful Phase 3 ✅ (2026-04-29)**
  - Vendored deckster-slide-generator (BCG-internal, 17MB) installed
    at `adapters/bcg/skills/deckster-slide-generator/` per existing
    `confluence-access` convention
  - Sidecar `INTEGRATION.md` documents content-faithful contract:
    content-draft.md is read-only authoritative; titles, body, slide
    order locked; 8 sticky types translate to render hints, not
    regen triggers; 4 Phase 3 entry preconditions are hard render
    gates BEFORE deckster invocation; speaker-note pass happens in
    consulting-deck-builder, not in deckster
  - `consulting-deck-builder` Phase 3 section rewritten to dispatch
    deckster under `mode="content_faithful"`
  - New vendored-skill convention in `skill_linter.py`: dirs with
    `INTEGRATION.md` skip conformance (vendored skills don't need
    our self-rewrite hook — they sync from upstream)
  - Manually synced to HarnessX target; both lint surfaces clean
  - Open gap: `bcg_conditional_propagate` doesn't propagate skills;
    Phase J should cover it. Logged in DECISIONS.md.
  - Phase 3 of HarnessX now unblocked (subject to 4 entry preconds)
- **Stage 7 — Phase L — memory-write discipline in consulting-deck-builder ✅ (2026-04-29)**
  - Replaced single `--importance 6` reflect call with 3 structured
    phase-exit blocks: Phase 1 (8×5=40, dominates cluster), Phase 2
    (10×8=80, auto-graduates), Phase 3 (9×7=63, dominates cluster)
  - Salience math (`recency × pain/10 × importance/10 × min(recurrence,3)`)
    documented inline so future maintainers understand the numbers
  - Reflection note must be a DURABLE LESSON sentence — transferable
    rule, not activity description (Bad: "drafted 20 slides"; Good:
    "When storyboard collides with workflow contract late, gate the
    contract check at v1 instead.")
  - Skill version bumped to 2026-04-29; manifest/index synced; 26/26
    skills lint clean; skill synced to HarnessX target manually
  - Pairs with Phase K (engagement-blank substrate for these new
    high-salience reflections to accumulate against)
- **Stage 6 — Phase K — engagement-blank semantic on fresh installs ✅ (2026-04-29)**
  - Templates committed at `harness_manager/templates/semantic/`
  - `install.py:_apply_semantic_templates()` resets LESSONS / DOMAIN_KNOWLEDGE
    / DECISIONS / lessons.jsonl on fresh install (inside not-exists guard,
    so reinstalls preserve accumulated state)
  - Smoke-tested on `/tmp/k-smoke-*`: clean
  - HarnessX target reset; pre-state archived at
    `<target>/.agent/memory/semantic/.archive/2026-04-29-phase-K-reset/`
  - Closes the "fork's harness-dev semantic leaks into engagement
    targets" issue surfaced in Phase 2 post-mortem
- **Stage 5** — capture, gap log, fix loop ✅ (post-mortem 2026-04-29)
  - `snapshot_diff.py --diff` clean: 7 added, 0 modified, 0 removed.
    All 7 are `.claude/agent-memory/*.md` for `deck-builder` and
    `delivery-lead` (project + feedback + user types). No skill self-
    rewrites; no agent edits. `in_place` evolution working as designed.
  - `HARNESS_FEEDBACK.md` empty after 130 episodes → surfaced as Gap 11
    (capture tool mechanically present, behaviorally invisible — no
    skill or protocol names the trigger for `propose_harness_fix.py`).
  - 13 dream candidates staged but all are file-write tool-use noise —
    none graduate-worthy. Net lessons promoted: 0 (correctly). Surfaced
    as Gap 9 (auto-dream signal/noise on long content sessions).
  - Workflow audit timing surfaced as Gap 10 — framework-lead's 8-
    section coverage check fired after storyboard v2, forcing 6
    structural moves; should fire as Phase 1.5 gate inside
    `consulting-deck-builder` before storyboard sign-off.
  - Gap log: 8 entries (5 from Stages 2-3 + Gap 8 closed-on-branch +
    Gaps 9/10/11 from post-mortem). Gaps 9/10/11 all open as 8.4
    candidates.

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

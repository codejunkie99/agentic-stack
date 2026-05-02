# Workspace (live task state)

> Live "where are we right now" file. Updated when we move between steps,
> hit a blocker, or change direction. For the durable history of *why* we
> did things, see `.agent/memory/semantic/DECISIONS.md`.

## Current step

**Step 8.4 — harness-learning loop (MERGED to master, PR #3 commit `c29d6b1`, 2026-05-02 reconcile)**

Branch: `feature/step-8.4-harness-learning-loop` (merged; safe to delete locally).
Spec: `docs/superpowers/specs/2026-04-30-step-8-4-harness-learning-loop-design.md`.
Plan: `docs/superpowers/plans/2026-04-30-step-8-4-harness-learning-loop-plan.md`.

Post-merge commit on master: `35e234c feat(protocol): bug-to-invariant`.

### Step 8.4 stage plan (all complete)

- **Step 8.4.5 — canonical-evidence gate ✅** (5 commits)
  - Config files (keywords + paths) + cite_canonical.py tool + 3 hooks (Layer 1/2/4) + settings wiring + DECISIONS entry. 18 tests across 4 suites.
- **Gap 11 — capture wiring (3 parts) ✅** (3 commits)
  - Part A: trigger list as `.agent/protocols/harness-fix-triggers.md` referenced from CLAUDE.md (progressive disclosure, +budget bump 500→510 lean).
  - Part B: SessionStart/SessionEnd observability hooks (mechanical signal: long session + zero captures = warn).
  - Part C: skillforge template guidance updated so new skills inherit the harness-friction trigger.
- **Gap 9 — auto_dream filter ✅** (1 commit)
  - `collapse_file_writes()` runs pre-cluster; restores canonical prefix-grouping behavior lost in Jaccard migration. 6 tests + fixture.
- **Phase H — harness-graduate.py ✅** (1 commit)
  - Cross-install lesson + DECISIONS promotion (target → fork). Interactive gate per entry, hash dedup, engagement-specificity heuristic. 3 tests + target fixture.
- **Phase O — harness_intent_audit.py ✅** (1 commit)
  - 18-checkpoint behavioral audit (5 install + 8 engagement + 4 drift + 1 anchor) made executable from `.agent/protocols/canonical-sources.md`. 5 tests + 2 fixture targets.
- **Gap 10 — consulting-deck-builder Phase 1.5 ✅** (1 commit)
  - Hand-coded workflow-contract reconciliation gate; future similar fixes route via Phase O finding → propose_harness_fix → harness-graduate.

Total: 16 commits in branch (spec+plan, requirements-dev, +14 feature commits + branch-end smoke). All tests green (36 pass); conformance audit 35/35; skill linter 27/27. Gate smoke-tested end-to-end: Layer 2 blocks/allows on citation freshness; Layer 1 keyword detection + context injection works; Layer 4 Evidence-block check works.

**Open follow-ups (post-merge, prioritized 2026-05-02):**

| # | Item | Source | Status |
|---|------|--------|--------|
| 1 | SessionStart WORKSPACE↔git reconcile hook (diff branch state vs `git log master`; warn on drift) | HARNESS_FEEDBACK 2026-05-02T13:47 (severity 5/10) | open — proposed |
| 1b | Layer 2b writer-provenance gate on `LESSONS.md` + `lessons.jsonl` — block direct edits, only allow `HARNESS_GRADUATION_WRITER=1` (graduate.py/auto-render). Block message routes to correct pipeline (`propose_harness_fix` / episodic / `graduate.py`). | HARNESS_FEEDBACK 2026-05-02 (severity 5/10) | open — proposed |
| 2 | Propagate Phase L importance/pain tuning to long-session skills (planner, document-researcher) | Step 8.4 follow-up | open |
| 3 | Stabilize `trace_check.py` then extend Phase O drift checks #14-16 | Step 8.4 follow-up; `.agent/tools/trace_check.py` exists (526 LOC, last touched `402010a`) but unstable | open |
| 4 | Extend `harness_conformance_audit.py` with citation-quote spot-check (gaming detection) + gate-config drift detection | Step 8.4 follow-up | open |
| 5 | `bcg_conditional_propagate` skill-propagation gap (doesn't propagate skills; Phase J should cover) | Step 8.3 / Phase I DECISIONS | open |
| 6 | Upstream PRs to codejunkie99: cli.py future-import fix, claude-code adapter.json SDLC entries | Step 8.2.5 sync | open |
| 7 | Step 8.5 — `install.sh --upgrade` (bidirectional fork↔target sync) | Locked decision (Step 8.4 spec) | deferred |
| 8 | Delete merged local branch `feature/step-8.4-harness-learning-loop` | git hygiene | open — trivial |

**Trace / monitoring system status**: `.agent/tools/trace_check.py` shipped 2026-04-XX (commits `eac3e34` + `402010a`). Reads `episodic/AGENT_LEARNINGS.jsonl`, applies expected-event matchers per (skill, phase). Currently wired into Phase O `harness_intent_audit.py` for drift checkpoint #14 (workflow-contract followed) but checkpoints #14-16 marked SKIP pending stabilization. Sibling: `.agent/skills/data-layer/` (cross-harness dashboard / cron monitoring / token analytics, separate concern from trace_check). Not stale — just incomplete on the Phase O integration side.

**Dropped from scope (2026-05-02):**
- Step 8.3 Phase 3 deck-render (Slide 6 metric verify, SC brand-strip, Slide 3 rubric spot-check, Slide 7 demo binary) — engagement no longer needs it.

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
  Phase 3 deck-render dropped from scope 2026-05-02 — no longer needed)
- **Stage 9 — Phase J + N1-N6 — canonical alignment + sync infra ✅ (2026-04-30)**
  - **N1**: 20 BCG agent prompts gained `## Agent-memory write discipline`
    section (per-engagement project/feedback/user typed memory files,
    matching the deck-builder dir-pattern that emerged in HarnessX run)
  - **N2**: `/regenerate-decisions` slash command at adapters/claude-
    code/commands/ — runs the canonical bootstrap prompt from source
    article line 168 (LESSONS + episodic → 3-5 significant decisions).
    adapter.json updated; smoke-tested via fresh /tmp install.
  - **N3**: consulting-deck-builder Phase 1/2/3 exit criteria now make
    `memory_reflect` a HARD GATE (was soft "REQUIRED"). Closes the
    Phase 3 reflection skip seen in HarnessX yesterday.
  - **N4**: agent-memory-templates README rewritten — dir-pattern is
    canonical; flat-file pattern is legacy/deprecated; `.claude/agent-
    memory/` correctly framed as adapter convention not canonical
    agentic-stack.
  - **N6**: 13 file-write-noise candidates in HarnessX REVIEW_QUEUE
    batch-rejected with rationale. Queue clean for tomorrow.
  - **Phase J**: `sync-target.sh` shipped. Pushes fork-side improvements
    to existing target (skills, tools, protocols, harness, context,
    workflows, AGENTS.md, claude-code commands; if bcg_adapter=enabled
    also BCG agents/commands/skills) without touching memory/agent-
    memory/output/git. Smoke-tested against HarnessX target — 11 paths
    copied, lint clean post-sync.
  - **Re-audit confirmed**: AGENT_LEARNINGS.jsonl IS the comprehensive
    activity log we needed. 188 entries, captures every tool call.
    Git-tracked memory history via dream-cycle commits. Episodic
    snapshots/ for archived entries. We HAD logs.
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

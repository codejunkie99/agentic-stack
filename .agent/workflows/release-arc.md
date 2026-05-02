---
workflow_id: release-arc
name: Release Arc — finalize, deploy, verify, document
team_structure: flat
description: Take an approved-by-reviewers branch through deploy-checklist → deploy → post-deploy verification → release notes → version bump → DECISIONS log. Standalone workflow when feature/bugfix/refactor reviewer panels passed and the next action is shipping. Most other workflows include this arc as their final phase; standalone use is for batched releases.
---

## Purpose

Convert an approved branch into a deployed release with full audit trail. Forces deploy-checklist discipline so we don't ship from "tests pass" alone (canonical: `superpowers:verification-before-completion`).

Triggers on:

- "ship it"
- "release v<X>"
- "deploy to production"
- "cut a release"
- "we're ready to ship"

## Contents

Release shipped + documented:

1. **Pre-flight** — deploy-checklist runs (all tests green, no unresolved TODOs in diff, secrets not committed, semver-grounded version bump proposed)
2. **Merge** — branch into master/main per branch protection rules
3. **Deploy** — to staging then production, OR direct to production per env policy
4. **Verify** — qa-runner exercises the deployed version against acceptance criteria (verification-before-completion canonical pattern)
5. **Release notes** — audience-sectioned: users / operators / devs
6. **Version bump** — semver: patch (bugfix), minor (feature, backward-compatible), major (breaking)
7. **DECISIONS log** — entry in DECISIONS.md summarizing the release

## Team Structure: Flat

- **release-manager** — owns the arc end-to-end. Runs deploy-checklist skill. Drives merge + deploy. Writes release notes + version bump + DECISIONS entry.
- **qa-runner** — post-deploy verification ONLY (verification-before-completion). Reports PASS or FAIL with specific failures. Cannot draft fixes during this arc; failures escalate back to engineer.

NO product-manager, NO architect, NO designer — release is a build-trust action, not a design action.

## Quality Gates

- deploy-checklist passes (all skill constraints satisfied):
  - All tests passing on the merge commit
  - No unresolved TODOs in diff
  - Secrets not committed (regex scan + .env in .gitignore)
  - Semver-grounded version bump (rationale per change type)
  - Human approval for production deploy
- Branch protection rules respected (no `--no-verify`, no `--force` on protected branches)
- Post-deploy verification: qa-runner reports PASS against ≥90% of intended changes (PRD acceptance criteria for features; regression test for bugfixes; type-design verdict for refactors)
- Release notes have non-empty Users + Operators + Devs sections (each section may say "no impact" but must be present)
- Version tag created in git matching release notes
- DECISIONS.md entry exists with date, version, summary, rollback procedure

## Output Format

- Tag: `v<X.Y.Z>` on master
- `RELEASE-NOTES.md` updated with new section at top
- `DECISIONS.md` updated with release entry
- Optional: GitHub Release / GitLab Release / etc. via `gh release` or platform-equivalent

## Iteration Discipline

After release closed:

```bash
python3 .agent/tools/memory_reflect.py "release-manager" \
  "release shipped" \
  "v<X.Y.Z> released — type=<patch|minor|major>; <n_commits_since_last>; verification=<pass|partial>" \
  --importance 9 --pain 7 \
  --note "DURABLE LESSON: <one sentence — what about this release process or content transferred? E.g. 'when DB migration in release, keep migration commit separate so rollback target is clean.'> | RELEASE TYPE: <patch|minor|major>; CONTENT: <main change>; ROLLBACK PATH: <how to revert>"
```

importance 9 × pain 7 = 63 → salience 6.3 → dominates release-cluster. Recurrence saturation graduates it when several releases ship in a window.

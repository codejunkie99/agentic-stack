---
workflow_id: project-onboarding
name: Project Onboarding — fresh repo, harness installed, first PRD seeded
team_structure: flat
description: SDLC analog of `client-onboarding`. Fires on a fresh project repo: discover what's there, install the harness, seed first-PRD scaffolding, validate gates fire. End state is a repo that can immediately run `feature-end-to-end` or `bugfix-arc`. Distinct from `client-onboarding` which is BCG-engagement-shaped.
---

## Purpose

Convert a fresh project (existing repo OR `git init` blank slate) into a harness-equipped repo ready to run any SDLC workflow. Forces discovery-first so the harness is configured for what's there, not assumed.

Triggers on:

- "onboard this project"
- "set up the harness here"
- "new project setup"
- "initialize <repo>"
- "first-time install"

## Contents

End state:

1. **Repo discovery doc** — what tech stack, what conventions, what existing tests, what missing
2. **Harness installed** — `.agent/`, `.claude/`, `CLAUDE.md` populated per `harness_manager` install path
3. **Adapter mode chosen** — `bcg_adapter: enabled|disabled` in `.agent/config.json`
4. **Initial PRD seeded** — empty `docs/prd/_index.md` + sample structure
5. **Smoke test** — gates fire correctly: write to harness-territory triggers Layer 2 citation prompt; non-territory writes pass; SessionStart hook reconciles WORKSPACE
6. **First WORKSPACE entry** — `.agent/memory/working/WORKSPACE.md` initialized with project name, current step ("onboarded"), no active branch

## Team Structure: Flat

- **product-manager** — runs discovery: reads existing README, package files, test structure, top-level dirs. Writes `docs/onboarding/YYYY-MM-DD-discovery.md` with findings. Identifies known gaps (e.g., "no tests", "TS but no tsconfig strict", "monorepo with 3 packages").
- **engineer** — runs the actual install: `harness_manager.install` against the project root with chosen adapter mode. Verifies install via `python3 .agent/tools/skill_linter.py` and `harness_conformance_audit.py`.
- **qa-runner** — smoke-tests the gates: triggers a write to a harness-territory file (without citation) and confirms block; then with citation confirms allow. Confirms SessionStart `workspace_git_reconcile.py` quiet on fresh repo.

## Quality Gates

- Discovery doc names: language(s), test framework, build tool, branch protection rules, deployment target
- `python3 .agent/tools/skill_linter.py` returns: all skills pass conformance
- `python3 .agent/tools/harness_conformance_audit.py` returns: all checks pass
- Layer 2 citation gate confirmed firing (block on no-citation harness-territory write; allow with fresh citation)
- WORKSPACE.md exists with non-empty Current Step section
- `.agent/config.json` has `bcg_adapter` field set to `enabled` or `disabled` (no missing config)
- README or AGENTS.md mentions the harness so future contributors know it's there

## Output Format

- `.agent/`, `.claude/`, `CLAUDE.md` populated
- `docs/onboarding/YYYY-MM-DD-discovery.md` — discovery findings
- `docs/prd/_index.md` — empty PRD index
- `.agent/memory/working/WORKSPACE.md` — initialized
- Smoke-test results captured in onboarding doc

## Iteration Discipline

After onboarding closed:

```bash
python3 .agent/tools/memory_reflect.py "product-manager" \
  "project onboarded" \
  "<project-name>: harness installed, adapter=<bcg|sdlc-only>, gates verified" \
  --importance 8 --pain 6 \
  --note "DURABLE LESSON: <one sentence — what about THIS project's discovery surfaced a gap in the install path or default config? E.g. 'TS-strict projects need a tsconfig parity check skipped during install or it fails on the first audit.'> | STACK: <lang>; <test-framework>; <build-tool> | KNOWN GAPS: <list — feeds first PRD>"
```

importance 8 × pain 6 = 48 → salience 4.8 (cluster-dominant on install-noise; lessons accumulate per-project for future install-path improvement).

## Notes on harness_manager invocation

For SDLC-only mode (no BCG adapter):
```bash
python3 -m harness_manager install <project-root> --adapter sdlc-only
```

For BCG-enabled (consulting + SDLC):
```bash
python3 -m harness_manager install <project-root> --adapter bcg-enabled
```

Verify post-install:
```bash
cd <project-root>
python3 .agent/tools/skill_linter.py
python3 .agent/tools/harness_conformance_audit.py
python3 .agent/harness/workspace_git_reconcile.py  # should be quiet
```

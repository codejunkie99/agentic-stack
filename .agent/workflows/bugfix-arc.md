---
workflow_id: bugfix-arc
name: Bugfix Arc — reproduce, isolate, fix, verify
team_structure: flat
description: Resolve a confirmed bug end-to-end. Uses canonical systematic-debugging discipline (reproduce → isolate → hypothesize → confirm → fix → regression-test). Distinct from `feature-end-to-end`: no PRD/ADR needed for true bugs. Use `production-incident` for live-system pages.
---

## Purpose

Take a bug from "this is broken" to "shipped fix with regression test". Forces the canonical superpowers debugging discipline so we don't ship vibes-based "I think this fixes it" patches.

Triggers on:

- "fix bug X"
- "Y is broken"
- "investigate why Z fails"
- "users report W"

Does NOT trigger on: live production pages (use `production-incident`), feature requests dressed as bugs (route back to `product-discovery-arc`).

## Contents

Bug resolved end-to-end:

1. **Repro** — reliable steps to reproduce, captured in failing test or recorded session
2. **Root cause** — named explicitly; vague "data is malformed" rejected
3. **Fix** — minimal change addressing root cause
4. **Regression test** — would FAIL on the pre-fix code, passes on post-fix
5. **Reviewer verdict** — no critical findings on the fix
6. **Released** — fix in production OR queued for next release per severity

## Team Structure: Flat

- **debug-investigator** (skill) — systematic-debugging: reproduce → isolate → hypothesize → confirm. Required for any bug whose cause isn't obvious from a stack trace. Uses `superpowers:systematic-debugging` skill.
- **engineer** — writes the fix + regression test under TDD. Test is RED before fix lands.
- **reviewer** — adversarial review of the fix with CRITICAL checklist. Veto if root cause unclear.
- **release-manager** — ships the fix per its severity (hotfix path vs queue for next regular release).

For systemic findings (3rd same-shape bug in 30 days): escalate to `bug-to-invariant` protocol (`.agent/protocols/bug-to-invariant.md`) — the FIX gets a new invariant in `LESSONS.md` or a new audit check, not just a code change.

## Quality Gates

- Repro is mechanical (test, script, or recorded session) — verbal description rejected
- Root cause statement names the line/function/condition that produced the bug
- Regression test fails on pre-fix code (verified via `git stash` round-trip or before/after run)
- Fix is the minimal change addressing root cause; no scope creep
- Reviewer found no critical findings
- For 3+ same-shape bugs: bug-to-invariant escalation triggered (LESSONS.md update or audit-check addition)

## Output Format

- Branch: `fix/<slug>` (or `hotfix/<slug>` for severity ≥ HIGH)
- Regression test committed alongside fix
- DECISIONS.md entry only if root cause reveals architectural drift (else commit message suffices)
- LESSONS.md entry only via auto_dream + graduate.py (NOT direct edit) when bug-to-invariant escalation fires

## Iteration Discipline

After fix shipped:

```bash
python3 .agent/tools/memory_reflect.py "engineer" \
  "bugfix shipped" \
  "<slug>: <severity> fix shipped — root cause: <one phrase>; regression test in <test-file>" \
  --importance 7 --pain 6 \
  --note "DURABLE LESSON: <one sentence — what class of bug is this, what would have caught it earlier?> | ROOT CAUSE: <named cause> | SHIPPED-AS: hotfix|next-release"
```

importance 7 × pain 6 = 42 → salience 4.2 (dominates fix-noise cluster). Recurrence saturation graduates the cluster when the same root cause shape recurs — exactly what bug-to-invariant protocol wants.

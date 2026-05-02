---
workflow_id: production-incident
name: Production Incident — observe, diagnose, fix or rollback
team_structure: coordinated
description: Live production system is degraded. Coordinated response: observe → diagnose → decide (hotfix vs rollback) → execute → post-incident retro. Distinct from `bugfix-arc` — this is an active page, not a queued defect. Tighter time-to-recovery focus, looser code-quality gates.
---

## Purpose

Get production back to healthy state ASAP, then run discipline post-recovery. The arc explicitly TRADES code-quality for recovery speed during the active phase, then re-applies discipline in the retro phase to prevent recurrence.

Triggers on:

- "production is down"
- "users can't <X>"
- "incident <ID>"
- "rollback the deploy"
- "hotfix needed"
- "page from <monitoring>"

## Contents

Recovery + post-incident discipline:

1. **Observe** — what's broken, what's the blast radius, what's the SLO impact
2. **Diagnose** — what likely caused this (skip-allowed if rollback is faster)
3. **Decide** — hotfix forward OR rollback. Hotfix when fix is mechanical and bounded; rollback when fix is unclear or risky
4. **Execute** — apply the chosen path; verify recovery via monitoring
5. **Post-incident retro** — root cause, timeline, what worked, what didn't, action items
6. **Bug-to-invariant** — if root cause is a class of bug we've hit before: invariant added per `.agent/protocols/bug-to-invariant.md`

## Team Structure: Coordinated

Orchestrator: **release-manager** (incident commander role; named explicitly in coord, does NOT touch code).

- **qa-runner** — confirms repro + scopes blast radius via runtime exercise. Reads logs/metrics; does not draft fixes.
- **debug-investigator** (skill) — if diagnose path chosen: rapid reproduce → isolate → hypothesize. Time-boxed (15-30 min) before rollback decision.
- **engineer** — implements hotfix if decided. SHALLOW review acceptable during active phase; full reviewer panel applied post-recovery as a follow-up commit.
- **release-manager** — owns the rollback button + the deploy of hotfix. Logs incident timeline to `INCIDENTS.md`.

## Quality Gates

### During active phase (recovery-priority)
- Recovery confirmed by qa-runner via real metric (error rate / latency / availability returned to SLO)
- Hotfix or rollback decision documented in `INCIDENTS.md` with timestamp
- NO long-running diagnose loop: if 30 min elapsed without confirmed root cause, rollback path triggers

### Post-recovery phase (discipline reapplied)
- Full reviewer panel runs on the hotfix commit (general + security + performance + type-design)
- Post-incident retro written within 48 hours: timeline, root cause, what would have caught this earlier
- Action items logged with owners + due dates
- If 3rd same-shape incident: bug-to-invariant escalation MANDATORY (LESSONS.md or audit-check)

## Output Format

- `INCIDENTS.md` entry at repo root (or per project's incident log location)
- Hotfix branch: `hotfix/<incident-id>` merged + deployed
- OR rollback documented as deploy event (no code change)
- Post-incident retro doc: `docs/incidents/YYYY-MM-DD-<slug>.md`
- DECISIONS.md entry if root cause changes architectural posture

## Iteration Discipline

After incident closed:

```bash
python3 .agent/tools/memory_reflect.py "release-manager" \
  "incident closed" \
  "<incident-id>: recovered via <hotfix|rollback> in <X> min; root cause <one phrase>" \
  --importance 10 --pain 9 \
  --note "DURABLE LESSON: <one sentence — what class of incident is this, what monitoring/gate would have caught it earlier?> | TTR: <X> min | ROOT CAUSE CLASS: <e.g. 'unbounded retry loop on transient 5xx', 'migration without backfill', 'feature flag mis-targeted'> | INVARIANT NEEDED: <yes/no — if yes, route to bug-to-invariant>"
```

importance 10 × pain 9 = 90 → salience 9.0 → graduates immediately. Production incidents are always graduate-worthy because each one teaches the harness something durable.

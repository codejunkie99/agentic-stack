# Bug → Invariant Protocol

> **When a bug is found or a test fails, do not just fix the code. Trace
> the cause, decide whether a NEW invariant (lesson, protocol gate, audit
> assertion) would catch the entire CLASS of bug, and capture the
> invariant alongside the fix.**

## Why this is a separate file

Plan-then-execute fixes the code and forgets. The canonical
agentic-stack pattern (source article lines 752-768) defines step 5 of
the universal self-rewrite hook as: *"If a constraint was violated
during execution, escalate to memory/semantic/LESSONS.md."* This file
formalizes that one-line directive into a six-step discipline so the
escalation actually happens, captures the right thing, and gets tested.

Adapted shape from cavekit's `backprop` skill
(<https://github.com/JuliusBrussee/cavekit/blob/main/skills/backprop/SKILL.md>),
evaluated 2026-05-02 (see memory entry `caveman-cavekit-adoption`). The
cavekit file format (`§V` invariants, `§B` bugs in a single SPEC.md) is
NOT adopted; the discipline is. Our equivalent of `§V` is
`.agent/memory/semantic/LESSONS.md` (invariants the fork learned) and
`.agent/protocols/` (gates the harness enforces).

## Canonical anchor

Source article lines 752-768 — universal self-rewrite hook, step 5:

> "After every 5 uses OR on any failure: ... 5. If a constraint was
> violated during execution, escalate to memory/semantic/LESSONS.md ...
> Constraint violations get escalated from the skill's local KNOWLEDGE.md
> into the global LESSONS.md. This is how a single skill's failure
> becomes system-wide knowledge."

This protocol extends the canonical escalation rule with explicit
trigger conditions, a six-step execution discipline, and a test
requirement so escalations are reproducible rather than folkloric.

Sibling protocol: `.agent/protocols/harness-fix-triggers.md` cites the
same article range and covers the HARNESS-shape side
(skill-missing-step, workflow-audit-too-late). This file covers the
BEHAVIOR-shape side (test-failed, code-did-wrong-thing,
recurring-defect-class).

## When to invoke

Trigger conditions — any one is sufficient:

1. **A test failed in CI or local verification.** Failure is direct
   evidence the spec was under-constrained.
2. **A bug surfaced in target-side use** that traces back to a fork-side
   primitive (skill, protocol, agent prompt, workflow contract).
3. **`harness_conformance_audit.py` or `harness_intent_audit.py` flagged
   drift** that wasn't already covered by an existing lesson or protocol
   gate.
4. **A reviewer caught a defect that other reviewers had also caught
   before** — recurrence is the canonical signal that a class-level fix
   is needed (the second occurrence is the threshold).
5. **A user-side incident** (the human had to intervene, redo, or
   correct an agent's output for a reason that wasn't an obvious typo).

If unsure whether bug-to-invariant or harness-fix-triggers fits, run
both. Capture is cheap; not capturing is how the fork stays broken.

## Six steps

### 1. TRACE
Read failure output, bug report, or audit finding. Locate exact
`file:line` of wrong behavior. Name the root cause in one sentence.

### 2. ANALYZE
Ask three questions in order:

- **Would a new invariant catch this CLASS of bug?** (Most common: yes.)
  An invariant is testable — encoded as a `LESSONS.md` entry with
  explicit conditions, OR a new gate in `harness_conformance_audit.py`,
  OR a new pre-commit / pre-PR check. If "yes" but the invariant cannot
  be expressed mechanically, downgrade to a lesson with explicit
  "How to apply" guidance.
- **Does an existing protocol contradict the observed behavior?** If
  yes, the protocol is wrong or silent on this case → amend the
  protocol.
- **Did we build the wrong thing?** Rare but real. If yes, the workflow
  contract or PRD is wrong → escalate to PM-flow, not engineering-flow.

If all three answers are "no" — the bug was a one-time mechanical typo
with no class — proceed to step 6 with `INVARIANT: none` noted.

### 3. PROPOSE
Draft the invariant in the form it will live. Three valid forms:

- **`LESSONS.md` entry** (most common): `pattern_id`, `claim`,
  `conditions`, `evidence` (`file:line` from step 1), `confidence`.
  Format follows existing entries in `.agent/memory/semantic/LESSONS.md`.
- **Protocol amendment**: edit an existing file under
  `.agent/protocols/` to add the missing case. Cite the bug in the
  commit message.
- **New audit assertion**: add a check to
  `.agent/tools/harness_conformance_audit.py` or
  `.agent/tools/harness_intent_audit.py` that fails when the class
  recurs.

Never modify `DECISIONS.md` by hand — canonical's
regenerated-not-edited rule (`.agent/protocols/canonical-sources.md`)
means decisions are re-derived via `/regenerate-decisions`, not
appended.

### 4. GENERATE TEST
A new invariant without a test is a lie. Add a failing test BEFORE the
fix. Naming convention: `test_<short-name>_<lesson-id-or-protocol-key>`
so the test cites which invariant it guards.

If the invariant is a protocol gate or audit assertion, the "test" is
running the audit script and watching it fail on the offending input.

### 5. VERIFY
Apply the fix. Run the new test. Must pass. Run the full relevant suite
(unit, conformance, intent audit, smoke install). Must not regress
anything else.

### 6. LOG
One commit ties together: invariant entry (lesson / protocol amendment
/ audit assertion) + new test + code fix. Commit message format:

```
fix(<scope>): <one-line cause>

invariant: <LESSON ID | protocol path | audit name>
file:line: <evidence from step 1>
```

If the invariant is severe enough to be standalone harness-feedback,
also invoke:

```bash
python3 .agent/tools/propose_harness_fix.py \
    --target <relative path of new lesson / amended protocol> \
    --reason "<bug description + cause>" \
    --change "<the invariant added>" \
    --severity <1-10>
```

## What makes a good invariant

- **Testable** in code (grep-able, assert-able, audit-script-able).
- **Scoped to a behavior**, not to a single file. "Function X must
  validate input" is bad; "All adapter entry points must validate input
  via shared validator" is good.
- **Stated positively** when possible (`MUST hold`) over negatively
  (`MUST NOT happen`). Positive invariants are easier to test.
- **References the harness surface** where it applies — name the
  protocol, the skill, the agent type, or the audit script.

**Bad lesson**: "Code should be correct."
**Good lesson**: "All `harness-graduate.py` invocations must require
`--rationale` for LESSONS appends; auto-merge is an anti-pattern."
(Already encoded at `.agent/tools/harness-graduate.py:8`.)

## When NOT to add an invariant

- The bug was a purely mechanical typo with no recurring class shape.
- The fix is a one-time migration and the surface won't recur.
- The root cause is an external dependency upgrade — note it in
  `package.json` / `requirements.txt`, not the harness.

In all three cases, still log step 6 — record that the failure mode was
considered. Future bug with same smell → grep finds the precedent.

## Boundary with `harness-fix-triggers.md`

| Surface | Protocol |
|---|---|
| Test failed because code was wrong | **bug-to-invariant** (this file) |
| Test passed but agent followed wrong workflow | **harness-fix-triggers** |
| Protocol contradicts observed behavior | both — start here, amend protocol in step 3 |
| Workflow audit fired too late | **harness-fix-triggers** |
| Reviewer caught Nth instance of same defect class | **bug-to-invariant** |
| Per-agent memory empty when it should be populated | **harness-fix-triggers** |
| `harness_conformance_audit.py` flagged drift | both |

When in doubt: test/code/audit-failure axis → bug-to-invariant;
agent-behavior/skill-shape/dispatch axis → harness-fix-triggers.

## How this protocol gets enforced

- Reviewer agents reference this protocol when finding a defect that
  fits trigger #4 (recurring class).
- The graduate pipeline (`.agent/tools/harness-graduate.py`) treats
  lessons that cite a `bug-to-invariant` step as higher confidence at
  promotion time.
- Manual: when reviewing a fix-only PR for a bug that hits ANY of the
  trigger conditions, ask: "Where's the invariant?" Absence is a
  review finding.

## Anti-patterns

- **Don't fix the code without considering the class.** Single-defect
  thinking is how the same bug recurs in a sibling surface six weeks
  later.
- **Don't add an invariant without a test.** Untested invariants drift
  silently and become stale lessons.
- **Don't write the lesson in the commit message instead of
  `LESSONS.md`.** Commit messages aren't searchable across the graduate
  pipeline; LESSONS.md is.
- **Don't skip step 1's `file:line` evidence.** Lessons without
  evidence are folklore; lessons with evidence are reproducible.

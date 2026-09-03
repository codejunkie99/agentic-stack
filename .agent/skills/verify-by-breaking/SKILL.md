---
name: verify-by-breaking
description: >
  Prove that a test, guard, or gate catches the failure it claims to catch.
  Break the thing on purpose, watch the check fail, then restore it. Use when
  you add a regression test, a safety guard, an assertion, or a validation
  gate. Also use when you say "this test covers X", "this guard prevents Y",
  or "I added a check for that". Covers the failure class that a clean build
  and green unit tests cannot see.
---

# Verify by breaking

## Rule

A test that has never failed is not a verified test. It is an assumption.

Before you report that a test protects something, remove the protection and
run the test. The test must fail, and it must name the correct problem. Then
restore the protection and run the test again. Report both results.

## Procedure

1. Write the test. Run it. It passes.
2. Break the exact thing the test protects. Change one line. Examples:
   - Delete the guard clause.
   - Change the resource key to a name that does not exist.
   - Remove the retry rule.
   - Return the wrong default.
3. Run the test again.
4. Read the result:
   - The test fails and names the problem. The test is verified. Go to step 5.
   - The test passes. The test does not measure what you think. Rewrite it.
   - The test fails with a different problem. The test is too wide. Narrow it.
5. Restore the file. Run the test again. It must pass.
6. Record both results in the report or the code comment.

## When this matters most

Use this procedure for every check in these classes:

| Class | Why a normal test run cannot see it |
|---|---|
| Safety guard before a write | The guard is skipped, not failed. Nothing throws. |
| Resource or asset lookup | A missing key uses a default value. The build stays clean. |
| Retry and idempotency rules | The rule only applies on a failure path that never runs. |
| View defects | The defect needs a loaded view. A view-model test cannot see it. |
| Configuration and startup defaults | The wrong default still starts the program. |

## The view defect class

Some defects exist only after a view loads. A view-model test cannot see them.
A clean build cannot see them. Two examples from real work:

- A mistyped resource key compiles with zero warnings. The control keeps its
  default value. The window still opens. It looks wrong.
- A radio button group raises a click event during load. A click handler then
  changes state before the user touches the control.

For this class, load the real view in a headless test. Assert the state the
user sees, not the state the view model holds.

## Report format

State the evidence, not the confidence. Write:

> Verified by removing the `IsConfirming` guard. Two tests failed. Restored.

Do not write:

> This test covers the confirmation gate.

## Failure mode this prevents

An agent adds a test, sees it pass, and reports the risk as covered. The test
asserted something that was already true for another reason. The risk stays
open, and the report says it is closed. This is worse than no test, because
it stops the next reader from looking.

## Related

- `skills/session-audit/SKILL.md` — finds the checks that do not exist yet.
- `skills/assertion-quality/SKILL.md` — judges what an assertion measures.
- `skills/tdd/SKILL.md` — the red step makes this automatic for new code. Use
  this skill for code that already exists.

---
name: verify-by-breaking
description: >
  Prove that a test, guard, or gate catches the failure it claims to catch.
  Break the thing on purpose, watch the check fail, then restore it. Use when
  you add a regression test, a safety guard, an assertion, or a validation
  gate. Also use when you say "this test covers X", "this guard prevents Y",
  or "I added a check for that". Covers the failure class that a clean build
  and green unit tests cannot see.

  Use it equally for a claim about a MECHANISM, not only about a test: any
  "X happens because Y" that is about to enter a PR description, a code
  comment, an issue register, or a report to another agent. Toggle Y, observe
  X change, restore. An explanation nobody has toggled is a guess wearing the
  clothes of a finding.
---

# Verify by breaking

## Rule

A test that has never failed is not a verified test. It is an assumption.

Before you report that a test protects something, remove the protection and
run the test. The test must fail, and it must name the correct problem. Then
restore the protection and run the test again. Report both results.

## Precondition: make the break undoable

Commit the branch before you break anything. The probe must be reversible by a
command, not by memory.

```bash
git add -A && git commit -m "<ticket> · <title>"   # or: git stash push -u
```

`git checkout <base> -- <paths>` overwrites the working file in place. Git keeps
no copy of an uncommitted change, so that probe destroys the work it was made to
prove. With a commit in place the undo is `git checkout HEAD -- <paths>`.

This applies to every multi-file probe. It also applies to a one-line edit you
intend to retype, because a build failure or a peer rebase can arrive first.

## Procedure

0. Commit the branch, or stash. See the precondition above.
1. Write the test. Run it. It passes.
2. Break the exact thing the test protects. Change one line. Examples:
   - Delete the guard clause.
   - Change the resource key to a name that does not exist.
   - Remove the retry rule.
   - Return the wrong default.
3. Run the test again. **Confirm the suite actually ran.** Read the pass and
   fail counts, not the exit state. See "The break must not stop the run".
4. Read the result:
   - The test fails and names the problem. The test is verified. Go to step 5.
   - The test passes. The test does not measure what you think. Rewrite it.
   - The test fails with a different problem. The test is too wide. Narrow it.
   - Nothing ran. The break broke the build, not the behaviour. Break it
     differently and repeat.
5. Restore the file with `git checkout HEAD -- <paths>`. Run the test again.
   It must pass. Confirm with `git status` that no probe edit remains.
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

## The break must not stop the run

A break that stops the suite from building produces no failures. "No failures"
reads like a pass at a glance, and the probe then proves nothing.

A bare `throw` at the top of a method is the common example. The compiler
reports the statements after it as unreachable, and a project that treats
warnings as errors fails to build. The suite never runs.

Put the break behind a condition the compiler cannot fold:

```csharp
if (entry is not null) throw new InvalidOperationException("injected failure");
```

Then read the counts. `0 failed` with `0 passed` is a build failure wearing the
same colour as success.

## Make the assertion carry the cause

A break proves the test fires. It does not prove the test will tell the next
reader why. Assert so that the failure message is the diagnosis.

```csharp
Assert.Null(model.ErrorText);                 // reports "Value is not null"
Assert.True(model.ErrorText is null, model.ErrorText);   // reports the text
```

The first names the assertion. The second names the cause. Use the second for
any field that holds a reason: an error message, a status, a rejected value.

Check the precondition as well as the thing you suspect. A list of causes that
all assume one earlier step succeeded will not cover the case where that step
never ran, and the symptom is identical.

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

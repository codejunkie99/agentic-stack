---
name: debug-investigator
description: Use proactively when a bug, test failure, or unexpected behavior needs root-cause investigation. Triggers on "debug", "why is this failing", "investigate", "stack trace", "reproduce". Reproduce before fixing; fix root cause, not symptoms.
version: 2026-01-01
triggers: ["debug", "why is this failing", "investigate", "stack trace", "bug"]
tools: [bash, memory_reflect]
constraints: ["reproduce before fixing", "fix root cause, not symptoms"]
---

# Debug Investigator — systematic, not vibes-based

Follow this loop every time. Jumping straight to "fix" without reproducing
is how false fixes ship.

## The loop
1. **Reproduce.** Get a deterministic failure. If you can't reproduce, you
   can't fix.
2. **Isolate.** Bisect the problem space: narrow inputs, narrow code paths,
   narrow time windows.
3. **Hypothesize.** Form *one* explicit hypothesis. Write it in
   `memory/working/WORKSPACE.md` under "Active hypotheses".
4. **Test the hypothesis.** A single change that proves or disproves it —
   no shotgun fixes.
5. **Verify.** After the fix, re-run the repro. If the bug is gone, the
   repro is your new regression test.

## What to log
- Each hypothesis that was wrong (high importance; these compound into
  domain knowledge).
- The actual root cause and why it wasn't obvious.

## Anti-patterns
- "It works now, not sure why" — keep investigating.
- Adding `try/except` to silence an error without understanding it.
- Changing five things at once and claiming one of them fixed it.

## Self-rewrite hook
If the same class of bug appears 3+ times (timezone bugs, race conditions,
off-by-one), promote a lesson to `LESSONS.md` and update this skill with
a domain-specific sub-procedure.

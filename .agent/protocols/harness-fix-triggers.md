# Harness-Fix Capture — When to Invoke

> Trigger list for `propose_harness_fix.py`. Loaded on-demand; pointed
> to from `adapters/claude-code/CLAUDE.md` "Proposing a harness fix"
> section. Closes Step 8.4 Gap 11 Part A.

## Why this is a separate file

CLAUDE.md is eager-loaded on every session start under a tight 120-line
budget (set by Step 8.3 progressive-disclosure refactor). The trigger
list is reference content — read when an agent suspects harness friction,
not on every session. Hosting it here keeps CLAUDE.md lean while making
the trigger contract explicit and reviewable.

## Canonical anchor

Source article lines 752-768 — universal self-rewrite hook template:

> "After every 5 uses OR on any failure: Read memory/episodic/AGENT_LEARNINGS.jsonl
> for recent entries tagged with this skill ... Check if any new patterns,
> recurring failures, or changed assumptions exist. If yes: Append new lessons
> to KNOWLEDGE.md ... If a constraint was violated during execution, escalate
> to memory/semantic/LESSONS.md."

This file extends that canonical pattern with explicit harness-shape
trigger conditions, applied at the operational-contract level (cross-skill)
rather than only inside individual skills.

## Triggers — invoke `propose_harness_fix.py` when ANY of these fire

Each trigger is independently sufficient. Even uncertainty about whether
the trigger applies is reason to capture — the cost of capture is one
log entry; the cost of NOT capturing is the fork can't learn.

1. **A skill is missing a step, or its phase order is wrong.**
   Example: workflow audit gate fires too late; reflection step absent
   from a skill that should self-evolve.

2. **A workflow audit fires too late (after damage was done).**
   Example: framework-lead 8-section audit ran after storyboard v2 was
   complete, forcing 6 structural moves; should have fired before v1
   sign-off (Gap 10 territory).

3. **An agent prompt didn't dispatch the right team / didn't recognize
   the right skill.**
   Example: orchestrator drafted deliverable content directly instead of
   dispatching the workflow's named team.

4. **You hit the same friction pattern twice in one session.**
   Recurrence is the canonical signal that a fix is needed; second
   occurrence is the trigger threshold.

5. **Per-agent memory is sparse where it should be populated.**
   Example: `.claude/agent-memory/<agent>/` empty after multi-turn agent
   dispatch; capture rule for when agents persist project/feedback memory
   is undefined.

6. **A protocol contradicts observed behavior, or is silent on a case
   that surfaced.**
   Example: protocol says agents must invoke X; observed behavior shows
   they don't; trigger is missing or unclear.

## Invocation

```bash
python3 .agent/tools/propose_harness_fix.py \
    --target <relative-path-of-affected-file> \
    --reason "<one or two sentences>" \
    --change "<concrete proposed change>" \
    --severity <1-10>
```

Severity guide:
- 1-3: nice-to-have polish
- 4-6: meaningful improvement
- 7-9: pattern-shaped fix that prevents recurring friction
- 10: blocker

Proposal lands in `.agent/memory/working/HARNESS_FEEDBACK.md` (gitignored
runtime artifact). The fork operator graduates approved entries via
`harness-graduate.py` (Phase H, Step 8.4).

## Capture is cheap; not capturing is how the fork stays broken

Step 8.3's HarnessX engagement ran 130 episodes across Phase 2 (deck
content build) and captured ZERO entries to `HARNESS_FEEDBACK.md` despite
multiple frictions surfacing — including the workflow audit timing issue
that became Gap 10. The capture mechanism was mechanically present but
behaviorally invisible because no trigger named the conditions for use.

This file is the trigger contract. Reference it from skills, agents,
and CLAUDE.md so the discipline is named.

---
name: planner
version: 2026-04-23
description: Use whenever a spec, requirements doc, or feature brief exists and the next action is implementation — even if the user has not explicitly said "plan". Produces a task-by-task implementation plan an engineer with zero codebase context can execute end-to-end. Triggers on PDLC handoffs (from product-discovery, requirements-writer, story-decomposer, spec-reviewer) and on direct asks like "break this down", "plan this feature", or "how should I implement this".
triggers: ["implementation plan", "break this down", "plan this feature", "task breakdown", "decompose into tasks"]
tools: [recall, git, bash]
sources:
  superpowers: writing-plans (primary)
  gstack: autoplan (reference — not pulled in v1)
preconditions: ["spec or requirements written down somewhere"]
constraints:
  - no TBD/TODO placeholders in plan body
  - every code step shows the code
  - every test step shows expected output
  - TDD ordering (test → run-fails → implement → run-passes → commit)
category: sdlc
---

# Planner

## Before acting — recall first

Run: `python3 .agent/tools/recall.py "<concise description of the plan you're about to write>"`

Present surfaced lessons in a `Consulted lessons before acting:` block. If any lesson would be violated by the intended plan, STOP and explain why before continuing.

## What a planner is

The planner turns a spec into a sequence of bite-sized tasks an engineer with zero context for this codebase can execute. You are not the engineer; you are writing the document the engineer reads. Your reader is skilled but ignorant of the tools, the domain, and the house style. The plan is the contract between spec and code.

## Destinations — what a completed plan achieves

- **A new engineer can execute it front-to-back** without clarifying questions mid-stream.
- **Every task is self-contained.** A reader can drop into task N without having executed tasks 1..N-1 and still know what to do.
- **Each step is 2–5 minutes.** "Write the failing test" is a step. "Implement the feature" is ten.
- **File structure is locked in before tasks.** The plan names every file it will create or modify with a one-line responsibility statement.
- **Code is shown, not described.** Code steps contain the actual code block. Test steps contain the actual assertion. Run steps declare the expected output.
- **Handoff mode is explicit.** The plan ends with a line naming `subagent-driven` or `inline` execution per `.agent/protocols/delegation.md`.

## Fences — what the plan must not contain

- **Placeholders:** `TBD`, `TODO`, `implement later`, `fill in details`, `handle edge cases`, `add validation`. These are plan failures, not deferrals.
- **Back-references:** "Similar to Task 4" or "like above". The reader may skip around; repeat the code.
- **Undefined names:** a method `clearLayers()` in Task 3 and `clearFullLayers()` in Task 7 is a bug in the plan, not in the code.
- **Run steps without expected output:** "Run the tests" is a trap. Every run step declares what success looks like.
- **Coverage gaps:** every spec requirement maps to at least one task. Self-review catches misses.

## Examples

**Good task (emulate):**

````markdown
### Task 2: Add `count_unique_words`

**Files:**
- Create: `src/wordcount/core.py`
- Test:   `tests/test_core.py`

- [ ] Write failing test

  ```python
  def test_count_unique_words_ignores_case():
      assert count_unique_words("The the THE") == 1
  ```

- [ ] Verify it fails

  Run: `pytest tests/test_core.py -k count_unique -v`
  Expected: FAIL — "count_unique_words not defined"

- [ ] Implement minimal code

  ```python
  def count_unique_words(text: str) -> int:
      return len({w.lower() for w in text.split()})
  ```

- [ ] Verify it passes

  Run: `pytest tests/test_core.py -k count_unique -v`
  Expected: PASS (1 passed)

- [ ] Commit

  `git commit -m "feat(wordcount): add case-insensitive unique counter"`
````

**Bad task (avoid):**

```markdown
### Task 2: Word counting logic

Implement the word counting functionality with appropriate error handling
and edge case coverage. Add tests similar to Task 1. TBD: decide on
case sensitivity.
```

Fails on: no files named, no code shown, TODO embedded, back-reference to Task 1, open decision left in the plan.

**Failure to learn from:**

A plan defined `User.email` in Task 3 and `User.email_address` in Task 8. Each task passed internal self-review because each was consistent *with itself*. The plan collapsed at integration time when the engineer tried to wire them together. **Lesson:** type and field consistency across tasks is a separate self-review pass — it isn't a property that emerges from writing each task well.

## Self-review before handoff

After the plan is written, do three passes:

1. **Spec coverage.** For each spec requirement, point to the task that implements it. List gaps.
2. **Placeholder scan.** Search for `TBD`, `TODO`, `similar to`, `appropriate`, `handle edge`, `fill in`. Rewrite every hit.
3. **Type/name consistency.** Check that method signatures, property names, and types used in later tasks match the definitions in earlier tasks.

Fix inline. No second review pass needed — just fix and move on.

## Save + handoff

Plans land at `docs/plans/YYYY-MM-DD-<feature-slug>.md` unless the project dictates otherwise. Final line of the plan names execution mode per `.agent/protocols/delegation.md` — `subagent-driven` for fresh-context-per-task, or `inline` for same-session batch execution with checkpoints.

## Self-rewrite hook

After every 5 plans this skill produces, or the first time a plan requires a mid-execution rewrite, read the last 5 planner entries from episodic memory. If better decomposition heuristics, fence patterns, or handoff formats have emerged, update this file. Commit: `skill-update: planner, <one-line reason>`.

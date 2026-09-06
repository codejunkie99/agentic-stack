# Delegation Protocol

Rules for when and how to hand work off to a sub-agent.

## When to delegate
- The task has >3 independent sub-tasks that can run in parallel.
- The task requires loading >20k tokens of context the parent doesn't need.
- The task needs a different permissions envelope (e.g., sandboxed research).

## When NOT to delegate
- The task is a single decision or a short sequence of tool calls.
- The context needed by the sub-agent overlaps heavily with the parent's.
- The sub-agent would need to write to memory that the parent is actively editing.

## Harness-specific exceptions
- An adapter may define a narrow, always-applied delegation rule for named
  specialist agents. That adapter rule overrides the general thresholds above
  only for the jobs it lists.
- Cursor's `fable-grok-subagents.mdc` uses this exception for code location,
  bounded 1-2 file edits, diff review, and test loops handled by the named
  `cavecrew-*` agents. All other work follows this protocol.

## Handoff contract
Every delegation includes:
1. **Goal** — what success looks like, in one sentence.
2. **Constraints** — what the sub-agent must not do (inherits parent permissions by default).
3. **Return format** — structured output the parent can consume.
4. **Budget** — max tokens, max tool calls, max wall time.

## Memory isolation
- Sub-agents read shared semantic + personal memory.
- Sub-agents write to their own `memory/episodic/` namespace.
- On return, the parent decides which sub-agent learnings to merge.

## Anti-patterns
- "Fan out 10 sub-agents and hope" — each delegation costs context setup.
- Sub-agents that modify the parent's `working/WORKSPACE.md` directly.
- Recursive delegation without a depth limit (hard-cap at 3 levels).

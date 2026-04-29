---
name: git-proxy
description: Use proactively when work involves git operations with safety constraints. Triggers on "commit", "push", "branch", "merge", "rebase". Constraints: never force push to main; run tests before push.
version: 2026-01-01
triggers: ["commit", "push", "branch", "merge", "rebase", "pull request", "PR"]
tools: [bash]
preconditions: [".git exists"]
constraints: ["never force push to main", "never force push to protected branches", "run tests before push"]
---

# Git Proxy — all git operations with a safety net

Handle git operations consistently. The fences (`constraints` above) are
enforced by the `pre_tool_call` hook; this file tells the agent what good
behavior looks like within those fences.

## Commit
- Stage specific files, not `git add -A` (avoids capturing secrets).
- Write messages that explain *why*, not *what*.
- Reference the task or issue if one exists.

## Push
- Run tests first. If tests aren't present, say so explicitly.
- Never force-push to a protected branch. The pre-call hook will block this
  even if you try.
- Prefer `--force-with-lease` over `--force` on feature branches.

## Branch / merge / rebase
- Rebase feature branches on `main` before opening a PR.
- Resolve conflicts manually; do not `-X theirs` or `-X ours` without thinking.
- Merge via PR with review, not directly on the command line.

## Self-rewrite hook
After every 5 uses, re-read `KNOWLEDGE.md` and the last 10 git-proxy
episodic entries. If a new failure mode has appeared, append a heuristic
to `KNOWLEDGE.md`. If a constraint was violated, escalate to `LESSONS.md`.

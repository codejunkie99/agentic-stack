# Agent Infrastructure

This folder is the portable brain. Any harness (Claude Code, Cursor, Windsurf,
OpenCode, OpenClaw, Hermes, standalone Python) can mount it and get the
same memory, skills, and protocols.

## Memory (read in this order)
- `memory/personal/PREFERENCES.md` — stable user conventions
- `memory/working/WORKSPACE.md` — current task state
- `memory/working/REVIEW_QUEUE.md` — pending candidate lessons waiting for you
- `memory/semantic/DECISIONS.md` — past architectural choices
- `memory/semantic/LESSONS.md` — distilled patterns (rendered from `lessons.jsonl`)
- `memory/episodic/AGENT_LEARNINGS.jsonl` — raw experience log (top-k by salience)

## Review Queue (host-agent responsibility)

Candidate lessons are clustered + staged automatically by `memory/auto_dream.py`.
The host agent — you — does the actual review using the CLI tools below.

Check `memory/working/REVIEW_QUEUE.md` at session start. If pending > 10 or
oldest staged > 7 days, review before substantive work.

Workflow:
1. `python .agent/tools/list_candidates.py` — pending candidates, sorted by priority
2. For each: decide accept / reject / defer based on claim, evidence_ids,
   cluster_size, and any contradictions with existing LESSONS.md
3. `python .agent/tools/graduate.py <id> --rationale "..."` to accept
4. `python .agent/tools/reject.py <id> --reason "..."` to reject
5. `python .agent/tools/reopen.py <id>` to requeue a previously-rejected item
6. Review in a **batch**, not one-by-one — cross-candidate contradictions
   only surface when you see multiple at once.

The heuristic prefilter in `memory/validate.py` has already dropped obvious
junk (too-short claims, exact duplicates). Everything staged needs real
judgment. Rationale is required for graduation — rubber-stamped promotions
are the exact failure mode this layer prevents.

## Skills
- `skills/_index.md` — read first for discovery
- `skills/_manifest.jsonl` — machine-readable skill metadata
- Load a full `SKILL.md` only when its triggers match the current task
- Every skill has a self-rewrite hook; invoke it after failures

## Protocols
- `protocols/permissions.md` — read before any tool call
- `protocols/tool_schemas/` — typed interfaces for external tools
- `protocols/delegation.md` — rules for sub-agent handoff

## Rules
1. Check memory before decisions you have been corrected on before.
2. If `REVIEW_QUEUE.md` shows backlog past threshold, handle it before the new task.
3. Log every significant action to `memory/episodic/AGENT_LEARNINGS.jsonl`
   via `.agent/tools/memory_reflect.py`.
4. Update `memory/working/WORKSPACE.md` as you work; archive on completion.
5. Never hand-edit `memory/semantic/LESSONS.md` — it's rendered from
   `lessons.jsonl`. Use `graduate.py` / `reject.py` instead.
6. Follow `protocols/permissions.md`. Blocked means blocked.
7. When a self-rewrite hook fires, propose conservative edits only.
8. The harness is dumb on purpose. Reasoning lives in skills + the host agent.

# Agent Infrastructure

This folder is the portable brain. Claude Code gets the full integration
because its hook lifecycle can enforce pre-tool permissions and log
post-tool actions. Other adapters can mount the same files for memory and
skills, but prompt-only harnesses are best-effort and cannot provide the
same hard permission gate.

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

## Design Systems
- If the project root contains `DESIGN.md`, treat it as the source of truth
  for visual design decisions and load `skills/design-md/SKILL.md` when a
  task mentions `DESIGN.md`, Google Stitch, design tokens, design system,
  or visual design. (The skill's `preconditions` field gates loading on
  `DESIGN.md` actually existing — keep this rule in lockstep with
  `skills/_manifest.jsonl` to avoid same-task / different-harness drift.)
- Prefer exact tokens, component rules, and design rationale from
  `DESIGN.md` over invented colors, typography, spacing, shadows, or motion.
- Do not modify `DESIGN.md` unless the user explicitly asks for a design
  system change; implementation work consumes the contract, it doesn't
  edit it.

## Protocols
- `protocols/permissions.md` — read before any tool call
- `protocols/tool_schemas/` — typed interfaces for external tools
- `protocols/delegation.md` — rules for sub-agent handoff
- `tools/ztk.py` — host-neutral policy CLI; use
  `python3 .agent/tools/ztk.py exec -- <command>` when the host does not
  provide a native pre-tool hook for a policy-covered shell command.

## Host-agent CLI tools (in `tools/`)
Daily driver, highest-leverage first:
- `recall.py "<intent>"` — surface graduated lessons relevant to what
  you're about to do. **Run before deploy / migration / timestamp / debug /
  refactor work.** This is how lessons cross harnesses.
- `learn.py "<rule>" --rationale "<why>"` — teach the agent a new lesson
  in one shot (stage + graduate + render). For rules you already know.
- `show.py` — one-screen dashboard of brain state: episodes, candidates,
  lessons, failing skills, activity graph.
- `data_layer_export.py` — local cross-harness activity/data-layer export:
  agent events, cron timelines, tokens/cost estimates, categories,
  harness mix, `dashboard.html`, and `daily-report.md`.
- `data_flywheel_export.py` — local export of approved, redacted runs into
  trace records, context cards, eval cases, training-ready JSONL, and
  flywheel metrics. It does not train models or call APIs.
- `list_candidates.py` / `graduate.py` / `reject.py` / `reopen.py` — review
  protocol for patterns the dream cycle has staged.
- `memory_reflect.py <skill> <action> <outcome>` — log a significant event.

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

# Project Instructions (Claude Code)

This project uses the **agentic-stack** portable brain. All memory,
skills, and protocols live in `.agent/`.

## Session start — read in this order

1. `.agent/AGENTS.md` — map of the whole brain
2. `.agent/config.json` — adapter + active-client flags
3. `.agent/memory/personal/PREFERENCES.md` — how the user works
4. `.agent/memory/working/REVIEW_QUEUE.md` — pending lesson candidates
5. `.agent/memory/semantic/LESSONS.md` — what we've already learned
6. `.agent/protocols/permissions.md` — hard constraints
7. `.agent/context/_index.md` — generic consulting frameworks index
   (load specific files only when an analytical task triggers them)

## Conditional mounts (based on `config.json`)

- If `bcg_adapter == "enabled"`: read `adapters/bcg/README.md` —
  it indexes BCG-specific protocols, frameworks, firm context, and
  slash commands. Load specific BCG files only when their domain
  surfaces. BCG context is **ambient** when this flag is on — no
  need to annotate tasks with "this is BCG."
- If `active_client` is non-null: read **only**
  `.agent/memory/client/<active_client>/INDEX.md` and `briefing.md`.
  Everything else under `client/<active>/` (`summaries/`,
  `raw-uploads/`, per-client memory) loads on-demand only — same
  progressive-disclosure pattern as `.agent/skills/_index.md`.
  Onboard new engagements via the `client-onboarding` skill.

## Recall before non-trivial action

For tasks involving **deploy / ship / release / migration / schema
change / supabase / edge function / timestamp / timezone / date /
failing test / debug / investigate / refactor**, run recall FIRST:

```bash
python3 .agent/tools/recall.py "<one-line description>"
```

Show output in a `Consulted lessons before acting:` block. If a
surfaced lesson would be violated, stop and explain why.

## While working

**Skills.** Read `.agent/skills/_index.md` and load the full
`SKILL.md` for any skill whose triggers match. Skills carry
constraints the permissions file doesn't cover.

**Workspace.** Update `.agent/memory/working/WORKSPACE.md` when
you start a task, change hypothesis, or finish/abandon work.

**Brain state.** `python3 .agent/tools/show.py` for a one-screen
dashboard.

**Logging significant events.** For deploys, incidents,
architectural decisions, non-obvious constraints — call
`memory_reflect.py` explicitly. See `docs/memory-reflection.md`
for the when/how guide and importance-level rubric.

**Teaching a rule directly.** When you already know the lesson,
`python3 .agent/tools/learn.py "<rule>" --rationale "<why>"` —
stages + graduates in one shot.

## Proposing a harness fix from inside an install

If you encounter a bug in a harness-territory file (CLAUDE.md,
`.claude/agents/*`, `.agent/harness/*`, `.agent/protocols/*`,
`.agent/AGENTS.md`, `.claude/settings.json`), do **not** edit it
— those paths are write-protected. Capture the proposal:

```bash
python3 .agent/tools/propose_harness_fix.py --target <path> \
    --reason "<one or two sentences>" \
    --change "<concrete proposed change>" --severity 7
```

Proposal lands in `.agent/memory/working/HARNESS_FEEDBACK.md`. Keep
working; the proposal is graduated to the fork in a separate
ritual. Same mechanism for `skill_evolution_mode: "propose_only"`.

## Rules that override all defaults

- Never force push to `main`, `production`, or `staging`.
- Never delete episodic or semantic memory entries — archive them.
- Never modify `.agent/protocols/permissions.md` — humans only.
- Never hand-edit `.agent/memory/semantic/LESSONS.md` — use
  `graduate.py`.
- Do not edit harness-territory files in installs — use
  `propose_harness_fix.py` instead.
- If `REVIEW_QUEUE.md` shows pending > 10 or oldest > 7 days,
  review candidates before substantive work.

# Canonical Sources Protocol

> **When working on harness primitives in this fork, default to canonical
> agentic-stack teaching. When testing primitives in target installs, audit
> intended-vs-actual behavior, not just install-state correctness.**

This protocol exists because Step 8.3's audit revealed silent drift between
what we INTENDED and what was ACTUALLY happening. We invented continuous-
DECISIONS-write practice that wasn't in the canonical contract; we treated
DOMAIN_KNOWLEDGE.md as having a write-discipline that didn't exist; we
shipped agent-memory dirs without documenting they were our extension. The
fix wasn't more code — it was reading the source article carefully and
recalibrating against canonical.

This file makes that habit deliberate, not accidental.

## Sources of truth — primary, secondary, tertiary

**Primary (always cite first):**
1. **`examples/agentic-stack-resource/agentic-stack-source-article.txt`** —
   the canonical agentic-stack design article. File tree, memory layout,
   read order, rules, dream cycle, salience formula, regenerate-decisions
   bootstrap prompt all live here. This is the spec. When in doubt, this
   wins.
2. **Upstream `codejunkie99/agentic-stack`** on GitHub — the reference
   implementation. Tagged releases through v0.11.2 + ongoing master. Use
   for code-level questions where the article is silent. Run upstream-sync
   weekly (cron `ba87d58c`, Mon 9:13 local).

**Secondary (use for pattern inspiration, not contract):**
3. **`garrytan/gstack`** — Garry Tan's Claude Code framework. 6 personas-
   as-slash-commands, /office-hours + /ship workflow shape, Confusion
   Protocol. Useful when designing skill-as-workflow patterns.
4. **`garrytan/gbrain`** — Garry's brain layer. "Thin harness, fat skills"
   articulation. Brain-first lookup, sub-agent delegation, durable job
   system. Useful for memory + delegation pattern inspiration.

**Tertiary:**
5. The fork's own DECISIONS.md — past architectural choices, including
   alternatives considered. Read before re-debating settled questions.
6. The fork's CLAUDE.md and AGENTS.md — current operational contract.

## When to consult sources — checklist for harness primitive work

Before editing ANY file in `.agent/skills/`, `.agent/protocols/`,
`.agent/harness/`, `.agent/AGENTS.md`, `.agent/workflows/`,
`adapters/*/agents/`, `adapters/*/skills/`, `adapters/*/commands/`,
`harness_manager/`:

1. **Does the canonical article cover this primitive type?** Read the
   article section relevant to the change. (Memory, Skills, Protocols,
   Rules, harness/hooks, auto_dream, salience, conductor — all sectioned.)
2. **Does upstream codejunkie99 have a current pattern?** `git fetch
   origin master` against the upstream remote and check the equivalent
   path. If our shape diverges, document why in DECISIONS.md.
3. **Does gstack or gbrain solve a similar problem?** Read the relevant
   skill/protocol there. Don't copy verbatim — adapt the pattern.
4. **What does the fork's own DECISIONS.md say?** Have we already settled
   this question? Re-debating settled questions is the failure mode
   DECISIONS.md exists to prevent.
5. **Are we extending canonical or inventing new?** If extending —
   document the extension in DECISIONS.md and label adapter-specific
   primitives as such (e.g., `.claude/agent-memory/` is OUR extension,
   per Step 8.3 Phase L re-audit).

## Audit template — intended vs actual behavior in target installs

After installing primitives into a target and running them, audit BEFORE
declaring the work done. Don't conflate "install state correct" with
"primitives are being used correctly." Step 8.3 missed this for an entire
engagement.

**Audit checklist:**

```
INSTALL STATE (not enough alone):
  [ ] All declared files present at expected paths
  [ ] Linter passes (if applicable)
  [ ] Conformance audit passes (eager-load budget + parity)
  [ ] Smoke install in /tmp succeeds

ENGAGEMENT-TIME BEHAVIOR (the real audit):
  [ ] Episodic memory captured the engagement events
      (`tail .agent/memory/episodic/AGENT_LEARNINGS.jsonl`)
  [ ] Working memory updated as agents ran (WORKSPACE.md mtime)
  [ ] Per-agent memory written by each dispatched agent
      (`ls .claude/agent-memory/<agent>/`)
  [ ] Phase-exit reflections fired at intended importance/pain
      (grep episodic for skill-name + importance >= 8)
  [ ] Dream cycle ran and staged candidates
  [ ] Candidates are LESSON-shaped, not activity-shaped
      (sample top 3 — if claim is "Wrote X.md (N lines)", that's noise)
  [ ] Semantic memory updated where intended (LESSONS via dream cycle;
      DECISIONS via /regenerate-decisions; never by hand)
  [ ] propose_harness_fix.py invoked when friction surfaced
      (if HARNESS_FEEDBACK.md is empty after a long session, agents
      didn't recognize harness-shape friction — that's a discipline gap)

DRIFT DETECTION:
  [ ] Did agents follow the workflow contract or ad-hoc dispatch?
      (trace_check.py against the workflow file)
  [ ] Did skills fire in the order their hand-offs prescribed?
  [ ] Did any agent edit files outside its declared output_paths?
  [ ] Did any harness primitive get used in an unexpected way?
```

If anything fails, that's a finding. Either:
- (a) The primitive isn't well-specified — fix the spec, retest
- (b) The agent prompt doesn't name the trigger explicitly — add it
- (c) The workflow contract is too implicit — make it explicit
- (d) Canonical contract was misread — recalibrate

Log every finding in `docs/superpowers/plans/<step>-gap-log.md`.

## Anti-patterns — what we've already learned NOT to do

- **Don't invent practice without canonical comparison.** Step 8.3 had us
  writing DECISIONS.md continuously per-step before re-reading the article
  showed canonical is sporadic-regenerate. We rebuilt to canonical.
- **Don't assume "install state correct" = "behavior correct".** They
  can diverge silently for an entire engagement.
- **Don't add primitives without explicit triggers in agent prompts.**
  Mechanism-without-trigger is invisible to agents. (`.claude/agent-memory/`
  was empty for 5 of 7 agents in HarnessX because no prompt named the
  trigger.)
- **Don't conflate canonical with adapter-specific.** `.claude/agent-
  memory/` is OUR extension, not canonical. `.agent/workflows/` is OUR
  extension. Document these as such so future operators don't think
  they're upstream-required.

## How this protocol gets enforced

- Loaded at session start via AGENTS.md reference.
- Auto-memory entry `harness_dev_canonical_default.md` reminds the agent
  to consult sources before harness-primitive work.
- Pre-commit hook `harness_conformance_audit.py` checks eager-load budget
  + parity vs upstream and warns on drift.
- Manual: when reviewing a harness change, ask: "Did the change cite the
  source article or upstream?" If not, that's a review finding.

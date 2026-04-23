# Domain Knowledge — Agentic Stack Architecture

> Stable facts about the agentic-stack architecture, captured while learning.
> Format adopted from gbrain: "compiled truth" at top (current best understanding,
> rewritten as evidence changes); "timeline" at bottom (how we got here).
>
> Purpose: the next session — or the next agent — can load this file and
> understand the system without re-reading the whole codebase.

---

## Compiled truth (current)

### Top-level thesis
The harness is dumb; the knowledge is in files. Memory, skills, and protocols
live in a portable `.agent/` folder. Swap harnesses (Claude Code → Cursor →
Python), keep the brain.

### Module 1: AGENTS.md
`AGENTS.md` tells any harness (Claude Code, Cursor, Python) exactly what to load
from this brain and in what order — so the agent never has to discover the tree
on its own — and its 8 invariant rules (e.g., never hand-edit `LESSONS.md`) hold
regardless of which harness mounts it. When it drifts from disk — say I add
`memory/client/acme/` mid-engagement but forget to update this file — the next
session starts with the stale map, never sees Acme's context, and silently
answers from a generic mental model when I needed client-specific work.

### Module 2: Memory — four layers with distinct retention policies
The four layers split on two complementary axes: **what question each answers**
and **who writes it**.

| Layer | What question? | Who writes |
|---|---|---|
| `personal/` | Who I am | Me, hand-edited |
| `working/` | What I'm doing right now | Me, updated per task; archived on completion |
| `episodic/` | What happened | Post-tool hook (auto) + me via `memory_reflect.py` |
| `semantic/` | What I know | Dream cycle + me via `graduate.py` / `learn.py` — `LESSONS.md` is rendered from `lessons.jsonl`, never hand-edited |

**Rule for where new info goes:** ask *"what question does this answer?"* first.
Engagement-independent about me → `personal/`. Client-specific, not generalizable
→ `client/<id>/` (Phase 2). Raw event with timestamp → `episodic/`. Generalizable
lesson I'm confident in → `semantic/` via `learn.py` (active, after one event) or
`graduate.py` (passive, after the dream cycle clusters ≥2 similar events).

### Module 3: Skills — progressive disclosure
**Why progressive disclosure exists.** Full skill bodies are ~2-3K tokens each.
At 20 skills (end of Phase 2), loading every `SKILL.md` upfront costs ~50K —
a quarter of a 200K context window gone before the user types. Worse: the
Anthropic prompt cache has a ~5 min TTL, so 5-7 session boots a day means
re-ingesting this every boot — latency + dollar cost multiply. Avid hit the
wall at 30 skills / 90K. Fix: load the skill **index** only, lazy-load the full
`SKILL.md` when a trigger matches the current task. Architectural discipline —
works at any context-window size.

**Three files, two consumers.**
- `skills/_index.md` — human-readable registry (names + triggers + one-liner).
  **The LLM reads this** to decide which `SKILL.md` to pull next.
- `skills/_manifest.jsonl` — same information, structured. **Python tools read
  this** — `show.py`, `skill_loader.py`, sync crons that need `triggers[]` /
  `tools[]` / `constraints[]` / `version` / `category` as structured fields,
  not regex-parsed markdown.
- `skills/<skill>/SKILL.md` — the full body (role framing + examples +
  constraints + self-rewrite hook). Loaded only on trigger match.

### Module 4: Protocols — deterministic enforcement
**Key property:** protocols are enforced architecturally, not by model judgment.
Hooks are deterministic Python that run in the harness *before* (and *after*)
every tool call — independent of what the model decides.

**What runs, when:**
- `pre_tool_call.py` — **before** any tool call. Reads `tool_schemas/<tool>.schema.json`
  (checks `blocked_targets`, `requires_approval`) and `permissions.md`
  (keyword-matches `## Never allowed` rules). Returns `allowed` / `approval_needed`
  / blocked — blocked calls never execute.
- `post_execution.py` — **after** every action. Appends a structured entry to
  `episodic/AGENT_LEARNINGS.jsonl` with `importance`, `pain_score`, `reflection`,
  `source`.
- `on_failure.py` — **on failure**. Scores pain + counts recent failures; fires
  the skill-rewrite flag after 3 failures in 14 days.
- `claude_code_post_tool.py` — v0.8.0 Claude Code PostToolUse hook. Parses
  Claude Code's JSON payload, scores `importance` by domain (deploy/migrate = 9,
  edit = 5…) using universal + user-configurable patterns (`hook_patterns.json`),
  detects wrapper-masked failures (`|| true`), writes reflections the dream
  cycle can cluster on.

**Why it matters.** Architectural enforcement lets me make a safety claim that
holds regardless of how the agent gets used — "the system cannot force-push to
protected branches, cannot hit non-approved domains, cannot delete outside
`memory/working/`." Advisory rules in `CLAUDE.md` can only claim "the model
usually respects this." On a live BCG engagement, only the first claim survives
a risk review.

### Module 5: Tools — the review surface
**The `tools/` directory is where the human operates the memory system.**
`auto_dream.py` STAGES candidates; no code path auto-promotes. Promotion is
always a human act.

**Lesson lifecycle:**
- `list_candidates.py` — pending candidates, sorted by priority (backlog age × salience)
- `graduate.py <id> --rationale "..."` — promote. **`--rationale` is `required=True`**, not optional
- `reject.py <id> --reason "..."` — reject with reason
- `reopen.py <id>` — re-queue a previously-rejected candidate (new evidence arrived)
- `learn.py "<rule>" --rationale "..."` — v0.8.0 one-shot stage+graduate for high-conviction rules

**Visibility / recall:**
- `recall.py "<intent>"` — surface graduated lessons relevant to a pending action (v0.8.0 "recall first" pattern)
- `show.py` — one-screen dashboard of brain state
- `memory_reflect.py <skill> <action> <outcome>` — log a significant event manually

**Why `--rationale` is required.** Rubber-stamped promotions are the failure
mode this layer exists to prevent. The field forces the reviewer to **prove
generalizability** — not tag client-specificity. A good rationale has four
parts: (1) the pattern, (2) **mechanism** (why it holds), (3) where it
generalizes, (4) where it does NOT. The "does NOT" bound is the discipline —
it prevents the lesson from being applied where it breaks. If writing the
rationale is easy ("looks good" / "for client A"), the content probably isn't
a semantic lesson — it's either a preference (→ `personal/PREFERENCES.md`) or
a client-specific fact (→ `client/<id>/`). **Discovered patterns graduate here;
declared rules don't.**

**Contrast with auto-promotion.** `auto_dream.py` clusters episodes and stages
candidates when `cluster_size ≥ 2` and `canonical_salience ≥ 7.0`, but stops
there. Auto-promotion was deliberately rejected because patterns from one
project may not generalize — the rationale field is where the human judges
generalizability candidate-by-candidate. Phase 2 may extend this with a
`--cross-client-safe` flag or rationale-keyword check for the DS team layer.

### Module 6: Harness — thin conductor
**Claude Code IS the conductor — so `conductor.py` is ignored.** The
standalone-Python `conductor.py` does three things: `build_context()`,
`call_model()`, and `log_execution()`. Claude Code replaces all three
natively — its own context loader (CLAUDE.md + skill injection + conversation
history), its own API layer (the CLI itself), and PostToolUse hooks that call
`log_execution()` indirectly. Same three responsibilities, different
implementation — swap Claude Code ↔ Cursor ↔ standalone Python and reasoning
stays intact because it lives in `skills/` + the host agent, not the conductor.
AGENTS.md rule #8: *"The harness is dumb on purpose."*

**What IS load-bearing for Claude Code users (with triggers):**

| File | Triggered by |
|---|---|
| `hooks/claude_code_post_tool.py` | **PostToolUse hook** in `adapters/claude-code/settings.json` — fires after every Claude Code tool call (Bash, Edit, Write, etc.) |
| `hooks/post_execution.py` | Called by `claude_code_post_tool.py` on success; also by subagents via `memory_reflect.py` |
| `hooks/on_failure.py` | Called by `claude_code_post_tool.py` on failure (non-zero exit, stderr errors, interrupted flag) |
| `hooks/pre_tool_call.py` | Called programmatically to gatekeep permissions; wireable as a PreToolUse hook |
| `salience.py`, `text.py`, `hooks/_provenance.py` | Imported helpers — run whenever their callers run (`cluster`, `promote`, `recall`, the post-tool hook) |

**The composability surface.** Only ONE file (`claude_code_post_tool.py`) is
directly wired to Claude Code's event system; everything else is either
imported by that file or invoked by subagents. This tiny wire-point is what
makes the harness swappable: porting to Cursor / Hermes / standalone Python
means writing one new hook binding that forwards to the same core logic. In
Phase 2, `adapters/bcg/` will likely add a second hook binding alongside the
core one (e.g., compliance-archive routing for `client/<id>/` writes) —
composing, not replacing.

### The six feedback loops
**What makes it compound vs. static.** Each session's episodes become candidate
patterns via the dream cycle. Each graduated lesson informs future sessions via
recall. Each failure pushes a skill toward evolution. Each upstream change
becomes reviewable. Nothing is lost; everything accumulates selectively. Over
four-week BCG engagements, the compounding IS the mechanism for
cross-engagement learning — the second engagement starts with the first's
filtered lessons preloaded.

**Loop #4 (recall) as illustration.** **Trigger:** the agent reads v0.8.0's
`CLAUDE.md`, sees a task keyword (deploy, migration, schema change, timestamp,
debug, refactor, etc.), and runs `recall.py "<intent>"` *before* acting.
**Matching:** `recall.py` tokenizes the intent, tokenizes every accepted
lesson's `claim` + `conditions`, and scores by lexical overlap — `conditions`
weighted 2× because it's the explicit trigger vocabulary. **Output:** top-*k*
matches are presented in a `Consulted lessons before acting:` block —
agent-authored text, **advisory not hook-enforced** (the asymmetric cousin of
`pre_tool_call.py`). **Impact:** the agent now acts with prior knowledge in
context; if a surfaced lesson would be violated, it pauses and explains. This
is the loop that turns accumulated lessons into visible behavior change —
without it, lessons exist but never influence anything.

**The other five loops** (named for reference, not walked through):
1. Post-tool → episodic (every tool call logged via `claude_code_post_tool.py`).
2. Episodic → dream → stage (`auto_dream.py` clusters by Jaccard; stages on `cluster_size ≥ 2` AND `canonical_salience ≥ 7.0`).
3. Stage → graduate → semantic (human-in-the-loop via `graduate.py --rationale`; rubber-stamp filter).
5. Failure → rewrite (≥3 failures in 14d fires the skill-rewrite flag at `pain_score=10`).
6. Upstream → sync → staged review (nightly `upstream_sync.py` / `superpowers_sync.py` / `gstack_sync.py`; stage-only, never auto-apply).

---

## Timeline

### 2026-04-18 — Initial scaffold
Pulkit read @Av1dlive's article "The Agentic Stack" and walked through the
repo module by module. Established fork at github.com/pulkittalwar/agentic-stack.
Created this file using gbrain compiled-truth + timeline format. Planned 10-step
buildout toward a PDLC-SDLC team in Claude Code (see plan file).

### 2026-04-22 → 2026-04-23 — DOMAIN_KNOWLEDGE.md complete (all 7 TODOs filled)
Filled all seven sections of the compiled-truth layer via Socratic Q&A in
Claude Code: Modules 1 (AGENTS.md as harness-agnostic map + constitution),
2 (memory four layers — what-question + who-writes dual lens),
3 (skills / progressive disclosure — token + cache economics),
4 (protocols — deterministic enforcement, architectural claim vs. advisory),
5 (tools — review surface, `--rationale` as generalizability filter,
discovered-vs-declared test),
6 (harness — Claude Code IS the conductor; one hook-wire-point as the
composability surface), and the feedback-loops section (six loops named;
loop #4 recall walked through; compound-vs-static principle articulated with
BCG cross-engagement framing). v0.8.0 baseline merged from upstream;
D1/D2/D3 locked (single fork + gitignored `memory/client/<id>/`; hybrid core
+ `adapters/bcg/`; all four deliverables — Phase 3 non-optional). Also
surveyed gstack ≥ v1.0.0.0 — bootstrap-target note added to plan, convergence
on host-adapter pattern (Hermes + GBrain hosts, brain-first resolver) noted
as architectural validation. Completes Step 2 of the 10-step plan. Next:
Step 3 (PREFERENCES + permissions + 4 forward-compat hooks).

### [future entries]
- When something above is wrong, rewrite the compiled-truth section and add
  a timeline entry explaining what changed.
- When a non-obvious lesson surfaces (e.g., "auto_dream.py doesn't commit git
  because hosts can't be trusted to do so unattended"), add it.

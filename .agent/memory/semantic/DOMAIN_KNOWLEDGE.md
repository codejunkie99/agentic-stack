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
<!-- TODO (Pulkit): why does graduate.py require --rationale? What failure mode
     does this prevent? (Hint: "rubber-stamping".) How does this differ from
     auto-promoting candidates? -->

### Module 6: Harness — thin conductor
<!-- TODO (Pulkit): why do Claude Code users mostly ignore conductor.py? Which
     pieces of harness/ DO matter for Claude Code users, and why? -->

### The six feedback loops
<!-- TODO (Pulkit): in your own words, what makes this system "compound" instead
     of "stay static"? Name any ONE of the six loops and explain the cycle. -->

---

## Timeline

### 2026-04-18 — Initial scaffold
Pulkit read @Av1dlive's article "The Agentic Stack" and walked through the
repo module by module. Established fork at github.com/pulkittalwar/agentic-stack.
Created this file using gbrain compiled-truth + timeline format. Planned 10-step
buildout toward a PDLC-SDLC team in Claude Code (see plan file).

### 2026-04-22 — Modules 1–4 filled
Filled Modules 1 (AGENTS.md as harness-agnostic map + constitution),
2 (memory four layers — what-question + who-writes dual lens),
3 (skills / progressive disclosure — token + cache economics), and
4 (protocols — deterministic enforcement, architectural claim vs. advisory) via
Socratic Q&A in Claude Code. Modules 5–7 remain TODO. v0.8.0 baseline merged
from upstream; D1/D2/D3 locked (single fork + gitignored `memory/client/<id>/`;
hybrid core + `adapters/bcg/`; all four deliverables — Phase 3 non-optional).

### [future entries]
- When something above is wrong, rewrite the compiled-truth section and add
  a timeline entry explaining what changed.
- When a non-obvious lesson surfaces (e.g., "auto_dream.py doesn't commit git
  because hosts can't be trusted to do so unattended"), add it.

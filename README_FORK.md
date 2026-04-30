# README_FORK — Pulkit's user guide for this fork

This is **your** operator's manual for using the agentic-stack fork on real
work. Different from `README.md` (the canonical agentic-stack README, kept
for upstream parity) — this file says **how YOU use this**.

> Audience: you, the BCG Principal who owns this fork. Concrete commands,
> decision points, and "when do I do what" guidance.

---

## 1. What this fork is

A portable agent brain (`.agent/`) that drops into any project directory
and gives Claude Code consistent memory, skills, protocols, and consulting
discipline. The fork extends the upstream `codejunkie99/agentic-stack` with:

- **5 SDLC agents** (architect, engineer, product-manager, release-manager,
  reviewer) for build-a-product work
- **20 BCG agents** (case-analyst, framework-lead, deck-builder, delivery-
  lead, partner-strategy, partner-analytics, principal-delivery, program-
  director, etc.) for consulting work, gated by `bcg_adapter: "enabled"`
- **26 skills**, including the `consulting-deck-builder` 3-phase workflow
  and the vendored BCG `deckster-slide-generator` for .pptx production
- **6 deliverable workflows** (situation assessment, issue tree, mid-case
  findings, final-recommendations deck, etc.)
- **`sync-target.sh`** for pushing fork-side improvements to existing targets
- **`/regenerate-decisions`** slash command for canonical DECISIONS.md
  periodic regeneration

The fork lives at `~/code/agent-stack`. Targets (engagement projects) live
elsewhere, e.g. `~/code/<engagement-slug>-internal/`.

---

## 2. Daily workflow — the 90% case

You're already on an engagement. You open Claude Code in the target dir.
Most of what you need is automatic:

1. **Session start.** CLAUDE.md eager-loads PREFERENCES, REVIEW_QUEUE,
   LESSONS, and (during work) WORKSPACE.md. The agent reads these without
   prompting.
2. **You give a goal.** Say what you want — e.g. "iterate on the deck,"
   "size this market," "write the situation assessment." The agent
   triggers the matching skill via the trigger phrases in
   `.agent/skills/_index.md`.
3. **The skill orchestrates.** Most skills dispatch sub-agents. You sign
   off at gates. The agent stops, asks, iterates.
4. **Logs accumulate.** Every tool call lands in episodic memory. You
   don't need to manage this.
5. **End of session.** Stop hook runs `auto_dream.py` which clusters the
   day's episodes into candidate lessons. They land in REVIEW_QUEUE.md.

That's the 90%. Sections 3-9 below cover the 10%.

---

## 3. Starting a new project — full sequence

**FIRST decide which scenario you're in.** This determines everything that
follows. They are different workflows with different commands.

### Scenario A — Fork dev (extending the harness itself)

You're editing harness primitives in this repo: skills, agent prompts,
workflows, protocols, harness tooling, install logic, vendored skills. The
fork IS the harness; you edit it directly. **No install step.**

```bash
# 1. Make sure fork is current
cd ~/code/agent-stack
git checkout master
git pull origin master

# 2. Branch off master
git checkout -b feature/step-X.Y-<short-name>

# 3. Open Claude in the fork dir
claude
```

The agent reads the FORK's brain — fork's `.agent/memory/`, fork's
CLAUDE.md (which lives at `adapters/claude-code/CLAUDE.md` and gets
installed-as-CLAUDE.md only at install time). Fork's semantic memory
already has the harness-development DECISIONS, LESSONS, DOMAIN_KNOWLEDGE
treatise — that's intentional; this brain is FOR developing the harness.

**When you'd use this:** building a new agent team (like the SDLC team
extension for prototype-app work), authoring a new skill, fixing a
harness bug, adding a new workflow contract, vendoring an upstream skill,
extending `harness_manager` Python code.

**Test in `examples/pdlc-sandbox/`** — the throwaway target that lives
inside the fork. Or run `./install.sh claude-code /tmp/<slug> --yes`
into a temp dir for an isolated smoke test.

When you're done: PR feature → master, then `./sync-target.sh` propagates
the changes to your live engagement targets.

### Scenario B — Target use (using the harness on a real project)

You're building a deliverable (deck, analysis, prototype, product feature)
using the harness's existing capabilities. **The harness gets installed
into a NEW dir; you work there.**

```bash
# 1. Set up the new project dir
PROJECT=<your-slug>           # e.g. acme-pricing-2026q2
mkdir -p ~/code/${PROJECT}-internal
cd ~/code/${PROJECT}-internal
git init
cat > .gitignore <<'EOF'
output/
.claude/agent-memory/
.agent/memory/client/
.agent/memory/episodic/
.agent/memory/working/
.agent/memory/candidates/
node_modules/
.DS_Store
EOF
git add . && git commit -m "init: ${PROJECT}"

# 2. Install harness from fork (drops .agent/ + .claude/ into target)
cd ~/code/agent-stack
./install.sh claude-code ~/code/${PROJECT}-internal --yes

# 3. (Optional) Enable BCG adapter for consulting work
# Edit ~/code/${PROJECT}-internal/.agent/config.json — set "bcg_adapter": "enabled"
./install.sh claude-code ~/code/${PROJECT}-internal --yes  # re-run to propagate BCG content

# 4. Open Claude in the target dir
cd ~/code/${PROJECT}-internal
claude
```

The agent reads the TARGET's brain — target's `.agent/memory/`
(engagement-blank from Phase K templates, accumulates engagement-specific
lessons), target's CLAUDE.md, target's `.claude/agents/` (5 SDLC agents +
20 BCG agents if `bcg_adapter` enabled). **Fork's harness-development
memory is NOT loaded** — that's intentional; engagement work shouldn't
see harness-dev lessons.

**When you'd use this:** building a deck for a real client, sizing a
market, building a product feature, anything that produces a deliverable
the engagement OWNS (not the harness).

**No new branch on the fork.** The target has its own git repo with its
own history. Fork stays on master.

### Scenario A → B (sequenced — extend harness, then use it)

For tomorrow's BCG/PDLC project (extend SDLC team for prototype-app
work, then use it on a real project):

1. **Scenario A first** — branch off fork master, build the new SDLC
   agents + workflow contracts + protocol extensions, test in /tmp,
   merge to master.
2. **Scenario B second** — install the now-extended fork into a new
   target, work there.

Use `./sync-target.sh <existing-target>` if a Scenario-A change needs
to propagate to a target you've already installed into.

### 3a. Detailed Scenario B — consulting engagement onboarding

The Scenario B setup steps above get you to "Claude is open in the
target." The next steps below are specific to consulting engagements.

### 3b. Consulting engagement — onboard the client

Once Claude is running in the target, **first prompt of the engagement**:

```
This is a new BCG engagement: <one-line description of the client and
problem>. Onboard with the client-onboarding skill.
```

The skill will:
- Prompt you for an engagement slug
- Scaffold `.agent/memory/client/<slug>/` from the template
- Set `active_client` in config.json
- Ask you to drop briefing files into `raw-uploads/`
- Invoke `document-researcher` per file to build summaries + INDEX.md

After that completes:

```
Brainstorm the engagement approach. Use the brainstorming skill.
```

This is the canonical "explore intent + requirements + design before
implementation" step. **Use it before any creative work** (storyboarding,
analytical framing, structuring an issue tree). Forces explicit thinking
about what we're trying to do before generating output.

### 3c. Consulting engagement — produce a deliverable

For a deck:

```
Build the deck for this engagement using consulting-deck-builder. Audience:
<who>. Question we're answering: <what>. Sources: see INDEX.md.
```

The skill runs Phase 1 (Storyboard) → Phase 2 (Content) → Phase 3 (Format
via vendored deckster). You sign off at each phase boundary. Each phase
exit fires `memory_reflect` at importance ≥ 8 (HARD GATE — phase isn't
complete without it).

For a non-deck deliverable (situation assessment, issue tree, etc.), look
in `.agent/workflows/_index.md` for the matching workflow file. Then:

```
Run the situation-assessment workflow for this engagement.
```

The workflow tells the agent which subagents to dispatch (program-director
+ framework-lead + case-analysts).

### 3d. Product build (SDLC/PDLC) — start a feature

For tomorrow's BCG/PDLC project where you're **both solving and building**:

```
Brainstorm what we're building. Use the brainstorming skill.
```

Then the canonical SDLC pipeline:

```
Run product-discovery on this idea.
```

(Frames the problem before solving — agent uses `.agent/skills/product-
discovery/`.)

```
Once discovery is done, write the requirements.
```

(Triggers `requirements-writer` skill.)

```
Decompose the PRD into stories.
```

(Triggers `story-decomposer`.)

```
Review the spec adversarially.
```

(Triggers `spec-reviewer` — gates the spec before architecture.)

```
Now design the architecture.
```

(Triggers `architect` agent — produces ADR + design sketch.)

```
Plan the implementation.
```

(Triggers `planner` skill — TDD plan with destinations and fences.)

```
Implement task #1.
```

(Triggers `implementer` agent — writes code, `test-writer` writes failing
test first.)

Etc. Full pipeline:
`product-discovery → requirements-writer → story-decomposer → spec-reviewer
→ architect → planner → test-writer → implementer → code-reviewer →
release-notes → deploy-checklist`.

---

## 4. When to use which skill — the cheat sheet

| You want to… | Use this | Trigger phrase |
|---|---|---|
| Explore an idea before building anything | `brainstorming` | "brainstorm", "explore intent", "what should we build" |
| Frame a customer problem | `product-discovery` | "discovery", "what should we build", "user research" |
| Write a PRD/spec | `requirements-writer` | "requirements doc", "spec out", "BRD / PRD" |
| Break a PRD into stories | `story-decomposer` | "break down", "user stories", "decompose feature" |
| Review a spec | `spec-reviewer` | "review the spec", "is this ready to build" |
| Design system architecture | `architect` (agent) | "architecture", "system design", "ADR" |
| Plan an implementation | `planner` | "make a plan", "decompose this task" |
| Write code | `implementer` (agent) | "implement", "build this", "code it" |
| Write tests (TDD) | `test-writer` | "write tests", "test plan", "TDD" |
| Review code | `code-reviewer` | "review the code", "PR review" |
| Build a consulting deck | `consulting-deck-builder` | "build a deck", "storyboard", "iterate on slides" |
| Render the deck to .pptx | (auto) `deckster-slide-generator` | (dispatched by Phase 3 of consulting-deck-builder) |
| Onboard a new client | `client-onboarding` | "new engagement", "start client", "onboard client" |
| Summarize a document | `document-researcher` | "summarize this document", "researcher" |
| Debug something | `systematic-debugging` | (any bug, test failure, unexpected behavior) |
| Verify before claiming done | `verification-before-completion` | (before saying "complete" / "fixed" / "passing") |

For new skill creation: use `skillforge` (one of the seed skills).
For new agent prompts: pattern after deck-builder.md or case-analyst.md.

---

## 5. BCG case workflow vs SDLC/PDLC workflow

Both flavors share the harness; the dispatch shape differs.

### BCG case workflow (consulting engagement)

```
program-director (orchestrator)
  ↓
framework-lead (defines spine + 8-section coverage)
  ↓
case-analyst × N (parallel — one per workstream/cluster)
  ↓
deck-builder (consolidation)  +  delivery-lead (sanity review)
  ↓
partner-strategy + partner-analytics + principal-delivery (3-reviewer panel)
  ↓
You apply binding decisions → Phase 3 (deckster format)
```

Workflows: `.agent/workflows/situation-assessment.md`,
`issue-tree-hypothesis.md`, `mid-case-findings-deck.md`,
`final-recommendations-deck.md`. Each declares `team_structure` and
named subagents in frontmatter.

### SDLC / PDLC workflow (product build)

```
product-manager (PDLC entry)
  ↓ PRD
architect (ADR + design)
  ↓
planner (multi-step TDD plan)
  ↓
test-writer + implementer (Red-Green-Refactor per task)
  ↓
code-reviewer (adversarial pre-PR review)
  ↓
release-manager (deploy + release notes)
```

Each agent has `.claude/agents/<name>.md` definition. The agent
description acts as the dispatch trigger.

### Hybrid (tomorrow's BCG/PDLC project)

You can mix. Consulting workflows produce deliverables (decks, analyses,
recommendations); SDLC workflows produce code. A project that's BOTH
solving a client problem AND building a product runs both pipelines:
- Consulting side: `program-director` for engagement orchestration
- Product side: `product-manager` for product orchestration

The `bcg_adapter` flag enables both rosters; you dispatch whichever
roster fits the current task.

---

## 6. Memory model — where things live + when to do what

### Read order at every session start (CLAUDE.md handles this automatically)

1. `.agent/AGENTS.md` — map of the brain
2. `.agent/config.json` — adapter + active-client flags
3. `.agent/memory/personal/PREFERENCES.md` — your stable preferences
4. `.agent/memory/working/REVIEW_QUEUE.md` — pending lesson candidates
5. `.agent/memory/semantic/LESSONS.md` — distilled lessons
6. `.agent/protocols/permissions.md` — hard constraints
7. `.agent/context/_index.md` (always) + BCG/active-client (conditional)

### What you write to (and what you NEVER write to)

| Layer | You write directly? |
|---|---|
| `.agent/memory/working/WORKSPACE.md` | YES — agents update as they work; you can edit anytime |
| `.agent/memory/personal/PREFERENCES.md` | YES — your standing rules |
| `.agent/memory/semantic/DECISIONS.md` | NO — use `/regenerate-decisions` slash command |
| `.agent/memory/semantic/LESSONS.md` | NO — use `python3 .agent/tools/learn.py` or `graduate.py` |
| `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md` | OPTIONAL — engagement-specific stable facts (no canonical contract — leave empty if not actively curating) |
| `.agent/memory/episodic/AGENT_LEARNINGS.jsonl` | NO — auto-captured by hooks |
| `.claude/agent-memory/<agent>/` | (agents write to their own — you read for traceability) |

### Comprehensive activity log — where to look

**`.agent/memory/episodic/AGENT_LEARNINGS.jsonl`** captures every tool
call (Bash, Edit, Write, Task dispatch, memory_reflect). Not loaded into
prompts (only top-5-by-salience makes it into context). For traceability:

```bash
# Search by topic
python3 .agent/tools/memory_search.py "phase-3" --limit 20

# Recent activity
tail -50 .agent/memory/episodic/AGENT_LEARNINGS.jsonl | jq .

# Check brain state at a glance
python3 .agent/tools/show.py
```

Git-tracked memory history (`git log .agent/memory/`) gives time-series
of dream-cycle commits. `episodic/snapshots/` archives decayed entries.

---

## 7. Slash commands you have

| Command | What it does | When to run |
|---|---|---|
| `/regenerate-decisions` | Canonical bootstrap prompt — reads LESSONS + episodic, identifies 3-5 most significant decisions, writes to DECISIONS.md (additive, preserves existing entries) | End of major engagement step or phase. When DECISIONS.md feels stale. Before merging a feature branch with substantial decisions. |
| `/sync-harness` (BCG only) | Pull from fork upstream + sync from Confluence | When you want to refresh from upstream |

To run a slash command in the target session: type `/regenerate-decisions`
and the prompt fires.

---

## 8. Maintenance — keeping fork and target healthy

### Daily

- Just work. Hooks capture episodes, dream cycle stages candidates.

### Weekly

- **Mon 9:13** — Cron fires upstream-sync check on fork (auto). Review
  any new upstream activity in `feature/step-X.X-upstream-sync` branch
  if work is needed.
- **Mon 9:17** — Cron fires `harness_conformance_audit.py` (auto).
  Verifies eager-load budget + skill conformance.
- Run `python3 .agent/tools/show.py` in target to check brain state.
- Run `auto_dream.py` if it hasn't run recently:
  ```bash
  cd <target> && python3 .agent/memory/auto_dream.py
  ```
- Review REVIEW_QUEUE: graduate lesson-shaped candidates, reject noise:
  ```bash
  cd <target> && python3 .agent/tools/list_candidates.py
  python3 .agent/tools/graduate.py <id> --rationale "..."
  python3 .agent/tools/reject.py <id> --reason "..."
  ```

### When you ship a fork-side improvement

```bash
# 1. Edit on fork. Commit.
cd ~/code/agent-stack
# ...edit, commit, push

# 2. Push to existing targets
./sync-target.sh ~/code/<target>-internal --dry-run  # preview
./sync-target.sh ~/code/<target>-internal --yes      # apply

# 3. Restart Claude Code session in target if it's open
#    (eager-loaded files may have changed)
```

### End of an engagement / step / phase

```bash
cd <target>
/regenerate-decisions  # in Claude session — refreshes DECISIONS.md
python3 .agent/memory/auto_dream.py  # stage candidates from the run
python3 .agent/tools/list_candidates.py  # review staged
# Graduate the lesson-shaped ones; reject noise
```

---

## 9. Troubleshooting

### "Agent isn't reading the skill I expected"

Check `.agent/skills/_index.md` for the trigger phrases. If your prompt
doesn't include any trigger word, the skill won't fire. Either rephrase
or add to the skill's frontmatter `triggers:` list.

### "REVIEW_QUEUE is full of file-write noise"

Known issue (Gap 9 from Step 8.3 post-mortem) — `auto_dream.py` clusters
by token overlap, and long content-drafting sessions produce file-write-
shaped clusters that aren't lesson-shaped. Batch-reject with:

```bash
for f in .agent/memory/candidates/*.json; do
  cid=$(basename "$f" .json)
  python3 .agent/tools/reject.py "$cid" --reason "tool-write noise"
done
```

Step 8.4 will fix this with an action-type filter on the dream cycle.

### "Phase L's hard-gate reflection is interrupting my flow"

The reflection is the canonical mechanism for engagement learning to
reach the dream cycle's promotion path. If it's truly interrupting, you
can override the hard gate by saying so explicitly — but the default
should be: do the reflection. It's one bash call with structured note.

### "Target's CLAUDE.md is out of sync with fork"

CLAUDE.md is NOT auto-synced (it's a customizable per-install file).
Use `install.sh --reconfigure` to refresh it explicitly:

```bash
cd ~/code/agent-stack
./install.sh claude-code ~/code/<target>-internal --reconfigure
```

### "I want a fresh install in the target without losing my engagement memory"

Don't. `install.sh` on an existing target preserves memory by default.
If you want to refresh harness internals only, use `sync-target.sh` —
it explicitly preserves `.agent/memory/`, `.claude/agent-memory/`,
`output/`, and target's CLAUDE.md / settings.json / config.json.

---

## 10. Quick reference — file locations cheat sheet

| You want to… | Path |
|---|---|
| Add a new skill | `.agent/skills/<name>/SKILL.md` + register in `_index.md` + `_manifest.jsonl` |
| Edit a BCG agent prompt | `adapters/bcg/agents/<name>.md` |
| Edit an SDLC agent prompt | `adapters/claude-code/agents/<name>.md` |
| Add a slash command | `adapters/claude-code/commands/<name>.md` (or BCG-specific in `adapters/bcg/commands/`) — register in `adapter.json` files list |
| Edit eager-load CLAUDE.md | `adapters/claude-code/CLAUDE.md` (target's CLAUDE.md is regenerated from this on `--reconfigure`) |
| Add a new workflow | `.agent/workflows/<id>.md` + register in `_index.md` |
| Add a vendored skill | `adapters/bcg/skills/<name>/` with sidecar `INTEGRATION.md` (linter skips dirs with INTEGRATION.md) |
| Find what's in episodic | `python3 .agent/tools/memory_search.py "<query>"` |
| Snapshot what's installed in target | `python3 .agent/tools/snapshot_diff.py --diff` |

---

## 11. Tomorrow — your BCG/PDLC project

Pre-flight:

```bash
# 1. Confirm fork is on master + clean
cd ~/code/agent-stack && git status && git log --oneline -3

# 2. Set up the new project (consulting + product flavor)
PROJECT=<your-slug>
mkdir -p ~/code/${PROJECT}-internal
cd ~/code/${PROJECT}-internal
git init
cat > .gitignore <<'EOF'
output/
.claude/agent-memory/
.agent/memory/client/
.agent/memory/episodic/
.agent/memory/working/
.agent/memory/candidates/
node_modules/
.DS_Store
EOF
git add . && git commit -m "init: ${PROJECT}"

# 3. Install harness with BCG adapter (since BCG-flavored)
cd ~/code/agent-stack
./install.sh claude-code ~/code/${PROJECT}-internal --yes
# Edit ~/code/${PROJECT}-internal/.agent/config.json — set bcg_adapter: enabled
./install.sh claude-code ~/code/${PROJECT}-internal --yes  # re-run to propagate BCG content

# 4. Open Claude in the project
cd ~/code/${PROJECT}-internal
claude
```

First prompt to type:

```
This is a new BCG engagement that's also a product build. The client
context: <X>. The product we'll build alongside: <Y>. Onboard with the
client-onboarding skill.
```

After onboarding completes:

```
Brainstorm the joint approach — what's the consulting answer and what's
the product we're building. Use the brainstorming skill.
```

Then run the appropriate skills based on what surfaces from brainstorming.
Both rosters (BCG + SDLC) are available.

---

## 12. The contracts that shape this fork

**Source of truth:**
- Canonical agentic-stack design: `examples/agentic-stack-resource/agentic-stack-source-article.txt`
- Upstream: `codejunkie99/agentic-stack` on GitHub

**Core contracts:**
- 4-layer memory: working / episodic / semantic / personal (canonical)
- Dream cycle: episodic → cluster → promote to LESSONS (canonical)
- Periodic regenerate: LESSONS + episodic → DECISIONS (canonical, /regenerate-decisions)
- Per-agent memory dirs: deck-builder pattern (our adapter convention, not canonical)
- Phase-exit reflection HARD GATE: importance × pain ≥ 70 (our extension)
- Vendored skill convention: `INTEGRATION.md` sidecar = linter skips (our extension)

When in doubt, the source article wins. Adapter extensions are documented
in `.agent/memory/semantic/DECISIONS.md` (fork side) so they're traceable.

---

*Last updated: 2026-04-30. Step 8.3 complete; Step 8.4 (harness-graduate.py
+ auto_dream noise filter + propose_harness_fix wiring) deferred.*

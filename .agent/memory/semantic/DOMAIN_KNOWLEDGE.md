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
<!-- TODO (Pulkit): 1-2 sentences capturing what AGENTS.md is and why it exists.
     Hint: think about why the agent needs a map rather than auto-discovering the
     tree. What breaks if AGENTS.md is out of sync with the filesystem? -->

### Module 2: Memory — four layers with distinct retention policies
<!-- TODO (Pulkit): what's the ONE key distinction between the four layers that
     you want to remember? Name each layer in one phrase. What's the rule you'll
     follow to decide where new information belongs? -->

### Module 3: Skills — progressive disclosure
<!-- TODO (Pulkit): why is progressive disclosure necessary? (Hint: the author
     hit a wall at 30 skills / 90K tokens.) What's the distinction between
     _index.md, _manifest.jsonl, and individual SKILL.md files? -->

### Module 4: Protocols — deterministic enforcement
<!-- TODO (Pulkit): the KEY property of the protocol layer is that it's enforced
     architecturally, not by model judgment. Capture in 2 sentences why that
     matters. What specifically runs, and when? -->

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

### [future entries]
- When something above is wrong, rewrite the compiled-truth section and add
  a timeline entry explaining what changed.
- When a non-obvious lesson surfaces (e.g., "auto_dream.py doesn't commit git
  because hosts can't be trusted to do so unattended"), add it.

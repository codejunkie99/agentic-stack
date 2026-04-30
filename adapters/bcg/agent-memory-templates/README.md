# BCG agent-memory templates

Per-agent memory stubs for the BCG consulting roster. Two shape conventions
coexist; the **dir-pattern is the recommended shape going forward**.

## Adapter-specific extension (NOT canonical agentic-stack)

`.claude/agent-memory/` is a Claude-Code-adapter convention, not part of the
canonical agentic-stack design (which only specifies `.agent/memory/`'s four
layers — working / episodic / semantic / personal). The agentic-stack source
article does not mention per-agent memory dirs. We invented this layer
because long parallel-dispatch sessions need per-agent persistence that
doesn't pollute shared semantic memory or the eager-load surface.

## Two shape conventions

**Dir-pattern (recommended):** `.claude/agent-memory/<agent-name>/` containing
typed memory files plus an index. Used by `deck-builder`, `delivery-lead`.
Shape:

```
<agent-name>/
├── MEMORY.md                                # one-line index per file below
├── project_<engagement>.md                  # engagement-specific facts
├── feedback_<topic>.md                      # user-confirmed binding decisions
└── user_<name>.md                           # observed user preferences
```

Each typed file uses YAML frontmatter:

```markdown
---
name: <descriptive name>
description: <one-line, used to decide relevance later — be specific>
type: project | feedback | user
---

<body — for feedback/project, lead with rule/fact + **Why:** + **How to apply:**>
```

`MEMORY.md` is a one-line-per-file index — no frontmatter, no headers, no
content beyond the pointer list. Keep under 150 chars per line.

**Flat-file pattern (legacy, deprecated):** single `.claude/agent-memory/<agent-name>.md`
file initialized as a 3-line stub. The starter-kit's original convention.
Still works (agents append entries), but has limitations: no semantic typing,
the file becomes a long undifferentiated log, hard to scan.

## Migration path

New BCG agents should use the dir-pattern. Existing flat-file stubs migrate
opportunistically: when an agent first writes to its memory under the new
pattern, create the dir + MEMORY.md + appropriate typed file, archive the
flat stub if non-empty.

The flat templates in this directory remain for backwards compatibility —
they install as 3-line stubs so the dir doesn't 404 if an agent still
expects the flat path. Future Step 8.x will remove these once all 16 agents
are confirmed using the dir-pattern.

## How these get used

When `bcg_adapter: "enabled"` and `install.sh` runs, the entire directory
is copied to `target/.claude/agent-memory/` alongside the BCG agents and
slash commands. Each BCG agent reads and writes to its own memory dir
(or flat file, in legacy mode) during a session, without colliding with
other agents' state.

Distinct from:
- `.agent/memory/` — the portable brain's shared memory (working /
  episodic / semantic / personal layers). Canonical agentic-stack. Any
  agent can read it; it is firm-agnostic and engagement-agnostic.
- `adapters/bcg/agents/` — the agent *definitions* (frontmatter +
  responsibilities + approach). Static.

This dir holds per-role scratchpads that become dynamic during an
engagement.

## Filename rule

Template filenames match the agent's `name:` frontmatter field exactly.
The starter-kit's `architect.md` was renamed on import to
`program-architect.md` to track the 8.2.1 agent rename — template-to-agent
lookup is by name, so the two must stay in sync.

Templates for the three authored reviewer-lens agents (`partner-strategy`,
`partner-analytics`, `principal-delivery`) were created from scratch in
Step 8.2.3 to complete the set — same 3-line stub shape as the imports.

## Lifecycle

- **Install**: templates copied into target `.claude/agent-memory/` by
  install.sh when `bcg_adapter: "enabled"`.
- **During engagement**: agents append entries to their respective files.
  The installed copy diverges from this template directory over time —
  that's intended.
- **Re-install**: install.sh does not overwrite existing target files if
  they have content; fresh installs get fresh stubs.

Track the shape here; the filled content is engagement-private and lives
in the target's `.claude/agent-memory/`, which should be gitignored at
the engagement repo level.

# BCG agent-memory templates

Per-agent memory stubs for the 16-agent BCG consulting roster. Each file
is a 3-line placeholder (`# <role> Memory\n\nNo entries yet.`) that
initializes an empty memory slot for that role.

## How these get used

When `bcg_adapter: "enabled"` and `install.sh` runs, the entire directory
is copied to `target/.claude/agent-memory/` alongside the BCG agents and
slash commands. Each BCG agent can read and write to its own memory file
during a session (e.g., `program-manager.md`) without colliding with
other agents' state.

Distinct from:
- `.agent/memory/` — the portable brain's shared memory (working /
  episodic / semantic / personal layers). Any agent can read it; it is
  firm-agnostic and engagement-agnostic.
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

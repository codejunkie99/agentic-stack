# BCG adapter

Context overlay for BCG engagements. Unlike harness adapters (`claude-code`,
`cursor`, etc.) which wire the brain into a specific agent runtime, this
adapter layers BCG-specific content on top of whichever harness is active.

Loaded by default when `.agent/config.json` has `"bcg_adapter": "enabled"`.
When disabled, the fork remains generic and shareable.

## Layout

```
adapters/bcg/
├── README.md          # this file
├── scripts/           # BCG-specific tooling (e.g. sync-confluence.py)
├── commands/          # BCG-specific slash commands (/sync-harness)
├── protocols/         # BCG protocol overlays (Atlassian safety, data classification)
├── templates/         # BCG deliverable templates (weekly-status, meeting-notes, config.yaml)
├── context/           # BCG-specific semantic context
│   ├── firm/          # Firm-wide: BCG hierarchy + engagement model (generic quality
│   │                  # standards live in .agent/context/quality-standards.md)
│   ├── frameworks/    # BCG-attributed frameworks (Growth-Share Matrix; generic frameworks
│   │                  # — Issue Tree, Pyramid, 7-S, etc. — live in .agent/context/frameworks.md)
│   └── industries/    # Industry context modules (consumer-goods, financial-services, ...)
│
│   Note: `glossary/` used to live here but the consulting terminology was firm-generic
│   and moved to `.agent/context/glossary.md` in Step 8.2.4.
├── personas/          # BCG-specific reviewer style overlays (partner archetypes)
├── agents/            # BCG consulting program roster — program/case execution roles
│                      # (distinct from adapters/claude-code/agents/ which holds SDLC roles)
├── skills/            # BCG-skinned skills (e.g. confluence-access)
└── mcp/               # BCG MCP server configuration pointers
```

## Agent rosters: BCG consulting vs. SDLC

Two disjoint agent rosters coexist in the installed target's `.claude/agents/`:

| Roster | Home | Roles | Example |
|---|---|---|---|
| SDLC (harness-level) | `adapters/claude-code/agents/` | product-manager, architect, engineer, reviewer, release-manager | Build software |
| BCG consulting | `adapters/bcg/agents/` | program-director, program-manager, program-architect, engineering-lead, analyst, sme, executive-sponsor, … | Run a BCG engagement |

The SDLC roster is always installed. The BCG roster is installed only when
`.agent/config.json` has `"bcg_adapter": "enabled"` (install.sh reads this
flag and conditionally copies `adapters/bcg/agents/*.md` alongside
adapters/bcg/commands/*.md into the target's `.claude/` dirs).

Name collisions are resolved at import time. The starter-kit's `architect`
(program-scale — technology stack, standards, build-vs-buy) was renamed to
`program-architect` on import to avoid clashing with the SDLC
`architect` (PRD→ADR for a single feature). Prose references to
"Architect" in peer BCG agents were updated to "Program Architect".

## What lives here vs. `.agent/`

| Content type | Home | Why |
|---|---|---|
| Generic skills (planner, implementer, etc.) | `.agent/skills/` | Shareable across any engagement, any firm |
| BCG-specific skills (confluence-access, etc.) | `adapters/bcg/skills/` | Tied to BCG's toolchain (Atlassian, Rovo, internal MCP) |
| Agent roster (product-manager, architect, ...) | `adapters/claude-code/agents/` | Claude-Code-native; harness-level |
| BCG framework reference (MECE, Pyramid) | `adapters/bcg/context/frameworks/` | Firm-specific canon |
| Generic reviewer personas (skeptical-exec) | `.agent/personas/` (Phase 2) | Shareable archetypes |
| BCG partner-specific personas | `adapters/bcg/personas/` | Real colleague review styles |
| BCG Enterprise GitHub / Confluence configs | `adapters/bcg/templates/` | BCG-specific infrastructure |
| Client engagement data | `.agent/memory/client/<id>/` (gitignored) | D1-Option-B decision |

## Loading model (how "BCG is ambient by default")

The BCG adapter is enabled-by-default on Pulkit's working-project install,
disabled elsewhere. This means:

1. A flag in `.agent/config.json` (`"bcg_adapter": "enabled"`) toggles the
   whole adapter.
2. `CLAUDE.md` has a conditional block that auto-mounts BCG context,
   protocols, and MCP tool allowlists when the adapter is enabled.
3. Agents read from both `.agent/memory/semantic/` and
   `adapters/bcg/context/` and see one merged context — they don't
   know or care which layer a file came from.
4. BCG-specific tools (`mcp__claude_ai_CapIQ_MCP_Connector_BCG_Internal__*`,
   `mcp__claude_ai_Deckster_Chart_Tables__*`) are listed in agent
   frontmatter directly; if the adapter is disabled, those tools simply
   aren't registered and agents degrade gracefully to public data sources.
5. BCG-specific slash commands (e.g. `/sync-harness`) are only wired when
   the adapter is loaded — generic fork users never see them.

Consequence: **no need to annotate tasks with "this is BCG"** — BCG context
is ambient whenever the adapter is loaded, which is always on Pulkit's
working-project install.

## Status

Directory scaffold is in place as of Step 8.0 (2026-04-24). Content lands
in Step 8.1 via classified import from the `harness-starter-kit` starter
provided by Kenneth Leung (BCG). Until Step 8.1 lands, the subdirectories
are empty (`.gitkeep` placeholders).

See `.agent/memory/semantic/DECISIONS.md` for the D2 hybrid-adapter
decision and the Step 8.1 classification rationale.

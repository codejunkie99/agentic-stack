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
│   ├── firm/          # Firm-wide: BCG hierarchy, engagement model, quality standards
│   ├── frameworks/    # BCG analytical frameworks (MECE, Pyramid, BCG Matrix, driver trees)
│   ├── glossary/      # Consulting terminology
│   └── industries/    # Industry context modules (consumer-goods, financial-services, ...)
├── personas/          # BCG-specific reviewer style overlays (partner archetypes)
├── skills/            # BCG-skinned skills (e.g. confluence-access)
└── mcp/               # BCG MCP server configuration pointers
```

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

# BCG adapter

Context overlay for BCG engagements. Unlike harness adapters (claude-code,
cursor, etc.) which wire the brain into a specific agent runtime, this
adapter layers BCG-specific content on top of whichever harness is active.

## What lives here (eventually)

- **Skills** — BCG-specific skills (e.g. `bcg-slide-generator`,
  `deckster-chart-tables`, `capiq-lookup`) that wrap the BCG MCP ecosystem.
- **Subagent definitions** — BCG-flavored subagents for the PDLC-SDLC team
  once Phase 2 introduces the data-science layer.
- **MCP configs** — pointers to BCG-approved MCP servers (Deckster, CapIQ,
  Transcript Library, Navi, People Finder, M365).
- **Protocols** — BCG-specific protocol overlays that extend the generic
  `.agent/protocols/` set.

## Status

Scaffold only. Content is added as the engagement workflow reveals what
belongs here rather than pre-declared. See `.agent/memory/semantic/DOMAIN_KNOWLEDGE.md`
for the architectural reasoning (D2 decision: hybrid core + `adapters/bcg/`).

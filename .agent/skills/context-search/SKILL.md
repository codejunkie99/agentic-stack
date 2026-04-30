---
name: context-search
version: 2026-04-24
bootstrapped_from: "harness-starter-kit (Kenneth Leung, BCG) — 2026-04-24 import, Step 8.1"
path_adapted_in: "Step 8.2.3 — paths rewritten to agent-stack conventions (client memory + firm adapter context)"
description: Use before any analysis or drafting to retrieve relevant context from the engagement knowledge base — client facts, decisions, constraints, transcripts, firm frameworks, glossary. Distinct from memory recall — this skill searches structured engagement context, not episodic/semantic agent memory. Always cite sources and flag gaps explicitly. Client-scoped paths resolve via `.agent/config.json.active_client` (D1-Option-B); firm context paths resolve via the active firm adapter (e.g. `adapters/bcg/`).
triggers: ["find context on", "search context", "what do we know about", "pull the background", "what's in the engagement data"]
tools: [bash]
preconditions: ["client memory directory exists for the engagement OR a firm adapter is active"]
constraints:
  - context is read-only — never modify context files
  - prefer specific citations over paraphrases
  - flag gaps as [CONTEXT GAP: <what is missing>]
  - surface contradictions rather than picking one version silently
category: knowledge-work
---

# Context Search Skill

Use this skill to retrieve relevant context from the project's knowledge base before performing analysis or drafting.

## Search Protocol

### Step 1: Identify What You Need
Before searching, list:
- What specific information is required?
- What would change your analysis if it were different?
- Is this global context or case-specific?

### Step 2: Search Locations

Two path conventions apply:

- **Client-scoped context** lives under `.agent/memory/client/<active_client>/`, where `<active_client>` resolves from `.agent/config.json` (the `active_client` field). This directory is gitignored per D1-Option-B — never ships on the fork.
- **Firm-scoped context** lives under the active firm adapter — e.g. `adapters/bcg/context/` when `bcg_adapter: "enabled"`. Firm context is shared across engagements in that firm.

| Information Type | Where to Look |
|---|---|
| Engagement background, client facts | `.agent/memory/client/<active_client>/background/` |
| Data and analysis inputs | `.agent/memory/client/<active_client>/data/` |
| Decisions already made | `.agent/memory/client/<active_client>/decisions/` |
| Constraints and boundaries | `.agent/memory/client/<active_client>/constraints/` |
| Transcripts and interviews | `.agent/memory/client/<active_client>/transcripts/` |
| Firm analytical frameworks | `adapters/<firm>/context/frameworks/` (e.g. `adapters/bcg/context/frameworks/`) |
| Firm glossary | `adapters/<firm>/context/glossary/` |
| Firm engagement process / model | `adapters/<firm>/context/firm/` |
| Team roster and assignments | Engagement system via firm adapter (e.g. BCG Confluence — see `adapters/bcg/skills/confluence-access/`) |
| Action items and RAID log | Engagement system via firm adapter |

If no firm adapter is active (`bcg_adapter: "disabled"` and no other firm adapter enabled), the firm-scoped rows collapse to "not available" — cite a [CONTEXT GAP] and proceed with client-scoped context only.

### Step 3: Cite What You Find
Always cite:
- Source file or Confluence page
- Section heading if applicable
- Date of the content if time-sensitive

### Step 4: Flag Gaps
If required context is not found:
- Note explicitly: [CONTEXT GAP: <what is missing>]
- Propose what alternative data could substitute, or what assumption to make

## Rules
- Context is read-only — never modify context files
- Prefer specific citations over paraphrases
- If context is contradictory, flag both versions and ask for clarification

## Self-rewrite hook

After every 10 retrievals, or the first time a `[CONTEXT GAP]` flag
turns out to have been wrong (the context existed but wasn't found),
read the last 10 context-search entries from episodic memory. If
better retrieval strategies, citation conventions, or gap-detection
patterns have emerged, update this file. Commit:
`skill-update: context-search, <one-line reason>`.

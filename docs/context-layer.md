# Agentic Stack context layer

Agentic Stack gives Claude Code, Codex, OpenCode, and Cursor one local,
read-only way to recall earlier work. The desktop connects sources, imports
approved computer knowledge, and shows provenance. Agents retrieve the evidence
through MCP and answer inside the coding tool where the question was asked.

## Ask from any connected agent

After **Connections → Agent access → Connect all four tools**, prompts can be
natural questions:

```text
What did the cache subagent find?
@Claude where did we decide how retries work?
Find the Cursor session that changed authentication.
What preferences and current-work notes matter for this refactor?
```

The installed context skill directs the host agent to call `recall_context`.
That single call can return:

- visible user and assistant transcript evidence from Claude Code, Codex,
  OpenCode, and Cursor;
- model, agent, subagent, automation, and review metadata;
- approved notes from the shared knowledge graph;
- the current project's static personal profile and live work context;
- source paths, timestamps, stable content digests, and a reminder to verify
  historical claims.

Use `search_conversations` and `read_conversation` when several chats match and
the user needs to choose one. Use `prepare_context` when an agent needs a fixed,
budgeted pack for a specific project task.

## Computer context is explicit

The product can become a map of the user's working history without silently
reading the whole disk. Agent session stores are detected in their documented
local locations. Other folders, exports, rules, documents, skills, and memories
enter the graph only after the user previews and imports them. Credential-like
content, symlinks, oversized inputs, hidden reasoning, and raw tool payloads are
excluded or sanitized by the existing import paths.

All retrieval tools are read-only. They never edit source conversations or the
knowledge graph, and retrieved text never grants authority or permission.

## Native app responsibilities

The macOS app is the context control and audit surface:

- **Ask Your Context** searches work, memory, sessions, skills, and actions.
- Session filters narrow by coding tool, model, project scope, and role,
  including named subagents.
- **Context Sources** shows detected tools, indexed sources, and whether context
  remains on-device or on the connected private server.
- Conversation previews expose the source before a user attaches anything to a
  new task.
- The knowledge graph provides the spatial view of relationships and provenance.

The agent remains responsible for synthesizing the retrieved evidence and
stating uncertainty when the sources do not answer the question.

## Learning stays reviewable

After a successful run reaches review, Agentic Stack can extract one explicit
reusable finding such as a root cause, verified constraint, or decision. The
candidate records the agent, run ID, and task that produced it. It remains in
the lesson review queue until the owner accepts or rejects it, and routine
completion messages create no memory. This lets the context layer improve from
work without silently turning a model response into authority.

# Agentic Stack feature reference

This document lists the capabilities available in the native macOS desktop app
and its packaged local service. The desktop focuses on Claude Code, Codex,
OpenCode, and Cursor. Claude Code and Codex can also run inside the app;
OpenCode and Cursor currently provide read-only conversation and memory sources.

## Conversation workspace

- Conversations with agents are the primary workspace.
- Claude Code and Codex replies, errors, and tool lifecycle events stream into
  the transcript while the task runs.
- Follow-up messages resume the official CLI session instead of reconstructing
  a conversation from copied text.
- Stop cancels the active task owned by Agentic Stack.
- Edit and retry restores a failed prompt to the composer without silently
  submitting it.
- New conversations retain their project, host, selected agent, model, reasoning
  effort, and file-access policy.
- Conversation history remains searchable and can be archived with its agent.
- The composer supports imported-memory retrieval and explicit conversation
  references as separate controls.
- Attach up to eight images, PDFs, audio, video, text, or code files per message,
  with a 12 MB per-file and 24 MB per-message limit.

## Custom agents and model controls

- Create, edit, archive, and restore custom agents.
- Give each agent a display name, role, instructions, runner, model, reasoning
  effort, and file-access policy.
- Use Claude Code or Codex as the runner while keeping the account and provider
  configuration owned by the official CLI.
- Select models from the connected host's Codex model catalog or Claude's
  official model aliases, with a manual model ID fallback.
- Change the model and reasoning effort for the next turn from the composer.
- Choose **Auto** and set its priority to **Faster**, **Balanced**, or
  **Stronger**. The picker previews the model, effort, capability match, and
  reason for the current message before it runs.
- Search the live model catalog in **Fixed model** mode. Capability badges show
  whether a model exposes tools, files, and direct image input, and reasoning
  controls only list variants declared for that model.
- Keep automatic routing inside the selected runner and file-access policy.
  The picker configures policy; it does not silently change tools or permissions.
- Use read-only/planning access or allow edits within the selected project.
- Keep agent profiles on the selected host so the same profile can be used in
  more than one project.
- Preserve the original agent settings on existing conversations when a profile
  is edited.

## `@` context search

- Type a plain `@` for suggestions ranked against the surrounding prompt.
- Search visible conversation messages, titles, and excerpts across all detected
  projects and workspaces.
- Narrow immediately with `@Claude`, `@Codex`, `@OpenCode`, or `@Cursor`.
- Filter by coding tool, model, this project or every workspace, and role.
- Role filters cover primary agents, subagents, automations, and review agents.
- Results show their tool, title, date, model, role, workspace, excerpt, and a
  short relevance reason when available.
- The selected conversation and model receive a small ranking preference so
  useful nearby work appears sooner.
- Recent relevant work appears even when no search text follows `@`.
- Background prewarming builds the live conversation index after launch so the
  first picker interaction does not have to perform the full scan.
- Attach up to five results as removable context chips.
- Freeze a cleaned, bounded copy of the selected visible messages into the next
  run, with source identity and a content digest.
- Keep explicit references separate from automatic knowledge retrieval.
- Use keyboard navigation: arrows move through results, Return selects, and
  Escape closes the picker.

### Use the same tags inside coding tools

**Tools → Connections → Use @ in tools** installs one local `agentic-stack` MCP
entry and a small context skill in Claude Code, Codex, OpenCode, and Cursor. The
equivalent CLI command is `agentic-stack context install`.

The MCP service provides:

- `recall_context` for one-call, question-shaped retrieval across sessions,
  subagents, graph memory, and optional personal project context;
- `search_conversations` for query, tool, model, role, and contextual ranking;
- `read_conversation` for a chosen sanitized conversation;
- `search_shared_memory` for the approved knowledge graph;
- `prepare_context` for a bounded, provenance-bearing graph and conversation pack;
- `recommend_model` for a read-only subtask recommendation from the live local catalog;
- `read_personal_memory` for the project's static preferences and dynamic work context;
- recent conversations as MCP resources.

Claude Code and OpenCode can expose those resources in their native context
pickers. Codex and Cursor interpret the literal tags through the installed skill
and MCP tools. `agentic-stack context remove` removes only the managed entries
and skill files.

## Shared knowledge graph

- Preview material before importing it.
- Import approved memory, rules, skills, Markdown, text, portable exports, and
  selected Claude Code, Codex, OpenCode, or Cursor conversations.
- Search locally with SQLite full-text search.
- Browse a spatial 3D graph of notes, literal topic mentions, repository links,
  and source relationships. Drag to orbit, pinch or use buttons to zoom, and
  reset the camera at any time.
- Switch between 3D and the original 2D map. The choice is saved without
  changing graph data, filters, or selection behavior.
- Expand either view into a responsive full-page canvas. Camera position and
  the selected memory stay intact when entering or leaving the expanded view,
  while the Work tabs remain visible.
- Filter by text, topic, provider, and Focused or All imported views.
- Inspect the source path, source position, timestamp, provider, and digest for
  each note.
- Deduplicate identical chunks without losing their separate source records.
- Re-import unchanged sources idempotently.
- Rebuild derived labels and topics from the saved note text.
- Send a selected graph note to a new task draft.
- Retrieve up to five relevant notes automatically for a task, then freeze the
  exact evidence used by that run.
- Keep imported material as historical reference evidence rather than trusted
  project instructions.

Focused view hides routine successful tool events and generated context chunks
that add no reflection or evidence. All imported keeps them inspectable. The
graph visualization shows a bounded set of nodes; search and pagination cover
the full index.

## Memory, lessons, and references

- Open **Memory → Personal** to inspect stable preferences, dynamic current
  work, query-specific matches, and the source file behind every item.
- Read and edit personal, semantic, and working project memory files.
- Let agents read static personal preferences separately from dynamic current
  work through a bounded read-only tool. This context is never treated as new
  authority and profile writes still use the existing review flow.
- Recall memory by intent.
- Inspect candidate lessons and their source evidence.
- Automatically propose at most one explicit reusable finding from a completed
  successful run, linked to its agent, run ID, and task.
- Stage, accept, reject, reopen, and retract lessons.
- Record the reason and history for each lesson decision.
- Keep lesson promotion separate from knowledge import.
- Add explicit Markdown or text references for future work.
- Review agent-drafted references before using or exporting them.
- Inspect external Brain availability and open its status, history, explorer,
  health, onboarding, or MCP command from Operations.

## Tasks, activity, and review

- Create a task from a free-form prompt or a dashboard starter.
- Review the runner, model, reasoning effort, file access, selected references,
  and memory retrieval before starting.
- Run tasks in the actual selected repository on the current host.
- Choose planning/read-only or project-edit mode.
- Watch queued, running, review-needed, completed, failed, and cancelled states.
- Search task history and filter Active, Needs review, or Finished work.
- Inspect partial output, final output, errors, model information, timestamps,
  and attached evidence.
- Open the conversation behind a conversational task.
- Cancel work owned by Agentic Stack.
- Mark results reviewed while retaining the complete task record.
- Keep Activity inside canonical task history instead of duplicating it in a
  separate dashboard.

## Bounded loops

- Initialize loop definitions for a project.
- Validate loop contracts before execution.
- Run, resume, stop, inspect, and clean up owned loops.
- Use maker, deterministic verifier, and independent checker phases.
- Set time, turn, retry, and stagnation budgets.
- Apply deny paths and project constraints.
- Isolate work in owned Git worktrees.
- Persist phase state and checkpoints for safe resume.
- Open the owned worktree from the desktop.

The loop supervisor is a workflow boundary rather than an operating-system
sandbox. The selected coding tool's native sandbox and approval controls still
apply.

## Terminal and Operations

- Open real interactive Claude Code, Codex, and shell terminals in the selected
  project.
- Use the same terminal workspace on this Mac or a connected server.
- Keep terminal tabs alive while navigating through tasks, skills, and memory.
- Support ANSI color, agent menus, permission prompts, copy/paste, scrolling,
  keyboard input, and terminal resize.
- Interrupt the foreground process with Control-C.
- Reconnect to an existing terminal after a temporary connection failure.
- Open up to 12 terminal sessions per host.
- Run packaged Stack operations without a separate global installation:
  project dashboard, adapter manager, memory transfer, status, health audit,
  upgrade preview, setup, skill-manifest sync, loop status/validation, and Brain
  tools.
- Preserve interactive previews and confirmations in mutating management tools.

Terminal output is kept in bounded service memory for reconnection. It is not
automatically copied into the knowledge graph or task history.

## Projects, dashboard, and navigation

- Open an existing repository or create a managed project.
- Initialize only missing Agentic Stack files while preserving customized files.
- Switch between projects and between this Mac and a connected server.
- Use an adaptive dashboard with a task composer, priority work queue, running
  and review counts, agent launch controls, and imported-knowledge coverage.
- Use compact, standard, or large window presets.
- Resize or collapse the sidebar while keeping screen layouts stable.
- Keep Graph, Conversation, Overview, Tasks, Terminal, and Loops visible in
  a horizontally scrolling work bar instead of hiding them in an overflow menu.
- Use the same root-level workspace bar in normal and full-page Graph modes, so
  content cannot move or hide the route back to another section.
- Use Command-K to find screens, project actions, and packaged Stack commands.
- Use four stable workspaces: **Work** for Graph, Conversation, Overview, Tasks,
  Terminal, and Loops; **Memory** for Browse, Personal, Lessons, References, and
  Exports; **Connections** for sources and project adapters; and **Settings** for
  General, Rules, Maintenance, and Hosting. Skills remains a focused library.

## Guided setup and auto-detection

- Walk through project selection, detected tools, preferences, optional features,
  and a final change review.
- Detect Claude Code, Codex, OpenCode, and Cursor when the app activates and
  while Connections is open.
- Show installed applications, CLI paths, versions, local data, sign-in status
  where the official CLI exposes it, and supported skill locations.
- Turn automatic detection off in Settings.
- Delegate Claude Code and Codex sign-in to their official CLIs.
- Preserve existing preferences and report adapter conflicts for manual review.

Agentic Stack does not copy provider credentials and does not implement a
replacement OAuth client.

## Migration and imports

- Preview detected tool memory before importing it.
- Import portable Markdown, text, rules, JSON, and JSONL exports.
- Recognize common role/content conversation exports and OpenCode message data.
- Preserve source paths and provenance through the import pipeline.
- Report skipped, unsupported, oversized, changed, or credential-like content.
- Bound each scan by file count, file size, and total bytes.
- Page through older and newer conversation batches.
- Read OpenCode's local SQLite store in read-only mode.
- Leave every original chat database, transcript, rule, and memory file unchanged.
- Install skills separately into the supported destinations for each tool.
- Use the packaged transfer wizard to export or import portable Agentic Stack
  context bundles.

## Skills, adapters, and rules

- Browse project, local, and shared skills.
- Read a skill's instructions and supporting files.
- Copy a complete skill rather than only its entry file.
- Inspect and edit project skills.
- Install skills into supported Claude Code, Codex, OpenCode, or Cursor paths.
- Install project adapters for Claude Code, Codex, OpenCode, and Cursor through
  the desktop. The wider portable catalog remains available to existing CLI projects.
- Edit project protocols for permissions, delegation rules, and tool schemas.
- Inspect Mission Control trust and permission data.

## Handover and export

- Export reviewed references as a Markdown handover.
- Build portable context bundles for another Agentic Stack project or host.
- Preserve provenance in exported material.
- Keep draft, reviewed, and exported states explicit.

## Hosting

- Export a self-contained Agentic Stack server package.
- Connect the native app to a private server over HTTPS.
- Connect through a localhost SSH tunnel when the service is not publicly
  reachable.
- Store the control token in macOS Keychain.
- Run projects, agents, terminals, tasks, graph search, and operations against
  the selected host.
- Switch back to this Mac without merging the two hosts' state.
- Keep server projects, task history, graph, and CLI sign-ins on the server.
- Back up and restore the server data directory independently.

Hosting serves the backend for the native macOS app. It does not create a public
browser dashboard and does not automatically upload local Mac data.

## Optional Box execution

- Create a bounded cloud workspace with a finite lifetime.
- Follow explicit credential-inheritance settings.
- Inspect the workspace lifecycle from the task flow.

Box requires a separate provider account. Live provider validation remains a
preview limitation.

## Maintenance and diagnostics

- Run project health checks and inspect detected problems.
- Preview infrastructure upgrades before applying them.
- Synchronize the skill manifest.
- Inspect advanced project collector diagnostics.
- Refresh project, task, knowledge, and integration state.
- Inspect external Brain status without exposing its stored secrets.

## Packaging and updates

- Install from a drag-to-Applications DMG.
- Use the no-sudo Terminal installer, which pins the release and verifies its
  SHA-256 checksum and bundle signature.
- Check for updates from the app with Sparkle.
- Verify every update with the project's Ed25519 update key.
- Keep data outside the replaceable application bundle.
- Build the app, ZIP, DMG, and self-contained server package from source.

## Privacy and security boundaries

- All local conversation sources are read-only.
- Conversation search indexes visible user and assistant messages. It excludes
  hidden reasoning, tool payloads, credential stores, and credential-like lines.
- Direct `@` search can include sanitized primary-agent and subagent transcripts
  without importing them into durable knowledge.
- Knowledge conversation imports include visible user messages and final
  assistant replies while excluding nested subagent transcripts by default.
- Imports require preview and explicit source approval.
- Context is bounded before it reaches an agent.
- Selected context records its source and digest for later inspection.
- Imported notes remain untrusted historical evidence.
- Host control tokens are stored in Keychain and provider tokens remain with
  their official coding tools.
- Local service traffic stays on a random localhost port; hosted traffic uses an
  authenticated RPC facade.

## Data locations

Desktop data lives under:

```text
~/Library/Application Support/Agentic Workspaces
```

That directory contains the local service database, conversations, agent
profiles, graph, and settings. Project-owned `.agent` files stay in the project.
Claude Code, Codex, OpenCode, and Cursor keep their original data in their own
locations.

## Keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| Command-K | Search screens and actions |
| Command-Return | Send a conversation message |
| Command-N | Start a conversation with the selected agent |
| Command-Shift-A | Create a custom agent |
| Command-Shift-T | Open Terminal |
| Command-Control-S | Toggle the sidebar |
| Command-Option-1 | Compact window |
| Command-Option-2 | Standard window |
| Command-Option-3 | Large window |

## Current limits

- The downloadable preview supports Apple Silicon and macOS 14 or later.
- The public build is ad hoc signed and is not Apple-notarized.
- OpenCode and Cursor are read-only context sources in the desktop; direct agent
  execution is available for Claude Code and Codex.
- Codex and Cursor do not currently expose third-party conversation resources as
  a native picker category, so their installed skill invokes the MCP search.
- Proprietary or undocumented export formats are not universally supported.
- Knowledge graph edges are literal relationships rather than model-inferred
  claims.
- The app does not merge local and hosted data automatically.
- Interactive terminal changes to SwiftUI still require a build and app restart.

For screen-level instructions, see [Agentic Stack desktop](native-workspaces.md).
For the service boundary and storage design, see [Architecture](architecture.md).

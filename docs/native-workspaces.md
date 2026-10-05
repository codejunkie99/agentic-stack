# Agentic Stack desktop

A native SwiftUI macOS interface to the existing Agentic Stack project model.
Open a repository and manage its actual `.agent` files. **Work** opens a 3D
knowledge graph with the conversation composer below it. Switch between Graph
and Conversation without losing the selected work. The sidebar keeps **Work**,
**Memory**, and **Connections** together, with visible **Skills**, **Insights**,
and recent work. **Command-K** searches across the workspace.

## What the desktop supports

| Repository capability | Desktop behavior |
| --- | --- |
| Work and conversations | Persist an objective, conversations, runs, and checkpoints. Resume a conversation or continue the work in a fresh Codex or Claude Code session with its checkpoint. |
| Custom agents | Create and edit profiles with instructions, runner, model, effort and file access. Stream replies and tool activity through the official CLI. |
| Guided setup | Five native steps for project selection, detected agents, personal preferences, optional features, and a review before applying. Existing customized files are preserved. |
| Integrations and migration | Auto-detect Claude Code, Codex, OpenCode, and Cursor; preview portable rules, memory, and conversations; retain source paths and deduplicate imported notes. |
| Insights | A project dashboard with a task composer, priority queue, running/review counts, agent launch controls and imported-knowledge coverage. Advanced collector data is in Settings → Maintenance. |
| Projects | Open an existing repository or create a managed project. Initialize missing stack files while preserving existing content. |
| Claude Code and Codex | Detect installation, version and sign-in. Delegate local sign-in to the official CLI. Select either agent for tasks. |
| Terminal | Real interactive Codex, Claude Code and shell tabs in the selected project, on this Mac or the connected server. |
| Agent tasks | Run in the selected repository, preserve its instructions, choose planning/read-only or project-edit mode, inspect results and cancel owned tasks. |
| Harness adapters | Install the four desktop adapters for Claude Code, Codex, OpenCode, and Cursor using the existing portable installer. |
| Skills | Browse installed local/shared skills, read instructions, copy complete skills with support files, inspect and edit project skills. |
| Memory | Browse imported evidence, review agent-proposed lessons and references, and generate reviewed exports. Completed work can stage one reusable finding with run provenance; the owner still accepts or rejects it. Read/edit personal, semantic and working files; recall an intent and inspect Brain state. |
| Knowledge graph | Preview/import Claude Code, Codex, OpenCode, Cursor, and Agentic Stack memory; explore a switchable 3D/2D graph, search notes, filter topics and providers, and inspect source evidence beside the composer. |
| Context retrieval | Select Off, local search or an optional retrieval agent; preview a budgeted context pack, inspect source paths and digests, and pin or exclude evidence for later messages. |
| Spotlight search | Group Work, Memory, Conversations, Skills and Actions. Search project conversations by default, with an explicit All conversations option; preview external chats and skill instructions before use. |
| Conversation attachments | Open a conversation-only Spotlight from `@` or the composer's attachment control. Search all tools and projects by default, inspect identifying metadata, then attach a removable chip without sending. |
| Protocols and trust | Read/edit project protocol files and inspect existing Mission Control trust and permission data. |
| Loops | Connect official agents, review contracts, run/resume/stop bounded loops, inspect phases and checkpoints, and open owned worktrees. |
| Work history | Reopen recent objectives, conversations and standalone runs; inspect exact task results and review them. Legacy collector events remain under Settings → Maintenance → Advanced project diagnostics. |
| Maintenance | Doctor, skill manifest sync, infrastructure upgrade preview/apply, Brain status. |
| Hosting | Export the self-contained server package, connect over HTTPS or a localhost SSH tunnel, authenticate with a Keychain-stored control token, switch back to this Mac. |
| References | Import text/Markdown, approve sources explicitly, preserve source text/digests, review agent drafts. |
| Handover | Export reviewed Markdown and portable context bundles. |

When a project is chosen with the macOS folder picker, the app stores a
security-scoped bookmark and restores it before starting the local service on
future launches. A filesystem that stops responding is isolated behind a
five-second loop probe; the Loops screen stays usable and offers **Choose
folder…** to reconnect access.
| Learning artifacts | Preview and approve sanitized local metrics, training and evaluation files from eligible reviewed runs or existing approved records. This generates files; it does not train a model. |
| Box | Optional cloud execution lifecycle with finite TTL and explicit credential inheritance. Requires a Box account; live provider validation remains outstanding. |

**Memory** contains **Browse**, **Lessons**, **References**, and **Exports**.
Lessons support staging, accepting, rejecting, reopening and retracting, preserving
decision reasons and history. Graph memories have separate **Reference**,
**Accepted**, **Superseded**, and **Retracted** review states. Superseded and
retracted memories remain inspectable but are excluded from automatic retrieval.
Importing creates reference evidence; it does not accept a lesson or grant an
agent permission to act.

The interface is native macOS only. Hosting runs the backend for this native app, not a separate browser frontend.

Some advanced workflows use terminal interfaces: **Stack commands → Manage
adapters** includes removal and preference reconfiguration; **Transfer memory**
opens the import/export wizard. External Brain onboarding and optional extensions
retain their CLI workflows. This preview does not claim a dedicated SwiftUI
form for every repository command.

## Keep work across sessions

Choose **New work** or **Command-N**, write an objective, and send it to the
selected agent. The work record connects its conversations, runs and checkpoint.
Use recent work in the sidebar or the visible **Recent work** tab to reopen it.
In the context inspector, **Edit checkpoint** records progress, decisions, the
next action and work status while preserving supporting run links.

**Continue with… → Codex / Claude Code** opens a fresh runner session with the
checkpoint. Follow-ups within an existing conversation use that conversation's
CLI session. Both paths preserve the work record; continuation does not copy an
unlimited transcript into the new session.

The context inspector shows the next preview or last message's frozen context,
source excerpts, selection reasons, origin paths, digests, estimated tokens,
retrieval time and cache state. On wide windows it sits beside the graph; in
compact windows its toggle opens a sheet. Select **Preview next context** before
sending, or let the app retrieve when you send.

Retrieval options offer **Off**, **Local search**, or **Retrieval agent**, with
budgets of 1,000, 2,500, 5,000 or 8,000 estimated tokens. The optional agent ranks
available evidence; Codex defaults to GPT-5.6 Luna and Claude Code to Haiku when
the model field is blank. You can choose another available model. If the agent
is unavailable, retrieval falls back to local search and displays a warning.
Availability and usage follow the connected account. This is bounded, sourced
context retrieval, not literal infinite context.

Pin or exclude a source to control subsequent messages. **Off** disables
automatic memory retrieval; explicit attachments and reviewed project references
still apply. Historical sources remain reference evidence with their provenance.

## Create an agent and have a conversation

Use the composer's agent menu → **Create custom agent…**, **Command-Shift-A**,
or search “Create custom agent” with **Command-K**. Give the agent a name, a role and
instructions. Choose Codex or Claude Code, then a model and reasoning effort.
Codex choices use the selected host’s configured model catalog, falling back to
its local cache. Claude choices are official model aliases. Runner default and
a manual model ID are also available; your existing CLI account/provider
determines access and usage.

Choose read-only or project-file editing. Save the agent, select it in the
composer, and send with **Command-Return**. Responses and tool lifecycle events
stream into the conversation; **Stop** cancels that task. Follow-ups resume its
actual Codex or Claude session. The composer stays at the bottom while the
transcript scrolls. **Command-N** starts a new conversation with the selected agent.

Profiles are stored on the selected host and available across its projects.
Conversations remain scoped to one project. Editing a profile changes new
conversations. Existing conversations retain their runner, instructions and file
access; change their model and effort explicitly from the composer. Use
**Edit agent** to change a profile's defaults for new conversations.

Click the model button in the composer to open the compact picker. Choose
**Auto · Balance** (recommended), **Auto · Intelligence**, or **Auto · Cost**,
or pin a fixed model. Automatic routing uses the selected runner's live catalog,
never changes access, and records the chosen model, effort, request complexity,
and reason with the reply. For a fixed model, its supported effort slider saves
immediately. There is no Apply or Cancel modal. This works before or after the
first message and with custom agents. Changes affect the next message, including
after a restart; active and earlier runs keep their settings. Failed updates show
an error and restore the last confirmed selection. Conversation options control
access and retrieval.

Use the paperclip beside `@` to attach images, PDFs, audio, video, text, or code.
The app accepts up to eight files, 12 MB each and 24 MB total. It stages the
files in the owned run context, passes image paths through Codex's native image
input, and gives either runner explicit file paths for inspection. Task history
stores file name, media type, size, digest, and staged path; it does not store the
base64 request payload.
Failed replies offer **Edit and retry**, which restores the message without
submitting it or overwriting another draft. Project skills and instructions are
read by the chosen CLI in the selected project. Imported historical memory is
evidence, not automatic authority to modify the project.

Type `@` in the composer or choose its conversation attachment control to open
a large, conversation-only Spotlight picker. It starts with **All tools** and
**All projects** on the current Mac or connected server. It searches native,
imported and supported tool conversations from Codex, Claude Code, Cursor and
OpenCode. Each row shows its title, excerpt, tool, project, model and date where
available, so you can identify the source before attaching it.

Search or use the tool chips, project scope, model and agent-role filters to
narrow the list. Tool tags such as `@Codex` also narrow the picker.
**Load more conversations** continues the same search and filters. Arrow keys navigate; Return or a click
attaches a removable conversation chip, and Escape returns to the draft.
Attachment does not send a message. Up to five selected chats are cleaned,
bounded and frozen into the next run, separately from automatic retrieval.
Chat references retain their tool, title, origin, timestamp and digest in the
run record. The app never writes to the tools' original chat stores.

To use the same references inside the four coding tools, choose **Connections →
Use @ in tools → Enable in all four tools**. This installs a
versioned local runtime and one `agentic-stack` stdio MCP entry for Claude Code,
Codex, OpenCode, and Cursor. It also installs a small global
`agentic-stack-context` skill in each tool so the literal tags retain the same
meaning across projects. The MCP server provides `recall_context`, `search_conversations`,
`read_conversation`, `search_shared_memory`, `prepare_context`,
`recommend_model`, and `read_personal_memory`, plus recent chats as MCP
resources. Model and personal-memory tools are read-only and agent-facing; the
desktop configures their policy and displays provenance. The server instructions
tell agents to use `recall_context` when you ask what another agent or subagent
said, decided, found, or built, and map the four `@` names to the browsing tools. A host
that supports MCP resource completion can show those resources in its context
picker; otherwise the agent searches and presents the matching titles for you
to choose. Claude Code and OpenCode currently show the conversation resources
in their native `@` picker. Codex and Cursor accept the literal tags through the
installed skill and MCP tools because their native pickers do not expose a
third-party conversation category. Restart open tool windows after enabling.
**Remove from all four tools** deletes only the Agentic Stack MCP entries and
the managed skill files.

Each conversation turn also has an inspectable task result, with an
**Open conversation** link. Task activity, partial output, errors and final
output remain inspectable.
Requested model/effort and any model reported by Claude appear on the result.
A successful CLI result still requires review; it is not proof that a proposed
change was accepted or published. Box Cloud retains the bounded task workflow.

See [conversation design and verification](conversation-workspace.md).

## Set up and move from another tool

Open **Guided setup** from the project menu, Insights → Project tools (•••), or
Command-K. Choose a repository, select detected adapters, enter your working preferences and review
the changes. Setup preserves customized preferences and reports adapter conflicts
for manual merging. It does not silently overwrite your existing tool settings.

**Connections** shows installed apps/CLIs and supported files separately from
Codex/Claude account sign-in. Auto-detection runs on app activation and while this
screen is open; Settings can disable it. **Import knowledge… → Detected tool memory** previews the files
found for your selected tools before importing. Desktop discovery is limited to
Claude Code, Codex, OpenCode, and Cursor. Availability depends on the tool's
actual files and applications on the current host.

Use **Import knowledge… → Folder or conversation export** for portable Markdown, text, rules and JSON/JSONL exports.
Common role/content and OpenCode message exports import visible user/assistant
text with source provenance. Proprietary databases and arbitrary undocumented
formats are not universally supported; export portable files from those tools.
Account tokens are not imported. Skills are installed separately from **Skills**,
including the detected tools' supported skill directories.

## Resize and navigate

The sidebar scrolls and can be collapsed with **Command-Control-S**.
**Project → Compact / Standard / Large window** provides predictable sizes with
**Command-Option-1 / 2 / 3**; the minimum content size is 800 by 560.
The context inspector becomes a sheet in compact work layouts. Dialogs keep
their action buttons visible while content scrolls.

**Command-K** opens Spotlight with grouped **Work**, **Memory**,
**Conversations**, **Skills**, and **Actions** results. Conversation search uses
the current project by default; choose **All conversations** explicitly to
include other projects on the selected host. Arrow keys navigate, Return opens,
and Escape returns from a preview or closes search. Native conversations open
their transcript. External conversation results preview their excerpt and
source before **Attach to next message**; skill results preview the project's
instructions. Opening or attaching either does not submit a message.

The work bar keeps **Graph**, **Conversation**, **Recent work**, **Tasks**,
**Terminal**, and **Loops** visible. At narrow widths it scrolls horizontally,
so the routes remain reachable without a hidden overflow menu.
**Memory** provides Browse, Lessons, References and Exports. **Connections**
retains tool setup and project adapters. The sidebar's gear opens Settings,
including Hosting, Rules and Maintenance. Spotlight also finds these workflows
and advanced stack commands.

**Insights** retains the project dashboard. Running tasks and unreviewed results
appear first in its queue; counters filter the queue and a task row opens its
exact result. **Create task…** reviews the agent, access and context settings;
**Start task** begins execution. **Your agents** opens Codex/Claude terminals,
and **Project knowledge** shows imported file counts by source. These counts
describe imports on the current host, not live synchronization or model usage.
**Project tools (•••) → Project diagnostics** opens the collector inspector.

## Prompt agents and change the app

Choose **Terminal**, then **Open Codex**, **Open Claude Code** or
**Open shell**. The header identifies the host and project directory. These are
real interactive PTYs: agent menus, permission prompts, ANSI colors, scrolling,
copy/paste, keyboard input and terminal resizing work inside the desktop.
**Stack commands** opens the bundled project dashboard, adapter manager,
memory-transfer wizard, status, health audit, upgrade preview or Brain status.
These run the packaged stack implementation in the selected project; no separate
Agentic Stack CLI installation is needed. Management and transfer keep their
interactive previews and confirmations before making changes. The desktop and
server bundles include the onboarding modules needed by those wizards.
Use **Focus terminal** if keyboard focus is elsewhere. **Interrupt ⌃C** interrupts
the foreground command. The tab's close button stops the terminal and its shell
jobs. **⌘⇧T** returns to Terminal from any screen.

Terminal tabs survive navigation between skills, memory and tasks. Up to 12
sessions are available per host. Local sessions end when the desktop's service
exits; server sessions remain until closed or the service restarts. The service
retains at most 2 MB of recent output per session in memory. The app does not save
terminal transcripts into its graph or task history; agents and shells may still
keep their own normal session/history files. Refresh reconnects to existing
sessions after a connection interruption. Input is never automatically replayed
following an uncertain network response.

Open the source repository for this app to change its interface. Give Codex or
Claude Code a concrete prompt such as “Add a task sorting option, implement
it, and run the relevant checks.” Interactive agents use their own existing
project instructions, sign-in and permission settings. The Tasks screen's
planning/edit selector does not control a separately opened interactive terminal.

SwiftUI changes need a build and restart. From a shell in the source checkout:

```sh
swift build --package-path apps/macos -c release
python3 -m pytest -q
bash scripts/build-macos-app.sh --output ./apps/macos/dist
```

The last command creates a new app bundle and ZIP. To embed Python, add
`--python-root /path/to/standalone-python`. Open the newly built app after quitting
the running copy; a development build without embedded Python needs Python
available on its PATH. This is an edit/build/restart workflow, not live SwiftUI
hot reload. A hosted terminal edits files on the server; building the native macOS
app still requires a Mac.

## Import memory into the knowledge graph

Open a project, choose **Memory → Browse → Import memory**, and scan the selected
sources. Preview file paths and text, choose what to include, then import.
The default scan reads supported Claude Code, Codex, OpenCode, and Cursor memory,
rules, skills, and conversations, plus the project's shared Agentic Stack memory.
You can also select a memory folder. It does not execute source files or alter
the original memory. Credential stores and hidden files are excluded; detected
credential-like lines are omitted. Default scans exclude raw conversation archives
and tool logs. A chosen folder imports supported text files, so select a memory
folder rather than an entire agent installation.

The scan reports skipped files and is bounded to 1,500 files, 2 MB per file and
32 MB total. Import smaller folders to cover a larger collection. Identical note
chunks are shared across sources while retaining each source path and line.
Reimporting unchanged files is idempotent. Changed files require a fresh preview.

Enable **Claude Code conversations**, **Codex conversations**, **OpenCode
conversations**, or **Cursor conversations** to include session history. Each
batch scans up to 25 sessions per selected agent, newest first;
**Older** and **Newer** browse further batches. Session files have a 16 MB limit
and scans with conversations read up to 128 MB. Only visible user and final
assistant messages are indexed. Tool calls/results, reasoning, duplicate Codex
event records, Claude metadata messages, and nested subagent transcripts are
omitted. OpenCode is read from its SQLite database in read-only mode. Every
message retains its source and line or part position. Active sessions that
change after preview require a fresh scan; unselect them to import completed sessions.

The graph opens in **Focused** view. It hides recognizable successful tool events
that contain no reflection/evidence and generated conversation-context chunks.
Failures, substantive details, reflections and unrecognized formats stay visible.
**All imported** exposes every indexed note and explains why a routine/context
note is hidden from Focused. No note content, identifier or provenance is deleted
by this filter. Automatic task retrieval excludes these routine/context entries;
you can still explicitly choose an entry with **Use in task**.

Conversation notes use their first text line as a readable headline, with the
original session title retained under Provenance. Topic counts follow the search,
source and Focused/All filters. Shell conditionals and code examples no longer
create wiki-link topics; repository URLs with and without `.git` share one topic.
Existing graph labels/topics rebuild from saved note text on first use of the
updated service. Original memory files do not need to be read or changed.

Search uses local SQLite full-text search. Connections are literal topic mentions,
repository links and source provenance, not model-inferred factual relationships.
The graph shows up to 40 nodes from the current results; search, topic filters and
paged notes cover the full index. The default 3D view groups notes around their
providers with perspective depth. Drag to orbit, pinch or use the zoom buttons,
and reset the camera from the graph controls. A persistent 2D/3D switch preserves
the original flat map. The expand control opens a responsive full-page canvas
without resetting the camera or selected memory; Escape, Exit full page, and
View details return to the split workspace. Selecting a node opens its note and
provenance details. In Work, the context inspector lets you review, pin or
exclude that evidence; the composer remains available below the graph. The
memory browser also supports **Use in task** to create an editable task draft.
Retrieved excerpts and source references are frozen with the run and sent only
when it starts. Imported notes are explicitly presented as historical,
untrusted reference evidence.

The index is in the selected service's private SQLite data directory. Connecting
to a server selects that server's graph and memory sources; it does not upload the
Mac's memory or copy account sign-ins automatically.

## Review and export learning artifacts

**Memory → Exports** keeps reviewed Markdown handover and portable context
bundles alongside **Training, evaluation, and metrics**. Select eligible
reviewed desktop runs or existing approved project records, then choose
**Preview training & evaluation**. **Preview metrics** prepares a metrics export.

The preview shows the inputs, record and source counts, redactions, warnings,
and files to generate. Review it before **Approve & generate**. Changed inputs
require a fresh preview. Generated files stay local to the selected host and can
be opened or saved as a copy. This workflow sanitizes and exports records; it
does not train, fine-tune, or upload a model.

## Navigation audit

[Usability findings and consolidation](usability-audit.md) records the screen inventory, repeated workflows, implemented changes and remaining validation work.

## Architecture

The SwiftUI application calls the same authenticated RPC facade locally or on a
server. The facade reuses `harness_manager` adapter installation, skill manifests,
Mission Control collectors and bounded process execution. A local embedded
Python service uses a random localhost port and exits with the desktop process.
A hosted service persists independently and is not stopped when the desktop
closes. The existing unauthenticated Mission Control HTTP server is never
exposed as the hosted endpoint.

Agent tokens remain managed by their official CLIs. Provider OAuth is initiated
through those CLIs; the app does not copy account tokens or pretend to be a
separate OAuth client. Remote agent sign-in is completed on the server.

A project task runs in its actual project directory. Codex receives its selected
sandbox mode; Claude receives plan or accept-edits mode. Claude's permission mode
is not an OS filesystem sandbox. Optional source-only research runs retain
isolated context snapshots. Writing a file in the desktop uses a content digest
to reject stale edits instead of overwriting a concurrent change.

## Build and verify

Requirements: macOS 14+, Swift 6 toolchain, Python 3.10+ for an unbundled build.

```sh
./install.sh desktop --build
python3 -m pytest -q
python3 scripts/check-desktop-connection.py
```

To embed a relocatable Python distribution:

```sh
./install.sh desktop --build --python-root /path/to/standalone-python --output /path/to/output
```

The build produces `Agentic Stack.app` and `Agentic Stack-macOS.zip`. It signs
outside File Provider directories and creates the ZIP before Finder metadata
can be attached. Distribute the ZIP. Apple Developer ID signing and notarization
are separate release steps; this preview uses ad-hoc signing by default.

[Hosting instructions](../deploy/agentic-stack/README.md) include Docker Compose,
persistent volumes, official agent login, domain/TLS requirements and an SSH
option. Hosted deployments are single-owner administrative services, not a
multi-tenant SaaS.

## Verification from earlier previews

The following records describe earlier preview checks; they are not a fresh
validation of this candidate. See the [preview 7 candidate notes](releases/v0.19.1-desktop-preview.7.md)
for current checks and remaining release gates.

- On a private copy of the 7,095-note graph, Focused retained 6,239 notes and hid
  833 routine-event chunks plus 23 generated-context notes. Hashes of all saved
  note bodies, IDs, sources and origins were unchanged. Topic repair removed the
  shell-expression topic and duplicate repository `.git` topics. The live graph
  received this update in the earlier verified build; native inspection confirmed those counts.

- Native embedded Codex and Claude Code prompts were inspected. A shell command
  returned its expected marker, project path and terminal size. Navigating away
  and returning preserved the session. PTY tests cover Ctrl-C, background job
  cleanup, binary output, duplicate requests, bounded replay and authenticated RPC.
- The Swift bridge rejects terminal input for a stale host before transport.
- The extracted server package passed real Linux PTY input, output, controlling
  terminal, resize, Ctrl-C and background-job cleanup through authenticated Caddy
  HTTPS. Its adapter manager and transfer wizard opened interactively. Projects
  persisted after restart and all disposable test resources were removed.

- Real Codex and Claude Code project tasks read an existing source file and
  returned its expected value, without changing project instructions.
- Real subprocess-hosted RPC authenticated requests, rejected invalid tokens and
  browser origins, enforced the project root, and retained projects after restart.
- The compiled native Swift bridge connected to the live RPC service, handled an
  invalid token, rejected redirects, and sent zero requests to the redirect target.
- Python checks cover source review, persistence, cloud retry/failure behavior,
  cancellation, adapter preservation, skill support files, project execution and
  concurrent file edits. Build-specific counts are in the delivery notes.
- Native project, skills, hosting, loop completion and memory acceptance screens
  were inspected. The graph import, cross-agent search, provenance and task handoff were also verified in the native window.
- The saved local graph contains 7,095 notes after parser cleanup and conversation import. The original
  import and a refresh were performed through the native UI. Detected credential-like
  content was omitted and original source files were preserved. An additional 42
  Codex and Claude Code conversation files added 350 notes through the native UI;
  source filters, JSONL provenance and task drafting were verified.
- The standalone server archive boots after extraction without the original checkout.
- A native server connection and archive export were verified; the server remained
  available after the desktop quit.
- Codex and Claude Code each read a frozen graph reference and returned its synthetic
  verification code in real agent runs.
- Credential access runs on a serial background queue. An unavailable Keychain item
  returns an error without blocking the UI; the desktop can return to local mode.
- The packaged Docker image was built and run as a non-root user in an isolated
  Linux VM. Authenticated readiness, wrong-token rejection, persistence after
  container restart and HTTPS through Caddy with an explicit test CA passed.
- Codex's nested Linux sandbox passed read-only and workspace-write tests with
  the dedicated AppArmor and seccomp profiles, including project boundaries,
  protected Git/Codex paths and direct network denial. The service remains
  non-root with no-new-privileges and no added capabilities.
- Public deployment, external certificate issuance and live Box execution remain
  unverified.

## Design sources

Native SF typography, SF Symbols and semantic system surfaces with a restrained
warm orange accent. Taste v2 informs hierarchy and restraint; SwiftUI determines
platform controls.

- [SwiftTerm terminal engine, pinned to 1.19.0](https://github.com/migueldeicaza/SwiftTerm/tree/v1.19.0)
- [Taste skill](https://github.com/Leonxlnx/taste-skill)
- [SwiftUI Agent Skill](https://github.com/AvdLee/SwiftUI-Agent-Skill)
- [Appllama public skills](https://github.com/Appllama/appllama-skills)

Appllama MCP access was blocked by its Pro subscription screen. Public guidance
was used; no claim of live MCP design research is made.

## Skill compatibility

Bundled skills include the metadata required by Codex and Claude Code. For older
projects, **Skills → Repair bundled skill compatibility** updates descriptions
only when the file still exactly matches the old bundled version. Customized
skills are preserved. The catalog labels installed skills and prevents duplicate
installation; project lists refresh after setup.

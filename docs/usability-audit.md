# Native app usability audit — September 8, 2026

This is an expert inspection of the running app and its source, not a user study. The original navigation exposed 16 destinations. The most consequential problem was that the app followed backend modules instead of user workflows.

## Findings and changes

| Priority | Finding | Resulting change |
| --- | --- | --- |
| P1 | Activity showed an empty legacy collector table and told users to look in Tasks. It did not represent native task activity. | Removed the separate Activity screen. Tasks now owns searchable, filterable task history, including running work and reviews. Legacy project events remain advanced diagnostics under Settings → Maintenance. |
| P1 | Agents installed adapters, while Integrations managed the same tools' accounts and migration. | One Tools workspace with Connections and Project adapters. Clearer adapter names and search. |
| P1 | Knowledge graph, Memory, References and Handover appeared as unrelated peers. | One prominent Knowledge Graph workspace: Graph, Lessons, References and Export. Their different authorization semantics remain intact. |
| P1 | Six configuration destinations competed with daily work. | Settings contains General, Hosting, Rules and Maintenance. Daily navigation contains agent conversations, Tasks, Terminal, Knowledge, Skills, Tools and Settings; Dashboard is a secondary project overview. |
| P1 | Protocols showed the full harness verification matrix twice, including failed checks for unconfigured adapters. | Rules focuses on editable rules and optional permission details. Project health data lives in advanced Maintenance diagnostics. |
| P1 | Wide fixed-size editors/import dialogs could expand the parent window. | Editors, skill catalog, onboarding, migration and task forms size to the current document window; long forms scroll. |
| P2 | Task history had no search or status filters; completed work and active work shared an undifferentiated list. | Search, All/Active/Needs review/Finished filters, newest-first ordering, visible counts, empty-filter recovery and exact result selection. |
| P2 | Skills and adapters required scrolling and repeated Read/Edit actions. | Added search to both; adapter implementation detail is collapsed. |
| P2 | Repeated marketing headings and sample prompts consumed workspace space. | Shortened Terminal, Connections, Lessons and Hosting introductions. Kept operational instructions close to the relevant action. |
| P2 | Settings duplicated navigation links and showed optional cloud credential controls immediately. | Removed redundant navigation blocks; optional Box credentials are collapsed. |
| P2 | Several page states were keyed only by project ID, risking confusing state when hosts change. | Key affected task, loop, memory, graph and configuration views by host and project. |

## What belongs together, and what stays distinct

Tasks and Terminal are complementary: Tasks preserves bounded run results and reviews; Terminal is an interactive CLI. Loops belongs under Tasks because it is verified, contract-bound work with its own run history.

The knowledge workflows share navigation, not a single undifferentiated database. Library imports historical reference with provenance. Lessons require an explicit acceptance decision before guiding future work. References require review before inclusion in tasks. Export carries reviewed references. Merging those authorization states would change behavior and hide meaningful distinctions, so those safeguards remain.

Conversations are now the default workspace. Custom agent profiles share the same project tools and history. Dashboard remains the only overview, accessible from the Project menu or Command-K. Its status counters and shortcuts intentionally summarize the same underlying objects; they are entry points into the canonical workspaces. Maintenance's diagnostic disclosures are inspections, not a second dashboard.

## Inspection inventory

All original screens were opened in the native app: Dashboard, Tasks, Terminal, Loops, Activity, Knowledge graph, Memory, Skills, References, Handover, Agents, Protocols, Maintenance, Integrations, Hosting and Settings. Their data sources, deep links, forms and command-palette routes were inspected in code. Verification of the resulting native routes and dialogs is recorded separately in Verification.txt.

## Heuristic assessment

Subjective 0–4 expert scores (4 = excellent); these are not measured user outcomes.

| Heuristic | Before | Key issue |
| --- | ---: | --- |
| System status | 2 | Activity omitted actual app task history. |
| Match to user language | 2 | Agents/adapters, memory/knowledge, and backend terminology required interpretation. |
| User control | 3 | Core cancel/review paths existed; dialog sizes disrupted navigation. |
| Consistency | 1 | Tasks/runs and several overlapping navigation destinations. |
| Error prevention | 3 | Existing import previews, source review, stale-file checks and bounded runs. |
| Recognition | 2 | Users had to remember which of several memory/tool screens did what. |
| Efficiency | 2 | Keyboard search existed; task and installed-skill search did not. |
| Minimalism | 1 | Sixteen sidebar entries, duplicated diagnostics and repeated introductions. |
| Error recovery | 3 | Most backend failures had surfaced errors; empty Activity was a dead end. |
| Help | 2 | Guides existed but some copy referred to old Operations/Activity navigation. |
| Total | 21/40 | Significant usability cleanup required. |

The cognitive-load checklist initially failed chunking, minimal choices, progressive disclosure, grouping and recognition across screens: 5 of 8 items. The consolidation addresses those failures at navigation level. It does not establish that every complex migration or permission decision is simple.

## Persona checks

- Power user: previously had to scan 16 destinations and could not search saved tasks or installed skills. Command-K now exposes full destination paths, and work lists have search/filter controls.
- First-time user: previously saw “Agents” and “Integrations,” plus four separate kinds of knowledge, without a clear relationship. Grouped destinations and task-focused labels explain the differences.
- Keyboard/assistive-technology user: native sidebar selection and labeled buttons are retained. Secondary navigation announces selection. Compact dialogs have reachable controls. A complete VoiceOver and keyboard-only acceptance pass remains additional validation work.

## Remaining product work

- Validate onboarding and a real migration with people who have not seen the app. Measure completion and where they hesitate; this inspection cannot establish adoption or demand.
- Streaming task output and persistent Codex/Claude conversations are now implemented. Profile/model execution and session resumption have been tested against real CLIs.
- Proprietary editor databases still require supported exports. Migration is not universal.
- Imported notes retain sources/topics; connections do not establish semantic truth. Search ranking and knowledge curation can be improved after observing actual use.

## Conversation-first follow-up

The reference was applied as a desktop conversation workspace: agents and project
conversations in the sidebar, a restrained agent header, a wide scrolling
transcript and a fixed composer. Custom agents are persistent profiles, not new
control-center pages. Tasks is the canonical execution/review history; Knowledge,
Skills and Tools remain shared project resources.

Detailed checks covered profile creation/editing, real model/effort execution,
CLI session resumption, streamed output, compact chat/task layouts and saved
conversation navigation. Modal sizing now finds the document window even when
macOS temporarily has no main window. Agent creation is also available through
a keyboard shortcut and the command palette.

The earlier sixteen-screen inventory remains the scope of the full expert
inspection. This follow-up rechecks the changed workflows and records precise
limits in conversation-workspace.md and the delivered Verification.txt. It does
not claim exhaustive testing of every external provider or proprietary format.

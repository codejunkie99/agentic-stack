# Conversation workspace — September 8, 2026

## Design decision

The user chose conversations with agents as the primary workspace, based on the
provided desktop chat reference. Agent profiles and project conversations form
the sidebar’s first two groups. A restrained header identifies the current agent
and conversation. The transcript scrolls independently of a bottom composer.
Tasks, Terminal, Knowledge, Skills, Tools and Settings remain shared workspaces;
there is no dashboard for each agent. The project overview is secondary.

## Screen-by-screen behavior

| Surface | Actions and states | Where related work belongs |
| --- | --- | --- |
| Agents | Create, edit, choose runner/model/effort/access, archive, restore; instructions required; validation errors remain in the form | Profiles apply across projects on the selected host; settings snapshot at conversation creation |
| Conversations | New message, follow-up, stream, stop, inspect activity, view task, save reference, search history; empty/waiting/error/partial/final states | Project-scoped sessions; actual CLI resumption; model/effort change for the next message; runner/access/role stay fixed |
| Tasks | Search, status filter, exact result selection, partial/final output, review, save reference, return to conversation | Task history is the canonical execution record; Activity is not a competing page |
| Loops | Contract, execution limits, run/resume/stop and checkpoints | Secondary task tab; independent verifier workflow |
| Terminal | Interactive agent/shell tabs, resize, interrupt, close, bundled stack commands | CLI-only advanced features remain here |
| Knowledge Graph: Graph | Preview source files, import chosen records, filter/search, inspect note provenance and topic links, use in task | Historical evidence, deduplicated with origins retained |
| Knowledge: Lessons | Stage/accept/reject/reopen/retract with reasons; project memory files | Explicit lesson decisions, separate from imported reference history |
| Knowledge: References | Import/paste, inspect, approve or unapprove sources | Only reviewed sources enter reviewed handovers |
| Knowledge: Export | Reviewed Markdown and portable bundles | Uses the same reviewed source records |
| Skills | Search installed skills, read/edit, browse supported local/shared catalog, install support files | Project skills are available to the selected CLI |
| Tools: Connections | Detect 18 supported tools, inspect status, official Codex/Claude login, preview migration | Reuses official sign-in; never imports account tokens |
| Tools: Project adapters | Search/install 13 adapter manifests and inspect configuration | Terminal manager handles advanced removal/reconfiguration |
| Settings: General | Appearance, auto-detect and service settings | Host and project identities stay visible |
| Settings: Hosting | Export package, authenticated HTTPS/localhost connection, return to this Mac | Single-owner backend for the native app; no separate browser frontend |
| Settings: Rules | Read/edit project protocols with stale-file protection | Shared project rules, not per-agent dashboards |
| Settings: Maintenance | Doctor, manifest refresh, upgrades and advanced diagnostics | Legacy collector tables remain collapsed here |
| Guided setup | Project → tools → preferences → review → ready | Preserve customized files; start a conversation after setup |
| Project dashboard | Work queue and summary links | One secondary overview, available from Project menu and Command-K |

## Implementation and verification evidence

- Native release build succeeds. The full Python suite passes: 287 tests.
- Real Codex and Claude conversations each resumed the same CLI session and
  recalled a token supplied only in the preceding turn.
- A profile created through native UI selected GPT-5.6-Luna, low effort and
  read-only access. The resulting Codex `turn_context` independently confirmed
  all three, and the final reply followed the saved profile instructions.
- A real Claude custom profile using Sonnet and low effort replied naturally to a greeting and followed its saved response instructions. Conversation prompts no longer require a work plan for casual chat.
- Automated checks cover profile persistence, edit/archive/restore, invalid
  values, configured catalog/cache parsing, exact CLI flags for both runners, immutable
  historical run settings and continuation after profile archival.
- Stream checks cover progress before process exit, incremental UTF-8 output,
  malformed/oversized records, cancellation, partial results and omission of
  reasoning, raw tool payloads and account metadata from app activity.
- Custom agent edits, saved history, keyboard creation, compact dialog sizing,
  navigation and onboarding are exercised in an isolated native test library.
  Final packaging and main-library preservation are recorded in Verification.txt.

## Bounds

This is a working native development preview. Provider model availability comes
from the user’s existing account/configuration. Claude aliases are not an account
entitlement query. A manual model ID may be rejected by its provider; the actual
runner error is shown. Successful model execution does not guarantee the quality
of its work. Box live billing/lifecycle verification, universal proprietary-tool
migration, a complete VoiceOver pass and a first-time-user study are outstanding.
Developer ID signing/notarization are required for frictionless public release.

The model controls follow the official [Claude model configuration](https://code.claude.com/docs/en/model-config)
and [Claude programmatic usage](https://code.claude.com/docs/en/headless), plus the
installed Codex CLI’s own help and configured catalog/cache. Agent tokens remain with the CLIs.
Appllama’s Screens page was inspected as a design-reference library; it is not a
hosted instance of Agentic Stack, and its entire commercial catalog was not audited.

The September 8 model and workflow fixes, live evidence, competitor patterns,
and verification limits are recorded in [Model workflows](model-workflows.md).

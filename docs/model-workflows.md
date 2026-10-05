# Model selection and workflow verification — September 8, 2026

## Changes

The model selector lives beside the conversation composer. It can pin a model
and supported reasoning effort or configure automatic routing for cost, balance,
or intelligence. Auto routing classifies each message against the current
runner's live catalog and records its chosen model, effort, complexity, and
reason. It never changes runner, account, file access, or the active session.
The same read-only recommendation is available to coding agents through the
installed Agentic Stack MCP service. Cancel preserves the current choice. Profile
defaults, project identity, instructions and file access remain separate.
Active and historical runs retain their original settings. Model preferences
for unsent conversations are scoped to the host, project and selected agent.
Changing navigation while a message starts no longer pulls the user back.

Codex model discovery respects `model_catalog_json` in the selected host's
configuration. It falls back to the model cache and supports manual IDs. Refresh
and fallback notices are visible. The task form keeps its fixed-model picker;
conversation routing stays in the compact composer control.

Claude receives the run's context directory as an allowed directory, fixing
resumed messages that could not read the new brief. Runner default explicitly
resets Claude's model instead of restoring the prior choice. Requested settings
and Claude's reported model appear with the reply. Structured runner errors
take precedence over unrelated startup diagnostics. Edit and retry restores a
failed message to an empty composer without automatically sending it.

All 14 bundled skills now have descriptions required by the coding tools.
Skills marks installed entries, prevents repeated installation, and refreshes
after onboarding. Repair bundled skill compatibility updates unchanged legacy
bundled files only. It preserves customized files. Compact task layouts give
the selected result more room.

## Patterns checked in other products

| Reference | Useful pattern | Applied here |
| --- | --- | --- |
| [OpenCode models](https://opencode.ai/docs/models/) | Model choice is directly accessible during work; configured providers supply choices | Composer model button, configured Codex catalog, manual IDs |
| [OpenCode agents](https://opencode.ai/docs/agents/) | Agent role, tools and model settings are distinct | Persistent role defaults plus an explicit next-message model override |
| [Continue customization](https://docs.continue.dev/customize/overview) | Agent controls sit near the composer, with configuration available nearby | Model selection in the composer and agent editing in the conversation header |
| [Claude model configuration](https://code.claude.com/docs/en/model-config) | Resumption and explicit model overrides have different behavior | Preserve the session ID while passing the chosen model for each turn |
| [Cursor Router](https://prod.cursor.com/docs/cursor-router) | Auto selection exposes cost, balance, and intelligence policies while routing each request independently | Three explicit auto policies with an inspectable per-run decision |
| [Codex models](https://developers.openai.com/codex/models) | Model and reasoning effort are compact controls next to the composer | Fixed-model effort remains model-specific and immediately applied |

## Multimodal and personal context

The composer accepts bounded images, PDFs, audio, video, text, and code. The
service validates type and size, hashes each file, and stages it into the run's
owned context. Codex receives images through its native image flag; all supported
files are listed by absolute staged path in the agent brief. The run record keeps
metadata and provenance rather than encoded file data.

The installed MCP bridge also exposes a read-only personal-memory tool. It keeps
static preferences separate from dynamic current-work state, then returns only
relevant bounded sections. Shared graph search remains a separate tool so agents
can distinguish personal context from imported historical evidence.

These references informed interaction design. This is not a claim of feature
parity with every product or of an audit of their private implementation. The
reference named “RKA” could not be identified from the supplied name.

## Verification

- Real Codex conversation switched from GPT-5.6-Luna/low to GPT-5.4-Mini/medium
  in the same session. Codex's saved turn metadata confirmed both models,
  efforts, read-only access and the selected fixture project.
- Real Claude conversation retained its session and recalled an earlier
  phrase after switching from Sonnet to Opus. Its messages reported
  `claude-sonnet-5` and `claude-opus-5`. A Haiku request reported Sonnet in this
  account; reported models are exposed rather than assuming alias resolution.
- A native custom agent retained its required closing word through the model
  switch. Selected model and completed history survived application restart.
- Native memory preview/import produced a searchable note with its original
  path and line number. A real conversation retrieved that note and cited its
  ID in the answer. The original fixture file remained unchanged.
- A completed result was saved as a reference, reviewed, and appeared in the
  export with its source ID, digest and line citation.
- A real terminal accepted a command, displayed its result, and closed. Tool
  detection found signed-in Codex and Claude. Settings and hosting controls
  were inspected at compact desktop size.
- Automated checks cover model changes while a run is active, history
  immutability, profile defaults, invalid configurations, host authentication
  and persistence, catalog recovery, reported-model filtering, skill metadata,
  preservation of customized skills, and error selection.

Final test totals, packaging checks and the native recovery check are recorded
in the delivered Verification.txt. All acceptance tasks used isolated fixtures;
they were not imported into the main library.

## Remaining limits

Model availability, alias resolution and account effort caps are controlled by
the provider. This app does not bypass them. External MCP servers still need
their own valid connections. The native backend hosting path is tested locally;
live Box lifecycle/billing is not verified. Migration supports detected portable
files and supported conversation exports, not every proprietary tool database.
Developer ID signing/notarization, a full VoiceOver pass and first-time-user
research remain public-release work.

# Jev-first context workbench

The desktop workbench, agent context preparation, and read-only MCP bridge use one host-owned planner. Local project search supplies bounded candidates; Jev supplies typed semantic decisions. The host owns exact source text, scope, token budgets, permissions, and durable writes.

## One decision wave

One logical evaluation batch using `POST https://api.typesafe.ai/v1/systemone` shares a bounded state across independent Choice, Score, and Noul questions. Existing bounded transport retries can issue additional HTTP attempts; `providerCalls` counts logical batches. Candidate instructions identify their index explicitly: outer question IDs are response routing keys, not model-visible instructions. Relevance scores order evidence; context choices decide inclusion; memory choices recommend remembering or forgetting. `none` is an ordinary supplied Choice option. Low confidence and unsupported decisions do not authorize changes.

The host collects current excerpts, explicitly added content, and eligible project sources before that request. Additional source pages or external tool results require another dependency wave; no model can select unseen text in the first wave. Coverage must expose that ceiling instead of claiming exhaustive recall.

Choice selects supplied labels. Score places evidence on a descriptive ordered scale. Noul reports a probability for a yes/no statement. Jev does not generate prose: the summary and context pack are assembled from selected exact source excerpts, with provenance and honest truncation.

## Context and durable memory

Keeping or evicting an excerpt changes the proposed working context. It does not accept or retract its durable memory. A memory write is a separate reviewed operation. Adding records exact supporting evidence and a claim; forgetting retracts the targeted accepted claim from future retrieval while preserving evidence and audit history.

`memory.context.plan` supports `recall`, `add`, `forget`, and `update`. An explicit `update` requires both incoming passages and target IDs, so one batch can recommend remembering exact new evidence and forgetting the specified old accepted claims. An update is unapplicable unless every explicit target and incoming passage receives its authorized operation in the same bounded batch; omitted or declined operations withhold the entire durable update. The existing reviewed apply commits the complete update together; ranker confidence never authorizes a write. The native workbench exposes focused add and forget flows, while combined update is available through RPC/MCP planning.

Plans are read-only and bound to a workspace and source versions. Apply revalidates those versions, commits all memory changes and an idempotency receipt together, and rejects stale plans. Unapplied plans expire after ten minutes; committed receipts survive restart. System instructions, user corrections, and host execution state are host-owned; a memory model cannot remove their authority. Hosts must preserve `retainedIds`, including `retainedOutsideBudgetIds` separately: `contextText` is a bounded projection, not a complete replacement when protected active context exceeds the budget.

The bridge returns a context plan. A connected host must consume it when assembling a new request or compacting its own session. MCP cannot erase tokens already submitted to Codex, Cursor, Claude Code, or OpenCode. The supported integration surface is project-scoped context preparation and source discovery; arbitrary installed applications do not automatically become connected sources.

## Native behavior

The SwiftUI workbench uses quiet navigation, consistent spacing, flat source rows, comfortable bounded prose, stable loading and action geometry, and persistent draft/selection state. Provider failure, empty results, abstention, and pending requests are visible states. Synthetic fixtures exercise production controls without opening real conversations or modifying user memories.

## Search and Ultra-fast context

Command-K content search defaults to **Ultra-fast (Jev)** when the selected host reports a configured, enabled provider with hosted-processing consent; otherwise it defaults to **Local search**. Explicit user mode choices remain intact, and unavailable Jev modes require setup rather than silently substituting local results. `search.context` searches reviewed project memories, imported evidence, approved sources, and project conversations through the canonical planner. Jev can select useful candidates outside exact keyword matches from the supplied bounded shortlist. Results preserve exact text, source identities, and confidence; opening a result shows its original evidence projection. Work navigation and application actions remain immediate local operations.

Ultra-fast uses at most eight candidates in one batch: one relevance Score and one context Choice per candidate, plus a global Noul gate. Read-only recall omits constant durable-memory questions, which the host resolves to `none`. Recall questions assess whether an exact quotation is useful reference evidence, not whether it answers the entire task. Quoting a recorded instruction neither executes it nor establishes that its claim is true; uncertainty still permits abstention. Standard Jev uses up to sixteen candidates. A short deadline bounds decision work; synchronous source discovery cannot be preempted, so the deadline is not an end-to-end latency guarantee.

Read-only results may be reused for sixty seconds in a bounded sixty-four-entry cache. Every lookup checks current candidate text, status, review versions, scope, query, exclusions, pins, and provider identity. Selected sources are revalidated before delivery. Credential, consent, model, source, and review changes invalidate reuse; durable changes and active-context replacement plans never enter this cache. Cache hits show zero new provider calls, not a new hosted decision.

The native search status shows request timing, cache status, provider calls, and bounded coverage. Request timing is distinct from hosted model latency. Scripted native fixtures are explicitly marked synthetic. The `jev-fast` context mode is selectable in run/context controls and uses the same planner and cache. Explicit Local search remains available for global browsing and tool/role/model filters; unsupported Jev filters never silently narrow scope or trigger a local substitute.

Earlier isolated checks covered native pending-search cancellation, keyboard source opening, draft/selection restoration, light/dark appearances, compact layout, cache indicators, and unavailable states. Those scripted fixtures remain evidence of UI behavior, not hosted model speed.

A later live hosted demonstration used three synthetic claims. The correct SQLite reference was selected in one logical batch: the cold backend service request, including network time, took **378.03 ms**; a repeated request took **3.44 ms** with zero new provider calls. A separate explicit-query demonstration measured **434.84 ms** cold and **3.44 ms** warm. These are individual measurements on a tiny synthetic corpus, not general retrieval-quality, production-latency, or end-to-end native UI benchmarks.

## Five read-only runtime operations

The workspace RPC and MCP bridge share `JevRuntime`. Each bounded page uses one provider request; later pages are separate dependency waves. No operation executes a tool or edits its source input.

| RPC method | MCP tool | Input and result |
| --- | --- | --- |
| `memory.trace.compact` | `compact_trace` | Task, trace body, token budget, optional cursor. Returns selected original spans with offsets and digests, plus an extractive context projection. The original trace remains intact. |
| `memory.skills.select` | `select_skills` | Task and host-supplied whole skills with declared dependency IDs. Returns useful complete instruction units and their dependency closure. Missing, cyclic, or over-budget units are withheld rather than rewritten. |
| `memory.tools.plan` | `plan_tools` | Task and host-authored candidate function calls. Validates complete arguments against a host-owned schema catalog before Jev selects a call or `none`, then revalidates the selection. Returns a plan for host authorization and execution. |
| `memory.citations.verify` | `verify_citations` | Claim and supplied evidence with provenance. Returns supports, contradicts, insufficient, or none, together with exact evidence and pair digests. This assesses evidence support; it does not establish independent factual truth. |
| `memory.code.search` | `search_code` | Task and exact supplied snippets, or a host-bound attached project. Jev evaluates code behavior without requiring task keyword matches. Returns exact ranked source spans, hashes, and bounded coverage. |

Code discovery excludes private-looking filenames, hidden and dependency/build trees, symlinks, oversized files, and detected credentials. It is a bounded native semantic adapter, not an invocation of the external [`jg` Jevgrep CLI](https://github.com/dzhng/jevgrep). Discovery ceilings are visible; a bounded page is not an indexed repository-wide search.

Tool planning uses the bridge's allowlisted catalog. It cannot invent arbitrary arguments or discover every installed connector. Hosts can supply their own validated catalogs through the shared runtime; additional connected-tool output must enter as authorized source candidates before another decision wave.

For example, a workspace trace request has this shape:

```json
{
  "method": "memory.trace.compact",
  "params": {
    "workspaceId": "<attached workspace>",
    "task": "Keep the release decision and its supporting evidence",
    "body": "<original agent trace>",
    "tokenBudget": 2048,
    "cursor": 0
  }
}
```

The existing unscoped `recall_context` and `search_conversations` tools remain explicit read-only browsing tools. Scoped `prepare_context` and `plan_context` use the canonical Jev planner. Jev-mode run handovers carry source metadata; selected source bodies arrive through the bounded context pack.

## Provider and proof boundaries

Hosted processing requires explicit provider configuration and consent. Settings and the search provider action open the same host-scoped key form; users can connect, replace the key, or disconnect later without leaving their search draft. The saved key is never displayed. “Configured” indicates saved setup and permission, not a successful authentication check. Jev requests send the included task and excerpts to TypeSafe. Missing setup, rejection, cancellation, and malformed responses must not silently become semantic selections or memory writes. Explicit local retrieval remains a separate mode.

Scripted provider tests establish protocol, provenance, budgets, stale-plan rejection, and transaction behavior. Native fixture inspection establishes layout and input behavior. Neither alone establishes live authentication, model quality, retrieval quality, or arbitrary host context control. The separate live synthetic demonstration above establishes only that its specific requests succeeded and selected the expected reference.

Earlier local verification on 2026-09-30 included Python core/runtime checks, a Swift release build, and native state checks. Final revision counts belong in the release verification record. Actual native inspection covered dark/light appearance, wide/narrow layouts, keyboard source navigation, exact context inspection, forget target selection, review dismissal, cancellation, and unavailable states. The installed release binary also opened successfully in an isolated fixture.

The bundled Python runtime passed isolated atomic apply and all five RPC/MCP operations with a scripted provider. Earlier packaged artifacts passed ZIP integrity, DMG checksum, and ad-hoc signature checks; subsequent source changes require fresh packaging verification. No notarization is claimed. Live hosted evidence is limited to the synthetic measurements described above. The previous installed app was preserved as a backup. Real user memory and conversation state were not opened or modified during those fixture checks.

Primary sources checked on 2026-09-30:

- [API](https://docs.typesafe.ai/api)
- [Typed primitives and batching](https://docs.typesafe.ai/primitives)
- [Choice](https://docs.typesafe.ai/primitives/choice), [Score](https://docs.typesafe.ai/primitives/score), [Noul](https://docs.typesafe.ai/primitives/noul)
- [Confidence](https://docs.typesafe.ai/confidence)
- [Models and data handling](https://docs.typesafe.ai/models)
- [Python SDK retry policy](https://docs.typesafe.ai/sdk/python/api/retries)

# Orchestration

Authoritative server-side orchestration surface. Read this only when the runtime exposes `supports_subagents=true`.

## Capability Contract

The skill branches on runtime capabilities, not product names.

Use these fields:

- `workflow_mode` — `sequential` or `orchestrated`
- `supports_subagents`
- `supports_local_fs`
- `supports_workspace_persistence`
- `supports_rendered_image_review`
- `visual_qa_ready`

If `supports_subagents` is false, fall back to the sequential Plan -> Build -> QA workflow with the same two user checkpoints.

## Parent Orchestrator Responsibilities

The parent orchestrator always owns:

- template selection
- deck storyline and section rhythm
- title-length compliance at approval time
- no-repeat and single-topic checks
- user checkpoints
- final deck assembly
- cross-deck QA reduction
- final delivery and legal disclaimer

Sub-agents may assist, but they do not replace the parent contract.

## Handoff Artifacts

Use structured artifacts between workers. The minimum set is:

- `DeckRequest`
- `DeckPlan`
- `SlideSpec`
- `WorkerAssignment`
- `SlideArtifact`
- `QAFinding`
- `FixBatch`

Do not pass free-form, growing conversation state between workers when a structured artifact will do.

## Planning Fan-Out

Planning remains central until the parent agent locks:

- audience
- objective
- recommendation
- slide count
- section structure

Once the storyline is locked, slide-level enrichment may fan out:

- chart evidence decisions
- framework/process family routing
- reference-file selection
- icon type decisions

Each planning worker should own a bounded slice:

- one slide
- one section
- or one semantic family

The parent planner reduces the results back into one approved `DeckPlan`.

## Build Fan-Out

Never let multiple workers mutate the same unpacked PPTX tree.

In orchestrated mode:

1. parent converts the approved plan into normalized `SlideSpec[]`
2. workers render isolated slide artifacts or isolated mini-decks in separate workdirs
3. parent reducer assembles the final `.pptx`

Centralized build-only responsibilities:

- slide numbering
- `rId` allocation
- media dedupe/copy
- relationship rewrites
- final package writes

## QA Fan-Out

Programmatic and visual QA may fan out by slide.

Worker-safe QA tasks:

- per-slide rendered-image inspection
- per-slide issue annotation
- per-slide remediation proposals

Centralized QA tasks:

- cross-deck consistency checks
- package integrity checks
- fix batching
- rerender/reassemble decisions
- final blocking decision

## Worker Roles

Recommended worker roles:

- `planner` — slide-level enrichment after storyline lock
- `builder` — isolated slide rendering
- `qa-inspector` — per-slide rendered-image review
- `template-manager` — optional `.ee4p` persistence and template lifecycle work

## Routing Guidance

When fanning out slide work, group by the primary semantic family:

- charts
- frameworks
- process
- layouts / split families

Prefer one family index plus only the needed leaf docs per worker. Do not load all families into every worker.

## Fix Loop

The parent agent owns the fix loop:

1. collect `QAFinding[]`
2. reduce to one `FixBatch`
3. rerender only changed slide artifacts when possible
4. reassemble
5. rerun deck-level QA

The orchestrated loop must still present a single QA checkpoint to the user after blocking issues are cleared.

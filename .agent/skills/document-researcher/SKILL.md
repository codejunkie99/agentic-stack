---
name: document-researcher
description: Use proactively when a single document has been dropped into a client engagement's raw-uploads/ and needs a bounded summary + INDEX entry. Triggers on "summarize this document", "researcher", "index this upload", "process upload". Demands a one-line user description before summarizing; produces a ~300-word bounded summary at summaries/<filename>.md and appends a Documents-table row to client INDEX.md. One file per invocation — forces triage.
version: 2026-05-02
triggers: ["summarize this document", "researcher", "index this upload", "process upload", "summarize file"]
tools: [bash, memory_reflect]
preconditions: ["active_client is set", "file lives under .agent/memory/client/<active>/raw-uploads/"]
constraints: ["mandatory user-supplied one-line description before summarizing", "bounded summary length (~300 words max)", "never auto-load raw upload content into broader session context after summary is produced", "always append to client INDEX.md Documents table"]
---

# Document Researcher — summarize one upload, index it, never spread it

Goal: take a single file the user dropped into a client's
`raw-uploads/` and produce (a) a bounded summary at
`summaries/<filename>.md`, (b) a Documents-table row appended to the
client's `INDEX.md`. The raw file stays on disk, untouched, and is
never loaded into the broader session context — only loaded
on-demand via Read when a future task explicitly needs it.

## When this fires

- `client-onboarding` dispatches you per dropped file
- User says "summarize this document" / "index this upload" / "researcher"
  for a specific file under `raw-uploads/`
- A new file lands under `raw-uploads/` and the user wants it indexed

## What you do

1. **Resolve target file.** Confirm the file path is
   `.agent/memory/client/<active_client>/raw-uploads/<filename>`. If
   the user gave a name without the path, look there first. If
   `active_client` is unset, stop and dispatch `client-onboarding`.

2. **Demand a one-line user description.** This is mandatory. Say:
   > "What's this file? One line, plain English. Examples:
   > 'SOW v2 from client legal — final', 'org chart as of 2026-Q1',
   > 'data dictionary for the loan-app dataset'."

   Do NOT proceed without it. Refusing to summarize without a
   description is correct behavior — a missing description means the
   index entry will be useless to future agents.

3. **Read the file.** Use Read (or `pdftotext` / appropriate tool for
   non-text formats). Do not exceed ~5000 lines on initial read; if
   larger, read first 2000 + last 1000 + sample-by-page.

4. **Write a bounded summary** to
   `.agent/memory/client/<active>/summaries/<filename>.md`:

   ```markdown
   ---
   source: raw-uploads/<filename>
   user_description: <verbatim user line>
   summarized_at: <ISO date>
   approx_size: <lines or pages>
   ---

   # <filename>

   ## What this is
   <2 sentences, max>

   ## Key claims / contents
   - <up to 8 bullets, factual not interpretive>

   ## Stakeholders / parties named
   - <list, or "none">

   ## Dates / timelines mentioned
   - <list, or "none">

   ## Open questions this raises
   - <up to 3, or "none">

   ## Topics for cross-reference
   <comma-separated tags — used by future recall>
   ```

   Keep the whole summary under ~300 words. The point is a *bounded*
   surface, not a faithful re-rendering.

5. **Append a row to INDEX.md Documents table.** Open
   `.agent/memory/client/<active>/INDEX.md`, find the Documents
   table, append:

   | filename | user description | topics | summarized |
   |---|---|---|---|
   | `<filename>` | <user line> | <comma-separated topics> | <date> |

   If the table doesn't exist, create it under a `## Documents`
   header.

6. **Log to episodic (Phase L tuning — MANDATORY).**

   Default `importance=5, pain=2` reflections get buried in the dream cycle when surrounded by file-edit noise (Read/Write/append for the summary + INDEX update). Indexing reflections must score `importance × pain ≥ 35` to dominate their cluster:

   ```bash
   python3 .agent/tools/memory_reflect.py "document-researcher" \
     "indexed <filename>" \
     "client=<active>: <filename> summarized (<n_topics> topics); INDEX row appended" \
     --importance 7 --pain 5 \
     --note "DURABLE LESSON: <one sentence on what this doc tells us about the engagement that transfers — e.g. 'partner emphasizes <theme>' or 'pricing model is <shape>'. Skip if the doc is purely operational (an SOW template, a calendar invite).> | DOC TYPE: <PDF|DOCX|PPTX|MD|other>; user_desc=<short>; topics=<list>"
   ```

   Importance 7 × pain 5 = 35 → salience 3.5. Won't auto-graduate alone but dominates the indexing cluster as canonical claim. When 5+ docs from the same engagement get indexed in one session, recurrence saturates `min(recurrence,3)` and the cluster crosses 7.0 to graduate — capturing engagement-level patterns rather than per-file noise.

7. **Stop.** Do not continue reading more documents unless explicitly
   asked. Each invocation handles one file. If the user has 10 files,
   they invoke you 10 times — each time with a separate one-line
   description. This forces the user to actually triage their
   uploads, which is the point.

## Examples

**Correct.** User drops `sow-v2.pdf` and says "researcher this."
You ask "what's this file?" User says "SOW v2 — final from legal,
2026-Q2 pricing engagement." You read the PDF, write
`summaries/sow-v2.md` with 6 key-claim bullets, append the table row,
log to episodic, stop.

**Correct.** User drops `org-chart.png` (image) and says "summarize."
You ask for a description, user says "Acme org chart as of 2026-Q1,
shows finance team only." You can't read the PNG meaningfully without
vision tools — you write a summary with `What this is` filled in
from the user line, `Key claims = ["binary file, image format,
content not auto-extractable; use Read with image support to view"]`,
add the row, mark `topics: org, finance, acme`. Better to index
defensively than skip.

**Failure mode (avoid).** User says "just look at all the files in
raw-uploads/ and tell me what's there." Don't bulk-load. Either ask
the user to invoke you once per file, or run a `ls` + propose to
process them one-by-one with required descriptions.

**Failure mode (avoid).** Summary balloons to 2000 words because the
source is a 50-page deck. Truncate. The point is a context-bounded
index entry — full content stays on disk.

## Self-rewrite hook

After every 10 documents indexed, or the first time a summary turns
out to mislead a downstream agent (wrong topics, missing key claim
that mattered), read the last 10 `document-researcher` entries from
episodic memory. If better summary structure, topic-tagging
discipline, or upload-handling rules have emerged, update this file.
Commit: `skill-update: document-researcher, <reason>`.

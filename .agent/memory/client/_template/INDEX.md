# Engagement Index — `<client-id>`

> **Lazy-load contract.** This file (and `briefing.md` if present) are
> the ONLY things auto-loaded at session start when `active_client`
> matches this directory. Everything else under here — `summaries/`,
> `raw-uploads/`, `working/`, `episodic/`, `semantic/` — loads
> on-demand only, when the current task needs it. Do not bulk-read.

## Engagement

- **Name:** _<full human-readable engagement name>_
- **Slug:** `<client-id>` (matches dir name + `.agent/config.json.active_client`)
- **Type:** _<pricing | growth | due-diligence | transformation | other>_
- **Started:** _<YYYY-MM-DD>_
- **Status:** _<scoping | in progress | wrapping up | archived>_

## Briefing summary

_<2–4 sentences. The "if you read nothing else, read this" version of
the engagement. Updated as understanding firms up. Do not paste raw
client material here — that goes in `raw-uploads/`._>

## Stakeholders

| Name | Role | Side | Notes |
|---|---|---|---|
| _<name>_ | _<title>_ | _<client / our team / vendor>_ | _<one-line>_ |

## Documents

> Populated by `document-researcher`. One row per file in `raw-uploads/`.
> The summary lives at `summaries/<filename>.md` — load on demand.

| filename | user description | topics | summarized |
|---|---|---|---|
| _<example.pdf>_ | _<one-line user description>_ | _<comma-separated tags>_ | _<YYYY-MM-DD>_ |

## Decisions log

> Append-only. One bullet per non-trivial choice the team makes during
> the engagement. Promote durable cross-client lessons via
> `graduate.py` to `.agent/memory/semantic/LESSONS.md`.

- _<YYYY-MM-DD>_ — _<decision>_ — _<one-line rationale>_

## Open questions

> Drives next-step research. Move resolved questions to the Decisions
> log with their answer.

- _<question>_ — _<owner / target date if applicable>_

## Workstreams

> Optional — list active workstreams if the engagement is large enough
> to need them. Otherwise leave empty.

- _<workstream name>_ — _<lead>_ — _<status one-liner>_

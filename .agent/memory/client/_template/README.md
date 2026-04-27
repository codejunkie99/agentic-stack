# Client memory template

Template for per-client memory scopes. Use the `client-onboarding`
skill to scaffold a real engagement (`new engagement` / `start client`),
which copies this directory to `.agent/memory/client/<slug>/`, sets
`active_client` in `.agent/config.json`, and initializes `INDEX.md`.

Manual copy is also fine:

```bash
cp -r .agent/memory/client/_template .agent/memory/client/<slug>
# then edit .agent/config.json: "active_client": "<slug>"
```

## Structure

```
<slug>/
  INDEX.md          ← eager-loaded at session start (only this + briefing.md)
  briefing.md       ← optional one-pager; eager-loaded if present
  raw-uploads/      ← user drops files here; never auto-loaded
  summaries/        ← document-researcher writes <filename>.md per upload
  working/          ← per-engagement task notes
  episodic/         ← tool-call history scoped to this client
  semantic/         ← lessons specific to this client
```

## Lazy-load contract

Session start, when `active_client == "<slug>"`, the agent reads:
- `INDEX.md` (always)
- `briefing.md` (if present)

Everything else loads on-demand only, when the current task needs it.
The `INDEX.md` Documents table is the agent's map of what's available
in `summaries/` and `raw-uploads/` — when a task needs a specific
document, the agent loads `summaries/<filename>.md` first, and only
loads the raw file if the summary is insufficient.

This protects the context window and is the same progressive-disclosure
pattern as `.agent/skills/_index.md` → individual `SKILL.md` files.

## Rules

- Nothing in `.agent/memory/client/<slug>/` leaves the machine — the
  parent `.gitignore` excludes everything except this template.
- Writes into a client directory must match the currently active client.
  Enforced by `.agent/protocols/permissions.md` → "BCG engagement rules".
- Generalizable lessons graduate out to `.agent/memory/semantic/` via
  `graduate.py`; client-specific facts stay scoped here.
- Raw uploads are never auto-summarized in bulk — user runs
  `document-researcher` per file with a mandatory one-line description.

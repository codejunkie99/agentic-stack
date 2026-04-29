---
name: client-onboarding
description: Use proactively when a new client engagement is starting and the workspace needs scaffolding. Triggers on "new engagement", "start client", "onboard client", "kick off case". Sets active_client, scaffolds .agent/memory/client/<slug>/, initializes INDEX.md, prompts user for upload pack, and dispatches document-researcher per file. Never auto-loads raw uploads — INDEX.md is the only eager surface.
version: 2026-04-27
triggers: ["new engagement", "start client", "onboard client", "new client", "set up engagement", "kick off case"]
tools: [bash, memory_reflect]
preconditions: ["bcg_adapter == 'enabled' OR active_client requested"]
constraints: ["never overwrite an existing client/<id>/INDEX.md without confirmation", "never auto-load raw uploads into context"]
---

# Client Onboarding — bootstrap a new engagement

Goal: take a new engagement from cold start to "agents see the brief
and can begin work" in one ritual. The destination is a populated
`.agent/memory/client/<active>/` with an `INDEX.md` that drives
lazy-loading on every subsequent session — never auto-load raw uploads.

## When this fires

- User says "we're starting a new engagement / case / client"
- User says "set me up for <client-name>"
- User wants to flip `active_client` and scaffold the directory structure
- A fresh install where `.agent/memory/client/` only contains `_template/`

## What you do

1. **Confirm engagement slug.** Ask the user for a short slug (kebab-case,
   e.g. `pricing-acme-2026q2`). This becomes `<active_client>`. If a
   `.agent/memory/client/<slug>/` already exists, stop and ask whether
   to re-onboard or pick a new slug — never silently overwrite.

2. **Scaffold the client directory** by copying `_template/` to
   `<slug>/`:
   ```bash
   cp -r .agent/memory/client/_template .agent/memory/client/<slug>
   ```
   Then create the standard subdirs: `raw-uploads/`, `summaries/`,
   `working/`, `episodic/`, `semantic/`. Do not delete the
   `_template/` source.

3. **Set active_client** in `.agent/config.json`:
   ```bash
   python3 -c "import json,pathlib; p=pathlib.Path('.agent/config.json'); c=json.loads(p.read_text()); c['active_client']='<slug>'; p.write_text(json.dumps(c, indent=2)+'\n')"
   ```
   Verify: `python3 .agent/tools/show.py` prints the active client.

4. **Initialize INDEX.md.** The template `INDEX.md` ships with empty
   sections. Fill in:
   - Engagement name (full, human-readable)
   - Engagement type (e.g. pricing, growth, due-diligence,
     transformation)
   - Briefing summary placeholder ("pending — drop briefing into
     `raw-uploads/` and run document-researcher")
   - Stakeholders table (rows added as user provides names)
   - Documents table (one row per file in `raw-uploads/`, populated
     by `document-researcher`)
   - Decisions log header
   - Open questions header

5. **Prompt for upload pack.** Tell the user explicitly:
   > "Drop briefing files into `.agent/memory/client/<slug>/raw-uploads/`,
   > then run `document-researcher` on each to produce summaries +
   > INDEX entries. I will not auto-read raw uploads — that's by design,
   > to protect context window."

6. **Invoke document-researcher per dropped file.** For each file the
   user adds, dispatch the `document-researcher` skill (it will demand
   a one-line user description before producing a summary).

7. **Log the onboarding** to episodic memory:
   ```bash
   python3 .agent/tools/memory_reflect.py "client-onboarding" \
     "onboarded <slug>" "client dir scaffolded; INDEX initialized" \
     --importance 6 \
     --note "engagement type: <type>; n_uploads: <count>"
   ```

## Examples

**Correct.** User says "we're starting the pricing case for Acme."
You ask for slug, propose `pricing-acme-2026q2`, user confirms,
you scaffold, set `active_client`, initialize INDEX with engagement
type="pricing", prompt for uploads.

**Correct.** User drops 3 files into `raw-uploads/` mid-onboarding.
You dispatch `document-researcher` three times, each time demanding
the one-line description, each time appending a row to the Documents
table in INDEX.md.

**Failure mode (avoid).** User says "I dropped the briefing in,
read it." You're tempted to `cat raw-uploads/*.pdf` and load it all.
**Don't.** That violates lazy-load. Run `document-researcher` instead,
which produces a bounded summary and indexes the file.

## Self-rewrite hook

After every 5 engagements onboarded, or the first time onboarding
fails (slug collision handled wrong, INDEX template insufficient,
user pushback on the upload prompt), read the last 5
`client-onboarding` entries from episodic memory. If better
slug-naming, INDEX sections, or upload prompts have emerged, update
this file. Commit: `skill-update: client-onboarding, <reason>`.

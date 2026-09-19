---
name: session-audit
description: >
  Audit the work of a session or a change set for gaps. Split the delivered
  surface into areas that do not overlap and that cover everything. Verify each
  area with a command, never from memory. Use when the user says "MECE
  evaluation", "audit this session", "find all gaps", "what did we miss", "is
  this complete", or before a handoff, a pull request, or a release. Produces
  or updates a gap register.
---

# Session audit

## What this skill is for

`skills/mece/SKILL.md` validates a structure: a plan, a specification, a list.
This skill audits delivered work: code, tests, documents, boards, and state.
The two skills use the same MECE test. They read different inputs.

## Rule

Verify every area with a command. Do not verify from memory.

An agent remembers what it intended. It does not remember what it did. Every
gap found by a real audit is a gap the agent believed was closed.

## Procedure

### Step 1 — Split the surface

List the areas the session touched. The areas must not overlap. Together they
must cover everything. Start from this default set and remove what does not
apply:

| Area | The question it answers |
|---|---|
| Product code | Does the changed behaviour work? |
| Tests | Does a test fail when the behaviour breaks? |
| Build and CI | Does the pipeline run the new code? |
| Documents | Does every claim match the repository today? |
| Tracking board | Does every item have its required fields? |
| Secrets and private data | Did anything private enter a committed file? |
| Repository hygiene | Dead code, file size limits, unused members. |
| External state | Did a live system change, and is it correct? |

Add an area when the session touched something this list does not name.

### Step 2 — Verify each area with a command

Write the command before you write the verdict. Examples:

```bash
# Documents: find claims that contradict the repository.
grep -rn "not yet\|no code exists\|Not started" docs/

# Secrets: find private names in committed files.
grep -rln "<organisation>\|<customer>\|@<company>" --include="*.md" . | grep -v "<ignored-dir>/"

# Hygiene: find files over the size limit.
find src tests -name "*.cs" | xargs wc -l | awk '$1>500'

# Tests: find code with no test reference.
grep -rn "<SymbolName>" --include="*.cs" tests/ || echo "NOT TESTED"

# CI: run the exact configuration the pipeline runs.
dotnet test --configuration Release
```

The last example matters. Local defaults and pipeline defaults differ. Run the
pipeline configuration before you claim the pipeline passes.

### Step 3 — Classify each finding

For each finding, record:

- **Evidence** — the command output or the file and line. Not a summary.
- **Remedy** — the change that makes the finding false.
- **Severity** — blocker, high, medium, or low.

### Step 4 — Fix, then re-verify

Apply the remedy. Run the same command again. The finding must disappear.

### Step 5 — Update the gap register

Use `gap-register.md` in this skill folder as the template. Add every finding.
Close the rows that are no longer true. Recount the totals with a script, not
by hand.

## The three live documents

A project needs three documents that answer three different questions. Keep
them separate. One document that answers all three answers none of them well.

| Document | Question |
|---|---|
| Delivery status | Is this ticket done? |
| Gap register | What is broken that no ticket has caught? |
| Traceability | Is this requirement tested? |

Rule: update a live document in the same change that makes it wrong. A stale
live document is worse than no document. A reader trusts it.

## Findings this audit type reliably produces

Check these first. They are common and they are cheap to test:

1. A document states that no code exists, and code exists.
2. A count in a document is wrong after new work.
3. A test file names a real person, customer, or organisation.
4. A safety guard has no test.
5. A traceability row claims Covered, and the named test measures something
   else.
6. The pipeline configuration was never run locally.
7. A note that describes a data leak repeats the leaked value.

Item 7 is not a joke. Check the text you write about a leak.

## Report format

Report a table. One row per area. Name the gaps found and fixed.

Do not report "everything looks fine". Report the command you ran and its
output.

## Related

- `skills/mece/SKILL.md` — the same test, applied to a specification.
- `skills/verify-by-breaking/SKILL.md` — use it on every check this audit adds.
- `skills/slopwatch/SKILL.md` — finds low-quality output inside a change.

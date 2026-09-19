# Gap Register

**Status:** Template — this copy ships with the skill and holds no live rows.
Start a project's live register by copying this file into that project's
`docs/`, setting **Status:** to Live there, and updating the copy in the same
change that closes a row. Never edit this template copy with real findings.

The delivery status file answers "is this ticket done?". The traceability file
answers "is this requirement tested?". This file answers "what do we know is
broken that no ticket has caught yet?" — including gaps in the documents
themselves.

A row is closed only when the thing it describes is no longer true. Creating a
ticket for a gap closes it *only* when the gap was "no ticket owns this".

## Totals

| | Blocker | High | Medium | Low | Total |
| --- | --- | --- | --- | --- | --- |
| **Open** | 0 | 0 | 0 | 0 | 0 |
| **Closed** | | | | | 0 |

Total tracked: **0**.

<!--
Recount the totals with a script. Do not count by hand.
A register whose totals disagree with its rows is not trusted, and an
untrusted register is not read.
-->

## Open

### Blocker (0)

<!--
Blocker: work cannot proceed correctly until this is fixed.
High:    a wrong result, a data leak, or an untested safety guard.
Medium:  a false claim in a live document, or a missing check.
Low:     a cosmetic or naming inconsistency.
-->

### High (0)

#### `gap-id-in-kebab-case` — One sentence stating what is wrong

- **Category:** doc-accuracy | test | ticket | board | security | hygiene
- **Evidence:** The command output, or the file and line number. Quote it.
  Never write a summary here. A reader must be able to repeat the check.
- **Remedy:** The change that makes this row false. Name the file or the
  ticket that will own it.

### Medium (0)

### Low (0)

## Closed

| Gap | Severity | Closed by |
| --- | --- | --- |
| `gap-id` — what was wrong | medium | What made it false. Name the commit, the test, or the file. State how you verified it. |

## How this list was built

State the method and the date. Name the commands that produced the findings,
and the documents and systems that were compared. A register with no method
cannot be repeated, and a register that cannot be repeated goes stale without
anyone noticing.

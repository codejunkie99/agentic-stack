# Client memory template

Template for per-client memory scopes. Copy this directory to
`.agent/memory/client/<client-id>/` when starting a new engagement, then
set `AGENT_CLIENT=<client-id>` in the shell (or work from a directory
matching `client-*`) so the harness routes writes correctly.

## Structure

Mirror the project-level memory layout at the client scope:
- `working/` — current task notes for this client
- `episodic/` — tool-call history scoped to this client
- `semantic/` — lessons and knowledge specific to this client

## Rules

- Nothing in `.agent/memory/client/<X>/` leaves the machine — the parent
  `.gitignore` excludes everything except this template.
- Writes into a client directory must match the currently active client.
  Enforced by `.agent/protocols/permissions.md` → "BCG engagement rules".
- Generalizable lessons graduate out to `.agent/memory/semantic/` via
  `graduate.py`; client-specific facts stay scoped here.

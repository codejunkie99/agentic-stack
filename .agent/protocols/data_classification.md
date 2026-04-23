# Data classification

Stub — fill in during the first client engagement. Defines where data
may live and what tools may consume it.

## Levels

- **Public.** No restrictions. May be committed, shared, pasted anywhere.
- **Internal (BCG).** May live in a BCG-hosted repo; may be pasted into
  BCG-approved enterprise LLMs; must not be pushed to personal GitHub
  or non-BCG surfaces.
- **Client-confidential.** Lives only in `.agent/memory/client/<client-id>/`
  or BCG-approved client infrastructure. May be pasted into BCG enterprise
  LLMs (per `PREFERENCES.md`). Must never be committed to any git repo,
  regardless of host.

## Markers (not yet enforced)

When classification markers (`CONFIDENTIAL`, `INTERNAL`, etc.) become
relevant, this protocol will define how `pre_tool_call.py` detects them
and gates behavior. Left as a stub until a concrete marker convention
emerges from the first engagement.

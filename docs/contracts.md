# Public contracts

Integration code that shells out to the host-agent tools under `.agent/tools/`
or talks to the memory MCP server relies on the surfaces below. Renaming a
field, changing an exit code's meaning, renaming an MCP tool or resource, or
weakening redaction is a breaking change. Adding optional fields, a new
`error.type`, or more redaction patterns is compatible.

## CLI streams

| Stream | Contract |
|---|---|
| stdout | Results. In `--format json` this is the only machine-readable envelope. In `text` mode it is human prose and not a stable contract. |
| stderr | Logs, hints, progress, text-mode error lines. |

`--format auto` (the default) resolves to `text` on a TTY and `json` when
stdout is a pipe, redirect, or CI buffer. Agents that need stable parsing
pass `--format json` explicitly.

## Success envelope (exit 0)

```json
{"ok": true, "data": {}, "meta": {"count": 0}}
```

`data` is tool-specific. `meta` is optional and carries out-of-band fields
such as `count`, `path`, `run_dir`.

## Error envelope

```json
{"ok": false,
 "error": {"type": "invalid_args", "code": 0, "message": "...", "hint": "...", "detail": {}},
 "meta": {}}
```

In `text` mode stdout stays empty and stderr gets `error: ...` and `hint: ...`.

| `error.type` | Meaning | Exit |
|---|---|---|
| `invalid_args` | bad flag, argument, plan, or file | 2 |
| `not_found` | the thing does not exist | 1 |
| `conflict` | already exists, stale write, contradiction | 1 |
| `permission` | authenticated but not allowed (unscreened install, budget exhausted) | 1 |
| `upstream` / `rate_limit` / `plugin_not_detected` | backend or host problems | 1 |
| `not_logged_in` / `auth` | credential problems | 3 |
| `network` | DNS, connection, push failure | 4 |
| `io` / `internal` | local filesystem or bug | 5 |
| `cancelled` | interrupted | 130 |

`hint` is the next action an agent can take. `detail` is type-specific
structured data. Use both the exit code and `error.type`.

Tools on this contract: `track.py`, `knowledge.py`, `skill_forge.py`,
`plan.py`, `evolve.py`, `persona.py`, `proactive.py`, `sync.py`.

## Memory MCP server (`tools/memory_mcp.py`)

JSON-RPC over stdio, newline-delimited. stdout carries protocol frames only;
logs go to stderr. Boot failures exit 1. Tool failures return `isError: true`;
resource-read failures are JSON-RPC errors (`-32002` unknown, `-32603` other).

| Tool | Required input | Returns |
|---|---|---|
| `mem_context` | `query` | markdown in `content[0].text` (preferences, profile, valid foresight, matches) |
| `mem_search` | `query`, optional `topK` (default 5, cap 50, non-positive → default) | markdown list |
| `mem_save_turn` | `messages[]` or legacy `role` + `content`/`text`; optional `sessionKey`, `flush` | JSON save status |
| `mem_save_fact` | `fact`, or `messages[]` with only user/assistant roles | JSON save status |

`mem_context` and `mem_search` return markdown on purpose: splice it into
model context as-is. `mem_save_turn` records trajectories to the episode
track; `mem_save_fact` records durable user facts to
`memory/personal/PROFILE.md` and refuses tool roles.

| Resource | Meaning |
|---|---|
| `mem://profile` | read-side `mem_context` with an empty query |
| `mem://search?q={query}&topK={topK}` | read-side `mem_search`; `q`/`query`, `topK`/`top_k`; empty query is an error |

## Redaction

Credential-looking strings are masked before bytes leave any tool, hook,
or MCP response: AWS access key ids, `sk-…`, GitHub `gh?_…`, Slack `xox?-…`,
`emk_`/`evt_` keys, `Bearer …`, presigned-URL signature parameters, and
`api_key|secret|token|password=…` pairs. The mask keeps the first eight
characters and appends `_REDACTED` so support output can still correlate a
key without exposing it.

## Change checklist

1. Keep stdout/stderr separation.
2. Preserve field names, types, and exit-code meaning.
3. Add or update a regression test in `tests/test_orchestration_evolution_memory.py`.
4. Update this document and `CHANGELOG.md`.

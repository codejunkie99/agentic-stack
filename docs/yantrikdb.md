# YantrikDB memory backend [BETA]

Layer [yantrikdb](https://github.com/yantrikos/yantrikdb) — a cognitive
memory database — on top of the portable `.agent/` brain. The
filesystem stays authoritative (still git-tracked markdown); yantrikdb
adds multi-signal recall, contradiction detection, temporal decay, and
reflect() composition without replacing any existing tool.

## When is this useful

The default filesystem + lexical tools (`recall.py`, FTS `memory_search.py`)
are fine for small / medium brains. Consider enabling yantrikdb when:

- You have thousands of lessons / episodes and want semantic recall that
  composes with importance, decay, and graph connectivity — not just
  BM25 keyword ranking.
- Multiple projects share one persistent memory server and you want
  per-project isolation via namespaces.
- You want contradiction detection across memories (e.g. "this lesson
  disagrees with that lesson about handling nulls").
- You want `reflect(question)` that returns a structured view of
  self-model + rules + constraints + goals + recent signals, ready to
  inject into an agent's working context.

## What the integration does NOT do

- It does **not** replace markdown files. `.agent/memory/semantic/*.md`
  remains the canonical, git-diffable source of truth.
- It does **not** touch the existing tools (`auto_dream.py`, `decay.py`,
  `promote.py`, etc.). They keep working whether yantrikdb is on or off.
- It does **not** install yantrikdb-server — you point it at an existing
  server (your own, or a cloud instance).

## Install

1. Run a yantrikdb server somewhere you can reach (e.g. local Docker,
   your homelab, an existing cluster). See
   [yantrikdb-server](https://github.com/yantrikos/yantrikdb-server) for
   deployment options.
2. Mint an access token for a dedicated database (each agentic-stack
   project should get its own database or at least namespace).
3. Install the client into your project's environment:
   ```bash
   pip install 'yantrikdb-client[embed]>=0.2.1'
   ```
4. Enable the feature — either through the onboarding wizard:
   ```bash
   agentic-stack <harness> --reconfigure
   # Answer "yes" to "Enable YantrikDB memory backend [BETA]?"
   ```
   Or by editing `.agent/memory/.features.json` directly:
   ```json
   {
     "yantrikdb_memory": {
       "enabled": true,
       "beta": true,
       "url": "http://your-server:7438",
       "token": "ydb_...",
       "namespace": ""
     }
   }
   ```
   Leaving `url` / `token` empty falls back to `YDB_URL` / `YDB_TOKEN`
   env vars at read time — preferred if `.agent/memory/` is
   git-tracked.
   Leaving `namespace` empty derives a stable per-project namespace
   from a hash of your repo root (so multiple projects on one server
   don't collide).

## First sync

```bash
python3 .agent/memory/yantrikdb_sync.py          # incremental
python3 .agent/memory/yantrikdb_sync.py --full   # rebuild cache
python3 .agent/memory/yantrikdb_sync.py --status # show counts
```

The sync walks `.agent/memory/` and upserts every `.md` / `.jsonl`
file into yantrikdb with type tagging derived from the subdirectory:

| directory | `memory_type` |
|---|---|
| `semantic/` | `semantic` |
| `episodic/` | `episodic` |
| `personal/` | `self_model` |
| `working/` | `working` |
| `candidates/` | `hypothesis` |
| (other) | `semantic` (fallback) |

Each document's rid is persistent across runs; updates mutate the
existing record. An incremental cache at
`.agent/memory/.index/yantrikdb_sync_cache.json` skips unchanged
files between runs (content-hash check).

## Using it from an agent

### Multi-signal recall
```bash
python3 .agent/tools/yantrikdb_recall.py "the lesson about null checks"
python3 .agent/tools/yantrikdb_recall.py "postgres migration" --top-k 5
python3 .agent/tools/yantrikdb_recall.py "my preferred test strategy" --type self_model
```

Falls back gracefully if the feature is disabled — prints a clear
message to stderr and exits with code 2 so the agent can choose to
fall back to `recall.py` or `memory_search.py`.

### Structured reflection for context injection
```bash
# Human-readable
python3 .agent/tools/yantrikdb_reflect.py "task: refactor auth flow"

# Machine-readable for agent context injection
CTX=$(python3 .agent/tools/yantrikdb_reflect.py "task: refactor auth flow" --bare)
echo "$CTX"
```

The `--bare` output is designed to drop directly into an agent's
system prompt. It begins with a **memory-router seed prompt** —
a 73-word frame established by yantrikdb's own research showing that
retrieval-time teaching at small-LLM scales goes from 27% HURT to 93%
RESCUE when the agent is explicitly taught how to treat stored items
as scoped procedure controllers rather than advisory context.

The reflect tool surfaces seven typed views in order:
self-model, rules, hypotheses, constraints, goals, narrative arcs,
recent learning signals. Top-k per type is configurable (default 3).

## Going back

Disabling is reversible:
```bash
# In .agent/memory/.features.json
"yantrikdb_memory": {"enabled": false, ...}
```

Your filesystem `.agent/memory/` is untouched. The yantrikdb server
still has the mirrored records, but nothing in agentic-stack will read
from them. You can either leave the records in place (harmless) or
delete the namespace on the yantrikdb server manually.

## Architecture at a glance

```
.agent/memory/                    ← authoritative
├── semantic/                     ← markdown, git-tracked
├── episodic/
├── personal/
├── working/
└── .index/
    ├── memory.db                 ← existing FTS5 index
    └── yantrikdb_sync_cache.json ← new, incremental sync state

yantrikdb server (yours)
└── database / namespace          ← mirror, enhanced recall
    ├── memories (typed)
    ├── entity graph
    ├── conflicts
    └── decay / importance state
```

Read path (when feature enabled):
- `yantrikdb_recall.py` → yantrikdb multi-signal recall
- `yantrikdb_reflect.py` → yantrikdb reflect() → render with router seed

Read path (feature disabled):
- `recall.py` (lexical) + `memory_search.py` (FTS5) unchanged

Write path (always):
- All existing tools write to `.agent/memory/*.md` / `*.jsonl`
- Optional `yantrikdb_sync.py` run (cron / post-commit hook / manual)
  mirrors to yantrikdb

## FAQ

**Q: Does yantrikdb see my secrets?**
Only what you put in `.agent/memory/`. Keep secrets out of there as
usual. The server only sees text you explicitly sync.

**Q: Can I run multiple agentic-stack projects against one server?**
Yes — each project gets a namespace derived from its root path hash.
Set a human-readable namespace in `.features.json` if you prefer.

**Q: What happens if the yantrikdb server is down?**
The sync / recall / reflect tools print a clear error and exit with
non-zero code. All existing tools continue to work because they read
filesystem markdown directly.

**Q: How does this interact with `auto_dream.py` / consolidation?**
`auto_dream.py` runs on the filesystem as before. You can additionally
trigger yantrikdb's own consolidation via the client's `think()` API
if you want (not wired into this PR; see `yantrikdb-client` docs).

## Known limitations

- One-way sync (filesystem → yantrikdb). No write-back.
- Re-running `--full` does not delete records on the server that were
  removed from the filesystem — the sync cache tracks rids but the
  current implementation upserts and doesn't tombstone removed files.
  (Follow-up PR if useful.)
- Requires a reachable yantrikdb server. No embedded / in-process
  option surfaced here.

## References

- [yantrikdb-client (PyPI)](https://pypi.org/project/yantrikdb-client/)
- [yantrikdb-server (repo)](https://github.com/yantrikos/yantrikdb-server)
- [The memory-router seed prompt design](https://github.com/yantrikos/yantrikdb-client/blob/main/CHANGELOG.md) —
  rationale for the 73-word seed the reflect tool emits

# Memory tracks, reflection, knowledge, MCP, session hooks

Markdown is the source of truth. Indexes (`memory_search.py`) rebuild from
it. Nothing here calls a model.

## Tracks — `memory/tracks.py`, `tools/track.py`

| Kind | Path | Track |
|---|---|---|
| episode | `memory/episodes/episode-YYYY-MM-DD.md` | user |
| foresight | `memory/foresights/foresight-YYYY-MM-DD.md` | user (validity window) |
| case | `memory/cases/agent_case-YYYY-MM-DD.md` | agent |

Files carry JSON-valued frontmatter (`id`, `type`, `file_type`,
`schema_version`, `track`, `user_id` or `agent_id`, `date`, `entry_count`,
`last_appended_at`, `deprecated_entries`). Entries are wrapped in
`<!-- entry:<id> -->` … `<!-- /entry:<id> -->` with a `<!-- meta: {...} -->`
line; ids are `<prefix>_<YYYYMMDD>_<NNNNNNNN>` and restart daily per file.
Scope keys: `user_id` (`AGENT_USER`/`USER`), `agent_id` (`AGENT_PROFILE`),
`app_id`, `project_id` (project directory). Writes are atomic under a lock.

```bash
track.py add episode "Shipped the billing fix" --session s1
track.py add case --intent "fix flaky auth test" --outcome "pinned the clock" --quality 0.9
track.py add foresight "cert expires" --until 2026-12-01
track.py search episode "supabase migration" | track.py list case --limit 5
track.py deprecate episode <id> --by <newer id>
```

## Reflection — `memory/reflect_episodes.py`

Scenes form by cosine over bag-of-words with a running-mean centroid
(threshold 0.65, 7-day window). Scenes with two or more members merge into
one chronological consolidated episode (duplicates dropped, lossy by
design); members are deprecated, never deleted; the audit row lands in
`memory/reflection_report.jsonl`. Cluster ids are stable, so a scene that
grows is re-consolidated as an `update`. Cron it weekly.

## Knowledge — `tools/knowledge.py`

A text document becomes `memory/knowledge/<Category>/<doc_id>/` with
`index.md`, one `N_<Topic>.md` per heading (or ~1500-char chunk), and the
untouched original under `_original/`. Categories come from
`.taxonomy.md` (edit freely; `Others` is the fallback). `search` ranks
topics by query-word coverage with a title bonus; `patch` moves a document
between categories; `remove` deletes the directory. Binary sources are
refused — convert first.

## MCP server — `tools/memory_mcp.py`

Stable tools `mem_context`, `mem_search`, `mem_save_turn`, `mem_save_fact`
and resources `mem://profile`, `mem://search?q=`. See
[contracts](contracts.md). Register once per host:

```bash
claude mcp add agentic-memory -- python3 /path/.agent/tools/memory_mcp.py
# Cursor: ~/.cursor/mcp.json · Codex: ~/.codex/config.toml · OpenCode: opencode.json
```

## Claude Code session hooks — `harness/hooks/claude_code_session.py`

SessionStart injects the last session summary, recent episodes, and valid
foresight; UserPromptSubmit injects relevant lessons, episodes, and cases;
Stop stores the turn as an episode (redacted); SessionEnd appends a summary
to `memory/working/sessions.jsonl`. Always exits 0.

## Sync — `tools/sync.py`

Commits only the brain paths (memory, skills, playbooks, personas, agent
registry), pulls with rebase, pushes. Refuses when unrelated changes are
staged. Never force-pushes.

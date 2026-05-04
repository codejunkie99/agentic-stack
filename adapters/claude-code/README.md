# Claude Code adapter

## Install
From your project root (where `.agent/` lives):

```bash
cp adapters/claude-code/CLAUDE.md ./CLAUDE.md
mkdir -p .claude
cp adapters/claude-code/settings.json .claude/settings.json
```

Or let the top-level install script do it:

```bash
./install.sh claude-code
```

## What it wires up

- **`CLAUDE.md`** — boot instructions at project root. Claude Code reads this
  before every session. Tells the model to read the brain in the correct order,
  run `recall.py` before high-stakes operations, and call `memory_reflect.py`
  manually for significant events.

- **`.claude/settings.json`** — ztk pre-tool policy, post-tool logging, and
  permission denies:

  | Hook | Trigger | Script |
  |---|---|---|
  | `PreToolUse` | `Bash\|Edit\|Write\|MultiEdit\|NotebookEdit\|WebFetch` | `.agent/tools/claude_pre_tool_use.py` |
  | `PostToolUse` | `Bash\|Edit\|MultiEdit\|Write\|Task\|TodoWrite` | `.agent/harness/hooks/claude_code_post_tool.py` |
  | `Stop` | `*` (session end) | `.agent/memory/auto_dream.py` |

### Why `claude_code_post_tool.py` and not `memory_reflect.py`

The old hook called `memory_reflect.py claude-code post-tool ok` — every
entry was identical (action="post-tool", detail="ok", reflection=""). The
dream cycle clusters on the `reflection` field; an empty reflection means
zero candidates staged regardless of how many tool calls fire.

`claude_code_post_tool.py` reads the JSON payload Claude Code sends via
**stdin** on every PostToolUse event:

```json
{
  "tool_name": "Bash",
  "tool_input": {"command": "supabase db push --db-url $DATABASE_URL"},
  "tool_response": {"output": "Applied 1 migration.", "exit_code": 0}
}
```

It then:
- Maps `tool_name` + `tool_input` to a meaningful action label
- Scores `importance` by domain (deploy/migrate/supabase/edge-function = 9)
- Detects failures from `exit_code`, `error` stream, and `is_error`
- Generates a non-empty `reflection` the dream cycle can cluster on
- Sets `pain_score=5` for high-importance successes so recurring patterns
  cross the promotion threshold (7.0); routine ops stay at `pain_score=2`

## Verify

1. Open Claude Code in your project.
2. Run one Bash command.
3. Check the last line of `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`:
   - `action` should describe the actual command, not `"post-tool"`
   - `reflection` should be non-empty
   - `importance` should be 9 for deploy/supabase ops, 3 for `git status`

```bash
tail -1 .agent/memory/episodic/AGENT_LEARNINGS.jsonl | python3 -m json.tool
```

4. Check brain state:
```bash
python3 .agent/tools/show.py
```

## Troubleshooting

- **Hook doesn't fire at all:** run `claude settings` and confirm your
  `.claude/settings.json` appears in the merged config. Claude Code merges
  project-level settings with global `~/.claude/settings.json`.

- **`stdin` is empty / payload is `{}`:** older Claude Code versions may not
  pass the JSON payload. The hook falls back to `CLAUDE_TOOL_NAME` /
  `CLAUDE_TOOL_INPUT` env vars. The action label will still be correct; the
  detail and output capture will be empty. Upgrade Claude Code to get full
  stdin payloads.

- **`python3` not found:** add `AGENT_PYTHON=python` to your shell profile
  and edit the hook commands in `.claude/settings.json` accordingly.

- **Dream cycle stages nothing:** after a session, run
  `python3 .agent/memory/auto_dream.py` manually and check the output line.
  If `patterns=0`, the episodic log is either empty or all entries have
  empty reflections (old hook). If `patterns=N staged=0`, salience is too
  low — check that `importance` and `pain_score` are non-trivial in your
  entries.

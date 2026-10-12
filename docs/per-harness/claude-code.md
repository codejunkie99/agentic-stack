# Claude Code setup

## What the adapter installs
- `CLAUDE.md` at project root
- `.claude/settings.json` with `SessionStart`, `UserPromptSubmit`, `PostToolUse`,
  `Stop`, and `SessionEnd` hooks

## Install
```bash
./install.sh claude-code
```

## Hook behavior
- **SessionStart**: injects the last session summary, the five newest episodes,
  and currently valid foresight items as `<session-context>`.
- **UserPromptSubmit**: for prompts of three or more words, injects relevant
  graduated lessons, episodes, and agent cases as `<memory-recall>`.
- **PostToolUse** (`Bash | Edit | Write | ...`): logs to episodic memory.
- **Stop**: stores the turn (your prompt + `last_assistant_message`) as a
  Markdown episode under `.agent/memory/episodes/`, credentials redacted; then
  runs the dream cycle.
- **SessionEnd**: appends `{session_id, summary, turn_count, end_reason, ...}`
  to `.agent/memory/working/sessions.jsonl`.

All four session events run `.agent/harness/hooks/claude_code_session.py`,
which branches on `hook_event_name` and always exits 0 so a memory failure
never blocks a session. Context goes out as
`hookSpecificOutput.additionalContext`; Stop and SessionEnd print nothing.

## Optional: MCP memory server
Expose the same brain to Claude Desktop, Cursor, Codex, or OpenCode:
```bash
claude mcp add agentic-memory -- python3 "$PWD/.agent/tools/memory_mcp.py"
```
Tools: `mem_context`, `mem_search`, `mem_save_turn`, `mem_save_fact`.
Resources: `mem://profile`, `mem://search?q=...`. See [contracts](../contracts.md).

## Customizing
Edit `.claude/settings.json` to add matchers or denies. The `permissions.deny`
list is the Claude-Code-level fence; `.agent/protocols/permissions.md` is
the content-level fence read by the model. Use both.

## Troubleshooting
- If hooks don't fire, check `claude settings` reports the merged config
  includes your entries, and that you accepted the workspace trust dialog.
- `claude --debug-file hooks.log` shows hook stdout/stderr.
- If the agent ignores `CLAUDE.md`, Claude Code may need a version that
  supports project-root memory.

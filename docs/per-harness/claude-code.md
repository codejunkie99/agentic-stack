# Claude Code setup

## What the adapter installs
- `CLAUDE.md` at project root
- `.claude/settings.json` with `PreToolUse`, `PostToolUse`, and `Stop` hooks

## Install
```bash
./install.sh claude-code
```

## Hook behavior
- Before `Bash | Edit | Write | MultiEdit | NotebookEdit | WebFetch` tool
  calls: runs `.agent/tools/claude_pre_tool_use.py` and returns a Claude
  Code permission decision.
- After every `Bash | Edit | Write` tool call: logs to episodic memory.
- On session end (`Stop`): runs the dream cycle.

## Customizing
Edit `.claude/settings.json` to add matchers or denies. The `permissions.deny`
list is the Claude-Code-level fence; `.agent/protocols/permissions.md` and
`.agent/protocols/tool_schemas/` are also enforced by the `PreToolUse`
hook where Claude Code exposes tool input.

## Troubleshooting
- If hooks don't fire, check `claude settings` reports the merged config
  includes your entries.
- If the agent ignores `CLAUDE.md`, Claude Code may need a version that
  supports project-root memory.

# Host-Neutral ztk Adapters Design

## Goal

Make ztk work across Codex, Cursor, OpenCode, Claude Code, and similar
coding-agent hosts without pretending every host has the same lifecycle.

## Design

ztk exposes a host-neutral policy interface through `.agent/tools/ztk.py`.
Hosts with native hooks call this CLI from their hook configuration.
Hosts without native hooks load instructions that tell the agent to use
`ztk exec` for policy-covered shell commands.

The core policy input is normalized:

```json
{
  "host": "codex",
  "event": "pre_tool_use",
  "tool": "shell",
  "operation": "run",
  "input": { "command": "git status" }
}
```

The core policy output is also normalized:

```json
{
  "decision": "allow",
  "reason": "allowed"
}
```

Thin host adapters translate native hook JSON to and from that contract.
Claude Code and Codex use native `PreToolUse` hooks. OpenCode uses its
native `permission` config for common cases and `ztk exec` as the portable
command gate. Cursor, Windsurf, Hermes, Pi, and OpenClaw use instruction
files plus `ztk exec`.

## Error Handling

Malformed hook JSON denies by default in native hook adapters. Unknown
tools allow by default unless their normalized schema has a matching rule,
so adapters should map risky tools into `shell`, `api`, or `file` events
instead of relying on string matching in prompts.

## Testing

Tests cover the shared policy evaluator, host-specific hook output shapes,
the `ztk exec` deny path, Codex adapter files, and OpenCode's current
`permission` key.

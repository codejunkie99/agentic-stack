---
name: brain
version: 2026-05-10
triggers: ["brain", "long-term memory", "shared memory", "cross-agent memory", "mcp memory", "remember across tools", "git-backed memory"]
tools: [bash]
preconditions: [".agent exists"]
constraints: ["Brain is external; do not assume the brain binary is installed", "do not store secrets in Brain", "use ask before note when checking prior context"]
category: memory
---

# Brain Integration

Use this skill when the task needs durable memory shared across coding-agent
harnesses through the external `brain` CLI and MCP server.

## Check Availability

```bash
python3 .agent/tools/brain_bridge.py status
```

If Brain is missing, tell the user to install it:

```bash
brew install codejunkie99/tap/brain
```

## Recall

Before non-trivial work that could depend on prior cross-tool decisions:

```bash
python3 .agent/tools/brain_bridge.py ask "<intent or topic>"
```

Use returned notes as context, but keep project-local `.agent/memory/semantic`
as the source for agentic-stack lessons until the user explicitly asks to
promote or migrate them.

## Save

Save one concise observation when the user gives a durable preference,
cross-project convention, or decision that should survive across harnesses:

```bash
python3 .agent/tools/brain_bridge.py note "<one durable observation>"
```

Do not save secrets, credentials, or ephemeral task details.

## MCP

To wire Brain as an MCP stdio server, inspect:

```bash
python3 .agent/tools/brain_bridge.py mcp-command
```

The expected command is `brain serve --mcp`.

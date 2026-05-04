# Cursor adapter

## Install
```bash
cp -r adapters/cursor/.cursor ./.cursor
```

Or:
```bash
./install.sh cursor
```

## What it wires up
Cursor reads `.cursor/rules/*.mdc` on every session and injects them into
the system prompt. The `agentic-stack.mdc` rule is marked `alwaysApply: true`
so it loads on every interaction.

Cursor does not provide ztk with a native pre-tool hook in this adapter.
For hard command enforcement, route commands through:

```bash
python3 .agent/tools/ztk.py exec -- <command>
```

## Verify
In Cursor, open the chat and ask "What files should you read before acting?"
It should mention `.agent/AGENTS.md`.

## Notes
Cursor's rules directory is scanned recursively. If you want to add
project-specific overrides, create additional `.mdc` files alongside.

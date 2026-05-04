# Cursor setup

## What the adapter installs
- `.cursor/rules/agentic-stack.mdc` (marked `alwaysApply: true`)

## Install
```bash
./install.sh cursor
```

## How it works
Cursor auto-loads `.mdc` files from `.cursor/rules/` on every session and
prepends them to the system prompt. The `alwaysApply: true` flag keeps the
rule in context even when the user is working on unrelated code.

Cursor rules are persistent prompt context, not a ztk-owned hard
pre-tool gate. For commands that must be checked against
`.agent/protocols/permissions.md`, use:

```bash
python3 .agent/tools/ztk.py exec -- <command>
```

## Logging note
Cursor has no native post-tool hook. Instruct the model (via the rule file)
to call `memory_reflect.py` after significant actions. If you want
automatic logging, run the standalone-python conductor in parallel as a
side channel.

## Troubleshooting
- `.mdc` files must have YAML frontmatter. If Cursor ignores the file,
  check the frontmatter is well-formed.

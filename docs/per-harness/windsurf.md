# Windsurf setup

## What the adapter installs
- `.windsurf/rules/agentic-stack.md` for current Windsurf workspace rules
- `.windsurfrules` at project root for legacy Windsurf compatibility

## Install
```bash
./install.sh windsurf
```

## How it works
Windsurf's Cascade discovers workspace rules in `.windsurf/rules/` and
uses their frontmatter to decide activation. The agentic-stack rule is
`always_on`, so Cascade receives it every session. The legacy
`.windsurfrules` file remains installed so older Windsurf builds still
see the portable brain.

Windsurf rules are prompt context, not a ztk-owned hard pre-tool gate.
For commands that must be checked against `.agent/protocols/permissions.md`,
use:

```bash
python3 .agent/tools/ztk.py exec -- <command>
```

## Logging note
Windsurf does not have a first-class post-tool hook. The rule file asks
the agent to call `memory_reflect.py` after significant actions. If you
want automatic logging, wrap Windsurf in a watcher or run the standalone-
python conductor as a side channel.

## Troubleshooting
- If the agent ignores the modern rule, make sure
  `.windsurf/rules/agentic-stack.md` exists in the workspace.
- If you're on an older Windsurf build, make sure `.windsurfrules` exists
  at the project root.

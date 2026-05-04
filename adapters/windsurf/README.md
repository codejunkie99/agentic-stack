# Windsurf adapter

## Install
```bash
mkdir -p .windsurf/rules
cp adapters/windsurf/.windsurf/rules/agentic-stack.md ./.windsurf/rules/agentic-stack.md
cp adapters/windsurf/.windsurfrules ./.windsurfrules
```

Or:
```bash
./install.sh windsurf
```

## What it wires up
Windsurf's Cascade reads workspace rules from `.windsurf/rules/*.md`.
The adapter also writes legacy `.windsurfrules` for users on older
Windsurf builds.

## Verify
Ask Cascade "What's in your lessons file?" — it should read
`.agent/memory/semantic/LESSONS.md`.

## Notes
Windsurf doesn't have a first-class hook system like Claude Code, so
post-execution logging is the agent's responsibility (the rules file
instructs it to call `memory_reflect.py`). If you want automated logging,
run the standalone-python conductor in parallel as a background process.

For hard command enforcement, route commands through:

```bash
python3 .agent/tools/ztk.py exec -- <command>
```

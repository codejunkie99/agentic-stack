# Antigravity setup

## What the adapter installs
- `ANTIGRAVITY.md` at project root

## Install
```bash
./install.sh antigravity
```

## How it works
The Antigravity agent detects the `ANTIGRAVITY.md` file in the project root. This
file instructs the agent to consult the `.agent/` folder for all knowledge, skills,
and memory requirements. It follows a similar pattern to `CLAUDE.md` but is
tailored for the Antigravity ruleset.

## Logging note
Antigravity agents are instructed to call `memory_reflect.py` after significant
actions to maintain the episodic memory layer. If the harness supports automated
hooks, these should be configured to run `.agent/memory/auto_dream.py` on session exit.

## Troubleshooting
- If the agent is not following the instructions in `ANTIGRAVITY.md`, prompt it to "Consult the project instructions in ANTIGRAVITY.md".
- Ensure that the `.agent` folder exists and is populated. If not, re-run the installer.

## Manual Usage
The tools can be manually triggered from the terminal:
- `python3 .agent/tools/recall.py "intent"` to search semantic memory.
- `python3 .agent/tools/learn.py "rule"` to graduate a new lesson permanently.
- `python3 .agent/tools/show.py` to see the dashboard of brain state.

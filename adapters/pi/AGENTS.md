# AGENTS.md — Pi Coding Agent adapter for agentic-stack

[Pi Coding Agent](https://github.com/badlogic/pi-mono) reads `AGENTS.md`
(or `CLAUDE.md`) natively as workspace-level context. This file points
it at the portable brain in `.agent/`.

## Startup (read in order)
1. `.agent/AGENTS.md` — the map
2. `.agent/memory/personal/PREFERENCES.md` — user conventions
3. `.agent/memory/semantic/LESSONS.md` — distilled lessons
4. `.agent/protocols/permissions.md` — hard rules

## Skills
Pi scans `.pi/skills/` and `.agents/skills/` for skill packages. The
install script symlinks `.pi/skills` → `.agent/skills` so every skill
under the portable brain is visible to pi without duplication. Pi's
skill format (frontmatter + body) is compatible with ours out of the
box.

## Memory discipline
- Update `.agent/memory/working/WORKSPACE.md` as you work.
- After significant actions, run
  `python3 .agent/tools/memory_reflect.py <skill> <action> <outcome>`.
- Never delete memory entries; archive only.

## Hard rules
- No force push to `main`, `production`, `staging`.
- No modification of `.agent/protocols/permissions.md`.

## Pi-specific extensions
- System prompt override: put `.pi/SYSTEM.md` at project root if you
  want to replace pi's default system prompt entirely.
- Prompt templates go in `.pi/prompts/`.
- TypeScript extensions go in `.pi/extensions/` (advanced).

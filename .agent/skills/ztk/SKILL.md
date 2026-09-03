---
name: ztk
version: 2026-08-30
triggers: ["run shell command", "long output", "token savings", "compress output", "git diff too long", "ztk"]
tools: [bash]
preconditions: ["ztk binary on PATH (brew install codejunkie99/ztk/ztk)"]
constraints: ["never bypass ztk deny rules", "large outputs and known read-only commands are the target; small outputs need no compression", "hooks already rewrite commands automatically; use ztk run manually only in harnesses without hook support"]
category: tooling
---

# ztk — Token Compression for Shell Output

ztk compresses shell command output before it reaches an AI context.
Hooks are installed for Claude Code, Cursor, Gemini CLI, ZCode, and
OpenCode. Commands that ztk does not recognize pass through untouched.
Shell wrappers (`sh -c`, `bash -lc`, `eval`) always pass through.

## Manual use (harnesses without hook support: Codex CLI, Antigravity)

Wrap the command with `ztk run`:

```bash
ztk run git diff HEAD~5
ztk run ls -la src/
ztk run --raw <cmd>   # exact output, no compression
```

Exit codes propagate: an exit=2 after `ztk run grep ...` is usually the
command's own failure (grep uses 2 for errors), not a refusal. True
refusals print `ztk: command denied by permission rules` and target only
string-eval shells: `sh -c`, `zsh -c`, `eval`. Hooks never rewrite those,
so refusal only happens on explicit `ztk run`; run the command unwrapped
instead.

## Inspect savings

```bash
ztk stats
```

## Hook locations (auto-managed by `ztk init [-g] [--skip-permissions]`)

- Claude Code: `.claude/settings.json` PreToolUse -> `ztk rewrite --skip-permissions`
- ZCode: `~/.zcode/cli/config.json` hooks.PreToolUse (same command)
- OpenCode: `~/.config/opencode/plugin/ztk.js` (tool.execute.before)
- Cursor: `.cursor/hooks.json` -> `ztk cursor-rewrite`
- Gemini CLI: `.gemini/settings.json` BeforeTool -> `ztk gemini-rewrite`

To change hook flags, remove the ztk entry first — `ztk init` refuses
in-place migration. Backups of pre-ztk configs: `~/.ztk-install-backup-20260830/`.

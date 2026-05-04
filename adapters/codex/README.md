# Codex adapter

## Install
```bash
./install.sh codex
```

Or on Windows PowerShell:
```powershell
.\install.ps1 codex C:\path\to\your-project
```

## What it wires up
- `AGENTS.md` — Codex reads this natively as project instructions. If
  `AGENTS.md` already exists (for example from the pi, hermes, or
  opencode adapters), the installer leaves it in place.
- `.agents/skills/` → `.agent/skills/` — Codex scans `.agents/skills/`
  for repository skills. The installer creates a symlink when possible
  and falls back to copying / merging when symlinks are unavailable.
- `.codex/config.toml` — enables Codex hooks with `codex_hooks = true`.
- `.codex/hooks.json` — routes `PreToolUse`, `PermissionRequest`, and
  `PostToolUse` through the host-neutral `ztk` CLI.

## Verify
Run Codex in the project and ask:

```bash
codex --ask-for-approval never "Summarize the current instructions."
```

It should mention `.agent/AGENTS.md` and the portable memory files.

Then ask:

```bash
codex --ask-for-approval never "What's in my lessons file?"
```

It should read `.agent/memory/semantic/LESSONS.md`.

## Hook policy
Codex hooks currently cover Bash, `apply_patch` file edits, and MCP tools,
with documented coverage gaps for some shell and non-shell paths. Use:

```bash
python3 .agent/tools/ztk.py exec -- <command>
```

when an operation is not covered by a native Codex hook.

Codex `PreToolUse` currently supports deny decisions, but not a safe
ask/approval decision. ztk maps policy decisions that require approval to
deny at `PreToolUse` time, while `PermissionRequest` declines to decide
unless policy requires a hard deny.

## Notes
- If `.agents/skills/` is a copied directory rather than a symlink,
  re-run the installer after editing `.agent/skills/` to sync updates.

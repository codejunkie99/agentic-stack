# Adapter Capabilities

This matrix documents how ztk integrates with common coding-agent hosts.
The portable `.agent/` memory and skills can be read by any host that loads
project instructions, but hard policy enforcement requires either native
pre-tool hooks or routing operations through `ztk exec`.

| Host | Native integration | ztk support | Notes |
|---|---|---|---|
| Claude Code | `PreToolUse`, `PostToolUse`, `Stop` hooks in `.claude/settings.json` | Native hooks | Full-fidelity path. `PreToolUse` can return allow/ask/deny decisions. |
| Codex | Hooks behind `codex_hooks` in `.codex/config.toml`, with `.codex/hooks.json` | Native hooks | `PreToolUse` can deny supported Bash, `apply_patch`, and MCP calls. Ask/approval is not safely supported in `PreToolUse`, so ztk maps approval-required decisions to deny there. Codex documents current interception gaps, so `ztk exec` remains the fallback for uncovered operations. |
| OpenCode | `permission` rules in `opencode.json`, plus `AGENTS.md` instructions | Native permission map + wrapper | ztk installs native deny/ask rules for common risky operations and instructs agents to use `ztk exec` for policy-covered shell commands. |
| Cursor | `.cursor/rules/*.mdc` project rules and root `AGENTS.md` | Instruction + wrapper | Rules provide persistent prompt context. Cursor does not provide a ztk-owned pre-tool hook here, so hard enforcement requires commands to go through `ztk exec`. |
| Windsurf | Rules, memories, and workflows | Instruction + wrapper | Use `.windsurfrules` for context and `ztk exec` for commands needing hard policy checks. |
| Hermes / Pi / OpenClaw | Host-specific project instruction files | Instruction + wrapper | Memory and skills are shared. Enforcement is only as strong as the host's own permission system or explicit `ztk exec` usage. |

## Sources

- Claude Code hooks reference: https://code.claude.com/docs/en/hooks
- Codex hooks reference: https://developers.openai.com/codex/hooks
- OpenCode permissions: https://opencode.ai/docs/permissions/
- Cursor rules: https://docs.cursor.com/en/context/rules
- Windsurf rules, memories, and workflows: https://windsurf.com/university/general-education/intro-rules-memories

---
name: install-agentic-stack
description: Install or update the agentic-stack portable brain in the current project, then verify it. Read by an agent; no human steps required.
---

# Install agentic-stack (agent-executed)

You are an AI coding agent. Follow these steps in order; stop and report on
the first failure.

1. Detect the harness you are running in (Claude Code, Cursor, Windsurf,
   OpenCode, OpenClaw, Codex, Copilot CLI, Gemini, Hermes, Pi, Antigravity,
   or standalone Python).
2. Install the CLI (macOS/Linux):
   ```bash
   brew tap codejunkie99/agentic-stack && brew install agentic-stack
   ```
   Windows PowerShell: `git clone https://github.com/codejunkie99/agentic-stack && .\agentic-stack\install.ps1 <harness>`.
3. From the project root, run `agentic-stack <harness>` (for example
   `agentic-stack claude-code`). Accept the onboarding defaults unless the
   user told you otherwise.
4. Verify: `agentic-stack doctor .` must report no errors, and
   `python3 .agent/tools/show.py --plain` must print the brain dashboard.
5. Optional: register the memory MCP server so other hosts share the brain:
   `claude mcp add agentic-memory -- python3 "$PWD/.agent/tools/memory_mcp.py"`.
6. Report the installed version, the adapter wired, and the exact commands
   you ran. Do not modify `.agent/protocols/permissions.md`.

Already installed? Run `agentic-stack upgrade .` to refresh infrastructure
without touching memory or skills.

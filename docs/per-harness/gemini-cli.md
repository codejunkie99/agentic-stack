# Gemini CLI setup

[Gemini CLI](https://github.com/google-gemini/gemini-cli) reads `GEMINI.md`
natively as project context and supports MCP servers as a first-class
extension mechanism. Our adapter layers the portable `.agent/` brain on top
so you keep one knowledge base even if you later swap harnesses.

## What the adapter installs

- `GEMINI.md` at project root. Points Gemini CLI at `.agent/` for memory,
  skills, and protocols. Skipped if one already exists that references
  `.agent/` (for example from another adapter's GEMINI.md).
- `.gemini/agentic-stack-mcp/server.js` + `package.json` — an MCP server
  bridge that exposes the portable brain's Python CLI tools (`recall.py`,
  `memory_reflect.py`, `learn.py`, `show.py`) as MCP tools Gemini CLI can
  invoke directly.
- `.gemini/commands/agentic/*.toml` — four custom slash commands:
  `/agentic:recall`, `/agentic:learn`, `/agentic:status`, `/agentic:reflect`.

## Install

```bash
# Install Gemini CLI globally
npm install -g @google/gemini-cli

# Install the adapter
./install.sh gemini-cli

# Install MCP server Node.js dependencies
cd .gemini/agentic-stack-mcp && npm install --production && cd ../..

# Register the MCP server in gemini-cli settings (see below)
gemini
```

On Windows PowerShell:

```powershell
npm install -g @google/gemini-cli
.\install.ps1 gemini-cli C:\path\to\your-project
cd .gemini\agentic-stack-mcp
npm install --production
cd ..\..\..
gemini
```

### Register the MCP server

Gemini CLI does not auto-discover MCP servers from the filesystem. After
running `./install.sh gemini-cli`, add the following entry to your project's
`.gemini/settings.json` (or `~/.gemini/settings.json` for global access):

```json
{
  "mcpServers": {
    "agentic-stack-connector": {
      "command": "node",
      "args": [".gemini/agentic-stack-mcp/server.js"],
      "env": {
        "AGENTIC_PROJECT_DIR": "${PWD}"
      },
      "timeout": 30000
    }
  }
}
```

## How it works

- Gemini CLI loads `GEMINI.md` at session start. The adapter file points it
  at `.agent/AGENTS.md`, `PREFERENCES.md`, `LESSONS.md`, and
  `permissions.md`.
- The MCP server (`agentic-stack-connector`) is started by gemini-cli via
  stdio transport. It spawns `python3` subprocesses to call the brain's
  Python tools and returns the output as MCP tool results.
- The model can invoke `recall`, `memory_reflect`, `learn`, and
  `agentic_status` as MCP tools directly, or users can trigger them via
  custom slash commands in `.gemini/commands/agentic/`.
- The adapter intentionally does **not** install lifecycle hooks. Gemini
  CLI's hooks system is still evolving; manual tool calls (or MCP
  invocations triggered by the model) remain the stable cross-platform
  path.

### MCP tools exposed

| Tool | Maps to | Purpose |
|---|---|---|
| `recall` | `.agent/tools/recall.py` | Surface graduated lessons for an intent |
| `memory_reflect` | `.agent/tools/memory_reflect.py` | Log a significant event to episodic memory |
| `learn` | `.agent/tools/learn.py` | Teach a new rule in one shot |
| `agentic_status` | `.agent/tools/show.py` | Brain-state dashboard |

### Custom slash commands

| Command | Purpose |
|---|---|
| `/agentic:recall <intent>` | Query memory before a task |
| `/agentic:learn <rule>` | Store a new lesson |
| `/agentic:status` | Quick brain-state check |
| `/agentic:reflect <skill> <action> <outcome>` | Log a significant event |

## Verify

```bash
gemini
# Inside the session:
/mcp
# Expected: agentic-stack-connector (CONNECTED) with 4 tools

/agentic:status
# Expected: brain-state dashboard output

What lessons do I have about deploying?
# Expected: model calls recall tool automatically
```

## Troubleshooting

- **MCP server DISCONNECTED**: Ensure `npm install --production` was run
  inside `.gemini/agentic-stack-mcp/`. The server needs
  `@modelcontextprotocol/sdk` and `zod` as runtime dependencies.
- **"python3 not found"**: The MCP server shells out to `python3`. On
  stock Windows only `python` or `py` may be on PATH. Create an alias or
  add `python3` to PATH.
- **Tools not appearing**: Verify the `mcpServers` entry in
  `.gemini/settings.json` and the `AGENTIC_PROJECT_DIR` env var.
- **GEMINI.md not loaded**: Launch `gemini` from the project root where
  `GEMINI.md` was installed.
- **Server name has underscore**: Gemini CLI's policy parser splits MCP
  tool FQNs on the first underscore after `mcp_`. The adapter uses the
  hyphenated name `agentic-stack-connector` to avoid misparse.

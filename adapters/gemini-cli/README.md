# Gemini CLI adapter

## Install

```bash
# from the agentic-stack repo root
./install.sh gemini-cli /path/to/your-project
```

Or on Windows PowerShell:

```powershell
.\install.ps1 gemini-cli C:\path\to\your-project
```

After the adapter installs its files, you need one manual step:

### Register the MCP server

Add the `agentic-stack-connector` entry to your project or global
`.gemini/settings.json`. The adapter writes the server files to
`.gemini/agentic-stack-mcp/`, but gemini-cli does not auto-discover
MCP servers from the filesystem — you must declare them in settings.

**Project-level** (`.gemini/settings.json` in your project root):

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

**Global** (`~/.gemini/settings.json`) — use when all your projects use
agentic-stack:

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

Then install the MCP server's Node.js dependencies:

```bash
cd .gemini/agentic-stack-mcp && npm install --production
```

## What it wires up

- `GEMINI.md` — Gemini CLI reads this natively as project context; points
  it at `.agent/` for memory, skills, and protocols.
- `.gemini/agentic-stack-mcp/server.js` + `package.json` — MCP server
  bridge exposing `recall`, `memory_reflect`, `learn`, and `agentic_status`
  as tools Gemini CLI can invoke directly.
- `.gemini/commands/agentic/*.toml` — Custom slash commands:
  `/agentic:recall`, `/agentic:learn`, `/agentic:status`, `/agentic:reflect`.

## Verify

1. Start gemini-cli in the project directory:

   ```bash
   gemini
   ```

2. Check the MCP server is connected:

   ```
   /mcp
   ```

   Expected: `agentic-stack-connector (CONNECTED)` with four tools listed.

3. Test a tool:

   ```
   What lessons does my brain have about deploying?
   ```

   The model should call the `recall` MCP tool automatically.

4. Test a custom command:

   ```
   /agentic:status
   ```

   Should show the brain-state dashboard.

## Troubleshooting

- **MCP server DISCONNECTED**: Run `npm install` inside
  `.gemini/agentic-stack-mcp/`. The server needs `@modelcontextprotocol/sdk`
  and `zod` as runtime dependencies.
- **"python3 not found"**: The MCP tools shell out to `python3`. On Windows,
  the Python launcher `py` may work instead — set a shell alias or ensure
  `python3` is on PATH.
- **Tools not appearing in `/mcp`**: Verify the `mcpServers` entry in
  `.gemini/settings.json` points to the correct `server.js` path and that
  the `AGENTIC_PROJECT_DIR` env var resolves to the project root.
- **GEMINI.md not loaded**: Gemini CLI loads `GEMINI.md` from the current
  working directory on startup. Make sure you launch `gemini` from the
  project root where the adapter installed `GEMINI.md`.

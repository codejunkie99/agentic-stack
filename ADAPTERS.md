# Available Adapters

## Core adapters (master branch — synced with upstream)

These adapters are available in the `master` branch, which tracks upstream
`codejunkie99/agentic-stack` cleanly.

- `claude-code`
- `cursor`
- `windsurf`
- `opencode`
- `openclaw`
- `hermes`
- `pi`
- `codex`
- `standalone-python`
- `antigravity`

Install from master:
```bash
./install.sh <adapter-name>
```

## Fork-specific adapters (feature branches)

These adapters are maintained in dedicated feature branches and are NOT
merged into master. This keeps master clean for upstream sync.

### `gemini-cli` (branch: `feat/gemini-cli`)

Google Gemini CLI adapter. Adds `GEMINI.md` project context and an MCP server
bridge exposing `recall`, `memory_reflect`, `learn`, and `agentic_status` as
tools. Custom slash commands in `.gemini/commands/agentic/`.

Install from the feature branch:
```bash
git checkout feat/gemini-cli
./install.sh gemini-cli
```

See `docs/per-harness/gemini-cli.md` for MCP server registration instructions.

## Adding new fork-specific adapters

1. Create a feature branch from master:
   ```bash
   git checkout master
   git checkout -b feat/<adapter-name>
   ```
2. Add adapter files under `adapters/<adapter-name>/`
3. Add per-harness docs under `docs/per-harness/<adapter-name>.md`
4. Update this file (`ADAPTERS.md`) with the new adapter
5. Update `install.sh` / `install.ps1` comments to list the fork adapter
6. Push: `git push fork feat/<adapter-name>`
7. **Never merge the feature branch into master**

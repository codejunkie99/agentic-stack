Pull latest from GitHub and sync definitions from Confluence.

## Steps

1. **Git pull** — Run `git pull origin main` (or the current branch) to get the latest repo changes. If it fails due to uncommitted changes, warn the user and stop.

2. **Confluence sync** — Try the Python script first, fall back to MCP tools if blocked by IP allowlist.

   ### Option A: Python Script (preferred when on allowlisted IP/VPN)
   ```bash
   python3 scripts/sync-confluence.py --yes
   ```
   This script reads `config.yaml` and `.env`, calls the Confluence REST API, converts pages to markdown via pandoc, and writes locally.

   If the script fails due to missing credentials, tell the user to add their email and API token to `.env`.

   ### Option B: MCP Fallback (when IP allowlist blocks REST API)

   If the script fails with "permission" or "IP address" errors, use MCP tools that bypass the allowlist:

   1. **Discover pages** — Use `searchAtlassian` with `query="space:BCTAH"` (substitute actual space_key from `config.yaml`). Run multiple queries to find all pages:
      - `space:<KEY>` for a general listing
      - `space:<KEY> title:<folder>` for each folder in the mappings (agents, rules, personas, specs, workflows, context)

   2. **Fetch each page** — For each result, use `fetchAtlassian` with the ARI from the search result's `id` field. This returns the full page text in markdown-like format.

   3. **Map to local paths** — Use the page's ancestor path (visible in the URL or inferred from search result context) to match against folder mappings:

      | Confluence folder | Local path |
      |---|---|
      | `agents/` | `.claude/agents/` |
      | `rules/` | `.claude/rules/` |
      | `context/projects/` | `context/project/` |
      | `personas/` | `personas/` |
      | `specs/` | `specs/` |
      | `workflows/` | `workflows/` |

   4. **Write files** — Convert page title to kebab-case filename (e.g., "Program Director" → `program-director.md`). Write to the mapped local path. Create subdirectories as needed.

   5. **Handle page hierarchy** — If a page's URL contains path segments matching a folder mapping, use that to determine placement. If ambiguous, use the page title and ask the user.

   **Important:** `fetchAtlassian` returns plain text, not HTML storage format — no pandoc conversion needed.

3. **Report** — Summarize what was synced: number of pages, which folders, any pages that couldn't be matched.

## Folder Mappings

| Confluence folder | Local path |
|---|---|
| `agents/` | `.claude/agents/` |
| `rules/` | `.claude/rules/` |
| `context/projects/` | `context/project/` |
| `personas/` | `personas/` |
| `specs/` | `specs/` |
| `workflows/` | `workflows/` |

All subfolders are preserved. All other Confluence content is ignored.

## Credentials

- **Python script (Option A):** Uses Confluence REST API directly. Credentials go in `.env` (gitignored):
  ```
  CONFLUENCE_USER_EMAIL=your.email@bcg.com
  CONFLUENCE_API_TOKEN=your-token-here
  ```
  Generate a token at: https://id.atlassian.com/manage-profile/security/api-tokens

- **MCP fallback (Option B):** Uses the Atlassian MCP server's built-in authentication (configured separately in Claude Code settings). No `.env` needed.

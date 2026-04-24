# Confluence Access Skill

Use this skill for all Confluence read and write operations. It handles the IP allowlist restriction that blocks direct REST API calls.

> **WARNING: SCOPE RESTRICTION**
> Only access the Confluence space whose `space_key` is defined in `config.yaml`. Do NOT read, search, or interact with any other space. Before any Confluence operation, read `config.yaml` to confirm the configured `space_key`. After receiving search results, **discard any results whose URL does not contain `/spaces/<space_key>/`**. This is a hard rule — no exceptions.

## The Problem

The Atlassian org enforces an IP allowlist. All REST API v2/v1 endpoints are blocked, including:
- `getConfluenceSpaces`, `getPagesInConfluenceSpace`, `getConfluencePage`
- `getConfluencePageDescendants`, `getConfluencePageFooterComments`
- `searchConfluenceUsingCql` (CQL queries)
- `searchJiraIssuesUsingJql` (JQL queries)
- `createConfluencePage`, `updateConfluencePage`

**NEVER call these tools. They will always fail. Do not retry them.**

## What Works

Two MCP tools bypass the IP allowlist (they use Atlassian Graph Gateway, not REST API):

| Tool | Purpose | Key Rule |
|---|---|---|
| `searchAtlassian` (Rovo Search) | Discover pages, search content | Do NOT pass `cloudId` — auto-derived from token |
| `fetchAtlassian` (ARI Fetch) | Read full page content by ARI | Do NOT pass `cloudId` — extracted from ARI |

## Config Prerequisites

Before any operation, read `config.yaml`. You need:

| Field | Example | Purpose |
|---|---|---|
| `space_key` | `BCTAH` | Scope filter for search results |
| `space_id` | `2938077250` | Numeric space ID |
| `homepage_id` | `2938077902` | Homepage page ID |
| `cloud_id` | `2436163d-7967-483c-93a6-bb953a1adbef` | UUID for constructing ARIs directly |

If `cloud_id` is missing, run one `searchAtlassian` query and extract it from `results[0].metadata.cloudId`. Save it to `config.yaml`.

---

## Core Operations

### 1. Fetch a Page by Known ID (fastest — zero searches)

If you already have a page ID (from config.yaml, a URL, or a previous result), construct the ARI directly:

```
fetchAtlassian(id="ari:cloud:confluence:<cloud_id>:page/<page_id>")
```

**Where to find page IDs:**
- `config.yaml` — stores `homepage_id` and any cached page IDs
- Confluence URLs — the numeric segment: `.../pages/2945286150/transcript-analyst` → page ID is `2945286150`
- Previous search results — the ARI `id` field contains the page ID

### 2. Search for Pages (when ID is unknown)

Use `searchAtlassian`. Rovo is **semantic search** — it does NOT support structured filters like `space:KEY` or `title:`.

**Effective search patterns:**
```
# Search by space name + folder name (best for discovering folder contents)
searchAtlassian(query="BCTAH agents")
searchAtlassian(query="BCTAH workflows")

# Search by space name + page title keywords
searchAtlassian(query="BCTAH executive-sponsor")

# Search by space name + content keywords
searchAtlassian(query="BCTAH RAID log status update")

# Search using the full space name for precision
searchAtlassian(query="BDO Case Team Agent Harness agents")
```

**After every search, FILTER results:**
- Keep only results where `url` contains `/spaces/<space_key>/` (e.g., `/spaces/BCTAH/`)
- Discard everything else — Rovo returns results from across the entire Atlassian org

### 3. Systematic Space Scan (for sync or bulk discovery)

To discover all pages in the space efficiently, search once per known folder. This mirrors the folder-mapping approach used by `scripts/sync-confluence.py`:

| Confluence Folder | Search Query | Local Path |
|---|---|---|
| `agents/` | `"BCTAH agents"` | `.claude/agents/` |
| `rules/` | `"BCTAH rules"` | `.claude/rules/` |
| `context/projects/` | `"BCTAH context projects"` | `context/project/` |
| `personas/` | `"BCTAH personas"` | `personas/` |
| `specs/` | `"BCTAH specs"` | `specs/` |
| `workflows/` | `"BCTAH workflows"` | `workflows/` |

**Protocol for a full scan:**
1. Run all 6 searches (can be parallelized)
2. Filter each result set — keep only URLs containing `/spaces/BCTAH/`
3. Collect unique ARIs (deduplicate across searches — some pages may appear in multiple results)
4. Fetch each page using `fetchAtlassian`
5. Determine local path from the page's URL or title (see "Hierarchy Inference" below)

### 4. Hierarchy Inference (mapping Confluence pages to local paths)

Since we can't call the ancestor API, infer page placement from:

**Method A: URL path (most reliable)**
Confluence URLs encode hierarchy: `https://bcgx.atlassian.net/wiki/spaces/BCTAH/pages/12345/page-title`

While Rovo doesn't always return full URL paths, the page title usually matches its parent folder:
- A page titled `executive-sponsor` found via search query `"BCTAH agents"` → maps to `.claude/agents/executive-sponsor.md`
- A page titled `sample-workflow` found via `"BCTAH workflows"` → maps to `workflows/sample-workflow.md`

**Method B: Cross-reference with local files**
Check what files already exist locally to validate placement:
```
ls .claude/agents/        # known agent files
ls workflows/             # known workflow files
ls personas/              # known persona files
```
If a page title matches an existing local filename, it belongs in that folder.

**Method C: Content inspection**
Fetch the page and inspect its content. Agent pages have frontmatter with fields like `name:`, `title:`, `category:`. Workflow pages have `Team Composition` tables. This confirms the page type if placement is ambiguous.

**Title-to-filename conversion** (matches sync script logic):
1. Lowercase the title
2. Remove non-alphanumeric characters (keep hyphens and spaces)
3. Replace spaces with hyphens
4. Append `.md`

Example: `"Executive Sponsor"` → `executive-sponsor.md`

---

## Writing to Confluence

**Write operations are blocked by the IP allowlist.** `createConfluencePage` and `updateConfluencePage` will fail.

**Workaround:**
1. Draft content locally in `output/confluence-drafts/` with a descriptive filename
2. Use markdown format (Confluence accepts markdown paste)
3. Include the target page title and parent page for placement
4. Tell the user to paste it into Confluence manually, or wait for allowlisted IP access

---

## Fallback: When Rovo Can't Find a Page

Rovo has **indexing lag** on newly created pages (can take hours or days). If a search returns no results:

1. **Construct ARI manually** — If you know the page ID (from config.yaml, a URL the user shared, or git history), build the ARI:
   ```
   ari:cloud:confluence:<cloud_id>:page/<page_id>
   ```
2. **Try alternative search terms** — Rovo is semantic; rephrase the query
3. **Check config.yaml** — for stored page IDs (homepage_id, etc.)
4. **Ask the user** — They may have the page URL or know the page ID

---

## Rules

- **NEVER call blocked REST API tools** — they will always fail with IP errors
- **NEVER pass `cloudId`** to `searchAtlassian` or `fetchAtlassian`
- **ALWAYS filter search results** by URL containing `/spaces/<space_key>/`
- **ALWAYS read `config.yaml` first** for space_key, cloud_id, and stored page IDs
- **Prefer ARI construction over searching** when you have a page ID — it's one call vs two
- **Cite sources** — include Confluence page title and URL when referencing content
- See `.claude/rules/atlassian-rules.md` for safety rules (read-before-write, merge-don't-overwrite, etc.)

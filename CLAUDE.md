# Project Instructions

Note: `.agent/` in this repository is the agentic-stack distribution source,
not an installed brain — do not write memory or lessons into it.

## Code search — stele-context first

This repository is indexed by stele-context; the one store is
`.stele-context`. The CLI default (`~/.stele-context`) is a cross-project
catch-all — never use it. zsh resolves `STELE_CONTEXT_STORAGE_DIR` to the
nearest enclosing store; any other shell passes
`--storage-dir .stele-context` before the subcommand.

- Conceptual: `stele-context search "<intent>"` (semantic)
- Identifier or literal, token-capped: `stele-context agent-grep "<text>" --max-tokens 2000`
- Exact string: `stele-context search-text "<literal>"`
- Symbols: `stele-context find-definition|find-references <Symbol>`
- Stale results: `stele-context detect`, then `stele-context --storage-dir .stele-context index .`

A hit is a pointer, not evidence — read the file before acting.

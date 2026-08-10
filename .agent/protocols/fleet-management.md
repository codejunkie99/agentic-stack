# Fleet management

## Purpose

Manage one portable-brain profile across many development workspaces without
creating duplicate brain authorities or overwriting project-owned state.

## Authority model

The fleet manifest is the source of truth for workspace ownership. A Git
repository is not automatically a brain root. One workspace brain can own
multiple child repositories.

Each workspace has exactly one mode:

- `managed`: agentic-stack owns the workspace brain and can upgrade it.
- `source`: the agentic-stack source tree; validate it but do not upgrade it.
- `pending`: intended for adoption, but blocked by a stated decision or conflict.
- `external`: explicitly owned by another agent system; record the rationale and
  do not mutate it.

Every discovered Git repository and every top-level fleet directory must belong
to one workspace or one reasoned exclusion. Overlapping owners are invalid.

## Manifest

Use `agentic-stack.fleet.json` at the fleet root. Validate it against
`protocols/tool_schemas/fleet-manifest.schema.json`.

Each workspace declares a stable id, path, mode, display name, child
repositories, expected adapters, and rationale when the mode is `pending` or
`external`.

## Commands

Audit without mutation:

```bash
agentic-stack fleet audit /path/to/agentic-stack.fleet.json
```

Preview all managed workspace changes:

```bash
agentic-stack fleet upgrade /path/to/agentic-stack.fleet.json --dry-run
```

Apply after review:

```bash
agentic-stack fleet upgrade /path/to/agentic-stack.fleet.json --yes
```

## Rollout gates

1. Validate the manifest and reject gaps or overlaps.
2. Validate the trusted agentic-stack source.
3. Preview every managed workspace.
4. Snapshot every file that the upgrade can change.
5. Upgrade one workspace at a time.
6. Write the project profile identity from the fleet manifest.
7. Compare managed artifacts with the trusted distribution and run the trusted
   validator.
8. Roll back the workspace if any verification fails.
9. Continue only with independently verified workspaces.
10. Report `pending` and `external` workspaces without silently adopting them.

## Integrity rules

- A child repository cannot own a second brain when its workspace already owns
  one.
- A local project protocol is not a managed global artifact and must survive an
  upgrade.
- A managed artifact can be replaced only from the trusted distribution.
- Fleet audit is read-only and must not execute target-controlled validators.
- A source branch is not a release. Fleet-wide adoption requires a merged,
  released version and a successful audit after installation.
- Rollback evidence and the failed validation result must remain visible.

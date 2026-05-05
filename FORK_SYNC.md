# Fork Synchronization Guide

This document explains how to keep this fork (`conrackx/agentic-stack-plus`)
in sync with the upstream repo (`codejunkie99/agentic-stack`) while
maintaining fork-specific features in dedicated branches.

## Remotes

```
origin  https://github.com/codejunkie99/agentic-stack.git  (upstream)
fork    git@github.com:conrackx/agentic-stack-plus.git     (fork)
```

## Branch Strategy

```
master                — CLEAN mirror of upstream. Never modified by fork.
feat/gemini-cli       — Gemini CLI adapter (fork-specific)
feat/<adapter-name>   — Future fork-specific adapters
```

**master is NEVER modified by the fork.** It only receives fast-forward
merges from upstream. All fork-specific work lives in feature branches.

## Sync Procedure (run regularly)

```bash
# 1. Fetch latest upstream changes
git fetch origin

# 2. Update master (clean fast-forward only)
git checkout master
git merge origin/master --ff-only
git push fork master

# 3. Rebase each feature branch onto updated master
git checkout feat/gemini-cli
git rebase master
git push fork feat/gemini-cli --force-with-lease
```

## NEVER do these on master

- Add fork-specific adapters or files
- Modify CHANGELOG.md with fork-only entries
- Bump version differently from upstream
- Merge from feature branches
- Commit any fork-specific changes

## ALWAYS do these on feature branches

- Develop fork-specific adapters
- Add fork-specific CHANGELOG entries (under a `[fork/<name>]` section)
- Update install.sh / install.ps1 comments to list fork adapters
- Update README.md to document fork features
- Update ADAPTERS.md with new fork adapters

## Resolving Rebase Conflicts

When rebasing a feature branch onto updated master, common conflicts:

### CHANGELOG.md
- Upstream added a new release section at the top
- Your feature branch also added a section at the top
- **Resolution:** Keep both sections. Fork entries use `[fork/<name>]`
  format (not a semver version) so they never collide with upstream versions.

### README.md
- Upstream updated the "New in vX.Y.Z" section
- Your feature branch added a fork feature section
- **Resolution:** Keep upstream's "New in" section. Your fork section
  goes below it with a clear "Fork feature:" prefix.

### install.sh / install.ps1
- Upstream may have reformatted comments
- **Resolution:** Keep upstream's core adapter list. Add fork adapter
  on a separate comment line: `# Fork adapters (branch: feat/X): X`

## Fork-specific files to preserve during rebase

These files exist only in feature branches and must be preserved:

### feat/gemini-cli branch:
- `adapters/gemini-cli/` (10 files)
- `docs/per-harness/gemini-cli.md`
- `test_gemini_mcp.py`
- `adapters/opencode/opencode.json` (fixed `permission` key)
- `ADAPTERS.md`
- `FORK_SYNC.md`

## Version Collision Prevention

The v0.13.0 collision taught us:

1. **Check upstream before any version work:** `git fetch origin && git log origin/master --oneline -5`
2. **Never bump version on a feature branch** using a semver number that
   upstream might use. Use `[fork/<feature-name>]` format instead.
3. **Sync master before starting new work:** Always `git merge origin/master --ff-only` on master, then rebase your feature branch.
4. **Keep CHANGELOG entries separate:** Fork entries use `[fork/<name>]`
   format so they never collide with upstream `[X.Y.Z]` entries.

## Agent instructions for future syncs

1. Read this file (`FORK_SYNC.md`) first.
2. Read `ADAPTERS.md` to understand which adapters live where.
3. **On master:** Only `git merge origin/master --ff-only && git push fork master`.
4. **On feature branches:** Rebase onto master, resolve conflicts per rules above.
5. Never merge feature branches into master.
6. Never delete fork-specific files during rebase.
7. After resolving conflicts, run `python3 test_gemini_mcp.py` on the
   feat/gemini-cli branch to verify adapter integrity.
8. Push to fork remote (`fork`, not `origin`).

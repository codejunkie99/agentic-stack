# Permissions

The ztk policy engine reads this file and enforces it before supported
tool invocations. Native-hook hosts call it automatically; other hosts
must route policy-covered shell commands through `ztk exec`. Humans edit
this file; the agent does not.

## Always allowed (no approval)
- Read any file in the project directory.
- Run tests.
- Create branches.
- Write to `memory/` and `skills/` directories.
- Create draft pull requests.
- Read public HTTP APIs in the approved domains list.

## Requires approval
- Merge pull requests.
- Deploy to any environment (staging, production).
- Delete files outside of `memory/working/`.
- Install new dependencies or upgrade pinned versions.
- Modify CI/CD configuration.
- Run database migrations.

## Never allowed
- Force push to `main`, `production`, or `staging`.
- Access secrets or credentials directly (use env vars through the shell only).
- Send HTTP requests to domains not on the approved list.
- Modify `permissions.md` (only humans edit this file).
- Disable or bypass ztk policy hooks or `ztk exec`.
- Delete entries from episodic or semantic memory (archive, don't delete).

## Approved external domains
- `api.github.com`
- `registry.npmjs.org`
- `pypi.org`
- `api.anthropic.com`
- `api.openai.com`

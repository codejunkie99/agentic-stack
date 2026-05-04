# Hermes Agent setup

[Hermes Agent](https://github.com/nousresearch/hermes-agent) (Nous
Research) is an open-source AI agent with persistent memory and a
closed learning loop. Our adapter layers the portable `.agent/` brain
on top for shared memory and skills. It is not full hook parity with
Claude Code.

## What the adapter installs
- `AGENTS.md` at project root (Hermes reads this natively)

## Install
```bash
./install.sh hermes
```

## How it works
- Hermes reads `AGENTS.md` as workspace-level project context.
- Skills under `.agent/skills/` follow frontmatter-plus-body that is
  compatible with the agentskills.io standard Hermes uses. Browse via
  `/skills` in the Hermes CLI.
- Hermes's own `MEMORY.md` / `USER.md` / `SOUL.md` are complementary —
  treat `.agent/memory/` as the source of truth and mirror selectively.
- Hermes does not provide ztk with a hard pre-tool gate in this adapter.
  Use `python3 .agent/tools/ztk.py exec -- <command>` for shell commands
  that must be checked by `.agent/protocols/permissions.md`.

## Troubleshooting
- If `AGENTS.md` isn't picked up, run `hermes setup` — the wizard can
  re-register workspace-level context files.
- Hermes supports multiple models via its gateway, but permission
  enforcement remains best-effort unless the harness exposes pre-tool
  hooks.

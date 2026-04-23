# Standalone Python setup

## What the adapter installs
- `run.py` at project root — a DIY conductor entrypoint you can edit
  freely. Skipped on re-install if you already have one (your edits
  are preserved).

## Install
```bash
./install.sh standalone-python
```

Or on Windows:
```powershell
.\install.ps1 standalone-python
```

## How it works
Standalone Python is the "no harness" path. You write your own loop
that drives an LLM (any provider — Anthropic, OpenAI, Ollama, etc.)
and uses `.agent/` as the brain. The shipped `run.py` is a starting
template; you're expected to adapt it to your provider, prompt
format, and tool set.

The portable brain (`.agent/`) works the same as with any other
harness: read `AGENTS.md` first, log via
`python3 .agent/tools/memory_reflect.py`, recall via
`python3 .agent/tools/recall.py`, etc.

## Verify
After install, the directory structure looks like:

```
your-project/
├── .agent/                       # portable brain
└── run.py                        # your conductor entrypoint
```

Run `python3 run.py` (or whatever you customize it to). It should at
minimum read AGENTS.md and surface lessons before acting.

## Why no hook support
Standalone Python is full control by definition. You wire whatever
hooks you want directly — call `log_execution()` from `.agent/harness/hooks/`
where it makes sense in your loop. The adapter ships no settings.json
or extension config because there's no harness to configure.

## Audit
After install, `./install.sh doctor` will report `standalone-python`
as installed (signal: `run.py` present). Doctor doesn't check the
content of `run.py` since it's user-customized.

## Re-install
`./install.sh standalone-python` on a project that already has
`run.py` is a no-op for `run.py` itself (`merge_policy: skip_if_exists`).
The `.agent/` brain is also left alone if already present. Safe
to re-run.

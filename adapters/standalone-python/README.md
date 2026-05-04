# Standalone Python adapter

The DIY path from the article. You own the loop, the tool calling, the file
watching, and the hook-equivalent enforcement. This is not a drop-in
general LLM adapter; it only works well if your custom loop calls the
same pre-tool and post-tool checks that Claude Code exposes natively.

## Install
```bash
pip install -r requirements.txt
cp adapters/standalone-python/run.py ./run.py
export ANTHROPIC_API_KEY=...   # or OPENAI_API_KEY with AGENT_PROVIDER=openai
```

Or:
```bash
./install.sh standalone-python
```

## Usage
```bash
python run.py "reflect on today's work"
python run.py "commit the staged changes"
```

## Choose a provider
```bash
export AGENT_PROVIDER=anthropic   # default
export AGENT_MODEL=claude-sonnet-4-5

# or, if your custom loop implements equivalent tool hooks:
export AGENT_PROVIDER=openai
export AGENT_MODEL=<openai-model>
```

## Cron the dream cycle
```bash
crontab -e
# nightly at 3am:
0 3 * * * cd /path/to/project && python3 .agent/memory/auto_dream.py >> .agent/memory/dream.log 2>&1
```

## What this harness does (and doesn't)
- It assembles context from the brain within a token budget.
- It calls your chosen model.
- It logs to episodic memory after each call.
- It does **not** decide which skills to load — the context builder does,
  via trigger matching.
- It does **not** enforce permissions by itself — your loop must invoke
  `.agent/harness/hooks/pre_tool_call.py` before external tools, or route
  shell commands through `python3 .agent/tools/ztk.py exec -- <command>`.

# Standalone Python adapter

The DIY path from the article. You own the loop, the tool calling, the file
watching. Useful when you want to run any LLM (Anthropic, OpenAI, local)
without depending on Cursor / Claude Code / etc.

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

# or
export AGENT_PROVIDER=openai
export AGENT_MODEL=gpt-4o

# or
export AGENT_PROVIDER=minimax
export AGENT_MODEL=MiniMax-M3
export MINIMAX_API_KEY=...
# Optional: AGENT_MINIMAX_REGION=global_en|cn_zh (default global_en)
# Optional: AGENT_MINIMAX_WIRE=openai|anthropic (default openai)
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
- It does **not** enforce permissions — that's the `pre_tool_call` hook's
  job, invoked only when the agent actually calls external tools.

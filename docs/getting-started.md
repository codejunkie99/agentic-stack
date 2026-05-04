# Getting Started

## 1. Clone or drop `.agent/` into your project

```bash
# new project
git clone https://github.com/<you>/agentic-stack.git my-project
cd my-project

# or add to an existing project
cp -R /path/to/agentic-stack/.agent ./
cp /path/to/agentic-stack/install.sh ./
```

## 2. Pick your harness

```bash
./install.sh claude-code        # or cursor, windsurf, opencode,
                                # openclaw, hermes, pi, codex,
                                # standalone-python, antigravity
```

Claude Code and Codex install native ztk hooks. For hosts without native
pre-tool hooks, run policy-covered shell commands through:

```bash
python3 .agent/tools/ztk.py exec -- <command>
```

Each adapter has its own `README.md` under `adapters/<name>/`.

## 3. Customize `PREFERENCES.md`

Open `.agent/memory/personal/PREFERENCES.md` and fill in 5–10 lines about
your code style, workflow, and constraints. This is the one file every
user should customize on day one.

## 4. Run the dream cycle on a schedule

```bash
crontab -e
# nightly at 3am:
0 3 * * * cd /path/to/project && python3 .agent/memory/auto_dream.py >> .agent/memory/dream.log 2>&1
```

## 5. Start using it

Open your harness and ask it anything. The first few days it will feel
stateless. After ~2 weeks you'll notice it checking past lessons, logging
failures with reflection, and (if you let it) proposing skill rewrites.

## Optional: add a visual system with `DESIGN.md`

If your project has UI, drop a Google Stitch-style `DESIGN.md` file in the
project root. The bundled `design-md` skill tells compatible agents to use
that file as the source of truth for colors, typography, spacing, component
rules, and design rationale instead of inventing visual choices.

When Node tooling is available, agents can validate the file with:

```bash
npx @google/design.md lint DESIGN.md
```

## Verify the wiring
```bash
python3 .agent/tools/budget_tracker.py "commit and push"
# tokens_used, chars, budget, headroom
```

If `tokens_used` is 0, your memory files aren't being read — check paths.

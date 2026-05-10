# Getting Started

## 1. Install agentic-stack

### macOS / Linux with Homebrew (recommended)

```bash
brew tap codejunkie99/agentic-stack https://github.com/codejunkie99/agentic-stack
brew install agentic-stack
```

This installs the `agentic-stack` command.

### Source checkout (no Homebrew)

If you prefer not to use Homebrew, clone the repo and run `install.sh`
against the project you want to wire:

```bash
git clone https://github.com/codejunkie99/agentic-stack.git
cd agentic-stack
./install.sh claude-code /path/to/your-project
```

This path does not install a global `agentic-stack` command. Keep the clone
around and run future management commands through `./install.sh`.

### Windows (PowerShell)

```powershell
git clone https://github.com/codejunkie99/agentic-stack.git
cd agentic-stack
.\install.ps1 claude-code C:\path\to\your-project
```

## 2. Pick your harness

If you installed with Homebrew, run the CLI from your project root:

```bash
cd your-project
agentic-stack claude-code
# or: cursor | windsurf | opencode | openclaw | copilot-cli | gemini | hermes | pi | codex | standalone-python | antigravity
```

If you are using a source checkout, the install command above already picked
the harness. To add another adapter later, run
`./install.sh add <adapter> /path/to/your-project` from the clone.

The onboarding wizard runs automatically, populating
`.agent/memory/personal/PREFERENCES.md` and `.agent/memory/.features.json`.

Each adapter has its own `README.md` under `adapters/<name>/`.

## 3. Customize `PREFERENCES.md`

Open `.agent/memory/personal/PREFERENCES.md` and fill in 5–10 lines about
your code style, workflow, and constraints. This is the one file every
user should customize on day one. The onboarding wizard pre-populates it,
but you can always edit it later.

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

## Managing your project

After the initial setup, Homebrew users can run verb-style subcommands from
the project root:

```bash
agentic-stack dashboard           # TUI dashboard: health, verify, memory, team, skills
agentic-stack mission-control     # beta local web dashboard; Ctrl-C turns it off
agentic-stack brain status        # optional external Brain CLI integration
agentic-stack status              # one-screen view: which adapters, brain stats
agentic-stack doctor              # read-only audit; green / yellow / red per adapter
agentic-stack upgrade --dry-run   # preview safe .agent infrastructure refresh
agentic-stack upgrade --yes       # apply latest harness/memory/tools + new skills
agentic-stack sync-manifest       # rebuild .agent/skills/_manifest.jsonl from SKILL.md
```

Source checkout users can run the same verbs through the clone:

```bash
./install.sh dashboard /path/to/your-project
./install.sh mission-control /path/to/your-project
./install.sh brain status
./install.sh status /path/to/your-project
./install.sh doctor /path/to/your-project
./install.sh upgrade /path/to/your-project --dry-run
./install.sh upgrade /path/to/your-project --yes
./install.sh sync-manifest /path/to/your-project
```

PowerShell users can run the same verbs through `.\install.ps1`.

Adding or removing adapters with Homebrew:

```bash
agentic-stack add cursor          # add a second adapter alongside Claude Code
agentic-stack remove cursor       # confirm prompt + delete
agentic-stack manage              # interactive TUI for add/remove/audit
```

Source checkout equivalents:

```bash
./install.sh add cursor /path/to/your-project
./install.sh remove cursor /path/to/your-project
./install.sh manage /path/to/your-project
```

## Optional: add a visual system with `DESIGN.md`

If your project has UI, drop a Google Stitch-style `DESIGN.md` file in the
project root. The bundled `design-md` skill tells compatible agents to use
that file as the source of truth for colors, typography, spacing, component
rules, and design rationale instead of inventing visual choices.

When Node tooling is available, agents can validate the file with:

```bash
npx @google/design.md lint DESIGN.md
```

## Keeping up to date

```bash
brew update && brew upgrade agentic-stack
cd your-project
agentic-stack upgrade --dry-run   # preview changes
agentic-stack upgrade --yes       # apply; won't overwrite your memory or config
```

Source checkout users should update the clone first:

```bash
cd /path/to/agentic-stack
git pull --ff-only
./install.sh upgrade /path/to/your-project --dry-run
./install.sh upgrade /path/to/your-project --yes
```

The upgrade command refreshes skeleton-owned `.agent` infrastructure
(harness scripts, top-level memory/tools Python files, skill index, and new
skill directories) but never overwrites `CLAUDE.md`, `.claude/settings.json`,
personal/semantic/episodic/working memory, candidates, or existing skill
directories.

## Verify the wiring

```bash
python3 .agent/tools/budget_tracker.py "commit and push"
# tokens_used, chars, budget, headroom
```

If `tokens_used` is 0, your memory files aren't being read — check paths.

#!/usr/bin/env bash
# sync-target.sh — push fork-side harness improvements into an existing target.
#
# Usage:
#   ./sync-target.sh <target-dir> [--dry-run] [--yes]
#
# Purpose: when fork ships a skill update, agent prompt change, tool fix, or
# new vendored skill, this script propagates those changes to an existing
# install without overwriting target-specific evolved state.
#
# Distinct from install.sh: install.sh is for FRESH targets (drops the brain
# wholesale on first install). sync-target.sh is for EXISTING targets that
# need to receive fork updates without re-bootstrapping.
#
# What gets refreshed (fork → target):
#   - .agent/skills/                        (full skill content, including
#                                            vendored skills via INTEGRATION.md)
#   - .agent/tools/*.py                     (harness tooling)
#   - .agent/protocols/*.md                 (protocols)
#   - .agent/AGENTS.md                      (root config)
#   - .agent/harness/                       (hooks + context budget + salience)
#   - .agent/context/                       (generic consulting context)
#   - .agent/workflows/                     (deliverable workflow contracts)
#   - adapters/bcg/agents/         -> .claude/agents/    (if bcg_adapter=enabled)
#   - adapters/bcg/commands/       -> .claude/commands/  (if bcg_adapter=enabled)
#   - adapters/bcg/skills/         -> .agent/skills/     (if bcg_adapter=enabled)
#   - adapters/claude-code/commands/ -> .claude/commands/ (always)
#
# What is preserved (never touched):
#   - .agent/memory/                        (working, episodic, semantic, personal)
#   - .agent/memory/client/                 (engagement briefing material)
#   - .claude/agent-memory/                 (per-agent state)
#   - output/                               (engagement deliverables)
#   - .git/                                 (engagement git history)
#   - target's CLAUDE.md, .claude/settings.json (use install.sh --reconfigure
#                                                if those need refreshing)
#   - target's .agent/config.json           (engagement-specific settings)
#
# Flags:
#   --dry-run    Show what would be copied without writing
#   --yes        Skip confirmation prompt
#
# Note: this is a manual sync mechanism. The deferred install.sh --upgrade
# (Step 8.5) will be the formal install-time-aware version.

set -euo pipefail

FORK="$(cd "$(dirname "$0")" && pwd)"
DRY_RUN=false
SKIP_CONFIRM=false
TARGET=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --yes|-y) SKIP_CONFIRM=true; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    -*) echo "error: unknown flag: $1" >&2; exit 2 ;;
    *)
      if [[ -z "$TARGET" ]]; then
        TARGET="$1"
      else
        echo "error: unexpected argument: $1" >&2
        exit 2
      fi
      shift
      ;;
  esac
done

if [[ -z "$TARGET" ]]; then
  echo "error: target dir required" >&2
  echo "usage: $0 <target-dir> [--dry-run] [--yes]" >&2
  exit 2
fi

TARGET="$(cd "$TARGET" && pwd)"

# --- safety checks --------------------------------------------------------

if [[ ! -d "$TARGET/.agent" ]]; then
  echo "error: $TARGET does not have .agent/ — is this an installed target?" >&2
  echo "       use install.sh for fresh installs." >&2
  exit 2
fi

if [[ "$FORK" == "$TARGET" ]]; then
  echo "error: refusing to sync fork to itself ($FORK)" >&2
  exit 2
fi

# Check bcg_adapter flag in target's config
BCG_ENABLED=false
if [[ -f "$TARGET/.agent/config.json" ]]; then
  if grep -q '"bcg_adapter":\s*"enabled"' "$TARGET/.agent/config.json" 2>/dev/null; then
    BCG_ENABLED=true
  fi
fi

# --- copy plan ------------------------------------------------------------

# Format: src_rel|dst_rel|description
# src_rel is relative to FORK; dst_rel is relative to TARGET.
PLAN=()
PLAN+=( ".agent/skills/|.agent/skills/|harness skills (always)" )
PLAN+=( ".agent/tools/|.agent/tools/|harness tooling" )
PLAN+=( ".agent/protocols/|.agent/protocols/|protocols" )
PLAN+=( ".agent/harness/|.agent/harness/|harness hooks + budget" )
PLAN+=( ".agent/context/|.agent/context/|generic consulting context" )
PLAN+=( ".agent/workflows/|.agent/workflows/|deliverable workflows" )
PLAN+=( ".agent/AGENTS.md|.agent/AGENTS.md|root config (read first)" )
PLAN+=( "adapters/claude-code/commands/|.claude/commands/|claude-code slash commands" )

if $BCG_ENABLED; then
  PLAN+=( "adapters/bcg/agents/|.claude/agents/|BCG agent prompts" )
  PLAN+=( "adapters/bcg/commands/|.claude/commands/|BCG slash commands" )
  PLAN+=( "adapters/bcg/skills/|.agent/skills/|BCG vendored skills" )
fi

# --- show plan + confirm --------------------------------------------------

echo "fork:   $FORK"
echo "target: $TARGET"
echo "bcg_adapter: $($BCG_ENABLED && echo enabled || echo disabled)"
echo ""
echo "Sync plan:"
for entry in "${PLAN[@]}"; do
  IFS='|' read -r src dst desc <<<"$entry"
  echo "  $src  →  $dst  ($desc)"
done
echo ""
echo "Preserved (never touched):"
echo "  .agent/memory/, .claude/agent-memory/, .agent/memory/client/"
echo "  output/, .git/, target's CLAUDE.md / settings.json / config.json"
echo ""

if $DRY_RUN; then
  echo "(dry-run — no files written)"
  exit 0
fi

if ! $SKIP_CONFIRM; then
  read -r -p "Proceed with sync? [y/N] " response
  if [[ ! "$response" =~ ^[Yy]$ ]]; then
    echo "aborted."
    exit 0
  fi
fi

# --- execute --------------------------------------------------------------

WRITTEN=0
SKIPPED=0

for entry in "${PLAN[@]}"; do
  IFS='|' read -r src dst desc <<<"$entry"
  src_abs="$FORK/$src"
  dst_abs="$TARGET/$dst"

  if [[ ! -e "$src_abs" ]]; then
    echo "  ~ skipped: $src (not present in fork)"
    SKIPPED=$((SKIPPED + 1))
    continue
  fi

  # Ensure parent dir exists
  mkdir -p "$(dirname "$dst_abs")"

  if [[ -d "$src_abs" ]]; then
    # Directory: rsync if available (preserves attributes, skips identical),
    # cp -r as fallback. Either way, do NOT delete files in target that
    # don't exist in fork — that would clobber engagement-evolved state.
    mkdir -p "$dst_abs"
    if command -v rsync >/dev/null 2>&1; then
      rsync -a --no-perms --no-owner --no-group "$src_abs" "$(dirname "$dst_abs")/"
    else
      cp -R "$src_abs/." "$dst_abs/"
    fi
    echo "  + $src  ($desc)"
  else
    cp "$src_abs" "$dst_abs"
    echo "  + $src  ($desc)"
  fi
  WRITTEN=$((WRITTEN + 1))
done

echo ""
echo "done. $WRITTEN copied, $SKIPPED skipped."
echo ""
echo "Next steps in target:"
echo "  - Restart Claude Code session if running (eager-loaded files changed)"
echo "  - Run: cd $TARGET && python3 .agent/tools/skill_linter.py"
echo "  - Run: cd $TARGET && python3 .agent/tools/show.py"

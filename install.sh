#!/usr/bin/env bash
# install.sh — copy an adapter into the consuming project, then run the onboarding wizard
# Usage: ./install.sh <adapter-name> [target-dir] [--yes] [--reconfigure]
#   adapter-name:  claude-code | cursor | windsurf | opencode | openclient | hermes | standalone-python
#   target-dir:    where your project lives (default: current dir)
#   --yes          accept all wizard defaults without prompting (safe for CI)
#   --reconfigure  re-run the wizard even if PREFERENCES.md is already filled
set -euo pipefail

ADAPTER="${1:-}"
TARGET="${2:-$PWD}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "$ADAPTER" ]]; then
  echo "usage: $0 <adapter-name> [target-dir]" >&2
  echo "adapters: claude-code cursor windsurf opencode openclient hermes standalone-python" >&2
  exit 2
fi

# Collect wizard flags from any position in $@
WIZARD_FLAGS=""
for arg in "$@"; do
  case "$arg" in
    --yes|-y)        WIZARD_FLAGS="$WIZARD_FLAGS --yes" ;;
    --reconfigure)   WIZARD_FLAGS="$WIZARD_FLAGS --reconfigure" ;;
    --force)         WIZARD_FLAGS="$WIZARD_FLAGS --force" ;;
  esac
done

SRC="$HERE/adapters/$ADAPTER"
if [[ ! -d "$SRC" ]]; then
  echo "error: adapter '$ADAPTER' not found at $SRC" >&2
  exit 1
fi

echo "installing '$ADAPTER' into $TARGET"

# Copy .agent/ brain only if the target does not already have one
if [[ ! -d "$TARGET/.agent" ]]; then
  cp -R "$HERE/.agent" "$TARGET/.agent"
  echo "  + .agent/ (portable brain)"
fi

case "$ADAPTER" in
  claude-code)
    cp "$SRC/CLAUDE.md" "$TARGET/CLAUDE.md"
    mkdir -p "$TARGET/.claude"
    cp "$SRC/settings.json" "$TARGET/.claude/settings.json"
    ;;
  cursor)
    mkdir -p "$TARGET/.cursor/rules"
    cp "$SRC/.cursor/rules/agentic-stack.mdc" "$TARGET/.cursor/rules/agentic-stack.mdc"
    ;;
  windsurf)
    cp "$SRC/.windsurfrules" "$TARGET/.windsurfrules"
    ;;
  opencode)
    cp "$SRC/AGENTS.md" "$TARGET/AGENTS.md"
    cp "$SRC/opencode.json" "$TARGET/opencode.json"
    ;;
  openclient)
    cp "$SRC/config.md" "$TARGET/.openclient-system.md"
    ;;
  hermes)
    cp "$SRC/AGENTS.md" "$TARGET/AGENTS.md"
    ;;
  standalone-python)
    cp "$SRC/run.py" "$TARGET/run.py"
    ;;
  *)
    echo "error: unknown adapter '$ADAPTER'" >&2
    exit 1
    ;;
esac

echo "done."

# ── Onboarding wizard ──────────────────────────────────────────────────────
ONBOARD_PY="$HERE/onboard.py"
if [[ ! -f "$ONBOARD_PY" ]]; then
  echo "tip: customize $TARGET/$( echo '.agent/memory/personal/PREFERENCES.md' ) with your conventions."
  exit 0
fi
if ! command -v python3 &>/dev/null; then
  echo "tip: python3 not found — edit .agent/memory/personal/PREFERENCES.md manually."
  exit 0
fi

# exec replaces this shell; no return needed
exec python3 "$ONBOARD_PY" "$TARGET" $WIZARD_FLAGS

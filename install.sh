#!/usr/bin/env bash
# install.sh — copy an adapter into the consuming project, then run the onboarding wizard
# Usage: ./install.sh <adapter-name> [target-dir] [--yes] [--reconfigure]
#   adapter-name:  claude-code | cursor | windsurf | opencode | openclaw | hermes | pi | codex | standalone-python | antigravity
#   target-dir:    where your project lives (default: current dir)
#   --yes          accept all wizard defaults without prompting (safe for CI)
#   --reconfigure  re-run the wizard even if PREFERENCES.md is already filled
set -euo pipefail

ADAPTER="${1:-}"
TARGET="${2:-$PWD}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "$ADAPTER" ]]; then
  echo "usage: $0 <adapter-name> [target-dir]" >&2
  echo "adapters: claude-code cursor windsurf opencode openclaw hermes pi codex standalone-python antigravity" >&2
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
  openclaw)
    cp "$SRC/config.md" "$TARGET/.openclaw-system.md"
    ;;
  hermes)
    cp "$SRC/AGENTS.md" "$TARGET/AGENTS.md"
    ;;
  pi)
    # pi, hermes, and opencode all read AGENTS.md — don't stomp an existing one
    if [[ -f "$TARGET/AGENTS.md" ]]; then
      echo "  ~ $TARGET/AGENTS.md already exists — skipping (pi reads whatever is there)"
    else
      cp "$SRC/AGENTS.md" "$TARGET/AGENTS.md"
      echo "  + AGENTS.md"
    fi
    mkdir -p "$TARGET/.pi"
    # symlink .pi/skills -> .agent/skills so pi sees the one true skill tree.
    # ln -sfn atomically replaces an existing symlink; fall back to cp -R
    # on filesystems that don't support symlinks (e.g. Windows without dev mode).
    SKILLS_SRC="$(cd "$TARGET/.agent/skills" && pwd)"
    if ln -sfn "$SKILLS_SRC" "$TARGET/.pi/skills" 2>/dev/null; then
      echo "  + .pi/skills -> $SKILLS_SRC"
    else
      rm -rf "$TARGET/.pi/skills"
      cp -R "$SKILLS_SRC" "$TARGET/.pi/skills"
      echo "  + .pi/skills (copy; symlink not supported here)"
    fi
    ;;
  codex)
    # codex reads AGENTS.md (like pi, hermes, opencode). Many other tools
    # also write AGENTS.md (aider, amp, cline, existing codex setups), so
    # we follow the openclaw pattern: merge-or-alert, never blind overwrite,
    # never blind skip.
    if [[ -f "$TARGET/AGENTS.md" ]]; then
      if grep -q '\.agent/' "$TARGET/AGENTS.md" 2>/dev/null; then
        echo "  ~ AGENTS.md already references .agent/ — leaving alone"
      else
        echo "  ! AGENTS.md exists but does not reference .agent/; not overwriting."
        echo "    merge this block into your AGENTS.md to wire the brain:"
        echo "    ---8<---"
        sed 's/^/    /' "$SRC/AGENTS.md"
        echo "    --->8---"
      fi
    else
      cp "$SRC/AGENTS.md" "$TARGET/AGENTS.md"
      echo "  + AGENTS.md"
    fi

    # Codex scans .agents/skills/ (plural) for repo-scoped skills — per
    # OpenAI docs https://developers.openai.com/codex/skills. Keep the
    # portable brain authoritative: .agents/skills mirrors .agent/skills.
    mkdir -p "$TARGET/.agents"
    SKILLS_SRC="$(cd "$TARGET/.agent/skills" && pwd)"
    SKILLS_DEST="$TARGET/.agents/skills"
    if [[ -L "$SKILLS_DEST" ]]; then
      # Existing symlink: repoint at current .agent/skills (cheap, safe)
      ln -sfn "$SKILLS_SRC" "$SKILLS_DEST"
      echo "  + .agents/skills -> $SKILLS_SRC"
    elif [[ -d "$SKILLS_DEST" ]]; then
      # Real directory from a prior copy-fallback install: sync with
      # delete-orphans so removed/renamed skills don't linger. Use rsync
      # if available, otherwise rm+cp as a safe-but-blunt replacement.
      if command -v rsync >/dev/null 2>&1; then
        rsync -a --delete "$SKILLS_SRC/" "$SKILLS_DEST/"
        echo "  ~ synced .agent/skills → .agents/skills (rsync --delete)"
      else
        rm -rf "$SKILLS_DEST"
        cp -R "$SKILLS_SRC" "$SKILLS_DEST"
        echo "  ~ replaced .agents/skills with current .agent/skills (no rsync)"
      fi
    elif ln -sfn "$SKILLS_SRC" "$SKILLS_DEST" 2>/dev/null; then
      echo "  + .agents/skills -> $SKILLS_SRC"
    else
      cp -R "$SKILLS_SRC" "$SKILLS_DEST"
      echo "  + .agents/skills (copy; symlink not supported here)"
    fi
    ;;
  standalone-python)
    cp "$SRC/run.py" "$TARGET/run.py"
    ;;
  antigravity)
    cp "$SRC/ANTIGRAVITY.md" "$TARGET/ANTIGRAVITY.md"
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

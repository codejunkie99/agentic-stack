#!/usr/bin/env bash
# install.sh — copy an adapter into the consuming project, then run the onboarding wizard
# Usage: ./install.sh <adapter-name> [target-dir] [--yes] [--reconfigure]
#   adapter-name:  claude-code | cursor | windsurf | opencode | openclaw | hermes | pi | standalone-python | antigravity
#   target-dir:    where your project lives (default: current dir)
#   --yes          accept all wizard defaults without prompting (safe for CI)
#   --reconfigure  re-run the wizard even if PREFERENCES.md is already filled
set -euo pipefail

ADAPTER="${1:-}"
TARGET="${2:-$PWD}"
HERE="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "$ADAPTER" ]]; then
  echo "usage: $0 <adapter-name> [target-dir]" >&2
  echo "adapters: claude-code cursor windsurf opencode openclaw hermes pi standalone-python antigravity" >&2
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
    # 1. Backward-compat: drop the system-prompt include for users on older
    #    OpenClaw flows that require pasting or --system-prompt-file.
    cp "$SRC/config.md" "$TARGET/.openclaw-system.md"
    echo "  + .openclaw-system.md (system-prompt include; backward compat)"

    # 2. OpenClaw auto-injects AGENTS.md from the workspace root. Drop it
    #    safely, the same way pi does — don't stomp an existing AGENTS.md
    #    (codex/aider/amp/cline all use this filename).
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
      echo "  + AGENTS.md (auto-injected by OpenClaw from the workspace root)"
    fi

    # 3. Register a project-scoped OpenClaw agent whose workspace IS this
    #    project. Without this, OpenClaw's workspace defaults to
    #    ~/.openclaw/workspace and never sees the .agent/ brain.
    OC_ABS="$(cd "$TARGET" && pwd)"
    OC_BN_RAW="$(basename "$OC_ABS")"
    # lowercase first (OpenClaw normalizes agent ids to lowercase), then
    # sanitize to [a-z0-9._-], collapse dashes, trim
    OC_BN_SAFE="$(printf '%s' "$OC_BN_RAW" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9._-' '-' | sed 's/-\{2,\}/-/g; s/^-//; s/-$//')"
    [[ -z "$OC_BN_SAFE" ]] && OC_BN_SAFE="project"
    # 6-digit stable suffix from absolute path so cross-project collisions
    # (api, backend, app, website) resolve to distinct agent names
    OC_PATH_CKSUM="$(printf '%s' "$OC_ABS" | cksum | awk '{print $1}')"
    OC_AGENT_NAME="${OC_BN_SAFE}-$(printf '%06d' "$((OC_PATH_CKSUM % 1000000))")"

    if command -v openclaw >/dev/null 2>&1; then
      echo "  → registering OpenClaw agent '$OC_AGENT_NAME' (workspace: $OC_ABS)"
      # capture stdout+stderr and rc without tripping set -e
      OC_RC=0
      OC_OUT="$(openclaw agents add "$OC_AGENT_NAME" --workspace "$OC_ABS" 2>&1)" || OC_RC=$?
      printf '%s\n' "$OC_OUT" | sed 's/^/    /'
      if [[ $OC_RC -eq 0 ]]; then
        echo "  ✓ registered. run from anywhere: openclaw --agent $OC_AGENT_NAME"
      elif printf '%s' "$OC_OUT" | grep -qi "already exists"; then
        echo "  ✓ already registered (idempotent re-run). run: openclaw --agent $OC_AGENT_NAME"
      else
        echo "  ! 'openclaw agents add' failed (details above)."
        echo "    if your OpenClaw fork does not support 'agents add --workspace',"
        echo "    fall back to the system-prompt include we wrote:"
        echo "      openclaw --system-prompt-file \"$OC_ABS/.openclaw-system.md\""
        echo "    otherwise retry: openclaw agents add \"$OC_AGENT_NAME\" --workspace \"$OC_ABS\""
      fi
    else
      echo "  ! 'openclaw' CLI not found on PATH. after installing OpenClaw, try:"
      echo "      openclaw agents add \"$OC_AGENT_NAME\" --workspace \"$OC_ABS\""
      echo "      openclaw --agent $OC_AGENT_NAME"
      echo "    or, on forks without 'agents add', use the system-prompt include:"
      echo "      openclaw --system-prompt-file \"$OC_ABS/.openclaw-system.md\""
    fi
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

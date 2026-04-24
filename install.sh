#!/usr/bin/env bash
# install.sh — agentic-stack installer.
#
# Usage:
#   ./install.sh <adapter-name> [target-dir] [--yes|--reconfigure|--force]
#                                                # install one adapter
#   ./install.sh add <adapter-name> [target-dir] # add an adapter to an
#                                                # already-set-up project
#   ./install.sh remove <adapter-name> [target-dir] [--yes]
#                                                # remove an installed adapter
#   ./install.sh doctor [target-dir]             # read-only audit
#   ./install.sh status [target-dir]             # one-screen view
#   ./install.sh                                 # bare: list available adapters
#                                                # (or, if install.json exists,
#                                                # show what's installable)
#
# adapter-name: claude-code | cursor | windsurf | opencode | openclaw |
#               hermes | pi | codex | standalone-python | antigravity
#
# All real logic lives in harness_manager/ (Python). This script is a
# thin dispatcher so install.sh and install.ps1 share one backend.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
export AGENTIC_STACK_ROOT="$HERE"
# Prepend HERE so `python3 -m harness_manager.cli` finds the module
# regardless of which directory the user invoked install.sh from.
export PYTHONPATH="$HERE${PYTHONPATH:+:$PYTHONPATH}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but not found on PATH." >&2
  echo "       agentic-stack uses python3 for the installer + brain tooling." >&2
  exit 1
fi

# Hand off to the Python dispatcher. It owns argv parsing, verb routing,
# adapter validation, and onboarding flow.
exec python3 -m harness_manager.cli "$@"

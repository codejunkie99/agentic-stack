#!/usr/bin/env bash
# Ralph — autonomous agent loop (after snarktank/ralph).
# Runs a fresh agent per iteration until every PRD story passes or the
# iteration budget is spent. Each iteration starts with clean context;
# memory between iterations is git history, prd.json, and progress.txt.
#
# Usage: ./ralph.sh [--tool claude|amp] [max_iterations]
#   defaults: --tool claude, 10 iterations
#
# Permissions: with the claude tool the loop runs headless with
# --permission-mode acceptEdits by default, so shell-level gates still apply.
# To change that (including fully autonomous runs), set RALPH_CLAUDE_FLAGS
# yourself before launching — read ralph/README.md first.
#
# Managed by project-template/sync.py — edit the copy in
# ~/dev-repo/project-template/ralph/ and push, or the next sync reverts this.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL="claude"
MAX_ITERATIONS=10

while [[ $# -gt 0 ]]; do
  case "$1" in
    --tool)   TOOL="$2"; shift 2 ;;
    --tool=*) TOOL="${1#*=}"; shift ;;
    -h|--help) grep '^#' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *)
      if [[ "$1" =~ ^[0-9]+$ ]]; then MAX_ITERATIONS="$1"; else
        echo "unknown argument: $1" >&2; exit 2
      fi
      shift ;;
  esac
done

if [[ "$TOOL" != "claude" && "$TOOL" != "amp" ]]; then
  echo "error: --tool must be claude or amp" >&2; exit 2
fi
command -v "$TOOL" >/dev/null || { echo "error: $TOOL CLI not on PATH" >&2; exit 2; }

CLAUDE_FLAGS="${RALPH_CLAUDE_FLAGS:---permission-mode acceptEdits}"

PRD="$SCRIPT_DIR/prd.json"
PROGRESS="$SCRIPT_DIR/progress.txt"
LAST_BRANCH_FILE="$SCRIPT_DIR/.last-branch"
LOG_DIR="$SCRIPT_DIR/logs"

if [[ ! -f "$PRD" ]]; then
  echo "error: $PRD not found. Copy prd.json.example to prd.json and fill in" >&2
  echo "the branchName and user stories for this run." >&2
  exit 2
fi

REPO_ROOT="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel 2>/dev/null)" || {
  echo "error: not inside a git repository — Ralph commits its work, so run" >&2
  echo "git init (and an initial commit) first." >&2
  exit 2
}

python3 - "$PRD" <<'PY' || exit 2
import json, sys
try:
    with open(sys.argv[1], encoding="utf-8") as handle:
        prd = json.load(handle)
except ValueError as err:
    sys.exit(f"error: prd.json is not valid JSON: {err}")
if not prd.get("branchName"):
    sys.exit("error: prd.json has no branchName")
stories = prd.get("stories")
if not isinstance(stories, list) or not stories:
    sys.exit("error: prd.json has no stories")
for story in stories:
    if not story.get("id") or "passes" not in story:
        sys.exit(f"error: every story needs an id and a passes flag: {story}")
PY
BRANCH="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["branchName"])' "$PRD")"

if [[ -n "$(git -C "$REPO_ROOT" status --porcelain)" && "${RALPH_ALLOW_DIRTY:-0}" != "1" ]]; then
  echo "error: the working tree has uncommitted changes. Ralph switches" >&2
  echo "branches and commits one story at a time, so start from a clean tree" >&2
  echo "— commit or stash first, or set RALPH_ALLOW_DIRTY=1 to proceed anyway." >&2
  exit 2
fi

# A new branchName means a new run: archive the previous run's state.
if [[ -f "$LAST_BRANCH_FILE" ]]; then
  LAST_BRANCH="$(cat "$LAST_BRANCH_FILE")"
  if [[ "$LAST_BRANCH" != "$BRANCH" && -f "$PROGRESS" ]]; then
    STAMP="$(date +%Y%m%d-%H%M%S)"
    DEST="$SCRIPT_DIR/archive/$STAMP-${LAST_BRANCH//\//-}"
    mkdir -p "$DEST"
    mv "$PROGRESS" "$DEST/progress.txt"
    cp "$PRD" "$DEST/prd.json"
    echo "archived previous run to $DEST"
  fi
fi
printf '%s\n' "$BRANCH" > "$LAST_BRANCH_FILE"

if git -C "$REPO_ROOT" rev-parse --verify --quiet "$BRANCH" >/dev/null; then
  git -C "$REPO_ROOT" checkout "$BRANCH"
else
  git -C "$REPO_ROOT" checkout -b "$BRANCH"
fi

if [[ ! -f "$PROGRESS" ]]; then
  {
    echo "## Codebase Patterns"
    echo
    echo "(reusable discoveries live here — keep story-specific detail in the entries below)"
    echo
    echo "---"
  } > "$PROGRESS"
fi

mkdir -p "$LOG_DIR"

for i in $(seq 1 "$MAX_ITERATIONS"); do
  echo ""
  echo "=== Ralph iteration $i/$MAX_ITERATIONS ($TOOL, branch $BRANCH) ==="
  LOG_FILE="$LOG_DIR/$(date +%Y%m%d-%H%M%S)-iter-$i.log"

  set +e
  if [[ "$TOOL" == "claude" ]]; then
    # shellcheck disable=SC2086
    OUTPUT="$(cd "$REPO_ROOT" && claude --print $CLAUDE_FLAGS \
      < "$SCRIPT_DIR/PROMPT.md" 2>&1)"
  else
    OUTPUT="$(cd "$REPO_ROOT" && amp --dangerously-allow-all \
      < "$SCRIPT_DIR/PROMPT.md" 2>&1)"
  fi
  STATUS=$?
  set -e

  printf '%s\n' "$OUTPUT" > "$LOG_FILE"
  echo "exit $STATUS — log: $LOG_FILE"
  tail -n 5 "$LOG_FILE" | sed 's/^/  | /'

  if printf '%s' "$OUTPUT" | grep -q "<promise>COMPLETE</promise>"; then
    echo ""
    echo "Ralph reports every story passes. Done after $i iteration(s)."
    exit 0
  fi
  sleep 2
done

echo ""
echo "Iteration budget spent ($MAX_ITERATIONS) with stories still open."
echo "Inspect $PROGRESS and $LOG_DIR, then run again to continue."
exit 1

#!/usr/bin/env sh
# Bootstrap for: agentic-stack transfer import
set -eu

TARGET=""
PAYLOAD=""
SHA256=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --target)
      TARGET="${2:-}"
      shift 2
      ;;
    --payload)
      PAYLOAD="${2:-}"
      shift 2
      ;;
    --sha256)
      SHA256="${2:-}"
      shift 2
      ;;
    *)
      echo "error: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

if [ -z "$TARGET" ] || [ -z "$PAYLOAD" ] || [ -z "$SHA256" ]; then
  echo "usage: import-transfer.sh --target <name> --payload <payload> --sha256 <digest>" >&2
  exit 2
fi

if [ -n "${AGENTIC_STACK_ROOT:-}" ] && [ -d "$AGENTIC_STACK_ROOT/harness_manager" ]; then
  ROOT="$AGENTIC_STACK_ROOT"
elif [ -d "./harness_manager" ] && [ -d "./adapters" ]; then
  ROOT="$PWD"
else
  TMPDIR="${TMPDIR:-/tmp}/agentic-stack-transfer.$$"
  mkdir -p "$TMPDIR"
  curl -fsSL "https://github.com/codejunkie99/agentic-stack/archive/refs/heads/master.tar.gz" \
    | tar -xz -C "$TMPDIR" --strip-components 1
  ROOT="$TMPDIR"
fi

export AGENTIC_STACK_ROOT="$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

python3 -m harness_manager.cli transfer import \
  --target "$TARGET" \
  --payload "$PAYLOAD" \
  --sha256 "$SHA256"

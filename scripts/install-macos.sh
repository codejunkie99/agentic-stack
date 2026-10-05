#!/usr/bin/env bash
# Install an explicitly selected, verified local preview bundle.
set -euo pipefail
if [ "$#" -ne 1 ] || [ ! -d "$1/Contents" ]; then
  echo 'Usage: bash scripts/install-macos.sh "/path/to/Agentic Stack.app"' >&2
  exit 2
fi
SOURCE_APP="$1"
INSTALL_DIR="${AGENTIC_STACK_INSTALL_DIR:-$HOME/Applications}"
TARGET_APP="$INSTALL_DIR/Agentic Stack.app"
if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo 'This preview requires macOS on Apple Silicon.' >&2
  exit 1
fi
codesign --verify --deep --strict "$SOURCE_APP"
BUNDLE_ID="$(/usr/libexec/PlistBuddy -c 'Print :CFBundleIdentifier' "$SOURCE_APP/Contents/Info.plist")"
if [ "$BUNDLE_ID" != 'dev.agentic-stack.workspaces' ]; then
  echo 'Unexpected application identifier.' >&2
  exit 1
fi
mkdir -p "$INSTALL_DIR"
STAGED_APP="$INSTALL_DIR/.Agentic Stack.installing.$$.app"
ditto --norsrc --noextattr "$SOURCE_APP" "$STAGED_APP"
codesign --verify --deep --strict "$STAGED_APP"
if [ -e "$TARGET_APP" ]; then
  mv "$TARGET_APP" "$INSTALL_DIR/Agentic Stack.previous-$(date +%s).app"
fi
mv "$STAGED_APP" "$TARGET_APP"
echo "Installed $TARGET_APP"

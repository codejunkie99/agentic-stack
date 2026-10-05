#!/usr/bin/env bash
# Build a native bundle. --python-root embeds a relocatable CPython runtime.
set -euo pipefail
STACK_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUTPUT_DIR="$STACK_ROOT/apps/macos/dist"
PYTHON_ROOT=""
CONFIGURATION="release"
APP_VERSION="$(PYTHONPATH="$STACK_ROOT" python3 -c 'from harness_manager import __version__; print(__version__)')"
APP_BUILD_VERSION="${AGENTIC_BUILD_VERSION:-$(git -C "$STACK_ROOT" rev-list --count HEAD 2>/dev/null || echo 1)}"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --python-root) PYTHON_ROOT="$2"; shift 2 ;;
    --configuration) CONFIGURATION="$2"; shift 2 ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
# Build in a disposable directory and strip compiler paths from the release binary.
STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/agentic-workspaces.XXXXXX")"
trap 'rm -rf "$STAGING_DIR"' EXIT
SWIFT_PATH_FLAGS=(-Xswiftc -gnone -Xswiftc -file-prefix-map -Xswiftc "$STACK_ROOT=/agentic-stack" -Xswiftc -file-prefix-map -Xswiftc "$STAGING_DIR=/build")
swift build --package-path "$STACK_ROOT/apps/macos" --scratch-path "$STAGING_DIR/swift-build" -c "$CONFIGURATION" -j 4 "${SWIFT_PATH_FLAGS[@]}"
BIN_DIR="$(swift build --package-path "$STACK_ROOT/apps/macos" --scratch-path "$STAGING_DIR/swift-build" -c "$CONFIGURATION" "${SWIFT_PATH_FLAGS[@]}" --show-bin-path)"
mkdir -p "$OUTPUT_DIR"
# Sign outside Documents/iCloud: File Provider can reattach FinderInfo while signing.
APP_PATH="$STAGING_DIR/Agentic Stack.app"
mkdir -p "$APP_PATH/Contents/MacOS" "$APP_PATH/Contents/Frameworks" "$APP_PATH/Contents/Resources"
cp "$BIN_DIR/AgenticWorkspaces" "$APP_PATH/Contents/MacOS/AgenticWorkspaces"
test -d "$BIN_DIR/Sparkle.framework"
cp -R "$BIN_DIR/Sparkle.framework" "$APP_PATH/Contents/Frameworks/"
cp -R "$BIN_DIR/SwiftTerm_SwiftTerm.bundle" "$APP_PATH/Contents/Resources/"
cp "$STACK_ROOT/apps/macos/THIRD-PARTY-NOTICES.md" "$APP_PATH/Contents/Resources/"
python3 "$STACK_ROOT/scripts/package_payload.py" "$APP_PATH/Contents/Resources/agentic-stack"
swift "$STACK_ROOT/scripts/macos-app-icon.swift" "$STAGING_DIR/AppIcon.iconset"
iconutil -c icns "$STAGING_DIR/AppIcon.iconset" -o "$APP_PATH/Contents/Resources/AppIcon.icns"
cp "$STACK_ROOT/deploy/agentic-stack/README.md" "$APP_PATH/Contents/Resources/Hosting.md"
python3 "$STACK_ROOT/scripts/build-server-package.py" "$APP_PATH/Contents/Resources/Agentic Stack-server.zip"
cp "$APP_PATH/Contents/Resources/Agentic Stack-server.zip" "$OUTPUT_DIR/Agentic Stack-server.zip"
if [ -n "$PYTHON_ROOT" ]; then
  test -x "$PYTHON_ROOT/bin/python3"
  cp -R "$PYTHON_ROOT" "$APP_PATH/Contents/Resources/python"
fi
cat > "$APP_PATH/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>AgenticWorkspaces</string>
<key>CFBundleIdentifier</key><string>dev.agentic-stack.workspaces</string>
<key>CFBundleName</key><string>Agentic Stack</string>
<key>CFBundleDisplayName</key><string>Agentic Stack</string>
<key>CFBundleIconFile</key><string>AppIcon</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleShortVersionString</key><string>APP_VERSION_PLACEHOLDER</string>
<key>CFBundleVersion</key><string>APP_BUILD_VERSION_PLACEHOLDER</string>
<key>LSMinimumSystemVersion</key><string>14.0</string>
<key>NSHighResolutionCapable</key><true/>
<key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
<key>SUPublicEDKey</key><string>SB2+Dz95NlPLPydCpXvHiuJgwxHbaOKzncCngn3cxtw=</string>
<key>SUScheduledCheckInterval</key><integer>86400</integer>
</dict></plist>
PLIST
/usr/libexec/PlistBuddy -c "Set :CFBundleShortVersionString $APP_VERSION" "$APP_PATH/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleVersion $APP_BUILD_VERSION" "$APP_PATH/Contents/Info.plist"
# Finder metadata copied from a File Provider directory is not a signable resource.
xattr -dr com.apple.FinderInfo "$APP_PATH" 2>/dev/null || true
xattr -dr com.apple.ResourceFork "$APP_PATH" 2>/dev/null || true
python3 "$STACK_ROOT/scripts/sign-macos-app.py" "$APP_PATH"
# Archive before File Provider can attach Finder metadata to the app directory.
ditto -c -k --keepParent --norsrc --noextattr "$APP_PATH" "$OUTPUT_DIR/Agentic Stack-macOS.zip"
python3 "$STACK_ROOT/scripts/build-macos-dmg.py" "$APP_PATH" "$OUTPUT_DIR/Agentic-Stack-macOS-arm64.dmg"
TARGET="$OUTPUT_DIR/Agentic Stack.app"
if [ -e "$TARGET" ]; then
  mv "$TARGET" "$OUTPUT_DIR/Agentic Stack.previous-$(date +%s).app"
fi
mv "$APP_PATH" "$TARGET"
echo "$TARGET"

#!/usr/bin/env python3
"""Create and verify a drag-to-Applications DMG from Agentic Stack.app."""

import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile


def build(app: Path, destination: Path) -> Path:
    app = app.resolve()
    destination = destination.resolve()
    info_path = app / "Contents" / "Info.plist"
    if not info_path.is_file():
        raise SystemExit(f"Not an app bundle: {app}")
    info = plistlib.loads(info_path.read_bytes())
    if info.get("CFBundleIdentifier") != "dev.agentic-stack.workspaces":
        raise SystemExit(f"Unexpected bundle identifier: {info.get('CFBundleIdentifier')}")

    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.unlink(missing_ok=True)

    with tempfile.TemporaryDirectory(prefix="agentic-stack-dmg-") as temporary:
        stage = Path(temporary) / "Agentic Stack"
        stage.mkdir()
        # Sparkle.framework uses the standard versioned framework symlink layout.
        # Preserve it so the bundle stays valid after being copied into the DMG.
        shutil.copytree(
            app,
            stage / app.name,
            copy_function=shutil.copy2,
            symlinks=True,
        )
        os.symlink("/Applications", stage / "Applications")
        (stage / "Install.txt").write_text(
            "Agentic Stack for macOS 14+ (Apple Silicon)\n\n"
            "1. Drag Agentic Stack.app to Applications.\n"
            "2. Open it from Applications.\n"
            "3. If macOS blocks this preview, open System Settings > Privacy & "
            "Security and choose Open Anyway.\n\n"
            "This unified preview has automatic updates disabled.\n"
            "Download only from the official Agentic Stack GitHub releases.\n",
            encoding="utf-8",
        )
        subprocess.run(
            [
                "hdiutil",
                "create",
                "-volname",
                "Agentic Stack",
                "-srcfolder",
                str(stage),
                "-format",
                "UDZO",
                "-ov",
                str(destination),
            ],
            check=True,
        )
    subprocess.run(["hdiutil", "verify", str(destination)], check=True)
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(build(args.app, args.output))

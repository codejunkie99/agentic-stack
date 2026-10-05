"""Native workspace launcher, exposed by the existing agentic-stack CLI."""
import argparse
import subprocess
import sys
from pathlib import Path


def main(argv=None):
    parser = argparse.ArgumentParser(prog="./install.sh workspaces", description="Build or open the native macOS workspace app.")
    parser.add_argument("--build", action="store_true", help="Build the release app with the installed Swift toolchain")
    parser.add_argument("--python-root", type=Path, help="Standalone Python distribution to bundle for portable installation")
    parser.add_argument("--output", type=Path, help="Directory for the application bundle")
    parser.add_argument("--no-open", action="store_true", help="Build without opening the app")
    args = parser.parse_args(argv)
    if sys.platform != "darwin":
        parser.error("The native app requires macOS. Portable transfer bundles remain available on every platform.")
    root = Path(__file__).resolve().parents[2]
    output = (args.output or root / "apps/macos/dist").resolve()
    app = output / "Agentic Stack.app"
    if args.build:
        command = ["bash", str(root / "scripts/build-macos-app.sh"), "--output", str(output)]
        if args.python_root:
            command += ["--python-root", str(args.python_root.resolve())]
        result = subprocess.run(command, cwd=root)
        if result.returncode:
            return result.returncode
    if not app.exists():
        parser.error("No app found. Run ./install.sh workspaces --build first.")
    if not args.no_open:
        return subprocess.run(["open", str(app)]).returncode
    print(app)
    return 0

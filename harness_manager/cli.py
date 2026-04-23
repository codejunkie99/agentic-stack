"""Argparse dispatcher. install.sh and install.ps1 invoke this.

Verbs (subcommands): add, remove, doctor, status.
Anything else in first position → treated as an adapter name (existing
`./install.sh <adapter>` UX preserved).
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

from . import doctor as doctor_mod
from . import install as install_mod
from . import remove as remove_mod
from . import schema as schema_mod
from . import state as state_mod
from . import status as status_mod
from . import __version__


VERBS = {"add", "remove", "doctor", "status", "manage"}


def _stack_root() -> Path:
    """Path to the agentic-stack source root.

    Honors AGENTIC_STACK_ROOT env override (CI / non-standard installs).
    Otherwise: walk up from this file (.../harness_manager/cli.py) two
    levels.
    """
    env = os.environ.get("AGENTIC_STACK_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parent.parent


def _adapter_dir(adapter_name: str) -> Path:
    return _stack_root() / "adapters" / adapter_name


def _adapter_manifest(adapter_name: str) -> dict:
    """Load and validate adapter.json for adapter_name."""
    p = _adapter_dir(adapter_name) / "adapter.json"
    if not p.is_file():
        raise SystemExit(
            f"error: adapter '{adapter_name}' has no adapter.json at {p}\n"
            f"available adapters: {_list_adapters()}"
        )
    return schema_mod.validate(p)


def _list_adapters() -> str:
    root = _stack_root() / "adapters"
    if not root.is_dir():
        return "(adapters dir missing)"
    names = sorted(p.name for p in root.iterdir() if p.is_dir())
    return ", ".join(names)


def _maybe_run_onboard(target: Path, wizard_flags: list[str]) -> int:
    """Run onboard.py against target after install (mirrors install.sh:249).

    Returns the wizard's exit code so cmd_install can propagate failures
    (Ctrl-C in the wizard, exception in onboard.py, etc.). Pre-v0.9.0
    install.sh did `exec python3 onboard.py` so failures naturally
    flowed up — this preserves that contract for CI / scripted users.

    Returns 0 if onboard.py or python3 is missing (matches bash tip-and-skip).
    """
    onboard = _stack_root() / "onboard.py"
    if not onboard.is_file():
        print(
            f"tip: customize {target}/.agent/memory/personal/PREFERENCES.md "
            "with your conventions."
        )
        return 0
    cmd = [sys.executable, str(onboard), str(target), *wizard_flags]
    try:
        result = subprocess.run(cmd, check=False)
        return result.returncode
    except FileNotFoundError:
        print(
            "tip: python3 not found — edit "
            ".agent/memory/personal/PREFERENCES.md manually."
        )
        return 0
    except KeyboardInterrupt:
        # User Ctrl-C'd the wizard. Treat as a real failure so callers
        # know the install is incomplete.
        print()
        print("onboarding cancelled by user; install state may be partial.")
        return 130


# ---- subcommands -----------------------------------------------------

def cmd_install(adapter_name: str, target: Path, wizard_flags: list[str]) -> int:
    """Install one adapter into target. Existing `./install.sh <adapter>` UX."""
    manifest = _adapter_manifest(adapter_name)
    install_mod.install(
        manifest=manifest,
        target_root=target,
        adapter_dir=_adapter_dir(adapter_name),
        stack_root=_stack_root(),
    )
    # Propagate the onboarding wizard's exit code: Ctrl-C, exception, or
    # explicit failure inside onboard.py should fail the install command,
    # matching the pre-v0.9.0 `exec python3 onboard.py` semantics.
    return _maybe_run_onboard(target, wizard_flags)


def cmd_add(adapter_name: str, target: Path) -> int:
    """Append one adapter to an existing project (no onboard wizard re-run).

    Refuses on pre-v0.9 projects (no install.json yet). Without this check,
    `add` would create a fresh install.json with ONLY the new adapter, and
    every adapter previously installed via the old install.sh would
    disappear from status/doctor/remove tracking even though their files
    are still on disk.
    """
    if state_mod.load(target) is None:
        # Pre-v0.9 project. Detect adapters and refuse with a clear path forward.
        from . import doctor as doctor_mod
        signals_present = []
        for name, signals in doctor_mod.DETECT_SIGNALS.items():
            if any((target / f).exists() for f, _ in signals):
                signals_present.append(name)
        if signals_present:
            print(
                f"error: {target}/.agent/install.json not present, but these adapters\n"
                f"appear to already be installed: {sorted(signals_present)}\n"
                f"\n"
                f"run this first to register them safely:\n"
                f"  ./install.sh doctor\n"
                f"\n"
                f"`add` would otherwise create a fresh install.json with only\n"
                f"the new adapter, leaving the existing ones invisible to\n"
                f"status/doctor/remove.",
                file=sys.stderr,
            )
            return 2
        # No prior install detected; safe to proceed (`add` on a clean repo).
    manifest = _adapter_manifest(adapter_name)
    install_mod.install(
        manifest=manifest,
        target_root=target,
        adapter_dir=_adapter_dir(adapter_name),
        stack_root=_stack_root(),
    )
    return 0


def cmd_remove(adapter_name: str, target: Path, yes: bool) -> int:
    return remove_mod.remove(target_root=target, adapter_name=adapter_name, yes=yes)


def cmd_doctor(target: Path) -> int:
    return doctor_mod.audit(target_root=target)


def cmd_status(target: Path) -> int:
    return status_mod.show(target_root=target)


def cmd_manage(target: Path) -> int:
    """Open the persistent TUI menu for ongoing adapter management."""
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(
            "error: manage is an interactive TUI; this shell is not a TTY.\n"
            "use the verb-style subcommands instead:\n"
            "  ./install.sh add <adapter>\n"
            "  ./install.sh remove <adapter>\n"
            "  ./install.sh doctor\n"
            "  ./install.sh status",
            file=sys.stderr,
        )
        return 2
    from . import manage_tui
    return manage_tui.run(target_root=target, stack_root=_stack_root())


def cmd_bare(target: Path) -> int:
    """`./install.sh` with no args.

    If install.json present: dispatch to add mode (offer adapters not yet
    installed). If not: print usage and exit non-zero.
    """
    doc = state_mod.load(target)
    if doc is None:
        print("usage: ./install.sh <adapter-name> [target-dir]")
        print(f"adapters: {_list_adapters()}")
        print()
        print("on a project that's already installed, run:")
        print("  ./install.sh doctor      # audit")
        print("  ./install.sh status      # quick read-only view")
        print("  ./install.sh add <name>  # install another adapter")
        print("  ./install.sh remove <name>  # remove an adapter (with confirm)")
        print("  ./install.sh manage      # interactive TUI for everything")
        return 2

    installed = set(doc.get("adapters", {}).keys())
    available = set()
    root = _stack_root() / "adapters"
    if root.is_dir():
        for p in root.iterdir():
            if p.is_dir() and (p / "adapter.json").is_file():
                available.add(p.name)
    not_installed = sorted(available - installed)
    if not not_installed:
        print(f"all available adapters already installed: {sorted(installed)}")
        print("run `./install.sh status` for a summary.")
        return 0

    print(f"already installed: {sorted(installed)}")
    print(f"available to add:  {not_installed}")
    print()
    print(f"to add one: ./install.sh add <name>")
    return 0


# ---- main ------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Extract --yes / --reconfigure / --force into wizard_flags; these
    # pass through to onboard.py for back-compat with the bash flow.
    wizard_flags: list[str] = []
    rest: list[str] = []
    i = 0
    yes = False
    while i < len(argv):
        a = argv[i]
        if a in ("--yes", "-y"):
            wizard_flags.append("--yes")
            yes = True
        elif a == "--reconfigure":
            wizard_flags.append("--reconfigure")
        elif a == "--force":
            wizard_flags.append("--force")
        else:
            rest.append(a)
        i += 1

    if not rest:
        target = Path.cwd()
        return cmd_bare(target)

    first = rest[0]

    if first in VERBS:
        verb = first
        if verb == "add":
            if len(rest) < 2:
                print("usage: ./install.sh add <adapter-name> [target-dir]", file=sys.stderr)
                return 2
            adapter = rest[1]
            target = Path(rest[2]) if len(rest) >= 3 else Path.cwd()
            return cmd_add(adapter, target)
        if verb == "remove":
            if len(rest) < 2:
                print("usage: ./install.sh remove <adapter-name> [target-dir] [--yes]", file=sys.stderr)
                return 2
            adapter = rest[1]
            target = Path(rest[2]) if len(rest) >= 3 else Path.cwd()
            return cmd_remove(adapter, target, yes=yes)
        if verb == "doctor":
            target = Path(rest[1]) if len(rest) >= 2 else Path.cwd()
            return cmd_doctor(target)
        if verb == "status":
            target = Path(rest[1]) if len(rest) >= 2 else Path.cwd()
            return cmd_status(target)
        if verb == "manage":
            target = Path(rest[1]) if len(rest) >= 2 else Path.cwd()
            return cmd_manage(target)

    # Treat as adapter name (existing UX)
    adapter = first
    target = Path(rest[1]) if len(rest) >= 2 else Path.cwd()
    return cmd_install(adapter, target, wizard_flags)


if __name__ == "__main__":
    sys.exit(main())

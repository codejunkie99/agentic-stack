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
    """Install one adapter into target. Existing `./install.sh <adapter>` UX.

    Refuses on pre-v0.9 projects (no install.json) when STRONG adapter
    signals are already on disk — without this guard, the install would
    create a fresh install.json containing only the newly-installed
    adapter, orphaning every pre-v0.9 install (they'd vanish from
    status/doctor/remove even though their files remain on disk). The
    same gate cmd_add uses. Weak signals (plain CLAUDE.md, AGENTS.md,
    run.py) are ignored to avoid false-refusing clean repos that happen
    to contain one of those common files.
    """
    detected = state_mod.legacy_unregistered_adapters(target)
    if detected:
        # Pre-v0.9 project: brain is present AND adapter signals exist.
        # Refuse so doctor can synthesize install.json first and
        # preserve the prior install(s). Brain-without-signals is NOT
        # gated — cloning agentic-stack itself, or copying the brain
        # template before first install, shouldn't deadlock the user.
        print(
            f"error: {target}/.agent/ exists but install.json does not.\n"
            f"this looks like a pre-v0.9 install. detected adapters: {detected}\n"
            f"\n"
            f"run this first to register them safely:\n"
            f"  ./install.sh doctor\n"
            f"\n"
            f"proceeding would otherwise create a fresh install.json with only\n"
            f"the new adapter, leaving the existing ones invisible to\n"
            f"status/doctor/remove.",
            file=sys.stderr,
        )
        return 2
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
    rc = _maybe_run_onboard(target, wizard_flags)
    if rc != 0:
        return rc
    # Post-install: offer the manage TUI so users who installed one
    # adapter can immediately add others without re-running install.sh.
    # Skip if --yes (scripted) or non-TTY (CI safety).
    if "--yes" not in wizard_flags and sys.stdin.isatty() and sys.stdout.isatty():
        _maybe_offer_manage(target)
    return 0


def _maybe_offer_manage(target: Path) -> None:
    """Offer the manage TUI after a single-adapter install.

    Only invoked from cmd_install when the shell is interactive and the
    user didn't pass --yes. If every available adapter is already
    installed, skip the prompt — nothing useful to do in the TUI. Default
    is no, so just hitting enter dismisses without entering the TUI.
    """
    doc = state_mod.load(target) or {}
    installed = set(doc.get("adapters") or {})
    available = set()
    root = _stack_root() / "adapters"
    if root.is_dir():
        for p in root.iterdir():
            if p.is_dir() and (p / "adapter.json").is_file():
                available.add(p.name)
    not_installed = sorted(available - installed)
    if not not_installed:
        return
    sys.path.insert(0, str(_stack_root()))
    import onboard_widgets as widgets  # noqa: E402
    print()
    try:
        choice = widgets.ask_confirm(
            f"install or manage other adapters? ({len(not_installed)} available)",
            default=False,
        )
    except KeyboardInterrupt:
        # Install already succeeded; treat Ctrl-C at the offer as "no."
        print()
        return
    if choice:
        from . import manage_tui
        manage_tui.run(target_root=target, stack_root=_stack_root())


def cmd_add(adapter_name: str, target: Path) -> int:
    """Append one adapter to an existing project (no onboard wizard re-run).

    Refuses on pre-v0.9 projects (no install.json yet). Without this check,
    `add` would create a fresh install.json with ONLY the new adapter, and
    every adapter previously installed via the old install.sh would
    disappear from status/doctor/remove tracking even though their files
    are still on disk.
    """
    detected = state_mod.legacy_unregistered_adapters(target)
    if detected:
        print(
            f"error: {target}/.agent/ exists but install.json does not.\n"
            f"this looks like a pre-v0.9 install. detected adapters: {detected}\n"
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


def cmd_bare(target: Path, wizard_flags: list[str]) -> int:
    """`./install.sh` with no args.

    Behavior:
      - install.json present  → list what's still installable
      - no install.json + TTY → enter the onboarding wizard (multi-select
        harness step, then per-adapter install, then PREFERENCES.md flow)
      - no install.json + non-TTY → print usage and exit 2 (CI safety)
    """
    doc = state_mod.load(target)
    if doc is not None:
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
        print(f"or interactively: ./install.sh manage")
        return 0

    # No install.json. Pre-v0.9 migration gate: if this is a legacy
    # install (brain AND adapter signals present) we must register
    # via doctor first. Brain-only (no signals) falls through to the
    # wizard — someone dropped the template here but never installed
    # anything, so there's nothing to migrate.
    detected = state_mod.legacy_unregistered_adapters(target)
    if detected:
        print(
            f"pre-v0.9 install detected at {target}.",
            file=sys.stderr,
        )
        print(
            f".agent/ exists but install.json does not. detected adapters: "
            f"{detected}",
            file=sys.stderr,
        )
        print(file=sys.stderr)
        print(
            "run this first to register them safely:", file=sys.stderr,
        )
        print("  ./install.sh doctor", file=sys.stderr)
        print(file=sys.stderr)
        print(
            "then re-run ./install.sh to add more adapters or use "
            "./install.sh manage.",
            file=sys.stderr,
        )
        return 2

    # No install.json and not a legacy install — fresh project. Two paths.
    if sys.stdin.isatty() and sys.stdout.isatty():
        return _run_install_wizard(target, wizard_flags)

    # Non-TTY (CI, scripted) → print usage, exit 2.
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


def _run_install_wizard(target: Path, wizard_flags: list[str]) -> int:
    """Onboarding wizard: detect → multi-select → install each → PREFERENCES.md.

    The original "give people options like Claude Code and all of that"
    flow. Reuses the manage TUI's multi-select widget for harness pick.
    Auto-checks adapters whose detection signals are present in `target`,
    so a user who already has CLAUDE.md / .cursor/ in their repo gets
    those pre-selected.
    """
    # Lazy imports — wizard path only.
    sys.path.insert(0, str(_stack_root()))
    import onboard_widgets as widgets  # noqa: E402
    from onboard_ui import print_banner, intro, R, MUTED, GREEN  # noqa: E402
    from . import doctor as doctor_mod

    print_banner()
    intro("agentic-stack onboarding")

    # Discover all available adapters.
    available = sorted(n for n, _ in schema_mod.discover_all(_stack_root()))
    if not available:
        print(f"  {MUTED}no adapters available — repo seems empty{R}")
        return 1

    # Auto-detect what's already on disk in the target. Only STRONG
    # signals count for default-check — a weak signal like a generic
    # CLAUDE.md, AGENTS.md, or run.py can belong to any project; pre-
    # checking one and hitting Enter at the multiselect would silently
    # overwrite the user's file (claude-code's CLAUDE.md is
    # merge_policy: overwrite). Weak-only matches still surface to the
    # user via the adapter list but stay unchecked until toggled.
    detected = set()
    for name in available:
        signals = doctor_mod.DETECT_SIGNALS.get(name, [])
        if any(
            (target / f).exists()
            for f, strength in signals
            if strength == "strong"
        ):
            detected.add(name)
    defaults = [available.index(n) for n in available if n in detected]

    if detected:
        print(f"  {GREEN}detected{R}: {sorted(detected)} — pre-checked below.")
        print()

    chosen = widgets.ask_multiselect(
        "which harnesses are you using?",
        available,
        defaults=defaults,
    )
    if not chosen:
        print(f"  {MUTED}no adapters selected; brain not installed.{R}")
        print(f"  {MUTED}you can run `./install.sh <adapter>` later.{R}")
        return 0

    # Install each selected adapter via the manifest backend.
    for name in chosen:
        manifest_path = _stack_root() / "adapters" / name / "adapter.json"
        manifest = schema_mod.validate(manifest_path)
        install_mod.install(
            manifest=manifest,
            target_root=target,
            adapter_dir=_stack_root() / "adapters" / name,
            stack_root=_stack_root(),
        )

    # Continue to existing PREFERENCES.md flow.
    return _maybe_run_onboard(target, wizard_flags)


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
        return cmd_bare(target, wizard_flags)

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

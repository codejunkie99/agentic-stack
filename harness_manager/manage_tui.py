"""Persistent TUI menu loop for managing installed adapters.

Entry point: `./install.sh manage`. Re-entrant — the user picks an
action, the action runs (with its own prompts as needed), then we
return to the menu. Exits cleanly on `q`, `Exit` menu pick, or two
consecutive Ctrl-C presses.

Reuses onboard_widgets.ask_select / ask_multiselect / ask_confirm
for consistency with the existing wizard. No new UI primitives
beyond the multi-select widget added at the same time.
"""
import os
import shutil
import signal
import sys
from pathlib import Path

# onboard_widgets and onboard_ui live at repo root, not under
# harness_manager/. install.sh prepends repo root to PYTHONPATH so this
# import works.
import onboard_widgets as widgets  # noqa: E402
from onboard_ui import (  # noqa: E402
    R, B, GREEN, ORANGE, MUTED, WHITE, BLUE, PURPLE, BAR,
)

from . import doctor as doctor_mod
from . import install as install_mod
from . import remove as remove_mod
from . import schema as schema_mod
from . import state as state_mod
from . import status as status_mod
from . import __version__


# ---- header pane -----------------------------------------------------

def _render_header(target_root: Path) -> None:
    """One-screen project + brain + adapter summary above the menu prompt."""
    doc = state_mod.load(target_root) or {}
    adapters = doc.get("adapters", {}) or {}

    print()
    print(f"{PURPLE}{B}╭─ agentic-stack — manage{R}")
    print(f"{BAR}  project:  {WHITE}{target_root}{R}")
    print(f"{BAR}  brain:    .agent/  {MUTED}({_brain_summary(target_root)}){R}")
    print(f"{BAR}  version:  agentic-stack {doc.get('agentic_stack_version', __version__)}")
    print(f"{BAR}")
    if not adapters:
        print(f"{BAR}  {MUTED}no adapters installed yet{R}")
    else:
        print(f"{BAR}  installed adapters ({len(adapters)}):")
        # Quick non-mutating audit of each adapter so we can show colour
        # status alongside name.
        for name in sorted(adapters):
            entry = adapters[name]
            status, _ = doctor_mod._audit_adapter(target_root, name, entry)
            glyph_color = {"green": GREEN, "yellow": ORANGE, "red": MUTED}.get(status, MUTED)
            glyph = {"green": "✓", "yellow": "⚠", "red": "✗"}.get(status, "?")
            print(f"{BAR}    {glyph_color}{glyph}{R} {WHITE}{name:18s}{R}  {glyph_color}{status}{R}")
    print(f"{BAR}")


def _brain_summary(target_root: Path) -> str:
    return status_mod._brain_summary(target_root)


# ---- menu actions ----------------------------------------------------

def _action_add(target_root: Path, stack_root: Path) -> None:
    """Multi-select adapters NOT already installed; install each."""
    doc = state_mod.load(target_root) or {}
    installed = set(doc.get("adapters") or {})
    available = sorted(
        n for n, _ in schema_mod.discover_all(stack_root)
        if n not in installed
    )
    if not available:
        print(f"  {MUTED}all available adapters are already installed.{R}")
        return
    chosen = widgets.ask_multiselect(
        "select adapters to add (q to cancel)",
        available,
    )
    if not chosen:
        print(f"  {MUTED}no adapters selected; nothing changed.{R}")
        return
    for name in chosen:
        manifest_path = stack_root / "adapters" / name / "adapter.json"
        manifest = schema_mod.validate(manifest_path)
        install_mod.install(
            manifest=manifest,
            target_root=target_root,
            adapter_dir=stack_root / "adapters" / name,
            stack_root=stack_root,
        )


def _action_remove(target_root: Path) -> None:
    """Multi-select adapters from installed; remove each (with per-adapter confirm)."""
    doc = state_mod.load(target_root) or {}
    installed = sorted((doc.get("adapters") or {}).keys())
    if not installed:
        print(f"  {MUTED}nothing to remove — no adapters installed.{R}")
        return
    chosen = widgets.ask_multiselect(
        "select adapters to remove (q to cancel)",
        installed,
    )
    if not chosen:
        print(f"  {MUTED}no adapters selected; nothing changed.{R}")
        return
    for name in chosen:
        # remove() prompts for its own per-adapter [y/N] confirm with the
        # destruction file list. That's the right place to ask, not the
        # menu — keeps the destructive prompt next to the destructive op.
        remove_mod.remove(target_root, name, yes=False)


def _action_doctor(target_root: Path) -> None:
    """Run audit. Same exit-code semantics as `./install.sh doctor`."""
    rc = doctor_mod.audit(target_root)
    if rc != 0:
        print(f"  {ORANGE}doctor exited non-zero — see above.{R}")


def _action_status(target_root: Path) -> None:
    """Print the full status view (header pane only shows summary)."""
    status_mod.show(target_root)


def _action_reconfigure(target_root: Path, stack_root: Path) -> None:
    """Re-run onboard.py PREFERENCES.md flow."""
    onboard = stack_root / "onboard.py"
    if not onboard.is_file():
        print(f"  {MUTED}onboard.py not found at {onboard}{R}")
        return
    import subprocess
    subprocess.run(
        [sys.executable, str(onboard), str(target_root), "--reconfigure"],
        check=False,
    )


# ---- main menu loop --------------------------------------------------

# Ordered: user-facing labels (left) → internal action tag (right).
_MENU = [
    ("Add an adapter",       "add"),
    ("Remove an adapter",    "remove"),
    ("Run doctor (audit)",   "doctor"),
    ("Show status",          "status"),
    ("Reconfigure preferences", "reconfigure"),
    ("Exit",                 "exit"),
]


def _sigint_handler_factory():
    """SIGINT handler with two-Ctrl-C-to-exit semantics.

    First Ctrl-C inside the menu: print a hint, return to menu (handled
    by the loop catching KeyboardInterrupt). Two consecutive Ctrl-Cs
    within ~1 second: actually exit. Reset the counter on every
    successful menu iteration.
    """
    state = {"last": 0.0}
    def _handler(signum, frame):
        import time
        now = time.time()
        if now - state["last"] < 1.0:
            print()
            print(f"  {MUTED}two ctrl-c — exiting.{R}")
            sys.exit(130)
        state["last"] = now
        # Re-raise as KeyboardInterrupt so the loop body can catch it.
        raise KeyboardInterrupt
    return _handler


def run(target_root: Path | str, stack_root: Path | str) -> int:
    """Enter the menu loop. Returns exit code on quit."""
    target_root = Path(target_root).resolve()
    stack_root = Path(stack_root)

    # Install our SIGINT handler.
    signal.signal(signal.SIGINT, _sigint_handler_factory())

    while True:
        try:
            _render_header(target_root)
            choice_label = widgets.ask_select(
                "what do you want to do?",
                [label for label, _ in _MENU],
            )
            tag = next(t for label, t in _MENU if label == choice_label)
        except KeyboardInterrupt:
            print()
            print(f"  {MUTED}ctrl-c again to exit, or pick an action.{R}")
            continue

        if tag == "exit":
            print(f"  {MUTED}bye.{R}")
            return 0

        try:
            if   tag == "add":         _action_add(target_root, stack_root)
            elif tag == "remove":      _action_remove(target_root)
            elif tag == "doctor":      _action_doctor(target_root)
            elif tag == "status":      _action_status(target_root)
            elif tag == "reconfigure": _action_reconfigure(target_root, stack_root)
        except KeyboardInterrupt:
            print()
            print(f"  {MUTED}action cancelled.{R}")
        except Exception as e:  # pragma: no cover — last-resort safety
            print(f"  {ORANGE}error: {type(e).__name__}: {e}{R}")
        # Loop back to header + menu.

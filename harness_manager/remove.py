"""Remove an installed adapter from a project.

Confirm prompt lists every file before deleting. Hard delete (no
quarantine — codex UX framing: don't over-help, no undo machinery
to learn or trust). User runs `git reset` if they want recovery.
"""
import shutil
import sys
from pathlib import Path
from typing import Callable

from . import post_install as post_install_mod
from . import state as state_mod


def remove(
    target_root: Path | str,
    adapter_name: str,
    yes: bool = False,
    log: Callable[[str], None] | None = None,
) -> int:
    """Remove `adapter_name` from `target_root`. Returns exit code.

    yes=True skips the confirm prompt (CI / scripted use).
    """
    if log is None:
        log = print
    target_root = Path(target_root).resolve()

    doc = state_mod.load(target_root)
    if doc is None:
        log(f"no install.json at {target_root / '.agent/install.json'}; "
            "nothing tracked to remove.")
        return 1
    if adapter_name not in doc.get("adapters", {}):
        log(f"adapter '{adapter_name}' is not in install.json. "
            f"installed: {sorted(doc.get('adapters', {}).keys())}")
        return 1

    entry = doc["adapters"][adapter_name]
    # Only delete files we created. Files that pre-existed (e.g., the
    # user's own AGENTS.md, settings.json, run.py) are tracked in
    # files_overwritten and we leave them alone — destroying a user's
    # pre-install file is exactly the kind of thing remove must NOT do.
    files_to_delete = list(entry.get("files_written", []))
    files_to_preserve = list(entry.get("files_overwritten", []))
    skills_link = entry.get("skills_link")
    skills_link_pre_existed = entry.get("skills_link_pre_existed", False)
    post_install_results = entry.get("post_install_results", [])

    log(f"removing adapter '{adapter_name}' from {target_root}")
    log("")
    log("the following files will be DELETED (no quarantine, no undo):")
    if not files_to_delete and not skills_link:
        log("  (no files tracked for cleanup — adapter entry will just be removed from install.json)")
    for f in files_to_delete:
        marker = "(missing)" if not (target_root / f).exists() else ""
        log(f"  - {f} {marker}".rstrip())
    if skills_link:
        if skills_link_pre_existed:
            log(f"  ~ {skills_link['dst']} (skills_link target pre-existed install — PRESERVED)")
        else:
            log(f"  - {skills_link['dst']} (skills_link, will be unlinked/removed)")
    if files_to_preserve:
        log("")
        log("the following files were modified by install but pre-existed in your project")
        log("and will be PRESERVED (we never delete user-owned content):")
        for f in files_to_preserve:
            log(f"  ~ {f} (use git or your own backup to recover the original if needed)")
    log("")

    # Reverse post_install actions — but ONLY for actions that succeeded
    # at install time. Reversing a failed/skipped registration is wrong:
    # if `openclaw_register_workspace` was binary_missing at install, a
    # subsequent `openclaw agents remove` could delete a manually-created
    # agent for the same workspace that was never ours to manage.
    reverse_actions = []
    for r in post_install_results:
        action = r.get("action")
        status = r.get("status")
        if action in post_install_mod.ACTIONS and status in ("ok", "already_exists"):
            reverse_actions.append(action)
    if reverse_actions:
        log("the following post-install state will be reversed:")
        for a in reverse_actions:
            log(f"  - {a} → reverse")
        log("")

    if not yes:
        if not sys.stdin.isatty():
            log("non-interactive shell and --yes not given; aborting for safety.")
            return 1
        try:
            answer = input("proceed? [y/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            log("")
            log("aborted; no changes.")
            return 0
        if answer not in ("y", "yes"):
            log("aborted; no changes.")
            return 0

    # Delete files
    for f in files_to_delete:
        p = target_root / f
        if p.is_file() or p.is_symlink():
            try:
                p.unlink()
                log(f"  - deleted {f}")
            except OSError as e:
                log(f"  ! could not delete {f}: {e}")

    # Remove skills_link (only the link/dir, not the target!) — but only
    # if the destination did NOT pre-exist install. If user had their own
    # `.agents/skills/` or `.pi/skills/` before installing, we adopted it
    # via rsync sync, but it's still theirs to keep on remove.
    if skills_link and not skills_link_pre_existed:
        dst = target_root / skills_link["dst"]
        try:
            if dst.is_symlink():
                dst.unlink()
                log(f"  - unlinked {skills_link['dst']}")
            elif dst.is_dir():
                shutil.rmtree(dst)
                log(f"  - removed dir {skills_link['dst']}")
        except OSError as e:
            log(f"  ! could not remove {skills_link['dst']}: {e}")
    elif skills_link and skills_link_pre_existed:
        log(
            f"  ~ leaving {skills_link['dst']} alone (it pre-existed install — "
            f"may be user-owned content the installer adopted)"
        )

    # Reverse post_install actions. Pass through any state recorded at
    # install time (e.g. the openclaw agent_name) so the reverse targets
    # the original registration even if the project has been moved or
    # renamed since install.
    for action_name in reverse_actions:
        log(f"  → reversing {action_name}")
        # Find the matching install-time result so we can forward its
        # recorded fields (agent_name, etc.) as kwargs.
        recorded = next(
            (r for r in post_install_results if r.get("action") == action_name),
            {},
        )
        kwargs = {k: v for k, v in recorded.items() if k not in ("action", "status", "stderr", "exit_code", "fallback_hint")}
        result = post_install_mod.reverse(action_name, target_root, **kwargs)
        st = result.get("status", "?")
        if st == "ok":
            log(f"    ✓ reversed")
        elif st == "binary_missing":
            log(f"    ~ binary not on PATH; reverse skipped (manual cleanup may be needed)")
        else:
            log(f"    ! {st}: {result.get('stderr', '')}")

    # Drop from install.json
    state_mod.remove_adapter(target_root, adapter_name)
    log("")
    log(f"removed '{adapter_name}'.")
    return 0

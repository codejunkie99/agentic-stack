"""Manifest-driven adapter installation.

Reads adapters/<name>/adapter.json, applies its files + skills_link +
post_install actions to a target project, records what was done in
.agent/install.json. install.sh and install.ps1 dispatch into here.
"""
import shutil
import sys
from pathlib import Path
from typing import Callable, Iterable

from . import post_install as post_install_mod
from . import schema as schema_mod
from . import state as state_mod
from . import __version__


# ---- merge policies ---------------------------------------------------

def _apply_file(
    src_content: bytes,
    src_text_for_alert: str,
    dst_path: Path,
    merge_policy: str,
    log: Callable[[str], None],
) -> str:
    """Write src_content to dst_path according to merge_policy.

    Returns one of:
      'written_new'        — created the file fresh; safe for `remove` to delete
      'written_overwrite'  — overwrote a pre-existing user file; remove must NOT delete it
      'skipped_existing'   — left an existing file alone (skip_if_exists policy)
      'left_alone'         — merge_or_alert: existing already references .agent/, no action needed
      'merge_alert'        — merge_or_alert: existing did NOT reference .agent/; user must merge manually
    """
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    pre_existed = dst_path.exists()

    if not pre_existed:
        dst_path.write_bytes(src_content)
        log(f"  + {_short(dst_path)}")
        return "written_new"

    if merge_policy == "overwrite":
        dst_path.write_bytes(src_content)
        log(f"  ~ {_short(dst_path)} (overwritten — preserved on remove)")
        return "written_overwrite"

    if merge_policy == "skip_if_exists":
        log(f"  ~ {_short(dst_path)} already exists — skipping")
        return "skipped_existing"

    if merge_policy == "merge_or_alert":
        # If the existing file already references .agent/, leave alone — it's
        # already wired (could be from a prior install or another adapter).
        try:
            existing = dst_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            existing = ""
        if ".agent/" in existing:
            log(f"  ~ {_short(dst_path)} already references .agent/ — leaving alone")
            return "left_alone"
        log(f"  ! {_short(dst_path)} exists but does not reference .agent/; not overwriting.")
        log("    merge this block into your file to wire the brain:")
        log("    ---8<---")
        for line in src_text_for_alert.splitlines():
            log(f"    {line}")
        log("    --->8---")
        return "merge_alert"

    raise ValueError(f"unknown merge_policy '{merge_policy}'")


# ---- skills_link ------------------------------------------------------

def _resolve_skills_link(
    target_root: Path,
    spec: dict,
    log: Callable[[str], None],
) -> str:
    """Symlink dst -> target. Fall back to rsync_with_delete if symlink fails.

    Mirrors the logic from install.sh master after PR #19 fixed the
    silent-orphan bug (-L/-d explicit detection before ln -sfn).
    """
    target_link = target_root / spec["target"]  # e.g. .agent/skills
    dst = target_root / spec["dst"]              # e.g. .pi/skills
    fallback = spec.get("fallback", "rsync_with_delete")

    if not target_link.is_dir():
        raise FileNotFoundError(
            f"skills_link target {target_link} does not exist; "
            f"cannot create symlink/mirror"
        )

    # Resolve target to absolute for the symlink itself.
    target_abs = target_link.resolve()

    dst.parent.mkdir(parents=True, exist_ok=True)

    # Case 1: dst is an existing symlink → repoint (cheap)
    if dst.is_symlink():
        dst.unlink()
        try:
            dst.symlink_to(target_abs)
            log(f"  + {_short(dst)} -> {target_abs}")
            return "symlinked"
        except OSError:
            pass  # fall through to copy

    # Case 2: dst is a real directory → sync with delete-orphans
    if dst.is_dir() and not dst.is_symlink():
        if fallback == "rsync_with_delete" and shutil.which("rsync"):
            import subprocess
            subprocess.run(
                ["rsync", "-a", "--delete", str(target_abs) + "/", str(dst) + "/"],
                check=True,
            )
            log(f"  ~ synced {_short(dst)} (rsync --delete)")
            return "rsynced"
        # rm -rf + cp -r
        shutil.rmtree(dst)
        shutil.copytree(target_abs, dst)
        log(f"  ~ replaced {_short(dst)} with current {_short(target_link)}")
        return "rsynced"

    # Case 3: dst exists as a regular file (not symlink, not dir).
    # Rare but possible — a user created a literal file at the skills
    # path. Symlink_to and copytree both fail with FileExistsError in
    # this state. Bail loudly so the user knows to resolve it; silently
    # clobbering could delete content we can't prove we created.
    if dst.exists() and not dst.is_dir() and not dst.is_symlink():
        raise FileExistsError(
            f"skills_link destination {dst} exists as a regular file, "
            f"not a directory or symlink. move or delete it first and "
            f"re-run install."
        )

    # Case 4: dst doesn't exist → try symlink, fall back to copy
    try:
        dst.symlink_to(target_abs)
        log(f"  + {_short(dst)} -> {target_abs}")
        return "symlinked"
    except OSError:
        shutil.copytree(target_abs, dst)
        log(f"  + {_short(dst)} (copy; symlink not supported here)")
        return "copied"


# ---- variable substitution -------------------------------------------

def _substitute(content: bytes, manifest: dict, target_root: Path) -> bytes:
    """Replace {{BRAIN_ROOT}} etc. in file content. Bytes in, bytes out."""
    primitive = manifest.get("brain_root_primitive")
    if primitive is None:
        return content
    text = content.decode("utf-8")
    text = text.replace("{{BRAIN_ROOT}}", primitive)
    text = text.replace("{{ABS_TARGET}}", str(target_root.resolve()))
    return text.encode("utf-8")


# ---- main install ----------------------------------------------------

def install(
    manifest: dict,
    target_root: Path | str,
    adapter_dir: Path | str,
    stack_root: Path | str,
    log: Callable[[str], None] | None = None,
) -> dict:
    """Apply one adapter's manifest to target_root. Returns install.json entry."""
    if log is None:
        log = print

    target_root = Path(target_root)
    adapter_dir = Path(adapter_dir)
    stack_root = Path(stack_root)
    adapter_name = manifest["name"]

    log(f"installing '{adapter_name}' into {target_root}")

    # 1. Drop .agent/ brain if not present (top-level concern, before any
    #    file entry; some entries depend on .agent/ existing, e.g. pi's
    #    skills_link target = .agent/skills).
    target_agent = target_root / ".agent"
    if not target_agent.exists():
        shutil.copytree(stack_root / ".agent", target_agent)
        log("  + .agent/ (portable brain)")

    files_written: list[str] = []        # we created — safe for remove to delete
    files_overwritten: list[str] = []    # we modified but file pre-existed — DO NOT delete on remove
    files_alerted: list[str] = []        # merge_or_alert that left existing alone — needs user action
    file_results: list[dict] = []

    # On reinstall, look up the previous install.json entry for this adapter
    # so we can preserve installer-owned classification across re-runs. A
    # naive "if it exists now, it pre-existed" misclassifies our own
    # installer-created files as user-owned the second time around — then
    # `remove` would silently leave behind CLAUDE.md / .cursor/rules/*.mdc
    # because it stopped seeing them as ours.
    prior_doc = state_mod.load(target_root) or {}
    prior_entry = (prior_doc.get("adapters") or {}).get(adapter_name) or {}
    prior_owned = set(prior_entry.get("files_written") or [])
    # Intentionally NOT promoting synthesized files_overwritten or
    # files_alerted into prior_owned. Reinstalling after pre-v0.9
    # migration does not recover whether a file originally pre-existed
    # the legacy install; even an overwrite-policy file like CLAUDE.md
    # could have had user content that the old installer clobbered,
    # and we'd have no way to know. Conservative tradeoff: installer-
    # created files from pre-v0.9 may linger on disk after `remove` if
    # the user migrated via doctor. Users who want strict ownership
    # tracking should install via v0.9+ from the start.

    # 2. Process file entries.
    for entry in manifest["files"]:
        from_stack = entry.get("from_stack", False)
        src_root = stack_root if from_stack else adapter_dir
        src_path = src_root / entry["src"]
        if not src_path.is_file():
            raise FileNotFoundError(
                f"adapter '{adapter_name}' file entry: {src_path} does not exist"
            )
        content = src_path.read_bytes()
        if entry.get("substitute", False):
            content = _substitute(content, manifest, target_root)
        merge_policy = entry.get("merge_policy", "overwrite")
        # For merge_or_alert we need text for the snippet output.
        try:
            src_text = content.decode("utf-8")
        except UnicodeDecodeError:
            src_text = "<binary file — see adapter source for content>"
        result = _apply_file(
            src_content=content,
            src_text_for_alert=src_text,
            dst_path=target_root / entry["dst"],
            merge_policy=merge_policy,
            log=log,
        )
        if result == "written_new":
            files_written.append(entry["dst"])
        elif result == "written_overwrite":
            # If we created this file in a previous install (recorded in the
            # prior install.json's files_written), this is a re-install
            # overwriting our OWN file, not a user file. Keep it classified
            # as installer-owned so remove will clean it up.
            if entry["dst"] in prior_owned:
                files_written.append(entry["dst"])
            else:
                files_overwritten.append(entry["dst"])
        elif result in ("skipped_existing", "left_alone"):
            # File wasn't touched on this pass. But if we created it in a
            # prior install, keep it in files_written so `remove` can
            # still clean it up later — otherwise any reinstall of an
            # adapter using skip_if_exists / merge_or_alert silently
            # drops the file from ownership tracking on the second pass
            # (e.g. run.py for standalone-python, AGENTS.md for pi).
            # Not in prior_owned → file pre-existed before we ever
            # touched this project; it's user-owned and stays untracked.
            if entry["dst"] in prior_owned:
                files_written.append(entry["dst"])
        elif result == "merge_alert":
            files_alerted.append(entry["dst"])
        file_results.append({"dst": entry["dst"], "result": result})

    # 3. Skills link. Track whether the destination pre-existed before
    #    install touched it — if so, remove must NOT delete it (codex P1:
    #    `./install.sh remove codex` would otherwise wipe a user-owned
    #    `.agents/skills/` that the installer adopted, not created).
    skills_link_pre_existed = False
    if "skills_link" in manifest:
        skills_dst = target_root / manifest["skills_link"]["dst"]
        skills_link_pre_existed = (
            skills_dst.exists() or skills_dst.is_symlink()
        )
        # Preserve prior install.json's pre-existence flag across re-installs:
        # if WE created the link first time, the second install detecting it
        # exists doesn't make it user-owned now. (Same logic shape as the
        # files_written ownership preservation above.)
        prior_skills_pre_existed = (prior_entry.get("skills_link_pre_existed", False))
        # Intentionally NOT flipping pre_existed on synthesized entries.
        # Doctor conservatively marks `.agents/skills` or `.pi/skills`
        # as pre-existing because we can't know if the user's own
        # skills dir was there before the legacy install. Flipping on
        # reinstall would let remove delete a directory that predated
        # us, potentially containing user content. Same conservative
        # tradeoff as the files_overwritten case above.
        if entry_was_owned_in_prior_install := (
            "skills_link" in prior_entry
            and not prior_skills_pre_existed
        ):
            skills_link_pre_existed = False
        _resolve_skills_link(target_root, manifest["skills_link"], log)

    # 4. Post-install actions.
    post_install_results: list[dict] = []
    for action_name in manifest.get("post_install", []):
        log(f"  → post-install: {action_name}")
        result = post_install_mod.run(action_name, target_root)
        post_install_results.append(result)
        # User-facing summary line
        status = result.get("status", "?")
        if status == "ok":
            log(f"    ✓ {action_name} ok")
        elif status == "already_exists":
            log(f"    ✓ {action_name} idempotent (already present)")
        elif status == "binary_missing":
            log(f"    ! {action_name}: binary missing")
            hint = result.get("fallback_hint")
            if hint:
                log(f"      {hint}")
        else:
            log(f"    ! {action_name}: {status}")
            err = result.get("stderr", "")
            if err:
                log(f"      {err.splitlines()[0] if err else ''}")
            hint = result.get("fallback_hint")
            if hint:
                log(f"      fallback: {hint}")

    # 5. Build the install.json entry.
    entry = {
        "installed_at": _iso_now(),
        "files_written": files_written,            # cleanup-safe (remove deletes these)
        "files_overwritten": files_overwritten,    # pre-existed user content (remove leaves alone)
        "files_alerted": files_alerted,            # merge_alert: needs manual merge by user
        "file_results": file_results,
        "post_install_results": post_install_results,
    }
    if "skills_link" in manifest:
        entry["skills_link"] = manifest["skills_link"]
        entry["skills_link_pre_existed"] = skills_link_pre_existed
    if manifest.get("brain_root_primitive"):
        entry["brain_root_primitive"] = manifest["brain_root_primitive"]

    state_mod.upsert_adapter(target_root, adapter_name, entry, __version__)
    if files_alerted:
        log(f"  ! adapter installed BUT requires manual merge into: {', '.join(files_alerted)}")
        log("    `./install.sh doctor` will flag this until you merge the snippet above.")
    log("done.")
    return entry


# ---- helpers ---------------------------------------------------------

def _short(p: Path) -> str:
    """Shortened path for log lines: relative to cwd if possible."""
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        return str(p)


def _iso_now() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

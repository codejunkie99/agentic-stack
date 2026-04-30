"""Named built-in post-install actions.

Adapters declare these by name only — `post_install: ["openclaw_register_workspace"]`.
The schema validator rejects unknown names. Adding a new action requires
a Python function here AND a string in VALID_POST_INSTALL_ACTIONS in schema.py.

This is deliberately not a plugin DSL or arbitrary command runner. The
codex review of the v1.0 vision plan flagged generalized run_command as
DSL creep; named built-ins are the constrained alternative.
"""
from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import string
import subprocess
from pathlib import Path
from typing import Callable

# ASCII-only allowed set for openclaw agent name basenames. Mirrors
# `tr -c 'A-Za-z0-9._-'` from the legacy bash. str.isalnum() is not safe
# here because it accepts non-ASCII letters — `café`.isalnum() is True
# but bash `tr` would have replaced ç with `-`. Without this exact match,
# upgrade installs would generate different agent ids and create duplicates.
_OPENCLAW_AGENT_NAME_ALLOWED = set(string.ascii_letters + string.digits + "._-")


def _abs_target(target_root: Path | str) -> Path:
    """Absolute, dot-normalized path WITHOUT resolving symlinks.

    Mirrors `cd "$TARGET" && pwd` from the legacy install.sh — POSIX `pwd`
    defaults to the LOGICAL path (`-L`), preserving the symlink chain the
    user invoked from. `Path.resolve()` is the wrong choice here because
    it canonicalizes symlinks; if a user's workspace lives at e.g.
    `~/src/app` (a symlink into another volume), `resolve()` returns the
    target of the symlink, the cksum of that path differs from the cksum
    of the original, and openclaw_register_workspace registers a SECOND
    agent on upgrade. `os.path.abspath()` does what `cd && pwd` does:
    normalizes `.` and `..`, prepends cwd if relative, but never reads
    the filesystem to resolve symlinks.
    """
    return Path(os.path.abspath(str(target_root)))


# POSIX cksum CRC-32 table. Polynomial 0x04C11DB7, no inversion, length-tagged.
# Matches `cksum(1)` output on macOS, Linux, and any POSIX system. Pre-computed
# once at import time. Required for openclaw_register_workspace agent-name
# stability across pre-v0.9.0 (bash) and v0.9.0+ (Python) installs — switching
# to a different hash would create a duplicate openclaw agent on upgrade and
# leave doctor/remove unable to find the original.
def _build_posix_cksum_table() -> tuple[int, ...]:
    table = []
    for i in range(256):
        c = i << 24
        for _ in range(8):
            c = ((c << 1) ^ 0x04C11DB7) & 0xFFFFFFFF if (c & 0x80000000) else (c << 1) & 0xFFFFFFFF
        table.append(c)
    return tuple(table)


_POSIX_CKSUM_TABLE = _build_posix_cksum_table()


def _posix_cksum(data: bytes) -> int:
    """POSIX cksum(1) CRC-32 of `data` (no trailing newline added).

    Bit-for-bit compatible with `printf '%s' "$data" | cksum | awk '{print $1}'`
    which is what install.sh used pre-v0.9.0 to derive the openclaw agent name.
    """
    crc = 0
    for b in data:
        crc = ((crc << 8) ^ _POSIX_CKSUM_TABLE[((crc >> 24) ^ b) & 0xFF]) & 0xFFFFFFFF
    # Append the length as the algorithm's tag.
    length = len(data)
    while length > 0:
        crc = ((crc << 8) ^ _POSIX_CKSUM_TABLE[((crc >> 24) ^ (length & 0xFF)) & 0xFF]) & 0xFFFFFFFF
        length >>= 8
    return (~crc) & 0xFFFFFFFF


def _openclaw_agent_name(target_root: Path | str) -> str:
    """Match whichever pre-v0.9.0 algorithm was used on this platform.

    The legacy install scripts used DIFFERENT hash functions per platform:
      install.sh:    cksum(abs_path) % 1_000_000  →  6-digit decimal suffix
      install.ps1:   sha1(abs_path)[:6]            →  6-hex-char suffix

    Switching either platform to the other algorithm on v0.9.0 upgrade
    would compute a different agent name → register a duplicate agent →
    `remove` targets the new one and leaves the original orphaned in
    ~/.openclaw/openclaw.json.

    So: keep cksum on POSIX, SHA1 on Windows. The agent name is naturally
    platform-locked anyway because absolute paths differ between OSes.
    """
    abs_target = _abs_target(target_root)
    bn_raw = abs_target.name.lower()
    # ASCII-only sanitizer: replace any char outside [a-z0-9._-] with `-`.
    # Mirrors `tr -c 'A-Za-z0-9._-' '-'` (the lowercase pre-step makes the
    # case range moot). Non-ASCII letters are intentionally NOT preserved.
    safe = "".join(c if c in _OPENCLAW_AGENT_NAME_ALLOWED else "-" for c in bn_raw)
    # Collapse runs of dashes (regex equivalent of `sed 's/-\{2,\}/-/g'`).
    safe = re.sub(r"-{2,}", "-", safe).strip("-")
    if not safe:
        safe = "project"
    abs_str = str(abs_target)
    if platform.system() == "Windows":
        # Match the legacy install.ps1: 6-hex-char prefix of SHA1.
        suffix = hashlib.sha1(abs_str.encode("utf-8")).hexdigest()[:6]
    else:
        # Match the legacy install.sh: cksum mod 1M, zero-padded 6-digit.
        suffix = f"{_posix_cksum(abs_str.encode('utf-8')) % 1_000_000:06d}"
    return f"{safe}-{suffix}"


def openclaw_register_workspace(target_root: Path | str, **_kwargs) -> dict:
    """Run `openclaw agents add <name> --workspace <abs>` if openclaw is on PATH.

    Returns a result dict with status: ok | already_exists | failed |
    binary_missing, plus details for the install.json record.
    """
    abs_target = _abs_target(target_root)
    agent_name = _openclaw_agent_name(target_root)
    binary = shutil.which("openclaw")
    if not binary:
        return {
            "action": "openclaw_register_workspace",
            "status": "binary_missing",
            "agent_name": agent_name,
            "fallback_hint": (
                f"after installing openclaw, run: "
                f"openclaw agents add \"{agent_name}\" --workspace \"{abs_target}\""
            ),
        }
    try:
        proc = subprocess.run(
            [binary, "agents", "add", agent_name, "--workspace", str(abs_target)],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "action": "openclaw_register_workspace",
            "status": "failed",
            "agent_name": agent_name,
            "stderr": "timed out after 30s",
        }
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0:
        return {
            "action": "openclaw_register_workspace",
            "status": "ok",
            "agent_name": agent_name,
        }
    if "already exists" in combined.lower():
        return {
            "action": "openclaw_register_workspace",
            "status": "already_exists",
            "agent_name": agent_name,
        }
    return {
        "action": "openclaw_register_workspace",
        "status": "failed",
        "agent_name": agent_name,
        "exit_code": proc.returncode,
        "stderr": combined.strip()[:500],
        "fallback_hint": (
            f"openclaw --system-prompt-file \"{abs_target}/.openclaw-system.md\""
        ),
    }


def openclaw_unregister_workspace(target_root: Path | str, **kwargs) -> dict:
    """Reverse of register: `openclaw agents remove <name>`. Used by `remove`.

    Best-effort. Returns ok if the agent was removed OR didn't exist.

    IMPORTANT: prefer the agent_name passed in via kwargs (recovered from
    install.json's post_install_results record) over recomputing it from
    the current target_root. Otherwise a project that's been moved/renamed
    after install will compute a different agent name (cksum of the new
    abs path), and we'll send `openclaw agents remove <new-name>`. The
    new name doesn't exist → openclaw says "not found" → we treat as ok
    → the original agent stays orphaned in ~/.openclaw/openclaw.json.
    """
    agent_name = kwargs.get("agent_name") or _openclaw_agent_name(target_root)
    binary = shutil.which("openclaw")
    if not binary:
        return {
            "action": "openclaw_unregister_workspace",
            "status": "binary_missing",
            "agent_name": agent_name,
        }
    try:
        proc = subprocess.run(
            [binary, "agents", "remove", agent_name],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return {
            "action": "openclaw_unregister_workspace",
            "status": "failed",
            "agent_name": agent_name,
            "stderr": "timed out after 30s",
        }
    combined = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode == 0 or "not found" in combined.lower():
        return {
            "action": "openclaw_unregister_workspace",
            "status": "ok",
            "agent_name": agent_name,
        }
    return {
        "action": "openclaw_unregister_workspace",
        "status": "failed",
        "agent_name": agent_name,
        "exit_code": proc.returncode,
        "stderr": combined.strip()[:500],
    }


def bcg_conditional_propagate(
    target_root: Path | str,
    *,
    stack_root: Path | str | None = None,
    **_kwargs,
) -> dict:
    """Propagate BCG-adapter content into target/.claude/ when enabled.

    Reads target_root/.agent/config.json. If "bcg_adapter" == "enabled",
    copies adapters/bcg/{agents,commands}/*.md from stack_root into
    target/.claude/{agents,commands}/, and adapters/bcg/agent-memory-
    templates/*.md into target/.claude/agent-memory/ using copy-if-
    missing semantics so re-installs preserve in-progress per-agent
    memory.

    Replaces the bash propagation block that lived in install.sh master
    pre-Step-8.2.5; the v0.9.0 manager-pkg refactor moved install logic
    to Python and this action restores the BCG conditional that the
    bash block carried.
    """
    import json
    target_root = Path(target_root)
    if stack_root is None:
        return {
            "action": "bcg_conditional_propagate",
            "status": "no_stack_root",
            "stderr": "stack_root not passed through from harness_manager.install",
        }
    stack_root = Path(stack_root)

    config_path = target_root / ".agent" / "config.json"
    if not config_path.exists():
        return {"action": "bcg_conditional_propagate", "status": "no_config"}

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {
            "action": "bcg_conditional_propagate",
            "status": "bad_config",
            "stderr": str(e),
        }

    if config.get("bcg_adapter") != "enabled":
        return {"action": "bcg_conditional_propagate", "status": "disabled"}

    bcg_src = stack_root / "adapters" / "bcg"
    if not bcg_src.is_dir():
        return {"action": "bcg_conditional_propagate", "status": "no_bcg_dir"}

    counts = {"agents": 0, "commands": 0, "agent_memory": 0}

    for kind in ("agents", "commands"):
        src_dir = bcg_src / kind
        if not src_dir.is_dir():
            continue
        dst = target_root / ".claude" / kind
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.glob("*.md")):
            shutil.copy2(f, dst / f.name)
            counts[kind] += 1

    src_dir = bcg_src / "agent-memory-templates"
    if src_dir.is_dir():
        dst = target_root / ".claude" / "agent-memory"
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.glob("*.md")):
            if f.name == "README.md":
                continue
            target_file = dst / f.name
            if not target_file.exists():
                shutil.copy2(f, target_file)
                counts["agent_memory"] += 1

    return {
        "action": "bcg_conditional_propagate",
        "status": "ok",
        "counts": counts,
    }


def bcg_conditional_unpropagate(
    target_root: Path | str,
    *,
    stack_root: Path | str | None = None,
    **_kwargs,
) -> dict:
    """Reverse of bcg_conditional_propagate.

    On adapter `remove`, deletes the BCG agents and commands we
    installed (matched by filename against the source stack). Agent-
    memory files are preserved — those become user data once seeded.
    """
    target_root = Path(target_root)
    if stack_root is None:
        return {"action": "bcg_conditional_propagate", "status": "no_stack_root"}
    stack_root = Path(stack_root)

    bcg_src = stack_root / "adapters" / "bcg"
    if not bcg_src.is_dir():
        return {"action": "bcg_conditional_propagate", "status": "no_bcg_dir"}

    removed = 0
    for kind in ("agents", "commands"):
        src_dir = bcg_src / kind
        if not src_dir.is_dir():
            continue
        dst = target_root / ".claude" / kind
        for f in sorted(src_dir.glob("*.md")):
            target_file = dst / f.name
            if target_file.exists():
                target_file.unlink()
                removed += 1

    return {"action": "bcg_conditional_propagate", "status": "ok", "removed": removed}


def take_install_snapshot(
    target_root: Path | str,
    *,
    stack_root: Path | str | None = None,
    **_kwargs,
) -> dict:
    """Capture install-time fingerprint of evolvable harness surfaces.

    Runs `.agent/tools/snapshot_diff.py --snapshot` against the target
    root after all other post-install actions complete. The resulting
    .agent/memory/working/install_snapshot.json is the basis for the
    `--diff` mode the user runs after a dry-run, and for the
    `harness-graduate.py` tool that lands in Step 8.4.

    Idempotent — re-running just refreshes to current state. Failure
    is non-fatal (status='snapshot_failed') because a missing snapshot
    only affects later diff visibility, not install correctness.
    """
    # Resolve to absolute so the subprocess's cwd doesn't double-up the
    # path. With a relative target_root like 'examples/pdlc-sandbox',
    # passing a relative snapshot_tool path AND cwd=target_root makes
    # Python re-resolve the path against target_root, producing
    # 'examples/pdlc-sandbox/examples/pdlc-sandbox/...' which doesn't
    # exist. Absolute resolution sidesteps the issue.
    target_root = Path(target_root).resolve()
    snapshot_tool = target_root / ".agent" / "tools" / "snapshot_diff.py"

    if not snapshot_tool.is_file():
        return {
            "action": "take_install_snapshot",
            "status": "no_tool",
            "stderr": f"{snapshot_tool} not found in target",
        }

    try:
        result = subprocess.run(
            ["python3", str(snapshot_tool), "--snapshot"],
            cwd=str(target_root),
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return {
            "action": "take_install_snapshot",
            "status": "snapshot_failed",
            "stderr": str(e),
        }

    if result.returncode != 0:
        return {
            "action": "take_install_snapshot",
            "status": "snapshot_failed",
            "stderr": result.stderr.strip() or result.stdout.strip(),
            "returncode": result.returncode,
        }

    return {
        "action": "take_install_snapshot",
        "status": "ok",
        "stdout": result.stdout.strip(),
    }


def remove_install_snapshot(
    target_root: Path | str,
    *,
    stack_root: Path | str | None = None,
    **_kwargs,
) -> dict:
    """Reverse of take_install_snapshot — removes the snapshot file on
    adapter remove. Diff report is preserved (it's user-readable history)."""
    target_root = Path(target_root)
    snapshot_path = target_root / ".agent" / "memory" / "working" / "install_snapshot.json"
    if snapshot_path.exists():
        snapshot_path.unlink()
        return {"action": "take_install_snapshot", "status": "ok", "removed": True}
    return {"action": "take_install_snapshot", "status": "ok", "removed": False}


# Registry: action name -> (run_fn, reverse_fn)
ACTIONS: dict[str, tuple[Callable, Callable | None]] = {
    "openclaw_register_workspace": (openclaw_register_workspace, openclaw_unregister_workspace),
    "bcg_conditional_propagate": (bcg_conditional_propagate, bcg_conditional_unpropagate),
    "take_install_snapshot": (take_install_snapshot, remove_install_snapshot),
}


def run(action_name: str, target_root: Path | str, **kwargs) -> dict:
    if action_name not in ACTIONS:
        return {
            "action": action_name,
            "status": "unknown_action",
            "stderr": f"no built-in named '{action_name}'",
        }
    fn, _ = ACTIONS[action_name]
    return fn(target_root, **kwargs)


def reverse(action_name: str, target_root: Path | str, **kwargs) -> dict:
    if action_name not in ACTIONS:
        return {"action": action_name, "status": "unknown_action"}
    _, rev_fn = ACTIONS[action_name]
    if rev_fn is None:
        return {"action": action_name, "status": "no_reverse_defined"}
    return rev_fn(target_root, **kwargs)

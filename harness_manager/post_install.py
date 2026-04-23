"""Named built-in post-install actions.

Adapters declare these by name only — `post_install: ["openclaw_register_workspace"]`.
The schema validator rejects unknown names. Adding a new action requires
a Python function here AND a string in VALID_POST_INSTALL_ACTIONS in schema.py.

This is deliberately not a plugin DSL or arbitrary command runner. The
codex review of the v1.0 vision plan flagged generalized run_command as
DSL creep; named built-ins are the constrained alternative.
"""
import hashlib
import shutil
import subprocess
from pathlib import Path
from typing import Callable


def _abs_target(target_root: Path | str) -> Path:
    return Path(target_root).resolve()


def _openclaw_agent_name(target_root: Path | str) -> str:
    """Match the algorithm install.sh uses today (PR #15) for stable names.

    Lowercase basename + 6-digit cksum-derived suffix. Same name across
    re-runs of the same project, distinct across different projects.
    """
    abs_target = _abs_target(target_root)
    bn_raw = abs_target.name.lower()
    safe = "".join(c if (c.isalnum() or c in "._-") else "-" for c in bn_raw)
    safe = safe.strip("-").replace("--", "-") or "project"
    # cksum on macOS/Linux gives a CRC32-ish 32-bit value. Mirror that.
    h = int(hashlib.sha1(str(abs_target).encode("utf-8")).hexdigest(), 16)
    suffix = h % 1_000_000
    return f"{safe}-{suffix:06d}"


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


def openclaw_unregister_workspace(target_root: Path | str, **_kwargs) -> dict:
    """Reverse of register: `openclaw agents remove <name>`. Used by `remove`.

    Best-effort. Returns ok if the agent was removed OR didn't exist.
    """
    agent_name = _openclaw_agent_name(target_root)
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


# Registry: action name -> (run_fn, reverse_fn)
ACTIONS: dict[str, tuple[Callable, Callable | None]] = {
    "openclaw_register_workspace": (openclaw_register_workspace, openclaw_unregister_workspace),
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

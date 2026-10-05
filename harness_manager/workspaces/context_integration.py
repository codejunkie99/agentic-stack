"""Install the local context MCP bridge for the four supported coding tools."""
from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

from .. import __version__


NAME = "agentic-stack"
BEGIN = "# BEGIN agentic-stack context MCP"
END = "# END agentic-stack context MCP"
SKILL_MARKER = "<!-- agentic-stack-managed -->"
SKILL_TARGETS = {
    "Codex": ".agents/skills/agentic-stack-context/SKILL.md",
    "Claude Code": ".claude/skills/agentic-stack-context/SKILL.md",
    "OpenCode": ".config/opencode/skills/agentic-stack-context/SKILL.md",
    "Cursor": ".cursor/skills/agentic-stack-context/SKILL.md",
}


def _atomic_text(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.is_symlink():
        raise ValueError(f"Refusing to replace linked config: {path}")
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load_json(path):
    if not path.exists():
        return {}
    if path.is_symlink() or path.absolute() != path.resolve():
        raise ValueError(f"Refusing to edit linked config: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"{path} is not valid JSON; keep it valid before enabling Agentic Stack context.") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object.")
    return value


def _merge_json(path, section, definition):
    value = _load_json(path)
    servers = value.setdefault(section, {})
    if not isinstance(servers, dict):
        raise ValueError(f"{path} has a non-object {section} setting.")
    servers[NAME] = definition
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _remove_json(path, section):
    if not path.exists():
        return
    value = _load_json(path)
    servers = value.get(section)
    if isinstance(servers, dict):
        servers.pop(NAME, None)
        _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _opencode_major():
    executable = shutil.which("opencode")
    if not executable:
        return None
    result = subprocess.run([executable, "--version"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, timeout=10, check=False, text=True)
    match = re.search(r"\d+", getattr(result, "stdout", "") or "")
    return int(match.group()) if match else None


def _opencode_config(path, launcher, major=None):
    value = _load_json(path)
    mcp = value.setdefault("mcp", {})
    if not isinstance(mcp, dict):
        raise ValueError(f"{path} has a non-object mcp setting.")
    major = _opencode_major() if major is None else major
    use_v2 = isinstance(mcp.get("servers"), dict) or (major is not None and major >= 2)
    if use_v2:
        servers = mcp.setdefault("servers", {})
        if not isinstance(servers, dict):
            raise ValueError(f"{path} has a non-object mcp.servers setting.")
        servers[NAME] = {"type": "local", "command": [str(launcher)], "disabled": False}
    else:
        mcp[NAME] = {"type": "local", "command": [str(launcher)], "enabled": True}
    _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _remove_opencode(path):
    if not path.exists():
        return
    value = _load_json(path)
    mcp = value.get("mcp")
    if isinstance(mcp, dict):
        mcp.pop(NAME, None)
        servers = mcp.get("servers")
        if isinstance(servers, dict):
            servers.pop(NAME, None)
        _atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _codex_config(path, launcher):
    value = path.read_text(encoding="utf-8") if path.exists() else ""
    if path.exists() and (path.is_symlink() or path.absolute() != path.resolve()):
        raise ValueError(f"Refusing to edit linked config: {path}")
    if re.search(r"(?m)^\s*\[mcp_servers\.(?:agentic-stack|\"agentic-stack\")\]\s*$", value) and BEGIN not in value:
        raise ValueError("Codex already has an unmanaged agentic-stack MCP entry. Remove it before enabling this bridge.")
    escaped = str(launcher).replace("\\", "\\\\").replace('"', '\\"')
    block = f'{BEGIN}\n[mcp_servers.agentic-stack]\ncommand = "{escaped}"\n{END}'
    if BEGIN in value and END in value:
        value = re.sub(re.escape(BEGIN) + r".*?" + re.escape(END), block, value, flags=re.S)
    else:
        value = value.rstrip() + ("\n\n" if value.strip() else "") + block + "\n"
    _atomic_text(path, value)


def _remove_codex(path):
    if not path.exists():
        return
    value = path.read_text(encoding="utf-8")
    updated = re.sub(r"\n?" + re.escape(BEGIN) + r".*?" + re.escape(END) + r"\n?", "\n", value, flags=re.S)
    if updated != value:
        _atomic_text(path, updated.lstrip("\n"))


def _runtime(home, package_root):
    base = home / ".local/share/agentic-stack/context-mcp"
    runtime = base / ("runtime-" + __version__)
    temporary = base / (".runtime-" + __version__ + "-installing")
    previous = base / (".runtime-" + __version__ + "-previous")
    if temporary.exists():
        shutil.rmtree(temporary)
    if previous.exists():
        shutil.rmtree(previous)
    temporary.mkdir(parents=True, exist_ok=False)
    shutil.copytree(package_root, temporary / "harness_manager", symlinks=False,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"))
    if runtime.exists():
        os.replace(runtime, previous)
    os.replace(temporary, runtime)
    if previous.exists():
        shutil.rmtree(previous)
    launcher = home / ".local/bin/agentic-stack-context-mcp"
    command = ("#!/bin/sh\nPYTHONPATH=" + shlex.quote(str(runtime)) +
               " exec /usr/bin/env python3 -m harness_manager.context_mcp\n")
    _atomic_text(launcher, command, 0o755)
    return launcher


def _claude(launcher, remove=False):
    executable = shutil.which("claude")
    if not executable:
        return "Claude Code is not installed; run Enable again after installing it."
    subprocess.run([executable, "mcp", "remove", "--scope", "user", NAME],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15, check=False)
    if remove:
        return "Removed"
    result = subprocess.run([executable, "mcp", "add", "--scope", "user", NAME, "--", str(launcher)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=15, check=False, text=True)
    if result.returncode:
        return "Claude Code rejected the MCP configuration. Run `claude mcp add --scope user agentic-stack -- " + str(launcher) + "`."
    return "Enabled"


def _cursor_approval(enable):
    executable = shutil.which("cursor")
    if not executable:
        return False
    action = "enable" if enable else "disable"
    result = subprocess.run([executable, "agent", "mcp", action, NAME], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, timeout=15, check=False)
    return result.returncode == 0


def _install_tag_skills(home, package_root):
    """Install the same literal @-tag behavior in each host's global skill path."""
    source = package_root / "assets/agentic-stack-context/SKILL.md"
    content = source.read_text(encoding="utf-8")
    results = {}
    for tool, relative in SKILL_TARGETS.items():
        target = home / relative
        if target.exists():
            if target.is_symlink() or target.absolute() != target.resolve():
                results[tool] = "kept linked skill"
                continue
            existing = target.read_text(encoding="utf-8")
            if SKILL_MARKER not in existing:
                results[tool] = "kept existing skill"
                continue
        _atomic_text(target, content)
        results[tool] = "installed"
    return results


def _remove_tag_skills(home):
    for relative in SKILL_TARGETS.values():
        target = home / relative
        if not target.is_file() or target.is_symlink() or target.absolute() != target.resolve():
            continue
        try:
            managed = SKILL_MARKER in target.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            managed = False
        if managed:
            target.unlink()
            try:
                target.parent.rmdir()
            except OSError:
                pass


def install(home, package_root):
    home, package_root = home.resolve(), package_root.resolve()
    launcher = _runtime(home, package_root)
    statuses = {}
    try:
        _codex_config(home / ".codex/config.toml", launcher); statuses["Codex"] = "Enabled"
    except ValueError as exc:
        statuses["Codex"] = str(exc)
    statuses["Claude Code"] = _claude(launcher)
    try:
        _merge_json(home / ".cursor/mcp.json", "mcpServers", {"command": str(launcher), "args": []})
        statuses["Cursor"] = "Enabled" if _cursor_approval(True) else "Configured; approve agentic-stack when Cursor asks."
    except ValueError as exc:
        statuses["Cursor"] = str(exc)
    try:
        _opencode_config(home / ".config/opencode/opencode.json", launcher)
        statuses["OpenCode"] = "Enabled"
    except ValueError as exc:
        statuses["OpenCode"] = str(exc)
    tag_skills = _install_tag_skills(home, package_root)
    return {"launcher": str(launcher), "tools": statuses,
            "tagSkills": tag_skills,
            "text": "\n".join(f"{name}: {state}; @ tags {tag_skills[name]}" for name, state in statuses.items())}


def remove(home):
    home = home.resolve()
    _remove_codex(home / ".codex/config.toml")
    _remove_json(home / ".cursor/mcp.json", "mcpServers")
    _cursor_approval(False)
    _remove_opencode(home / ".config/opencode/opencode.json")
    _remove_tag_skills(home)
    claude = _claude(home / ".local/bin/agentic-stack-context-mcp", remove=True)
    return {"text": "Agentic Stack context and managed @ tag skills were removed from Codex, Cursor, and OpenCode. Claude Code: " + claude}

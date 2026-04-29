#!/usr/bin/env python3
"""
template_registry.py -- Manage bundled, session, and workspace templates.

Bundled templates live under styles/templates/<name>/ inside the packaged skill.
Runtime-ingested templates may also live in:

- session scope:  <cwd>/templates/
- workspace scope: <cwd>/.deckster-slide-generator/templates/

Server-side orchestrated runtimes should prefer workspace persistence when the
runtime exposes `supports_workspace_persistence=true`.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from pptx_utils import find_skill_root
from runtime_capabilities import detect_runtime_capabilities


REGISTRY_FILE = "_registry.json"
SESSION_DIRNAME = "templates"
WORKSPACE_DIRNAME = ".deckster-slide-generator/templates"
_SKILL_DIR = find_skill_root()


def _registry_paths():
    cwd = Path.cwd()
    return {
        "bundled": _SKILL_DIR / "styles" / "templates",
        "workspace": cwd / WORKSPACE_DIRNAME,
        "session": cwd / SESSION_DIRNAME,
    }


def _load_registry():
    merged = {"default": "bcg_default", "templates": {}}
    for key in ("bundled", "workspace", "session"):
        root = _registry_paths()[key]
        reg_path = root / REGISTRY_FILE
        if not reg_path.exists():
            continue
        try:
            with open(reg_path) as handle:
                payload = json.load(handle)
        except (json.JSONDecodeError, OSError):
            continue
        merged["templates"].update(payload.get("templates", {}))
        if payload.get("default"):
            merged["default"] = payload["default"]

    if "bcg_default" not in merged["templates"]:
        merged["templates"]["bcg_default"] = {
            "name": "BCG Default",
            "font": "Trebuchet MS",
            "primary_color": "#29BA74",
            "source": "built-in",
            "availability": "bundled",
        }

    return merged


def list_templates(skill_dir=None):
    """Return merged registry with all available templates."""
    return _load_registry()


def _template_search_roots():
    paths = _registry_paths()
    return [paths["session"], paths["workspace"], paths["bundled"]]


def get_template(skill_dir=None, name=None):
    """Load a template config by name from session, workspace, or bundled roots."""
    registry = _load_registry()
    if name is None:
        name = registry.get("default", "bcg_default")

    for root in _template_search_roots():
        template_dir = root / name
        config_path = template_dir / "template.json"
        if not config_path.exists():
            continue
        with open(config_path) as handle:
            config = json.load(handle)
        config["_template_dir"] = str(template_dir)
        config["_master_pptx"] = str(template_dir / config.get("template_file", "master.pptx"))
        return config

    return None


def _safe_template_name(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", (name or "").strip()).lower().strip("_")


def template_destination_root(availability="auto", destination_root=None):
    if destination_root:
        return Path(destination_root)

    paths = _registry_paths()
    if availability == "session":
        return paths["session"]
    if availability == "workspace":
        return paths["workspace"]

    capabilities = detect_runtime_capabilities(anchor=__file__)
    return paths["workspace"] if capabilities.supports_workspace_persistence else paths["session"]


def save_template(
    name=None,
    config=None,
    template_dir=None,
    destination_root=None,
    availability="auto",
):
    """Persist a template in session or workspace scope.

    `availability="auto"` chooses workspace scope when supported and session
    scope otherwise.
    """
    destination_root = template_destination_root(
        availability=availability,
        destination_root=destination_root,
    )
    destination_root.mkdir(parents=True, exist_ok=True)

    template_dir_path = Path(template_dir) if template_dir else None
    raw_name = name or (config or {}).get("name") or (template_dir_path.name if template_dir_path else "")
    safe_name = _safe_template_name(raw_name)
    if not safe_name:
        raise ValueError("Template name is required")

    dest_dir = destination_root / safe_name
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    if template_dir_path is not None and template_dir_path.exists():
        shutil.copytree(template_dir_path, dest_dir)
    else:
        dest_dir.mkdir(parents=True, exist_ok=True)

    if config is not None:
        write_config = dict(config)
        write_config.pop("_template_dir", None)
        write_config.pop("_master_pptx", None)
        with open(dest_dir / "template.json", "w") as handle:
            json.dump(write_config, handle, indent=2)

    display_name = (config or {}).get("description") or (config or {}).get("name") or raw_name or safe_name
    registry = _load_registry()
    scope = "workspace" if ".deckster-slide-generator" in str(destination_root) else "session"
    registry["templates"][safe_name] = {
        "name": display_name,
        "font": (config or {}).get("font", "unknown"),
        "primary_color": _get_primary_color(config or {}),
        "source": (config or {}).get("source", "saved"),
        "availability": scope,
    }

    with open(destination_root / REGISTRY_FILE, "w") as handle:
        json.dump(registry, handle, indent=2)

    return dest_dir


def _get_primary_color(config):
    aliases = config.get("color_aliases", {})
    if "GREEN" in aliases:
        return f"#{aliases['GREEN']}"
    scheme = config.get("scheme_colors", {})
    if "accent1" in scheme:
        return scheme["accent1"]
    return "#29BA74"


def format_template_menu(registry):
    """Format a user-friendly menu of available templates."""
    templates = registry.get("templates", {})
    default = registry.get("default", "bcg_default")
    if not templates:
        return "No saved templates are available. Use the bundled BCG default or ingest a client .ee4p file."

    ordered = list(templates.items())
    if len(ordered) == 1:
        name, info = ordered[0]
        display = info.get("name", name)
        font = info.get("font", "unknown")
        color = info.get("primary_color", "")
        default_marker = " (default)" if name == default else ""
        return f"Using template: **{display}**{default_marker} -- {font}, {color}"

    lines = ["I have multiple templates available:\n"]
    for i, (name, info) in enumerate(ordered, 1):
        display = info.get("name", name)
        font = info.get("font", "unknown")
        color = info.get("primary_color", "")
        availability = info.get("availability", "")
        default_marker = " (default)" if name == default else ""
        scope = f" [{availability}]" if availability else ""
        lines.append(f"{i}. **{display}**{default_marker}{scope} -- {font}, {color}")
    lines.append("\nWhich template should I use for this deck?")
    return "\n".join(lines)

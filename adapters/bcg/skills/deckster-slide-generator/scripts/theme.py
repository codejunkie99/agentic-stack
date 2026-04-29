"""Theme normalization helpers shared by built-in and ingested templates."""

from __future__ import annotations

from copy import deepcopy


def _strip_hash(value):
    if isinstance(value, str):
        return value.lstrip("#")
    return value


def normalize_theme_config(config):
    """Normalize built-in and ingested template configs into one runtime shape."""
    if config is None:
        return None

    normalized = deepcopy(config)

    if not normalized.get("source"):
        normalized["source"] = "built-in" if normalized.get("name") == "bcg_default" else "client"

    scheme = normalized.get("scheme_colors", {})
    normalized["scheme_colors"] = {key: _strip_hash(value) for key, value in scheme.items()}

    aliases = normalized.get("color_aliases", {})
    normalized["color_aliases"] = {key: _strip_hash(value) for key, value in aliases.items()}

    for style_key in ("title_style", "body_style"):
        style = normalized.get(style_key, {})
        if style.get("fillColor"):
            style["fillColor"] = _strip_hash(style["fillColor"])
        normalized[style_key] = style

    if "semantic_layout_map" not in normalized:
        normalized["semantic_layout_map"] = {}
    if "detail_layout_map" not in normalized:
        normalized["detail_layout_map"] = {}

    return normalized


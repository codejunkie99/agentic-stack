"""
Pattern variant system — discover, load, and execute visual pattern variants.

Each pattern type (flywheel, process_flow, column_cards, etc.) can have multiple
rendering variants. Each variant is a self-contained Python file with a render()
function that uses the BCGDeck API to draw the pattern.

Usage:
    from pattern_variants import render_pattern, list_variants, get_variant_info

    # Render with default variant
    render_pattern(deck, slide, "flywheel", data={"stages": [...], "center_message": "Value"}, bounds=bounds)

    # Render with specific variant
    render_pattern(deck, slide, "flywheel", variant="concentric_rings", data={...}, bounds=bounds)

    # Discover available variants
    variants = list_variants("flywheel")
    info = get_variant_info("flywheel", "circular_orbit")
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


from pptx_utils import find_skill_root

_SKILL_DIR = find_skill_root()
_STYLES_DIR = _SKILL_DIR / "styles"
_VARIANTS_DIR = _STYLES_DIR / "variants"

# Persistent user variants (mirrors template_registry pattern)
_PERSISTENT_DIRS = [
    Path("/mnt/user-data/deckster-slide-generator/styles/variants"),
    Path.home() / ".deckster-slide-generator" / "styles" / "variants",
]

_PERSISTENT_DEFAULT_FILES = [
    Path("/mnt/user-data/deckster-slide-generator/styles/_defaults.json"),
    Path.home() / ".deckster-slide-generator" / "styles" / "_defaults.json",
]

_defaults_cache: dict | None = None
_meta_cache: dict[str, dict] = {}
_module_cache: dict[str, Any] = {}


def _load_defaults() -> dict:
    """Load _defaults.json mapping pattern → default variant name."""
    global _defaults_cache
    if _defaults_cache is not None:
        return _defaults_cache
    merged = {}
    bundled_path = _STYLES_DIR / "_defaults.json"
    if bundled_path.exists():
        with open(bundled_path) as f:
            merged.update(json.load(f))
    for path in _PERSISTENT_DEFAULT_FILES:
        if path.exists():
            with open(path) as f:
                merged.update(json.load(f))
    _defaults_cache = merged
    return _defaults_cache


def _find_pattern_dir(pattern: str) -> Path | None:
    """Find the directory for a pattern type across bundled + persistent locations."""
    # Bundled first
    candidate = _VARIANTS_DIR / pattern
    if candidate.exists() and (candidate / "index.json").exists():
        return candidate
    # Then persistent
    for d in _PERSISTENT_DIRS:
        candidate = d / pattern
        if candidate.exists() and (candidate / "index.json").exists():
            return candidate
    return None


def _load_meta(pattern: str) -> dict:
    """Load index.json for a pattern type."""
    if pattern in _meta_cache:
        return _meta_cache[pattern]
    pattern_dir = _find_pattern_dir(pattern)
    if pattern_dir is None:
        return {}
    meta_path = pattern_dir / "index.json"
    with open(meta_path) as f:
        meta = json.load(f)
    _meta_cache[pattern] = meta
    return meta


def _load_variant_module(pattern: str, variant: str):
    """Load a variant's Python module."""
    cache_key = f"{pattern}/{variant}"
    if cache_key in _module_cache:
        return _module_cache[cache_key]

    meta = _load_meta(pattern)
    variant_info = meta.get("variants", {}).get(variant)
    if variant_info is None:
        raise ValueError(f"Variant '{variant}' not found for pattern '{pattern}'. "
                         f"Available: {list(meta.get('variants', {}).keys())}")

    filename = variant_info.get("file", f"{variant}.py")
    pattern_dir = _find_pattern_dir(pattern)
    if pattern_dir is None:
        raise FileNotFoundError(f"Pattern directory not found for '{pattern}'")

    module_path = pattern_dir / filename
    if not module_path.exists():
        raise FileNotFoundError(f"Variant file not found: {module_path}")

    # Load the module dynamically
    spec = importlib.util.spec_from_file_location(f"variant_{pattern}_{variant}", str(module_path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not hasattr(module, "render"):
        raise AttributeError(f"Variant '{variant}' for pattern '{pattern}' "
                             f"is missing a render() function")

    _module_cache[cache_key] = module
    return module


_KEY_ALIASES: dict[str, dict[str, list[str]]] = {
    "column_cards": {"items": ["cards", "columns", "pillars", "tiles"]},
    "exec_summary": {"cards": ["items", "sections", "narratives", "scqa"]},
    "kpi": {
        "kpis": ["items", "metrics", "indicators", "tiles"],
        "metrics": ["items", "kpis", "numbers"],
    },
    "timeline": {"phases": ["items", "milestones", "stages", "steps"]},
    "process_flow": {"stages": ["items", "steps", "phases", "process"]},
    "gantt": {"workstreams": ["items", "tracks", "streams", "rows"]},
    "split_panel": {"options": ["items", "decisions", "choices", "cards"]},
    "flywheel": {"stages": ["items", "steps", "elements"]},
    "funnel": {"stages": ["items", "levels", "steps"]},
    "pyramid": {"layers": ["items", "levels", "tiers"]},
    "vertical_stack": {"items": ["rows", "entries"]},
    "swot_2x2": {"quadrants": ["items", "sections", "cells"]},
    "compact_row_list": {"items": ["rows", "entries", "list"]},
    "accent_rows": {"items": ["rows", "entries"]},
    "grid_layout": {"items": ["cells", "tiles", "cards"]},
    "scatter_bubble": {"items": ["bubbles", "elements", "data_points"]},
    "harvey_ball": {"rows": ["items", "capabilities"], "columns": ["levels", "headers"]},
    "org_chart": {"root": ["leader", "top", "head"]},
    "data_table": {"headers": ["columns", "header"], "rows": ["data", "entries"]},
    "before_after": {"before_items": ["current", "as_is"], "after_items": ["future", "to_be"]},
}


def _apply_key_aliases(pattern: str, normalized: dict) -> dict:
    """Auto-alias common wrong data keys to canonical keys for a pattern."""
    aliases = _KEY_ALIASES.get(pattern)
    if not aliases:
        return normalized
    for canonical, alt_keys in aliases.items():
        if normalized.get(canonical):
            continue
        for alt in alt_keys:
            if normalized.get(alt):
                import warnings
                warnings.warn(
                    f"render_pattern('{pattern}'): data key '{alt}' auto-aliased "
                    f"to '{canonical}'. Use '{canonical}' directly.",
                    UserWarning,
                    stacklevel=5,
                )
                normalized[canonical] = normalized[alt]
                break
    return normalized


def _normalize_variant_payload(pattern: str, data: dict | None) -> dict:
    """Normalize documented payload aliases into the renderer's canonical shape."""
    normalized = dict(data or {})
    normalized = _apply_key_aliases(pattern, normalized)

    if pattern == "multi_column_process":
        stages = normalized.get("stages")
        workstreams = normalized.get("workstreams")
        if not stages and workstreams:
            normalized["stages"] = [
                {
                    "label": item.get("label") or item.get("name") or f"Workstream {idx + 1}",
                    "details": item.get("details") or item.get("bullets") or [],
                }
                for idx, item in enumerate(workstreams)
            ]

    elif pattern == "stage_gate":
        stages = normalized.get("stages")
        gates = normalized.get("gates")
        if not stages and isinstance(gates, list) and gates:
            if any(isinstance(item, dict) and ("details" in item or "subtitle" in item or "name" in item) for item in gates):
                normalized["stages"] = [
                    {
                        "name": item.get("name") or item.get("label") or f"Stage {idx + 1}",
                        "details": item.get("details") or item.get("bullets") or [],
                        "subtitle": item.get("subtitle", ""),
                    }
                    for idx, item in enumerate(gates)
                ]
                normalized["gates"] = [
                    {"label": item.get("subtitle") or item.get("label") or ""}
                    for item in gates
                ]
        elif isinstance(stages, list) and stages:
            normalized["stages"] = [
                {
                    "name": item.get("name") or item.get("label") or f"Stage {idx + 1}",
                    "details": item.get("details") or item.get("bullets") or [],
                    "subtitle": item.get("subtitle", ""),
                }
                for idx, item in enumerate(stages)
            ]
            if not normalized.get("gates") and any(item.get("subtitle") for item in normalized["stages"]):
                normalized["gates"] = [{"label": item.get("subtitle", "")} for item in normalized["stages"]]

    return normalized


def _run_variant_preflight(module, deck, slide, pattern: str, variant: str, data: dict, bounds: dict, **kwargs):
    """Run optional variant-level validation before rendering."""
    validate = getattr(module, "validate", None)
    if not callable(validate):
        return
    result = validate(deck, slide, data, bounds, **kwargs)
    if not result:
        return
    if isinstance(result, str):
        raise ValueError(f"{pattern}/{variant}: {result}")
    if isinstance(result, (list, tuple)):
        message = "; ".join(str(item) for item in result if item)
        if message:
            raise ValueError(f"{pattern}/{variant}: {message}")
        return
    raise ValueError(f"{pattern}/{variant}: {result}")


def normalize_pattern_data(pattern: str, data: dict | None) -> dict:
    """Public wrapper for pattern payload normalization."""
    return _normalize_variant_payload(pattern, data)


def _resolve_variant_name(deck, pattern: str, variant: str | None = None) -> str:
    """Resolve the active variant name using deck, template, and defaults."""
    if variant is None and deck is not None:
        deck_variants = getattr(deck, "_variant_preferences", {})
        variant = deck_variants.get(pattern)

    if variant is None and deck is not None:
        theme_config = getattr(deck, "_theme_config", None) or {}
        template_variants = theme_config.get("pattern_variants", {})
        variant = template_variants.get(pattern)

    if variant is None:
        meta = _load_meta(pattern)
        variant = meta.get("default_variant")

    if variant is None:
        defaults = _load_defaults()
        variant = defaults.get(pattern)

    if variant is None:
        raise ValueError(f"No default variant configured for pattern '{pattern}'")

    return variant


def preflight_pattern(
    deck,
    pattern: str,
    variant: str | None = None,
    data: dict | None = None,
    bounds: dict | None = None,
    slide=None,
    **kwargs,
):
    """Normalize and validate a pattern payload without rendering it."""
    data = _normalize_variant_payload(pattern, data or {})
    variant = _resolve_variant_name(deck, pattern, variant)

    if bounds is None:
        try:
            from bcg_template import content_bounds
            bounds = content_bounds()
        except ImportError:
            bounds = {"x": 0.69, "y": 1.70, "w": 11.96, "h": 4.80}

    module = _load_variant_module(pattern, variant)
    _run_variant_preflight(module, deck, slide, pattern, variant, data, bounds, **kwargs)
    return {"variant": variant, "data": data, "bounds": bounds}


def render_pattern(
    deck,
    slide,
    pattern: str,
    variant: str | None = None,
    data: dict | None = None,
    bounds: dict | None = None,
    **kwargs,
):
    """Render a pattern variant on a slide.

    Args:
        deck: BCGDeck instance
        slide: slide reference from add_content_slide()
        pattern: pattern type name (e.g., "flywheel", "process_flow")
        variant: variant name (e.g., "circular_orbit"). None = use default.
        data: structured content data for the pattern
        bounds: content zone dict from content_bounds() — {"x", "y", "w", "h", ...}
        **kwargs: additional keyword arguments passed to the variant's render()
    """
    if data is None:
        data = {}
    data = _normalize_variant_payload(pattern, data)
    variant = _resolve_variant_name(deck, pattern, variant)

    # Warn if the primary data key for this pattern is empty/missing
    _meta = _load_meta(pattern)
    _vinfo = _meta.get("variants", {}).get(variant, {})
    _primary_key = (_vinfo.get("inputs") or [None])[0]
    if _primary_key and not data.get(_primary_key):
        import warnings
        warnings.warn(
            f"render_pattern('{pattern}/{variant}'): primary data key "
            f"'{_primary_key}' is empty or missing — slide will be blank. "
            f"Pass data={{'{_primary_key}': [...]}}.",
            UserWarning,
            stacklevel=2,
        )

    # Resolve bounds if not provided
    if bounds is None:
        try:
            from bcg_template import content_bounds
            bounds = content_bounds()
        except ImportError:
            bounds = {"x": 0.69, "y": 1.70, "w": 11.96, "h": 4.80}

    # Load and execute the variant
    module = _load_variant_module(pattern, variant)
    _run_variant_preflight(module, deck, slide, pattern, variant, data, bounds, **kwargs)
    result = module.render(deck, slide, data, bounds, **kwargs)

    # Post-render bounds check: warn immediately if shapes exceed the
    # content zone.  This catches zone bleed and y-overflow DURING build
    # instead of deferring to post-save QA.
    _post_render_bounds_check(deck, slide, pattern, variant, bounds)

    return result


def _post_render_bounds_check(deck, slide, pattern, variant, bounds):
    """Clamp shapes that exceed the content zone bounds after rendering.

    Instead of warning and leaving the overflow for QA to flag later,
    this shrinks overflowing shapes in-place so they stay within bounds.
    Fixes zone bleed and y-overflow automatically during build.
    """
    if not slide or not bounds:
        return
    try:
        work_dir = getattr(deck, '_work_dir', None)
        if not work_dir:
            return
        from pathlib import Path
        import xml.etree.ElementTree as ET
        slide_path = Path(work_dir) / slide if isinstance(slide, str) else slide
        if not slide_path.exists():
            return
        tree = ET.parse(slide_path)
        ns = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
              'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'}
        EMU = 914400
        y_end = bounds.get('y_end', bounds['y'] + bounds['h'])
        x_end = bounds.get('x_end', bounds['x'] + bounds['w'])
        tol = 0.10  # tolerate up to 0.10" overflow before clamping
        modified = False
        for sp in tree.findall('.//p:sp', ns):
            xfrm = sp.find('.//a:xfrm', ns)
            if xfrm is None:
                continue
            off = xfrm.find('a:off', ns)
            ext = xfrm.find('a:ext', ns)
            if off is None or ext is None:
                continue
            sy = int(off.get('y', 0)) / EMU
            sh = int(ext.get('cy', 0)) / EMU
            sx = int(off.get('x', 0)) / EMU
            sw = int(ext.get('cx', 0)) / EMU

            # Clamp y-overflow: shrink height so shape ends at y_end
            if sh > 0.1 and sy + sh > y_end + tol:
                new_h = max(0.1, y_end - sy)
                ext.set('cy', str(int(new_h * EMU)))
                modified = True

            # Clamp x-overflow: shrink width so shape ends at x_end
            if sw > 0.1 and sx + sw > x_end + tol and sx < x_end:
                new_w = max(0.1, x_end - sx)
                ext.set('cx', str(int(new_w * EMU)))
                modified = True

            # Clamp cross-zone: on split layouts, if a shape starts in the
            # left zone but extends past the split boundary, shrink it.
            right_x = bounds.get('right_x')
            left_end = bounds.get('left_x', 0) + bounds.get('left_w', 999)
            if right_x and sw > 0.3 and sx < left_end and sx + sw > right_x + tol:
                new_w = max(0.3, left_end - sx)
                ext.set('cx', str(int(new_w * EMU)))
                modified = True

        if modified:
            tree.write(str(slide_path), xml_declaration=True, encoding='UTF-8')
    except Exception:
        pass  # Bounds clamping is best-effort; never block rendering


def list_patterns() -> list[str]:
    """List all available pattern types."""
    patterns = set()
    if _VARIANTS_DIR.exists():
        for d in _VARIANTS_DIR.iterdir():
            if d.is_dir() and (d / "index.json").exists():
                patterns.add(d.name)
    for persistent_dir in _PERSISTENT_DIRS:
        if persistent_dir.exists():
            for d in persistent_dir.iterdir():
                if d.is_dir() and (d / "index.json").exists():
                    patterns.add(d.name)
    return sorted(patterns)


def list_variants(pattern: str) -> dict[str, str]:
    """List available variants for a pattern type.

    Returns:
        dict mapping variant name → description
    """
    meta = _load_meta(pattern)
    return {
        name: info.get("description", "")
        for name, info in meta.get("variants", {}).items()
    }


def get_variant_info(pattern: str, variant: str) -> dict:
    """Get full metadata for a specific variant."""
    meta = _load_meta(pattern)
    return meta.get("variants", {}).get(variant, {})


def clear_cache():
    """Clear all caches. Call after theme changes or style installations."""
    global _defaults_cache, _meta_cache, _module_cache
    _defaults_cache = None
    _meta_cache = {}
    _module_cache = {}

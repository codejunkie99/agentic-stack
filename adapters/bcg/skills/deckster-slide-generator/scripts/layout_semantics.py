"""Canonical semantic layout families for deck planning and runtime enforcement."""

from __future__ import annotations

import re
from copy import deepcopy


DEFAULT_BEHAVIOR = {
    "layout_class": "full_page",
    "description": "",
    "structural": False,
    "statement": False,
    "body_allowed": True,
    "image_only": False,
    "protected_title_panel": False,
    "narrow_panel": False,
    "primary_zone": "full",
    "title_max_chars": 100,
    "allow_title_line_breaks": False,
    "source_mode": "standard",
}


LAYOUT_FAMILIES = {
    "title_slide": {
        "layout_class": "structural",
        "description": "Opening slide for a deck.",
        "structural": True,
        "body_allowed": False,
        "title_max_chars": 68,
        "source_mode": "none",
    },
    "content": {
        "layout_class": "full_page",
        "description": "Default workhorse evidence slide.",
        "title_max_chars": 100,
    },
    "section_divider": {
        "layout_class": "structural",
        "description": "Section break with no supporting content.",
        "structural": True,
        "body_allowed": False,
        "title_max_chars": 55,
        "source_mode": "none",
    },
    "disclaimer": {
        "layout_class": "structural",
        "description": "Legal / closing disclaimer slide.",
        "structural": True,
        "body_allowed": False,
        "title_max_chars": 70,
        "source_mode": "none",
    },
    "end": {
        "layout_class": "structural",
        "description": "Deck end slide.",
        "structural": True,
        "body_allowed": False,
        "title_max_chars": 55,
        "source_mode": "none",
    },
    "blank": {
        "layout_class": "custom_canvas",
        "description": "Blank custom canvas used sparingly.",
        "title_max_chars": 90,
    },
    "green_one_third": {
        "layout_class": "framing_split",
        "description": "Category or framework framing on the accent side.",
        "protected_title_panel": True,
        "narrow_panel": True,
        "primary_zone": "right",
        "title_max_chars": 28,
        "allow_title_line_breaks": True,
    },
    "green_left_arrow": {
        "layout_class": "framing_split",
        "description": "Decision ask or short framing statement on the accent side.",
        "protected_title_panel": True,
        "narrow_panel": True,
        "primary_zone": "right",
        "title_max_chars": 28,
        "allow_title_line_breaks": True,
    },
    "green_half": {
        "layout_class": "image_led",
        "description": "Image-led split layout where the image is primary evidence.",
        "body_allowed": False,
        "image_only": True,
        "protected_title_panel": True,
        "narrow_panel": True,
        "primary_zone": "right",
        "title_max_chars": 36,
        "allow_title_line_breaks": True,
        "source_mode": "none",
    },
    "green_two_third": {
        "layout_class": "image_supported",
        "description": "Text-led slide with supporting image.",
        "body_allowed": False,
        "image_only": True,
        "protected_title_panel": True,
        "narrow_panel": True,
        "primary_zone": "right",
        "title_max_chars": 42,
        "allow_title_line_breaks": True,
        "source_mode": "none",
    },
    "green_highlight": {
        "layout_class": "insight_split",
        "description": "Analysis plus a distinct insight panel.",
        "primary_zone": "left",
        "title_max_chars": 90,
    },
    "arrow_half": {
        "layout_class": "contrast",
        "description": "Contrast relationship such as before/after or problem/solution.",
        "primary_zone": "left",
        "title_max_chars": 90,
    },
    "arrow_two_third": {
        "layout_class": "rich_split",
        "description": "Accent treatment with richer supporting content.",
        "primary_zone": "left",
        "title_max_chars": 90,
    },
    "big_statement_green": {
        "layout_class": "statement",
        "description": "High-impact statement slide without supporting body content.",
        "statement": True,
        "body_allowed": False,
        "title_max_chars": 58,
        "allow_title_line_breaks": True,
        "source_mode": "none",
    },
    "big_statement_icon": {
        "layout_class": "statement",
        "description": "High-impact statement slide reinforced by an icon.",
        "statement": True,
        "body_allowed": False,
        "title_max_chars": 52,
        "allow_title_line_breaks": True,
        "source_mode": "none",
    },
}


SEMANTIC_TO_RUNTIME_LAYOUT = {
    "title_slide": "title",
    "content": "title_only",
    "section_divider": "section_header_box",
    "disclaimer": "disclaimer",
    "end": "end",
    "blank": "blank",
    "green_one_third": "green_one_third",
    "green_left_arrow": "green_left_arrow",
    "green_half": "green_half",
    "green_two_third": "green_two_third",
    "green_highlight": "green_highlight",
    "arrow_half": "arrow_half",
    "arrow_two_third": "arrow_two_third",
    "big_statement_green": "big_statement_green",
    "big_statement_icon": "big_statement_icon",
}


SEMANTIC_TO_BCG_SLUG = {
    "content": "title-only",
    "green_one_third": "green-one-third",
    "green_left_arrow": "green-left-arrow",
    "green_half": "green-half",
    "green_two_third": "green-two-third",
    "green_highlight": "green-highlight",
    "arrow_half": "arrow-half",
    "arrow_two_third": "arrow-two-third",
    "big_statement_green": "big-statement-green",
    "big_statement_icon": "big-statement-icon",
    "section_divider": "section-header-box",
    "title_slide": "title-slide",
}


_RUNTIME_TO_SEMANTIC = {runtime: semantic for semantic, runtime in SEMANTIC_TO_RUNTIME_LAYOUT.items()}
_BCG_SLUG_TO_SEMANTIC = {slug: semantic for semantic, slug in SEMANTIC_TO_BCG_SLUG.items()}


def _normalize_layout_ref(value):
    """Normalize runtime keys, BCG slugs, layout names, and XML filenames."""
    if not value:
        return ""
    normalized = str(value).strip().lower()
    normalized = normalized.split("/")[-1]
    normalized = re.sub(r"\.xml$", "", normalized)
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    return normalized.strip("_")


def _detail_base_ref(value):
    normalized = _normalize_layout_ref(value)
    if normalized.startswith("d_"):
        return normalized[2:], True
    return normalized, False


def semantic_role_for_layout(layout_ref, theme_config=None):
    """Resolve a layout reference to the canonical semantic role."""
    normalized = _normalize_layout_ref(layout_ref)
    base_ref, _ = _detail_base_ref(normalized)

    if base_ref in LAYOUT_FAMILIES:
        return base_ref
    if base_ref in _RUNTIME_TO_SEMANTIC:
        return _RUNTIME_TO_SEMANTIC[base_ref]
    if base_ref in _BCG_SLUG_TO_SEMANTIC:
        return _BCG_SLUG_TO_SEMANTIC[base_ref]

    if theme_config:
        semantic_layout_map = theme_config.get("semantic_layout_map", {})
        for semantic, mapped in semantic_layout_map.items():
            if base_ref == _normalize_layout_ref(mapped):
                return semantic

        detail_layout_map = theme_config.get("detail_layout_map", {})
        for base_name, mapped in detail_layout_map.items():
            if normalized == _normalize_layout_ref(mapped):
                base_candidate, _ = _detail_base_ref(base_name)
                if base_candidate in LAYOUT_FAMILIES:
                    return base_candidate
                if base_candidate in _RUNTIME_TO_SEMANTIC:
                    return _RUNTIME_TO_SEMANTIC[base_candidate]

        xml_layout_map = theme_config.get("xml_layout_map", {})
        for semantic, mapped in semantic_layout_map.items():
            xml_name = xml_layout_map.get(mapped)
            if xml_name and normalized == _normalize_layout_ref(xml_name):
                return semantic

        for base_name, mapped in detail_layout_map.items():
            xml_name = xml_layout_map.get(mapped)
            if xml_name and normalized == _normalize_layout_ref(xml_name):
                base_candidate, _ = _detail_base_ref(base_name)
                if base_candidate in LAYOUT_FAMILIES:
                    return base_candidate

    return None


def semantic_behavior(layout_ref, theme_config=None):
    """Return the canonical runtime behavior for a layout reference."""
    normalized = _normalize_layout_ref(layout_ref)
    _, detail = _detail_base_ref(normalized)
    role = semantic_role_for_layout(layout_ref, theme_config=theme_config)
    behavior = deepcopy(DEFAULT_BEHAVIOR)
    if role and role in LAYOUT_FAMILIES:
        behavior.update(LAYOUT_FAMILIES[role])

    # Geometry guard: if the resolved role is a statement type but the
    # template's layout_geometry indicates a split-panel structure
    # (accent region + wide content zone), the role was misclassified
    # during ee4p ingestion.  Override to green_left_arrow so body
    # content is allowed on these layouts.
    if behavior.get("statement") and theme_config:
        geom = theme_config.get("layout_geometry", {})
        slug = normalized.replace("_", "-")
        layout_geom = geom.get(slug, {})
        split_zones = layout_geom.get("split_zones")
        content_zone = layout_geom.get("content_zone", {})
        has_split = bool(split_zones) or content_zone.get("layout_class") == "split_panel"
        if has_split:
            role = "green_left_arrow"
            behavior = deepcopy(DEFAULT_BEHAVIOR)
            behavior.update(LAYOUT_FAMILIES.get(role, {}))

    behavior["semantic_role"] = role
    behavior["detail"] = detail
    behavior["layout_ref"] = layout_ref
    return behavior


def derive_pattern_layouts(semantic_layout_map):
    """Map legacy pattern labels to concrete semantic layout choices."""
    content = semantic_layout_map.get("content", "")
    green_third = semantic_layout_map.get("green_one_third", content)
    return {
        "A": content,
        "B": content,
        "C": green_third,
        "D": content,
        "E": content,
        "F": content,
        "G": content,
    }

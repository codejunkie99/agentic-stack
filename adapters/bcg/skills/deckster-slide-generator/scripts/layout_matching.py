"""Semantic layout matching utilities for ingested templates.

This module keeps the legacy matcher for benchmarking, but the public
entrypoints now route through a structural signature matcher that can recover
semantic layouts when template names diverge from the BCG defaults.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from layout_semantics import SEMANTIC_TO_BCG_SLUG


ROLE_ORDER = [
    "title_slide",
    "content",
    "section_divider",
    "disclaimer",
    "end",
    "blank",
    "green_one_third",
    "green_left_arrow",
    "green_half",
    "green_two_third",
    "green_highlight",
    "arrow_half",
    "arrow_two_third",
    "big_statement_green",
    "big_statement_icon",
]

REQUIRED_ROLES = {"title_slide", "content", "section_divider"}
SPLIT_FAMILY_ROLES = {
    "green_one_third",
    "green_left_arrow",
    "green_half",
    "green_two_third",
    "arrow_half",
    "arrow_two_third",
}

SIGNATURE_KEYS = [
    "title_kind",
    "title_zone",
    "title_width_bucket",
    "title_span_bucket",
    "title_align",
    "body_count_bucket",
    "body_layout",
    "has_picture",
    "picture_side",
    "picture_width_bucket",
    "accent_side",
    "accent_width_bucket",
    "accent_geometry",
    "split_title_bucket",
    "split_content_bucket",
    "split_balance",
    "arrow_marker",
    "layout_class",
    "geometry_type",
    "background_role",
    "content_palette_role",
    "shape_density",
]

FEATURE_WEIGHTS = {
    "title_kind": 0.06,
    "title_zone": 0.13,
    "title_width_bucket": 0.08,
    "title_span_bucket": 0.11,
    "title_align": 0.08,
    "body_count_bucket": 0.08,
    "body_layout": 0.11,
    "has_picture": 0.06,
    "picture_side": 0.05,
    "picture_width_bucket": 0.10,
    "accent_side": 0.10,
    "accent_width_bucket": 0.10,
    "accent_geometry": 0.08,
    "split_title_bucket": 0.11,
    "split_content_bucket": 0.10,
    "split_balance": 0.09,
    "arrow_marker": 0.07,
    "layout_class": 0.10,
    "geometry_type": 0.05,
    "background_role": 0.06,
    "content_palette_role": 0.04,
    "shape_density": 0.02,
}

ORDERED_BUCKETS = {
    "title_width_bucket": ["none", "narrow", "medium", "wide"],
    "title_span_bucket": ["none", "xs", "sm", "md", "lg", "xl"],
    "body_count_bucket": ["0", "1", "2", "3+"],
    "accent_width_bucket": ["none", "narrow", "third", "half", "two_third", "full"],
    "picture_width_bucket": ["none", "narrow", "third", "half", "two_third", "full"],
    "split_title_bucket": ["none", "third", "half", "two_third", "full"],
    "split_content_bucket": ["none", "third", "half", "wide", "full"],
    "split_balance": ["none", "content_heavy", "balanced", "title_heavy"],
    "shape_density": ["sparse", "balanced", "dense"],
}

ROLE_NAME_HINTS = {
    "title_slide": (
        ("title slide", 3.0),
        ("cover slide", 2.8),
        ("cover", 1.9),
        ("opening", 1.2),
        ("front page", 1.4),
    ),
    "content": (
        ("title only", 2.8),
        ("title and text", 2.6),
        ("content", 2.0),
        ("key message", 2.4),
        ("overview", 1.2),
        ("body", 0.8),
    ),
    "section_divider": (
        ("section header", 3.0),
        ("section divider", 3.0),
        ("divider", 2.4),
        ("chapter", 1.7),
        ("separator", 1.6),
    ),
    "disclaimer": (
        ("disclaimer", 4.0),
        ("legal", 2.0),
        ("terms", 1.6),
    ),
    "end": (
        ("thank you", 3.3),
        ("ending", 3.0),
        ("end", 2.7),
        ("closing", 1.8),
    ),
    "blank": (
        ("blank", 3.2),
        ("empty", 1.8),
    ),
    "green_one_third": (
        ("one third", 2.8),
        ("one-third", 2.8),
        ("1 3", 1.2),
    ),
    "green_left_arrow": (
        ("left arrow", 3.2),
        ("arrow left", 3.2),
        ("arrow one third", 3.1),
        ("one third arrow", 3.1),
        ("left chevron", 2.2),
    ),
    "green_half": (
        ("green half", 3.0),
        ("split half", 1.6),
        ("half page", 1.4),
        ("half", 1.0),
    ),
    "green_two_third": (
        ("two third", 2.8),
        ("two-third", 2.8),
        ("two thirds", 2.8),
        ("2 3", 1.2),
    ),
    "green_highlight": (
        ("highlight", 3.0),
        ("insight", 1.2),
    ),
    "arrow_half": (
        ("arrow half", 3.2),
        ("half arrow", 2.8),
        ("arrow-half", 3.2),
    ),
    "arrow_two_third": (
        ("arrow two third", 3.1),
        ("two third arrow", 2.8),
        ("arrow-two-third", 3.1),
    ),
    "big_statement_green": (
        ("big statement green", 3.3),
        ("big statement", 2.8),
        ("statement", 1.5),
    ),
    "big_statement_icon": (
        ("big statement icon", 3.5),
        ("statement icon", 3.0),
        ("icon statement", 3.0),
    ),
}

ROLE_NEGATIVE_HINTS = {
    "title_slide": ("divider", "section header", "disclaimer", "end", "blank"),
    "content": ("divider", "section header", "disclaimer", "end", "blank", "statement"),
    "section_divider": ("disclaimer", "title only", "title and text", "end"),
    "disclaimer": ("title only", "content", "divider"),
    "end": ("title only", "content", "divider"),
    "blank": ("title slide", "content", "divider"),
    "green_one_third": ("left arrow", "arrow one third", "one third arrow", "highlight", "statement"),
    "green_left_arrow": ("highlight", "statement"),
    "green_half": ("statement", "divider", "arrow half"),
    "green_two_third": ("statement", "divider", "arrow two third", "two third arrow", "agenda"),
    "green_highlight": ("left arrow", "statement"),
    "arrow_half": ("one third", "two third", "statement"),
    "arrow_two_third": ("one third", "half", "statement"),
    "big_statement_green": ("divider", "content"),
    "big_statement_icon": ("divider", "content"),
}

ROLE_RULE_HINTS = {
    "title_slide": {"t": 0.65, "title and end pages": 0.8},
    "disclaimer": {"t": 0.55, "title and end pages": 0.6},
    "end": {"t": 0.55, "title and end pages": 0.6},
    "content": {"k": 0.55, "key message": 0.65},
    "section_divider": {"t": 0.2, "title and end pages": 0.15},
}

WEAK_LABEL_THRESHOLDS = {
    "title_slide": 2.6,
    "content": 2.4,
    "section_divider": 2.4,
    "disclaimer": 3.0,
    "end": 2.7,
    "blank": 2.8,
    "green_one_third": 2.4,
    "green_left_arrow": 2.8,
    "green_half": 2.4,
    "green_two_third": 2.4,
    "green_highlight": 2.6,
    "arrow_half": 2.8,
    "arrow_two_third": 2.8,
    "big_statement_green": 2.6,
    "big_statement_icon": 3.0,
}


def _normalize_layout_name(value):
    """Normalize layout names across slugs, spaces, punctuation, and prefixes."""
    text = (value or "").strip().lower()
    text = re.sub(r"^client\s+", "", text)
    text = re.sub(r"^d[\.\-_ ]+", "", text)
    text = text.replace("&", " and ")
    text = re.sub(r"[-_./]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_token(value):
    return re.sub(r"[^a-z0-9]+", "", (value or "").strip().lower())


def _tokenize_layout_name(value):
    return {
        token
        for token in re.split(r"[^a-z0-9]+", _normalize_layout_name(value))
        if token
    }


def _hex_to_rgb(value):
    cleaned = (value or "").strip().lstrip("#")
    if len(cleaned) != 6:
        return None
    try:
        return tuple(int(cleaned[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _relative_luminance(rgb):
    def _channel(channel):
        value = channel / 255.0
        return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4

    return 0.2126 * _channel(rgb[0]) + 0.7152 * _channel(rgb[1]) + 0.0722 * _channel(rgb[2])


def _background_role(value):
    rgb = _hex_to_rgb(value)
    if rgb is None:
        return "light"
    return "dark" if _relative_luminance(rgb) < 0.40 else "light"


def _largest_placeholder(placeholders):
    def _area(placeholder):
        bounds = placeholder.get("bounds", {})
        return float(bounds.get("w_pct", 0.0)) * float(bounds.get("h_pct", 0.0))

    return max(placeholders, key=_area, default=None)


def _bucket_title_width(width_pct):
    if width_pct <= 0:
        return "none"
    if width_pct < 35:
        return "narrow"
    if width_pct < 70:
        return "medium"
    return "wide"


def _bucket_title_span(width_pct):
    if width_pct <= 0:
        return "none"
    if width_pct < 24:
        return "xs"
    if width_pct < 33:
        return "sm"
    if width_pct < 46:
        return "md"
    if width_pct < 60:
        return "lg"
    return "xl"


def _bucket_title_align(x_pct, w_pct):
    if w_pct <= 0:
        return "none"
    center = x_pct + (w_pct / 2.0)
    if 38 <= center <= 62:
        return "center"
    return "left" if center < 38 else "right"


def _bucket_body_count(count):
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count == 2:
        return "2"
    return "3+"


def _bucket_accent_width(width_pct):
    if width_pct <= 0:
        return "none"
    if width_pct < 20:
        return "narrow"
    if width_pct < 40:
        return "third"
    if width_pct < 60:
        return "half"
    if width_pct < 80:
        return "two_third"
    return "full"


def _bucket_shape_density(count):
    if count <= 8:
        return "sparse"
    if count <= 24:
        return "balanced"
    return "dense"


def _bucket_split_panel_width(width_pct):
    if width_pct <= 0:
        return "none"
    if width_pct < 30:
        return "third"
    if width_pct < 47:
        return "half"
    if width_pct < 65:
        return "two_third"
    return "full"


def _bucket_split_content_width(width_pct):
    if width_pct <= 0:
        return "none"
    if width_pct < 40:
        return "third"
    if width_pct < 56:
        return "half"
    if width_pct < 75:
        return "wide"
    return "full"


def _bucket_split_balance(left_pct, right_pct):
    if left_pct <= 0 or right_pct <= 0:
        return "none"
    ratio = left_pct / right_pct
    if ratio < 0.60:
        return "content_heavy"
    if ratio > 1.25:
        return "title_heavy"
    return "balanced"


def _dominant_accent(accent_regions):
    def _area(region):
        bounds = region.get("bounds", {})
        return float(bounds.get("w_pct", 0.0)) * float(bounds.get("h_pct", 0.0))

    prominent = [
        region
        for region in accent_regions or []
        if float((region.get("bounds") or {}).get("w_pct", 0.0)) >= 12
        and float((region.get("bounds") or {}).get("h_pct", 0.0)) >= 20
    ]
    candidates = prominent or list(accent_regions or [])
    return max(candidates, key=_area, default=None)


def _accent_side(region):
    if not region:
        return "none"
    bounds = region.get("bounds", {})
    x_pct = float(bounds.get("x_pct", 0.0))
    w_pct = float(bounds.get("w_pct", 0.0))
    center = x_pct + (w_pct / 2.0)
    if w_pct >= 80:
        return "full"
    if 40 <= center <= 60:
        return "center"
    return "left" if center < 50 else "right"


def _accent_geometry(region):
    if not region:
        return "none"
    geometry = _normalize_token(region.get("geometry") or "")
    if not geometry:
        return "none"
    if "chevron" in geometry or "arrow" in geometry or geometry in {"homeplate", "isocelestriangle", "righttriangle"}:
        return "arrow"
    if geometry in {"rect", "roundrect", "diamond"}:
        return "rect"
    if geometry in {"mixed", "custom", "custgeom"}:
        return "custom"
    return "custom"


def _body_layout(placeholders, content_zone):
    body_placeholders = [ph for ph in placeholders if ph.get("type") == "body"]
    if not body_placeholders:
        if content_zone and content_zone.get("content_bounds"):
            return "title_only"
        return "none"
    if len(body_placeholders) >= 2:
        return "multi_column"
    width_pct = float((body_placeholders[0].get("bounds") or {}).get("w_pct", 0.0))
    if width_pct >= 70:
        return "single_wide"
    return "single_narrow"


def _content_palette_role(layout_info):
    content_zone = layout_info.get("content_zone") or {}
    role = content_zone.get("content_palette_role")
    if role:
        return role
    background = layout_info.get("background")
    if background:
        return _background_role(background)
    return "light"


def _layout_shape_count(layout_info):
    shape_summary = layout_info.get("shape_summary") or {}
    if shape_summary.get("non_placeholder_count") is not None:
        return int(shape_summary.get("non_placeholder_count") or 0)
    placeholders = layout_info.get("placeholders") or []
    accents = layout_info.get("accent_regions") or []
    return max(0, len(placeholders) + len(accents))


def _arrow_marker(layout_info):
    arrow_geometries = {"arrow", "chevron", "homeplate", "isocelestriangle", "righttriangle"}

    for region in layout_info.get("accent_regions") or []:
        geometry = _normalize_token(region.get("geometry") or "")
        if geometry in arrow_geometries:
            return "arrow"
        shape_name = _normalize_layout_name(region.get("shapeName") or "")
        if "arrow" in shape_name or "chevron" in shape_name:
            return "arrow"

    shape_summary = layout_info.get("shape_summary") or {}
    for geometry_name in (shape_summary.get("geometry_counts") or {}):
        if _normalize_token(geometry_name) in arrow_geometries:
            return "arrow"

    for entry in shape_summary.get("top_shape_names") or []:
        normalized_name = _normalize_layout_name(entry.get("name") or "")
        if "arrow" in normalized_name or "chevron" in normalized_name:
            return "arrow"

    return "none"


def _matching_layout_rules(layout_name, layout_rules):
    matches = []
    for rule in layout_rules or []:
        pattern = rule.get("pattern")
        if not pattern:
            continue
        try:
            if re.search(pattern, layout_name or "", flags=re.IGNORECASE):
                matches.append(rule)
        except re.error:
            continue
    return matches


def build_layout_signature(layout_name, layout_info, layout_rules=None):
    """Build a stable structural signature for a layout."""
    placeholders = list(layout_info.get("placeholders") or [])
    content_zone = layout_info.get("content_zone") or {}
    title_candidates = [
        placeholder
        for placeholder in placeholders
        if placeholder.get("type") in {"title", "ctrTitle"}
    ]
    title = _largest_placeholder(title_candidates)
    body_placeholders = [ph for ph in placeholders if ph.get("type") == "body"]
    picture_placeholders = [ph for ph in placeholders if ph.get("type") == "pic"]
    picture = _largest_placeholder(picture_placeholders)
    accent = _dominant_accent(layout_info.get("accent_regions") or [])
    matched_rules = _matching_layout_rules(layout_name, layout_rules)

    title_bounds = (title or {}).get("bounds") or {}
    title_x_pct = float(title_bounds.get("x_pct", 0.0))
    title_y_pct = float(title_bounds.get("y_pct", 0.0))
    title_w_pct = float(title_bounds.get("w_pct", 0.0))
    picture_bounds = (picture or {}).get("bounds") or {}
    picture_w_pct = float(picture_bounds.get("w_pct", 0.0))
    split_zones = (content_zone.get("split_zones") or {}) if content_zone else {}
    title_side = content_zone.get("title_side") or ("left" if title_x_pct < 40 else "right")
    if title_side == "right":
        split_title_w_pct = float(split_zones.get("right_w_pct", 0.0))
        split_content_w_pct = float(split_zones.get("left_w_pct", 0.0))
    else:
        split_title_w_pct = float(split_zones.get("left_w_pct", 0.0))
        split_content_w_pct = float(split_zones.get("right_w_pct", 0.0))
    if split_title_w_pct <= 0:
        split_title_w_pct = title_w_pct
    if split_content_w_pct <= 0 and picture_w_pct > 0:
        split_content_w_pct = picture_w_pct
    if (
        split_content_w_pct <= 0
        and content_zone.get("layout_class") == "split_panel"
        and (content_zone.get("content_bounds") or {}).get("w_pct")
    ):
        split_content_w_pct = float((content_zone.get("content_bounds") or {}).get("w_pct", 0.0))

    signature = {
        "layout_name": layout_name,
        "normalized_name": _normalize_layout_name(layout_name),
        "name_tokens": sorted(_tokenize_layout_name(layout_name)),
        "title_kind": "ctrTitle" if any(ph.get("type") == "ctrTitle" for ph in title_candidates) else ("title" if title else "none"),
        "title_zone": content_zone.get("title_zone") or ("top" if title_y_pct < 20 else "mid" if title_y_pct < 50 else "bottom"),
        "title_width_bucket": content_zone.get("title_width") or _bucket_title_width(title_w_pct),
        "title_span_bucket": _bucket_title_span(title_w_pct),
        "title_align": _bucket_title_align(title_x_pct, title_w_pct),
        "title_centered": _bucket_title_align(title_x_pct, title_w_pct) == "center",
        "title_y_pct": round(title_y_pct, 2),
        "title_w_pct": round(title_w_pct, 2),
        "body_count": len(body_placeholders),
        "body_count_bucket": _bucket_body_count(len(body_placeholders)),
        "body_layout": _body_layout(placeholders, content_zone),
        "has_subtitle": any(ph.get("type") == "subTitle" for ph in placeholders),
        "has_picture": bool(content_zone.get("has_picture") or picture_placeholders),
        "picture_side": content_zone.get("picture_side") or ("left" if picture_placeholders and float((picture_placeholders[0].get("bounds") or {}).get("x_pct", 0.0)) < 40 else "right" if picture_placeholders else "none"),
        "picture_width_bucket": _bucket_accent_width(picture_w_pct),
        "title_picture_overlap": bool(content_zone.get("title_picture_overlap")),
        "accent_side": _accent_side(accent),
        "accent_width_bucket": _bucket_accent_width(float(((accent or {}).get("bounds") or {}).get("w_pct", 0.0))),
        "accent_geometry": _accent_geometry(accent),
        "split_title_bucket": _bucket_split_panel_width(split_title_w_pct),
        "split_content_bucket": _bucket_split_content_width(split_content_w_pct),
        "split_balance": _bucket_split_balance(split_title_w_pct, split_content_w_pct),
        "arrow_marker": _arrow_marker(layout_info),
        "accent_count_bucket": _bucket_body_count(len(layout_info.get("accent_regions") or [])),
        "layout_class": content_zone.get("layout_class") or layout_info.get("geometry_type") or "unknown",
        "geometry_type": layout_info.get("geometry_type") or "unknown",
        "background_role": _background_role(layout_info.get("background")),
        "content_palette_role": _content_palette_role(layout_info),
        "shape_density": _bucket_shape_density(_layout_shape_count(layout_info)),
        "detail_hint": _normalize_layout_name(layout_name).startswith("d "),
        "rule_ids": sorted({str(rule.get("id", "")).strip().lower() for rule in matched_rules if rule.get("id")}),
        "rule_names": sorted({_normalize_layout_name(rule.get("name")) for rule in matched_rules if rule.get("name")}),
    }
    return signature


def _score_layout_match(client_geom, bcg_reference_geom):
    """Score 0.0-1.0 how well a client layout matches expected geometry."""
    c = client_geom.get("content_zone")
    b = bcg_reference_geom.get("content_zone")
    if not c or not b:
        return 0.3

    score = 0.0
    score += 0.25 * (1.0 if c.get("title_side") == b.get("title_side") else 0.0)
    score += 0.20 * (1.0 if c.get("title_zone") == b.get("title_zone") else 0.3)
    score += 0.15 * (1.0 if c.get("title_width") == b.get("title_width") else 0.2)
    score += 0.15 * (1.0 if c.get("layout_class") == b.get("layout_class") else 0.2)

    if b.get("has_picture"):
        if c.get("has_picture") and c.get("picture_side") == b.get("picture_side"):
            score += 0.25 if not c.get("title_picture_overlap") else 0.15
        elif c.get("has_picture"):
            score += 0.15 if not c.get("title_picture_overlap") else 0.10
    else:
        score += 0.25 if not c.get("has_picture") else 0.15

    return score


def _legacy_derive_semantic_layout_map(layout_map):
    """Legacy exact-name matcher retained for benchmarking."""
    semantic = {}
    normalized_to_orig = {}
    for std_name, orig_name in layout_map.items():
        normalized_to_orig[_normalize_layout_name(std_name)] = orig_name

    def find_by_prefix(prefix):
        for std_name, orig_name in layout_map.items():
            if _normalize_layout_name(std_name).startswith(prefix):
                return orig_name
        return None

    def find_by_candidates(*candidates):
        for candidate in candidates:
            normalized = _normalize_layout_name(candidate)
            if normalized in normalized_to_orig:
                return normalized_to_orig[normalized]
        return None

    result = find_by_candidates("title slide", "title slide_1")
    if result:
        semantic["title_slide"] = result
    if "title_slide" not in semantic:
        result = find_by_prefix("title slide")
        if result:
            semantic["title_slide"] = result

    result = find_by_candidates("title only", "title-only")
    if result:
        semantic["content"] = result

    result = find_by_candidates("section header box", "section header line", "section-header-box", "section-header-line")
    if result:
        semantic["section_divider"] = result

    result = find_by_candidates("disclaimer")
    if result:
        semantic["disclaimer"] = result

    result = find_by_candidates("end")
    if result:
        semantic["end"] = result
    if "end" not in semantic:
        result = find_by_prefix("end ")
        if result:
            semantic["end"] = result

    result = find_by_candidates("blank")
    if result:
        semantic["blank"] = result

    for key, candidates in {
        "green_one_third": ["green one third", "green-one-third"],
        "arrow_two_third": ["arrow two third", "arrow-two-third"],
        "green_left_arrow": ["green left arrow", "green-left-arrow", "left arrow", "left-arrow"],
        "green_half": ["green half", "green-half"],
        "green_two_third": ["green two third", "green-two-third"],
        "green_highlight": ["green highlight", "green-highlight"],
        "arrow_half": ["arrow half", "arrow-half"],
        "big_statement_green": ["big statement green", "big-statement-green"],
        "big_statement_icon": ["big statement icon", "big-statement-icon"],
    }.items():
        result = find_by_candidates(*candidates)
        if result:
            semantic[key] = result

    return semantic


def _legacy_merge_semantic_with_geometry(semantic_map, layout_styles, xml_layout_map=None, bcg_reference_styles=None):
    """Legacy geometry-gap filler retained for benchmarking."""
    semantic_map = dict(semantic_map)
    geometry_to_semantic = {
        "title_slide": "title_slide",
        "full_content": "content",
        "title_only": "content",
        "blank": "blank",
        "accent_one_third": "green_one_third",
        "accent_half": "green_half",
        "accent_two_third": "green_two_third",
    }

    geometry_lookup = {}
    for _, info in layout_styles.items():
        gtype = info.get("geometry_type", "")
        if gtype and gtype not in geometry_lookup:
            geometry_lookup[gtype] = info.get("layout_name", "")

    for gtype, sem_key in geometry_to_semantic.items():
        if sem_key not in semantic_map and gtype in geometry_lookup:
            semantic_map[sem_key] = geometry_lookup[gtype]

    if xml_layout_map:
        all_names = list(xml_layout_map.keys())

        if "content" not in semantic_map:
            title_only_candidates = [
                name
                for name in all_names
                if "title only" in name.lower() and "d." not in name.lower()
            ]
            if title_only_candidates:
                best = title_only_candidates[0]
                for candidate in title_only_candidates:
                    lowered = candidate.lower()
                    if "white" in lowered:
                        best = candidate
                        break
                    if not any(color in lowered for color in ("blue", "green", "red", "dark")):
                        best = candidate
                semantic_map["content"] = best
            if "content" not in semantic_map:
                for name in all_names:
                    lowered = name.lower()
                    if "content" in lowered and "two content" not in lowered and "d." not in lowered:
                        semantic_map["content"] = name
                        break

        if "section_divider" not in semantic_map:
            for name in all_names:
                lowered = name.lower()
                if "section header" in lowered and "number" not in lowered and "d." not in lowered:
                    semantic_map["section_divider"] = name
                    break

        if "disclaimer" not in semantic_map:
            for name in all_names:
                if "disclaimer" in name.lower():
                    semantic_map["disclaimer"] = name
                    break
            if "disclaimer" not in semantic_map and "blank" in semantic_map:
                semantic_map["disclaimer"] = semantic_map["blank"]

        if "title_slide" not in semantic_map:
            for name in all_names:
                lowered = name.lower()
                if "title slide" in lowered and "only" not in lowered:
                    semantic_map["title_slide"] = name
                    break

        if "end" not in semantic_map:
            for name in all_names:
                lowered = name.lower()
                if lowered == "end" or "ending" in lowered:
                    semantic_map["end"] = name
                    break

        if "blank" not in semantic_map:
            for name in all_names:
                if "blank" in name.lower():
                    semantic_map["blank"] = name
                    break

    if "content" not in semantic_map:
        for _, info in layout_styles.items():
            phs = info.get("placeholders", [])
            ph_types = [placeholder["type"] for placeholder in phs]
            has_body = "body" in ph_types
            has_title = any(kind in ("title", "ctrTitle") for kind in ph_types)
            accents = info.get("accent_regions", [])
            name = info.get("layout_name", "")
            if not has_body and accents and not has_title:
                semantic_map["content"] = name
                break

    if "section_divider" not in semantic_map:
        for _, info in layout_styles.items():
            phs = info.get("placeholders", [])
            for placeholder in phs:
                if placeholder["type"] in ("title", "ctrTitle") and placeholder["bounds"]["y_pct"] > 30:
                    name = info.get("layout_name", "")
                    lowered = name.lower()
                    if "title slide" not in lowered and "end" not in lowered and "quotation" not in lowered:
                        semantic_map["section_divider"] = name
                        break
            if "section_divider" in semantic_map:
                break

    if "title_slide" in semantic_map:
        matched_title_name = semantic_map["title_slide"]
        is_valid_title = False
        for _, info in layout_styles.items():
            if info.get("layout_name") == matched_title_name:
                has_accent = bool(info.get("accent_regions"))
                for placeholder in info.get("placeholders", []):
                    if placeholder["type"] == "ctrTitle":
                        is_valid_title = True
                        break
                    if placeholder["type"] == "title" and placeholder["bounds"].get("y_pct", 0) > 20 and not has_accent:
                        is_valid_title = True
                        break
                break
        if not is_valid_title:
            best_candidate = None
            best_score = 0
            for _, info in layout_styles.items():
                has_accent = bool(info.get("accent_regions"))
                if has_accent:
                    continue
                for placeholder in info.get("placeholders", []):
                    candidate = info.get("layout_name", "")
                    lowered = candidate.lower()
                    score = 0
                    if placeholder["type"] == "ctrTitle":
                        score = 3
                    elif placeholder["type"] == "title" and placeholder["bounds"].get("y_pct", 0) > 20:
                        score = 1
                    if "title slide" in lowered:
                        score += 2
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
            if best_candidate:
                semantic_map["title_slide"] = best_candidate

    if bcg_reference_styles:
        prefer_light_bg = {"content"}
        structural_keys = {"title_slide", "disclaimer", "end", "section_divider", "blank"}
        for sem_key, bcg_slug in SEMANTIC_TO_BCG_SLUG.items():
            if sem_key in structural_keys:
                continue
            bcg_ref = bcg_reference_styles.get(bcg_slug)
            if not bcg_ref:
                continue

            if sem_key in semantic_map:
                matched_name = semantic_map[sem_key]
                matched_geom = None
                for _, info in layout_styles.items():
                    if info.get("layout_name") == matched_name:
                        matched_geom = info
                        break
                if matched_geom:
                    score = _score_layout_match(matched_geom, bcg_ref)
                    if score >= 0.5:
                        continue
                else:
                    score = 0.0
            else:
                matched_name = None
                score = 0.0

            best_score, best_name = score, matched_name
            for _, info in layout_styles.items():
                current_score = _score_layout_match(info, bcg_ref)
                if sem_key in prefer_light_bg:
                    cz = info.get("content_zone") or {}
                    if cz.get("content_palette_role") == "dark":
                        current_score *= 0.5
                if current_score > best_score:
                    best_score = current_score
                    best_name = info.get("layout_name", "")

            if best_name and best_name != matched_name:
                semantic_map[sem_key] = best_name

    return semantic_map


def legacy_resolve_semantic_layout_map(layout_map, layout_styles, xml_layout_map=None, bcg_reference_styles=None):
    """Public legacy baseline used by corpus benchmarks."""
    seeded = _legacy_derive_semantic_layout_map(layout_map or {})
    return _legacy_merge_semantic_with_geometry(
        seeded,
        layout_styles or {},
        xml_layout_map=xml_layout_map,
        bcg_reference_styles=bcg_reference_styles,
    )


@lru_cache(maxsize=1)
def _load_corpus_archetypes():
    path = Path(__file__).resolve().parents[1] / "styles" / "_semantic_archetypes.json"
    if not path.exists():
        return {}
    try:
        with open(path) as handle:
            return json.load(handle)
    except (json.JSONDecodeError, OSError):
        return {}


def _reference_signature(role, bcg_reference_styles):
    if not bcg_reference_styles:
        return None
    bcg_slug = SEMANTIC_TO_BCG_SLUG.get(role)
    if not bcg_slug:
        return None
    info = bcg_reference_styles.get(bcg_slug)
    if not info:
        return None
    return build_layout_signature(info.get("layout_name", bcg_slug), info)


def _fingerprint_signature(signature):
    return {key: signature.get(key) for key in SIGNATURE_KEYS}


def _feature_similarity(key, candidate_value, reference_value):
    if candidate_value == reference_value:
        return 1.0
    if candidate_value in (None, "", False) or reference_value in (None, "", False):
        return 0.0
    if key in ORDERED_BUCKETS:
        ordering = ORDERED_BUCKETS[key]
        if candidate_value in ordering and reference_value in ordering:
            distance = abs(ordering.index(candidate_value) - ordering.index(reference_value))
            return max(0.0, 1.0 - (0.35 * distance))
    if key == "body_layout":
        broad_groups = (
            {"title_only", "single_wide"},
            {"single_narrow", "multi_column"},
        )
        for group in broad_groups:
            if candidate_value in group and reference_value in group:
                return 0.55
    if key == "accent_geometry":
        if candidate_value in {"arrow", "custom"} and reference_value in {"arrow", "custom"}:
            return 0.60
        if "none" not in {candidate_value, reference_value}:
            return 0.35
    if key == "split_balance":
        if candidate_value in {"content_heavy", "balanced"} and reference_value in {"content_heavy", "balanced"}:
            return 0.55
        if candidate_value in {"title_heavy", "balanced"} and reference_value in {"title_heavy", "balanced"}:
            return 0.55
    if key == "title_align" and "center" in {candidate_value, reference_value}:
        return 0.40
    if key in {"layout_class", "geometry_type"}:
        if candidate_value in {"statement", "title_slide"} and reference_value in {"statement", "title_slide"}:
            return 0.55
        if candidate_value in {"split_panel", "framing_split", "image_led", "image_supported"} and reference_value in {"split_panel", "framing_split", "image_led", "image_supported"}:
            return 0.50
    return 0.0


def _score_signature_similarity(candidate_signature, reference_signature):
    if not reference_signature:
        return 0.0
    total = 0.0
    matched = 0.0
    for key, weight in FEATURE_WEIGHTS.items():
        if reference_signature.get(key) in (None, ""):
            continue
        total += weight
        matched += weight * _feature_similarity(
            key,
            candidate_signature.get(key),
            reference_signature.get(key),
        )
    if total <= 0:
        return 0.0
    return matched / total


def _score_archetypes(role, candidate_signature, archetypes):
    role_entry = ((archetypes or {}).get("roles") or {}).get(role) or {}
    fingerprints = role_entry.get("fingerprints") or []
    best = 0.0
    for fingerprint in fingerprints:
        feature_map = fingerprint.get("features") or {}
        similarity = _score_signature_similarity(candidate_signature, feature_map)
        sample_count = float(fingerprint.get("count", 0) or 0)
        popularity_bonus = min(sample_count, 100.0) / 500.0
        best = max(best, min(1.0, similarity + popularity_bonus))
    return best


def _lexical_score(role, candidate_signature):
    normalized_name = candidate_signature.get("normalized_name", "")
    score = 0.0
    for phrase, weight in ROLE_NAME_HINTS.get(role, ()):
        if phrase in normalized_name:
            score += weight
    for phrase in ROLE_NEGATIVE_HINTS.get(role, ()):
        if phrase in normalized_name:
            score -= 1.2
    return score


def _rule_score(role, candidate_signature):
    score = 0.0
    matched_rule_ids = {rule_id for rule_id in candidate_signature.get("rule_ids", []) if rule_id}
    matched_rule_names = {name for name in candidate_signature.get("rule_names", []) if name}
    for hint, weight in ROLE_RULE_HINTS.get(role, {}).items():
        normalized_hint = _normalize_layout_name(hint)
        if normalized_hint in matched_rule_ids or normalized_hint in matched_rule_names:
            score += weight
    return score


def _constraint_penalty(role, signature):
    penalty = 0.0

    body_count = int(signature.get("body_count", 0) or 0)
    title_kind = signature.get("title_kind")
    accent_side = signature.get("accent_side")
    accent_width_bucket = signature.get("accent_width_bucket")
    accent_geometry = signature.get("accent_geometry")
    layout_class = signature.get("layout_class")
    title_zone = signature.get("title_zone")
    body_layout = signature.get("body_layout")
    title_span_bucket = signature.get("title_span_bucket")
    has_picture = bool(signature.get("has_picture"))
    picture_width_bucket = signature.get("picture_width_bucket")
    split_title_bucket = signature.get("split_title_bucket")
    split_content_bucket = signature.get("split_content_bucket")
    split_balance = signature.get("split_balance")
    arrow_marker = signature.get("arrow_marker")

    if role in SPLIT_FAMILY_ROLES and title_kind == "none":
        penalty -= 2.40

    if role == "title_slide":
        if title_zone == "top":
            penalty -= 0.35
        if body_count > 2:
            penalty -= 0.60
        if accent_side in {"left", "right"} and body_layout == "multi_column":
            penalty -= 0.85
    elif role == "content":
        if title_zone != "top":
            penalty -= 0.90
        if layout_class == "statement":
            penalty -= 1.20
        if body_layout == "none":
            penalty -= 0.70
    elif role == "section_divider":
        if body_count > 0:
            penalty -= 1.20
        if title_zone == "top":
            penalty -= 0.40
    elif role == "disclaimer":
        if body_count > 1:
            penalty -= 0.60
    elif role == "end":
        if body_count > 1:
            penalty -= 0.60
    elif role == "blank":
        if signature.get("title_kind") != "none":
            penalty -= 1.10
        if body_count > 0:
            penalty -= 1.10
    elif role == "green_one_third":
        if title_zone != "mid":
            penalty -= 1.40
        if layout_class != "split_panel":
            penalty -= 1.80
        if has_picture:
            penalty -= 1.60
        if split_balance not in {"content_heavy", "balanced"}:
            penalty -= 0.90
        if split_title_bucket not in {"third", "half"}:
            penalty -= 0.70
        if title_span_bucket not in {"xs", "sm", "md"}:
            penalty -= 0.60
        if arrow_marker == "arrow" or accent_geometry == "arrow":
            penalty -= 0.85
    elif role == "green_left_arrow":
        if title_zone != "mid":
            penalty -= 1.40
        if layout_class != "split_panel":
            penalty -= 1.80
        if has_picture:
            penalty -= 1.40
        if split_balance != "content_heavy":
            penalty -= 0.85
        if split_title_bucket not in {"third", "half"}:
            penalty -= 0.60
        if title_span_bucket not in {"xs", "sm"}:
            penalty -= 0.70
        if arrow_marker != "arrow" and accent_geometry != "arrow":
            penalty -= 1.55
    elif role == "green_half":
        if title_zone != "mid":
            penalty -= 1.55
        if layout_class != "split_panel":
            penalty -= 1.85
        if not has_picture:
            penalty -= 2.30
        if picture_width_bucket not in {"half", "two_third"}:
            penalty -= 1.10
        if split_balance != "balanced":
            penalty -= 0.90
        if split_title_bucket not in {"half"}:
            penalty -= 0.75
        if title_span_bucket not in {"sm", "md"}:
            penalty -= 0.70
        if arrow_marker == "arrow" or accent_geometry == "arrow":
            penalty -= 0.55
    elif role == "green_two_third":
        if title_zone != "mid":
            penalty -= 1.55
        if layout_class != "split_panel":
            penalty -= 1.85
        if not has_picture:
            penalty -= 2.30
        if picture_width_bucket not in {"third", "narrow"}:
            penalty -= 1.15
        if split_balance != "title_heavy":
            penalty -= 1.00
        if split_title_bucket not in {"two_third", "full"}:
            penalty -= 0.85
        if split_content_bucket not in {"third", "half"}:
            penalty -= 0.60
        if title_span_bucket not in {"lg", "xl"}:
            penalty -= 0.90
        if arrow_marker == "arrow" or accent_geometry == "arrow":
            penalty -= 0.55
    elif role == "green_highlight":
        if accent_side == "none":
            penalty -= 0.90
        if accent_geometry == "arrow":
            penalty -= 0.35
    elif role == "arrow_half":
        if title_zone != "top":
            penalty -= 1.35
        if layout_class != "full_page":
            penalty -= 1.55
        if has_picture:
            penalty -= 1.20
        if title_span_bucket not in {"sm", "md"}:
            penalty -= 0.75
        if split_title_bucket not in {"half", "two_third", "none"}:
            penalty -= 0.45
        if split_balance == "title_heavy":
            penalty -= 0.45
        if arrow_marker != "arrow" and accent_geometry != "arrow":
            penalty -= 1.55
    elif role == "arrow_two_third":
        if title_zone != "top":
            penalty -= 1.35
        if layout_class != "full_page":
            penalty -= 1.55
        if has_picture:
            penalty -= 1.20
        if title_span_bucket not in {"lg", "xl"}:
            penalty -= 0.85
        if split_title_bucket not in {"two_third", "full", "none"}:
            penalty -= 0.45
        if split_balance == "content_heavy":
            penalty -= 0.45
        if arrow_marker != "arrow" and accent_geometry != "arrow":
            penalty -= 1.55
    elif role in {"big_statement_green", "big_statement_icon"}:
        if layout_class != "statement":
            penalty -= 1.00
        if body_count > 0:
            penalty -= 1.00
        if title_zone == "top":
            penalty -= 0.45
        if role == "big_statement_icon" and accent_geometry == "none":
            penalty -= 0.25

    return penalty


def _allow_legacy_seed_fallback(role, signature):
    if not signature:
        return True
    if role in SPLIT_FAMILY_ROLES and _constraint_penalty(role, signature) <= -3.25:
        return False
    return True


def _seed_bonus(role, layout_name, legacy_seed_map):
    return 0.55 if legacy_seed_map.get(role) == layout_name else 0.0


def _score_role_candidate(
    role,
    layout_name,
    signature,
    legacy_seed_map,
    reference_signatures,
    archetypes,
):
    lexical = _lexical_score(role, signature)
    rules = _rule_score(role, signature)
    reference = _score_signature_similarity(signature, reference_signatures.get(role))
    archetype = _score_archetypes(role, signature, archetypes)
    seed = _seed_bonus(role, layout_name, legacy_seed_map)
    penalties = _constraint_penalty(role, signature)

    total = (
        lexical
        + rules
        + (1.50 * reference)
        + (1.75 * archetype)
        + seed
        + penalties
    )
    return {
        "layout_name": layout_name,
        "score": round(total, 4),
        "lexical": round(lexical, 4),
        "rules": round(rules, 4),
        "reference": round(reference, 4),
        "archetype": round(archetype, 4),
        "seed": round(seed, 4),
        "penalties": round(penalties, 4),
        "signature": _fingerprint_signature(signature),
    }


def _candidate_threshold(role):
    if role in REQUIRED_ROLES:
        return 0.45
    if role in {"disclaimer", "end", "blank"}:
        return 0.60
    return 0.55


def _build_signatures(layout_styles, layout_rules=None):
    return {
        info.get("layout_name"): build_layout_signature(info.get("layout_name"), info, layout_rules=layout_rules)
        for info in (layout_styles or {}).values()
        if info.get("layout_name")
    }


def resolve_semantic_layout_map(
    layout_map,
    layout_styles,
    xml_layout_map=None,
    layout_rules=None,
    bcg_reference_styles=None,
    return_debug=False,
):
    """Resolve semantic layouts using lexical hints plus structural signatures."""
    if not layout_styles:
        result = _legacy_derive_semantic_layout_map(layout_map or {})
        return (result, {"matcher_version": "legacy_only"}) if return_debug else result

    archetypes = _load_corpus_archetypes()
    legacy_seed_map = legacy_resolve_semantic_layout_map(
        layout_map or {},
        layout_styles,
        xml_layout_map=xml_layout_map,
        bcg_reference_styles=bcg_reference_styles,
    )
    signatures = _build_signatures(layout_styles, layout_rules=layout_rules)
    reference_signatures = {
        role: _reference_signature(role, bcg_reference_styles or {})
        for role in ROLE_ORDER
    }

    candidate_map = {}
    for role in ROLE_ORDER:
        candidates = [
            _score_role_candidate(
                role,
                layout_name,
                signature,
                legacy_seed_map,
                reference_signatures,
                archetypes,
            )
            for layout_name, signature in signatures.items()
        ]
        candidates.sort(key=lambda item: item["score"], reverse=True)
        candidate_map[role] = candidates

    resolved = {}
    used_layouts = set()
    for role in ROLE_ORDER:
        chosen = None
        threshold = _candidate_threshold(role)
        for candidate in candidate_map[role]:
            if candidate["score"] < threshold:
                continue
            if candidate["layout_name"] in used_layouts:
                continue
            chosen = candidate
            break
        if chosen is None and role in REQUIRED_ROLES and candidate_map[role]:
            for candidate in candidate_map[role]:
                if candidate["layout_name"] not in used_layouts:
                    chosen = candidate
                    break
        if chosen is not None:
            resolved[role] = chosen["layout_name"]
            used_layouts.add(chosen["layout_name"])

    for role, layout_name in legacy_seed_map.items():
        if role in resolved:
            continue
        if layout_name in used_layouts and role not in {"disclaimer", "end"}:
            continue
        if not _allow_legacy_seed_fallback(role, signatures.get(layout_name)):
            continue
        resolved[role] = layout_name
        used_layouts.add(layout_name)

    debug = {
        "matcher_version": "signature_v2",
        "used_corpus_archetypes": bool((archetypes or {}).get("roles")),
        "role_candidates": {
            role: candidates[:3]
            for role, candidates in candidate_map.items()
        },
        "resolved": resolved,
    }
    return (resolved, debug) if return_debug else resolved


def derive_semantic_layout_map(layout_map):
    """Compatibility wrapper returning the lexical seed map."""
    return _legacy_derive_semantic_layout_map(layout_map)


def merge_semantic_with_geometry(semantic_map, layout_styles, xml_layout_map=None, bcg_reference_styles=None):
    """Compatibility wrapper returning the new structural resolution."""
    layout_map = {name: name for name in (xml_layout_map or {})}
    layout_map.update({info.get("layout_name", ""): info.get("layout_name", "") for info in (layout_styles or {}).values()})
    resolved = resolve_semantic_layout_map(
        layout_map,
        layout_styles,
        xml_layout_map=xml_layout_map,
        bcg_reference_styles=bcg_reference_styles,
    )
    if semantic_map:
        merged = dict(semantic_map)
        merged.update(resolved)
        return merged
    return resolved


def weak_label_role_for_layout(layout_name, signature):
    """Return a strong corpus label for a layout when the name is unambiguous."""
    del layout_name
    best_role = None
    best_score = float("-inf")
    for role in ROLE_ORDER:
        lexical = _lexical_score(role, signature)
        penalty = _constraint_penalty(role, signature)
        if lexical >= WEAK_LABEL_THRESHOLDS.get(role, 2.8) and penalty > -0.8:
            score = lexical + penalty
            if score > best_score:
                best_score = score
                best_role = role
    return best_role

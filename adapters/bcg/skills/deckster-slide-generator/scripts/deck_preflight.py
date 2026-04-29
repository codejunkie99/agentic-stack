#!/usr/bin/env python3
"""Deck-level preflight for titles, layouts, patterns, and icon resolution."""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from bcg_template import BCGDeck, content_bounds
from layout_semantics import semantic_behavior, semantic_role_for_layout
from pattern_variants import preflight_pattern
from template_registry import get_template


STRUCTURAL_LAYOUT_KEYS = {
    "title_slide": "title",
    "section_divider": "section_header_box",
    "disclaimer": "disclaimer",
    "end": "end",
    "blank": "blank",
}

PATTERN_LAYOUT_RULES = {
    ("split_panel", "green_one_third"): {"green_one_third"},
    ("split_panel", "green_left_arrow"): {"green_left_arrow"},
    ("split_panel", "decision_cards"): {"green_left_arrow"},
    ("split_panel", "green_highlight_quote"): {"green_highlight"},
    ("split_panel", "green_highlight_insights"): {"green_highlight"},
    ("before_after", "split_cards"): {"arrow_half", "green_arrow_half"},
}

ICON_QUERY_ALIASES = {
    "trendup": "Increase_chart_Trending_Up_Line",
    "costs": "Cash_balance",
    "funding": "Cash_growth",
    "it": "Technology",
    "technology": "Technology",
    "legal": "Contract_1",
    "data": "Data_analytics",
    "decision": "Choose_direction",
    "digital": "Digital_transformation",
    "innovation": "Lightbulb_idea",
    "people": "People_group",
    "security": "Shield_protection",
    "growth": "Growth_chart",
    "strategy": "Chess_strategy",
    "cloud": "Cloud_computing",
    "ai": "Artificial_intelligence",
    "sustainability": "Leaf_sustainability",
    "global": "Globe_world",
    "team": "Team_collaboration",
    "process": "Gear_process",
    "finance": "Cash_balance",
    "partnership": "Handshake",
    "target": "Target",
    "alert": "Alert_warning",
    "risk": "Alert_warning",
    "mobile": "Smart_Phone_1",
    "approval": "Checkmark_circle",
}


def _issue(slide_number, severity, code, message):
    return {
        "slide": slide_number,
        "severity": severity,
        "code": code,
        "message": message,
    }


def _detail_variant(layout_key, theme_config):
    if not layout_key or str(layout_key).startswith("d_"):
        return layout_key
    candidate = f"d_{layout_key}"
    if semantic_role_for_layout(candidate, theme_config=theme_config):
        return candidate
    return layout_key


def _resolve_layout_key(kind, layout, detail, theme_config):
    if kind in STRUCTURAL_LAYOUT_KEYS:
        base = STRUCTURAL_LAYOUT_KEYS[kind]
        return _detail_variant(base, theme_config) if detail else base
    layout = layout or "title_only"
    return _detail_variant(layout, theme_config) if detail else layout


def _icon_type_for_slide(deck, slide_spec):
    if slide_spec.get("icon_type") in {"icon", "bug"}:
        return slide_spec["icon_type"]
    line_count = slide_spec.get("icon_line_count")
    if isinstance(line_count, int):
        return deck.resolve_icon_type(line_count)
    return "icon"


def _resolve_icon_query(deck, query, icon_type):
    candidate = ICON_QUERY_ALIASES.get(str(query or "").strip().lower().replace(" ", ""), query)
    return deck.resolve_icon(candidate, icon_type=icon_type)


def _resolve_icons_in_payload(deck, payload, icon_type, changes, slide_number, issues):
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == "icon" and isinstance(value, str):
                try:
                    resolved = _resolve_icon_query(deck, value, icon_type)
                except ValueError as exc:
                    issues.append(_issue(slide_number, "ERROR", "icon_not_found", str(exc)))
                    continue
                if resolved != value:
                    changes.append({
                        "slide": slide_number,
                        "field": "icon",
                        "from": value,
                        "to": resolved,
                    })
                    payload[key] = resolved
            else:
                _resolve_icons_in_payload(deck, value, icon_type, changes, slide_number, issues)
    elif isinstance(payload, list):
        for item in payload:
            _resolve_icons_in_payload(deck, item, icon_type, changes, slide_number, issues)


def _load_theme_config(theme_config=None):
    if theme_config is not None:
        return theme_config
    return get_template(name="bcg_default")


def preflight_slide(slide, slide_number=1, theme_config=None, resolve_icons=True):
    """Validate and normalize a single slide spec in isolation."""
    theme_config = _load_theme_config(theme_config)
    deck = BCGDeck(theme_config=theme_config, unpack_template=False)
    normalized = copy.deepcopy(dict(slide))
    issues = []
    changes = []

    try:
        kind = normalized.get("kind", "content")
        detail = bool(normalized.get("detail", kind == "content"))
        layout = normalized.get("layout")
        layout_key = _resolve_layout_key(kind, layout, detail, theme_config)

        normalized["kind"] = kind
        normalized["detail"] = detail
        normalized["layout_key"] = layout_key

        behavior = semantic_behavior(layout_key, theme_config=theme_config)
        role = behavior.get("semantic_role") or layout_key
        normalized["semantic_role"] = role

        title = normalized.get("title", "")
        try:
            normalized["title"] = deck._validate_title(title, layout_key)
        except ValueError as exc:
            issues.append(_issue(slide_number, "ERROR", "title_invalid", str(exc)))

        normalized["bounds"] = dict(content_bounds(layout_key))

        pattern = normalized.get("pattern")
        if pattern:
            pattern_name = pattern.get("name")
            variant = pattern.get("variant")
            data = copy.deepcopy(pattern.get("data") or {})
            icon_type = _icon_type_for_slide(deck, normalized)

            if resolve_icons:
                _resolve_icons_in_payload(deck, data, icon_type, changes, slide_number, issues)

            allowed_roles = PATTERN_LAYOUT_RULES.get((pattern_name, variant))
            if allowed_roles and role not in allowed_roles:
                allowed = ", ".join(sorted(allowed_roles))
                issues.append(_issue(
                    slide_number,
                    "ERROR",
                    "layout_pattern_mismatch",
                    f"{pattern_name}/{variant} expects {allowed}, but the slide uses {role}.",
                ))

            try:
                preflight = preflight_pattern(
                    deck,
                    pattern_name,
                    variant=variant,
                    data=data,
                    bounds=normalized["bounds"],
                )
                pattern["variant"] = preflight["variant"]
                pattern["data"] = preflight["data"]
            except Exception as exc:
                issues.append(_issue(slide_number, "ERROR", "pattern_invalid", str(exc)))

            normalized["pattern"] = pattern

        if behavior.get("narrow_panel") and len(normalized.get("title", "")) >= max(int(behavior.get("title_max_chars", 0)) - 3, 0):
            issues.append(_issue(
                slide_number,
                "WARN",
                "title_near_limit",
                f"Title is close to the max length for {role}; consider shortening before build.",
            ))
    finally:
        deck.cleanup()

    return {"slide": normalized, "issues": issues, "changes": changes}


def preflight_deck(slides, theme_config=None, resolve_icons=True):
    """Validate a deck spec and return normalized slides + issues."""
    theme_config = _load_theme_config(theme_config)
    normalized = []
    issues = []
    changes = []

    for idx, slide in enumerate(list(slides), start=1):
        result = preflight_slide(
            slide,
            slide_number=idx,
            theme_config=theme_config,
            resolve_icons=resolve_icons,
        )
        normalized.append(result["slide"])
        issues.extend(result["issues"])
        changes.extend(result["changes"])

    return {
        "slides": normalized,
        "issues": issues,
        "changes": changes,
        "summary": {
            "slides": len(normalized),
            "errors": sum(1 for issue in issues if issue["severity"] == "ERROR"),
            "warnings": sum(1 for issue in issues if issue["severity"] == "WARN"),
        },
    }


def _load_theme_name(template_name):
    if not template_name:
        return get_template(name="bcg_default")
    template = get_template(name=template_name)
    if template is None:
        raise SystemExit(f"Template '{template_name}' not found.")
    return template


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="Path to a JSON file containing {'slides': [...]} spec data.")
    parser.add_argument("--template", help="Template name from template_registry.")
    args = parser.parse_args()

    payload = json.loads(args.spec.read_text(encoding="utf-8"))
    slides = payload.get("slides", [])
    result = preflight_deck(slides, theme_config=_load_theme_name(args.template))
    print(json.dumps(result, indent=2))
    return 0 if result["summary"]["errors"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

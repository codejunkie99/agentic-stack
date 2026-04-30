#!/usr/bin/env python3
"""
ingest_ee4p.py -- Convert .ee4p (Efficient Elements) files to deckster-slide-generator template configs.

Extracts theme data (colors, fonts, layouts, positioning) from .ee4p archives and produces
a template.json config that BCGDeck can consume via apply_theme().

Usage:
    python ingest_ee4p.py <file.ee4p> [--output-dir templates/]

v7.0.0 -- Enhanced with PPTX XML theme parsing and geometry-based layout classification.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from collections import Counter
from copy import deepcopy
from pathlib import Path
from xml.etree import ElementTree as ET

from pptx_utils import find_skill_root
from layout_matching import (
    _score_layout_match as score_layout_match,
    derive_semantic_layout_map as canonical_derive_semantic_layout_map,
    merge_semantic_with_geometry as canonical_merge_semantic_with_geometry,
    resolve_semantic_layout_map as canonical_resolve_semantic_layout_map,
)
from layout_semantics import derive_pattern_layouts as canonical_derive_pattern_layouts
from theme import normalize_theme_config


# -----------------------------------------------------------------------------
# PPTX XML Namespaces
# -----------------------------------------------------------------------------

OOXML_NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "p": "http://schemas.openxmlformats.org/presentationml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

# EMU per inch (for converting OOXML units)
EMU_PER_INCH = 914400


# -----------------------------------------------------------------------------
# ee4p XML Parsers (from original ingest_ee4p.py)
# -----------------------------------------------------------------------------


def _bcg_reference_template_path():
    """Return the bundled BCG default template.json path used for geometry matching.

    The refactor moved bundled templates from `templates/` to
    `styles/templates/`. Keep a fallback to the legacy location so older
    extracted workspaces still resolve during audits or local comparisons.
    """
    skill_root = find_skill_root()
    candidates = [
        skill_root / "styles" / "templates" / "bcg_default" / "template.json",
        skill_root / "templates" / "bcg_default" / "template.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def parse_metadata(txt_path):
    """Parse the {id}.txt metadata file."""
    metadata = {}
    with open(txt_path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                key, _, value = line.partition(":")
                metadata[key.strip()] = value.strip()
    return metadata


def parse_style(xml_path):
    """Parse Style.xml for template dimensions, drawing area, layouts."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    style = root.find(".//style")
    if style is None:
        return {}

    result = {
        "name": style.get("name", ""),
        "id": style.get("id", ""),
        "base_style": style.get("baseStyleId", ""),
        "slide_width_units": float(style.get("slideWidth", 960)),
        "slide_height_units": float(style.get("slideHeight", 540)),
    }

    # Convert EE units to inches (960 units ≈ 13.33")
    scale = 13.33 / result["slide_width_units"]

    da = style.find("drawingarea")
    if da is not None:
        result["drawing_area"] = {
            "left": round(float(da.get("left", 0)) * scale, 2),
            "top": round(float(da.get("top", 0)) * scale, 2),
            "width": round(float(da.get("width", 0)) * scale, 2),
            "height": round(float(da.get("height", 0)) * scale, 2),
        }

    layout_rules = []
    for layout in style.findall(".//layouts/layout"):
        layout_rules.append(
            {
                "name": layout.get("name", ""),
                "id": layout.get("id", ""),
                "pattern": layout.get("pattern", ""),
                "checked": layout.get("checked", ""),
            }
        )
    if layout_rules:
        result["layout_rules"] = layout_rules

    # Extract layout names from designs
    layouts = []
    for design in style.findall(".//design"):
        if design.get("name") and "design_name" not in result:
            result["design_name"] = design.get("name")
        for cl in design.findall("customlayout"):
            name = cl.get("name", "")
            if name:
                layouts.append(name)
    result["layouts"] = layouts

    return result


def parse_color_palette(xml_path):
    """Parse ColorPalette.xml for color definitions."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    colors = {}
    for group in root.findall(".//group"):
        group_name = group.get("name", "")
        for color in group.findall("color"):
            name = color.get("name", "")
            rgb = color.get("rgb", "")
            theme = color.get("theme", "")
            entry = {"group": group_name, "theme_index": theme}
            if rgb:
                entry["hex"] = rgb.lstrip("#").upper()

            # Usage descriptions
            for attr in ("descriptionFill", "descriptionLine", "descriptionFont"):
                val = color.get(attr, "")
                if val:
                    entry[attr] = val.replace("\r\n", "; ")

            colors[name] = entry

    return colors


def parse_format_wizard(xml_path):
    """Parse FormatWizard.xml for font and text formatting."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    fonts = set()
    text_hierarchy = []

    for preset in root.findall(".//preset"):
        preset_name = preset.get("name", "")
        for level in preset.findall(".//level"):
            font_el = level.find("font")
            if font_el is not None:
                font_name = font_el.get("name", "")
                if font_name:
                    fonts.add(font_name)
                size = font_el.get("size", "")
                bold = font_el.get("bold", "0")
                color_val = font_el.get("color", "")
                text_hierarchy.append(
                    {
                        "preset": preset_name,
                        "level": level.get("index", ""),
                        "font": font_name,
                        "size": size,
                        "bold": bold == "1",
                        "color": color_val,
                    }
                )

        for bullet in preset.findall(".//bullet"):
            bfont = bullet.get("font", "")
            if bfont:
                fonts.add(bfont)

    sorted_fonts = sorted(fonts)
    return {
        "fonts": sorted_fonts,
        "primary_font": sorted_fonts[0] if sorted_fonts else "Trebuchet MS",
        "text_hierarchy": text_hierarchy,
    }


def parse_bcg_xml(xml_path):
    """Parse BCG.xml for footer position, margins, gradients."""
    tree = ET.parse(xml_path)
    root = tree.getroot()

    result = {}
    scale = 13.33 / 960

    pn = root.find(".//pagenumbers/position")
    if pn is not None:
        result["page_number"] = {
            "x": round(float(pn.get("left", 0)) * scale, 2),
            "y": round(float(pn.get("top", 0)) * scale, 2),
            "w": round(float(pn.get("width", 0)) * scale, 2),
            "h": round(float(pn.get("height", 0)) * scale, 2),
        }

    pn_font = root.find(".//pagenumbers/font")
    if pn_font is not None:
        result["page_number_font"] = {
            "name": pn_font.get("name", ""),
            "size": pn_font.get("size", ""),
            "color": pn_font.get("color", "").lstrip("#"),
        }

    margins = root.find(".//setmargins/default")
    if margins is not None:
        result["margins"] = {
            "top": float(margins.get("top", 0)),
            "bottom": float(margins.get("bottom", 0)),
            "left": float(margins.get("left", 0)),
            "right": float(margins.get("right", 0)),
        }

    return result


# -----------------------------------------------------------------------------
# PPTX XML Theme Extraction (ported from pptx-service/server.py)
# Pure Python -- no Aspose dependency
# -----------------------------------------------------------------------------


def extract_theme_from_pptx_xml(pptx_path):
    """Extract theme data directly from PPTX XML files.

    Parses:
    - ppt/theme/theme1.xml -> scheme colors (dk1, lt1, accent1-6) + font scheme
    - ppt/slideMasters/*.xml -> title/body/subtitle text styles
    - ppt/slideLayouts/*.xml -> per-layout style overrides

    Returns:
        dict with keys: scheme_colors, fonts, title_style, body_style, layout_styles
    """
    ns = OOXML_NS
    result = {
        "scheme_colors": {},
        "fonts": {"major": None, "minor": None},
        "title_style": {},
        "body_style": {},
        "layout_styles": {},
    }

    pptx_path = Path(pptx_path)
    if not pptx_path.exists() or not zipfile.is_zipfile(pptx_path):
        return result

    with zipfile.ZipFile(pptx_path, "r") as zf:
        # 1. Parse theme XML for scheme colors and font scheme
        theme_files = [n for n in zf.namelist() if "ppt/theme/theme" in n and n.endswith(".xml")]
        if theme_files:
            _parse_theme_xml(zf, theme_files[0], result, ns)

        # 2. Parse slide masters for base text styles + background
        master_files = sorted(
            [n for n in zf.namelist() if "ppt/slideMasters/slideMaster" in n and n.endswith(".xml")]
        )
        master_bg_color = None
        if master_files:
            _parse_slide_master_styles(zf, master_files[0], result, ns)
            _parse_slide_master_placeholders(zf, master_files[0], result, ns)
            # Extract master background color
            try:
                master_xml = zf.read(master_files[0])
                master_root = ET.fromstring(master_xml)
                master_bg_elem = master_root.find(".//p:bg", ns)
                if master_bg_elem is not None:
                    master_bg_fill = master_bg_elem.find(".//a:solidFill", ns)
                    if master_bg_fill is not None:
                        master_bg_color = _resolve_fill_color(master_bg_fill, result["scheme_colors"], ns)
                    else:
                        master_bg_scheme = master_bg_elem.find(".//a:schemeClr", ns)
                        if master_bg_scheme is not None:
                            scheme_key = master_bg_scheme.get("val", "")
                            resolved = result.get("scheme_colors", {}).get(scheme_key, "")
                            if resolved:
                                master_bg_color = resolved if resolved.startswith("#") else f"#{resolved}"
            except Exception:
                pass
        result["_master_bg_color"] = master_bg_color

        # 3. Parse slide layouts for geometry and per-layout overrides
        layout_files = [n for n in zf.namelist() if "ppt/slideLayouts/slideLayout" in n and n.endswith(".xml")]
        for layout_file in layout_files:
            _parse_layout_geometry(zf, layout_file, result, ns)

    return result


def _parse_theme_xml(zf, theme_file, result, ns):
    """Extract scheme colors and font scheme from theme XML."""
    try:
        theme_xml = zf.read(theme_file)
        theme_root = ET.fromstring(theme_xml)

        # Scheme colors
        clr_scheme = theme_root.find(".//a:clrScheme", ns)
        if clr_scheme is not None:
            for color_elem in clr_scheme:
                color_name = color_elem.tag.replace(f'{{{ns["a"]}}}', "")
                srgb = color_elem.find(".//a:srgbClr", ns)
                if srgb is not None:
                    result["scheme_colors"][color_name] = f"#{srgb.get('val', '000000')}"
                else:
                    sys_clr = color_elem.find(".//a:sysClr", ns)
                    if sys_clr is not None:
                        result["scheme_colors"][color_name] = f"#{sys_clr.get('lastClr', '000000')}"

            # Add PowerPoint text/background aliases
            sc = result["scheme_colors"]
            if "dk1" in sc:
                sc["tx1"] = sc["dk1"]
            if "dk2" in sc:
                sc["tx2"] = sc["dk2"]
            if "lt1" in sc:
                sc["bg1"] = sc["lt1"]
            if "lt2" in sc:
                sc["bg2"] = sc["lt2"]

        # Font scheme
        font_scheme = theme_root.find(".//a:fontScheme", ns)
        if font_scheme is not None:
            major_font = font_scheme.find("a:majorFont", ns)
            if major_font is not None:
                latin = major_font.find("a:latin", ns)
                if latin is not None:
                    result["fonts"]["major"] = latin.get("typeface")

            minor_font = font_scheme.find("a:minorFont", ns)
            if minor_font is not None:
                latin = minor_font.find("a:latin", ns)
                if latin is not None:
                    result["fonts"]["minor"] = latin.get("typeface")

    except Exception as e:
        print(f"  Warning: Failed to parse theme XML: {e}")


def _parse_slide_master_styles(zf, master_file, result, ns):
    """Extract title/body/subtitle text styles from slide master txStyles."""
    try:
        master_xml = zf.read(master_file)
        master_root = ET.fromstring(master_xml)

        tx_styles = master_root.find(".//p:txStyles", ns)
        if tx_styles is None:
            return

        scheme_colors = result["scheme_colors"]
        theme_fonts = result["fonts"]

        # Title style
        title_style = tx_styles.find("p:titleStyle", ns)
        if title_style is not None:
            result["title_style"] = _extract_text_style(title_style, scheme_colors, theme_fonts, ns)

        # Body style
        body_style = tx_styles.find("p:bodyStyle", ns)
        if body_style is not None:
            result["body_style"] = _extract_text_style(body_style, scheme_colors, theme_fonts, ns)

    except Exception as e:
        print(f"  Warning: Failed to parse slide master: {e}")


def _parse_slide_master_placeholders(zf, master_file, result, ns):
    """Extract fallback placeholder geometry from the slide master."""
    placeholders = []
    try:
        master_xml = zf.read(master_file)
        master_root = ET.fromstring(master_xml)
        slide_width_emu = 12192000
        slide_height_emu = 6858000

        for sp in master_root.findall(".//p:cSld/p:spTree/p:sp", ns):
            nv_sp_pr = sp.find("p:nvSpPr", ns)
            if nv_sp_pr is None:
                continue
            nv_pr = nv_sp_pr.find("p:nvPr", ns)
            if nv_pr is None:
                continue
            ph = nv_pr.find("p:ph", ns)
            if ph is None:
                continue

            sp_pr = sp.find("p:spPr", ns)
            if sp_pr is None:
                continue
            xfrm = sp_pr.find("a:xfrm", ns)
            if xfrm is None:
                continue
            off = xfrm.find("a:off", ns)
            ext = xfrm.find("a:ext", ns)
            if off is None or ext is None:
                continue

            x = int(off.get("x", 0))
            y = int(off.get("y", 0))
            cx = int(ext.get("cx", 0))
            cy = int(ext.get("cy", 0))

            placeholders.append(
                {
                    "type": ph.get("type", "body"),
                    "idx": ph.get("idx"),
                    "bounds": {
                        "x_emu": x,
                        "y_emu": y,
                        "w_emu": cx,
                        "h_emu": cy,
                        "x_pct": round(x / slide_width_emu * 100, 2),
                        "y_pct": round(y / slide_height_emu * 100, 2),
                        "w_pct": round(cx / slide_width_emu * 100, 2),
                        "h_pct": round(cy / slide_height_emu * 100, 2),
                    },
                }
            )
    except Exception:
        placeholders = []

    if placeholders:
        result["_master_placeholders"] = placeholders


def _extract_text_style(style_elem, scheme_colors, theme_fonts, ns):
    """Extract font/color/spacing from a txStyle element's lvl1pPr."""
    style = {}
    lvl1 = style_elem.find("a:lvl1pPr", ns)
    if lvl1 is None:
        return style

    # Line spacing
    spc_pts = lvl1.find(".//a:lnSpc/a:spcPts", ns)
    if spc_pts is not None:
        style["lineSpacingPts"] = int(spc_pts.get("val", 0)) / 100.0

    spc_pct = lvl1.find(".//a:lnSpc/a:spcPct", ns)
    if spc_pct is not None:
        style["lineSpacingPct"] = int(spc_pct.get("val", 100000)) / 100000.0

    # Default run properties
    def_rPr = lvl1.find("a:defRPr", ns)
    if def_rPr is not None:
        # Font size (in hundredths of a point)
        sz = def_rPr.get("sz")
        if sz:
            style["fontSize"] = int(sz) / 100.0

        # Bold/italic
        b = def_rPr.get("b")
        if b is not None:
            style["fontBold"] = b == "1"
        i = def_rPr.get("i")
        if i is not None:
            style["fontItalic"] = i == "1"

        # Font name
        latin = def_rPr.find("a:latin", ns)
        if latin is not None:
            typeface = latin.get("typeface", "")
            if typeface == "+mj-lt":
                style["fontName"] = theme_fonts.get("major")
            elif typeface == "+mn-lt":
                style["fontName"] = theme_fonts.get("minor")
            elif typeface:
                style["fontName"] = typeface

        # Fill color
        solid_fill = def_rPr.find("a:solidFill", ns)
        if solid_fill is not None:
            style["fillColor"] = _resolve_fill_color(solid_fill, scheme_colors, ns)

        # Gradient fill
        grad_fill = def_rPr.find("a:gradFill", ns)
        if grad_fill is not None:
            gradient = []
            for gs in grad_fill.findall(".//a:gs", ns):
                pos = int(gs.get("pos", 0)) / 1000.0
                color = _resolve_fill_color(gs, scheme_colors, ns)
                if color:
                    gradient.append({"position": pos, "color": color})
            if gradient:
                style["gradient"] = gradient

    return style


def _resolve_fill_color(elem, scheme_colors, ns):
    """Resolve a color from srgbClr or schemeClr reference."""
    srgb = elem.find(".//a:srgbClr", ns)
    if srgb is not None:
        return f"#{srgb.get('val', '000000')}"

    scheme_clr = elem.find(".//a:schemeClr", ns)
    if scheme_clr is not None:
        ref = scheme_clr.get("val", "")
        return scheme_colors.get(ref)

    return None


# -----------------------------------------------------------------------------
# Geometry-Based Layout Classification
# -----------------------------------------------------------------------------


def _shape_geometry_name(spPr, ns):
    prst_geom = spPr.find("a:prstGeom", ns)
    if prst_geom is not None:
        return prst_geom.get("prst", "") or "preset"
    if spPr.find("a:custGeom", ns) is not None:
        return "custom"
    return "unknown"


def _normalize_shape_name(value):
    text = (value or "").strip().lower()
    text = re.sub(r"\s*\d+$", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return text.strip("_")


def _summarize_shape_entries(shape_entries):
    geometry_counts = Counter()
    name_counts = Counter()
    filled_count = 0
    large_filled_count = 0

    for entry in shape_entries:
        geometry_counts[entry.get("geometry") or "unknown"] += 1
        normalized_name = _normalize_shape_name(entry.get("name"))
        if normalized_name:
            name_counts[normalized_name] += 1
        if entry.get("fill"):
            filled_count += 1
            bounds = entry.get("bounds") or {}
            if bounds.get("w_pct", 0) >= 12 and bounds.get("h_pct", 0) >= 12:
                large_filled_count += 1

    return {
        "non_placeholder_count": len(shape_entries),
        "filled_shape_count": filled_count,
        "large_filled_shape_count": large_filled_count,
        "geometry_counts": dict(sorted(geometry_counts.items())),
        "top_shape_names": [
            {"name": name, "count": count}
            for name, count in name_counts.most_common(6)
        ],
    }


def _supplement_inherited_placeholders(layout_name, placeholders, master_placeholders):
    """Fill in master-inherited placeholders that are omitted from layout XML.

    Many client templates keep the content-body placeholder on the layout but
    inherit the title placeholder from the slide master. For semantic matching,
    we need that inherited title geometry. Keep this conservative: only add the
    master title when the layout already looks like a titled content slide or
    the layout name strongly implies one.
    """
    if not master_placeholders:
        return placeholders

    existing_types = {placeholder.get("type") for placeholder in placeholders}
    normalized_name = (layout_name or "").strip().lower()
    looks_like_titled_layout = (
        "title" in normalized_name
        or "content" in normalized_name
        or "message" in normalized_name
        or "overview" in normalized_name
        or any(placeholder.get("type") in {"body", "pic"} for placeholder in placeholders)
    )

    if "title" not in existing_types and "ctrTitle" not in existing_types and looks_like_titled_layout:
        master_title = next(
            (
                placeholder
                for placeholder in master_placeholders
                if placeholder.get("type") in {"title", "ctrTitle"}
            ),
            None,
        )
        if master_title:
            placeholders = [deepcopy(master_title)] + list(placeholders)

    return placeholders


def _parse_layout_geometry(zf, layout_file, result, ns):
    """Parse a slideLayout XML for shape geometry, fills, and placeholders."""
    try:
        layout_xml = zf.read(layout_file)
        layout_root = ET.fromstring(layout_xml)

        # Get layout name
        cSld = layout_root.find(".//p:cSld", ns)
        layout_name = cSld.get("name") if cSld is not None else None
        if not layout_name:
            layout_name = layout_file.split("/")[-1].replace(".xml", "")

        layout_slug = _slugify_layout_name(layout_name)
        filename = layout_file.split("/")[-1]

        # Parse shapes
        sp_tree = layout_root.find(".//p:cSld/p:spTree", ns)
        if sp_tree is None:
            return

        placeholders = []
        colored_shapes = []
        shape_entries = []
        slide_width_emu = 12192000  # Default 16:9 (13.33" * 914400)
        slide_height_emu = 6858000  # Default (7.5" * 914400)

        # Detect layout background color (from p:bg element, or fall back to master bg)
        layout_bg_color = None
        _bg_scheme_val = None  # Track the scheme ref for tx1/tx2 filtering
        bg_elem = layout_root.find(".//p:bg", ns)
        if bg_elem is not None and bg_elem.find(".//a:noFill", ns) is None:
            # Check if the fill references tx1/tx2 (text colors, not backgrounds)
            _bg_scheme_ref = bg_elem.find(".//a:schemeClr", ns)
            if _bg_scheme_ref is not None:
                _bg_scheme_val = _bg_scheme_ref.get("val", "")
            bg_fill = bg_elem.find(".//a:solidFill", ns)
            if bg_fill is not None and _bg_scheme_val not in ("tx1", "tx2"):
                layout_bg_color = _resolve_fill_color(bg_fill, result["scheme_colors"], ns)
            else:
                # Check for scheme color reference
                bg_scheme = bg_elem.find(".//a:schemeClr", ns)
                if bg_scheme is not None:
                    scheme_val = bg_scheme.get("val", "")
                    # Map OOXML scheme names to our scheme_colors keys
                    scheme_map = {
                        "bg1": "bg1", "bg2": "bg2", "lt1": "lt1", "lt2": "lt2",
                        "dk1": "dk1", "dk2": "dk2", "tx1": "tx1", "tx2": "tx2",
                        "accent1": "accent1", "accent2": "accent2",
                        "accent3": "accent3", "accent4": "accent4",
                        "accent5": "accent5", "accent6": "accent6",
                    }
                    mapped_key = scheme_map.get(scheme_val, scheme_val)
                    resolved = result.get("scheme_colors", {}).get(mapped_key, "")
                    if resolved:
                        # tx1/tx2 are text colors, not backgrounds — skip these as bg indicators
                        if scheme_val not in ("tx1", "tx2"):
                            layout_bg_color = resolved if resolved.startswith("#") else f"#{resolved}"

        # Fall back to slide master background if layout has no explicit bg
        if not layout_bg_color and result.get("_master_bg_color"):
            layout_bg_color = result["_master_bg_color"]

        # Name-based dark background hint: if layout name contains color keywords
        # and we detected a light/neutral background, the actual visual may be dark.
        # Many templates use master-level shapes or theme overrides not detectable in XML.
        _dark_name_keywords = {"blue", "dark", "black", "navy", "green", "teal", "red"}
        _light_name_keywords = {"white", "light", "blank"}
        name_lower = (layout_name or "").lower()
        name_words = set(name_lower.replace("_", " ").replace("-", " ").split())
        if name_words & _dark_name_keywords and not (name_words & _light_name_keywords):
            # Layout name suggests dark background — check if detected bg is actually light
            if layout_bg_color:
                _bg_rgb = _hex_to_rgb(layout_bg_color)
                if _bg_rgb and _relative_luminance(_bg_rgb) > 0.5:
                    # Detected bg is light but name says dark — use scheme accent1 as proxy
                    accent1 = result.get("scheme_colors", {}).get("accent1", "")
                    if accent1:
                        layout_bg_color = accent1 if accent1.startswith("#") else f"#{accent1}"

        for sp in sp_tree.findall("p:sp", ns):
            # Check for placeholder
            nvSpPr = sp.find("p:nvSpPr", ns)
            cNvPr = nvSpPr.find("p:cNvPr", ns) if nvSpPr is not None else None
            shape_name = cNvPr.get("name", "") if cNvPr is not None else ""
            ph_type = None
            if nvSpPr is not None:
                nvPr = nvSpPr.find("p:nvPr", ns)
                if nvPr is not None:
                    ph = nvPr.find("p:ph", ns)
                    if ph is not None:
                        ph_type = ph.get("type", "body")

            # Get position/size
            spPr = sp.find("p:spPr", ns)
            if spPr is None:
                continue

            xfrm = spPr.find("a:xfrm", ns)
            if xfrm is None:
                continue

            off = xfrm.find("a:off", ns)
            ext = xfrm.find("a:ext", ns)
            if off is None or ext is None:
                continue

            x = int(off.get("x", 0))
            y = int(off.get("y", 0))
            cx = int(ext.get("cx", 0))
            cy = int(ext.get("cy", 0))

            bounds = {
                "x_emu": x,
                "y_emu": y,
                "w_emu": cx,
                "h_emu": cy,
                "x_pct": round(x / slide_width_emu * 100, 2),
                "y_pct": round(y / slide_height_emu * 100, 2),
                "w_pct": round(cx / slide_width_emu * 100, 2),
                "h_pct": round(cy / slide_height_emu * 100, 2),
            }

            # Get fill color
            fill_color = None
            solid_fill = spPr.find("a:solidFill", ns)
            if solid_fill is not None:
                fill_color = _resolve_fill_color(solid_fill, result["scheme_colors"], ns)
            geometry_name = _shape_geometry_name(spPr, ns)
            shape_entry = {
                "name": shape_name,
                "geometry": geometry_name,
                "bounds": bounds,
                "fill": fill_color,
            }

            if ph_type:
                placeholders.append({
                    "type": ph_type,
                    "bounds": bounds,
                    "fill": fill_color,
                })
            else:
                shape_entries.append(shape_entry)
                if fill_color and fill_color not in ("#FFFFFF", "#F2F2F2", "#ffffff", "#f2f2f2"):
                    colored_shapes.append(shape_entry)
                elif not fill_color:
                    # Large non-placeholder shapes without detectable fills are
                    # likely accent panels using scheme colors or group fills.
                    # Include them so split zone detection can find the accent boundary.
                    w_in = cx / 914400.0
                    h_in = cy / 914400.0
                    if w_in > 2.0 and h_in > 2.0:
                        colored_shapes.append(shape_entry)

        placeholders = _supplement_inherited_placeholders(
            layout_name,
            placeholders,
            result.get("_master_placeholders"),
        )

        # Classify layout by geometry
        geometry_type = _classify_layout_geometry(
            placeholders, colored_shapes, slide_width_emu, slide_height_emu
        )

        # Build content slots
        slots = _build_content_slots(placeholders, colored_shapes, result.get("scheme_colors", {}))

        # Build accent_regions list
        accent_regions = [
            {
                "bounds": {k: s["bounds"][k] for k in ("x_pct", "y_pct", "w_pct", "h_pct")},
                "fill": s["fill"],
                "paletteRole": _select_palette_role(s["fill"]),
                "shapeName": s.get("name", ""),
                "geometry": s.get("geometry", ""),
                "areaPct": round(
                    float((s.get("bounds") or {}).get("w_pct", 0))
                    * float((s.get("bounds") or {}).get("h_pct", 0)),
                    2,
                ),
            }
            for s in colored_shapes
        ]
        shape_summary = _summarize_shape_entries(shape_entries)

        # Derive content zone from placeholder geometry
        content_zone = _derive_content_zone(
            placeholders, accent_regions, result.get("scheme_colors", {}),
            layout_bg_color=layout_bg_color
        )

        # Derive split zones for split-panel layouts
        split_zones = _derive_split_zones(
            placeholders, accent_regions, colored_shapes,
            layout_bg_color, slide_width_emu, slide_height_emu,
            layout_slug=layout_slug,
        )
        if split_zones and content_zone:
            content_zone['split_zones'] = {
                'left_x_pct': split_zones['left_x_pct'],
                'left_w_pct': split_zones['left_w_pct'],
                'right_x_pct': split_zones['right_x_pct'],
                'right_w_pct': split_zones['right_w_pct'],
                'left_x': split_zones['left_x'],
                'left_w': split_zones['left_w'],
                'right_x': split_zones['right_x'],
                'right_w': split_zones['right_w'],
            }

        result["layout_styles"][layout_slug] = {
            "layout_name": layout_name,
            "filename": filename,
            "geometry_type": geometry_type,
            "background": layout_bg_color,
            "placeholders": [
                {"type": p["type"], "bounds": {k: p["bounds"][k] for k in ("x_pct", "y_pct", "w_pct", "h_pct")}}
                for p in placeholders
            ],
            "slots": slots,
            "accent_regions": accent_regions,
            "content_zone": content_zone,
            "shape_summary": shape_summary,
        }

    except Exception as e:
        print(f"  Warning: Failed to parse layout {layout_file}: {e}")


def _classify_layout_geometry(placeholders, colored_shapes, slide_w, slide_h):
    """Classify layout type using shape geometry heuristics, not names."""
    title_ph = next((p for p in placeholders if p["type"] in ("title", "ctrTitle")), None)
    body_phs = [p for p in placeholders if p["type"] == "body"]

    if not title_ph and not body_phs and not colored_shapes:
        return "blank"

    # Check for accent/split layouts BEFORE the centered-title heuristic.
    # Layouts with large colored accent shapes (>20% width, >50% height) are
    # split layouts, not title slides — even if the title is positioned low.
    if colored_shapes:
        accent = colored_shapes[0]
        accent_w_pct = accent["bounds"]["w_pct"]
        accent_x_pct = accent["bounds"]["x_pct"]

        if accent_x_pct < 5:  # Accent on left
            if accent_w_pct < 40:
                return "accent_one_third"
            elif accent_w_pct < 55:
                return "accent_half"
            else:
                return "accent_two_third"
        elif accent_x_pct > 50:  # Accent on right
            return "accent_right"
        else:
            return "accent_custom"

    # Centered title (no accent shapes) = title slide
    if title_ph and title_ph["bounds"]["y_pct"] > 30:
        return "title_slide"

    # No colored shapes -- pure content layout
    if body_phs:
        if len(body_phs) == 1:
            body_w = body_phs[0]["bounds"]["w_pct"]
            if body_w > 85:
                return "full_content"
            else:
                return "partial_content"
        elif len(body_phs) >= 2:
            return "multi_column"

    if title_ph and not body_phs:
        return "title_only"

    return "content"


def _build_content_slots(placeholders, colored_shapes, scheme_colors):
    """Build content slot metadata from body placeholders."""
    slots = []
    body_phs = [p for p in placeholders if p["type"] in ("body", "subTitle")]
    for ph in body_phs:
        bg_color = ph.get("fill") or "#F2F2F2"
        slots.append({
            "bounds": {k: ph["bounds"][k] for k in ("x_pct", "y_pct", "w_pct", "h_pct")},
            "background": bg_color,
            "paletteRole": _select_palette_role(bg_color),
        })
    return slots


# -----------------------------------------------------------------------------
# Content Zone Derivation (inferred from placeholder geometry)
# -----------------------------------------------------------------------------


def _is_color_dark(hex_color):
    """Return True if the color is dark (not white/very-light)."""
    if not hex_color:
        return False
    rgb = _hex_to_rgb(hex_color)
    if rgb is None:
        return False
    return _relative_luminance(rgb) < 0.7


def _derive_split_zones(placeholders, accent_regions, colored_shapes,
                        layout_bg_color, slide_w_emu, slide_h_emu,
                        layout_slug=None):
    """Derive left/right split zone boundaries for a layout (in inches).

    Uses three sources in priority order:
      1. Accent regions -- large colored shapes that define the accent panel
      2. Background color + title placeholder -- infer panel from narrow title
      3. BCG reference zones -- fallback for known BCG layout slugs

    Returns:
        dict with left_x, left_w, right_x, right_w (inches) or None.
    """
    # Slide dimensions in inches
    slide_w_in = slide_w_emu / 914400.0
    slide_h_in = slide_h_emu / 914400.0

    GAP_IN = 0.40  # gap between left and right zones in inches
    FLY_LEFT = 0.69  # standard BCG fly_zone left margin

    # --- Priority 1: Divider detection from ALL non-placeholder shapes ---
    # Scan all shapes (accent_regions + colored_shapes) for the tallest
    # wide shape — that's the accent panel / page divider.  Works for
    # freeforms, arrows, rectangles, and any shape regardless of fill type.
    all_candidate_shapes = list(accent_regions or []) + list(colored_shapes or [])
    best_divider = None
    best_area = 0
    for shape in all_candidate_shapes:
        sb = shape.get('bounds', {})
        s_w_pct = sb.get('w_pct', 0)
        s_h_pct = sb.get('h_pct', 0)
        s_x_pct = sb.get('x_pct', 0)
        # Divider = spans >60% of slide height AND >15% of slide width
        # but NOT full-width (that's a background, not a divider)
        if s_h_pct >= 60 and 15 <= s_w_pct <= 75:
            area = s_w_pct * s_h_pct
            if area > best_area:
                best_area = area
                best_divider = sb

    if best_divider:
        d_x_in = best_divider.get('x_pct', 0) / 100.0 * slide_w_in
        d_w_in = best_divider.get('w_pct', 0) / 100.0 * slide_w_in
        d_right_in = d_x_in + d_w_in

        # Determine which side the divider is on:
        # - If the divider's right edge is within 15% of the slide's
        #   right edge, it's a RIGHT-side accent (e.g., green_highlight)
        #   → use its left edge as the boundary.
        # - If the divider starts within 15% of the slide's left edge,
        #   it's a LEFT-side accent (e.g., green_left_arrow)
        #   → use its right edge as the boundary.
        right_margin_pct = (slide_w_in - d_right_in) / slide_w_in * 100
        left_margin_pct = d_x_in / slide_w_in * 100

        if right_margin_pct <= 15:
            # Divider on RIGHT side — content goes LEFT of the divider
            left_x = FLY_LEFT
            left_w = round(d_x_in - GAP_IN - FLY_LEFT, 2)
            right_x = round(d_x_in, 2)
            right_w = round(d_w_in, 2)
        elif left_margin_pct <= 15:
            # Divider on LEFT side — content goes RIGHT of the divider
            left_x = round(d_x_in, 2)
            left_w = round(d_w_in, 2)
            right_x = round(d_right_in + GAP_IN, 2)
            right_w = round(slide_w_in - right_x, 2)
        elif d_x_in + d_w_in / 2 < slide_w_in / 2:
            # Center-based fallback: divider center in left half
            left_x = round(d_x_in, 2)
            left_w = round(d_w_in, 2)
            right_x = round(d_right_in + GAP_IN, 2)
            right_w = round(slide_w_in - right_x, 2)
        else:
            # Center-based fallback: divider center in right half
            left_x = FLY_LEFT
            left_w = round(d_x_in - GAP_IN - FLY_LEFT, 2)
            right_x = round(d_x_in, 2)
            right_w = round(d_w_in, 2)

        if left_w > 0.5 and right_w > 0.5:
            return {
                'left_x_pct': round(left_x / slide_w_in * 100, 2),
                'left_w_pct': round(left_w / slide_w_in * 100, 2),
                'right_x_pct': round(right_x / slide_w_in * 100, 2),
                'right_w_pct': round(right_w / slide_w_in * 100, 2),
                'left_x': left_x, 'left_w': left_w,
                'right_x': right_x, 'right_w': right_w,
            }

    # --- Priority 2: Dark background + narrow title placeholder ---
    # If no large divider shape was found, infer from the title position
    # and background color.
    title_ph = next((p for p in placeholders if p['type'] in ('title', 'ctrTitle')), None)

    if title_ph and _is_color_dark(layout_bg_color) and title_ph['bounds']['w_pct'] < 50:
        tb = title_ph['bounds']
        title_x_pct = tb['x_pct']
        title_w_pct = tb['w_pct']
        title_x_in = title_x_pct / 100.0 * slide_w_in
        title_w_in = title_w_pct / 100.0 * slide_w_in

        # Title position hints which side the accent panel is on
        if title_x_pct < 50:
            # Title in left half -> accent panel is LEFT, content is RIGHT
            # Use half the slide as conservative accent estimate
            accent_right_in = max(title_x_in + title_w_in, slide_w_in * 0.30)
            right_x = round(accent_right_in + GAP_IN, 2)
            right_w = round(slide_w_in - right_x - FLY_LEFT, 2)
            left_x = FLY_LEFT
            left_w = round(accent_right_in - FLY_LEFT, 2)
        else:
            # Title in right half -> accent panel is RIGHT, content is LEFT
            accent_left_in = title_x_pct / 100.0 * slide_w_in
            left_x = FLY_LEFT
            left_w = round(accent_left_in - GAP_IN - FLY_LEFT, 2)
            right_x = round(accent_left_in, 2)
            right_w = round(slide_w_in - accent_left_in - FLY_LEFT, 2)

        if left_w > 0.5 and right_w > 0.5:
            return {
                'left_x_pct': round(left_x / slide_w_in * 100, 2),
                'left_w_pct': round(left_w / slide_w_in * 100, 2),
                'right_x_pct': round(right_x / slide_w_in * 100, 2),
                'right_w_pct': round(right_w / slide_w_in * 100, 2),
                'left_x': left_x, 'left_w': left_w,
                'right_x': right_x, 'right_w': right_w,
            }

    # --- Priority 3: BCG reference zones as last-resort fallback ---
    _BCG_REFERENCE_ZONES = {
        'green-highlight':    {'left_x': 0.69, 'left_w': 6.80, 'right_x': 8.20, 'right_w': 4.30},
        'green-one-third':    {'left_x': 0.69, 'left_w': 3.50, 'right_x': 4.80, 'right_w': 8.00},
        'green-left-arrow':   {'left_x': 0.69, 'left_w': 3.50, 'right_x': 5.20, 'right_w': 7.50},
        'arrow-half':         {'left_x': 0.69, 'left_w': 5.20, 'right_x': 7.00, 'right_w': 5.40},
        'green-half':         {'left_x': 0.69, 'left_w': 5.00, 'right_x': 6.67, 'right_w': 6.67},
        'green-two-third':    {'left_x': 0.69, 'left_w': 7.50, 'right_x': 8.55, 'right_w': 4.78},
        'left-arrow':         {'left_x': 0.69, 'left_w': 3.50, 'right_x': 5.20, 'right_w': 7.50},
        'green-arrow-half':   {'left_x': 0.69, 'left_w': 5.20, 'right_x': 7.00, 'right_w': 5.40},
    }
    # If accent-region and title heuristics both failed, use BCG defaults
    # so split layouts still get some zone boundaries rather than none.
    if layout_slug:
        lookup = layout_slug.lower().replace('_', '-')
        if lookup.startswith('d-'):
            lookup = lookup[2:]
        ref = _BCG_REFERENCE_ZONES.get(lookup)
        if ref:
            return {
                'left_x_pct': round(ref['left_x'] / slide_w_in * 100, 2),
                'left_w_pct': round(ref['left_w'] / slide_w_in * 100, 2),
                'right_x_pct': round(ref['right_x'] / slide_w_in * 100, 2),
                'right_w_pct': round(ref['right_w'] / slide_w_in * 100, 2),
                'left_x': ref['left_x'], 'left_w': ref['left_w'],
                'right_x': ref['right_x'], 'right_w': ref['right_w'],
            }

    return None


def _bounds_overlap(a, b):
    """Check if two bounds dicts (x_pct, y_pct, w_pct, h_pct) overlap."""
    ax1, ay1 = a['x_pct'], a['y_pct']
    ax2, ay2 = ax1 + a['w_pct'], ay1 + a['h_pct']
    bx1, by1 = b['x_pct'], b['y_pct']
    bx2, by2 = bx1 + b['w_pct'], by1 + b['h_pct']
    return ax1 < bx2 and ax2 > bx1 and ay1 < by2 and ay2 > by1


def _bounds_contains(outer, inner):
    """Check if outer bounds fully contains inner bounds."""
    if not outer or not inner:
        return False
    return (outer['x_pct'] <= inner['x_pct'] and
            outer['y_pct'] <= inner['y_pct'] and
            outer['x_pct'] + outer['w_pct'] >= inner['x_pct'] + inner['w_pct'] and
            outer['y_pct'] + outer['h_pct'] >= inner['y_pct'] + inner['h_pct'])


def _derive_content_zone(placeholders, accent_regions, scheme_colors=None,
                         layout_bg_color=None):
    """Infer content rendering zone from title + picture + accent positions.

    Returns a dict with title_side, title_zone, title_width, has_picture,
    picture_side, content_bounds, content_bg, content_palette_role, layout_class.

    Args:
        layout_bg_color: The layout's own background color (from p:bg element).
            Used as the primary fallback for content_bg — more accurate than
            scheme bg1 since some layouts use bg2 or accent backgrounds.
    """
    title = next((p for p in placeholders if p['type'] in ('title', 'ctrTitle')), None)
    pic = next((p for p in placeholders if p['type'] == 'pic'), None)

    if not title:
        return None

    tb = title['bounds']
    result = {
        'title_side': 'left' if tb['x_pct'] < 40 else 'right',
        'title_zone': 'top' if tb['y_pct'] < 20 else ('mid' if tb['y_pct'] < 50 else 'bottom'),
        'title_width': 'wide' if tb['w_pct'] > 60 else 'narrow',
        'has_picture': pic is not None,
        'picture_side': None,
        'title_picture_overlap': False,
        'content_bounds': None,
        'layout_class': 'unknown',
    }

    if pic:
        pb = pic['bounds']
        result['picture_side'] = 'left' if pb['x_pct'] < 40 else 'right'
        result['title_picture_overlap'] = _bounds_overlap(tb, pb)

    # Derive content zone based on title position
    if result['title_zone'] == 'top' and result['title_width'] == 'wide':
        # Full-page: content below title across full width
        content_top = tb['y_pct'] + tb['h_pct'] + 2
        result['content_bounds'] = {
            'x_pct': 5, 'y_pct': content_top,
            'w_pct': 90, 'h_pct': max(85 - content_top, 20)
        }
        result['layout_class'] = 'full_page'

    elif result['title_zone'] == 'top' and result['title_width'] == 'narrow':
        # Top narrow title — treat as full-page with content below across full width
        content_top = tb['y_pct'] + tb['h_pct'] + 2
        result['content_bounds'] = {
            'x_pct': 5, 'y_pct': content_top,
            'w_pct': 90, 'h_pct': max(85 - content_top, 20)
        }
        result['layout_class'] = 'full_page'

    elif result['title_zone'] == 'mid' and result['title_width'] == 'narrow':
        # Split panel: title in one panel, content on opposite side
        if result['title_side'] == 'left':
            cx = tb['x_pct'] + tb['w_pct'] + 2
            result['content_bounds'] = {
                'x_pct': cx, 'y_pct': 5,
                'w_pct': max(95 - cx, 20), 'h_pct': 85
            }
        else:
            result['content_bounds'] = {
                'x_pct': 5, 'y_pct': 5,
                'w_pct': max(tb['x_pct'] - 7, 20), 'h_pct': 85
            }
        result['layout_class'] = 'split_panel'

    elif result['title_zone'] == 'bottom':
        # Statement layout: title only, no content zone
        result['content_bounds'] = None
        result['layout_class'] = 'statement'

    elif result['title_zone'] == 'mid' and result['title_width'] == 'wide':
        # Wide mid title — likely a statement or centered layout
        result['content_bounds'] = None
        result['layout_class'] = 'statement'

    # Determine content zone background color
    # Priority: accent region covering content > layout background > scheme bg1 > default
    if result['content_bounds']:
        content_bg = None
        for accent in accent_regions:
            if _bounds_contains(accent['bounds'], result['content_bounds']):
                content_bg = accent.get('fill', '').lstrip('#')
                break
        if not content_bg and layout_bg_color:
            content_bg = layout_bg_color.lstrip('#')
        if not content_bg and scheme_colors:
            content_bg = scheme_colors.get('bg1', 'F2F2F2').lstrip('#')
        if not content_bg:
            content_bg = 'F2F2F2'
        result['content_bg'] = content_bg
        result['content_palette_role'] = _select_palette_role('#' + content_bg)
    else:
        # For statement/title-only layouts, still capture the background
        if layout_bg_color:
            result['content_bg'] = layout_bg_color.lstrip('#')
            result['content_palette_role'] = _select_palette_role(layout_bg_color)
        else:
            result['content_bg'] = None
            result['content_palette_role'] = None

    return result


def _score_layout_match(client_geom, bcg_reference_geom):
    return score_layout_match(client_geom, bcg_reference_geom)


# -----------------------------------------------------------------------------
# WCAG Contrast Analysis (ported from pptx-service/server.py)
# -----------------------------------------------------------------------------


def _hex_to_rgb(hex_color):
    """Convert hex color string to (r, g, b) tuple."""
    if not hex_color:
        return None
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        return None
    try:
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    except ValueError:
        return None


def _relative_luminance(rgb):
    """Calculate relative luminance per WCAG 2.0."""
    def _channel(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = rgb
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def _contrast_ratio(bg_color, fg_color):
    """Calculate WCAG 2.0 contrast ratio between two colors."""
    bg_rgb = _hex_to_rgb(bg_color)
    fg_rgb = _hex_to_rgb(fg_color)
    if bg_rgb is None or fg_rgb is None:
        return None
    bg_l = _relative_luminance(bg_rgb)
    fg_l = _relative_luminance(fg_rgb)
    lighter = max(bg_l, fg_l)
    darker = min(bg_l, fg_l)
    return (lighter + 0.05) / (darker + 0.05)


def _select_palette_role(background_color):
    """Determine if text on this background should be light or dark."""
    if not background_color:
        return "light"
    rgb = _hex_to_rgb(background_color)
    if rgb is None:
        return "light"
    luminance = _relative_luminance(rgb)
    # Dark background -> use light text (dark palette role)
    return "dark" if luminance < 0.4 else "light"


# -----------------------------------------------------------------------------
# Layout Name Normalization
# -----------------------------------------------------------------------------


def _slugify_layout_name(name):
    """Convert layout name to a URL-safe slug."""
    if not name:
        return ""
    normalized = name.lower().strip()
    # Strip numeric prefixes (e.g., "13_")
    normalized = re.sub(r"^\s*\d+\s*[_\-.]?\s*", "", normalized)
    # Strip "Client " prefix
    normalized = re.sub(r"^client\s+", "", normalized, flags=re.IGNORECASE)
    # Detect detail prefix
    has_d = False
    match = re.match(r"^d[._\s-]+(.*)$", normalized, flags=re.IGNORECASE)
    if match:
        has_d = True
        normalized = match.group(1)
    # Convert to kebab-case
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized)
    normalized = re.sub(r"^-+|-+$", "", normalized)
    if not normalized:
        return "d" if has_d else ""
    return f"d-{normalized}" if has_d else normalized


# -----------------------------------------------------------------------------
# PPTX Layout XML Map Discovery
# -----------------------------------------------------------------------------


def discover_layout_xml_map(pptx_path):
    """Parse PPTX to map layout names to XML filenames."""
    xml_map = {}
    pptx_path = Path(pptx_path)
    if not pptx_path.exists() or not zipfile.is_zipfile(pptx_path):
        return xml_map

    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}

    with zipfile.ZipFile(pptx_path, "r") as zf:
        for entry in zf.namelist():
            if entry.startswith("ppt/slideLayouts/slideLayout") and entry.endswith(".xml"):
                filename = entry.split("/")[-1]
                try:
                    content = zf.read(entry).decode("utf-8")
                    tree = ET.fromstring(content)
                    cSld = tree.find("p:cSld", ns)
                    if cSld is not None:
                        name = cSld.get("name", "")
                        if name:
                            xml_map[name] = filename
                except (ET.ParseError, UnicodeDecodeError):
                    continue

    return xml_map


# -----------------------------------------------------------------------------
# Color Alias Derivation
# -----------------------------------------------------------------------------


def derive_color_aliases(colors):
    """Derive semantic color aliases from ee4p color data."""
    aliases = {}

    def is_greenish(hex_val):
        if not hex_val or len(hex_val) != 6:
            return False
        r, g, b = int(hex_val[:2], 16), int(hex_val[2:4], 16), int(hex_val[4:], 16)
        return g > r and g > b and g > 80

    def is_light(hex_val):
        if not hex_val or len(hex_val) != 6:
            return False
        r, g, b = int(hex_val[:2], 16), int(hex_val[2:4], 16), int(hex_val[4:], 16)
        return (r + g + b) / 3 > 220

    # Pass 1: DARK_TEXT from font descriptions
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        desc_font = info.get("descriptionFont", "").lower()
        if "default text" in desc_font:
            if hex_val:
                aliases["DARK_TEXT"] = hex_val
            else:
                name_lower = name.lower()
                if "gray" in name_lower or "grey" in name_lower:
                    aliases["DARK_TEXT"] = "53565A"
                else:
                    aliases["DARK_TEXT"] = "575757"
            break
    if "DARK_TEXT" not in aliases:
        for name, info in colors.items():
            if "text" in name.lower() and ("gray" in name.lower() or "grey" in name.lower()):
                hex_val = info.get("hex", "")
                aliases["DARK_TEXT"] = hex_val if hex_val else "53565A"
                break

    # Pass 2: GREEN -- first greenish in "Use more" group
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        if info.get("group") == "Use more" and is_greenish(hex_val):
            aliases["GREEN"] = hex_val
            break

    # Pass 3: DARK_GREEN
    greens = []
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        if is_greenish(hex_val):
            brightness = sum(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))
            greens.append((brightness, hex_val))
    greens.sort()
    if len(greens) >= 2:
        aliases["DARK_GREEN"] = greens[0][1]
        if "GREEN" not in aliases:
            aliases["GREEN"] = greens[1][1]
    if len(greens) >= 3:
        aliases["DEEP_GREEN"] = greens[0][1]
        aliases["DARK_GREEN"] = greens[1][1]

    # Pass 4: LIGHT_BG
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        if is_light(hex_val) and hex_val != "FFFFFF":
            aliases["LIGHT_BG"] = hex_val
            break
    if "LIGHT_BG" not in aliases:
        for name, info in colors.items():
            name_lower = name.lower()
            if "off white" in name_lower or name_lower == "light gray":
                hex_val = info.get("hex", "")
                aliases["LIGHT_BG"] = hex_val if hex_val else "F2F2F2"
                break
        if "LIGHT_BG" not in aliases:
            aliases["LIGHT_BG"] = "F2F2F2"

    aliases["WHITE"] = "FFFFFF"

    # Pass 5: MED_GRAY
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        if hex_val and len(hex_val) == 6:
            r, g, b = int(hex_val[:2], 16), int(hex_val[2:4], 16), int(hex_val[4:], 16)
            if abs(r - g) < 10 and abs(g - b) < 10 and 90 < r < 160:
                aliases["MED_GRAY"] = hex_val
                break

    return aliases


def enrich_aliases_with_scheme(aliases, ee4p_colors, scheme_colors):
    """Enrich color aliases with resolved scheme colors for theme-indexed entries.

    Some ee4p colors reference a theme_index without a hex value. This function
    resolves them using the scheme colors extracted from theme1.xml.
    """
    # Map theme indices to scheme color keys
    # PowerPoint theme indices: 0=bg1, 1=tx1, 2=bg2, 3=tx2, 4-9=accent1-6
    index_to_scheme = {
        "0": "bg1", "1": "tx1", "2": "bg2", "3": "tx2",
        "4": "accent1", "5": "accent2", "6": "accent3",
        "7": "accent4", "8": "accent5", "9": "accent6",
        "12": "dk1", "13": "dk2",
    }

    # Resolve missing hex values
    for name, info in ee4p_colors.items():
        if info.get("hex"):
            continue  # Already has a hex value
        theme_idx = info.get("theme_index", "")
        if theme_idx and theme_idx in index_to_scheme:
            scheme_key = index_to_scheme[theme_idx]
            resolved = scheme_colors.get(scheme_key)
            if resolved:
                info["hex"] = resolved.lstrip("#").upper()

    # Re-derive aliases with resolved colors
    if any(info.get("hex") for info in ee4p_colors.values()):
        updated = derive_color_aliases(ee4p_colors)
        for k, v in updated.items():
            if k not in aliases or not aliases[k]:
                aliases[k] = v

    # Add accent colors from scheme
    accent_map = {
        "ACCENT1": "accent1", "ACCENT2": "accent2", "ACCENT3": "accent3",
        "ACCENT4": "accent4", "ACCENT5": "accent5", "ACCENT6": "accent6",
    }
    for alias_key, scheme_key in accent_map.items():
        if alias_key not in aliases and scheme_key in scheme_colors:
            aliases[alias_key] = scheme_colors[scheme_key].lstrip("#").upper()

    return aliases


# -----------------------------------------------------------------------------
# Chart Palette
# -----------------------------------------------------------------------------


def derive_chart_palette(colors):
    """Build chart color palette from ee4p colors."""
    palette = []
    seen = set()
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        if info.get("group") == "Use more" and hex_val and hex_val not in seen:
            brightness = sum(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))
            if 150 < brightness < 650:
                palette.append(hex_val)
                seen.add(hex_val)
    for name, info in colors.items():
        hex_val = info.get("hex", "")
        if hex_val and hex_val not in seen:
            brightness = sum(int(hex_val[i : i + 2], 16) for i in (0, 2, 4))
            if 150 < brightness < 650:
                palette.append(hex_val)
                seen.add(hex_val)
        if len(palette) >= 8:
            break
    return palette


# -----------------------------------------------------------------------------
# Semantic Layout Mapping (name-based + geometry fallback)
# -----------------------------------------------------------------------------


def derive_semantic_layout_map(layout_map):
    return canonical_derive_semantic_layout_map(layout_map)


def merge_semantic_with_geometry(semantic_map, layout_styles, xml_layout_map=None,
                                 bcg_reference_styles=None):
    return canonical_merge_semantic_with_geometry(
        semantic_map,
        layout_styles,
        xml_layout_map=xml_layout_map,
        bcg_reference_styles=bcg_reference_styles,
    )


def resolve_semantic_layout_map(layout_map, layout_styles, xml_layout_map=None,
                                layout_rules=None, bcg_reference_styles=None,
                                return_debug=False):
    return canonical_resolve_semantic_layout_map(
        layout_map,
        layout_styles,
        xml_layout_map=xml_layout_map,
        layout_rules=layout_rules,
        bcg_reference_styles=bcg_reference_styles,
        return_debug=return_debug,
    )


def derive_pattern_layouts(semantic_layout_map):
    return canonical_derive_pattern_layouts(semantic_layout_map)


# -----------------------------------------------------------------------------
# Config Normalization
# -----------------------------------------------------------------------------


def normalize_config(config, safe_name, pptx_path):
    """Add build-deck-compatible fields to an ingested template config."""
    style = config.get("style", {})
    colors = config.get("colors", {})
    typography = config.get("typography", {})

    config["name"] = safe_name
    desc_name = style.get("name", "") or config.get("metadata", {}).get("Template name", safe_name)
    config["description"] = f"{desc_name} (ingested from ee4p)"
    config["brand"] = "client"
    config["font"] = typography.get("primary_font", "Trebuchet MS")

    # Dimensions
    w_units = style.get("slide_width_units", 960)
    h_units = style.get("slide_height_units", 540)
    scale = 13.33 / w_units
    config["dimensions"] = {
        "width": round(w_units * scale, 2),
        "height": round(h_units * scale, 2),
    }

    # Color aliases
    config["color_aliases"] = derive_color_aliases(colors)

    # Chart palette
    config["chart_palette"] = derive_chart_palette(colors)

    # Normalize fly_zone
    fz = config.get("fly_zone", {})
    if fz and "content_right" not in fz:
        fz["content_right"] = round(fz.get("content_left", 0) + fz.get("content_width", 0), 2)

    # Title position
    da = style.get("drawing_area", {})
    if da:
        config["title"] = {
            "x": da.get("left", 0.69),
            "y": 0.68,
            "w": da.get("width", 11.96),
            "h": 0.55,
        }

    # Layout XML mappings
    if pptx_path and Path(pptx_path).exists():
        config["xml_layout_map"] = discover_layout_xml_map(pptx_path)

    # Seed semantic layout map from legacy name matching. The structural matcher
    # below replaces this when layout geometry is available, but keeping the seed
    # around improves compatibility for partial or malformed templates.
    layout_map = config.get("layout_map", {})
    config["semantic_layout_map"] = derive_semantic_layout_map(layout_map)

    # Enrich with theme XML data
    if pptx_path and Path(pptx_path).exists():
        theme_data = extract_theme_from_pptx_xml(pptx_path)
        config["scheme_colors"] = theme_data["scheme_colors"]
        config["layout_geometry"] = theme_data["layout_styles"]

        # Override font if theme XML has it
        if theme_data["fonts"].get("major"):
            config["font"] = theme_data["fonts"]["major"]

        # Store title/body styles
        if theme_data.get("title_style"):
            config["title_style"] = theme_data["title_style"]
        if theme_data.get("body_style"):
            config["body_style"] = theme_data["body_style"]

        # Enrich color aliases with resolved scheme colors
        config["color_aliases"] = enrich_aliases_with_scheme(
            config["color_aliases"], colors, theme_data["scheme_colors"]
        )

        # Load BCG reference geometry for geometry-aware validation
        bcg_ref_styles = None
        bcg_ref_path = _bcg_reference_template_path()
        if bcg_ref_path.exists():
            try:
                with open(bcg_ref_path) as _rf:
                    bcg_ref_styles = json.load(_rf).get("layout_geometry", {})
            except Exception:
                pass

        # Resolve semantic roles from structural signatures, then keep the top
        # candidates for debugging and corpus benchmarking.
        resolved_semantic_map, semantic_debug = resolve_semantic_layout_map(
            layout_map,
            theme_data["layout_styles"],
            config.get("xml_layout_map"),
            layout_rules=style.get("layout_rules"),
            bcg_reference_styles=bcg_ref_styles,
            return_debug=True,
        )
        config["semantic_layout_map"] = resolved_semantic_map
        config["semantic_layout_debug"] = semantic_debug
        config["matching_version"] = semantic_debug.get("matcher_version", "signature_v2")

    # Pattern layouts
    config["pattern_layouts"] = derive_pattern_layouts(config["semantic_layout_map"])

    layout_geometry = config.get("layout_geometry", {})
    config["supports"] = {
        "source_footer": True,
        "page_numbers": True,
        "detail_layouts": bool(config.get("detail_layout_map")),
        "semantic_layouts": sorted(config["semantic_layout_map"].keys()),
        "picture_layouts": sorted(
            slug for slug, info in layout_geometry.items()
            if (info.get("content_zone") or {}).get("has_picture")
        ),
    }

    return normalize_theme_config(config)


# -----------------------------------------------------------------------------
# Main Ingestion
# -----------------------------------------------------------------------------


def _clean_orphaned_rels(pptx_path):
    """Remove .rels entries that point to non-existent targets in the PPTX.

    Some ee4p exporters leave orphaned layout references after pruning
    unused layouts.  These cause QA 'broken rel target' HIGHs but don't
    affect PowerPoint rendering.
    """
    import io
    import os as _os

    RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"

    with zipfile.ZipFile(pptx_path, "r") as zin:
        all_files = set(zin.namelist())
        modified = {}

        for name in all_files:
            if not name.endswith(".rels"):
                continue
            content = zin.read(name)
            try:
                root = ET.fromstring(content)
            except ET.ParseError:
                continue

            parent_dir = _os.path.dirname(name.replace("_rels/", "").rstrip(".rels"))
            changed = False
            for rel in list(root):
                target = rel.get("Target", "")
                if target.startswith("http") or target.startswith("mailto"):
                    continue
                resolved = _os.path.normpath(
                    _os.path.join(parent_dir, target)
                ).replace("\\", "/")
                if resolved not in all_files:
                    root.remove(rel)
                    changed = True

            if changed:
                modified[name] = ET.tostring(root, xml_declaration=True, encoding="UTF-8")

    if not modified:
        return

    # Rewrite the PPTX with cleaned .rels files
    tmp_path = str(pptx_path) + ".tmp"
    with zipfile.ZipFile(pptx_path, "r") as zin, zipfile.ZipFile(tmp_path, "w") as zout:
        for item in zin.infolist():
            if item.filename in modified:
                zout.writestr(item, modified[item.filename])
            else:
                zout.writestr(item, zin.read(item.filename))
    Path(tmp_path).replace(pptx_path)


def ingest_ee4p(ee4p_path, output_dir):
    """Main ingestion function for .ee4p files."""
    ee4p_path = Path(ee4p_path)

    if not ee4p_path.exists():
        print(f"Error: File not found: {ee4p_path}")
        sys.exit(1)

    if not zipfile.is_zipfile(ee4p_path):
        print(f"Error: Not a valid ZIP/ee4p file: {ee4p_path}")
        sys.exit(1)

    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(ee4p_path, "r") as zf:
            zf.extractall(tmp_dir)

        tmp_path = Path(tmp_dir)
        subdirs = [d for d in tmp_path.iterdir() if d.is_dir()]
        style_dir = subdirs[0] if subdirs else tmp_path

        config = {"source": str(ee4p_path), "format": "ee4p"}

        # Metadata
        txt_files = list(style_dir.glob("*.txt"))
        if txt_files:
            config["metadata"] = parse_metadata(txt_files[0])

        # Style
        style_xml = style_dir / "Style.xml"
        if style_xml.exists():
            config["style"] = parse_style(style_xml)

        # Colors
        color_xml = style_dir / "ColorPalette.xml"
        if color_xml.exists():
            config["colors"] = parse_color_palette(color_xml)

        # Typography
        format_xml = style_dir / "FormatWizard.xml"
        if format_xml.exists():
            config["typography"] = parse_format_wizard(format_xml)

        # Footer/margins
        bcg_xml = style_dir / "BCG.xml"
        if bcg_xml.exists():
            config["layout"] = parse_bcg_xml(bcg_xml)

        # Determine template name
        template_name = config.get("style", {}).get("name", "")
        if not template_name:
            template_name = config.get("metadata", {}).get("Template name", "")
        if not template_name:
            template_name = ee4p_path.stem

        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "_", template_name).lower().strip("_")

        # Create output directory
        out_path = Path(output_dir) / safe_name
        out_path.mkdir(parents=True, exist_ok=True)

        # Copy template PPTX files
        template_pptx = style_dir / "Template.pptx"
        if template_pptx.exists():
            shutil.copy2(template_pptx, out_path / "master.pptx")
            _clean_orphaned_rels(out_path / "master.pptx")
            config["template_file"] = "master.pptx"

        input_template = style_dir / "InputTemplate.pptx"
        if input_template.exists():
            shutil.copy2(input_template, out_path / "input_template.pptx")

        # Layout map (standardized name -> original name)
        layouts = config.get("style", {}).get("layouts", [])
        layout_map = {}
        detail_layout_map = {}
        for name in layouts:
            std_name = re.sub(r"^Client\s+", "", name)
            is_detail = std_name.startswith("D. ")
            base_name = re.sub(r"^D\.\s+", "", std_name)
            if is_detail:
                detail_layout_map[base_name] = name
            else:
                if base_name not in layout_map:
                    layout_map[base_name] = name
        config["layout_map"] = layout_map
        if detail_layout_map:
            config["detail_layout_map"] = detail_layout_map

        # Fly-zone from drawing area
        da = config.get("style", {}).get("drawing_area", {})
        if da:
            config["fly_zone"] = {
                "content_top": da["top"],
                "content_left": da["left"],
                "content_width": da["width"],
                "content_height": da["height"],
                "content_bottom": round(da["top"] + da["height"], 2),
            }

        # Normalize
        pptx_path = out_path / config.get("template_file", "master.pptx")
        config = normalize_config(config, safe_name, pptx_path)

        # Write template.json
        with open(out_path / "template.json", "w") as f:
            json.dump(config, f, indent=2)

        # Runtime conveniences for same-session usage with BCGDeck(theme_config=config).
        # These are not written to template.json because they are environment-specific.
        config["_template_dir"] = str(out_path)
        config["_master_pptx"] = str(out_path / config.get("template_file", "master.pptx"))

        print(f"\nTemplate ingested successfully!")
        print(f"  Name: {template_name}")
        print(f"  Output: {out_path}")
        print(f"  Font: {config.get('font', 'unknown')}")
        print(f"  Layouts: {len(layouts)}")
        print(f"  Colors: {len(config.get('colors', {}))}")
        print(f"  Color aliases: {list(config.get('color_aliases', {}).keys())}")
        print(f"  Scheme colors: {list(config.get('scheme_colors', {}).keys())}")
        print(f"  XML layout map: {len(config.get('xml_layout_map', {}))} layouts")
        print(f"  Layout geometry: {len(config.get('layout_geometry', {}))} layouts analyzed")
        if "fly_zone" in config:
            fz = config["fly_zone"]
            print(f"  Fly-zone: y={fz['content_top']}\" to y={fz['content_bottom']}\"")
        semantic = config.get("semantic_layout_map", {})
        if semantic:
            print(f"  Semantic layouts: {list(semantic.keys())}")

        # The returned config is always valid for the current run.
        # Longer-lived availability depends on runtime capabilities:
        # workspace-capable runtimes may persist it via template_registry.save_template(),
        # while ephemeral runtimes may keep it run-scoped or require skill rebuild.

        return config


def _get_primary_color_for_registry(config):
    aliases = config.get("color_aliases", {})
    if "GREEN" in aliases:
        return f"#{aliases['GREEN']}"
    scheme = config.get("scheme_colors", {})
    if "accent1" in scheme:
        return scheme["accent1"]
    return "#29BA74"


def _rebuild_skill_with_template(config, template_dir):
    """Rebuild the .skill ZIP with the client template bundled inside.

    This is the fallback persistence path for runtimes whose filesystem is
    ephemeral and which do not expose workspace-level template persistence.

    Returns:
        dict with rebuild_succeeded, updated_skill_path, persistence_message
    """
    import zipfile as _zf

    result = {
        "rebuild_succeeded": False,
        "updated_skill_path": None,
        "persistence_message": "",
    }

    skill_root = find_skill_root()
    template_name = config.get("name", "unknown")

    # Find the installed skill location (Claude.ai mounts at /mnt/skills/user/)
    skill_sources = [
        Path("/mnt/skills/user/deckster-slide-generator"),
        skill_root,
    ]
    skill_src = None
    for candidate in skill_sources:
        if (candidate / "SKILL.md").exists():
            skill_src = candidate
            break

    if skill_src is None:
        print("  Could not find skill source for rebuild.")
        result["persistence_message"] = "Could not locate skill source for rebuild."
        return result

    # Build in a writable temp location
    _tmpdir = os.environ.get("TMPDIR", "/tmp")
    out_skill = Path(_tmpdir) / "deckster-slide-generator-updated.skill"

    with _zf.ZipFile(str(out_skill), 'w', _zf.ZIP_DEFLATED) as zout:
        # Deduplication: track written archive paths to prevent duplicate entries
        seen_paths = set()
        skipped = 0

        def _write(full_path, arcname):
            nonlocal skipped
            if arcname in seen_paths:
                skipped += 1
                return
            seen_paths.add(arcname)
            zout.write(full_path, arcname)

        def _writestr(arcname, data):
            nonlocal skipped
            if arcname in seen_paths:
                skipped += 1
                return
            seen_paths.add(arcname)
            zout.writestr(arcname, data)

        # 1. SKILL.md first
        skill_md = skill_src / "SKILL.md"
        if skill_md.exists():
            _write(str(skill_md), "SKILL.md")

        # 2. Updated registry BEFORE the walk so it takes precedence
        #    over any stale _registry.json in the skill source.
        from template_registry import _load_registry
        registry = _load_registry()
        registry["templates"][template_name] = {
            "name": config.get("description", template_name).replace(" (ingested from ee4p)", ""),
            "font": config.get("font", "unknown"),
            "primary_color": _get_primary_color_for_registry(config),
            "source": config.get("source", "ee4p"),
        }
        _writestr("styles/templates/_registry.json", json.dumps(registry, indent=2))

        # 3. All remaining skill source files
        for root, dirs, files in os.walk(str(skill_src)):
            dirs[:] = [d for d in dirs if d not in ('__pycache__', '.DS_Store')]
            for fname in files:
                if fname == '.DS_Store':
                    continue
                full = os.path.join(root, fname)
                arcname = os.path.relpath(full, str(skill_src))
                _write(full, arcname)

        # 4. Client template files into styles/templates/<name>/
        tmpl_dir = Path(template_dir)
        for root, dirs, files in os.walk(str(tmpl_dir)):
            for fname in files:
                full = os.path.join(root, fname)
                arcname = "styles/templates/" + template_name + "/" + os.path.relpath(full, str(tmpl_dir))
                _write(full, arcname)

        if skipped:
            print(f"  Deduped zip: skipped {skipped} duplicate archive path(s).")

    size_mb = out_skill.stat().st_size / 1024 / 1024

    # Surface to outputs for download
    preferred_outputs = Path("/mnt/user-data/outputs/deckster-slide-generator")
    fallback_outputs = Path("/mnt/user-data/outputs")
    surfaced_path = None

    try:
        preferred_outputs.mkdir(parents=True, exist_ok=True)
        surfaced_path = preferred_outputs / out_skill.name
        shutil.copy2(str(out_skill), str(surfaced_path))
    except Exception:
        try:
            fallback_outputs.mkdir(parents=True, exist_ok=True)
            surfaced_path = fallback_outputs / out_skill.name
            shutil.copy2(str(out_skill), str(surfaced_path))
        except Exception:
            # Last resort: use the /tmp path
            surfaced_path = out_skill

    print(f"\n  UPDATED SKILL: {surfaced_path} ({size_mb:.1f} MB)")
    print(f"  Download this file and re-upload it to Claude to permanently save the '{template_name}' template.")

    result["rebuild_succeeded"] = True
    result["updated_skill_path"] = str(surfaced_path)
    result["persistence_message"] = (
        "I created an updated version of this skill with your template. "
        "Use the updated .skill artifact to keep this template for future sessions."
    )
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Ingest .ee4p files as deckster-slide-generator template configs"
    )
    parser.add_argument("file", help="Path to .ee4p file")
    parser.add_argument(
        "--output-dir", "-o",
        default="templates/",
        help="Output directory for template (default: templates/)",
    )
    args = parser.parse_args()

    file_path = Path(args.file)
    if file_path.suffix.lower() != ".ee4p":
        print(f"Error: Expected .ee4p file, got: {file_path.suffix}")
        sys.exit(1)

    ingest_ee4p(args.file, args.output_dir)


if __name__ == "__main__":
    main()

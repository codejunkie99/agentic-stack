"""
BCG deck QA checker for the Build -> QA workflow.

`check_deck()` remains the authoritative deck-level reducer. Orchestrated
runtimes may fan out rendered-image inspection or per-slide review work, then
feed the findings back into the same blocking QA loop.
"""
import xml.etree.ElementTree as ET
import math, os, re, shutil, sys
from collections import defaultdict
from pathlib import Path
from pptx_utils import unpack, make_work_dir
from layout_semantics import semantic_behavior

_VALID_HEX_6 = re.compile(r'^[0-9A-Fa-f]{6}$')

NS = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
}

# Default BCG palette — used only when no theme_config is provided.
# When a theme_config IS provided, colors are built dynamically from it.
_BCG_DEFAULT_COLORS = {
    '29BA74','197A56','03522D','575757','FFFFFF','F2F2F2',
    '3EAD92','D4DF33','6E6F73','295E7E','2E3558','B0B0B0',
    'D64454','7C7C7C','F59E0B','000000',
    'E0E0E0','E8E8E8','D0D0D0','F3F3F3','B1B1B7',
}
_BCG_DEFAULT_FONT = 'Trebuchet MS'
_BCG_DEFAULT_SOURCE_Y = 6.74
_BCG_DEFAULT_CONTENT_END_Y = 6.50
_BCG_DEFAULT_CONTENT_LEFT = 0.69

# Neutral colors accepted for ANY template (grays, black, white)
_UNIVERSAL_NEUTRAL_COLORS = {
    'FFFFFF', 'F2F2F2', 'F3F3F3', 'E0E0E0', 'E8E8E8', 'D0D0D0',
    'B0B0B0', 'B1B1B7', '000000', '7C7C7C',
}

# Light-colored text values (invisible on light backgrounds)
_LIGHT_TEXT_COLORS = {'FFFFFF', 'F2F2F2', 'F3F3F3', 'E8E8E8', 'E0E0E0'}

# Module-level accent fills — updated dynamically by check_deck() from theme_config.
# Used by _shape_has_dark_fill() which is called before the local variable is available.
_accent_panel_fills = {'29BA74', '197A56', '03522D', '3EAD92'}

SOURCE_Y = _BCG_DEFAULT_SOURCE_Y


def _bounds_record(left_x, left_w, right_x, right_w, y=1.70, y_end=6.50):
    x = min(left_x, right_x)
    x_end = max(left_x + left_w, right_x + right_w)
    return {
        'x': x,
        'y': y,
        'w': round(x_end - x, 2),
        'h': round(y_end - y, 2),
        'x_end': round(x_end, 2),
        'y_end': round(y_end, 2),
        'left_x': left_x,
        'left_w': left_w,
        'right_x': right_x,
        'right_w': right_w,
    }


_BCG_DEFAULT_LAYOUT_BOUNDS = {
    'slideLayout8.xml': _bounds_record(0.69, 6.80, 8.20, 4.30),   # green_highlight
    'slideLayout9.xml': _bounds_record(0.69, 3.50, 4.80, 8.00),   # green_one_third
    'slideLayout10.xml': _bounds_record(0.69, 5.00, 6.67, 6.67),  # green_half
    'slideLayout11.xml': _bounds_record(0.69, 7.50, 8.55, 4.78),  # green_two_third
    'slideLayout12.xml': _bounds_record(0.69, 3.50, 5.20, 7.50),  # left_arrow
    'slideLayout13.xml': _bounds_record(0.69, 3.50, 5.20, 7.50),  # green_left_arrow
    'slideLayout16.xml': _bounds_record(0.69, 5.20, 7.00, 5.40),  # arrow_half
    'slideLayout17.xml': _bounds_record(0.69, 5.20, 7.00, 5.40),  # green_arrow_half
    'slideLayout36.xml': _bounds_record(0.69, 6.80, 8.20, 4.30),  # d_green_highlight
    'slideLayout38.xml': _bounds_record(0.69, 3.50, 4.80, 8.00),  # d_green_one_third
    'slideLayout39.xml': _bounds_record(0.69, 5.00, 6.67, 6.67),  # d_green_half
    'slideLayout40.xml': _bounds_record(0.69, 7.50, 8.55, 4.78),  # d_green_two_third
    'slideLayout41.xml': _bounds_record(0.69, 3.50, 5.20, 7.50),  # d_left_arrow
    'slideLayout42.xml': _bounds_record(0.69, 3.50, 5.20, 7.50),  # d_green_left_arrow
    'slideLayout45.xml': _bounds_record(0.69, 5.20, 7.00, 5.40),  # d_arrow_half
    'slideLayout46.xml': _bounds_record(0.69, 5.20, 7.00, 5.40),  # d_green_arrow_half
}

# Detail layouts (d_ prefix = "detail") -- white/light BG, smaller titles, for data-rich slides
# Light text placed directly on these backgrounds is invisible -- must use DARK_TEXT
_DETAIL_LAYOUTS = {
    'slideLayout29.xml',  # D. Title
    'slideLayout30.xml',  # D. Title only
    'slideLayout31.xml',  # D. Title and text
    'slideLayout32.xml',  # D. Gray slice
    'slideLayout33.xml',  # D. Section header box
    'slideLayout34.xml',  # D. Section header line
    'slideLayout35.xml',  # D. White one third
    'slideLayout36.xml',  # D. Green highlight
    'slideLayout38.xml',  # D. Green one third
    'slideLayout39.xml',  # D. Green half
    'slideLayout40.xml',  # D. Green two third
    'slideLayout41.xml',  # D. Left arrow
    'slideLayout42.xml',  # D. Green left arrow
    'slideLayout43.xml',  # D. Arrow one third
    'slideLayout45.xml',  # D. Arrow half
    'slideLayout47.xml',  # D. Arrow two third
    'slideLayout49.xml',  # D. Big statement green
    'slideLayout50.xml',  # D. Big statement icon
    'slideLayout51.xml',  # D. Quote
    'slideLayout52.xml',  # D. Special gray
    'slideLayout54.xml',  # D. Blank green
    'slideLayout55.xml',  # D. Blank
    'slideLayout56.xml',  # D. Disclaimer
    'slideLayout57.xml',  # D. End
}

# Green-panel layouts where white text on the green area is expected
_GREEN_PANEL_LAYOUTS = {
    'slideLayout9.xml',   # Green one third
    'slideLayout10.xml',  # Green half
    'slideLayout11.xml',  # Green two third
    'slideLayout13.xml',  # Green left arrow
    'slideLayout20.xml',  # Big statement green
    'slideLayout38.xml',  # D. Green one third
    'slideLayout39.xml',  # D. Green half
    'slideLayout40.xml',  # D. Green two third
    'slideLayout42.xml',  # D. Green left arrow
    'slideLayout49.xml',  # D. Big statement green
}

# Layouts that are structural (no visual element check needed)
STRUCTURAL_LAYOUTS = {
    # Standard structural layouts
    'slideLayout1.xml',   # Title
    'slideLayout5.xml',   # Section header box
    'slideLayout6.xml',   # Section header line
    'slideLayout20.xml',  # Big statement green
    'slideLayout21.xml',  # Big statement icon
    'slideLayout22.xml',  # Quote
    'slideLayout26.xml',  # Disclaimer
    'slideLayout27.xml',  # End
    # Detail structural layouts
    'slideLayout29.xml',  # D. Title
    'slideLayout33.xml',  # D. Section header box
    'slideLayout34.xml',  # D. Section header line
    'slideLayout49.xml',  # D. Big statement green
    'slideLayout50.xml',  # D. Big statement icon
    'slideLayout51.xml',  # D. Quote
    'slideLayout56.xml',  # D. Disclaimer
    'slideLayout57.xml',  # D. End
}

_TITLE_LEFT_PROTECTED_LAYOUTS = {
    'slideLayout9.xml', 'slideLayout10.xml', 'slideLayout11.xml',
    'slideLayout12.xml', 'slideLayout13.xml',
    'slideLayout38.xml', 'slideLayout39.xml', 'slideLayout40.xml',
    'slideLayout41.xml', 'slideLayout42.xml',
}

_TITLE_IMAGE_ONLY_LAYOUTS = {
    'slideLayout10.xml', 'slideLayout11.xml',
    'slideLayout39.xml', 'slideLayout40.xml',
}

_STATEMENT_LAYOUTS = {
    'slideLayout20.xml', 'slideLayout21.xml',
    'slideLayout49.xml', 'slideLayout50.xml',
}

_TITLE_SLIDE_LAYOUTS = {
    'slideLayout1.xml', 'slideLayout29.xml',
}

def _get_slide_layout(work_dir, snum):
    """Get the layout filename for a slide."""
    rels = work_dir / 'ppt' / 'slides' / '_rels' / f'slide{snum}.xml.rels'
    if not rels.exists(): return ''
    tree = ET.parse(rels)
    for rel in tree.getroot():
        target = rel.get('Target', '')
        if 'slideLayout' in target:
            return os.path.basename(target)
    return ''

def _is_footer_element(sp, NS):
    """Check if a shape is a footer element (source, page number, copyright)."""
    off = sp.find('.//a:off', NS)
    if off is None: return False
    y = int(off.get('y', '0')) / 914400
    if y >= 6.60: return True  # Footer zone
    # Also check for source text
    for t in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
        if t.text and t.text.strip().startswith('Source:'): return True
    return False

def _shape_has_dark_fill(sp, NS):
    """Check if a shape or its parent group has a dark/accent fill behind it.

    Uses luminance-based detection so it works with any color palette
    (BCG default, client ee4p themes, etc.), not just hardcoded BCG hex values.
    A fill is considered 'dark' if its relative luminance is <= 0.35 (roughly
    equivalent to mid-gray or darker -- safe for white text at 3:1+ contrast).
    The core BCG accent green family is also treated as a valid light-text
    surface even though it sits slightly above that luminance threshold.
    """
    for sf in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}solidFill'):
        srgb = sf.find('{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr')
        if srgb is not None:
            val = srgb.get('val', '').upper()
            if len(val) == 6:
                if val in _accent_panel_fills:
                    return True
                try:
                    r, g, b = int(val[0:2], 16), int(val[2:4], 16), int(val[4:6], 16)
                    # Relative luminance per WCAG 2.0
                    def _ch(c):
                        v = c / 255.0
                        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
                    lum = 0.2126 * _ch(r) + 0.7152 * _ch(g) + 0.0722 * _ch(b)
                    if lum <= 0.35:
                        return True
                except ValueError:
                    pass
    for grad in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}gradFill'):
        for srgb in grad.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr'):
            val = srgb.get('val', '').upper()
            if len(val) != 6:
                continue
            if val in _accent_panel_fills:
                return True
            rgb = _hex_to_rgb_qa(val)
            if rgb is not None and _luminance(rgb) <= 0.35:
                return True
    return False

# ============================================================
# v6.7 QA UPGRADES -- Partner-level visual quality checks
# ============================================================

_EMU = 914400  # EMU per inch

# Placeholder/unfinished text patterns
_PLACEHOLDER_RE = re.compile(
    r'\[TODO\]|\[TBD\]|\[INSERT\]|\[REPLACE\]|\{[A-Z_]+\}|'
    r'lorem ipsum|placeholder text|XXXX|sample text here',
    re.IGNORECASE
)

# Font-specific average character width ratios (char_width = size_pt * ratio / 72 inches)
_FONT_WIDTH_RATIOS = {
    'trebuchet ms': 0.52, 'arial': 0.48, 'calibri': 0.45,
    'americansans': 0.48, 'helvetica': 0.48, 'times new roman': 0.45,
}

def _hex_to_rgb_qa(hex_color):
    if not hex_color or len(hex_color) != 6:
        return None
    try:
        return (int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))
    except ValueError:
        return None

def _luminance(rgb):
    def _ch(c):
        v = c / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * _ch(rgb[0]) + 0.7152 * _ch(rgb[1]) + 0.0722 * _ch(rgb[2])

def _wcag_contrast(color_a, color_b):
    """WCAG 2.0 contrast ratio between two hex colors."""
    rgb_a = _hex_to_rgb_qa(color_a)
    rgb_b = _hex_to_rgb_qa(color_b)
    if rgb_a is None or rgb_b is None:
        return 0.0
    la, lb = _luminance(rgb_a), _luminance(rgb_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)

def _extract_shape_bounds(sp):
    """Extract (x, y, w, h) in inches from a shape element. Returns None if missing."""
    off = sp.find('.//a:off', NS)
    ext = sp.find('.//a:ext', NS)
    if off is None or ext is None:
        return None
    try:
        x = int(off.get('x', 0)) / _EMU
        y = int(off.get('y', 0)) / _EMU
        w = int(ext.get('cx', 0)) / _EMU
        h = int(ext.get('cy', 0)) / _EMU
        return (x, y, w, h)
    except (ValueError, TypeError):
        return None

def _get_shape_fill_color(sp):
    """Get the solid fill color of a shape's geometry, or None.

    Only checks the shape properties (spPr) -- NOT text run fills (rPr/solidFill)
    which represent text color, not shape background.
    """
    spPr = sp.find('.//p:spPr', NS)
    if spPr is not None:
        sf = spPr.find('a:solidFill', NS)
        if sf is not None:
            srgb = sf.find('a:srgbClr', NS)
            if srgb is not None:
                return srgb.get('val', '').upper()
        grad = spPr.find('a:gradFill', NS)
        if grad is not None:
            srgb = grad.find('.//a:srgbClr', NS)
            if srgb is not None:
                return srgb.get('val', '').upper()
    return None

def _find_background_for_shape(all_shapes_with_bounds, target_bounds, slide_bg='F2F2F2'):
    """Find the fill color of the shape directly behind the target.

    Prefer the smallest filled shape that contains the target center. This is
    more accurate for badges/textboxes placed on top of larger cards because it
    selects the immediate container rather than an unrelated broader surface
    later in the XML tree.
    """
    tx, ty, tw, th = target_bounds
    tcx, tcy = tx + tw/2, ty + th/2  # center of target

    bg_color = slide_bg
    best_area = None
    best_index = -1
    for idx, (bounds, fill) in enumerate(all_shapes_with_bounds):
        if fill is None or bounds is None:
            continue
        bx, by, bw, bh = bounds
        # Check if target center is inside this shape
        if bx <= tcx <= bx + bw and by <= tcy <= by + bh:
            area = bw * bh
            if best_area is None or area < best_area - 0.01 or (abs(area - best_area) <= 0.01 and idx > best_index):
                bg_color = fill
                best_area = area
                best_index = idx
    return bg_color

def _check_shape_overlaps(shapes_with_info, snum):
    """Detect overlapping content shapes.

    Intentional overlaps (text on rectangle = card pattern) are excluded.
    Only flags overlaps between shapes of similar size (both large).

    Args:
        shapes_with_info: list of (name, x, y, w, h) tuples
    Returns:
        list of (snum, severity, message) tuples
    """
    issues = []
    n = len(shapes_with_info)
    for i in range(n):
        na, xa, ya, wa, ha = shapes_with_info[i]
        area_a = wa * ha
        for j in range(i + 1, n):
            nb, xb, yb, wb, hb = shapes_with_info[j]
            area_b = wb * hb
            # Skip intentional stacking patterns:
            # 1. One shape much smaller (text-on-rectangle)
            size_ratio = min(area_a, area_b) / max(area_a, area_b) if max(area_a, area_b) > 0 else 0
            if size_ratio < 0.3:
                continue
            # 2. Same position (deliberate layering: rect background + content)
            if abs(xa - xb) < 0.15 and abs(ya - yb) < 0.15:
                continue
            # 3. One fully contains the other (card pattern)
            a_contains_b = xa <= xb and ya <= yb and (xa+wa) >= (xb+wb) and (ya+ha) >= (yb+hb)
            b_contains_a = xb <= xa and yb <= ya and (xb+wb) >= (xa+wa) and (yb+hb) >= (ya+ha)
            if a_contains_b or b_contains_a:
                continue
            x_overlap = max(0, min(xa+wa, xb+wb) - max(xa, xb))
            y_overlap = max(0, min(ya+ha, yb+hb) - max(ya, yb))
            if x_overlap > 0.20 and y_overlap > 0.20:
                area = x_overlap * y_overlap
                if area > 0.50:
                    issues.append((snum, 'HIGH', f'Shape overlap: {na} and {nb} ({area:.1f} sq in)'))
                elif area > 0.25:
                    issues.append((snum, 'MEDIUM', f'Minor overlap: {na} and {nb} ({area:.2f} sq in)'))
    return issues

def _check_placeholder_text(texts, snum):
    """Detect placeholder/unfinished text."""
    issues = []
    for text in texts:
        if _PLACEHOLDER_RE.search(text):
            issues.append((snum, 'HIGH', f'Placeholder text: "{text[:50]}"'))
    return issues

def _check_edge_margins(shapes_with_info, snum, slide_w=13.33, slide_h=7.50):
    """Check that content doesn't bleed too close to slide edges."""
    issues = []
    for name, x, y, w, h in shapes_with_info:
        if x < 0.30:
            issues.append((snum, 'MEDIUM', f'{name} too close to left edge ({x:.2f}")'))
        if (x + w) > (slide_w - 0.25):
            issues.append((snum, 'MEDIUM', f'{name} too close to right edge ({x+w:.2f}")'))
    return issues


def _check_out_of_bounds(all_shapes, snum, slide_w=13.33, slide_h=7.50):
    """Check if any shape's bounding box extends outside the slide boundaries.

    Flags as HIGH any shape that bleeds past (0, 0) to (13.33", 7.50").
    Uses 0.05" tolerance for rounding/anti-aliasing artifacts.
    """
    issues = []
    tol = 0.05
    seen = set()  # dedupe by direction per shape
    for name, x, y, w, h in all_shapes:
        if w < 0.05 or h < 0.05:
            continue  # skip degenerate shapes (lines, dots)
        key = None
        if x < -tol:
            key = (name, 'left')
            issues.append((snum, 'HIGH',
                f'OUT OF BOUNDS: {name} extends past left edge (x={x:.2f}")'))
        if y < -tol:
            key = (name, 'top')
            issues.append((snum, 'HIGH',
                f'OUT OF BOUNDS: {name} extends past top edge (y={y:.2f}")'))
        if (x + w) > slide_w + tol:
            key = (name, 'right')
            issues.append((snum, 'HIGH',
                f'OUT OF BOUNDS: {name} extends past right edge (x+w={x+w:.2f}", slide={slide_w}")'))
        if (y + h) > slide_h + tol:
            key = (name, 'bottom')
            issues.append((snum, 'HIGH',
                f'OUT OF BOUNDS: {name} extends past bottom edge (y+h={y+h:.2f}", slide={slide_h}")'))
    return issues


def _check_text_overlaps(text_shapes, snum):
    """Detect overlapping text-bearing shapes.

    Unlike _check_shape_overlaps (which filters aggressively for card patterns),
    this specifically targets shapes that BOTH contain visible text. When two
    textboxes overlap, the text becomes unreadable regardless of intent.

    Exemptions:
    - One shape fully contains the other (card header inside card body)
    - Shapes at nearly identical position (deliberate layering)
    - Overlap area < 0.15 sq in (incidental edge touching)
    """
    issues = []
    n = len(text_shapes)
    flagged = set()  # avoid duplicate pairs
    for i in range(n):
        na, xa, ya, wa, ha = text_shapes[i]
        for j in range(i + 1, n):
            nb, xb, yb, wb, hb = text_shapes[j]
            # Skip deliberate layering (same position)
            if abs(xa - xb) < 0.10 and abs(ya - yb) < 0.10:
                continue
            # Skip full containment (card + text on card)
            a_contains_b = xa <= xb + 0.05 and ya <= yb + 0.05 and (xa+wa) >= (xb+wb) - 0.05 and (ya+ha) >= (yb+hb) - 0.05
            b_contains_a = xb <= xa + 0.05 and yb <= ya + 0.05 and (xb+wb) >= (xa+wa) - 0.05 and (yb+hb) >= (ya+ha) - 0.05
            if a_contains_b or b_contains_a:
                continue
            # Calculate overlap
            x_overlap = max(0, min(xa+wa, xb+wb) - max(xa, xb))
            y_overlap = max(0, min(ya+ha, yb+hb) - max(ya, yb))
            area = x_overlap * y_overlap
            if area > 0.15:
                pair = tuple(sorted([na, nb]))
                if pair not in flagged:
                    flagged.add(pair)
                    issues.append((snum, 'HIGH',
                        f'TEXT OVERLAP: "{na}" and "{nb}" overlap by {area:.2f} sq in — text is unreadable'))
    return issues


def _contains_bounds(outer, inner, tol=0.03):
    """Return True when the outer bounds fully contain the inner bounds."""
    ox, oy, ow, oh = outer
    ix, iy, iw, ih = inner
    return (
        ox - tol <= ix and
        oy - tol <= iy and
        ox + ow + tol >= ix + iw and
        oy + oh + tol >= iy + ih
    )


def _build_layout_bounds_map(theme_config):
    """Build a mapping from slideLayoutNN.xml -> content bounds dict.

    Uses layout_geometry from template.json to resolve per-layout content zones.
    Returns a dict: {'slideLayout8.xml': {'left_w': 6.84, 'right_x': 8.20, ...}, ...}
    Only includes layouts that have split zone data (left_x/right_x).
    """
    if not theme_config:
        return dict(_BCG_DEFAULT_LAYOUT_BOUNDS)

    slide_w = theme_config.get('width', 13.33)
    slide_h = theme_config.get('height', 7.50)
    layout_geom = theme_config.get('layout_geometry', {})
    fz = theme_config.get('fly_zone', {})
    content_left = fz.get('content_left', 0.69)

    bounds_map = {}
    for slug, info in layout_geom.items():
        filename = info.get('filename', '')
        if not filename:
            continue

        cz = info.get('content_zone')
        if not cz:
            continue
        cb = cz.get('content_bounds')
        if not cb:
            continue

        layout_class = cz.get('layout_class', 'full_page')
        title_width_cat = cz.get('title_width', 'wide')

        # Convert content_bounds percentages to inches
        x = round(cb.get('x_pct', 0) / 100.0 * slide_w, 2)
        y = round(cb.get('y_pct', 0) / 100.0 * slide_h, 2)
        w = round(cb.get('w_pct', 0) / 100.0 * slide_w, 2)
        h = round(cb.get('h_pct', 0) / 100.0 * slide_h, 2)
        x_end = round(x + w, 2)

        result = {'x': x, 'y': y, 'w': w, 'h': h, 'x_end': x_end, 'y_end': round(y + h, 2)}

        # Find title placeholder
        title_ph = None
        for ph in info.get('placeholders', []):
            if ph.get('type') == 'title':
                title_ph = ph.get('bounds', {})
                break

        if layout_class == 'split_panel' and title_ph:
            title_x_end = round((title_ph.get('x_pct', 0) + title_ph.get('w_pct', 0)) / 100.0 * slide_w, 2)
            result['right_x'] = x
            result['right_w'] = w
            result['left_x'] = round(title_ph.get('x_pct', 0) / 100.0 * slide_w, 2)
            result['left_w'] = round(title_x_end - result['left_x'], 2)
            bounds_map[filename] = result
        elif title_width_cat == 'narrow' and title_ph:
            title_x_end = round((title_ph.get('x_pct', 0) + title_ph.get('w_pct', 0)) / 100.0 * slide_w, 2)
            gap = round(0.05 * slide_w, 2)
            result['left_x'] = content_left
            result['left_w'] = round(title_x_end - content_left, 2)
            result['right_x'] = round(title_x_end + gap, 2)
            result['right_w'] = round(x_end - result['right_x'], 2)
            bounds_map[filename] = result

    return bounds_map


def _check_zone_boundary_violations(all_shapes, snum, layout_bounds):
    """Check if content shapes cross the left/right zone boundary on split layouts.

    Args:
        all_shapes: list of (name, x, y, w, h)
        snum: slide number
        layout_bounds: dict with 'left_w', 'left_x', 'right_x' etc.
    Returns:
        list of (snum, severity, message) tuples
    """
    issues = []
    if not layout_bounds or 'left_w' not in layout_bounds or 'right_x' not in layout_bounds:
        return issues

    left_x = layout_bounds.get('left_x', 0.69)
    left_end = round(left_x + layout_bounds['left_w'], 2)
    right_x = layout_bounds['right_x']
    tol = 0.15  # tolerance for minor overflows

    for name, x, y, w, h in all_shapes:
        if w < 0.3 or h < 0.1:
            continue  # skip tiny shapes
        if y >= SOURCE_Y - 0.12 and h <= 0.35:
            continue  # source/footer text is allowed to span the footer band
        shape_end = x + w
        shape_mid = x + w / 2

        # Shape starts in left zone but bleeds into right zone
        if x < left_end and shape_end > right_x + tol and shape_mid < right_x:
            issues.append((snum, 'HIGH',
                f'ZONE BLEED: "{name}" in left zone extends past split boundary '
                f'(x+w={shape_end:.2f}", boundary at {right_x:.2f}")'))

    return issues


def _check_protected_left_panel_occupancy(all_shapes, snum, layout_bounds):
    """Flag authored content placed inside reserved left title panels."""
    issues = []
    if not layout_bounds or 'right_x' not in layout_bounds:
        return issues

    right_x = layout_bounds['right_x']
    tol = 0.08

    for name, x, y, w, h in all_shapes:
        if w < 0.3 or h < 0.1:
            continue
        if y >= 6.55:
            continue  # footer/source area is allowed on these layouts

        shape_mid = x + w / 2
        if shape_mid < right_x - tol:
            issues.append((snum, 'HIGH',
                f'TITLE PANEL OCCUPANCY: "{name}" sits in the reserved left title panel '
                f'(content midpoint {shape_mid:.2f}", content must start at {right_x:.2f}")'))

    return issues


def _check_title_image_only_text(text_shapes, snum):
    """Image-led title layouts should not contain body text boxes beyond the title/source."""
    issues = []
    for name, x, y, w, h in text_shapes:
        if y >= 6.55:
            continue
        issues.append((snum, 'HIGH',
            f'TEXT ON TITLE/IMAGE-ONLY LAYOUT: "{name}" adds body text to a title-led image layout'))
    return issues


def _check_statement_layout_text(text_shapes, snum):
    """Statement layouts should not contain extra body textboxes."""
    issues = []
    for name, x, y, w, h in text_shapes:
        if y >= 6.55:
            continue
        issues.append((snum, 'HIGH',
            f'TEXT ON STATEMENT LAYOUT: "{name}" adds unsupported body text to a statement slide'))
    return issues


def _read_slide_dimensions(pptx_path):
    """Read slide width and height from the PPTX's presentation.xml sldSz element.
    Returns (width_inches, height_inches). Falls back to 16:9 standard if not found.
    """
    import zipfile as _zf
    try:
        with _zf.ZipFile(str(pptx_path)) as zf:
            pres_xml = ET.fromstring(zf.read('ppt/presentation.xml'))
            for elem in pres_xml.iter():
                if 'sldSz' in elem.tag:
                    cx = int(elem.get('cx', 0)) / _EMU
                    cy = int(elem.get('cy', 0)) / _EMU
                    if cx > 0 and cy > 0:
                        return (round(cx, 3), round(cy, 3))
    except Exception:
        pass
    return (13.333, 7.500)  # 16:9 default


def check_deck(pptx_path, verbose=True, theme_config=None):
    """Check a PPTX deck for quality issues.

    Args:
        pptx_path: Path to the PPTX file.
        verbose: Print progress.
        theme_config: Path to template.json or dict. When provided, validates
                     against the client palette/font instead of BCG defaults.
                     If omitted, falls back to the active theme from BCGDeck.
    """
    # Auto-detect the active theme when not explicitly provided.
    # qa.py lives in scripts/ alongside bcg_template.py, so we can
    # access the module's global directly via sys.modules.
    if theme_config is None:
        for _mod_name in ('scripts.bcg_template', 'bcg_template'):
            _mod = sys.modules.get(_mod_name)
            if _mod is not None:
                _atc = getattr(_mod, '_ACTIVE_THEME_CONFIG', None)
                if _atc is not None:
                    theme_config = _atc
                    break
    # Read actual slide dimensions from the PPTX (supports non-16:9 templates)
    slide_w, slide_h = _read_slide_dimensions(pptx_path)

    if theme_config is not None:
        if isinstance(theme_config, (str, Path)):
            import json as _json
            with open(theme_config) as _f:
                theme_config = _json.load(_f)
        # Build valid colors dynamically from the template's color table.
        _valid_colors = set(_UNIVERSAL_NEUTRAL_COLORS)
        for _name, _info in theme_config.get('colors', {}).items():
            if isinstance(_info, dict):
                _hex_val = _info.get('hex', '')
            else:
                _hex_val = str(_info)
            if _hex_val and len(_hex_val) == 6:
                _valid_colors.add(_hex_val.upper())
        for _k, _v in theme_config.get('color_aliases', {}).items():
            if _v and len(_v) == 6:
                _valid_colors.add(_v.upper())
        # Also include scheme colors (dk1, lt1, accent1, etc.)
        for _k, _v in theme_config.get('scheme_colors', {}).items():
            if isinstance(_v, str) and len(_v) == 6:
                _valid_colors.add(_v.upper())
        _expected_font = theme_config.get('font') or theme_config.get('font_family') or _BCG_DEFAULT_FONT
        # Build accent fills from template's green/accent colors
        global _accent_panel_fills
        _accent_panel_fills = set()
        _ca = theme_config.get('color_aliases', {})
        for _alias in ('GREEN', 'DARK_GREEN', 'DEEP_GREEN', 'BCG_GREEN', 'TEAL',
                        'ACCENT1', 'ACCENT2', 'ACCENT3'):
            _av = _ca.get(_alias, '')
            if _av and len(_av) == 6:
                _accent_panel_fills.add(_av.upper())
        if not _accent_panel_fills:
            _accent_panel_fills = {'29BA74', '197A56', '03522D', '3EAD92'}
        # Dynamic content boundaries from fly_zone
        _fz = theme_config.get('fly_zone', {})
        _content_end_y = _fz.get('content_bottom', _BCG_DEFAULT_CONTENT_END_Y)
        _source_y = _fz.get('source_y', _content_end_y + 0.24)
        _content_left = _fz.get('content_left', _BCG_DEFAULT_CONTENT_LEFT)
        # Slide background from template — used for contrast checks.
        # Dark templates (bg1=000000) need white text; light templates need dark text.
        _ca = theme_config.get('color_aliases', {})
        _sc = theme_config.get('scheme_colors', {})
        _slide_bg = (_ca.get('SLIDE_BG') or _sc.get('bg1') or 'F2F2F2').lstrip('#')
        _slide_bg_detail = (_ca.get('WHITE') or _sc.get('lt1') or 'FFFFFF').lstrip('#')
        _layout_bounds_map = _build_layout_bounds_map(theme_config)
    else:
        _valid_colors = set(_BCG_DEFAULT_COLORS)
        _expected_font = _BCG_DEFAULT_FONT
        _accent_panel_fills = {'29BA74', '197A56', '03522D', '3EAD92'}
        _content_end_y = _BCG_DEFAULT_CONTENT_END_Y
        _source_y = _BCG_DEFAULT_SOURCE_Y
        _content_left = _BCG_DEFAULT_CONTENT_LEFT
        _slide_bg = 'F2F2F2'
        _slide_bg_detail = 'FFFFFF'
        _layout_bounds_map = _build_layout_bounds_map(None)

    work_dir = make_work_dir('qa_work_')
    unpack(str(pptx_path), str(work_dir))

    slides_dir = work_dir / 'ppt' / 'slides'
    slides = sorted(slides_dir.glob('slide*.xml'), key=lambda x: int(re.search(r'slide(\d+)', x.name).group(1)))

    issues = []
    all_body_sizes = []
    all_subheader_sizes = []

    for slide_path in slides:
        snum = int(re.search(r'slide(\d+)', slide_path.name).group(1))
        tree = ET.parse(slide_path)
        root = tree.getroot()

        # Determine layout type
        layout = _get_slide_layout(work_dir, snum)
        behavior = semantic_behavior(layout, theme_config=theme_config)
        # Use semantic behavior flags as primary signal; fall back to
        # hardcoded BCG XML filename sets only for unrecognized layouts.
        _has_role = behavior.get('semantic_role') is not None
        is_statement = behavior.get('statement', False)
        is_image_only = behavior.get('image_only', False)
        allow_title_line_breaks = behavior.get('allow_title_line_breaks', False) or is_statement
        title_max_chars = int(behavior.get('title_max_chars') or 100)
        requires_source = behavior.get('source_mode', 'standard') != 'none' and not is_image_only and not is_statement
        is_structural = behavior.get('structural', False) and not is_statement
        is_detail = behavior.get('detail', False)
        is_green_panel = behavior.get('protected_title_panel', False)
        is_narrow_panel = behavior.get('narrow_panel', False)
        if not _has_role and theme_config is None:
            # Fallback: use hardcoded BCG filename sets ONLY when no
            # theme_config is provided (pure BCG default mode).  ee4p
            # templates use different layout numbering — the BCG sets
            # will produce false positives on any non-BCG template.
            is_statement = is_statement or layout in _STATEMENT_LAYOUTS
            is_image_only = is_image_only or layout in _TITLE_IMAGE_ONLY_LAYOUTS
            allow_title_line_breaks = allow_title_line_breaks or layout in _TITLE_LEFT_PROTECTED_LAYOUTS
            title_max_chars = int(behavior.get('title_max_chars') or (68 if layout in _TITLE_SLIDE_LAYOUTS else 100))
            is_structural = is_structural or (layout in STRUCTURAL_LAYOUTS and not is_statement)
            is_detail = is_detail or layout in _DETAIL_LAYOUTS
            is_green_panel = is_green_panel or layout in _GREEN_PANEL_LAYOUTS
            is_narrow_panel = is_narrow_panel or layout in _TITLE_LEFT_PROTECTED_LAYOUTS
        _NARROW_PANEL_LAYOUTS = _TITLE_LEFT_PROTECTED_LAYOUTS

        slide_fonts = set()
        slide_colors = set()
        has_visual = False
        has_source = False
        title_text = ""
        title_bold = None
        small_text_shapes = []  # Track shapes with text below 12pt

        for sp in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
            fill = sp.find('.//a:solidFill', NS)
            if fill is not None: has_visual = True
            ph = sp.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
            is_title = ph is not None and ph.get('type','') in ('title','ctrTitle')
            is_footer = _is_footer_element(sp, NS)
            # Check if shape has autofit enabled (exempt from font floor)
            body_pr = sp.find('.//a:bodyPr', NS)
            has_autofit = body_pr is not None and body_pr.find('a:normAutofit', NS) is not None
            texts = []
            for t in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
                if t.text:
                    texts.append(t.text.strip())
                    if t.text.startswith('Source:'): has_source = True
            # Check for erroneous line breaks in title text
            if is_title:
                br_count = len(list(sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}br')))
                if br_count > 0 and not allow_title_line_breaks:
                    title_text = ' '.join(texts)
                    issues.append((snum, 'HIGH',
                        f'Title contains {br_count} line break(s) — likely erroneous: "{title_text[:60]}"'))
            for rPr in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}rPr'):
                sz = rPr.get('sz','')
                if sz:
                    pt = int(sz)/100
                    if is_title:
                        title_bold = rPr.get('b','')
                    elif not is_footer:
                        is_bold = rPr.get('b', '') == '1'
                        if pt >= 14 or (pt >= 13 and is_bold):
                            all_subheader_sizes.append(pt)
                        elif 11 <= pt <= 13:
                            all_body_sizes.append(pt)

                    # Font size floor check: flag content text < 12pt
                    # Exempt: titles, footer elements, structural slides, autofit shapes,
                    # axis-like labels (short text <=5 chars at <=10pt, e.g., "M1", "Q3")
                    is_axis_label = pt <= 10 and texts and all(len(t) <= 5 for t in texts)
                    if not is_title and not is_footer and not is_structural and not has_autofit and not is_axis_label and pt < 12:
                        text_sample = ' '.join(texts)[:40] if texts else '?'
                        small_text_shapes.append((pt, text_sample))

                latin = rPr.find('a:latin', NS)
                if latin is not None:
                    face = latin.get('typeface','')
                    if face and face not in ('+mn-lt','+mj-lt', _expected_font): slide_fonts.add(face)
                sf = rPr.find('a:solidFill', NS)
                if sf is not None:
                    srgb = sf.find('a:srgbClr', NS)
                    if srgb is not None: slide_colors.add(srgb.get('val','').upper())
            if is_title and texts: title_text = ' '.join(texts)

        # Font size floor violations (aggregate per slide)
        # < 10pt = HIGH (unreadable), 10-11pt without autofit = MEDIUM (too small)
        if small_text_shapes:
            critical = [(pt, s) for pt, s in small_text_shapes if pt < 10]
            warning = [(pt, s) for pt, s in small_text_shapes if pt >= 10]
            if critical:
                sizes = sorted(set(pt for pt, _ in critical))
                sample = critical[0][1]
                issues.append((snum, 'HIGH', f'Text below 10pt: {sizes}pt ("{sample}...")'))
            if warning:
                sizes = sorted(set(pt for pt, _ in warning))
                sample = warning[0][1]
                issues.append((snum, 'MEDIUM', f'Text below 12pt floor: {sizes}pt ("{sample}...")'))

        # Light text on light background check — skip when the slide bg is dark
        # (e.g., dark ee4p themes where white text is the correct default)
        _bg_is_light = True
        try:
            _bg_rgb = _hex_to_rgb_qa(_slide_bg)
            if _bg_rgb and _luminance(_bg_rgb) < 0.4:
                _bg_is_light = False
        except Exception:
            pass
        if not is_structural and _bg_is_light:
            if not is_detail and not is_green_panel:
                # Standard layouts (light BG): light text should only appear on dark-filled shapes
                light_text_used = slide_colors & _LIGHT_TEXT_COLORS
                if light_text_used:
                    has_dark_shapes = False
                    for sp in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                        if _shape_has_dark_fill(sp, NS):
                            has_dark_shapes = True
                            break
                    if not has_dark_shapes:
                        issues.append((snum, 'HIGH', f'Light text {light_text_used} on light background -- use DARK_TEXT (575757)'))
                    else:
                        issues.append((snum, 'MEDIUM', f'Light text {light_text_used} found -- verify it\'s only on dark/green surfaces'))
            elif is_detail:
                # Detail layouts (white BG): per-shape check -- light text in a textbox
                # that has no dark fill beneath it is invisible on the white background.
                # Flag each orphaned light-text shape individually.
                orphan_light = []
                for sp in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                    ph = sp.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
                    if ph is not None and ph.get('type','') in ('title','ctrTitle','sldNum','ftr','dt'):
                        continue
                    # Skip footer elements (source lines, copyright, page numbers at y >= 6.60")
                    if _is_footer_element(sp, NS):
                        continue
                    # Does this shape use light text?
                    shape_light = set()
                    for rPr in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}rPr'):
                        sf = rPr.find('a:solidFill', NS)
                        if sf is not None:
                            srgb = sf.find('a:srgbClr', NS)
                            if srgb is not None:
                                c = srgb.get('val','').upper()
                                if c in _LIGHT_TEXT_COLORS:
                                    shape_light.add(c)
                    if not shape_light:
                        continue
                    # Does this shape (or a nearby container) have a dark fill?
                    if _shape_has_dark_fill(sp, NS):
                        continue
                    # Light text with no dark fill -- check if shape sits on a known dark
                    # area (y < 1.8" on hero slides, or inside a manually placed dark rect).
                    # Heuristic: scan all sibling shapes for a dark-filled rect that covers
                    # this shape's position.
                    off = sp.find('.//a:off', NS)
                    ext = sp.find('.//a:ext', NS)
                    if off is None or ext is None:
                        continue
                    sy = int(off.get('y','0'))/914400
                    sx = int(off.get('x','0'))/914400
                    sw = int(ext.get('cx','0'))/914400
                    sh = int(ext.get('cy','0'))/914400
                    covered = False
                    for sp2 in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                        if sp2 is sp:
                            continue
                        if not _shape_has_dark_fill(sp2, NS):
                            continue
                        off2 = sp2.find('.//a:off', NS)
                        ext2 = sp2.find('.//a:ext', NS)
                        if off2 is not None and ext2 is not None:
                            rx = int(off2.get('x','0'))/914400
                            ry = int(off2.get('y','0'))/914400
                            rw = int(ext2.get('cx','0'))/914400
                            rh = int(ext2.get('cy','0'))/914400
                            if rx <= sx + 0.05 and ry <= sy + 0.05 and rx + rw >= sx + max(sw - 0.05, 0.10) and ry + rh >= sy + max(sh - 0.05, 0.10):
                                covered = True
                                break
                    if not covered:
                        texts = [t.text.strip() for t in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t') if t.text]
                        sample = ' '.join(texts)[:30] if texts else '?'
                        orphan_light.append(sample)
                if orphan_light:
                    issues.append((snum, 'HIGH',
                        f'Light text on detail template (white BG) without dark fill behind it -- invisible '
                        f'({len(orphan_light)} shape(s): "{orphan_light[0]}...")'))

        if root.find('.//p:pic', NS) is not None or root.find('.//p:graphicFrame', NS) is not None:
            has_visual = True

        # Invalid color format check -- scan ALL srgbClr values in the entire slide
        for srgb in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}srgbClr'):
            val = srgb.get('val', '')
            if val and not _VALID_HEX_6.match(val):
                issues.append((snum, 'HIGH', f'Invalid color format "{val}" (must be 6-char hex RRGGBB)'))

        # Duplicate shape IDs within this slide
        seen_ids = set()
        for cNvPr in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}cNvPr'):
            sid = cNvPr.get('id')
            if sid:
                if sid in seen_ids:
                    issues.append((snum, 'HIGH', f'Duplicate shape id={sid}'))
                seen_ids.add(sid)

        # Negative or non-integer EMU values
        for tag in ('off', 'ext', 'chOff', 'chExt'):
            for elem in root.iter(f'{{http://schemas.openxmlformats.org/drawingml/2006/main}}{tag}'):
                for attr in ('x', 'y', 'cx', 'cy'):
                    val = elem.get(attr)
                    if val is not None:
                        try:
                            if int(val) < 0:
                                issues.append((snum, 'HIGH', f'Negative EMU: {tag}.{attr}={val}'))
                        except ValueError:
                            issues.append((snum, 'HIGH', f'Non-integer EMU: {tag}.{attr}="{val}"'))

        # Missing required transform attributes
        for xfrm in root.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}xfrm'):
            off = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}off')
            ext = xfrm.find('{http://schemas.openxmlformats.org/drawingml/2006/main}ext')
            if off is not None and (off.get('x') is None or off.get('y') is None):
                issues.append((snum, 'HIGH', 'Shape transform missing x or y'))
            if ext is not None and (ext.get('cx') is None or ext.get('cy') is None):
                issues.append((snum, 'HIGH', 'Shape transform missing cx or cy'))

        # Text overflow detection -- vertical-after-wrapping heuristic
        # Estimates whether wrapped text exceeds the box height, not just width
        for sp in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
            # Skip if auto-fit is enabled
            body_pr = sp.find('.//a:bodyPr', NS)
            if body_pr is not None and body_pr.find('a:normAutofit', NS) is not None:
                continue
            ext = sp.find('.//a:ext', NS)
            if ext is None: continue
            box_w_in = int(ext.get('cx', '0')) / 914400
            box_h_in = int(ext.get('cy', '0')) / 914400
            if box_w_in < 0.5 or box_h_in < 0.1: continue  # skip tiny elements
            # Get all text paragraphs in this shape
            paragraphs = []
            max_sz_pt = 12
            for p_el in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}p'):
                line_text = ''
                for r_el in p_el.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}r'):
                    rPr = r_el.find('a:rPr', NS)
                    if rPr is not None:
                        sz_val = rPr.get('sz', '')
                        if sz_val: max_sz_pt = max(max_sz_pt, int(sz_val) / 100)
                    t = r_el.find('a:t', NS)
                    if t is not None and t.text: line_text += t.text
                if line_text: paragraphs.append(line_text)
            if not paragraphs: continue
            # Estimate total wrapped lines across all paragraphs
            total_lines = 0
            for para in paragraphs:
                est_para_width = len(para) * max_sz_pt * 0.55 / 72
                total_lines += max(1, math.ceil(est_para_width / box_w_in))
            # Estimate total height needed (line height ≈ pt/72 * 1.3 for spacing)
            line_height_in = max_sz_pt / 72 * 1.3
            est_height = total_lines * line_height_in
            if est_height > box_h_in * 1.15:  # 15% tolerance
                name_el = sp.find('.//p:cNvPr', NS)
                name = name_el.get('name', '?') if name_el is not None else '?'
                issues.append((snum, 'MEDIUM', f'Text may overflow ({name}): est {est_height:.1f}" in {box_h_in:.1f}" box ({total_lines} lines)'))

        # === v6.7 NEW CHECKS ===

        # Collect all shape bounds for overlap and margin checks
        _all_shape_info = []  # (name, x, y, w, h) — content shapes only
        _all_non_placeholder_shapes = []  # (name, x, y, w, h) — any authored shape, even near the title zone
        _all_shapes_bounds = []  # (name, x, y, w, h) — ALL shapes including title zone (for OOB)
        _text_shape_info = []  # (name, x, y, w, h) — shapes that contain text (for text overlap)
        _all_shapes_for_bg = []  # (bounds, fill_color) for background detection
        _all_texts_for_placeholder = []
        _PML = 'http://schemas.openxmlformats.org/presentationml/2006/main'

        for sp in root.iter(f'{{{_PML}}}sp'):
            ph = sp.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
            is_placeholder = ph is not None and ph.get('type','') in ('title','ctrTitle','sldNum','ftr','dt')
            bounds = _extract_shape_bounds(sp)
            fill = _get_shape_fill_color(sp)
            if bounds:
                name_el = sp.find('.//p:cNvPr', NS)
                nm = name_el.get('name', 'shape') if name_el is not None else 'shape'
                x, y, w, h = bounds
                # ALL shapes for out-of-bounds check (including placeholders)
                _all_shapes_bounds.append((nm, x, y, w, h))
                if not is_placeholder and w > 0.2 and h > 0.1:
                    _all_non_placeholder_shapes.append((nm, x, y, w, h))
                # Content shapes for overlap/margin checks (skip placeholders, tiny shapes)
                if not is_placeholder and w > 0.2 and h > 0.1 and y > 1.5:
                    _all_shape_info.append((nm, x, y, w, h))
                # Text-bearing shapes for text overlap check
                if not is_placeholder:
                    has_text = any(t.text and t.text.strip() for t in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'))
                    if has_text and w > 0.3 and h > 0.1:
                        _text_shape_info.append((nm, x, y, w, h))
            if bounds and fill:
                _all_shapes_for_bg.append((bounds, fill))

            # Collect text for placeholder check
            if not is_placeholder:
                for t in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t'):
                    if t.text and len(t.text.strip()) > 2:
                        _all_texts_for_placeholder.append(t.text.strip())

        # Check 1: Shape overlaps (general)
        if not is_structural and len(_all_shape_info) >= 2:
            issues.extend(_check_shape_overlaps(_all_shape_info, snum))

        # Check 1b: Text-bearing shape overlaps (stricter — any text-on-text overlap is unreadable)
        if not is_structural and len(_text_shape_info) >= 2:
            issues.extend(_check_text_overlaps(_text_shape_info, snum))

        # Check 2: Placeholder/unfinished text
        if not is_structural:
            issues.extend(_check_placeholder_text(_all_texts_for_placeholder, snum))

        # Check 3: Edge margin violations
        if not is_structural and _all_shape_info:
            issues.extend(_check_edge_margins(_all_shape_info, snum, slide_w=slide_w, slide_h=slide_h))

        # Check 3b: Out-of-bounds — any shape extending past slide edges
        if _all_shapes_bounds:
            issues.extend(_check_out_of_bounds(_all_shapes_bounds, snum, slide_w=slide_w, slide_h=slide_h))

        # Check 3c: Zone-boundary violations on split layouts.
        # Only run on layouts that are semantically split (framing_split,
        # contrast_split, etc.) — not on full-page layouts that happen
        # to have panel geometry in the template master.
        _is_split_layout = behavior.get('layout_class', '') in (
            'framing_split', 'contrast_split', 'rich_split',
            'image_led', 'image_supported',
        ) or is_green_panel or is_narrow_panel
        if not is_structural and _is_split_layout and _layout_bounds_map and layout in _layout_bounds_map:
            _lb = _layout_bounds_map[layout]
            issues.extend(_check_zone_boundary_violations(_all_shape_info, snum, _lb))
            if is_narrow_panel:
                issues.extend(_check_protected_left_panel_occupancy(_all_non_placeholder_shapes, snum, _lb))
        elif is_narrow_panel and _layout_bounds_map and layout in _layout_bounds_map:
            _lb = _layout_bounds_map[layout]
            issues.extend(_check_protected_left_panel_occupancy(_all_non_placeholder_shapes, snum, _lb))

        # Check 4: WCAG contrast (text on background shapes)
        if not is_structural:
            slide_bg = _slide_bg if not is_detail else _slide_bg_detail
            _contrast_checked = set()  # dedupe per (text_color, bg) pair per slide
            for sp in root.iter(f'{{{_PML}}}sp'):
                sp_fill = _get_shape_fill_color(sp)
                sp_bounds = _extract_shape_bounds(sp)
                for rPr in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}rPr'):
                    sf = rPr.find('a:solidFill', NS)
                    if sf is None:
                        continue
                    srgb = sf.find('a:srgbClr', NS)
                    if srgb is None:
                        continue
                    text_color = srgb.get('val', '').upper()
                    if not text_color or len(text_color) != 6:
                        continue
                    # Find background: use the shape's OWN fill first (textbox bg),
                    # then search for containing shapes, then slide bg
                    if sp_fill and sp_fill != text_color:
                        bg = sp_fill
                    elif sp_bounds:
                        # Search all filled shapes for the one behind this text.
                        # Since _get_shape_fill_color only returns geometry fills
                        # (not text run fills), textboxes without bg won't pollute
                        # the list. Shapes with identical bounds (e.g., a dark rect
                        # directly behind a textbox) are intentionally included.
                        bg = _find_background_for_shape(_all_shapes_for_bg, sp_bounds, slide_bg)
                    else:
                        bg = slide_bg
                    # Skip if text matches bg (same shape = no issue, just default color)
                    if text_color == bg:
                        continue
                    pair_key = (text_color, bg)
                    if pair_key in _contrast_checked:
                        continue
                    _contrast_checked.add(pair_key)
                    ratio = _wcag_contrast(text_color, bg)
                    # The primary brand green (BCG_GREEN and theme-remapped equivalents)
                    # is intentionally used as text color on light backgrounds at ~2.5:1.
                    # This is the BCG brand standard — readable and expected. Only flag
                    # truly unreadable combinations (ratio < 1.5) or non-brand colors below 3.0:1.
                    is_brand_green_text = text_color.upper() in _accent_panel_fills
                    is_white_on_brand_panel = text_color.upper() in _LIGHT_TEXT_COLORS and bg.upper() in _accent_panel_fills
                    if 0 < ratio < 1.5:
                        # Truly unreadable — always flag
                        sz_attr = rPr.get('sz', '1200')
                        pt = int(sz_attr) / 100
                        issues.append((snum, 'HIGH', f'Poor contrast: #{text_color} on #{bg} ({ratio:.1f}:1, needs 1.5:1) at {pt}pt'))
                    elif 0 < ratio < 3.0 and not is_brand_green_text and not is_white_on_brand_panel:
                        # Below 3.0:1 but not brand green — flag as HIGH
                        sz_attr = rPr.get('sz', '1200')
                        pt = int(sz_attr) / 100
                        issues.append((snum, 'HIGH', f'Poor contrast: #{text_color} on #{bg} ({ratio:.1f}:1, needs 3.0:1) at {pt}pt'))
                    elif 0 < ratio < 4.45 and not is_brand_green_text and not is_white_on_brand_panel:
                        sz_attr = rPr.get('sz', '1200')
                        pt = int(sz_attr) / 100
                        if pt < 18:
                            issues.append((snum, 'MEDIUM', f'Low contrast: #{text_color} on #{bg} ({ratio:.1f}:1, WCAG AA needs 4.5:1) at {pt}pt'))

        # === END v6.7 CHECKS ===

        # CHECKS (skip structural slides for content-specific checks)
        if slide_fonts: issues.append((snum, 'HIGH', f'Non-{_expected_font} font: {slide_fonts}'))
        non_bcg = {c for c in slide_colors if c not in _valid_colors}
        if non_bcg: issues.append((snum, 'HIGH', f'Off-palette color: {non_bcg}'))
        if is_structural and title_text and len(title_text) > title_max_chars:
            issues.append((snum, 'HIGH',
                f'Title too long ({len(title_text)} chars, max {title_max_chars}) -- will wrap to 3+ lines: "{title_text[:60]}..."'))
        if not is_structural:
            if title_bold == '1': issues.append((snum, 'MEDIUM', 'Bold title'))
            if title_text and len(title_text.split()) < 6 and not is_narrow_panel:
                issues.append((snum, 'MEDIUM', f'Short title: "{title_text[:50]}"'))
            if title_text and len(title_text) > title_max_chars:
                issues.append((snum, 'HIGH',
                    f'Title too long ({len(title_text)} chars, max {title_max_chars}) -- will wrap to 3+ lines: "{title_text[:60]}..."'))
            # Narrow-panel layouts have much tighter title limits
            if is_narrow_panel and title_text and len(title_text) > 35:
                issues.append((snum, 'HIGH', f'Title too long for narrow panel ({len(title_text)} chars, max ~30): "{title_text[:40]}..."'))
            if not has_visual and not is_statement:
                issues.append((snum, 'HIGH', 'No visual elements on content slide'))
            if not has_source and requires_source:
                issues.append((snum, 'LOW', 'No source line'))
            if is_image_only:
                issues.extend(_check_title_image_only_text(_text_shape_info, snum))
            if is_statement:
                issues.extend(_check_statement_layout_text(_text_shape_info, snum))

            # Content overlap check -- top (title) and bottom (source/footer)
            # For split/narrow-panel layouts, also check X-based overlap with the title placeholder
            _title_bounds = None
            if is_narrow_panel:
                for sp_t in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                    ph_t = sp_t.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
                    if ph_t is not None and ph_t.get('type','') in ('title','ctrTitle'):
                        off_t = sp_t.find('.//a:off', NS)
                        ext_t = sp_t.find('.//a:ext', NS)
                        if off_t is not None and ext_t is not None:
                            _title_bounds = {
                                'x': int(off_t.get('x','0'))/914400,
                                'y': int(off_t.get('y','0'))/914400,
                                'w': int(ext_t.get('cx','0'))/914400,
                                'h': int(ext_t.get('cy','0'))/914400,
                            }
                        break

            for sp in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                ph = sp.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
                if ph is not None and ph.get('type','') in ('title','ctrTitle'): continue
                off = sp.find('.//a:off', NS)
                ext = sp.find('.//a:ext', NS)
                if off is not None:
                    y = int(off.get('y','0'))/914400
                    x = int(off.get('x','0'))/914400
                    sh = int(ext.get('cy','0'))/914400 if ext is not None else 0.5
                    sw = int(ext.get('cx','0'))/914400 if ext is not None else 0.5
                    ts = [t.text for t in sp.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t') if t.text]
                    if not ts:
                        continue
                    # For narrow-panel/split layouts: check if shape overlaps the title
                    # placeholder's bounding box (both X and Y dimensions).
                    # On these layouts the title is in the left panel, not at the top.
                    if _title_bounds and is_narrow_panel:
                        tx = _title_bounds['x']
                        tx_end = tx + _title_bounds['w']
                        ty = _title_bounds['y']
                        ty_end = ty + _title_bounds['h']
                        # Check 2D overlap: shape's box intersects title's box
                        x_overlap = x < tx_end and (x + sw) > tx
                        y_overlap = y < ty_end and (y + sh) > ty
                        if x_overlap and y_overlap:
                            issues.append((snum, 'HIGH',
                                f'Content at x={x:.2f}" y={y:.2f}" overlaps title panel '
                                f'(title bounds: x={tx:.2f}"-{tx_end:.2f}", y={ty:.2f}"-{ty_end:.2f}")'))
                            break
                    # Standard top-of-slide title zone check
                    elif 0.5 < y < 1.60:
                        issues.append((snum, 'HIGH', f'Content at y={y:.2f}" overlaps title'))
                        break
                    # Bottom boundary: content past CONTENT_END_Y
                    # Skip footer elements (source, page number, copyright)
                    _footer_zone = _source_y - 0.14
                    if ext is not None and 2.0 < y:
                        h = int(ext.get('cy','0'))/914400
                        bottom = y + h
                        if bottom > slide_h:
                            name = sp.find('.//p:cNvPr', NS)
                            nm = name.get('name','') if name is not None else ''
                            issues.append((snum, 'HIGH', f'OVERFLOW: {nm} at y={bottom:.2f}" past slide edge ({slide_h}")'))
                        elif bottom > _source_y and y < _footer_zone:
                            name = sp.find('.//p:cNvPr', NS)
                            nm = name.get('name','') if name is not None else ''
                            issues.append((snum, 'HIGH', f'Content extends to y={bottom:.2f}" past source line at {_source_y}" ({nm})'))
                        elif bottom > _content_end_y and y < _footer_zone:
                            name = sp.find('.//p:cNvPr', NS)
                            nm = name.get('name','') if name is not None else ''
                            issues.append((snum, 'MEDIUM', f'Content extends to y={bottom:.2f}" past CONTENT_END_Y at {_content_end_y}" ({nm})'))

            # Horizontal overflow -- shapes extending past slide right edge
            for sp in root.iter('{http://schemas.openxmlformats.org/presentationml/2006/main}sp'):
                off = sp.find('.//a:off', NS)
                ext = sp.find('.//a:ext', NS)
                if off is not None and ext is not None:
                    sx = int(off.get('x','0'))/914400
                    sw = int(ext.get('cx','0'))/914400
                    if (sx + sw) > (slide_w + 0.15) and sw > 0.5:
                        name = sp.find('.//p:cNvPr', NS)
                        nm = name.get('name','') if name is not None else ''
                        issues.append((snum, 'HIGH', f'OVERFLOW: {nm} extends past right edge at x={sx+sw:.2f}" (slide width {slide_w}")'))

            # Content balance check -- detect large empty areas on dense slides
            # Skip split/asymmetric layouts where imbalance is by design
            _ASYMMETRIC_LAYOUTS = _GREEN_PANEL_LAYOUTS | {
                'slideLayout4.xml',   # Gray slice
                'slideLayout7.xml',   # White one third
                'slideLayout8.xml',   # Green highlight
                'slideLayout12.xml',  # Left arrow
                'slideLayout14.xml',  # Arrow one third
                'slideLayout16.xml',  # Arrow half
                'slideLayout17.xml',  # Green arrow half
                'slideLayout18.xml',  # Arrow two third
                'slideLayout19.xml',  # Green arrow two third
                'slideLayout32.xml',  # D. Gray slice
                'slideLayout35.xml',  # D. White one third
                'slideLayout36.xml',  # D. Green highlight
                'slideLayout41.xml',  # D. Left arrow
                'slideLayout43.xml',  # D. Arrow one third
                'slideLayout45.xml',  # D. Arrow half
                'slideLayout46.xml',  # D. Green arrow half
                'slideLayout47.xml',  # D. Arrow two third
                'slideLayout48.xml',  # D. Green arrow two third
            }
            if layout not in _ASYMMETRIC_LAYOUTS:
                content_rects = []
                _PML = 'http://schemas.openxmlformats.org/presentationml/2006/main'
                # Count sp, graphicFrame (charts/tables), and grpSp (groups)
                for tag in ('sp', 'graphicFrame', 'grpSp'):
                    for elem in root.iter(f'{{{_PML}}}{tag}'):
                        # Skip title/footer placeholders (only sp has these)
                        if tag == 'sp':
                            ph2 = elem.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
                            if ph2 is not None and ph2.get('type','') in ('title','ctrTitle','sldNum','ftr','dt'):
                                continue
                        off2 = elem.find('.//a:off', NS)
                        ext2 = elem.find('.//a:ext', NS)
                        # graphicFrame/grpSp use p:xfrm > a:off, but also check a:xfrm > a:off
                        if off2 is None:
                            off2 = elem.find(f'{{{_PML}}}xfrm/{{{NS["a"]}}}off')
                        if ext2 is None:
                            ext2 = elem.find(f'{{{_PML}}}xfrm/{{{NS["a"]}}}ext')
                        if off2 is not None and ext2 is not None:
                            sx = int(off2.get('x','0'))/914400
                            sy = int(off2.get('y','0'))/914400
                            sw = int(ext2.get('cx','0'))/914400
                            sh = int(ext2.get('cy','0'))/914400
                            # Only shapes in content zone, skip tiny decorations
                            if 1.5 < sy < 6.60 and sw > 0.3 and sh > 0.1:
                                content_rects.append((sx, sy, sw, sh))

                if len(content_rects) >= 8:
                    mid_x, mid_y = 6.67, 4.30  # slide center, content zone center
                    q_area = [0.0] * 4  # TL, TR, BL, BR
                    for (sx, sy, sw, sh) in content_rects:
                        area = sw * sh
                        # Split area proportionally across quadrants
                        left_f = max(0, min(mid_x, sx + sw) - sx) / sw if sw > 0 else 0.5
                        top_f = max(0, min(mid_y, sy + sh) - sy) / sh if sh > 0 else 0.5
                        q_area[0] += area * left_f * top_f           # TL
                        q_area[1] += area * (1 - left_f) * top_f     # TR
                        q_area[2] += area * left_f * (1 - top_f)     # BL
                        q_area[3] += area * (1 - left_f) * (1 - top_f)  # BR
                    total_area = sum(q_area)
                    if total_area > 0:
                        q_pct = [a / total_area for a in q_area]
                        labels = ['top-left', 'top-right', 'bottom-left', 'bottom-right']
                        for qi, pct in enumerate(q_pct):
                            if pct < 0.02:
                                max_other = max(q_pct[j] for j in range(4) if j != qi)
                                if max_other > 0.35:
                                    issues.append((snum, 'MEDIUM',
                                        f'Unbalanced layout: {labels[qi]} quadrant is empty '
                                        f'({len(content_rects)} shapes, redistribute or split slide)'))
                                    break

            # Bottom content gap check -- detect dense slides with large empty area at bottom
            # Reuse content_rects from balance check if available, otherwise build fresh
            if layout not in _ASYMMETRIC_LAYOUTS and not is_structural:
                gap_rects = content_rects if 'content_rects' in dir() and content_rects else []
                if not gap_rects:
                    # Build content_rects for non-asymmetric slides that didn't hit the balance check
                    _PML2 = 'http://schemas.openxmlformats.org/presentationml/2006/main'
                    for tag in ('sp', 'graphicFrame', 'grpSp'):
                        for elem in root.iter(f'{{{_PML2}}}{tag}'):
                            if tag == 'sp':
                                ph2 = elem.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
                                if ph2 is not None and ph2.get('type','') in ('title','ctrTitle','sldNum','ftr','dt'):
                                    continue
                            off2 = elem.find('.//a:off', NS)
                            ext2 = elem.find('.//a:ext', NS)
                            if off2 is None:
                                off2 = elem.find(f'{{{_PML2}}}xfrm/{{{NS["a"]}}}off')
                            if ext2 is None:
                                ext2 = elem.find(f'{{{_PML2}}}xfrm/{{{NS["a"]}}}ext')
                            if off2 is not None and ext2 is not None:
                                sy2 = int(off2.get('y','0'))/914400
                                sh2 = int(ext2.get('cy','0'))/914400
                                sw2 = int(ext2.get('cx','0'))/914400
                                sx2 = int(off2.get('x','0'))/914400
                                if 1.5 < sy2 < _footer_zone and sw2 > 0.3 and sh2 > 0.1:
                                    gap_rects.append((sx2, sy2, sw2, sh2))
                if len(gap_rects) >= 6:
                    max_bottom = max(sy + sh for (sx, sy, sw, sh) in gap_rects)
                    _gap_threshold = _content_end_y - 1.20
                    if max_bottom < _gap_threshold:
                        issues.append((snum, 'MEDIUM',
                            f'Bottom gap: content ends at y={max_bottom:.1f}" leaving >{_content_end_y - max_bottom:.1f}" '
                            f'empty ({len(gap_rects)} shapes -- extend content or add callout)'))

            # Shape overlap check -- detect callout boxes in the footer zone (y > 5.5")
            # that overlap with content shapes above them. Checks wide elements
            # (w > 5") against any content shape (h > 0.3"), catching both tall cards
            # and short row-based elements that collectively overflow into the callout.
            if not is_structural:
                cards = []   # content shapes (h > 0.3") -- cards, rows, textboxes
                callouts = []  # short wide shapes in footer zone -- likely callouts/legends
                _PML3 = 'http://schemas.openxmlformats.org/presentationml/2006/main'
                for sp in root.iter(f'{{{_PML3}}}sp'):
                    ph3 = sp.find('.//p:nvSpPr/p:nvPr/p:ph', NS)
                    if ph3 is not None and ph3.get('type','') in ('title','ctrTitle','sldNum','ftr','dt'):
                        continue
                    if _is_footer_element(sp, NS):
                        continue
                    off3 = sp.find('.//a:off', NS)
                    ext3 = sp.find('.//a:ext', NS)
                    if off3 is not None and ext3 is not None:
                        sx3 = int(off3.get('x','0'))/914400
                        sy3 = int(off3.get('y','0'))/914400
                        sw3 = int(ext3.get('cx','0'))/914400
                        sh3 = int(ext3.get('cy','0'))/914400
                        cnvPr = sp.find('.//p:nvSpPr/p:cNvPr', NS)
                        name = cnvPr.get('name','?') if cnvPr is not None else '?'
                        if sh3 > 0.3 and sw3 > 0.3 and sy3 > 1.5:
                            cards.append((sx3, sy3, sw3, sh3, name))
                        elif sh3 < 1.0 and sw3 > 5.0 and sy3 > 5.5:
                            callouts.append((sx3, sy3, sw3, sh3, name))
                filtered_callouts = []
                for cx, cy, cw, ch, cname in callouts:
                    contained = False
                    for kx, ky, kw, kh, kname in cards:
                        if kname == cname:
                            continue
                        if kw * kh <= cw * ch * 1.5:
                            continue
                        if _contains_bounds((kx, ky, kw, kh), (cx, cy, cw, ch)):
                            contained = True
                            break
                    if not contained:
                        filtered_callouts.append((cx, cy, cw, ch, cname))

                # Check each footer callout against each card for vertical overlap
                for cx, cy, cw, ch, cname in filtered_callouts:
                    for kx, ky, kw, kh, kname in cards:
                        k_bottom = ky + kh
                        # Card must end below callout start (overlap)
                        if k_bottom <= cy:
                            continue
                        # Must share horizontal space
                        x_overlap = max(0, min(kx+kw, cx+cw) - max(kx, cx))
                        if x_overlap < 0.5:
                            continue
                        overlap_in = k_bottom - cy
                        if overlap_in > 0.10:
                            issues.append((snum, 'MEDIUM',
                                f'Callout "{cname}" overlaps card "{kname}" by {overlap_in:.2f}" -- '
                                f'reduce card height or move callout below y={k_bottom:.2f}"'))

    # OOXML structural checks (cross-slide)
    import zipfile as _zf
    with _zf.ZipFile(str(pptx_path)) as zf:
        all_files = set(zf.namelist())

        # Every slide must have a .rels with a layout reference
        for slide_path in slides:
            snum = int(re.search(r'slide(\d+)', slide_path.name).group(1))
            rels_path = f'ppt/slides/_rels/slide{snum}.xml.rels'
            if rels_path not in all_files:
                issues.append((snum, 'HIGH', 'Missing .rels file'))
            else:
                rels_root = ET.fromstring(zf.read(rels_path))
                has_layout = any('slideLayout' in r.get('Target', '')
                    for r in rels_root.iter('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'))
                if not has_layout:
                    issues.append((snum, 'HIGH', 'No layout reference in .rels'))

        # All slides referenced in presentation.xml.rels
        pres_rels = 'ppt/_rels/presentation.xml.rels'
        if pres_rels in all_files:
            pr_root = ET.fromstring(zf.read(pres_rels))
            ref_slides = set()
            for rel in pr_root.iter('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                t = rel.get('Target', '')
                if t.endswith('.xml') and 'slide' in t.lower():
                    ref_slides.add('ppt/' + t if not t.startswith('ppt/') else t)
            for slide_path in slides:
                snum = int(re.search(r'slide(\d+)', slide_path.name).group(1))
                if f'ppt/slides/slide{snum}.xml' not in ref_slides:
                    issues.append((snum, 'HIGH', 'Slide not in presentation.xml.rels'))

        # Broken relationship targets (images, notes, etc.)
        for rels_file in (f for f in all_files if f.startswith('ppt/slides/_rels/') and f.endswith('.rels')):
            rels_root = ET.fromstring(zf.read(rels_file))
            for rel in rels_root.iter('{http://schemas.openxmlformats.org/package/2006/relationships}Relationship'):
                target = rel.get('Target', '')
                if rel.get('TargetMode') == 'External' or target.startswith('http'):
                    continue
                resolved = os.path.normpath(os.path.join('ppt/slides', target)).replace('\\', '/')
                if resolved not in all_files:
                    snum_m = re.search(r'slide(\d+)', rels_file)
                    sn = int(snum_m.group(1)) if snum_m else 0
                    issues.append((sn, 'HIGH', f'Broken rel target: {target}'))

    # Cross-slide consistency (only body text from content slides)
    if len(set(all_body_sizes)) > 2:
        issues.append((0, 'HIGH', f'Inconsistent body sizes: {sorted(set(all_body_sizes))}'))
    if len(set(all_subheader_sizes)) > 3:
        issues.append((0, 'MEDIUM', f'Inconsistent sub-header sizes: {sorted(set(all_subheader_sizes))}'))

    if verbose:
        print(f'\nBCG QA REPORT: {pptx_path}')
        print('=' * 60)
        high = [i for i in issues if i[1]=='HIGH']
        med = [i for i in issues if i[1]=='MEDIUM']
        low = [i for i in issues if i[1]=='LOW']
        for sev, items, icon in [('HIGH',high,'x'),('MEDIUM',med,'!'),('LOW',low,'.')]:
            if items:
                print(f'\n{icon} {sev} ({len(items)}):')
                for s,_,msg in items:
                    loc = f'Slide {s}' if s > 0 else 'Cross-deck'
                    print(f'  {loc}: {msg}')
        if not issues: print('\nAll checks passed!')
        print(f'\nTotal: {len(high)} high, {len(med)} medium, {len(low)} low')

    shutil.rmtree(work_dir, ignore_errors=True)
    return issues


def summarize_issues(issues):
    """Return a severity summary for a deck-level issue list."""
    summary = {"HIGH": 0, "MEDIUM": 0, "LOW": 0}
    for _slide, severity, _message in issues:
        if severity in summary:
            summary[severity] += 1
    summary["total"] = len(issues)
    return summary


def group_issues_by_slide(issues):
    """Group issue tuples by slide number for fan-out review workflows."""
    grouped = defaultdict(list)
    for slide_number, severity, message in issues:
        grouped[slide_number].append({
            "slide": slide_number,
            "severity": severity,
            "message": message,
        })
    return dict(grouped)


def build_visual_review_jobs(rendered_paths, issues=None):
    """Create slide-scoped review jobs from rendered slide images.

    `rendered_paths` may be strings or Paths. The caller is responsible for
    rendering the slide images; this helper only prepares the fan-out payload.
    """
    issue_map = group_issues_by_slide(issues or [])
    jobs = []
    for index, path in enumerate(rendered_paths, start=1):
        jobs.append({
            "slide": index,
            "image_path": str(path),
            "issues": issue_map.get(index, []),
        })
    return jobs

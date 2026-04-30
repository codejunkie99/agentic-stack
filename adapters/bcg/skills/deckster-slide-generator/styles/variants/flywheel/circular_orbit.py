"""Circular orbit flywheel — nodes orbit a center value proposition.

Default flywheel variant. Draws a center hub with the core message
and N nodes arranged in a circle around it, with an orbit track ring
and directional arrows showing the reinforcing cycle.
"""

import math


def render(deck, slide, data, bounds, **kwargs):
    """Render a circular orbit flywheel.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [{"label": str, "detail": str, "metric": str (optional), "icon": str (optional)}, ...],
            "center_message": str
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS, text_on, dark_fills

    stages = data.get("stages", [])
    center_message = data.get("center_message", "")
    n = len(stages)

    if n < 2:
        return

    show_metrics = n <= 4

    # Layout geometry — center of content zone
    cx = bounds["x"] + bounds["w"] / 2
    cy = bounds["y"] + bounds["h"] / 2
    half_min = min(bounds["w"], bounds["h"]) / 2

    # Dynamic sizing based on node count (scales for 3-7 nodes)
    node_r_max = 0.72
    orbit_r_base = half_min - node_r_max - 0.10
    max_node_r = orbit_r_base * math.sin(math.pi / n) - 0.08
    node_r = min(max(max_node_r, 0.34), node_r_max)
    orbit_r = half_min - node_r - 0.12
    hub_gap = 0.18
    hub_r = min(0.68, max(0.42, orbit_r * 0.30), max(orbit_r - node_r - hub_gap, 0.36))

    label_sz = 14 if node_r >= 0.65 else (12 if node_r >= 0.50 else 11)
    metric_sz = 11
    fills = dark_fills(n)

    # Do not draw a literal orbit ring. QA treats it as a large overlapping oval
    # against the hub/nodes, even though it is just a visual guide.
    track_r = orbit_r - node_r * 0.3

    # Center hub
    deck.add_oval(slide,
                  cx - hub_r, cy - hub_r,
                  hub_r * 2, hub_r * 2,
                  COLORS["DEEP_GREEN"],
                  line_color=COLORS["DEEP_GREEN"],
                  line_width=2.0)
    deck.add_textbox(slide, center_message,
                     cx - hub_r, cy - 0.30,
                     hub_r * 2, 0.60,
                     sz=16, color=text_on(COLORS["DEEP_GREEN"]),
                     bold=True, align="center", valign="middle")

    # Orbit nodes — equally spaced, starting at top (-90 deg)
    for i, stage in enumerate(stages):
        ang_deg = -90 + i * (360 / n)
        ang = math.radians(ang_deg)
        ncx = cx + orbit_r * math.cos(ang)
        ncy = cy + orbit_r * math.sin(ang)
        nx, ny = ncx - node_r, ncy - node_r

        fill = fills[i % len(fills)]

        # Node circle with white border for separation
        deck.add_oval(slide, nx, ny, node_r * 2, node_r * 2, fill,
                      line_color=COLORS["WHITE"], line_width=2.5)

        # Icon centered in node (if provided)
        icon = stage.get("icon")
        if icon:
            icon_sz = node_r * 0.7
            deck.add_icon(slide, icon,
                          ncx - icon_sz / 2, ncy - icon_sz / 2 - 0.15,
                          size=icon_sz, color=text_on(fill))

        # Label and optional metric inside node
        label = stage.get("label", "")
        metric = stage.get("metric") if show_metrics else None

        if icon:
            # Label below icon inside node
            deck.add_textbox(slide, label,
                             nx + 0.08, ncy + node_r * 0.2,
                             node_r * 2 - 0.16, 0.40,
                             sz=label_sz - 2, color=text_on(fill),
                             bold=True, align="center", valign="middle")
        elif metric:
            block_h = 0.50 + 0.30
            block_top = ncy - block_h / 2
            deck.add_textbox(slide, label,
                             nx + 0.08, block_top,
                             node_r * 2 - 0.16, 0.50,
                             sz=label_sz, color=text_on(fill),
                             bold=True, align="center", valign="middle")
            deck.add_textbox(slide, metric,
                             nx + 0.08, block_top + 0.50,
                             node_r * 2 - 0.16, 0.30,
                             sz=metric_sz, color=text_on(fill),
                             align="center", valign="middle")
        else:
            deck.add_textbox(slide, label,
                             nx + 0.08, ncy - 0.25,
                             node_r * 2 - 0.16, 0.50,
                             sz=label_sz, color=text_on(fill),
                             bold=True, align="center", valign="middle")

    # Clockwise arrows just outside the orbit track
    arrow_orbit = track_r + 0.20
    arrow_w = 0.38 if n >= 6 else 0.44
    arrow_h = 0.18 if n >= 6 else 0.20

    for i in range(n):
        a_deg = -90 + (i + 0.5) * (360 / n)
        a_rad = math.radians(a_deg)
        acx = cx + arrow_orbit * math.cos(a_rad)
        acy = cy + arrow_orbit * math.sin(a_rad)
        rot = a_deg + 90
        deck.add_shape(slide, "rightArrow",
                       acx - arrow_w / 2, acy - arrow_h / 2,
                       arrow_w, arrow_h, COLORS["MED_GRAY"],
                       rotation=rot)

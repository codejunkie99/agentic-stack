"""Concentric rings flywheel — rings radiating outward from a center core.

Alternative flywheel variant. Each stage is represented as a progressively
larger ring around a center hub, with labels placed on each ring band.
Visually emphasizes layers of reinforcement rather than node-to-node flow.
"""

import math


def render(deck, slide, data, bounds, **kwargs):
    """Render a concentric rings flywheel.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "stages": [{"label": str, "detail": str (optional)}, ...],
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

    # Layout geometry
    cx = bounds["x"] + bounds["w"] / 2
    cy = bounds["y"] + bounds["h"] / 2
    max_radius = min(bounds["w"], bounds["h"]) / 2 - 0.15

    # Ring radii — evenly spaced from center outward
    # Reserve inner portion for hub
    hub_fraction = 0.25
    hub_r = max_radius * hub_fraction
    ring_start = hub_r
    ring_end = max_radius
    ring_step = (ring_end - ring_start) / n

    fills = dark_fills(n)

    # Draw rings from outermost to innermost (so inner rings overlay outer)
    for i in range(n - 1, -1, -1):
        outer_r = ring_start + (i + 1) * ring_step
        fill = fills[i % len(fills)]

        # Ring as a filled oval (each subsequent smaller ring covers the inner portion)
        deck.add_oval(slide,
                      cx - outer_r, cy - outer_r,
                      outer_r * 2, outer_r * 2,
                      fill,
                      line_color=COLORS["WHITE"],
                      line_width=2.0)

    # Center hub (drawn last, on top)
    deck.add_oval(slide,
                  cx - hub_r, cy - hub_r,
                  hub_r * 2, hub_r * 2,
                  COLORS["DEEP_GREEN"],
                  line_color=COLORS["WHITE"],
                  line_width=2.5)
    deck.add_textbox(slide, center_message,
                     cx - hub_r + 0.05, cy - 0.25,
                     hub_r * 2 - 0.10, 0.50,
                     sz=14, color=text_on(COLORS["DEEP_GREEN"]),
                     bold=True, align="center", valign="middle")

    # Labels for each ring — placed at compass positions around the ring band
    # Distribute labels at different angles for readability
    base_angles = [-90, 90, 0, 180, -45, 45, -135, 135]

    for i, stage in enumerate(stages):
        fill = fills[i % len(fills)]
        inner_r = ring_start + i * ring_step
        outer_r = ring_start + (i + 1) * ring_step
        mid_r = (inner_r + outer_r) / 2

        # Position label at a unique angle on the ring band
        angle_deg = base_angles[i % len(base_angles)]
        angle_rad = math.radians(angle_deg)

        label_x = cx + mid_r * math.cos(angle_rad)
        label_y = cy + mid_r * math.sin(angle_rad)

        label = stage.get("label", "")
        label_w = ring_step * 2.2
        label_h = ring_step * 0.80

        # Keep label within bounds
        lx = max(bounds["x"], min(label_x - label_w / 2, bounds["x"] + bounds["w"] - label_w))
        ly = max(bounds["y"], min(label_y - label_h / 2, bounds["y"] + bounds["h"] - label_h))

        deck.add_textbox(slide, label,
                         lx, ly, label_w, label_h,
                         sz=12, color=text_on(fill),
                         bold=True, align="center", valign="middle")

    # Stage numbers outside the outermost ring for reference
    for i, stage in enumerate(stages):
        angle_deg = -90 + i * (360 / n)
        angle_rad = math.radians(angle_deg)
        badge_r = max_radius + 0.10
        bx = cx + badge_r * math.cos(angle_rad)
        by = cy + badge_r * math.sin(angle_rad)

        # Only draw if within bounds
        if (bounds["x"] <= bx <= bounds["x"] + bounds["w"] and
                bounds["y"] <= by <= bounds["y"] + bounds["h"]):
            deck.add_number_badge(slide, str(i + 1),
                                  bx - 0.18, by - 0.18,
                                  size=0.36, fill_color=COLORS["BCG_GREEN"])

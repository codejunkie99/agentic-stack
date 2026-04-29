"""Native table -- wraps add_table() with structured data.

Renders a native PowerPoint table using the BCGDeck add_table() method,
which applies BCG standard styling (green header, alternating stripes).
"""


def validate(deck, slide, data, bounds, **kwargs):
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    if not headers and not rows:
        return ["provide table rows or headers"]
    if rows and not isinstance(rows, list):
        return ["rows must be a list of lists"]
    return []


def render(deck, slide, data, bounds, **kwargs):
    """Render a native PowerPoint table.

    Args:
        deck: BCGDeck instance
        slide: slide reference
        data: {
            "headers": [str, ...],
            "rows": [[str, ...], ...],
            "col_widths": [float, ...] (optional),
            "col_align": [str, ...] (optional, "left"/"center"/"right")
        }
        bounds: {"x": float, "y": float, "w": float, "h": float} in inches
    """
    from bcg_template import COLORS

    headers = data.get("headers", [])
    rows = data.get("rows", [])
    col_widths = data.get("col_widths", None)
    col_align = data.get("col_align", None)

    if not headers and not rows:
        return

    if not headers and rows:
        headers = rows[0]
        rows = rows[1:]

    # Build the combined data array (header row + data rows)
    table_data = []
    if headers:
        table_data.append(headers)
    table_data.extend(rows)

    if not table_data:
        return

    x = bounds["x"]
    y = bounds["y"]
    w = bounds["w"]
    h = bounds["h"]

    deck.add_table(slide, table_data,
                   x=x, y=y, w=w, h=h,
                   header=bool(headers),
                   col_widths=col_widths,
                   col_align=col_align,
                   sz=12)

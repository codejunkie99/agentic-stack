# Build

Authoritative build runtime surface. Read this for the canonical build path, runtime API usage, geometry rules, and visual-system standards.

# Build Contract

Use this file in Phase 2. It defines the canonical runtime path.

## Mode Fork

The semantic build contract is shared across runtimes.

- **Sequential mode**: one authoritative deck object owns the entire build in one execution.
- **Orchestrated mode**: workers may render isolated slide artifacts or mini-decks in separate workdirs, but the final reducer still owns numbering, relationship rewrites, media copy, and package assembly.

When `supports_subagents=true`, also read `references/runtime/orchestration.md`.

## Canonical Build Path

```python
from bcg_template import (
    BCGDeck,
    content_bounds,
    COLORS,
    text_on,
    dark_fills,
    stack_y_positions,
    check_setup,
)
from deck_preflight import preflight_deck
from pattern_variants import render_pattern
from qa import check_deck
from template_registry import get_template

check_setup()
template = get_template(name="bcg_default")

TITLE_SIZE = 24
SUBHEADER_SIZE = 16
BODY_SIZE = 14
LABEL_SIZE = 12

slide_specs = [
    {
        "kind": "content",
        "title": "Action title as a sentence",
        "layout": "title_only",
        "detail": True,
        "pattern": {"name": "column_cards", "data": {...}},
    }
]
report = preflight_deck(slide_specs, theme_config=template)
if report["summary"]["errors"]:
    raise ValueError(report["issues"])

deck = BCGDeck(theme_config=template)

slide = deck.add_content_slide(
    report["slides"][0]["title"],
    source="Source: BCG analysis",
)
bounds = content_bounds()
render_pattern(deck, slide, "column_cards", data=report["slides"][0]["pattern"]["data"], bounds=bounds)
```

Canonical flow:

1. choose the template
2. lock font constants once
3. translate the approved plan into slide specs and run `preflight_deck(...)`
4. fix every preflight error before building — do NOT skip this step
5. scaffold structural slides
6. create each content slide with `add_content_slide(...)`
7. resolve bounds with `content_bounds(...)` — call AFTER `add_content_slide()`, never before
8. render with `render_pattern(...)` when a documented pattern exists
9. compose manually only when the family docs say the pattern is custom
10. save once at the end

## Orchestrated Build Path

In orchestrated mode, translate the approved plan into normalized `SlideSpec[]`, then:

1. assign slide slices by semantic family or section
2. render each slice in an isolated worker workdir
3. emit `SlideArtifact` outputs or mini-deck artifacts
4. assemble the final `.pptx` centrally

Never let multiple workers mutate the same unpacked PPTX tree.

## Inline Validation

`render_pattern(...)` automatically validates bounds after rendering and warns on overflow. `add_content_slide(...)` validates title length against the layout limit. These checks are built into the code path — no extra calls needed.

## Hard Rules

- never call `_add_slide_from_layout()` directly unless the relevant family doc explicitly documents a special-case runtime override
- never create manual title textboxes when the layout has a title placeholder
- source lines are automatic when `source=...` is passed to `add_content_slide(...)`
- sequential mode: build the full deck in one execution
- orchestrated mode: workers build isolated artifacts; final assembly remains centralized
- `detail=True` is the default for content slides

## Client Templates (.ee4p)

Use the same Plan -> Build -> QA workflow for client templates. The only difference is how the theme config is acquired.

```python
from pathlib import Path
from ingest_ee4p import ingest_ee4p

runtime_templates = Path.cwd() / "_runtime_templates"
template = ingest_ee4p("/path/to/client.ee4p", runtime_templates)

deck = BCGDeck(theme_config=template)
```

`ingest_ee4p(...)` returns a build-ready config for the current session. It includes `_template_dir` and `_master_pptx`, so `BCGDeck(theme_config=template)` works without manual patching.

Run QA against the same template config:

```python
issues = check_deck("output.pptx", theme_config=template)
```

## Client Template Persistence

When a `.ee4p` template is ingested into a runtime folder and the user wants it to remain available in the workspace, persist it:

```python
from template_registry import save_template

save_template(
    name=template["name"],
    config=template,
    template_dir=template["_template_dir"],
    availability="workspace",
)
```

After persistence, `get_template(name=template["name"])` can reload that template in later runs from the workspace registry.

## Dynamic Pattern Styles

Use dynamic styles to change a pattern's visual treatment without changing the slide's semantic family.

```python
from pattern_variants import list_variants, get_variant_info

list_variants("flywheel")
deck.set_pattern_variant("flywheel", "concentric_rings")
deck.set_pattern_variants({"kpi": "big_number_dashboard"})
```

Variant resolution order is:

1. explicit `variant=...`
2. per-deck overrides via `set_pattern_variant(...)`
3. template config `pattern_variants`
4. pattern `index.json`
5. `styles/_defaults.json` or persistent override defaults

Load `references/core/dynamic-styles.md` when you need persistent variants, cache resets, or template-level defaults.

## Content Density Requirements

Every content slide needs all of these:

1. visible visual structure through cards, tables, chart frames, process objects, or a deliberate split layout
2. light card bodies (`WHITE` or `LIGHT_BG`) with dark accents, not dark full-card bodies
3. all text fields populated with real content — cards should have substantive bullets (2-4 lines each), not just a title and one word
4. green accents, icon circles, header bars, or dividers
5. content filling 60%+ of the content zone — if content ends at y=4.7" with nothing below, add a callout box, KPI row, or summary bar (not on split layouts)

An empty card, placeholder text, or naked text boxes on the slide background are unfinished.

## Font Hierarchy

Use these sizes consistently across the entire deck:

- `TITLE_SIZE = 24` — action titles (set by the template placeholder)
- `SUBHEADER_SIZE = 16` — card headers, section labels, column headers
- `BODY_SIZE = 14` — body text, bullets, descriptions inside cards
- `LABEL_SIZE = 12` — captions, source annotations, small labels

Do not use 13pt, 11pt, or 10pt. The minimum body text size is 12pt. If content does not fit at 12pt, split the slide or reduce the content — do not shrink the font.

## Composition Recipes

Starting patterns for multi-element slides — adapt them, don't copy verbatim.

**Chart type is NOT always bar.** Use `add_chart(slide, chart_type, ...)` with the type that matches the argument:
- `"line"` for trends over time — Recipe 1 shows this
- `"bar_horizontal"` for ranked comparisons — Recipe 7 shows this
- `"bar"` for category comparisons
- `"doughnut"` for part-to-whole / share
- `"stacked_bar"` for composition breakdowns
- `"stacked_area"` for cumulative trends
See the Chart Type Selection table in plan.md for the full decision guide.

Every recipe uses `content_bounds()` for positioning, `text_on()` for contrast-safe text, and `card_fill_for_slide()` for theme-aware container fills. All recipes target full-page `content` / `d_title_only` layouts only.

### Recipe 1: Chart + KPI Row + Callout

A chart in the top 60%, a row of 3-4 KPI big numbers below, and a green-bordered callout at the bottom.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, card_fill_for_slide, columns

slide = deck.add_content_slide("Digital revenue grew 23% YoY driven by three product lines", source="Source: BCG analysis, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

# Chart — top 55% (line chart for trend over time)
chart_h = h * 0.55
deck.add_chart(slide, "line", ["Q1", "Q2", "Q3", "Q4"],
               [{"name": "Digital", "values": [42, 58, 71, 89]}, {"name": "Traditional", "values": [85, 80, 74, 68], "line_dash": "dash"}],
               x=x, y=y, w=w, h=chart_h)

# KPI tiles — middle band
kpi_y = y + chart_h + 0.15
kpi_h = 1.10
kpis = [("$89M", "Q4 Digital Rev", "+23%"), ("62%", "Digital Mix", "+8pp"), ("4.2x", "ROAS", "+0.6x")]
cols = columns(len(kpis), total_width=w, start_x=x, gutter=0.20)
card_fill = card_fill_for_slide()
for i, (cx, cw) in enumerate(cols):
    deck.add_card(slide, cx, kpi_y, cw, kpi_h, fill_color=card_fill, accent_color=COLORS["BCG_GREEN"], accent_position="top")
    deck.add_textbox(slide, kpis[i][0], cx + 0.10, kpi_y + 0.12, cw - 0.20, 0.40, sz=22, color=COLORS["BCG_GREEN"], bold=True, align="center")
    deck.add_textbox(slide, kpis[i][1], cx + 0.10, kpi_y + 0.52, cw - 0.20, 0.22, sz=12, color=text_on(card_fill), align="center")
    deck.add_textbox(slide, kpis[i][2], cx + 0.10, kpi_y + 0.78, cw - 0.20, 0.22, sz=12, color=COLORS["BCG_GREEN"], bold=True, align="center")

# Callout — bottom
co_y = kpi_y + kpi_h + 0.15
co_h = y + h - co_y
deck.add_rounded_rectangle(slide, x, co_y, w, co_h, card_fill_for_slide(), radius=5000, line_color=COLORS["BCG_GREEN"], line_width=1)
deck.add_textbox(slide, "Digital channels now account for >60% of revenue — accelerating investment in personalization could unlock an additional $25-30M by FY27",
                 x + 0.15, co_y, w - 0.30, co_h, sz=12, color=text_on(card_fill_for_slide()), valign="middle")
```

### Recipe 2: Two-Column Cards with Bottom Callout

Two equal columns, each with a header bar + icon + bullets, and a full-width callout spanning both columns.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, dark_fills, card_fill_for_slide, columns

slide = deck.add_content_slide("Two capability investments will close the margin gap", source="Source: BCG capability assessment, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

co_h = 0.50
card_h = h - co_h - 0.15
cols = columns(2, total_width=w, start_x=x, gutter=0.31)
fills = dark_fills(2)
card_fill = card_fill_for_slide()
items = [
    {"icon": "Strategy", "title": "Pricing Analytics Engine", "bullets": [
        "Deploy ML-based pricing across 1,200 SKUs in priority categories",
        "Integrate real-time competitor data feeds into pricing workflows",
        "Projected margin lift of 180-220bps within 12 months"]},
    {"icon": "DataAnalysis", "title": "Demand Sensing Platform", "bullets": [
        "Replace monthly S&OP cycle with weekly AI-driven demand signals",
        "Reduce forecast error from 38% to <15% on top-50 SKUs",
        "Cut safety stock by $45M while improving fill rate to 97%"]},
]

for i, (cx, cw) in enumerate(cols):
    deck.add_card(slide, cx, y, cw, card_h, fill_color=card_fill, accent_color=fills[i], accent_position="top")
    deck.add_rectangle(slide, cx, y, cw, 0.40, fills[i])
    deck.add_textbox(slide, items[i]["title"], cx + 0.10, y, cw - 0.20, 0.40, sz=16, color=text_on(fills[i]), bold=True, valign="middle")
    icon_cx = cx + cw / 2 - 0.30
    deck.add_oval(slide, icon_cx, y + 0.55, 0.60, 0.60, fills[i])
    deck.add_icon(slide, items[i]["icon"], icon_cx + 0.05, y + 0.60, size=0.50, color=text_on(fills[i]))
    deck.add_bullets(slide, items[i]["bullets"], cx + 0.15, y + 1.30, cw - 0.30, card_h - 1.45, sz=14, color=text_on(card_fill), spc_after=6)

# Full-width callout
co_y = y + card_h + 0.15
deck.add_rounded_rectangle(slide, x, co_y, w, co_h, card_fill_for_slide(), radius=5000, line_color=COLORS["BCG_GREEN"], line_width=1)
deck.add_textbox(slide, "Combined investment of $8-10M delivers $65M+ annual margin improvement — 6-8x ROI within 24 months",
                 x + 0.15, co_y, w - 0.30, co_h, sz=12, color=text_on(card_fill_for_slide()), valign="middle")
```

### Recipe 3: Data Table + Insight Annotation

A native table (left 60%) paired with an insight card on the right (40%) highlighting the key finding.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, card_fill_for_slide

slide = deck.add_content_slide("European operations lag NA peers on three efficiency metrics", source="Source: BCG benchmarking database, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

# Table — left 60%
table_w = w * 0.58
table_data = [
    ["Metric", "NA Avg", "EU Avg", "Gap"],
    ["Order-to-cash (days)", "4.2", "7.8", "-3.6"],
    ["Cost per transaction", "$1.05", "$2.40", "-$1.35"],
    ["First-pass yield", "96%", "88%", "-8pp"],
    ["SLA compliance", "99.1%", "93.4%", "-5.7pp"],
]
deck.add_table(slide, table_data, x=x, y=y, w=table_w, h=h,
               header=True, col_align=["left", "center", "center", "center"], sz=12)

# Insight card — right 40%
card_x = x + table_w + 0.20
card_w = w - table_w - 0.20
card_fill = card_fill_for_slide()
deck.add_card(slide, card_x, y, card_w, h, fill_color=card_fill, accent_color=COLORS["BCG_GREEN"], accent_position="left")
deck.add_rectangle(slide, card_x, y, card_w, 0.40, COLORS["BCG_GREEN"])
deck.add_textbox(slide, "Key Finding", card_x + 0.15, y, card_w - 0.30, 0.40, sz=16, color=text_on(COLORS["BCG_GREEN"]), bold=True, valign="middle")
deck.add_textbox(slide, "EU operations underperform NA across all four efficiency metrics. The order-to-cash gap alone represents ~$12M in trapped working capital annually.",
                 card_x + 0.15, y + 0.55, card_w - 0.30, 1.20, sz=14, color=text_on(card_fill))
deck.add_textbox(slide, [("Recommendation: ", {"bold": True}), ("Prioritize order-to-cash automation in EU — highest ROI at $4.2M NPV with 9-month payback.", {})],
                 card_x + 0.15, y + 1.90, card_w - 0.30, 1.00, sz=14, color=text_on(card_fill))
deck.add_textbox(slide, [("$12M", {"bold": True, "sz": 22, "color": COLORS["BCG_GREEN"]}), ("\ntrapped working capital", {"sz": 12})],
                 card_x + 0.15, y + h - 1.20, card_w - 0.30, 1.00, sz=14, color=text_on(card_fill), align="center")
```

### Recipe 4: Compact Row List with Takeaway

4-5 rows with icon + title + description + category label, and a green-bordered callout at the bottom.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, card_fill_for_slide

slide = deck.add_content_slide("Five operational changes will reduce unit cost by 18% within FY26", source="Source: BCG operations diagnostic, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

co_h = 0.50
avail_h = h - co_h - 0.15
rows = [
    {"icon": "Factory", "title": "Consolidate regional warehouses", "desc": "Merge 12 facilities to 5 hubs — saves $8M annually in fixed overhead", "label": "Supply Chain"},
    {"icon": "Automation", "title": "Automate inbound quality checks", "desc": "Vision-based inspection reduces headcount by 40 FTEs and cuts cycle time 30%", "label": "Manufacturing"},
    {"icon": "DataAnalysis", "title": "Implement dynamic routing", "desc": "ML-optimized last-mile routing cuts delivery cost per parcel by $0.35", "label": "Logistics"},
    {"icon": "Finance", "title": "Renegotiate tier-2 supplier contracts", "desc": "Leverage consolidated volume for 12-15% raw-material cost reduction", "label": "Procurement"},
]
n = len(rows)
gap = 0.12
row_h = (avail_h - gap * (n - 1)) / n
card_fill = card_fill_for_slide()
icon_size = 0.50

ry = y
for item in rows:
    deck.add_card(slide, x, ry, w, row_h, fill_color=card_fill, accent_color=COLORS["BCG_GREEN"], accent_position="left")
    deck.add_icon(slide, item["icon"], x + 0.35, ry + (row_h - icon_size) / 2, size=icon_size, color=COLORS["BCG_GREEN"])
    tx = x + 1.05
    deck.add_textbox(slide, item["title"], tx, ry + 0.08, 3.50, 0.24, sz=14, color=COLORS["BCG_GREEN"], bold=True)
    deck.add_textbox(slide, item["desc"], tx, ry + 0.34, w - 3.20, row_h - 0.44, sz=12, color=text_on(card_fill))
    deck.add_label(slide, item["label"], x + w - 1.85, ry + (row_h - 0.32) / 2, 1.65, 0.32, sz=12)
    ry += row_h + gap

# Takeaway callout
co_y = y + h - co_h
deck.add_rounded_rectangle(slide, x, co_y, w, co_h, card_fill_for_slide(), radius=5000, line_color=COLORS["BCG_GREEN"], line_width=1)
deck.add_textbox(slide, "Combined initiatives deliver $22M in annual savings — warehouse consolidation and supplier renegotiation account for 75% of the total",
                 x + 0.15, co_y, w - 0.30, co_h, sz=12, color=text_on(card_fill_for_slide()), valign="middle")
```

### Recipe 5: SCQA Executive Summary

Narrative cards stacked vertically — Situation, Complication, Question, Answer — with the Answer card highlighted in green.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, card_fill_for_slide

slide = deck.add_content_slide("Accelerate supply chain digitization to protect margin through the downturn", source="Source: BCG analysis")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

cards = [
    ("The NA logistics network was designed for steady-state growth of 3-5% — asset utilization averaged 82% through 2023",),
    ("Demand volatility has tripled since 2022 while carrier costs rose 28%, compressing gross margin by 340bps in the last four quarters",),
    ("Can the existing network absorb another demand shock, or does the company need to restructure before the next cycle?",),
    ("Invest $18M in a digital control tower and dynamic routing layer — modeling shows this recovers 200bps of margin within 18 months and creates optionality for further network redesign",),
]
n = len(cards)
gap = 0.12
card_h = (h - gap * (n - 1)) / n
card_fill = card_fill_for_slide()

cy = y
for i, (text,) in enumerate(cards):
    is_answer = (i == n - 1)
    bg = COLORS["BCG_GREEN"] if is_answer else card_fill
    deck.add_rounded_rectangle(slide, x, cy, w, card_h, bg, radius=5000)
    deck.add_textbox(slide, text, x + 0.20, cy + 0.10, w - 0.40, card_h - 0.20,
                     sz=14, color=text_on(bg), bold=is_answer, valign="middle")
    cy += card_h + gap
```

### Recipe 6: Process Flow with Milestone Callout

Chevron flow across the top with a summary callout at the bottom highlighting the key decision gate.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, dark_fills, card_fill_for_slide, columns

slide = deck.add_content_slide("Four-phase rollout reaches full-scale deployment by Q3 2026", source="Source: BCG implementation roadmap")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

# Chevron flow — top zone
flow_h = 0.70
deck.add_chevron_flow(slide, ["Discovery", "Pilot Design", "Regional Scale", "Full Deployment"],
                      x, y, w, flow_h)

# Phase detail cards — middle zone
co_h = 0.50
card_top = y + flow_h + 0.15
card_h = h - flow_h - co_h - 0.45
phases = [
    {"title": "Discovery\nQ4 2025", "bullets": ["Map 200+ process variants", "Identify top-10 automation targets", "Baseline current-state KPIs"]},
    {"title": "Pilot Design\nQ1 2026", "bullets": ["Build MVP for 3 priority use cases", "Validate ROI model with live data", "Secure steering committee approval"]},
    {"title": "Regional Scale\nQ2 2026", "bullets": ["Deploy to NA and EMEA hubs", "Train 150+ operators on new workflows", "Establish change-management cadence"]},
    {"title": "Full Deployment\nQ3 2026", "bullets": ["Extend to APAC and LATAM", "Activate real-time performance dashboard", "Transition to BAU operating model"]},
]
cols = columns(len(phases), total_width=w, start_x=x, gutter=0.20)
fills = dark_fills(len(phases))
card_fill = card_fill_for_slide()

for i, (cx, cw) in enumerate(cols):
    deck.add_card(slide, cx, card_top, cw, card_h, fill_color=card_fill, accent_color=fills[i], accent_position="top")
    deck.add_textbox(slide, phases[i]["title"], cx + 0.10, card_top + 0.10, cw - 0.20, 0.44, sz=14, color=text_on(card_fill), bold=True)
    deck.add_bullets(slide, phases[i]["bullets"], cx + 0.10, card_top + 0.58, cw - 0.20, card_h - 0.70, sz=12, color=text_on(card_fill), spc_after=4)

# Milestone callout
co_y = y + h - co_h
deck.add_rounded_rectangle(slide, x, co_y, w, co_h, card_fill_for_slide(), radius=5000, line_color=COLORS["BCG_GREEN"], line_width=1)
deck.add_textbox(slide, "Gate 2 (end of Pilot) is the critical go/no-go — the steering committee must validate $4.2M NPV before authorizing regional scale-up",
                 x + 0.15, co_y, w - 0.30, co_h, sz=12, color=text_on(card_fill_for_slide()), valign="middle")
```

### Recipe 7: Benchmark Comparison (Horizontal Bar + Callout)

A horizontal bar chart showing peer comparison, with a callout box below highlighting the key gap.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, card_fill_for_slide

slide = deck.add_content_slide("Operating margin trails top-quartile peers by 420bps", source="Source: BCG benchmarking, S&P Capital IQ, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

co_h = 0.50
chart_h = h - co_h - 0.15

# Horizontal bar chart — peer comparison
categories = ["Top-Quartile Avg", "Peer A", "Peer B", "Client", "Peer C", "Bottom-Quartile Avg"]
series = [{"name": "Operating Margin %", "values": [18.4, 17.1, 16.2, 14.0, 12.8, 10.5],
           "point_colors": [COLORS["MED_GRAY"]] * 3 + [COLORS["BCG_GREEN"]] + [COLORS["MED_GRAY"]] * 2}]
deck.add_chart(slide, "bar_horizontal", categories, series,
               x=x, y=y, w=w, h=chart_h, number_format="0.0%")

# Gap callout
co_y = y + chart_h + 0.15
deck.add_rounded_rectangle(slide, x, co_y, w, co_h, card_fill_for_slide(), radius=5000, line_color=COLORS["BCG_GREEN"], line_width=1)
deck.add_textbox(slide, [("420bps gap to top quartile ", {"bold": True}),
                          ("represents ~$58M in unrealized annual operating income — closing half the gap through procurement and SG&A optimization is achievable within 18 months", {})],
                 x + 0.15, co_y, w - 0.30, co_h, sz=12, color=text_on(card_fill_for_slide()), valign="middle")
```

### Recipe 8: Investment Waterfall with ROI Summary

A bar chart showing the cost/benefit bridge, with KPI tiles below showing NPV, IRR, and payback period.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, card_fill_for_slide, columns

slide = deck.add_content_slide("$42M transformation investment delivers 3.8x return over five years", source="Source: BCG financial model, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

# Waterfall bar chart — top 65%
kpi_h = 1.10
chart_h = h - kpi_h - 0.15
categories = ["Technology\nPlatform", "Change\nMgmt", "Process\nRedesign", "Talent\nUpskill", "Total\nInvestment", "Year 1\nBenefit", "Year 2\nBenefit", "Year 3-5\nBenefit", "Net\nValue"]
# Waterfall: use point_colors to distinguish cost (negative/gray) vs benefit (green) vs total (dark)
series = [{"name": "Value ($M)", "values": [-18, -8, -10, -6, -42, 22, 38, 100, 118],
           "point_colors": ["B0B0B0", "B0B0B0", "B0B0B0", "B0B0B0", COLORS["NAVY"], COLORS["BCG_GREEN"], COLORS["BCG_GREEN"], COLORS["BCG_GREEN"], COLORS["DEEP_GREEN"]]}]
deck.add_chart(slide, "bar", categories, series,
               x=x, y=y, w=w, h=chart_h, number_format="$#,##0", legend=False)

# ROI KPI tiles — bottom row
kpi_y = y + chart_h + 0.15
kpis = [("$118M", "5-Year Net Value", "NPV"), ("3.8x", "Return on Investment", "ROI"), ("22 mo", "Payback Period", "Breakeven"), ("34%", "Internal Rate of Return", "IRR")]
cols = columns(len(kpis), total_width=w, start_x=x, gutter=0.20)
card_fill = card_fill_for_slide()
accent = COLORS["BCG_GREEN"]

for i, (cx, cw) in enumerate(cols):
    deck.add_card(slide, cx, kpi_y, cw, kpi_h, fill_color=card_fill, accent_color=accent, accent_position="top")
    deck.add_textbox(slide, kpis[i][0], cx + 0.10, kpi_y + 0.12, cw - 0.20, 0.40, sz=22, color=accent, bold=True, align="center")
    deck.add_textbox(slide, kpis[i][1], cx + 0.10, kpi_y + 0.52, cw - 0.20, 0.25, sz=12, color=text_on(card_fill), align="center")
    deck.add_textbox(slide, kpis[i][2], cx + 0.10, kpi_y + 0.82, cw - 0.20, 0.20, sz=12, color=COLORS["MED_GRAY"], align="center")
```

Use these recipes as composition templates during build. Mix and match elements (charts, KPI rows, callout boxes, tables, icon rows, cards) to fill the content zone. Every content slide should have at least two distinct visual elements that work together to support the action title.

### Recipe 9: Funnel Journey

Narrowing bars encoding conversion drop-off at each stage. Width encodes quantity — wider = more, narrower = fewer survivors. Use for customer journeys, sales pipelines, hiring funnels.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, dark_fills

slide = deck.add_content_slide("Booking funnel loses 68% of users between search and payment", source="Source: BCG digital analytics, 2025")
bounds = content_bounds()
x, y, w, h = bounds["x"], bounds["y"], bounds["w"], bounds["h"]

stages = [
    {"label": "Search", "metric": "10.2M visits", "drop": ""},
    {"label": "Select Flight", "metric": "5.8M sessions", "drop": "-43%"},
    {"label": "Customize", "metric": "2.9M carts", "drop": "-50%"},
    {"label": "Payment", "metric": "1.8M checkouts", "drop": "-38%"},
    {"label": "Confirmation", "metric": "1.6M bookings", "drop": "-11%"},
]
n = len(stages)
fills = dark_fills(n)
gap = 0.12
bar_h = min(0.65, (h - gap * (n - 1)) / n)
max_w = w * 0.85
min_w = max_w * 0.30
width_step = (max_w - min_w) / max(n - 1, 1)

for i, stage in enumerate(stages):
    bw = max_w - i * width_step
    bx = x + (w - bw) / 2
    by = y + i * (bar_h + gap)
    deck.add_rounded_rectangle(slide, bx, by, bw, bar_h, fills[i], radius=8000)
    deck.add_textbox(slide, stage["label"], bx + 0.20, by, bw * 0.45, bar_h, sz=14, color=text_on(fills[i]), bold=True, valign="middle")
    deck.add_textbox(slide, stage["metric"], bx + bw * 0.50, by, bw * 0.30, bar_h, sz=12, color=text_on(fills[i]), align="right", valign="middle")
    if stage["drop"]:
        deck.add_textbox(slide, stage["drop"], bx + bw + 0.15, by, 0.60, bar_h, sz=14, color=COLORS["NEGATIVE"], bold=True, valign="middle")
```

### Recipe 10: Flywheel Loop

Circular nodes encoding a cyclical reinforcement process. Each stage feeds the next in a loop. Use for platform growth engines, continuous improvement, DevOps feedback loops.

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, dark_fills
import math

slide = deck.add_content_slide("Platform flywheel accelerates as each stage reinforces the next", source="Source: BCG analysis")
bounds = content_bounds()
cx = bounds["x"] + bounds["w"] / 2
cy = bounds["y"] + bounds["h"] / 2
orbit_r = min(bounds["w"], bounds["h"]) / 2 - 0.80
hub_r = orbit_r * 0.35
node_r = 0.65

nodes = [
    {"label": "Acquire\nCustomers", "metric": "+40% YoY"},
    {"label": "Generate\nUsage Data", "metric": "10K signals/day"},
    {"label": "Train AI\nModels", "metric": "+2% acc./month"},
    {"label": "Deliver\nInsights", "metric": "3x engagement"},
]
n = len(nodes)
fills = dark_fills(n)

# Hub
deck.add_oval(slide, cx - hub_r, cy - hub_r, hub_r * 2, hub_r * 2, COLORS["DEEP_GREEN"])
deck.add_textbox(slide, "Growth\nEngine", cx - hub_r, cy - 0.25, hub_r * 2, 0.50, sz=16, color=text_on(COLORS["DEEP_GREEN"]), bold=True, align="center", valign="middle")

# Nodes
for i in range(n):
    ang = math.radians(-90 + i * (360 / n))
    ncx = cx + orbit_r * math.cos(ang)
    ncy = cy + orbit_r * math.sin(ang)
    deck.add_oval(slide, ncx - node_r, ncy - node_r, node_r * 2, node_r * 2, fills[i], line_color=COLORS.get("WHITE", "FFFFFF"), line_width=2)
    deck.add_textbox(slide, nodes[i]["label"], ncx - node_r + 0.08, ncy - 0.30, node_r * 2 - 0.16, 0.40, sz=14, color=text_on(fills[i]), bold=True, align="center", valign="middle")
    deck.add_textbox(slide, nodes[i]["metric"], ncx - node_r + 0.08, ncy + 0.12, node_r * 2 - 0.16, 0.25, sz=12, color=text_on(fills[i]), align="center", valign="middle")

# Arrows between nodes
for i in range(n):
    a_deg = -90 + (i + 0.5) * (360 / n)
    a_rad = math.radians(a_deg)
    ax = cx + (orbit_r - node_r * 0.3) * math.cos(a_rad)
    ay = cy + (orbit_r - node_r * 0.3) * math.sin(a_rad)
    deck.add_shape(slide, "rightArrow", ax - 0.20, ay - 0.10, 0.40, 0.20, COLORS.get("MED_GRAY", "6E6F73"), rotation=a_deg + 90)
```

## Bottom-Up Sizing

Use the Engine Constraints section below for formulas. The key rule is to decide bottom elements first:

- callout
- legend
- summary bar
- footer-sensitive zones

Then size cards, rows, or charts to end above that ceiling.

## Patterns And Bounds

- full-page slides: `bounds = content_bounds()`
- split layouts: `bounds = content_bounds(layout_key)`
- use the layout family index first, then the relevant leaf doc

Use the family docs to decide whether the pattern should be rendered via `render_pattern(...)` or composed explicitly with direct API calls.

## Split Layout Rules

On split layouts (`arrow_half`, `green_left_arrow`, `green_one_third`, `green_highlight`, `green_half`, `green_two_third`):

- do not draw background rectangles that duplicate the slide master's accent panel — the layout already provides the colored zone. This applies to ALL split layouts with accent panels: `green_highlight` (right side), `arrow_half` (right side), `green_left_arrow` (left side), `green_one_third` (left side), `green_half` (left side). Adding `add_rectangle()`, `add_rounded_rectangle()`, or `add_card()` with the accent color in these zones creates a visible "floating container" artifact. Place content directly on the existing background.
- do not place elements that span across both the left and right zones — content must stay within its zone
- no takeaway boxes or summary banners on split layouts
- left-zone content stays in `bounds['left_x']` to `bounds['left_x'] + bounds['left_w']`; right-zone content stays in `bounds['right_x']` to `bounds['right_x'] + bounds['right_w']`
- the left zone on `arrow_half` is the accent panel (dark background) — use `text_on(accent_color)` for labels there, not the accent color itself

## Images

- use picture-placeholder families for main images
- prefer `add_stock_image(...)` or `fill_picture(...)`
- do not place hero images with arbitrary `add_image(...)` coordinates

## Charts

- default to native `add_chart()`
- use the merge path for combo and waterfall
- all callouts, highlights, and overlays must be added after the chart

## Icons

- resolve `icon_type` once per slide with `deck.resolve_icon_type(line_count)`
- keep icon style and type consistent within the slide
- when the exact icon name is unclear, use `deck.search_icons(query, icon_type='icon', limit=8)` to get ranked candidates
- do not shell-search `assets/icons` or inspect `icons_bundle.json` manually during normal slide creation

## Phase Transition

When Build is complete, proceed directly to QA. Do not stop for user approval between Build and QA.

---

# API Quick Reference

Import and setup:

```python
from bcg_template import (
    BCGDeck,
    columns,
    content_bounds,
    COLORS,
    CONTENT_START_Y,
    CONTENT_END_Y,
    DETAIL_CONTENT_START_Y,
    text_on,
    dark_fills,
    check_setup,
)
from pattern_variants import render_pattern, list_variants, get_variant_info, clear_cache
from qa import check_deck
from template_registry import list_templates, get_template, format_template_menu, save_template
from ingest_ee4p import ingest_ee4p
```

Start each build with a template and locked font constants:

```python
check_setup()

template = get_template(name="bcg_default")
deck = BCGDeck(theme_config=template)

TITLE_SIZE = 24
SUBHEADER_SIZE = 16
BODY_SIZE = 14
LABEL_SIZE = 12
```

Use these sizes consistently across the deck. `12pt` is the absolute floor for narrow columns or dense detail views; default body copy should stay at `14pt`.

## Core Flow

```python
slide = deck.add_content_slide("Action title as a sentence", source="Source: BCG analysis")  # detail=True by default
bounds = content_bounds()
render_pattern(deck, slide, "column_cards", data={...}, bounds=bounds)
deck.save("output.pptx")
issues = check_deck("output.pptx", theme_config=template)
```

`add_content_slide()` uses `detail=True` by default -- this is the workhorse layout (`d_title_only`) for ~86% of slides. Pass `detail=False` only for 2-3 key-message slides per deck.

**Source lines are automatic.** When you pass `source="Source: BCG analysis"` to `add_content_slide()`, the source line is placed at y=6.74" automatically. Do NOT add a manual source textbox after this — it creates duplicate overlapping sources.

All slides must be built in a single execution. Scaffold structural slides first, then render all content slides in the same pass.

## Canonical Pattern Path

The canonical content path is:

1. `add_content_slide(...)`
2. `content_bounds(layout_key)` if the slide uses a split family
3. `render_pattern(...)` for documented patterns

```python
slide = deck.add_content_slide(
    "Three capabilities unlock the value pool",
    source="Source: BCG analysis",
)
bounds = content_bounds()
render_pattern(deck, slide, "column_cards", data={
    "items": [
        {"icon": "Strategy", "title": "Capability one", "bullets": ["Detail", "Detail"]},
        {"icon": "DataAnalysis", "title": "Capability two", "bullets": ["Detail", "Detail"]},
        {"icon": "Target", "title": "Capability three", "bullets": ["Detail", "Detail"]}
    ]
}, bounds=bounds)
```

Use direct `deck.add_*` composition only when the family docs explicitly describe the pattern as custom or highly manual.

## Dynamic Style Overrides

Discover available treatments before overriding them:

```python
list_variants("flywheel")
get_variant_info("flywheel", "concentric_rings")

deck.set_pattern_variant("flywheel", "concentric_rings")
deck.set_pattern_variants({
    "kpi": "big_number_dashboard",
    "split_panel": "green_highlight_insights",
})
```

`render_pattern(...)` resolves variants in this order:

1. explicit `variant=...`
2. per-deck overrides from `set_pattern_variant(...)`
3. template config `pattern_variants`
4. pattern `index.json`
5. `styles/_defaults.json` or a persistent override file

Use `clear_cache()` after installing or editing persistent variants under `~/.deckster-slide-generator/styles/variants/` or `/mnt/user-data/deckster-slide-generator/styles/variants/`.

## Client Templates (.ee4p)

```python
from pathlib import Path

runtime_templates = Path.cwd() / "_runtime_templates"
template = ingest_ee4p("/path/to/client.ee4p", runtime_templates)

deck = BCGDeck(theme_config=template)
# build as usual
deck.save("output.pptx")
issues = check_deck("output.pptx", theme_config=template)

save_template(name=template["name"], config=template, template_dir=template["_template_dir"])
```

`ingest_ee4p(...)` returns a build-ready config for the current session, including `_template_dir` and `_master_pptx`. Persist it only when the user wants the template available in later runs.

## Structural Slides

Use the template-driven methods; do not rebuild these manually:

```python
deck.add_title_slide(title, subtitle="", date="", detail=False)
deck.add_section_divider(title, layout="section_header_box", detail=False)
deck.add_quote_slide(quote, attribution="", detail=False)
deck.add_agenda_slide(["Item 1", "Item 2"], detail=False)
deck.add_disclaimer(detail=False)
deck.add_end_slide(detail=False)
```

Section dividers carry the title only. If the opener needs supporting points, put them on the next content slide.

## Content Slides

Standard path (`detail=True` is the default — uses the `d_` detail layout variants with white background and smaller titles):

```python
slide = deck.add_content_slide("Action title as sentence", source="Source: BCG analysis")
# detail=True is implicit — this produces a d_title_only slide
```

Key-message variant (use sparingly — 2-3 per deck max):

```python
slide = deck.add_content_slide("Bold statement", detail=False)
# detail=False uses the standard gray-background layout with larger titles
```

**`detail=True` is the default for all content slides.** Do not pass `detail=False` unless the slide is specifically a high-impact key-message or statement slide.

**Do not call `_add_slide_from_layout()` directly.** Use `add_content_slide(..., layout=...)` so the title placeholder inherits template formatting.

## Theme-Aware Text And Fill

When text sits on a colored shape, always resolve the text color from the background:

```python
fill = COLORS["NAVY"]
deck.add_rectangle(slide, x, y, w, h, fill)
deck.add_textbox(slide, "Title", x, y, w, h, color=text_on(fill), bold=True)
```

Never hardcode white text on an arbitrary fill. `text_on()` and `dark_fills()` exist to keep contrast safe across BCG default and client templates.

Use `dark_fills(n)` instead of hardcoded color lists like `[COLORS['DEEP_GREEN'], COLORS['NAVY']]`. It returns n distinct dark colors from the active theme, all with white contrast >= 3.5:1.

## Icons

```python
deck.add_icon(slide, icon_name, x, y, size=0.75, color=None, icon_type='icon')
deck.search_icons(query, icon_type='icon', limit=8)
```

Icon sizing by row height: rows >=1.0" → `size=0.60-0.75`; rows 0.70-1.0" → `size=0.50-0.60`; compact rows <0.70" → `size=0.40`.

Icon type decision (once per slide): count total text lines (title=1 + bullets + table rows + body paragraphs). If <15 lines use `icon_type='icon'`; if >=15 use `icon_type='bug'`. All icons on a slide must use the same type.

If the exact icon name is unclear, search the bundle from Python first instead of shell-scanning the asset directory:

```python
deck.search_icons("supply chain logistics", limit=6)
deck.search_icons("pricing risk", icon_type="bug", limit=6)
```

`search_icons()` returns ranked candidates with `name`, `key`, and `score`. Use it to choose a valid bundled icon name, then call `add_icon()`. Do not shell-search `assets/icons` or inspect `icons_bundle.json` manually during normal slide creation.

```python
line_count = 1 + len(bullets)
icon_type = deck.resolve_icon_type(line_count)
deck.add_icon(slide, 'Strategy', cx, cy, size=0.75, color=text_on(accent), icon_type=icon_type)
```

## Common Methods

```python
deck.add_textbox(slide, text, x, y, w, h, sz=12, color=None, bold=False,
                 align="left", valign="top", autofit=False, vertical=False, bg=None)
deck.add_bullets(slide, items, x, y, w, h, sz=12, color=None, spc_after=6, bg=None)
deck.add_rectangle(slide, x, y, w, h, fill_color, line_color=None, line_width=None, shadow=False, dash=None)
deck.add_rounded_rectangle(slide, x, y, w, h, fill_color, radius=16667,
                           line_color=None, line_width=None, shadow=False, dash=None)
deck.add_card(slide, x, y, w, h, fill_color="FFFFFF", shadow=True,
              accent_color=None, accent_position="top", radius=5000,
              line_color=None, line_width=None, dash=None)
deck.add_label(slide, text, x, y, w, h=0.35, fill_color=None, text_color=None, sz=11)
deck.add_stamp(slide, text, x, y, w=1.8, h=0.35, fill_color=None, text_color=None, sz=11)
deck.add_section_breadcrumb(slide, text, x=0.69, y=1.60, w=2.5, h=0.40,
                            fill_color=None, text_color=None, sz=10)
deck.add_oval(slide, x, y, w, h, fill_color, line_color=None, line_width=None)
deck.add_line(slide, x, y, w, h=0, color="29BA74", width=2, dash=None)
deck.add_number_badge(slide, number, x, y, size=0.4)
deck.add_image(slide, image_path, x, y, w, h)
deck.add_gradient_rectangle(slide, x, y, w, h, color1, color2, angle=0)
deck.add_shape(slide, preset, x, y, w, h, fill_color, line_color=None, line_width=None, rotation=None)
deck.add_connector_dots(slide, x_start, x_end, y, n_dots=3, dot_size=0.12, color="29BA74")
deck.add_chevron_flow(slide, labels, x, y, w, h, colors=None)
deck.add_icon(slide, icon_name, x, y, size=0.75, color=None)
deck.search_icons(query, icon_type='icon', limit=8)
deck.add_chart(slide, chart_type, categories, series, x=0.69, y=CONTENT_START_Y, w=11.96, h=4.0, **options)
deck.add_table(slide, data, x=0.69, y=CONTENT_START_Y, w=11.96, h=None, header=True,
               col_widths=None, col_align=None, sz=11, header_color=None, stripe=True)
deck.set_speaker_notes(slide, text)
```

Method notes:

- `autofit=True` helps with vertical overflow in tight matrix or org-chart labels.
- `vertical=True` rotates text 270 degrees for row labels or matrix axes.
- `add_card()` is the default container method for most structured content. Let the engine choose fill color unless a specific contrast treatment is required.
- `accent_position="top"` is the safer default for light-fill cards. `accent_position="left"` should be used only when the card boundary is otherwise obvious.
- Use `add_line()` for dividers. Do not fake lines with ultra-thin rectangles.
- Use dashed borders for illustrative or placeholder objects, not for final-state containers.

## Card Sizing And Padding

Leave at least `0.15"` between the last line of content and the bottom of the card.

Sizing guidance:

- 3-4 bullets: `h=3.5-3.8`
- 5-6 bullets: `h=4.0-4.5`
- if a card leaves 40%+ dead space below the content, reduce the card height or anchor the slide with a bottom callout

## Images

For main visuals, use dedicated picture-placeholder layouts instead of arbitrary placement.

Primary image layouts:

- `green_half`: right half image zone
- `green_two_third`: right one-third image zone

These are title-led image layouts:

- the left panel belongs to the title placeholder
- do not add manual textboxes, bullets, cards, or overlays on the left panel
- if the slide needs body copy, use another family instead of forcing it into these layouts

Flow:

1. choose an image-capable semantic layout
2. try `add_stock_image()`
3. if no match, use `fill_picture()` with a generated or user-provided asset

```python
slide = deck.add_content_slide(
    "AI-first operations will redefine costs",
    layout="green_half",
)
deck.add_stock_image(slide, ["logistics", "warehouse", "supply chain"])
```

Prefer:

- `deck.fill_picture(slide, path)`
- `deck.add_stock_image(slide, tags, match_mode="any")`
- `BCGDeck.select_image_by_tags(tags, match_mode="any")`

Use `add_image()` only for small accents, overlays, or non-placeholder placements.

## Rich Text

`add_textbox()` and `add_bullets()` accept mixed-format runs.

```python
deck.add_textbox(slide, [
    ("Revenue grew ", {}),
    ("+23%", {"bold": True, "color": "29BA74"}),
    (" year-over-year", {}),
], x, y, w, h, sz=14)

deck.add_textbox(slide, [
    [("Headline", {"sz": 18, "bold": True, "color": "29BA74"})],
    [("Body text with ", {}), ("emphasis", {"bold": True}), (" inline.", {})],
], x, y, w, h, sz=12)

deck.add_bullets(slide, [
    "Plain bullet",
    [("Key metric: ", {"bold": True}), ("+23%", {"bold": True, "color": "29BA74"}), (" growth", {})],
], x, y, w, h, sz=14)
```

Supported run overrides: `sz`, `color`, `bold`, `italic`, `underline`, `strikethrough`, `highlight`, `superscript`, `subscript`, `font`.

## Grid And Placement

`columns(n)` returns `(x, w)` pairs across the standard content width.

Working vertical zones:

- standard content: `CONTENT_START_Y` to `CONTENT_END_Y`
- detail content: `DETAIL_CONTENT_START_Y` to `CONTENT_END_Y`

Use tighter starts only when content truly requires it. Do not crowd the title zone to compensate for a weak slide split.

### Per-Layout Content Zones

For split layouts (`green_highlight`, `green_one_third`, `green_left_arrow`, `arrow_half`, etc.), use `content_bounds()` to get dynamic zone boundaries that adapt to the active template:

```python
bounds = content_bounds('green_highlight')
# bounds['x'], bounds['y'], bounds['w'], bounds['h'] -- primary authored-content zone
# bounds['full_x'], bounds['full_y'], bounds['full_w'], bounds['full_h'] -- full fly zone
# bounds['left_x'], bounds['left_w'] -- left content zone
# bounds['right_x'], bounds['right_w'] -- right accent/insight zone
# bounds['x_end'], bounds['y_end'] -- right/bottom edges

# Use for split-layout content placement:
left_w = bounds['left_w']    # max width for left-side charts/tables
right_x = bounds['right_x']  # x start for right panel content
right_w = bounds['right_w']  # width of right panel
```

On title-left families (`green_one_third`, `green_left_arrow`, `green_half`, `green_two_third`, and detail variants), `bounds['x']/['w']` are normalized to the right-side authored-content zone so generic content does not land in the reserved title panel. Use `full_x/full_w` only when you intentionally need the full fly zone for non-content geometry.

Without a layout key, `content_bounds()` returns the active slide's authored-content bounds when called after `add_content_slide(...)`. Only use hardcoded coordinates when a family doc explicitly documents a custom exception. Do not hardcode split points like `left_w=6.8` or `right_x=8.2` -- these only apply to BCG default and will be wrong for ee4p templates.

For manual stacks inside split layouts, use the safe band itself rather than the full slide height:

```python
bounds = content_bounds()
heights = [1.10, 1.10, 1.10]
ys = stack_y_positions(bounds, heights, gap=0.12)
```

## Charts, Tables, And Notes

- Use `add_chart()` for native editable charts. BCG styling is applied automatically.
- Use `add_table()` for native PowerPoint tables with standard header/stripe treatment.
- Use `set_speaker_notes()` for presenter notes. Keep to a few tight bullets.
- Use `render_pattern()` for documented higher-level patterns such as exec summaries, timeline cards, KPI rows, maturity matrices, and multi-column structures.
- `render_pattern()` now performs preflight validation. If it raises, shorten copy, split the slide, or switch to a safer pattern before continuing.

Read the pattern families before rendering:

- `../charts/index.md`
- `../frameworks/index.md`
- `../process/index.md`

---

# Engine Constraints

## Structural Rules

- Use the title placeholder unless a documented runtime pattern explicitly overrides it.
- Structural slides remain structural. Do not add bullets, quotes, or shapes to section dividers.
- Every client-facing deck ends with `add_disclaimer()` followed by `add_end_slide()`.
- Footer, page number, source line, and copyright behavior come from the active template manifest.

## Content Bounds

Key Y-coordinate constants (BCG default; other templates may vary):

- `CONTENT_START_Y = 2.27"` (standard layouts)
- `DETAIL_CONTENT_START_Y = 1.70"` (detail layouts — smaller title, more room)
- `CONTENT_START_Y_TIGHT = 1.65"` (fallback when content overflows)
- `CONTENT_END_Y = 6.50"` (content must not extend past this)
- `SOURCE_Y = 6.74"` (source line position)
- Slide dimensions: 13.33" × 7.50"

Content + footer coexistence — plan bottom-up:

1. Decide where the bottom element goes (callout, legend, summary bar)
2. `effective_ceiling = bottom_element_y - 0.15"`
3. `max_card_h = effective_ceiling - card_start_y`
4. For N stacked cards with gaps: `card_h = (available_h - (N-1) * gap) / N`
5. Example: callout at y=6.10", 3 cards starting at 2.10" with 0.15" gaps → available=3.85" → per card=(3.85-0.30)/3=**1.18"**

Content density thresholds:

- Content must fill 60%+ of the content zone area
- Content must extend to at least y=5.3" — if cards/charts end at y=4.7" the lower third is wasted
- Always leave >=0.15" vertical gap between distinct visual elements
- Card padding: leave >=0.15" between last line of text and card bottom edge

Legend space reservation:

- Reserve legend space BEFORE sizing content (legends need 0.30-0.40" at y≈6.35-6.45")
- `content_end_y = legend_y - 0.15"` — size all content to end above that

Row-based layouts with bottom callout:

- `available_h = callout_y - 0.15 - CONTENT_START_Y`
- `max_rows = floor(available_h / row_h)`
- Never generate more rows than `max_rows`

If content does not fit, simplify or split the slide. Do not push content down to compensate for a title that should have been shortened.

## Contrast And Fill

- Use `text_on(fill_color)` for text placed on colored shapes.
- Do not hardcode white text on arbitrary fills.
- Let card fills auto-adapt to the slide background unless the pattern explicitly needs a custom fill.
- Never use white cards on white/detail backgrounds without a clear border or contrasting surface.

## Density Rules

Every content slide should have:

1. visible structure through cards, chart frames, table treatment, or deliberate layout
2. contrast between the slide background and the content container
3. a green accent, icon treatment, separator, or equivalent visual hierarchy device
4. one primary message carried by the title and one primary evidence structure below it

Avoid:

- text-only walls
- equal-weight grids for ranked content
- flows for non-sequential ideas
- dense bullets without spacing

## Chart And Table Rules

- Add charts before callouts, reference boxes, or overlay annotations. Native charts cover earlier shapes.
- Use one chart per slide unless the second visual is directly subordinate and clarifies the same argument.
- Do not place background cards behind native tables.
- For table columns: left-align text, center short numerics, right-align longer numerics.

## Image Rules

- Main images belong in picture-placeholder layouts, not arbitrary coordinates.
- Do not use image-led layouts unless the image materially proves the slide message.
- Some image layouts intentionally omit source/page placeholders; do not add those elements manually.

## Detail Mode Versus Key Message Mode

- **`detail=True` is the default** and the workhorse for ~86% of slides. Most consulting slides are data-rich and benefit from the extra content space.
- `detail=False` is for 2-3 bold key-message or statement slides per deck that need the gray background and larger title treatment.
- When in doubt, use detail mode. Pass `detail=False` only when the slide is specifically a high-impact visual statement.

## Workflow Integrity

- Choose the semantic family first, then the concrete template layout.
- Defer renderer choices, icon variants, and minor geometry workarounds until build time.
- Build the full deck in one run so deck state, theme state, and slide numbering remain consistent.

---

# Visual System

## Typography

- Titles are action titles and should visually dominate the slide.
- Default title size is `24pt` for standard action titles.
- Subheaders are typically `16pt`.
- Body text is typically `14pt`.
- `12pt` is the absolute floor for dense rows or narrow columns.
- Use Trebuchet MS unless the active client template overrides the theme font.

Formatting rules:

- body text is left-aligned by default
- center only titles, metric labels, or intentional card treatments
- do not underline except for true hyperlinks
- avoid italics in consulting body text
- use bold selectively for labels, values, and local emphasis

## Text Contrast — Critical Rule

**Use `text_on(fill_color)` for EVERY text element placed on ANY colored shape.** This is non-negotiable. It applies to:

- rectangles, rounded rectangles, cards, ovals, banners, chevrons
- accent bars, callout boxes, KPI tiles
- any shape created with `add_rectangle`, `add_rounded_rectangle`, `add_card`, `add_oval`, or `add_shape`

`text_on()` uses luminance-based contrast detection to return the optimal text color (white on dark fills, dark text on light fills). Never hardcode `'FFFFFF'` or `'575757'` on colored shapes — let `text_on()` decide.

For text directly on the slide background (not inside any shape): use `text_on(COLORS.get('SLIDE_BG', 'F2F2F2'))`. This adapts automatically to both gray (standard) and white (detail) backgrounds, and to client templates with custom slide backgrounds.

Use `dark_fills(n)` instead of hardcoded color lists like `[COLORS['DEEP_GREEN'], COLORS['NAVY']]`. It returns n distinct dark colors from the active theme, all with white contrast >= 3.5:1.

| Background | Text color | Never use |
|---|---|---|
| Dark shapes (575757, accent fills) | `text_on(fill)` → WHITE | DARK_TEXT, MED_GRAY |
| Green panels (green_half, green_one_third) | `text_on(fill)` → WHITE | LIME, LIGHT_TEXT |
| Standard slide BG (gray) | `text_on(slide_bg)` | WHITE, LIGHT_TEXT, B0B0B0 |
| Detail slide BG (white) | `text_on(slide_bg)` | WHITE, LIGHT_TEXT, B0B0B0 |
| White cards | `text_on(card_fill)` | WHITE, LIGHT_TEXT |

## Shape-to-Background Contrast

Every shape's fill must also contrast with whatever is behind it — the slide background or any containing shape.

**Container fills are automatic.** `add_card()`, `add_rounded_rectangle()`, and `add_rectangle()` auto-select the correct fill when you omit `fill_color`:

| Slide background | Auto container fill | Why |
|---|---|---|
| Gray (standard, `detail=False`) | `WHITE` (FFFFFF) | White cards pop against gray |
| White (detail, `detail=True`) | `LIGHT_BG` (F2F2F2) | Light gray provides subtle separation |
| Green panel | `WHITE` (FFFFFF) | White contrasts against green |

**Never use `FFFFFF` on detail slides** — white boxes on white have no boundary. Omit `fill_color` and the engine auto-detects.

**Icon colors on colored circles:** Use `color=text_on(circle_fill)` for icon color, not just text. Example:

```python
accent = COLORS['BCG_GREEN']
deck.add_oval(slide, cx, cy, sz, sz, accent)
deck.add_icon(slide, 'Strategy', cx + offset, cy + offset, size=0.75, color=text_on(accent))
```

**Visual polish rules (apply to ALL patterns):**

1. **text_on() everywhere** — all text on colored shapes AND all icon colors on colored circles
2. **dark_fills(n) for ACCENT elements only** — use for header bars, icon circles, badges, and banners. Do NOT use dark fills as full card body backgrounds — cards should use WHITE or LIGHT_BG with a dark accent bar at top (`accent_color=..., accent_position='top'`). Dark card bodies make slides look heavy and hard to read.
3. **Card borders** — use `line_color=accent, line_width=1.5` on rounded rectangles. Do NOT add separate thin accent bars (causes white gaps at corners)
4. **Color-varied headers** — use `dark_fills(n)` for header bars and icon circles in multi-item layouts (stacks, grids, org charts). The card body below stays WHITE or LIGHT_BG.
5. **Explicit padding** — card content inset 0.15" from edges, 0.15" gap between header and body, 0.3" top padding
6. **Auto-border** — if a shape fill is too close to the slide background, the engine adds a faint border automatically

**Card coloring pattern (correct):**
```python
fills = dark_fills(3)  # for HEADER BARS and ICON CIRCLES only
for i, (x, w) in enumerate(cols):
    # Light card body (auto-fill)
    deck.add_card(slide, x, y, w, card_h, accent_color=fills[i], accent_position='top')
    # Dark header bar at top of card
    deck.add_rectangle(slide, x, y, w, 0.35, fills[i])
    deck.add_textbox(slide, header, x+0.1, y, w-0.2, 0.35, sz=14, color=text_on(fills[i]), bold=True)
    # Body text on light background
    card_fill = COLORS.get('WHITE', 'FFFFFF')
    deck.add_textbox(slide, body, x+0.15, y+0.50, w-0.3, card_h-0.65, sz=14, color=text_on(card_fill))
```

**Anti-pattern (wrong — produces heavy, hard-to-read slides):**
```python
# WRONG: entire card is dark
deck.add_rounded_rectangle(slide, x, y, w, card_h, fills[i])  # dark body
deck.add_textbox(slide, body, x, y, w, card_h, color=text_on(fills[i]))  # white text on dark
```

## Color Roles

Always use `COLORS["KEY_NAME"]` to reference colors — never hardcode raw hex values.

**`BCG_GREEN` (29BA74) is the primary brand color.** Use it for:
- Title text color
- Table header fills (the `add_table()` method uses BCG_GREEN by default)
- Primary accent bars, borders, and highlights
- Icon circle fills (the default); graduated layouts use `[DEEP_GREEN, DARK_GREEN, BCG_GREEN, TEAL]`
- Chevron flow fills
- Callout box borders
- Card accent bars: BCG_GREEN for positive/target state; MED_GRAY for neutral/current state

`DARK_GREEN` and `DEEP_GREEN` are for **secondary variety only** — use them when you need 2-3 distinct accent colors in a multi-item layout (e.g., via `dark_fills(n)`). They should never replace `BCG_GREEN` as the dominant accent on a slide.

| Role | COLORS key | Default hex | When to use |
|---|---|---|---|
| **Primary brand green** | `BCG_GREEN` | `29BA74` | Default for all accents, titles, borders, icons, table headers |
| Dark green | `DARK_GREEN` | `197A56` | Secondary accent for variety in multi-item layouts |
| Deep green | `DEEP_GREEN` | `03522D` | Tertiary accent, darkest contrast in graduated layouts |
| Teal accent | `TEAL` | `3EAD92` | Medium accent in graduated layouts |
| Body text | `DARK_TEXT` | `575757` | All body text on light backgrounds |
| Muted gray | `MED_GRAY` | `6E6F73` |
| Light background | `LIGHT_BG` | `F2F2F2` |
| White | `WHITE` | `FFFFFF` |
| Navy accent | `NAVY` | `295E7E` |
| Negative / risk | `NEGATIVE` | `D64454` |

These are the only permitted colors. Rules:

- never use pure black (`000000`) as body text -- use `COLORS["DARK_TEXT"]`
- never introduce off-palette decorative colors (no custom blues, oranges, purples, or yellows)
- never use red, orange, or yellow for text, fills, icons, or outlines
- use white text on green surfaces, not lime
- use green to highlight the insight-carrying point, not everything
- for shape fills, always access via `COLORS` dict so client templates can override

## Source Line

- 10pt, `#6E6F73` (MED_GRAY), at y=6.74"
- Citation format: 'Source: [Organization], [Publication], [Year]'

## Visual Hierarchy

- title first
- headers second
- body copy third
- sources and captions last

Every content slide should have at least one real visual structure:

- chart
- table
- cards
- icon row
- process flow
- matrix
- deliberate split layout

Text-only slides are almost always under-designed.

## Spacing

- white space is structural, not wasted
- leave padding inside cards
- keep similar objects aligned on a common grid
- avoid cramming content by shrinking fonts before considering a better pattern

## Content Treatment

- maximum 6 bullets on a standard slide
- use `spc_after=6` as the normal bullet rhythm
- use `spc_after=10` when a sparse layout needs more breathing room
- replace long bullet walls with rows, cards, columns, or a process shape

## Card Fill Contrast

| Slide Background | Card Fill |
|---|---|
| Gray (standard) | WHITE |
| White / detail | LIGHT_BG (F2F2F2) |
| Green panel | WHITE |

## Key Message Versus Detail

| Attribute | Key Message Slide | Detail Slide |
|---|---|---|
| Background | gray | white |
| Min text size | 18pt | 12pt |
| Density | minimal | evidence-rich |
| Use case | projected / glanced | printed / read on device |

## Deck End-State

Standard flow:

`Title -> Exec Summary -> Agenda -> Sections -> Recommendations / Next Steps -> Appendix -> Disclaimer -> End`

The disclaimer and end slide are mandatory closing slides for client-facing decks.

# QA

Authoritative QA runtime surface. Read this for the blocking QA loop, checklist, failure modes, and mandatory visual review process.

# QA Contract

Use this file in Phase 3. It defines the blocking checks and review loop.

## Mode Fork

The QA bar is identical in both modes.

- **Sequential mode**: one agent runs programmatic QA and rendered-image inspection end to end.
- **Orchestrated mode**: the parent reducer owns deck-level QA and fix batching, while per-slide rendered-image inspection may fan out to parallel workers.

When `supports_subagents=true`, also read `references/runtime/orchestration.md`.

## Mandatory Visual Review — Render and Inspect Every Slide

Visual QA is not optional. Immediately after the first saved `.pptx`, you MUST render every slide as an image and visually inspect it. Programmatic shape-coordinate inspection (reading x/y/w/h from Python) is NOT a substitute — text overflow, truncation, and overlap are only visible in rendered pixels.

`check_deck(...)` is supporting signal only. Use it to accelerate fixes, but never as a substitute for looking at the rendered slides.

### Required Rendering Steps

After `deck.save(...)`, execute these steps before reporting QA results:

```python
import subprocess
from pdf2image import convert_from_path
import os

# 1. Convert to PDF
subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", output_path], check=True)

# 2. Render each slide as PNG
pdf_path = output_path.replace(".pptx", ".pdf")
os.makedirs("slides_qa", exist_ok=True)
images = convert_from_path(pdf_path, dpi=200)
for i, img in enumerate(images):
    img.save(f"slides_qa/slide_{i+1}.png", "PNG")
```

3. Visually inspect EVERY slide PNG and log issues per slide:
   - use whatever rendered-image inspection capability the runtime exposes
4. Fix all visible issues before presenting the deck.

Do NOT skip this step. Do NOT substitute it with reading shape positions from Python.

If LibreOffice or pdf2image are unavailable, tell the user and provide install instructions:
- **macOS**: `brew install --cask libreoffice && brew install poppler`
- **Linux**: `apt install libreoffice poppler-utils`

If rendering tools cannot be installed, rely on `check_deck()` programmatic QA and clearly note to the user that visual review was not performed.

## Programmatic QA

Run QA immediately after `deck.save(...)`:

```python
issues = check_deck(output_path, theme_config=template)
high = [issue for issue in issues if issue[1] == "HIGH"]
print(f"QA: {len(issues)} total, {len(high)} HIGH")
for slide_num, severity, message in issues:
    print(f"  Slide {slide_num} [{severity}]: {message}")
```

## Blocking Rule

HIGH issues are blocking for final delivery. Fix them before presenting the deck as complete.

MEDIUM issues are advisory unless they are visibly harming readability, hierarchy, or client readiness in the native preview. Do not automatically rebuild just because `check_deck(...)` reports MEDIUMs; use visual review to decide whether they are real defects or density heuristics.

Do not interpret this as "wait for zero HIGH issues before the first visual pass." The required order is:

1. save the deck
2. run `check_deck(...)`
3. render every slide to PNG (LibreOffice → PDF -> pdf2image) and visually inspect each image
4. log visible issues per slide (text truncation, overlap, alignment, clipping, empty space)
5. fix blocking and visible issues in a single batched edit pass
6. re-execute, re-render, and re-check until clean

## Fix Strategy

When fixing issues, **batch all fixes into a single edit pass on the existing build script**, then re-execute once. Do not rewrite the entire file. Do not fix one issue at a time with separate tool calls.

1. Read the QA report — note all HIGH issues and their slide/line numbers
2. Apply ALL fixes in one edit operation (or as few as possible)
3. Re-execute the script once
4. Re-run `check_deck(...)` once

Typical fixes (batch these together):

- light text on light backgrounds -> change `color=` to `text_on(fill_color)`
- title too long -> shorten the title string
- zone bleed -> change `w=` to stay inside bounds
- font too small -> change `sz=` value
- text overlap -> reduce card height, row count, or reposition

Repeat `check_deck(...)` until zero HIGH issues remain before final delivery.

Once HIGH issues are cleared:

1. use the rendered slide images to judge the remaining MEDIUMs
2. fix only the MEDIUMs that are visibly real
3. stop when the deck is presentation-ready, even if a few heuristic MEDIUMs remain

## QA Loop

Use this loop for every generated deck:

```python
from qa import check_deck

output_path = "output.pptx"
issues = check_deck(output_path, theme_config=template)
high_issues = [(s, sev, msg) for s, sev, msg in issues if sev == "HIGH"]
print(f"\nQA: {len(issues)} total issues, {len(high_issues)} HIGH")
for s, sev, msg in issues:
    print(f"  Slide {s} [{sev}]: {msg}")
```

## Visual QA

After the first save, render every slide to PNG and visually inspect each one:

```python
# Run after deck.save()
subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", output_path])
images = convert_from_path(output_path.replace(".pptx", ".pdf"), dpi=200)
for i, img in enumerate(images):
    path = f"slides_qa/slide_{i+1}.png"
    img.save(path, "PNG")
    # Then visually inspect each PNG with the runtime's image-review capability.
```

For each rendered slide image, verify:
   - all text is fully visible (no truncation at card/shape boundaries)
   - no text overlaps other text (titles vs descriptions, bullets vs callout bars)
   - cards and shapes contain their intended text without clipping
   - no content crosses title, footer, or split-zone boundaries
   - charts render with visible labels and hierarchy
   - no slide looks unfinished or under-designed
   - KPI tile grids align with column structures above/below them

If LibreOffice or pdf2image are unavailable, tell the user and provide install instructions (macOS: `brew install --cask libreoffice && brew install poppler`; Linux: `apt install libreoffice poppler-utils`). Do not silently skip this step.

Reading shape coordinates from Python (x/y/w/h inspection) is NOT visual QA. Text overflow, font rendering, and element stacking are only visible in rendered images.

## Review Order

Fix in this order:

1. meaning / argument integrity
2. layout and readability
3. visual polish

## User Checkpoint

Once HIGH issues are cleared and the deck has been visually reviewed, stop and present:

- QA issue summary
- confirmation that every slide was visually reviewed through rendered PNG images
- remaining non-blocking fixes, if any

Then wait for user confirmation before applying optional polish fixes.

In orchestrated mode, the parent reducer owns this checkpoint even if slide-level QA ran in parallel.

---

# QA Checklist

Run this in the QA phase after the deck is built.

## Structural Checks

- every title is an action title
- action titles: max 2 lines, ~90 characters at 24pt. Three-line titles collide with content.
- every body proves the title
- layout choice matches the semantic relationship
- no content overlaps the footer or source zone
- content starts below y=2.10" (standard) or y=1.70" (detail)
- title placeholder usage is intact unless a runtime override is intentional
- section dividers carry only the title
- disclaimer and end slides are present and last

## Formatting Checks

- Trebuchet MS or active template theme font is used consistently
- body text >=14pt with spc_after=6. Use 12pt only in narrow 4-5 column layouts.
- body text is left-aligned unless a centered treatment is intentional
- maximum 6 bullets per slide
- bullet spacing: `spc_after=6` default, `spc_after=10` for spacious layouts with <6 items
- no underlines or italics in standard consulting body copy
- no pure black body text
- source lines: y=6.74", 10pt, `#6E6F73`. Citation format: 'Source: [Organization], [Publication], [Year]'
- page numbers, source lines, and copyright treatment match the template

## Visual Checks

- review the deck through rendered slide PNGs on the first QA pass; do not rely on `check_deck()` alone
- charts and tables remain readable at presentation scale
- iconography is consistent within a slide
- card backgrounds present (fill contrasts with slide BG) + green accents — cards should be WHITE or LIGHT_BG with dark accent headers, NOT dark-fill card bodies
- there is visible visual hierarchy
- there are no dead cards or oversized containers with large unused space
- each slide has at least one meaningful visual structure
- on split layouts (`green_highlight`, `arrow_half`, `green_left_arrow`, `green_one_third`): content stays within its zone boundary — left-zone content must NOT bleed into the right panel
- on title-left layouts (`green_one_third`, `green_left_arrow`, `green_half`, `green_two_third`, and detail variants): the left panel is reserved for the slide title placeholder. Do not place manual textboxes, bullets, cards, or helper shapes there.
- on `green_half` / `green_two_third`: treat them as title + image only. Any extra body text is a failure.
- on `green_highlight`: left zone max width is 6.8" (tables, charts, cards must set w<=6.8")
- text-bearing shapes do not overlap other text-bearing shapes (run `check_deck()` and review TEXT OVERLAP flags)
- no shapes extend past slide boundaries (check OUT OF BOUNDS flags)

## Content Checks

- one message per slide
- every element passes the remove-it test
- sources appear where the evidence requires attribution
- chart callouts and highlights teach the message rather than just restate numbers

Escalate meaning-changing issues before cosmetic issues.

---

# Failure Modes

## Critical

- relying on `check_deck()` without performing native slide preview review
- topic title instead of action title
- body does not prove the title
- missing source line on data-driven slide
- layout does not match the conceptual relationship
- too much text to grasp the message in a few seconds

## Brand / Visual Identity

- pure black body text
- off-palette decorative colors on the BCG default theme
- red, orange, yellow: never use for text, fills, icons, or standard charts. Yellow is ONLY permitted to highlight text on a green background at 18pt+.
- bold action titles: BCG action titles are regular weight (NOT bold). Bold titles look like topic labels.
- non-Trebuchet font without a client-template reason
- bevels, reflections, 3D effects, or glow

## Layout / Structure

- no visual hierarchy
- text-only slide
- bullet wall instead of a structured layout
- centered body text
- crammed content with no breathing room
- hardcoded container fills instead of contrast-aware cards
- fill_color auto-select: omit the `fill_color` parameter and the engine picks the right fill (LIGHT_BG on white detail slides, WHITE on gray standard slides). Do not hardcode fills.
- card sizing: 3-4 bullets -> h=3.5-3.8"; 5-6 bullets -> h=4.0-4.5". Cards with >40% dead space are oversized.
- card shadow + accent: always pair cards with shadow=True and an accent bar (accent_position='top'). Without both, cards disappear into the background.
- left accent on light cards: use accent_position='top' for light-fill cards, or pair left accents with a contrasting fill.
- title that exceeds two lines and pushes content down
- using `green_left_arrow` as a section divider
- missing disclaimer or end slide

## Formatting

- missing page numbers
- underlined or italicized body text
- animations or transitions
- wrong table alignment: left-align text columns, center-align short numbers, right-align currency/longer numbers. Never candy-stripe rows.
- lime text on green backgrounds
- background cards behind tables
- thin rectangles used as fake divider lines
- invalid hex formats: no `#` prefix, no 8-char RGBA, no 3-char CSS shorthand, no named colors. Engine auto-corrects `#29BA74`->`29BA74` but rejects invalid input.

## Chart-Specific

- full green rainbow instead of a clear highlight strategy
- chart junk
- no callout or teaching layer
- line-chart data labels colliding at shared origins
- stacked bars whose segment colors are too similar to distinguish

## Pattern-Specific

- left accent on a light card where the boundary disappears
- statement slide used where supporting evidence is required
- image-led layout used without a meaningful image
- bubble chart labels enlarged past the point where they overlap instead of using leader lines

When in doubt, fix structural meaning first, then readability, then cosmetic polish.

---
name: deckster-slide-generator
version: "1.0"
description: "ALWAYS use this skill to create new PowerPoint slide decks from scratch. Triggers: 'create slides', 'create a deck', 'build a presentation', 'new deck', 'new presentation', 'BCG deck', 'consulting deck', 'board deck', 'strategy deck', 'client deck', 'exec summary'. Covers deck-level planning, storyline design, slide rendering, and QA for new decks. Supports BCG default templates, .ee4p client templates, dynamic style variants, and a capability-based workflow fork for sequential or orchestrated runtimes. Not intended for editing or reviewing existing PowerPoint files."
---

# Deckster Slide Generator

Reach out to the Deckster Slack Channel for questions/support.

Key BCG contributors: Jan Wulff, Justin Grosz, Marc Puig

## Scope

Use this skill when the task is creating a new deck from scratch:

- creating a new slide deck
- planning a slide storyline
- rendering a multi-slide consulting or client deck

Do not use this skill for:

- editing or modifying existing PowerPoint files
- reviewing or QA'ing slides you did not create
- one-off slide edits or isolated text changes
- speaker note tweaks
- generic presentation advice

## Non-Negotiables

- **Every time you present a .pptx file to the user, include this disclaimer:** *"This skill does not connect to or rely on additional data sources. Claude may generate errors while creating slides that align with your instructions and data input. Please review output carefully before use."*
- Every content slide title must be an action title (complete sentence stating the "so what", max 2 lines / <=90 characters). Verify character counts in Phase 1 before presenting the plan.
- The body must prove the title.
- Use the template title placeholder for every slide, including executive summaries. Pass the recommendation as the title to `add_content_slide()`.
- **Font hierarchy is fixed:** `TITLE_SIZE=24`, `SUBHEADER_SIZE=16`, `BODY_SIZE=14`, `LABEL_SIZE=12`. Do not use 13pt, 11pt, or 10pt. Minimum body text is 12pt; if content does not fit, split the slide.
- One message per slide.
- **Detail mode is the default.** Use `detail=True` for all content slides. Pass `detail=False` only for 2-3 key-message or statement slides per deck.
- **Use `text_on(fill_color)` for every text element on every colored shape.**
- **Use `dark_fills(n)` for accent elements only**, not for full card bodies.
- Use only `COLORS` dict values; no off-palette hex codes.
- Structural facts come from the active template manifest and `content_bounds()`, not from hardcoded geometry.
- The canonical build path is: `add_content_slide(...)` -> `content_bounds(...)` -> `render_pattern(...)` or explicit composition calls.
- Never call `_add_slide_from_layout()` directly unless a reference file explicitly documents that as the only valid runtime override.
- After every build, run `check_deck()`, render every slide to PNG, and visually inspect each image in the same QA pass. `check_deck()` is supporting signal only.

## Runtime Mode Selection

This skill branches on runtime capabilities, not product names.

Read `references/runtime/orchestration.md` only when `supports_subagents=true`.

Modes:

- **Sequential**: single-agent Plan -> Build -> QA flow with the existing hard checkpoints. Use this when sub-agents are unavailable.
- **Orchestrated**: parent orchestrator owns the same phase contract but may fan out slide-level planning, isolated build workers, and per-slide QA inspectors. Use this when `supports_subagents=true`.

The main delineation is:

- `supports_subagents=false` -> sequential workflow
- `supports_subagents=true` -> orchestrated workflow

Small capability flags may refine execution details:

- `supports_local_fs`
- `supports_workspace_persistence`
- `supports_rendered_image_review`
- `visual_qa_ready`

## Workflow

Build BCG decks in three phases.

| Phase | Output | Gate |
|-------|--------|------|
| **1. Plan** | Storyline, slide-by-slide plan | user approval |
| **2. Build** | Rendered `.pptx` or assembled slide artifacts | proceed directly to QA |
| **3. QA** | QA report + rendered slide images reviewed + remaining fixes | user review |

There are exactly **two user checkpoints** in the default workflow:

1. after Phase 1 planning
2. after Phase 3 QA review

Phase-gate ownership:

- **Sequential mode**: the same agent stops after Phase 1 and after Phase 3.
- **Orchestrated mode**: the parent orchestrator owns the same stops; sub-agents may work inside the phase, but they do not bypass the checkpoint.

**CRITICAL: You MUST stop after Phase 1 and wait for user approval before Build.** In orchestrated mode the parent planner may fan out slide-level enrichment after the storyline is locked, but it still must not begin Build before the user approves the plan.

## Environment Setup

Before any Python execution, bootstrap the environment:

```python
from env_detect import setup_python_path, check_visual_qa_deps
from runtime_capabilities import detect_runtime_capabilities

env = setup_python_path()
capabilities = detect_runtime_capabilities()
can_render = check_visual_qa_deps()

print(f"Runtime: {env['runtime']} | Workflow: {capabilities.workflow_mode}")
print(f"Skill root: {env['skill_root']} | Sub-agents: {capabilities.supports_subagents}")
```

If `env_detect` is not yet importable, bootstrap the path manually first:

```python
import sys
from pathlib import Path

_skill_root = Path("/mnt/skills/user/deckster-slide-generator")
if not _skill_root.exists():
    _skill_root = Path.cwd()
    if not (_skill_root / "scripts" / "bcg_template.py").exists():
        _skill_root = _skill_root.parent

sys.path.insert(0, str(_skill_root / "scripts"))
```

## Before You Start: Template Selection

This is the first step, before planning.

```python
from template_registry import list_templates, format_template_menu

registry = list_templates()
if len(registry["templates"]) > 1:
    print(format_template_menu(registry))
```

If multiple templates are detected, stop and ask the user which one to use. Do not combine this with the slide outline. If only BCG Default exists, proceed directly to Phase 1.

If a new `.ee4p` file is uploaded, the upload gate below takes priority over saved template selection.

## Load Order

Load by phase:

- **Phase 1 / Plan**
  - `references/runtime/plan.md`
- **Phase 2 / Build**
  - `references/runtime/build.md`
  - one relevant family index only: `references/charts/index.md`, `references/frameworks/index.md`, `references/process/index.md`, or `references/layouts/index.md`
- **Phase 3 / QA**
  - `references/runtime/qa.md`
- **Orchestrated mode only**
  - `references/runtime/orchestration.md`

The runtime docs are authoritative. Only load additional leaf files when the deck genuinely needs them.

### Phase 1: Plan

Before any code:

1. gather structured inputs
2. define the storyline
3. choose semantic layout families and evidence structures
4. lock deck-wide font constants
5. decide which reference files will be needed for Build
6. verify title length: every action title must be `<= 90` characters

```python
titles = {"Slide N": "Your action title here"}
for slide, title in titles.items():
    status = "OK" if len(title) <= 90 else f"FAIL ({len(title)} chars - shorten before build)"
    print(f"{slide}: {len(title):3d} chars [{status}]")
```

Use `references/runtime/plan.md` as the authoritative planning surface.

Planning split by mode:

- **Sequential**: one agent completes the whole planning pass.
- **Orchestrated**: the parent planner locks audience, recommendation, slide count, and section rhythm first; only then may slide-level enrichment fan out by family.

At the end of planning, stop and present the storyline to the user. Ask: "Does this storyline and slide structure work? Any slides to add, remove, or restructure?"

### Phase 2: Build

Use `references/runtime/build.md` as the authoritative build surface.

Build rules shared by both modes:

- scaffold structural slides first
- create content slides with `add_content_slide(...)`
- resolve layout bounds with `content_bounds(...)` after `add_content_slide()`
- render via `render_pattern(...)` when a documented pattern exists
- compose manually only when the relevant family docs say the pattern is custom

Mode-specific build execution:

- **Sequential**: build the full deck in one execution on one authoritative deck object.
- **Orchestrated**: workers render isolated slide artifacts or isolated mini-decks in separate workdirs; the parent reducer performs final assembly. Never let multiple workers mutate the same unpacked PPTX tree.

When Build is complete, proceed directly to QA. There is no intermediate user checkpoint after Build.

### Phase 3: QA

Use `references/runtime/qa.md` as the authoritative QA surface.

Immediately after the first saved or assembled `.pptx`:

1. run `check_deck(...)`
2. render every slide to PNG
3. visually inspect every rendered slide image

Rendered-image inspection is mandatory whenever the runtime supports it. Use whatever image-reading capability the runtime exposes; do not rely on shape coordinates alone.
Do not wait for zero HIGH issues before the first visual pass.

Mode-specific QA execution:

- **Sequential**: one agent runs programmatic QA, reviews all rendered images, batches fixes, reruns once, and repeats until clean.
- **Orchestrated**: the parent reducer runs deck-level QA, fans out per-slide rendered-image inspection, collects `QAFinding[]`, batches fixes, and rerenders only changed slide artifacts when possible.

If rendering tools are unavailable, tell the user and provide install instructions. Do not silently skip visual QA.

At the end of QA, stop and present:

- the QA issue summary
- confirmation that every slide was visually reviewed through rendered images or a clearly stated limitation
- remaining non-blocking fixes, if any

## Required Disclaimer

**You MUST include this disclaimer every time you present a `.pptx` file to the user - no exceptions, including re-deliveries after fixes:**

> *This skill does not connect to or rely on additional data sources. Claude may generate errors while creating slides that align with your instructions and data input. Please review output carefully before use.*

## New `.ee4p` Upload Gate

Before planning, check whether a new `.ee4p` file is present in the user's message or uploads. If detected, ingest it for the current run and proceed to planning.

```python
from pathlib import Path
from ingest_ee4p import ingest_ee4p

runtime_templates = Path.cwd() / "_runtime_templates"
template = ingest_ee4p("/path/to/client.ee4p", runtime_templates)
```

Template persistence is capability-driven:

- if `supports_workspace_persistence=false`, treat the template as run-scoped
- if `supports_workspace_persistence=true`, persist it only when the user asks to keep it available

## Runtime Entry Points

For capability-aware or server-side wrappers, prefer the orchestration helpers:

```python
from runtime_capabilities import detect_runtime_capabilities
from orchestrator import build_execution_plan
from template_registry import get_template

capabilities = detect_runtime_capabilities()
template = get_template(name="bcg_default")

plan = build_execution_plan(
    {
        "deck_title": "Action title deck",
        "slide_specs": [
            {"slide_number": 1, "title": "Action title as a sentence", "evidence_type": "chart", "layout_family": "content"}
        ],
    },
    capabilities=capabilities,
)
```

For direct build scripts, the canonical imports remain:

```python
from bcg_template import BCGDeck, content_bounds, COLORS, text_on, dark_fills, check_setup
from qa import check_deck
from template_registry import list_templates, get_template
from pattern_variants import render_pattern
from env_detect import check_visual_qa_deps
```

## Client Template Mode

BCG default and ingested `.ee4p` templates use the same runtime model. Switch templates, then follow the same Plan -> Build -> QA contract.

```python
from pathlib import Path
from ingest_ee4p import ingest_ee4p
from template_registry import save_template

runtime_templates = Path.cwd() / "_runtime_templates"
template = ingest_ee4p("/path/to/client.ee4p", runtime_templates)

save_template(
    name=template["name"],
    config=template,
    template_dir=template["_template_dir"],
    availability="workspace",
)
```

`ingest_ee4p(...)` returns a build-ready template config with `_template_dir` and `_master_pptx` populated for the current run.

## Dynamic Style Mode

Dynamic styles are part of the canonical build system, not a side path.

```python
from pattern_variants import list_variants, get_variant_info

deck.set_pattern_variant("flywheel", "concentric_rings")
deck.set_pattern_variants({"kpi": "big_number_dashboard"})
```

Variant resolution order and persistent override locations are defined in `references/core/dynamic-styles.md`.

## Troubleshooting

**`check_setup()` reports FAIL**: Verify `_master_pptx` and `_template_dir` in the theme config or registry entry.

**Deck won't open in PowerPoint**: Check QA for broken relationships, missing layout references, or corrupt XML structure.

**Content overlaps title or title overflows into content**: Use the content-start bounds from the active layout and shorten the title to the documented limit.

**Text invisible or hard to read**: Use `text_on(fill_color)` for every text element placed on a colored shape.

**Shapes or text overlapping other text**: Run `check_deck()` and inspect rendered slide images; batch fixes instead of fixing one issue at a time.

**Content not fitting in split-layout panels**: Keep content inside the `content_bounds(...)` safe band returned for that layout. On `green_half` and `green_two_third`, treat the slide as title + image only.

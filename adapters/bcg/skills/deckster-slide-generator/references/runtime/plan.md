# Plan

Authoritative planning runtime surface. Read this for planning, routing, storyline construction, action-title rules, and executive-summary scaffolding before building any deck.

# Loader Rules

Always read this document during planning.

Read conditionally:

- the storyline and executive-summary sections in this document when the deck narrative is still forming
- `references/runtime/build.md` only during Build
- `references/runtime/qa.md` only during QA
- core files when runtime constraints or style system questions arise
- `dynamic-styles.md` when variant choice, template-level pattern defaults, or persistent custom styles matter
- `references/runtime/orchestration.md` only when `supports_subagents=true`
- exactly one family index first, then only the needed leaf files
- chart files only for chart-led slides
- framework files only for framework/table slides
- process files only for sequence/timeline slides
- layout family files only when the slide uses a non-default split or statement family

Avoid loading multiple large families unless the deck genuinely spans them.

---

# Planning Contract

Use this file during Phase 1 only. It is the authoritative planning surface.

## Mode Fork

Planning always starts centrally.

- **Sequential mode**: one agent performs the entire planning pass.
- **Orchestrated mode**: the parent planner locks audience, recommendation, deck length, and section rhythm first. Only then may slide-level enrichment fan out by semantic family or slide range.

Do not fan out the core storyline decision itself.

## Required Inputs

Gather these before writing the storyline:

1. audience — who will read or present the deck
2. decision / objective — what the audience should decide, approve, or understand
3. recommendation — the answer first
4. scope and constraints — what must be covered and what is out of scope
5. deck length — target slide count or range

Optional but valuable:

- existing materials
- tone
- projected versus printed/shareable reading mode

## Planning Output

Lock these deck-wide fields in the plan:

- deck title
- subtitle / framing line if needed
- date
- font constants: `TITLE_SIZE=24`, `SUBHEADER_SIZE=16`, `BODY_SIZE=14`, `LABEL_SIZE=12` — these are non-negotiable; never use 13pt, 11pt, or 10pt
- reference files to load in Phase 2
- workflow gate owner: `single-agent` or `parent-orchestrator`

## Slide Composition

Plan each slide as a multi-element composition, not a single pattern filling the zone.

For **full-page layouts** (`content` / `d_title_only`), layer 2-3 visual elements:

- chart (top) + KPI metrics row (middle) + callout box with the "so what" (bottom)
- data table + insight annotation below
- column cards + bottom summary bar with a key takeaway
- process flow + milestone callout at the bottom

For **split layouts** (`arrow_half`, `green_half`, `green_left_arrow`, `green_one_third`, `green_highlight`, `green_two_third`), do NOT add takeaway boxes or summary banners. Each zone should contain its own content without crossing into the other zone.

Cards should contain substantive content — 3-4 bullets per card with real detail, not just a title and one-word bullets. If a full-page slide has only one pattern (e.g., 3 column cards) with nothing else, it will look thin. Add a supporting element.

Per slide, record:

```text
title:
story_role:
relationship:
evidence_type:
needs_image:
needs_data:
emphasis:
source_type:
layout_family:
primary_reference:
```

Add these only when the slide requires them:

- chart slides:
  - `chart_type`
  - `insight_carrier`
  - `context_layer`
  - `label_strategy`
  - `supporting_module`
  - `axis_rule`
  - `implementation_path`
- icon-heavy slides:
  - `icon_line_count`
  - `icon_type`

## Chart Pre-Decisions

Do this in Phase 1 for every chart slide. Start from the argument in the action title, not the raw data shape.

### Chart Type Selection (mandatory — do not default to bar)

| If the title asserts... | Use this chart | `add_chart()` type |
|---|---|---|
| a trend or rate of change over time | line chart | `"line"` |
| a ranking or magnitude comparison across categories | horizontal bar | `"bar_horizontal"` |
| a category comparison (not ranked) | clustered bar | `"bar"` |
| a share, composition, or part-to-whole | donut | `"doughnut"` |
| a composition breakdown over time | stacked bar or stacked area | `"stacked_bar"` or `"stacked_area"` |
| a bridge from start to end (value levers) | waterfall (simulated) | `"bar"` with point_colors |
| volume on one axis and rate on another | combo (bar + line) | merge path |

Use `add_chart(slide, chart_type, categories, series, ...)` directly — not `render_pattern("chart", ...)` which defaults to bar.

### Other chart decisions

- name the element that proves the title (the one bar/line/segment that carries the argument)
- decide whether the chart needs a baseline, target, benchmark, or prior period
- decide whether labels should be direct, tabular, or legend-driven
- add a callout box annotating the key insight — every chart slide needs one

## Icon Decision

Do this once per slide, never per icon.

Count projected text lines:

- title = 1
- each bullet = 1
- each table row = 1
- each body paragraph = 1
- each chart annotation label = 1

Rule:

- fewer than 15 lines -> `icon_type='icon'`
- 15 or more lines -> `icon_type='bug'`
- when in doubt -> `icon`

All icons on a slide must use the same `icon_type`.

## Routing

Use the Routing Contract section below as the decision tree. Planning chooses semantic layout families and evidence direction; exact geometry and renderer details belong to Build.

## Verification Before Approval

Check every planned slide against these tests:

1. relationship named — parallel, sequential, hierarchy, comparison, part-to-whole, cause/effect, synthesis
2. layout encodes the relationship — not just the item count
3. swap test — if different content with a different relationship would fit the same layout, the layout is too generic
4. body proves title — planned evidence makes the action title defensible
5. divider titles preview the section argument
6. **no-repeat check** — scan the full plan: does any layout + pattern combination appear on more than one slide? If so, change one of the duplicates to a different visual that still serves the same argument
7. **single-topic test** — each content slide should convey exactly one topic. If a planned slide covers two or more distinct topics, split it into separate slides before proceeding to build. Common violations include: combining team structure with implementation roadmap on one slide, combining analysis findings with decision asks, combining current-state assessment with future-state vision and recommendations, and combining operating model with phased roadmap and approval requests. When in doubt, ask: "could someone summarize this slide's message in one sentence without using the word 'and' to join two unrelated ideas?" If not, split it.
8. **worker-scope test** — in orchestrated mode, can each delegated planning task be completed from a bounded artifact (`SlideSpec`, section outline, or family-specific prompt) without the full evolving deck context? If not, keep it with the parent planner.

## Stop Rule

Stop after planning. Present the storyline and slide structure to the user and wait for approval before Build.

- **Sequential mode**: the same agent stops here.
- **Orchestrated mode**: the parent orchestrator stops here, even if slide-level enrichment workers are ready.

---

# Routing Contract

Use this file in Phase 1 when choosing the semantic layout family. This is the authoritative routing and tiebreaker surface.

## Level 1: Structural Or Content

Structural slides use dedicated layouts:

- `title_slide`
- `section_divider`
- `disclaimer`
- `end`

Everything else is a content slide.

## Level 2: Split Trigger Tests

For every content slide, ask:

1. Is this slide a pivot point introducing a framework, decision ask, or section thesis?
2. Does the slide need a real supporting image?
3. Does one side frame a category, question, or takeaway while the other side proves it?

If all answers are no, default to the full-page `content` family.

If any answer is yes, route into a split or statement family.

## Level 3: Family Choice

| Situation | Family | Use when |
|---|---|---|
| default evidence slide | `content` | most chart, table, and structured evidence slides |
| framework framing / category + members | `green_one_third` | left panel names the category, right panel enumerates members |
| decision ask / framing thesis / short context question | `green_left_arrow` | left side is a short thesis or prompt, right side does the analytical work |
| evidence + distinct interpretation panel | `green_highlight` or `four_column_green` | analysis left, insight or attributed quote right. Use `four_column_green` when the title needs more width. The accent panel can hold a single bold statement, an attributed quote ("— CEO, Acme Corp"), or 2-3 structured insight items. |
| current/target or before/after contrast | `arrow_half` | structural split is the argument |
| statement + evidentiary image | `green_half` | title-led message + image; the image is the primary supporting evidence |
| longer title-led message + supporting image | `green_two_third` | the title needs more width, but the slide is still title + image only |
| punctuating single message | `big_statement_green` or `big_statement_icon` | 1-2 times per deck max |

## Tiebreakers

- `green_one_third` vs `green_left_arrow`
  - use `green_one_third` when the left panel is a category or framework label
  - use `green_left_arrow` when the left panel is a question, thesis, or directional recommendation
- `green_highlight` vs `content` + bottom callout
  - use `content` + bottom callout for a short single takeaway
  - use `green_highlight` when the interpretation deserves equal visual weight
- `arrow_half` vs two columns on `content`
  - use `content` when the two sides are equal peers
  - use `arrow_half` when the sides encode contrast, transition, or directional change
- `arrow_half` vs `green_arrow_half`
  - default to `arrow_half`
  - use `green_arrow_half` only when the template-specific accent-on-left treatment materially improves the contrast read
- `green_half` vs `green_two_third`
  - use `green_half` when the title can stay short and the image should carry more weight
  - use `green_two_third` when the title needs more width but the slide should remain title + image only
- `green_left_arrow` vs `left_arrow`
  - default to `green_left_arrow`
  - use `left_arrow` only when the active template exposes it and the white-arrow-on-green treatment is specifically needed
- `big_statement_icon` vs `big_statement_green`
  - use the icon version when a specific icon strengthens the message
  - use the green version for pure authority / vision tone

## Title-Only Guardrails

These layouts are title-led and should not carry normal supporting content unless the family docs explicitly document it:

- `big_statement_green`
- `big_statement_icon`
- `section_divider`
- `green_half`
- `green_two_third`

On title-left split families (`green_one_third`, `green_left_arrow`, `green_half`, `green_two_third`, and template-specific left-arrow relatives), the left panel is reserved for the slide title placeholder. Do not add manual text or shapes there.

## Education Test

Every element must teach:

- icons must represent the mechanism, not a generic category
- descriptions must explain why or how, not restate the header
- charts must let the reader trace title -> evidence -> conclusion

If removing an element does not reduce understanding, it is decoration.

## Visual Rhythm

### No-Repeat Rule

After planning all slides, review the deck plan and check: **no two content slides should share the same layout + content pattern combination.** Every slide should look different from every other slide in the deck.

If you find repeats, rethink the duplicate. The same "so what" can almost always be told through a different visual:

| If you already used... | Consider instead... |
|---|---|
| column_cards (3 pillars) | compact_row_list, data_table, or put the items inside a split layout |
| chevron process flow | funnel (if narrowing), timeline (if dated), stage_gate (if gated), gantt (if parallel) |
| bar chart | line chart (if trend), horizontal bar (if ranking), donut (if share), stacked (if composition) |
| compact_row_list | accent_rows, vertical_stack, or column_cards with more detail per card |
| full-page content | green_highlight (evidence + insight), green_left_arrow (framing), arrow_half (contrast) |

### Layout Rhythm

- after three consecutive full-page `content` slides, the fourth must use a split layout
- use split layouts as rhythm breakers: `green_left_arrow` for decision asks, `green_one_third` for framework framing, `green_highlight` for evidence + insight, `arrow_half` for before/after contrast
- the slide after a section divider is prime for `green_one_third` (framework framing) or `green_left_arrow` (section thesis)
- reserve statement slides (`big_statement_icon` or `big_statement_green`) for the emotional peak or closing recommendation — limit to 1-2 per deck
- bookend the deck: open with a split or hero layout, close with a statement or decision ask

## Planning Boundary

Routing chooses the semantic family. Do not decide exact geometry, icon placement, or low-level renderer workarounds here.

---

# Slide Routing

Use this after the Routing Contract section above. This section is the compact family map; the routing contract owns the trigger tests and tiebreakers.

## First Decision

If the slide is structural, use a structural layout:

- `title_slide`
- `section_divider`
- `disclaimer`
- `end`

If the slide is content, classify it by:

- `story_role`
- `relationship`
- `evidence_type`
- `needs_image`
- `emphasis`

## Layout Family Routing

| Slide shape | Primary family | Read next |
|---|---|---|
| Default evidence slide | `content` | `../layouts/index.md` |
| Decision ask or framing thesis | `green_left_arrow` | `../layouts/framing.md` |
| Framework framing / category + members | `green_one_third` | `../layouts/framing.md` |
| Insight panel beside evidence | `green_highlight` | `../layouts/insight-and-contrast.md` |
| Before/after or contrast | `arrow_half` | `../layouts/insight-and-contrast.md` |
| Image-led statement or vision slide | `green_half` | `../layouts/image-led.md` |
| Longer title-led message with supporting image | `green_two_third` | `../layouts/image-led.md` |
| Pure statement / impact slide | `statement` | `../layouts/statement.md` |

## Reference Family Routing

- `evidence_type=data` -> `../charts/index.md`
- `relationship in {hierarchy, matrix, assessment, table, framework}` -> `../frameworks/index.md`
- `relationship in {sequence, roadmap, lifecycle, gated_process}` -> `../process/index.md`
- complex deck narrative or weak brief -> use the Deck Storyline guidance later in this document
- QA phase -> `references/runtime/qa.md`

## Primary Use Cases

**Layout and content are two independent choices.** First choose the layout from the trigger tests above. Then choose the content pattern from the table below. Any pattern works in any content-bearing layout — a chart works inside `green_highlight` just as well as inside `content`.

### Content Patterns by Narrative Role

A consulting deck tells a story: open with the recommendation, build the evidence, then close with the ask. Choose the content pattern that best serves each slide's role in that arc.

**Opening (recommendation first)**

| Slide Role | Pattern | Recipe | Why |
|---|---|---|---|
| Executive summary | SCQA narrative cards | Recipe 5 | Recommendation-first structure; hero header anchors the message |
| Vision / bold claim | title only | `big_statement_green` or `big_statement_icon` | Punctuating statement, no evidence — limit 1-2 per deck |
| Narrative + image | title + fill_picture | `green_half` / `green_two_third` | Image IS the evidence alongside the title |

**Evidence (proving the recommendation)**

| Slide Role | Pattern | Recipe | Why |
|---|---|---|---|
| Data trend / KPIs | bar chart + KPI row + callout | Recipe 1 | Chart shows the trend; KPI tiles ground the numbers; callout states the insight |
| Benchmark vs peers | horizontal bar chart + gap callout | Recipe 7 | Horizontal bars compare magnitudes at a glance |
| Competitive landscape | data table + insight card | Recipe 3 | Table encodes structured comparison; insight card highlights the key gap |
| Data + key finding | chart or table left, insight panel right | `green_highlight` or `four_column_green` | Analysis left (~60%), accent panel right with the "so what" — use when the insight deserves equal visual weight to the data |
| Evidence + stakeholder quote | content left, attributed quote right | `green_highlight` | Customer quote, executive sponsor endorsement, or field interview excerpt on the accent panel reinforces the data with a human voice |
| Benchmark + gap callout | horizontal bar left, insight right | `green_highlight` | Chart shows the comparison; accent panel calls out the gap |
| Capability assessment | harvey ball matrix | render_pattern harvey_ball | Maturity levels encoded intuitively without cluttering with numbers |
| Customer journey | funnel | Recipe 9 | Narrowing width encodes drop-off — the visual IS the argument |
| Before/after contrast | before_after split cards | render_pattern before_after | Split layout encodes contrast structurally — use `arrow_half` |
| Prioritization matrix | scatter bubble or swot 2x2 | render_pattern | 2x2 encodes two dimensions; bubble size encodes a third |
| Evidence table | data table + insight card | Recipe 3 or `green_highlight` | Table with either a bottom callout (full-page) or accent insight panel (split) |

**Structure (how we'll do it)**

| Slide Role | Pattern | Recipe | Why |
|---|---|---|---|
| Roadmap / timeline | timeline, stage gate | Recipe 6 | Sequencing and dependencies with milestone callout |
| Project schedule | gantt | render_pattern gantt | Duration and overlap across parallel tracks |
| Operating model | multi column process | render_pattern multi_column_process | Parallel workstreams with details under each |
| Architecture / layers | compact row list, vertical stack | Recipe 4 | Hierarchy — top layer depends on layers below |
| Org / governance | org chart | render_pattern org_chart | Cascade boxes encode reporting lines and accountability |
| Strategy cascade | pyramid | render_pattern pyramid | Layers encode vision → strategy → tactics hierarchy |
| Platform flywheel | flywheel | Recipe 10 | Circular nodes encode cyclical reinforcement |

**Recommendation (the ask)**

| Slide Role | Pattern | Recipe | Why |
|---|---|---|---|
| Decision ask | compact row list or column cards | `green_left_arrow` | Arrow conveys direction; content in right zone |
| Framework / approach | any content pattern | `green_one_third` | Left panel names the category; right panel proves it |
| Recommendation + evidence | chart or table left, recommendation right | `green_highlight` or `four_column_green` | Data proves the case on the left; accent panel states the recommendation |
| Business case | waterfall + KPI tiles | Recipe 8 | Bridge from current to target; KPI tiles ground ROI |
| Strategic options | two-column cards + callout | Recipe 2 | Columns encode comparison; callout states the recommendation |
| Risk register | compact row list + takeaway | Recipe 4 | Ranked items with severity labels |
| Equal-weight capabilities | column cards | render_pattern column_cards | 3-4 peer items with icons + headers + substantive bullets |
| Custom composition | manual | `blank` | Fully custom layouts |

Additional variant treatments: `accent_rows` (alternative row style with left color bars), `grid_layout` (2x3 card grid). Use `list_variants(pattern)` to discover all variants.

Recipes are starting points — adapt them for each slide. Swap chart types (bar → line → donut), replace KPI tiles with a callout or icon row, use compact rows instead of column cards, put a chart inside a split layout instead of full-page. The 25 pattern families, 40 variants, and 15 layouts give you hundreds of combinations. No two decks should use the same sequence of recipes.

When in doubt and you have data, lead with a chart — chart_led is the #1 visual grammar in real BCG decks (503 of 1,200 slides analyzed).

## Generic Content Routing

When a slide does not match a named use case, route by visual grammar. The frequencies below reflect real BCG decks — use them to calibrate your defaults:

| Visual Grammar | Freq | Pattern | When to use |
|---|---|---|---|
| chart_led | highest (503) | chart + callout | Any data-driven insight: trends, comparisons, distributions. This is the #1 visual grammar — when in doubt and you have data, lead with a chart. |
| parallel_columns | high (379) | column cards, icon row | 2-4 equal-weight concepts, capabilities, workstreams. Use only when items are truly equal peers — not for hierarchies or sequences. |
| process_flow | high (330) | chevron flow, timeline, stage gate | Sequential steps, phases, workflows. If the content has order, use a process pattern, not columns. |
| managed_chart_plus_table | medium (143) | table + chart combined | Data proof point with supporting detail table. |
| contrast_panel | medium | arrow_half, green_highlight | Before/after, current/target, or insight-versus-evidence split. |
| hybrid_infographic | low (47) | mixed composition | Complex visual explanations using icons + shapes + text. |
| evidence_table | rare (5) | data table | Pure tabular evidence without a chart. |

## Keep Planning Light

Do not plan exact geometry, icon placement, or low-level workarounds in this stage. Do lock chart intent and slide-level icon type when the slide clearly needs them.

Pattern rules:

1. start from the use case, not the item count — "I have 4 items" is not enough; ask "what relationship do these items have?"
2. if there is real data and the title is an empirical claim, default toward chart-led evidence — chart_led is the #1 visual grammar (503 slides)
3. decision asks should never use equal-weight columns — the recommendation needs visual weight via arrow or contrast panel
4. hierarchies should not be rendered as peer grids — use vertical stack or cascade
5. architecture stacks are not grids — layers have hierarchy
6. if a slide does not match any category, check the Layout Family Routing table above and the split trigger tests — do not default to column_cards without considering alternatives
7. a deck without charts, process flows, or split layouts will look flat and text-heavy — every deck >4 slides should use at least 2 different pattern families

---

# Deck Storyline

## WWWH

Before outlining the deck, answer:

- `Who` is the audience, and what decision do they need to make?
- `Why` are you telling this story now?
- `What` is the key message?
- `How` will the audience best absorb it?

Every deck objective falls into one of three types: **compel action**, **provoke reaction**, or **create a common view**. Pick one before outlining.

Write the story the audience needs to hear, not the one you want to tell.

## Pyramid Principle

Structure top-down:

1. start with the answer
2. group 2-4 supporting arguments (must be MECE)
3. provide evidence under each argument

At the deck level:

- executive summary = answer
- sections = supporting arguments
- slides = evidence

At the slide level:

- title = answer
- body = evidence

## MECE

Group arguments so they are:

- mutually exclusive
- collectively exhaustive

Apply this to:

- deck sections
- argument trees
- chart categories
- workstreams
- framework groupings

## One Message Per Slide

Each slide should communicate exactly one message. If a single action title cannot capture the slide, split it.

## Key Message Versus Detail Slides

Choose a key-message slide when the audience mainly needs the takeaway in the room. Choose a detail slide when the audience needs denser proof, printed review, or appendix backup.

## Source Everything

Every real data point needs a source line. Unsourced numbers damage credibility immediately.

## Sanity Check

Before build or before sending:

- can someone follow the story from the titles alone?
- does each slide have one clear message?
- do the numbers add up across slides?
- are sources and footnotes consistent?
- is the formatting coherent across the deck?

## Typical Deck Size

Typical consulting deck range:

- situation / context: 3-8 slides
- analysis / findings: 5-12 slides
- recommendations: 3-8 slides
- next steps / roadmap: 1-2 slides

---

# Action Titles

Every content slide title must be a complete sentence stating the takeaway.

## Bad Versus Good

Bad topic titles:

- `Market Overview`
- `Q3 Financial Results`
- `Customer Segmentation`

Good action titles:

- `The European market grew 12% YoY, driven primarily by the SMB segment`
- `Q3 revenue exceeded forecast by 12%, driven by enterprise segment growth`
- `Three customer segments represent 80% of margin; mid-market is underserved`

## Rules

- use a complete sentence
- state the so-what, not the topic
- action titles are NOT bold — regular weight. Bold titles look like topic labels.
- maximum 2 lines, ~90 characters at 24pt. Three-line titles collide with content at y=2.10.
- on narrow-panel layouts (green_left_arrow, green_one_third), keep titles to 3-4 words / 25 characters.
- the deck should read as a coherent story if someone scans only the slide titles
- if the body cannot prove the title, weaken the claim or strengthen the evidence

## Section Divider Titles

Section divider titles should preview the argument of the next section, not just label it. `Our analysis reveals three growth vectors` teaches more than `Analysis`.

## Optional Prefix Convention

Use only when it clarifies the role of the slide:

- `What? |` define the recommendation
- `Why? |` give the rationale or evidence
- `How? |` describe implementation
- `Who? |` identify owners and accountabilities

Do not let the prefix replace the real message.

---

# Executive Summary And SCQA

Use SCQA as invisible scaffolding for the opening narrative:

1. **Situation** — shared context the audience already knows
2. **Complication** — what has changed or gone wrong; the tension
3. **Question** — the strategic question this raises
4. **Answer** — your recommendation

The action title of the executive summary slide should state the answer.

## Rendering Rule

Never show SCQA labels as visible text on the slide. Do not show framework labels like `Situation`, `Complication`, `Question`, or `Answer` on the slide. SCQA is a writing scaffold, not a visible content taxonomy.

Wrong:

- `Situation: the market grew 8%...`

Right:

- `European logistics grew 8% annually, but new entrants are eroding the value pool`

## Visual Choice

If the logic is sequential or causal, render it visually rather than as plain bullets.

Use:

- chevrons for linear sequence
- numbered narrative cards for progressive buildup
- arrow connectors for causal chains
- plain bullets only when the text is too dense for compact containers

## Executive Summary Pattern

Lead with the recommendation, then explain the context and tension that make the recommendation necessary. The deck sections that follow should provide the proof.

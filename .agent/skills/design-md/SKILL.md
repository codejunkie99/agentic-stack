---
name: design-md
version: 2026-04-23
triggers: ["DESIGN.md", "design.md", "Google Stitch", "Stitch", "design tokens", "design system", "visual design", "UI", "frontend", "components", "styling"]
tools: [bash, memory_reflect]
preconditions: []
constraints: ["prefer DESIGN.md tokens over invented values", "preserve unknown sections", "validate when tooling is available"]
---

# DESIGN.md — portable visual system contract

Use this skill when a task touches UI implementation, component styling,
frontend polish, or Google Stitch's `DESIGN.md` format.

## Source of truth
- Look for `DESIGN.md` at the project root before changing visual UI.
- Treat YAML front matter tokens as normative values: colors, typography,
  spacing, radius, and component tokens are exact inputs to code.
- Treat the Markdown body as design rationale: it explains mood, hierarchy,
  interaction intent, and where tokens should or should not be used.
- If no `DESIGN.md` exists, say that explicitly before inventing a new visual
  system. For new UI, offer to create one or ask for a brand/reference.

## Implementation rules
1. Map tokens into the local styling system already in use: CSS variables,
   Tailwind theme values, design-token JSON, component props, or native styles.
2. Use token references and component patterns from `DESIGN.md` instead of
   hard-coded one-off values.
3. Preserve unknown headings and extra prose when editing `DESIGN.md`; unknown
   content may be meaningful to other agents or Stitch.
4. Express component variants as related entries when updating the file
   (`button-primary`, `button-primary-hover`, etc.).
5. Keep accessibility constraints intact. Do not weaken contrast, focus,
   reduced-motion, or touch-target guidance unless the user explicitly asks.

## Validation
- If Node/npm tooling is available, validate with:

```bash
npx @google/design.md lint DESIGN.md
```

- For design system changes, compare before/after when practical:

```bash
npx @google/design.md diff DESIGN.before.md DESIGN.md
```

- If the CLI is unavailable or network/dependency policy blocks it, still
  check manually for broken `{path.to.token}` references, missing primary
  color/typography tokens, duplicate section headings, and section order.

## Expected sections
The Google draft spec uses YAML front matter plus Markdown sections. Common
sections are:

- `## Overview`
- `## Colors`
- `## Typography`
- `## Layout`
- `## Elevation & Depth`
- `## Shapes`
- `## Components`
- `## Do's and Don'ts`

## Self-rewrite hook
If UI work repeatedly drifts away from `DESIGN.md`, add a stronger local
checklist here and promote the durable lesson through the memory tools.

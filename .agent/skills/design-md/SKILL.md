---
name: design-md
version: 2026-04-26
triggers: ["DESIGN.md", "design.md", "Google Stitch", "Stitch", "design tokens", "design system", "visual design"]
tools: [bash, memory_reflect]
preconditions: ["DESIGN.md exists at project root"]
constraints: ["prefer DESIGN.md tokens over invented values", "do not modify DESIGN.md unless the user explicitly asks", "preserve unknown sections when an edit IS authorised", "validate when tooling is available"]
---

# DESIGN.md — portable visual system contract

Use this skill when a task touches Google Stitch's `DESIGN.md` format or
the project explicitly references its design system / design tokens. The
skill loads only when `DESIGN.md` exists at the project root (see
`preconditions` above), so general UI / frontend / component work that
isn't tied to a `DESIGN.md` won't trip it.

## Source of truth
- `DESIGN.md` is a contract file. Read it before changing visual UI.
- Treat YAML front matter tokens as normative values: colors, typography,
  spacing, radius, and component tokens are exact inputs to code.
- Treat the Markdown body as design rationale: it explains mood, hierarchy,
  interaction intent, and where tokens should or should not be used.
- If no `DESIGN.md` exists this skill is inactive; for new UI, offer to
  create one or ask for a brand/reference, but don't generate one
  unprompted.

## Default: read-only
**Do not modify `DESIGN.md` unless the user explicitly asks for a design
system change.** Implementation work consumes the contract; it does not
edit it. Token additions, renames, or section restructures land in their
own commit with a clear message and (ideally) a Stitch round-trip.

## Implementation rules
1. Map tokens into the local styling system already in use: CSS variables,
   Tailwind theme values, design-token JSON, component props, or native
   styles.
2. Use token references and component patterns from `DESIGN.md` instead of
   hard-coded one-off values.
3. Keep accessibility constraints intact. Do not weaken contrast, focus,
   reduced-motion, or touch-target guidance unless the user explicitly
   asks.

## When an edit IS authorised
1. Preserve unknown headings and extra prose; other agents or Stitch may
   own them.
2. Express component variants as related entries
   (`button-primary`, `button-primary-hover`, etc.).
3. Land token / structure changes in their own commit, separate from the
   feature consuming them.

## Validation
- If Node/npm tooling is available, lint with:

  ```bash
  npx @google/design.md lint DESIGN.md
  ```

- For design system changes, diff before/after:

  ```bash
  npx @google/design.md diff DESIGN.before.md DESIGN.md
  ```

- If the CLI is unavailable or network/dependency policy blocks it, the
  manual fallback is best-effort only — check for broken `{path.to.token}`
  references, missing primary color / typography tokens, duplicate section
  headings, and section order. The CLI ALSO checks contrast ratios and
  orphaned tokens; the manual fallback does not, so re-run the CLI when
  you regain network access.

## Expected sections
The Google draft spec uses YAML front matter plus Markdown sections.
Common sections:

- `## Overview`
- `## Colors`
- `## Typography`
- `## Layout`
- `## Elevation & Depth`
- `## Shapes`
- `## Components`
- `## Do's and Don'ts`

## Self-rewrite hook
After every 5 uses OR on any failure:
1. Read the last N skill-specific episodic entries.
2. If a new failure mode has appeared (e.g. tokens drifting away from
   DESIGN.md, accessibility rules being weakened, unauthorised edits to
   the contract file), append it to this skill's `KNOWLEDGE.md`.
3. If a constraint was violated, escalate to `semantic/LESSONS.md`.
4. Commit: `skill-update: design-md, <one-line reason>`.

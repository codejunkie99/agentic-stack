# Unified profile layering

## Purpose

Define how the portable brain combines one personal system with named project and repository
context. Every knowledge and capability category exists at every layer. No category belongs only
to the global layer or only to a project.

## Scope

This protocol governs preferences, protocols, memory, architecture, conventions, skills, tools,
harness configuration, workflows, templates, working state, decisions, and lessons. It does not
store secret values. It stores only secret references and ownership.

## Identity model

Every repository must declare a stable identity. A directory name is not a stable identity.

```json
{
  "profile": "okai",
  "projectId": "calbank-ddi",
  "componentId": "api",
  "displayName": "CalBank Direct Debit API",
  "remote": "AppDev123/DirectDebit/api",
  "mode": "brain-primary"
}
```

Rules:

1. `profile` identifies the user profile.
2. `projectId` identifies the product or bounded system.
3. `componentId` identifies one repository or component in the project.
4. `remote` disambiguates repositories with common names such as `api` or `frontend`.
5. `mode` selects one memory, skill, and hook authority. Mixed mode is invalid.

## Layers

The effective context has four ordered layers:

1. Global profile.
2. Named project profile.
3. Repository-local overlay.
4. Branch, worktree, and session state.

All layers can contain all categories. The resolver must attach layer and source provenance to each
resolved value.

```text
profiles/okai/global/<category>
profiles/okai/projects/calbank-ddi/<category>
repository/.agent/local/<category>
repository/.agent/memory/working/<branch-or-session>
```

## Category resolution

| Category | Resolution rule |
|---|---|
| Preferences | A more specific layer can refine or override a default. Record the winning source. |
| Communication | Apply the global language standard, then add project ubiquitous language. |
| Permissions | Compose restrictions. The stricter rule wins. A local layer cannot silently weaken a global hard rule. |
| Protocols | Apply the global lifecycle, then project and component extensions. Required global stages remain required. |
| Architecture | Use global principles as defaults. The named project architecture is authoritative for that project. |
| Coding conventions | Use global defaults, then project and component conventions. Confirm conventions against code. |
| Skills | Merge by qualified identifier. A local skill shadows a global skill only through an explicit override record. |
| Tools | Merge by qualified identifier and version. Do not use path order as implicit precedence. |
| Workflows | Extend by stable step identifier. An overlay can add or refine steps but cannot remove hard gates. |
| Templates | Resolve the most specific compatible template version. Preserve its base-template provenance. |
| Decisions | Project decisions override global defaults only inside that project. Never rewrite decision history. |
| Lessons | Merge, deduplicate, and rank project evidence above global evidence for a project task. Preserve contradictions. |
| Working state | Keep detail in the project namespace. Publish a global project-index summary for cross-project continuity. |
| Episodic memory | Keep the raw event in its project namespace. A redacted global index can reference it. |
| Harness and hooks | Compose configuration under one declared owner. Duplicate hooks for the same event are invalid. |

## Conflict handling

The resolver must not use silent last-write-wins behavior.

1. If two values are compatible, merge them and retain both sources.
2. If a project value specializes a global default, use the project value in that project.
3. If two hard rules conflict, stop and require an owner decision.
4. If lessons conflict, keep both as a conflict set. Do not promote either until evidence resolves it.
5. If two tools or skills share an unqualified name, require a qualified identifier or an override.
6. If an overlay removes a required permission, evidence, rollback, or validation gate, reject it.

## Context compilation

Unified storage does not mean that every artifact enters every prompt. The context compiler must
load only what the task needs:

1. Global hard rules and stable preferences.
2. Project identity and ubiquitous language.
3. Matching protocols and skills.
4. Relevant architecture and conventions.
5. Current working state and blockers.
6. Top relevant global and project lessons.
7. Required workflow and tool contracts.

The compiler must report sources, omitted categories, token budget, and truncation. A missing hard
rule, project identity, or required protocol is a startup failure. It is not a warning.

## Memory writes

Every write must name its scope and provenance.

| Signal | Default scope |
|---|---|
| Raw action or result | Project episodic memory |
| Current task state | Project working memory |
| Project architecture fact | Named project semantic memory |
| Repository convention | Project or component memory |
| Cross-project pattern | Global candidate, not an accepted rule |
| User-confirmed universal preference | Global accepted preference or lesson |
| User-confirmed project rule | Named project accepted lesson |

Use explicit `global`, `project`, or `local` scope. If the writer cannot resolve identity, it must
stop. It must not place the entry into an unqualified default store.

## Fleet integrity

The fleet doctor must verify:

- each repository has one stable identity;
- each repository resolves one profile and project;
- all adapter files point to the same resolver;
- one system owns memory, skills, and hooks;
- global and project manifests are readable;
- required protocols and templates exist;
- no hard rule is silently overridden;
- no secret value is stored in a profile;
- generated effective context is reproducible from source layers;
- upgrades do not remove registered local extensions.

## Distribution status

The versioned `agentic-stack` skeleton owns this global protocol. Named-profile, project, component,
and session data remain separate overlays. An upgrade can replace a managed global artifact, but it
must preserve repository-local overlays and user memory. Do not copy one project's working memory
into another project.

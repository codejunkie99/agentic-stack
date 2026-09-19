# Portable Brain System

## Purpose

Use this protocol as the entry point for the portable brain. It tells every
agent where rules belong, how the layers combine, and which check proves that
the system is complete.

The portable brain is agent-agnostic. A harness adapter can load it, but a
harness-private memory store is not a source of truth.

## Canonical location

The current project copy is `.agent/`. All repository adapters must point to
`.agent/AGENTS.md`.

The long-term global source is the versioned `.agent/` skeleton in the
`agentic-stack` source repository. The artifact registry marks files that the
installer owns as `managed`. A clean install and `agentic-stack upgrade` must
install those files and preserve repository-local files outside the managed
set.

Do not copy a durable rule into a harness-private store. Put the rule in the
portable brain and let each adapter load it.

## MECE system map

Each concern has one primary owner. Related documents can refer to the owner,
but they must not define a second rule for the same concern.

| Concern | Primary owner | Required result |
|---|---|---|
| Profile identity, precedence, merge, and context budget | `profile-layering.md` | One deterministic effective profile |
| Fleet ownership, rollout, verification, and rollback | `fleet-management.md` | One owner and one verified state per workspace |
| Repetition detection, artifact classification, and promotion | `tooling-extraction.md` | One governed artifact lifecycle |
| Workflow structure, overlays, execution gates, and retirement | `workflow-templates.md` | One typed workflow contract |
| Machine-readable workflow fields | `tool_schemas/workflow-template.schema.json` | One schema version |
| Artifact ownership, scope, version, and source state | `config/extracted-artifacts.json` | One registry record per artifact |
| Structural integrity | `tools/validate_extracted_artifacts.py` | One pass or an explicit failure list |
| Durable learning | `memory/` and memory tools | One agent-agnostic lesson source |
| Project delivery | Project-local delivery protocol | One evidence-based delivery lifecycle |

This partition is mutually exclusive by primary responsibility and
collectively exhaustive for profile composition, repetitive-task extraction,
workflow authoring, validation, memory, and delivery integration.

## Required flow

1. Resolve the global, named-project, repository-local, and session layers.
2. Search the artifact registry and existing skills before creating anything.
3. Apply the extraction threshold and select exactly one primary artifact type.
4. Draft the artifact with provenance, permissions, evidence, budget, and an
   owner.
5. For a workflow, use the workflow schema and the workflow authoring protocol.
6. Validate the registry and every registered workflow.
7. Evaluate the artifact in fresh context and with a lower-capability model.
8. Get the required approval before publication.
9. Publish at the narrowest valid scope and update the registry.
10. Record the outcome in portable-brain memory and monitor the first three
    uses.

Run the integrity gate before publication and after a portable-brain upgrade:

```bash
python3 .agent/tools/validate_extracted_artifacts.py
```

## Integrity rules

- Every registered path must exist and parse when its format is machine-readable.
- The fleet doctor must compare managed files with its trusted distribution
  copy before it runs the trusted validator. It must not execute a validator
  from the audited project.
- Every artifact must have one stable identifier, owner, scope, version,
  status, source state, and trigger set.
- Every workflow step must declare evidence and side effects.
- Every referenced protocol, skill, tool, or workflow must exist.
- An overlay can make a gate stricter. It cannot weaken a global hard gate.
- Publication and self-approval cannot be the same authority.
- A failed check blocks publication. An agent must not replace evidence with a
  written assurance.
- History is append-only. Supersede or archive an artifact; do not erase its
  provenance.

## Distribution boundary

The `agentic-stack` installer distributes the protocol, registry, schema,
reference workflow, validator, and adapter discovery map. A source checkout is
not fleet-wide adoption. Each repository must install or upgrade to a release
that contains these artifacts and pass the validator.

This contract does not execute arbitrary workflows. A workflow runtime is a
separate artifact with its own permission, evidence, retry, and rollback
contract. Do not claim runtime execution when only structural validation ran.

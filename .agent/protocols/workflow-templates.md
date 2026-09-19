# Workflow template authoring

## Purpose

Define how agents write, extend, validate, evaluate, publish, and execute workflow templates. A
workflow template coordinates existing protocols, skills, tools, roles, and evidence. It does not
duplicate their internal instructions.

## Canonical format

Use dependency-free JSON as the canonical source. A renderer can produce YAML or Markdown views.
Do not make a rendered view authoritative. Canonical files use the suffix `.workflow.json`.

The starter is `.agent/templates/workflow-template.workflow.json`. Validate registered templates
with:

```bash
python3 .agent/tools/validate_extracted_artifacts.py
```

## Required sections

| Section | Responsibility |
|---|---|
| Identity | Stable id, name, scope, version, description, and project requirements. |
| Parameters | Typed external inputs and defaults. |
| Preconditions | Checks that run before side effects. |
| Steps | Ordered work with artifact references and stop behavior. |
| Permissions | Maximum side effects and approval gates. |
| Budget | Tool-call, token, and wall-time bounds. |
| Memory | Declared reads and writes with scope. |
| Evidence | Required outputs that prove completion. |
| Completion | Machine-checkable closure conditions. |
| Rollback | Reversal or an explicit not-applicable rationale. |
| Handoff | Required receiving state and owner actions. |
| Evaluation | Test scenarios and lower-model requirement. |
| Provenance | Author, sources, observation time, and supersession. |

## Step contract

Each step has:

- a unique stable `id`;
- one `use` reference to a protocol, skill, tool, workflow, template, or human gate;
- explicit `with` inputs;
- declared `produces` outputs;
- `onFailure` behavior;
- side-effect class;
- required evidence identifiers.

Use stable step ids so project overlays can add a step before or after another step. Do not use
array position as an overlay contract.

## Side-effect classes

| Value | Meaning |
|---|---|
| `none` | Read, compute, or render only. |
| `local-write` | Writes only inside the authorized project/profile scope. |
| `remote-read` | Reads an approved external system. |
| `remote-write` | Changes an external system and needs the declared authority. |
| `destructive` | Deletes, overwrites, migrates, or makes recovery difficult. |

The workflow-level permission is the maximum. A step cannot exceed it. An overlay can reduce the
maximum but cannot increase it without a new approval record.

## Workflow authoring from a trace

1. Select a successful trace and related failures.
2. State the stable outcome and boundaries.
3. Replace project values with typed parameters.
4. Convert repeated deterministic actions into tool references.
5. Keep judgment in a skill or human gate.
6. Add missing preconditions, failure handling, evidence, rollback, and handoff.
7. Set budgets from observed use with a safe margin.
8. Generate required evaluation scenarios.
9. Register the draft.
10. Validate, simulate, evaluate, and publish.

## Workflow authoring from a request

An agent can draft a workflow when the user requests a reusable flow. The agent must search the
registry first. If no compatible workflow exists, it uses the canonical template and records the
request as provenance. The same validation and evaluation gates apply as trace-based authoring.

## Overlay contract

A project or component workflow can extend a global workflow by stable identifier and compatible
major version. An overlay can:

- bind project identity and defaults;
- add preconditions or steps;
- refine parameters;
- reduce permission and budget limits;
- add evidence, evaluation, rollback, or handoff requirements;
- replace an extension point that the base marks as replaceable.

An overlay cannot:

- remove a global hard gate;
- widen side effects or permissions without approval;
- remove required evidence, rollback, or failure behavior;
- select a different memory/hook authority;
- hide a base workflow version conflict.

## Execution

Before execution, the runner must:

1. Resolve global, project, local, and session layers.
2. Validate the effective workflow.
3. Resolve every referenced artifact and version.
4. Validate parameters and freshness.
5. show required approvals and maximum side effect.
6. Establish budget counters and evidence storage.

During execution, record step start, result, outputs, evidence, duration, tool calls, and token
estimate. Stop when a required step fails unless the workflow declares an exact fallback.

Closure requires all completion conditions and evidence. A handoff is part of completion.

## Validation and evaluation

Structural validation is necessary but not sufficient. Validate schema, identifiers, references,
permissions, budgets, step order, evidence ownership, completion, rollback, handoff, and provenance.

Evaluate valid input, missing input, stale input, permission denial, tool failure, project overlay,
lower-capability model, and repeat-run behavior. Do not give the evaluation agent the intended
answer or hidden reasoning.

## Versioning and retirement

Use semantic versions. A breaking parameter, output, step-id, permission, or evidence change
increments the major version. A compatible capability increments the minor version. A correction
increments the patch version.

An active workflow can be `superseded` and then `archived`. Keep its provenance and execution
history. Never silently edit a version that has execution evidence.

## Template-writing integrity

An agent can write workflow templates, but it cannot self-approve them. Publication requires:

- registry entry;
- structural validator pass;
- referenced artifact resolution;
- required scenario results;
- independent fresh-context review;
- owner or approved promotion-policy decision;
- versioned provenance.

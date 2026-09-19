# Repetitive-work extraction

## Purpose

Convert repeated agent work into governed protocols, skills, tools, workflows, templates, or
memory. Reduce repeated discovery and token use without creating duplicate or unsafe automation.

## Boundary

This protocol governs observation, candidate detection, classification, drafting, evaluation,
publication, use, evolution, and retirement. It does not permit remote writes, dependency
installation, or permission changes.

## Evidence inputs

The extractor can use only redacted, attributed evidence:

- episodic entries from `memory_reflect.py` and harness hooks;
- completed work-item plans and verification records;
- PR review findings and file-to-ticket audits;
- repeated command and tool sequences;
- repeated user corrections;
- recurring validator failures;
- workflow duration, tool-call count, and token estimates;
- successful and failed handoffs.

Each observation must record `profile`, `projectId`, `componentId`, task type, ordered actions,
inputs, outputs, side effects, result, source, observation time, and redaction state.

## Candidate thresholds

A repeated flow becomes a candidate when one condition is true:

1. It succeeds three times with substantially the same steps.
2. The same omission or failure occurs twice.
3. Two agents independently create the same helper or checklist.
4. Agents repeatedly spend material tokens rediscovering a stable contract.
5. A deterministic cross-file or cross-system invariant needs repeated checks.
6. A security-critical deterministic check must not depend on model judgment.
7. The user explicitly requests automation or standardization.

The candidate remains evidence, not active tooling.

## Artifact classification

Classify by the primary responsibility. Do not place one responsibility in two artifact types.

| Decision | Artifact |
|---|---|
| Mandatory invariant or lifecycle rule | Protocol |
| Contextual procedure that requires judgment | Skill |
| Deterministic input-to-output operation or check | Tool |
| Multi-step coordination across tools, gates, roles, or systems | Workflow template |
| Reusable code, document, or configuration structure | Asset/template |
| Stable fact, preference, decision, lesson, or current state | Memory |

One candidate can produce several artifacts when each owns a different responsibility. Example:
a Sprint-planning flow can produce a protocol for plan coverage, a validator tool, a planning skill,
a workflow template, and a work-item asset. The artifacts must link through identifiers. They must
not repeat the same instructions.

## Promotion scope

| Evidence | Initial destination |
|---|---|
| One project only | Named project candidate |
| Two or more projects with the same invariant | Global candidate |
| One component-specific contract | Component overlay |
| User-confirmed universal rule | Global accepted rule |
| User-confirmed project rule | Named project accepted rule |

Imported or cross-project patterns lose confidence until the target project confirms them. A
global workflow can have project overlays. An overlay cannot weaken a hard global gate.

## Lifecycle

Each artifact moves through these states:

```text
observed → candidate → drafted → validated → evaluated → accepted → active
                                                        ↘ rejected
active → superseded → archived
```

Rules:

1. Keep observation and decision provenance.
2. Do not publish directly from an observation.
3. Validate deterministic behavior before model evaluation.
4. Evaluate a complex artifact with a fresh context and no hidden answer.
5. Require a human or an approved promotion policy for global publication.
6. Never delete history. Supersede and archive.
7. Re-run dependent tests when an artifact changes.

## Artifact contracts

### Protocol

State purpose, scope, mandatory rules, stop conditions, evidence, precedence, exceptions, and owner.
Hard rules must be enforceable where possible.

### Skill

Use concise triggering metadata, a focused `SKILL.md`, progressive disclosure, and only necessary
scripts, references, and assets. Test scripts and forward-test judgment-heavy workflows.

### Tool

Declare:

- stable identifier and version;
- typed inputs and outputs;
- side effects and permission class;
- idempotency and retry behavior;
- timeout and resource bounds;
- redaction and secret policy;
- failure exit codes;
- supported platforms;
- tests, owner, and provenance.

Tools are dependency-free by default. They fail closed on malformed input. They do not print
secrets. A tool failure must not cause an agent to improvise the same mutation manually.

### Workflow template

Follow `protocols/workflow-templates.md` and the canonical workflow template. Declare parameters,
preconditions, steps, permissions, budgets, evidence, completion gates, rollback, handoff,
evaluation, and provenance.

### Asset/template

Keep reusable output structure separate from instructions. A template has a version, owner,
parameters, compatibility rules, and validation method.

### Memory

Use the profile-layering protocol. Store facts and lessons once with scope and provenance. Do not
copy the same rule into adapter files.

## Drafting process

1. Select evidence and state the repeated invariant.
2. Replace observed values with typed parameters.
3. Separate deterministic work from judgment.
4. Reuse existing artifacts before creating one.
5. Add permissions, failure handling, evidence, rollback, and handoff.
6. Set global, project, component, or local scope.
7. Register the draft with status `drafted`.
8. Run structural validation and tests.
9. Run independent evaluation for skills and workflows.
10. Publish only after all required evidence exists.

## Evaluation matrix

Use a fresh agent context for each required scenario:

| Scenario | Required result |
|---|---|
| Valid input | Completes and produces all evidence. |
| Missing input | Stops before side effects and names the input. |
| Stale input | Refreshes or stops at the freshness gate. |
| Permission denied | Performs no prohibited action. |
| Tool failure | Stops or follows the declared fallback. |
| Project overlay | Applies the correct project identity and extension. |
| Lower-capability model | Completes without hidden session knowledge. |
| Repeat run | Honors idempotency and does not duplicate effects. |

## Runtime integrity

Agents must:

1. Resolve profile and project identity before discovery.
2. Load required protocols, skills, workflows, and tool contracts.
3. Validate the extracted-artifact registry.
4. Follow workflow step order and stop conditions.
5. Produce required evidence before closure.
6. Record reflection after significant use or failure.
7. Propose evolution when the same workaround or failure recurs.

Hooks and validators should enforce deterministic checks. A completion statement from a model is
not evidence.

## Rejection rules

Reject extraction when:

- the task has not repeated and is not safety-critical;
- the underlying contract is unstable;
- inputs, outputs, or side effects cannot be defined;
- human judgment is the essential operation;
- an existing artifact already owns the behavior;
- the wrapper only renames one simple command;
- maintenance cost exceeds measured savings;
- it requires unapproved dependencies or remote mutation;
- it stores or exposes secret values;
- it duplicates project-native tooling.

## Metrics and evolution

Track use count, success/failure, manual fallback, token savings, duration, stale-contract failures,
and user corrections. A recurring failure returns the artifact to `drafted`. A superseding artifact
must name what it replaces. Archive unused artifacts after review; never delete their history.

# Confluence-access Integration Contract — BCG Confluence read access

> **This file is the BCG-harness sidecar to `SKILL.md`** (vendored, BCG-
> firm-specific, not subject to fork conformance lint). Marks the skill
> as vendored so `skill_linter.py` skips its self-rewrite-hook + manifest
> + index conformance checks (per Step 8.4 Phase I sidecar convention).

## Why vendored

The `confluence-access` skill encodes BCG-firm-specific configuration:

- Hard-coded `bcgx.atlassian.net` Confluence host
- BCG IP-allowlist protocol references
- BCG-internal page slug conventions (e.g., `BCTAH` space)

Cannot run on a non-BCG install without failing loudly. Therefore:

- Lives under `adapters/bcg/skills/` (BCG adapter territory, not fork
  generic territory)
- Propagated to target's `.agent/skills/` only when
  `bcg_adapter == "enabled"` in target's `.agent/config.json`
  (per `harness_manager.post_install.bcg_conditional_propagate`)
- Updates flow fork → adapter → target via `sync-target.sh`; the
  fork does NOT iterate on the SKILL body, so the canonical self-
  rewrite hook discipline does not apply

## Conformance posture

`skill_linter.py` checks dirs containing `INTEGRATION.md` are vendored
and skips:
- Self-rewrite hook section presence
- Manifest entry (`.agent/skills/_manifest.jsonl`) match
- Index entry (`.agent/skills/_index.md`) header match

These three are appropriate for skills the fork OWNS and evolves, not
for vendored upstream content the fork merely propagates.

## Update path

Changes to the BCG-side `confluence-access/SKILL.md` happen on the BCG
adapter side, then propagate to existing targets via:

```bash
./sync-target.sh <target-dir>
```

Fresh-install targets get it on first install via
`bcg_conditional_propagate`.

## When to graduate to non-vendored

If a Confluence-access pattern emerges that is firm-agnostic
(generic Confluence integration, no BCG-specific URLs/protocols),
fork it into `.agent/skills/<generic-confluence>/` and let it
inherit full conformance discipline. The current skill stays
vendored.

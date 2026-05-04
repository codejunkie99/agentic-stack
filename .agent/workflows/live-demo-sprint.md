---
workflow_id: live-demo-sprint
name: Live External-Stakeholder Demo Sprint
team_structure: full
description: End-to-end build of a working live demo for a fixed external-stakeholder meeting (client, partner, exec audience). Real backend logic on a thin UI, anchored on a single critical-path "wow" beat (a planted-discovery moment, an unexpected agent action, a non-obvious result). Distinct from prototype-app.md (validation-focused, no fixed external audience) and demo-prep.md (packaging an EXISTING prototype). This workflow runs from blank → meeting-ready, with scenario-lock, synthetic-scenario design, wow-beat hardening, audience-translation, and dry-run as explicit stages with named owners.
---

## Purpose

Produce a live demo for a fixed-date external meeting where the audience must come away convinced the system *does something*, not just *looks like something*. The demo's value is concentrated in one or two beats; everything else is table stakes. The deadline does not move and the audience does not get a second take.

This workflow exists because:

- `prototype-app.md` (lite-PDLC) optimizes for hypothesis validation. The lessons-learned doc is the deliverable. A live external demo has no LEARNINGS.md exit — the deliverable is the meeting going well.
- `demo-prep.md` packages an existing prototype. It assumes the build is done. This workflow drives the build *and* the package.
- `feature-prototype.md` and `tech-spike.md` are scoped to a single feature or research question. A live demo typically threads multiple capabilities (data, reasoning, UI, narration) into one continuous beat sequence.

The workflow stays opinionated about three things: scenario must lock before build, synthetic data must contain a discoverable structure (not just be plausible), and the wow beat gets disproportionate engineering time.

## Trigger phrases

"build a live demo for [meeting]", "demo for [stakeholder] on [date]", "we're showing this to the client on [date]", "live working demo", "build the [scenario] demo", "five-minute demo", "partner showcase demo".

## When NOT to use

- The meeting is internal-only with low stakes — use `prototype-app.md` spike mode + `demo-prep.md` instead.
- There's no fixed external deadline — use `prototype-app.md` (lite-PDLC) and treat demo packaging as a follow-on.
- The demo is a click-through mock with no backend logic — use `feature-prototype.md` or a Figma flow; a backend-light demo doesn't need this workflow.
- The scope is a tech evaluation ("does library X work for our use case") — use `tech-spike.md`.

## Stages

Each stage names an owner agent, the inputs it consumes, the artifact it produces, and the exit gate that lets the next stage start. Calendar dates are an engagement-instance concern; the workflow itself is about the sequence and ownership.

| # | Stage | Owner | Inputs | Output | Exit gate |
|---|---|---|---|---|---|
| S1 | **Scenario lock** | `brainstorming` skill + `product-discovery` skill (root agent runs both) | Briefing materials, partner intent, audience profile | `output/demos/<slug>/scenario.md` (one-pager: who, what, single sentence on the moment that lands) | Partner / requesting stakeholder signs off in writing (transcript snippet, Slack reply, email reply — captured into the file) |
| S2 | **Demo spec** | `product-manager` agent (lite mode — see "Demo spec contract" below) | Scenario one-pager | `output/demos/<slug>/demo-spec.md` | `spec-reviewer` skill returns ≥ 7/10; the wow beat has an explicit success criterion you could observe in the room |
| S3 | **Synthetic scenario design** | `backend-engineer` + `synthetic-scenario-design` skill | Demo spec | `output/demos/<slug>/data/` (generator script + dataset + `pattern-card.md` documenting the planted discovery) | The planted pattern surfaces when an agent queries the dataset blind, AND does not surface from a 30-second eyeball scan of a sampled slice |
| S4 | **Build (parallel where independent)** | `prototype-engineer` (lead) + `backend-engineer` + `frontend-engineer` | Demo spec, dataset | Working end-to-end demo runnable from one command | Demo runs the full beat sequence end-to-end without manual stitching |
| S5 | **Wow-beat hardening** | `prototype-engineer` + `qa-runner` | Working demo | Hardened critical-path beat with deterministic outcome (or controlled stochasticity within an acceptable band) | The wow beat lands cleanly across 3 consecutive cold runs; failure modes documented in `runbook.md` |
| S6 | **Audience-translation pass** | `delivery-lead` (acting as audience-fit reviewer) + root agent | Working demo + draft narration | `output/demos/<slug>/narration.md` (spoken track, audience-tuned) + `q-and-a.md` | No software jargon in the spoken track unless the audience is software-fluent; technical claims have a one-line plain-language gloss |
| S7 | **Demo packaging** | engineer or `prototype-engineer` + `demo-prep` skill | Hardened demo + narration | `output/demos/<slug>/` package (README, demo command, screenshots, fallback, narration, q-and-a) | One-command run from a clean clone; fallback screenshots cover all beats; demo-prep skill quality gates pass |
| S8 | **Dry-run** | `qa-runner` + root agent | Full package | `output/demos/<slug>/dry-run-log.md` (per-run timing, what landed, what slipped) | At least 2 consecutive timed runs land within the agreed time window with the wow beat firing as designed |

Stages can compress when the calendar is tight: S1+S2 in one sitting, S3 starts as soon as the wow beat is named (don't wait for full demo-spec), S6 + S7 + S8 in the final day. What CANNOT compress: S5 (wow-beat hardening) and S8 (dry-run). Both protect against in-meeting failure.

## Demo spec contract (S2 output)

A demo-spec is lighter than a PRD and heavier than a HYPOTHESIS.md. It exists because the team needs a single doc that names the beats, the success criterion, and the fallback — without spending half a day on a full PRD for throwaway code.

Required sections:

- **Audience** — who's in the room, what they know, what jargon to avoid
- **The single sentence that summarizes the demo** — if you can't say it in one sentence, the demo isn't focused
- **Beats** — each beat: target time, what the user sees, what the system does, narration line
- **Wow beat** — explicitly tagged. What is the moment the audience leans in for? What is the success criterion (observable in the room)?
- **Backend logic surface** — bullet list. What does the system actually compute / decide / discover? (This is what makes the demo not-vibecode.)
- **Scope guardrails — out of scope** — what we are NOT building. Pushed out, parked, or replaced with a static placeholder.
- **Fallback plan** — if the live demo fails mid-run, what's the recovery? (Pre-recorded video, screenshots, hand-wave + narrate forward.)
- **Success criterion** — what does "the demo went well" look like? (Specific stakeholder reaction, follow-up meeting booked, specific question asked.)

The spec is approved by the root agent at S2 exit and re-read at the start of every subsequent stage.

## Wow-beat protection

The wow beat is the project. Everything else can degrade gracefully; the wow cannot. Protections this workflow encodes:

- **S5 is non-skippable.** Even when the calendar is on fire, S5 happens. If you must cut a stage, cut S7 polish (use a rougher package) or S6 narration depth (use bullet points instead of a tuned script).
- **S3's planted-pattern test is binary.** Either an agent finds the pattern from a blind query of the dataset, or the data redesigns. No "it'll work in the demo because we'll prompt it just right."
- **S5 produces a runbook entry per failure mode.** When the wow beat fails in a cold run, the failure goes into `runbook.md` with a recovery line. If 3 cold runs all fail differently, escalate scope — the beat is too brittle for live.
- **Stochasticity is contained.** If the wow beat depends on a non-deterministic agent run, S5 must establish either (a) a deterministic seed, (b) a prompt + tool surface narrow enough that the band of outcomes is acceptable, or (c) a "best of N" pre-run that gets cached for the meeting.

## Audience-translation gate (S6)

Live demos collapse when the spoken track uses vocabulary the audience doesn't share. This gate is enforced explicitly because software-fluent teams default to software-fluent narration without noticing.

The gate produces:

- A **spoken track** for the demo presenter — sentence-by-sentence, mapped to beats
- A **jargon ledger** — every software/AI term that appears in the demo, paired with the plain-language gloss to use instead
- A **Q&A doc** — anticipated audience questions with answers in audience-vocabulary

Pass criterion: a non-software-fluent reader can read the spoken track and predict what the system is doing at each beat. If they can't, the gate fails and S6 reruns.

## Iteration cookbook

Once the demo is built, the user (or partner) tests it and surfaces feedback. Most feedback is shaped by which stage's output it implicates. Talk to the session normally — the orchestrator reads this table and re-enters at the right stage. You don't need to address agents directly.

| Feedback shape | Re-enter at | Why |
|---|---|---|
| "The wow beat feels flat / not surprising" | S5, possibly S3 (data redesign) | The discovery isn't landing because either the discovery is too obvious, the planted pattern is too noisy, or the build doesn't surface it cleanly. Start at S5; if the discovery itself isn't compelling, redesign data at S3. |
| "The narration doesn't land for this audience" | S6 | Jargon, pacing, or framing — audience-translation gate failure. |
| "Backend logic is broken / produces wrong output" | S4 (bugfix-arc.md inline) | Mechanical bug. Bugfix-arc, then re-run S5 dry-runs. |
| "UI looks ugly / distracting" | S4 (frontend-engineer) OR S6 (narration ducks under it) | Decide whether the UI matters for the wow or whether narration carries it. |
| "Data pattern feels fake / engineer in the room will spot it" | S3 (data redesign) | Planted-pattern credibility failure. Redesign generator with domain-credible noise floor + pattern shape. |
| "Partner wants a new beat added" | S2 (demo-spec amendment), then S3+ as needed | New beat means scope change. Re-spec, then propagate. Resist adding beats without re-spec. |
| "Demo runs over time" | S2 (cut beats) or S5 (tighten transitions) | If the spec is honest, the cut comes from S2 (drop a beat). If transitions are loose, S5 fixes it. |
| "Demo runs under time and feels thin" | Caution — DO NOT add a new beat without re-running S2 spec review | Thin demos that get padded last-minute usually break in the room. Better to land short and confident than long and ragged. |
| "Engineer in the audience asked a question we couldn't answer" | S6 (extend Q&A doc) for next round | Update Q&A; capture the question in `runbook.md`. |
| "Fallback path is untested" | S5 + S8 | Run a dry-run with deliberate primary-path failure to verify fallback. |

For feedback that doesn't fit this table, default behavior is: name the affected output (data, build, narration, package), re-enter the corresponding stage, re-run S5 + S8 before declaring done.

## Quality gates (workflow exit)

- All 8 stages signed off in `output/demos/<slug>/WORKSPACE.md` or equivalent
- 3 consecutive successful timed dry-runs (S8 final state)
- Fallback path tested at least once
- Narration script finalized; jargon ledger empty or fully glossed
- Memory reflection captured (see below)

## Memory write discipline

`memory_reflect` at workflow exit:

- `importance=9, pain=7` (live external demos are high-stakes recurring work — this should dominate the cluster)
- Note must capture a DURABLE LESSON: what about the scenario, the planted-pattern design, the wow-beat shape, or the audience-translation choice generalizes to the next demo. Not "we built X." Closer to "Singapore mech-elec audiences need plain-language gloss inline with each beat, not bundled at end."
- Tag the entry with the engagement slug and the audience profile (software-fluent / domain-fluent / mixed) so future demo builds can pull lessons by audience shape.

## Anti-patterns

- **Skipping scenario lock and going straight to build.** Build without a locked scenario produces 80% of a demo for a scenario that gets cut on Wednesday. Lock scenario first; the cost of S1 is < the cost of one rebuild.
- **Treating S3 (synthetic data) as "throw some mock data in a JSON file."** Real wow-beats discover real-shaped patterns. Mock data without planted structure makes the agent look like it's improvising; mock data with cartoonish structure makes the agent look like it's cheating. The skill exists for this reason.
- **Polishing S7 packaging before S5 hardening is done.** Packaging a brittle demo wastes packaging effort when the demo gets reshaped after S5 surfaces failures.
- **Adding beats in the last 24 hours.** Net negative. Cut, don't add.
- **Letting an internal-team rehearsal substitute for S8 cold runs.** Internal rehearsal calibrates the team; S8 cold runs verify the system. Both are needed; one isn't a substitute.

## Path-forward decision (post-meeting)

After the meeting:

- **Scrap** — demo served its purpose; archive at `output/demos/<slug>/` with status="archived" and the meeting outcome captured.
- **Iterate** — re-run S6/S7 (or earlier) for a follow-on meeting with a different audience.
- **Graduate** — the demo's logic should become a real product feature. Re-run `feature-end-to-end.md` against the validated PRD; rebuild under production discipline. The demo's value was the locked scenario + the proven backend logic shape, not the code.

This decision is documented in `output/demos/<slug>/POST-MORTEM.md` before the orchestrator moves on.

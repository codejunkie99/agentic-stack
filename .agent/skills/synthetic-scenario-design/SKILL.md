---
name: synthetic-scenario-design
description: Use when a demo or prototype needs synthetic data that contains a planted, agent-discoverable structure — not just plausible-looking mock data. Designs domain-credible datasets where an agent can find a non-obvious pattern (seasonality, correlation, drift, hidden cluster) that an engineer-eyeball scan would miss in 30 seconds. Triggers on "design synthetic data with a hidden pattern", "fake dataset where the AI finds something", "synthetic logs with planted seasonality", "demo data with a discoverable pattern". Distinct from generic mock-data generators — this skill enforces credibility (domain-shaped noise floor) AND discoverability (planted structure that survives an agent's blind query).
version: 2026-05-04
triggers: ["design synthetic data with a hidden pattern", "fake dataset where the AI finds something", "synthetic logs with planted seasonality", "demo data with a discoverable pattern", "scenario with planted pattern", "synthetic dataset for demo wow beat"]
tools: [bash, memory_reflect]
preconditions: ["demo-spec or scenario document exists naming the wow-beat discovery", "domain context available (engineer SME, document-researcher summaries, or partner brief)"]
constraints: ["planted pattern must survive a blind agent query", "planted pattern must NOT be visible in a 30-second eyeball scan of a sampled slice", "domain-credible noise floor (no cartoon distributions)", "every planted structure documented in pattern-card.md alongside the dataset"]
---

# Synthetic Scenario Design — design data the agent can discover something in

Goal: produce a synthetic dataset for a live demo or prototype where the wow beat is "the agent found something a human missed." The dataset must be (a) domain-credible enough that a subject-matter expert in the room doesn't reject it on sight, (b) noisy enough that the planted structure isn't trivial, and (c) structured enough that the agent's discovery is genuine — the pattern is actually there, the agent didn't hallucinate it.

## When this fires

- A `live-demo-sprint.md` or `prototype-app.md` workflow has reached the "we need data" stage and the wow beat depends on the agent finding something
- User says "we need synthetic data where the AI surfaces a hidden pattern" or equivalent
- A demo-spec names a wow beat that's a discovery (seasonality, correlation, drift, anomaly cluster, hidden segment)

## When this does NOT fire

- Generic mock data for unit tests — use a fixture file
- UI placeholder data — use Lorem-ipsum-shape generators
- Data that just needs to *look* plausible without a planted pattern — use any mock-data library
- Production-grade synthetic data with privacy guarantees — different problem (use differential privacy / GAN-based synthesis instead)

## What you do

The skill runs in five steps. Don't skip steps; the failure mode of synthetic-scenario design is "the planted pattern is too obvious OR too noisy" and the steps are designed to catch that.

### 1. Read the demo spec and name the discovery in one sentence

Open the demo-spec or scenario doc. Find the wow beat. Restate it as: "The agent will discover that [one specific pattern] in [the dataset]."

If you can't restate it that cleanly, stop and ask the requester to sharpen the wow beat. A vague wow beat ("the agent finds something interesting") cannot be designed into data — you'd be planting noise. Force the precision before generating.

Examples of well-named discoveries:
- "The agent will discover that chiller coil-fouling alarms correlate with high-haze-index days from regional fires (2-day lag), surfacing across 18 months of logs."
- "The agent will discover that customer-churn risk is bimodal: a known high-tenure cluster AND an unexpected 30-60-day-tenure cluster driven by post-onboarding integration friction."
- "The agent will discover that error-rate spikes lead deploy events by ~45 minutes, suggesting a pre-deploy traffic shift."

### 2. Establish the domain-credible base distribution

Before planting anything, model the dataset *as if* the planted structure didn't exist. What's the natural shape?

- What dimensions / columns / fields does this dataset have? (Domain-shaped, not generic.)
- What's the normal range, distribution, seasonality of each? (Use real-world references where possible — published industry benchmarks, public datasets, SME input.)
- What's the noise floor? (How much variation does the domain show in a normal week / day / hour?)
- What correlations exist *naturally* in the domain? (Temperature ↔ humidity in HVAC; promotions ↔ sales in retail; deploys ↔ error rates in software.)

Document this in `pattern-card.md` Section 1: **Base distribution**. The planted pattern will be layered on top of this, not in place of it.

### 3. Plant the discoverable pattern

Now layer the structure that the agent must find. Two contracts:

**Contract A — surfaceable.** The pattern must appear when an agent runs a reasonable query against the dataset blind (no pre-knowledge of the pattern). Run the smell-test: write the query an agent would run and confirm the pattern shows up in the output. If you have to lead the agent to it with prompt scaffolding, the pattern is too weak.

**Contract B — not eyeball-visible.** The pattern must NOT appear when a human samples 50-100 rows and scans for 30 seconds. Run this test too: print a random 100-row slice, ask yourself "could I see the seasonality / correlation / cluster from this?" If yes, the pattern is too strong — make the noise floor harder, lengthen the time horizon, dilute the signal.

The space between "surfaces from a blind query" and "doesn't surface from eyeball scan" is the credibility window. Most failures of synthetic-scenario design are outside this window.

Document the planted structure in `pattern-card.md` Section 2: **Planted structure**. Include:
- The shape of the pattern (formula, correlation coefficient, magnitude, lag, etc.)
- The expected query that surfaces it
- The expected output of that query
- The noise level the pattern survives at

### 4. Generate, sample, verify

Write the generator script. Generate the dataset. Then run two verifications:

**Verification A — blind agent query.** Pretend you're an agent with no foreknowledge. Run the kind of query an agent would run (group-by-time, correlation matrix, anomaly detection, clustering). The planted pattern should rank in the top results. If it doesn't, the noise floor is too high or the pattern magnitude is too low.

**Verification B — eyeball test.** Print a 100-row sample. Scan for 30 seconds. Can you see the pattern? If yes, the pattern is too strong.

Loop on the generator until both verifications pass. This is the single most important step in the skill — most generated datasets fail one or the other on the first try.

Document verification results in `pattern-card.md` Section 3: **Verification log**.

### 5. Stress-test against the wow-beat narration

Read the demo-spec narration line for the wow beat. Imagine the demo running. Does the dataset support the narration?

- If the narration says "the agent found this across 3 years of logs," does the dataset cover 3 years? (Don't fake the time horizon.)
- If the narration implies "and a human couldn't have spotted this," does Verification B confirm it?
- If the narration implies "and this is a real-world-shaped fault," does the planted pattern map to a known domain mechanism (not invented)?

Mismatches between dataset and narration are the second-most-common failure mode. Catch them here, not in the demo.

Document any narration-driven adjustments in `pattern-card.md` Section 4: **Narration alignment**.

## Pattern-card.md format

Every dataset this skill produces ships with a sibling `pattern-card.md` so future demos and post-mortems know what was planted.

```markdown
---
dataset: <path or generator script>
generated_at: <ISO date>
demo_slug: <slug>
wow_beat: <one-sentence restatement of the discovery>
---

# Pattern Card — <dataset slug>

## 1. Base distribution
- Dimensions: ...
- Natural ranges + noise floor: ...
- Natural correlations: ...
- References / SME input: ...

## 2. Planted structure
- Shape: ...
- Magnitude / coefficient: ...
- Time horizon required to surface: ...
- Expected agent query: ...
- Expected query output: ...

## 3. Verification log
- Blind agent query test: PASS / FAIL — what surfaced
- Eyeball test (30s scan, 100-row sample): PASS / FAIL — what was visible
- Iteration count to pass both: <n>

## 4. Narration alignment
- Demo-spec narration line: "..."
- Dataset coverage matches: yes / no — what we adjusted
- Domain-credible mechanism: <name the real-world fault/mechanism>

## 5. Failure modes to watch for in the demo
- ...
```

## Examples

**Correct.** HVAC demo for a Singapore airport. Scenario: agent finds chiller coil-fouling correlates with regional-haze-index. Skill produces a 3-year synthetic dataset of HVAC logs with: realistic chiller operating ranges (8000-12000 RT, 5-7 °C chilled water supply), tropical-climate humidity baseline (65-90% RH year-round), monsoon-season ventilation loads, AND a planted 2-day-lagged correlation between haze-event days (publicly documented PSI spikes from Sumatran fires) and coil-fouling alarm density. Agent's blind query (group-by-week + cross-correlate alarm rate with external climate signals) surfaces the haze correlation. Eyeball scan of 100 rows shows nothing. Pattern card documents domain mechanism (haze particulates → coil deposition) so the SME in the room recognizes it.

**Failure mode (avoid).** "Add some seasonality to the data and the agent will figure it out." Too vague. The pattern won't be designed; it'll be improvised at generation time, fail one of the two verifications, and the demo's wow beat won't survive the dry-run. Force the discovery to a single sentence in step 1.

**Failure mode (avoid).** Pattern is so strong it's visible in a 100-row eyeball scan. The audience SME notices and the demo collapses ("isn't that just obvious from the data?"). Loop on noise floor until eyeball test fails.

**Failure mode (avoid).** Pattern is so weak the agent only finds it with a prompt that reveals the answer ("look for haze-correlated alarms"). The agent looks like it's reciting, not discovering. Loop on pattern magnitude until blind query surfaces it.

**Failure mode (avoid).** Pattern doesn't map to a known domain mechanism (e.g., correlating chiller failures with stock-market volatility). SME in the room rejects it as cargo-cult AI. Always anchor the planted pattern in a domain-credible mechanism documented in pattern-card.md Section 4.

## Self-rewrite hook

After every 3 datasets this skill produces, OR the first time a dataset's planted pattern fails in a live demo (audience didn't react, SME called it out, agent didn't surface it), read the last 3 `synthetic-scenario-design` entries from episodic memory plus the failed demo's POST-MORTEM.md. If a better verification step, a new failure mode worth flagging, or a sharper way to express the credibility window has emerged, update this file. Commit: `skill-update: synthetic-scenario-design, <reason>`.

Reflect at exit:

```bash
python3 .agent/tools/memory_reflect.py "synthetic-scenario-design" \
  "designed dataset for <demo-slug>" \
  "wow_beat=<one-line>; planted_pattern=<shape>; iterations=<n>; both verifications passed" \
  --importance 8 --pain 6 \
  --note "DURABLE LESSON: <one sentence on what about this dataset's design transfers to the next planted-discovery demo — e.g. 'tropical-climate datasets need monsoon-season as the natural seasonality so the planted lag-correlation is the discovery, not the climate itself'>"
```

Importance 8 × pain 6 = 48 → salience high enough to dominate cluster, low enough to not auto-graduate without a second similar entry. When 2+ planted-pattern designs from different engagements graduate together, that's the lesson worth promoting to LESSONS.md.

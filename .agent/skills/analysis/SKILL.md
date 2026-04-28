---
name: analysis
version: 2026-04-24
bootstrapped_from: "harness-starter-kit (Kenneth Leung, BCG) — 2026-04-24 import, Step 8.1"
description: Use for structured analytical work on case/engagement questions — market sizing, benchmarking, driver decomposition, scenario analysis, feasibility. Produces findings in a [Finding → So What → Confidence] shape with explicit assumptions, data gaps, and sensitivity on top-driver inputs. Trigger on analytical questions, not on planning or implementation.
triggers: ["analyze this", "market sizing", "benchmarking", "driver analysis", "scenario analysis", "how big is", "what drives", "is this feasible"]
tools: [recall, bash]
preconditions: ["analytical question stated"]
constraints:
  - every finding has a So What and a confidence level
  - assumptions listed explicitly — no hidden premises
  - sensitivity check identifies top 2-3 driver inputs
  - flag data gaps rather than silently filling them
category: knowledge-work
---

# Analysis Skill

Use this skill to perform structured analytical work on case engagement questions.

## Analysis Protocol
1. **Frame the Question** — State the analytical question in one sentence
2. **Identify Data Sources** — List what's available in context; flag gaps
3. **Apply Method** — Choose appropriate method (sizing, benchmarking, regression proxy, etc.)
4. **Produce Findings** — Structure as: [Finding] → [So What] → [Confidence Level]
5. **State Assumptions** — Explicit list of all assumptions made
6. **Sensitivity Check** — Identify top 2-3 inputs that most affect the conclusion

## Method Selection

| Question Type | Method |
|---|---|
| "How big is X?" | Market sizing (top-down or bottom-up) |
| "How do we compare?" | Benchmarking (peer set + methodology) |
| "What drives X?" | Driver decomposition |
| "What if?" | Scenario analysis with range |
| "Is this feasible?" | Capacity/resource analysis |

## Output Format

```yaml
question: <analytical question>
method: <chosen method>
findings:
  - finding: <observation>
    so_what: <implication>
    confidence: high | medium | low
assumptions:
  - <explicit assumption>
data_gaps:
  - <gap and impact on conclusion>
sensitivity:
  - input: <key variable>
    range: <plausible range>
    impact: <how conclusion changes>
```

## Self-rewrite hook

After every 5 analyses produced, or the first time a confidence
assignment turns out to be miscalibrated (a high-confidence finding
proved wrong, or a low-confidence finding proved correct), read the
last 5 analysis entries from episodic memory. If better decomposition
heuristics, sensitivity-range patterns, or confidence-assignment
rules have emerged, update this file. Commit:
`skill-update: analysis, <one-line reason>`.

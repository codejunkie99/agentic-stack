---
name: loop-guard
version: 2026-07-18
triggers: ["loop guard", "loop budget"]
tools: [bash]
preconditions: [".agent/loops/budget.json exists"]
constraints: ["read contracts and state before acting", "stop on budget or stagnation decisions"]
category: engineering
---

# Loop guard

Read current state before spending another attempt. Stop on pause, budget,
stagnation, or cancellation decisions and preserve the checkpoint.

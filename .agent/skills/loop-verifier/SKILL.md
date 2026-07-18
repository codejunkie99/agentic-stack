---
name: loop-verifier
version: 2026-07-18
triggers: ["loop verify", "verify loop work"]
tools: [bash]
preconditions: [".agent/loops and .agent/runtime exist"]
constraints: ["read contracts and state before acting", "run deterministic checks exactly as configured"]
category: engineering
---

# Loop verifier

Read the contract and checkpoint before reviewing. The deterministic verifier
is authoritative; do not turn a checker approval into a test pass.

---
name: loop-triage
version: 2026-07-18
triggers: ["loop triage", "daily triage"]
tools: [bash]
preconditions: [".agent/loops and .agent/runtime exist"]
constraints: ["read the selected contract and checkpoint before acting", "remain read-only"]
category: operations
---

# Loop triage

Read the selected loop contract and current checkpoint before reporting. Keep
the report bounded and do not mutate the workspace.

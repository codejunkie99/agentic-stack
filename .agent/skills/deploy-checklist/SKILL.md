---
name: deploy-checklist
description: Use proactively before deploying, shipping, or releasing. Triggers on "deploy", "ship", "release", "go live", "ready to ship". Verifies all tests passing, no unresolved TODOs in diff, requires human approval for production.
version: 2026-01-01
triggers: ["deploy", "ship", "release", "go live"]
tools: [bash]
constraints: ["all tests passing", "no unresolved TODOs in diff", "requires human approval for production"]
---

# Deploy Checklist — the fence between staging and prod

Run this checklist before any deploy. The production deploy itself is
gated by a human approval step enforced in `protocols/permissions.md`.

## Pre-deploy checks
- [ ] All tests passing locally and in CI.
- [ ] No unresolved TODOs or FIXMEs in the diff.
- [ ] Migrations are reversible, or an explicit rollback plan is documented.
- [ ] Env vars for new features are set in the target environment.
- [ ] Feature flags default to off for anything user-visible.
- [ ] Changelog or release notes updated.

## Staging deploy
- Deploy. Watch logs for 5 minutes. Click through the new flow in a real browser.
- If anything looks off, roll back and investigate. Do not push through.

## Production deploy
- This step *requires* human approval. The agent must ask, not assume.
- Deploy during a low-traffic window when possible.
- Watch error rate and latency dashboards for 15 minutes post-deploy.
- Be ready to rollback in one command; have the rollback command pre-typed.

## Post-deploy
- Log the deploy (version, time, who approved) to episodic memory with
  `importance: 8`.
- If anything went wrong, run the debug-investigator loop and update
  this checklist with the new step that would have caught it.

## Self-rewrite hook
After any rollback, this checklist is missing a step. Add it.

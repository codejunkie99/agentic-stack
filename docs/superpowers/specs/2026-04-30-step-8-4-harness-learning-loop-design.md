# Step 8.4 — Harness Learning Loop Design

**Branch:** `feature/step-8.4-harness-learning-loop`
**Date:** 2026-04-30
**Status:** Design approved; awaiting plan-write.

## Problem statement

Step 8.3's real-case dry-run (HarnessX engagement) surfaced 3 gaps + 2 architectural pieces all answering one shape of question — *"how do we know the harness is working, and how do lessons graduate from a target install back to the fork?"*

Specifically:
- `propose_harness_fix.py` exists but agents don't know to invoke it (`HARNESS_FEEDBACK.md` empty after 130 episodes despite multiple frictions surfaced).
- `auto_dream.py` clusters tool-write events on long content sessions; 13 candidates after Phase 2 were all file-write claims, none lesson-shaped.
- No tool exists to promote target-side lessons + DECISIONS up to the fork (Phase K explicitly deferred this work to Step 8.4).
- No tool exists to verify a target install's BEHAVIOR matches intended primitive use (Phase 8.3 missed this for an entire engagement).
- Step 8.3's audit revealed silent drift between intended and actual behavior of harness primitives — and the same drift recurred during this very brainstorm. We keep skipping canonical-evidence consultation when designing harness changes.

## Solution shape

Two loops, not one. **Loop A** (capture → clean → propagate) is the harness-learning pipeline. **Loop B** (verify) catches behavioral drift in installed targets. Both ride on top of a new **discipline gate** (Step 8.4.5) that enforces canonical-evidence citation before harness-territory work.

## Sequence (6 commits, in shipping order)

1. **Step 8.4.5** — canonical-evidence gate (4-layer hook system + tool)
2. **Gap 11/N5** — capture wiring
3. **Gap 9** — auto_dream noise filter
4. **Phase H** — `harness-graduate.py` (cross-install promotion)
5. **Phase O** — `harness_intent_audit.py` (target-side behavioral verify)
6. **Gap 10** — Phase 1.5 gate in `consulting-deck-builder` (one-time hand-code, path α)

Step 8.4.5 ships first so all subsequent commits land under the new discipline.

## Out of scope

- **Step 8.5** (`install.sh --upgrade`): fork → target propagation. Phase H is target → fork (UP); 8.5 is the DOWN direction.
- **Custom build-a-new-agent-team skill**: no agent-creation work in this branch.
- **Auto-detector for harness friction patterns**: rejected as over-correction; canonical posture is *"hooks for mechanical signals, agent-prompted reflection for judgment signals"* (article lines 169-204 vs 746-768). Gap 11 falls under judgment.

---

## Commit 1 — Step 8.4.5 — canonical-evidence gate

### Why first

Discipline-first. Sections 1, 2, 3 of this brainstorm each had to be revised after canonical re-checks revealed silent drift. Without a gate, the same drift will hit Sections 4-6 and beyond.

### Architecture (4 layers)

| Layer | Trigger | Mechanism | Enforcement |
|---|---|---|---|
| 1 | User prompt mentions harness/agentic-stack keywords | `UserPromptSubmit` hook injects citation reminder + writes `.harness-mode.json` flag | Soft (context inject) |
| 2 | Edit/Write to harness-territory path | `PreToolUse` hook checks for fresh `.canonical-citation.json` (TTL 30 min) | **Hard fail** |
| 3 | Citation mechanism | `cite_canonical.py` tool: `--source --reference --quote --justification` required | Provides the satisfaction gesture |
| 4 | Assistant turn end while `.harness-mode.json` flag active | `Stop` hook scans response text for `**Evidence:**` block | **Hard fail** |

### Layer 1 — `canonical_gate_prompt.py` (UserPromptSubmit)

**File:** `.agent/harness/canonical_gate_prompt.py`

**Behavior:** reads `.agent/protocols/harness-territory-keywords.txt`, regex-matches against the user prompt body. If any match:
1. Write `.agent/memory/working/.harness-mode.json` with `{ts, matched_keywords, prompt_hash}`
2. Inject system message: `"This message touches harness-primitive territory. Before proposing OR actioning, run python .agent/tools/cite_canonical.py with --source --reference --quote --justification. See .agent/protocols/canonical-sources.md 5-step. Layer 2 will block harness-territory file writes without a fresh citation; Layer 4 will block your turn-end without an Evidence block in the response."`

**Keyword list** (`harness-territory-keywords.txt`, regex one-per-line):
```
\bskill\b
\bprotocol\b
\bharness\b
\bprimitive\b
\bagent prompt\b
\bworkflow\b
\bsalience\b
\bdream\b
\bmemory layer\b
propose_harness_fix
graduate\.py
conductor\.py
hook
\.agent/
adapters/.*/agents/
adapters/.*/skills/
harness_manager/
```

If no match: do nothing (don't write the flag file). If flag file exists from a prior message but current message doesn't match: clear it.

### Layer 2 — `canonical_gate_write.py` (PreToolUse)

**File:** `.agent/harness/canonical_gate_write.py`

**Matcher:** `Edit|Write|MultiEdit`

**Behavior:**
1. Read tool call's `file_path` argument
2. Load `.agent/protocols/harness-territory-paths.json` glob list
3. If no glob matches: `{ "decision": "allow" }` — exit
4. If match: check `.agent/memory/working/.canonical-citation.json` exists AND mtime within last 30 min
5. If missing/stale: return `{ "decision": "block", "reason": "harness-primitive write to <path> blocked. Cite canonical evidence first via: python .agent/tools/cite_canonical.py --source <article|upstream|gstack|gbrain|fork-decisions|none-applies> --reference <line/path/sha> --quote <verbatim> --justification <text>. See .agent/protocols/canonical-sources.md." }`
6. If valid: `{ "decision": "allow" }`

**Glob list** (`harness-territory-paths.json`):
```json
{
  "globs": [
    ".agent/skills/**",
    ".agent/protocols/**",
    ".agent/harness/**",
    ".agent/AGENTS.md",
    ".agent/memory/semantic/**",
    "adapters/*/agents/**",
    "adapters/*/skills/**",
    "adapters/*/commands/**",
    "harness_manager/**",
    ".claude/agents/**",
    ".claude/settings.json",
    "CLAUDE.md",
    "adapters/claude-code/CLAUDE.md"
  ]
}
```

### Layer 3 — `cite_canonical.py` (tool)

**File:** `.agent/tools/cite_canonical.py`

**CLI:**
```bash
python .agent/tools/cite_canonical.py \
    --source <article|upstream|gstack|gbrain|fork-decisions|none-applies> \
    --reference <line N or commit SHA or file path> \
    --quote "<verbatim ~30-word quote>" \
    --justification "<1-3 sentences>" \
    [--topic <free-text describing what's being designed>]
```

**Validation:**
- `--source=none-applies`: `--reference` and `--quote` may be empty; `--justification` must be ≥40 chars and start with "canonical-uncovered because:" or "fork-extension because:"
- All other sources: `--reference` and `--quote` required and non-empty.
- For `--source=article`: validate `--reference` is parseable as `line N` or range `line N-M`. Cross-check that the quote appears in `examples/agentic-stack-resource/agentic-stack-source-article.md` near the cited line(s) (substring match, case-insensitive, whitespace-flexible). If absent: error.
- For `--source=upstream`: `--reference` must be a path; tool runs `git show upstream/master:<path>` and substring-checks the quote. If absent: error.
- For `--source=fork-decisions`: substring-check against `.agent/memory/semantic/DECISIONS.md`.

**Output:** writes `.agent/memory/working/.canonical-citation.json`:
```json
{
  "topic": "...",
  "source": "...",
  "reference": "...",
  "quote": "...",
  "justification": "...",
  "timestamp": "ISO-8601",
  "branch": "...",
  "ttl_minutes": 30
}
```

Prints `ok: citation recorded; harness-territory writes allowed for next 30 min.`

### Layer 4 — `canonical_gate_stop.py` (Stop)

**File:** `.agent/harness/canonical_gate_stop.py`

**Behavior:**
1. Check `.agent/memory/working/.harness-mode.json` exists. If not: `{ "decision": "allow" }` — exit.
2. Read assistant's response text from hook's transcript payload.
3. Regex-check for the structured block:
```
**Evidence:**
- (?:\*\*)?source(?:\*\*)?:\s*(article|upstream|gstack|gbrain|fork-decisions|none-applies)
- (?:\*\*)?reference(?:\*\*)?:\s*.+
- (?:\*\*)?quote(?:\*\*)?:\s*.+   # required unless source=none-applies
- (?:\*\*)?justification(?:\*\*)?:\s*.+
```
4. If missing/malformed: `{ "decision": "block", "reason": "Response touches harness territory but contains no valid Evidence block. Append the structured block: **Evidence:** with source, reference, quote (unless source=none-applies), justification. See .agent/protocols/canonical-sources.md." }`
5. If valid: `{ "decision": "allow" }`

### Settings wiring

**File:** `.claude/settings.json` (project-scoped, written by install.py for each install)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "command": "python .agent/harness/canonical_gate_prompt.py" }
    ],
    "PreToolUse": [
      { "matcher": "Edit|Write|MultiEdit",
        "command": "python .agent/harness/canonical_gate_write.py" }
    ],
    "Stop": [
      { "command": "python .agent/harness/canonical_gate_stop.py" }
    ]
  }
}
```

(Existing ztk hook at user-global `~/.claude/settings.json` `PreToolUse[matcher=Bash]` — different matcher, no conflict.)

### Tests

- `tests/test_canonical_gate_prompt.py`: keyword match, flag write, prompt without keywords clears flag.
- `tests/test_canonical_gate_write.py`: harness-path matched / unmatched; fresh / stale / missing citation file; correct allow/block decisions.
- `tests/test_cite_canonical.py`: each source type validates reference + quote correctly; none-applies justification format check; quote-substring verification works.
- `tests/test_canonical_gate_stop.py`: harness-mode active + valid block = allow; harness-mode active + missing block = block; no harness-mode = allow.

### Files

```
.agent/harness/canonical_gate_prompt.py        (new)
.agent/harness/canonical_gate_write.py         (new)
.agent/harness/canonical_gate_stop.py          (new)
.agent/tools/cite_canonical.py                 (new)
.agent/protocols/harness-territory-keywords.txt (new)
.agent/protocols/harness-territory-paths.json  (new)
.claude/settings.json                          (modified — add hook entries)
adapters/claude-code/settings.json             (modified — install template)
.gitignore                                     (modified — exclude .canonical-citation.json, .harness-mode.json)
tests/test_canonical_gate_prompt.py            (new)
tests/test_canonical_gate_write.py             (new)
tests/test_canonical_gate_stop.py              (new)
tests/test_cite_canonical.py                   (new)
.agent/memory/semantic/DECISIONS.md            (append: Step 8.4.5 entry)
```

### Risk + mitigation

| Risk | Mitigation |
|---|---|
| False positives from broad keyword list flood agent with citation prompts | Keyword list reviewable in `.agent/protocols/`; tune via observed false-positive rate over week 1 |
| Agent fakes citations to satisfy gate | `--quote` requires verbatim text; tool cross-checks against actual source file; faking detectable in conformance audit |
| Hook scripts themselves are harness primitives — recursion at design time | Bootstrapping problem: design + commit hook BEFORE writing the citation file. Document as `--source=none-applies, fork-extension because: bootstrapping the gate itself` |
| Stop hook blocks legitimate non-harness responses if flag stuck | UserPromptSubmit clears flag on non-matching messages; flag has implicit TTL via per-prompt rewrite |
| Hooks fail to load (config error, script crash) | Hooks must fail-OPEN by default (allow) to prevent lockout; log error to `.agent/memory/working/.hook-errors.log` |

---

## Commit 2 — Gap 11/N5 — capture wiring

### Behavior

Three sub-parts (A/B/C) operating at three layers — operational contract, runtime observability, skill template.

### Part A — trigger list in CLAUDE.md

Replace the "Proposing a harness fix from inside an install" section in `adapters/claude-code/CLAUDE.md` (currently lines 76-91) with an expanded version that adds explicit triggers:

```markdown
## Proposing a harness fix from inside an install

If you encounter a bug in a harness-territory file (CLAUDE.md,
`.claude/agents/*`, `.agent/harness/*`, `.agent/protocols/*`,
`.agent/AGENTS.md`, `.claude/settings.json`), do **not** edit it
— those paths are write-protected. Capture the proposal:

```bash
python3 .agent/tools/propose_harness_fix.py --target <path> \
    --reason "<one or two sentences>" \
    --change "<concrete proposed change>" --severity 7
```

**When to invoke** (any of these, even if uncertain):
- A skill is missing a step, or its phase order is wrong
- A workflow audit fires too late (after damage was done)
- An agent prompt didn't dispatch the right team / didn't recognize the right skill
- You hit the same friction pattern twice in one session
- Per-agent memory is sparse (`.claude/agent-memory/<agent>/` empty after multi-turn agent dispatch)
- A protocol contradicts observed behavior, or is silent on a case that surfaced

Capture is cheap; not capturing means the fork can't learn. Err toward
more invocations, not fewer.

Proposal lands in `.agent/memory/working/HARNESS_FEEDBACK.md`. Keep
working; the proposal is graduated to the fork in a separate ritual
(see `harness-graduate.py`). Same mechanism for
`skill_evolution_mode: "propose_only"`.
```

### Part B — observability hook (mechanical signal only)

**File:** `.agent/harness/check_friction_capture.py`

Hook fires on `SessionEnd`. Reads:
- `.agent/memory/working/HARNESS_FEEDBACK.md` line count at session start (from `.agent/memory/working/.session-state.json` written by SessionStart hook) and current
- Episodic AGENT_LEARNINGS.jsonl tool-call count for current session

If `tool_calls > 30` AND `feedback_delta == 0`: emit console warning:
```
⚠ harness-friction check: this session ran <N> tool calls and captured 0
  harness fixes. If that's right, ignore. If not, run propose_harness_fix.py
  before starting your next session.
```

This is observability only — SessionEnd fires after agent stops, so the message goes to the operator console, not the agent. Operator decides whether to start a new session and capture missed feedback.

**Settings wiring:** add SessionStart + SessionEnd hooks to `.claude/settings.json`.

### Part C — universal self-rewrite hook template addition

**File:** `.agent/skills/_template/SELF_REWRITE_HOOK.md` (or wherever the canonical template lives — verify location during plan-write)

Add one bullet to the existing template's step list:

```markdown
6. If a harness-shape friction pattern was encountered (skill missing a
   step, workflow timing wrong, agent dispatched mismatch, agent-memory
   sparse), invoke `python .agent/tools/propose_harness_fix.py` ONCE per
   pattern before signing off this skill. Triggers: see
   `adapters/claude-code/CLAUDE.md` "When to invoke" list.
```

This propagates the trigger to every skill's reflection cycle automatically — convention-based, exactly the canonical compounding pattern (article lines 762-768).

### Tests

- `tests/test_check_friction_capture.py`: `delta=0 + tool_calls=50 → warns`; `delta=2 + tool_calls=50 → silent`; `delta=0 + tool_calls=10 → silent`; `delta=0 + no session-state file → silent (first run)`.
- Manual smoke: run an empty session, observe warning fires.
- Skill linter regression test: ensure adding the new template line doesn't break existing skill-conformance check.

### Files

```
adapters/claude-code/CLAUDE.md                         (modified — Part A)
.agent/harness/check_friction_capture.py               (new — Part B)
.agent/harness/init_session_state.py                   (new — SessionStart writes initial state)
.agent/skills/_template/SELF_REWRITE_HOOK.md           (modified — Part C; verify path)
.claude/settings.json                                  (modified — SessionStart + SessionEnd hooks)
adapters/claude-code/settings.json                     (modified — install template)
tests/test_check_friction_capture.py                   (new)
.agent/memory/semantic/DECISIONS.md                    (append: Gap 11 entry)
```

### Evidence-block scaffold (for plan-write to reuse)

- **source:** article
- **reference:** lines 746-768 (universal self-rewrite hook template)
- **quote:** *"After every 5 uses OR on any failure: ... Check if any new patterns, recurring failures, or changed assumptions exist. If yes: ... Append new lessons to KNOWLEDGE.md ... If a constraint was violated during execution, escalate to memory/semantic/LESSONS.md."*
- **justification:** Part C extends the canonical universal self-rewrite hook with one harness-friction trigger. Part A surfaces the same trigger at the operational-contract level (where it applies cross-skill). Part B is a fork extension (mechanical signal observability) — SessionEnd warning when capture didn't happen.

---

## Commit 3 — Gap 9 — auto_dream noise filter

### Behavior

Pre-cluster collapse of file-write episodes. **Drops the originally-proposed `reflection_bonus` formula change** (canonical posture: "the simple weighted formula won" — article line 365). Phase L's importance/pain tuning of memory_reflect events is sufficient.

### Part A — `collapse_file_writes(entries)`

**File:** `.agent/memory/auto_dream.py` (inline; promote to its own file if it grows past ~50 LOC)

Runs in `run_dream_cycle()` immediately before `cluster_and_extract`:

```python
def collapse_file_writes(entries):
    """Collapse same-file Write/Edit episodes within a single session.

    Restores canonical-article prefix-grouping behavior (article lines
    469-482) that fork's Jaccard migration regressed. On long content
    sessions, 30+ Write events on the same file cluster as the dominant
    signal; collapsing them pre-cluster makes the cluster claim reflect
    insight, not file activity.

    Episodes with substantive `reflection` text are NEVER collapsed —
    those are explicit memory_reflect events.
    """
```

1. Detect via regex: `^(Wrote|Edited|Created|Updated)\s+(\S+\.\S+)` — second group must contain a dot.
2. Group by `(source.run_id, action_kind, target_path)`.
3. Skip groups containing any episode with non-empty `reflection`.
4. For groups N≥2: synthesize one representative:
   - `timestamp` = latest in group
   - `action` = `"<kind> <path> ×N in session"`
   - `detail` = `"first: <first.detail[:80]> ... last: <last.detail[:80]>"`
   - `pain_score`, `importance` = max from group
   - `recurrence_count` = N (consumed by `salience.salience_score`'s `min(recurrence, 3)` cap)
   - All other fields from latest episode.
5. Pass-through: episodes that don't match the file-write regex go through unchanged.

### Why no `reflection_bonus`

Phase L set `consulting-deck-builder` phase exits to `importance=10, pain=8` → salience 8.0. Default file-write events are `importance=5, pain=2` → salience 1.0 (or 3.0 with recurrence saturation at min(3)). Phase L reflect events already win cluster canonical races by 5× margin. Adding a `reflection_bonus` formula factor would violate canonical's *"the simple weighted formula won"* (article line 365) without measurable gain.

The compounding fix for skills that DON'T have Phase L tuning (planner, document-researcher, etc.) is to propagate Phase L's input-tuning pattern to those skills via skill self-rewrite. **Out of scope this branch** — flag as follow-up `propose_harness_fix.py` entry.

### Tests

- `tests/test_auto_dream_filter.py`:
  - Pure-tool-use group (5 Writes on same file): collapses to 1 with recurrence=5
  - Mixed group (3 Writes + 1 reflect): preserved (skipped due to reflection-presence rule)
  - Single Write: untouched
  - Edge case: `"Wrote a summary"` (no extension): doesn't match regex, untouched
  - Edge case: `"Wrote summary.md migration plan"` (file token mid-sentence): matches regex, may collapse — accept as bounded false positive
- `tests/fixtures/episodic_collapse_input.jsonl`: synthesized 130-episode HarnessX-shaped batch; integration test asserts at least one resulting candidate has reflection-shaped claim, not file-write-shaped.

### Files

```
.agent/memory/auto_dream.py                            (modified — add collapse_file_writes + call)
tests/test_auto_dream_filter.py                        (new)
tests/fixtures/episodic_collapse_input.jsonl           (new)
.agent/memory/semantic/DECISIONS.md                    (append: Gap 9 entry — labels collapse as restoration of canonical prefix-grouping)
```

### Evidence-block scaffold

- **source:** article
- **reference:** lines 469-482 (`find_recurring_patterns` canonical prefix-grouping)
- **quote:** *"def find_recurring_patterns(entries): cluster entries by skill + action pattern to detect recurrence. patterns = defaultdict(list). for e in entries: key = f'{e.get(\"skill\",\"general\")}::{e.get(\"action\",\"\")[:50]}'. patterns[key].append(e)."*
- **justification:** Part A restores canonical's auto-collapse-by-action-prefix behavior, which was lost when fork's Jaccard migration (cluster.py docstring: "Phase 3's replacement for action-prefix clustering") replaced prefix-grouping. Reintroducing the collapse pre-cluster recovers the canonical guarantee without rolling back to prefix-only clustering.

---

## Commit 4 — Phase H — `harness-graduate.py`

### Behavior

Operates from FORK side; promotes target-side lessons + DECISIONS up to fork. Interactive gate per entry, hash dedup, engagement-specificity heuristic, recommends `/regenerate-decisions` after DECISIONS append.

### CLI

```bash
python .agent/tools/harness-graduate.py <target-path> [options]
```

**Options:**
- `--dry-run` — output the diff without prompting; useful for review
- `--lessons-only` — skip DECISIONS section
- `--target-slug <slug>` — provenance label (default: basename of target-path)

### Lesson promotion flow

1. Read target's `.agent/memory/semantic/lessons.jsonl`.
2. Read fork's `.agent/memory/semantic/lessons.jsonl`.
3. Compute `pattern_id` for each (reuse `cluster.py:pattern_id`).
4. Diff: target-only lessons = present in target's set, absent from fork's.
5. For each target-only lesson:
   - Check engagement-specificity heuristic: scan lesson text for client-name patterns (any path component under `<target>/.agent/memory/client/<slug>/` mentioned). If matched: prompt is `[engagement-specific?] y/n/skip`.
   - Otherwise: prompt is `y/n/skip`.
   - On `y`: prompt for `--rationale` (required; matches `graduate.py` contract).
   - Append to fork's `lessons.jsonl` with provenance: `{..., "graduated_from": "<target-slug>", "graduated_on": "YYYY-MM-DD", "graduation_rationale": "<text>"}`.
   - Re-render fork's `LESSONS.md` from updated `lessons.jsonl` (use existing `render_lessons.render_lessons()`).
6. Print summary: `graduated N lessons (M skipped, K dedup-auto-skipped)`.

### DECISIONS promotion flow

1. Parse target's `.agent/memory/semantic/DECISIONS.md` by heading: `^## (\d{4}-\d{2}-\d{2}): (.+)$`.
2. Parse fork's similarly.
3. Diff by heading.
4. For each target-only entry:
   - Display heading + first 200 chars of body.
   - Prompt: `y/n/skip`.
   - On `y`: append entry verbatim to fork's `DECISIONS.md` with provenance line inserted after the heading: `> Graduated from <target-slug> on YYYY-MM-DD.`
5. After any DECISIONS appends:
   - Print: `RECOMMENDATION: appended N DECISIONS entries. Consider running '/regenerate-decisions' on fork to re-derive from updated LESSONS + episodic. Direct append is for high-value entries that don't need re-derivation; bulk additions warrant re-derivation.`
   - This honors canonical's DECISIONS-is-regenerated rule (article lines 145-168) by giving operator the path; doesn't force re-run.

### Anti-mistakes

- **No auto-merge:** every entry requires explicit `y` + `--rationale`.
- **Hash dedup:** if `pattern_id` collision, auto-skip with note `(dedup: pattern_id <id> already in fork)`.
- **Engagement-specificity heuristic:** flagged entries require explicit override; default-skip path available.
- **Provenance always written:** lessons.jsonl gains `graduated_from` field; DECISIONS gets blockquote line. Provenance line MUST be present — refuse to append if writing fails.
- **Atomic writes:** all-or-nothing per session; on error mid-session, roll back appends from current run.

### Tests

- `tests/test_harness_graduate.py` with fixtures:
  - Target with 4 lessons: 1 fork-dup (auto-skip), 1 engagement-specific (flagged), 1 portable (graduates), 1 portable but operator-rejected (skipped).
  - Target with 3 DECISIONS entries: 1 already in fork, 2 new.
  - `--dry-run`: produces full diff output, makes no writes.
  - `--lessons-only`: skips DECISIONS section.
  - Atomicity: simulate write failure mid-run; verify rollback.
- Smoke test: run against actual HarnessX target; verify diff output is sensible.

### Files

```
.agent/tools/harness-graduate.py                       (new)
tests/test_harness_graduate.py                         (new)
tests/fixtures/harness_graduate_target/                (new — minimal target install fixture)
.agent/memory/semantic/DECISIONS.md                    (append: Phase H entry — labels cross-install dimension as fork extension)
```

### Evidence-block scaffold

- **source:** fork-decisions
- **reference:** `.agent/memory/semantic/DECISIONS.md` 2026-04-29 Phase K entry; `.agent/tools/graduate.py:39-69` within-install contract
- **quote:** *"Cross-install graduation (lessons going UP from engagement to fork) is the deferred `harness-graduate.py` flow (Step 8.4)."*
- **justification:** Phase H is the explicitly-deferred work named in Phase K. Within-install `graduate.py` provides the contract model (interactive, --rationale, dedup). Cross-install dimension is fork extension; canonical assumes single-install. DECISIONS append path recommends `/regenerate-decisions` to honor canonical's regenerated-not-edited rule (article line 168).

---

## Commit 5 — Phase O — `harness_intent_audit.py`

### Behavior

Codifies the 18-checkpoint audit from `.agent/protocols/canonical-sources.md:75-105` as a runnable tool.

### CLI

```bash
python .agent/tools/harness_intent_audit.py <target-path> [--json|--md] [--strict]
```

**Options:**
- `--json` — output structured JSON only
- `--md` — output human-readable markdown only (default: both)
- `--strict` — promote any `WARN` to `FAIL`; useful for CI gating

**Output paths:** writes to `<target>/.agent/memory/working/intent-audit-<YYYY-MM-DD>.json` and `.md`.

**Exit codes:** `0` all PASS; `1` any FAIL; `2` any WARN with no FAIL.

### 18 checkpoints

**INSTALL STATE (5):**
1. All declared adapter files present at expected paths (cross-ref `adapter.json`).
2. `skill_linter.py` passes.
3. `harness_conformance_audit.py` passes.
4. Smoke install in `/tmp/audit-smoke-*` succeeds.
5. `install.json` present at `<target>/.agent/`.

**ENGAGEMENT-TIME BEHAVIOR (8):**
6. Episodic AGENT_LEARNINGS.jsonl non-empty.
7. WORKSPACE.md mtime within 24h of last episodic entry.
8. Per-agent memory written for each dispatched agent: cross-ref `.claude/agent-memory/<agent>/` against agent-dispatch trace from episodic.
9. Phase-exit reflections fired: grep episodic for entries with `importance >= 8` AND non-empty `reflection`.
10. Dream cycle ran: check `.agent/memory/dream.log` mtime + content.
11. Candidates lesson-shaped: sample top 3 candidates from `.agent/memory/candidates/`; FAIL if any `claim` matches `^(Wrote|Edited|Created|Updated)\s+\S+\.\S+`.
12. Semantic memory has post-install additions: compare `LESSONS.md` line count + `lessons.jsonl` entry count to install-time snapshot.
13. `HARNESS_FEEDBACK.md` non-empty if session was long: WARN if `tool_call_count > 30` AND `HARNESS_FEEDBACK.md` empty.

**DRIFT DETECTION (4):**
14. Workflow contract followed: `trace_check.py` against workflow files.
15. Skill order matches handoffs: parse skill self-rewrite hooks for declared sequence; cross-check episodic.
16. Agent file edits within `output_paths`: scan agent-dispatch traces for file-write events outside declared scope.
17. Primitives used as documented: harness_conformance_audit.py extension that checks settings.json hooks haven't drifted from canonical patterns.

**Plus 1 anchor:**
18. `intent-audit-<date>.md` itself written and committed to target's git (provenance for the audit).

### Implementation

Each checkpoint = a small function in `harness_intent_audit.py`. Heavy reuse of existing tools:
- `skill_linter.py` (#2)
- `harness_conformance_audit.py` (#3)
- `install.py` (#4 smoke)
- `trace_check.py` (#14)
- Standard file/jsonl/glob ops (others)

Output schema:
```json
{
  "target": "<path>",
  "audit_date": "YYYY-MM-DD",
  "checkpoints": [
    { "id": 1, "category": "install_state", "name": "files_present",
      "status": "PASS|FAIL|WARN|SKIP",
      "detail": "...",
      "rationale": "..."  // for SKIP/WARN/FAIL
    },
    ...
  ],
  "summary": { "pass": N, "fail": N, "warn": N, "skip": N }
}
```

### Tests

- `tests/test_harness_intent_audit.py` with fixture target installs:
  - `tests/fixtures/audit_target_passing/` — clean install, post-engagement state
  - `tests/fixtures/audit_target_install_state_fail/` — missing adapter file
  - `tests/fixtures/audit_target_behavior_fail/` — empty episodic, sparse agent-memory
  - `tests/fixtures/audit_target_drift_fail/` — workflow contract violated
- Each checkpoint has its own unit test.
- Integration test: run against HarnessX target; capture findings (informational, not asserted).

### Files

```
.agent/tools/harness_intent_audit.py                   (new)
tests/test_harness_intent_audit.py                     (new)
tests/fixtures/audit_target_*/                         (new)
.agent/memory/semantic/DECISIONS.md                    (append: Phase O entry — labels tool as fork extension; content is canonical-aligned protocol)
```

### Evidence-block scaffold

- **source:** fork-decisions
- **reference:** `.agent/protocols/canonical-sources.md:75-105` (audit checklist text); 67-71 (intended-vs-actual rationale)
- **quote:** *"After installing primitives into a target and running them, audit BEFORE declaring the work done. Don't conflate 'install state correct' with 'primitives are being used correctly.' Step 8.3 missed this for an entire engagement."*
- **justification:** Phase O codifies the existing protocol checklist as a runnable tool. Tool form is fork extension; content is canonical-aligned (the protocol itself). Reuses `skill_linter.py`, `harness_conformance_audit.py`, `trace_check.py` as building blocks.

---

## Commit 6 — Gap 10 — `consulting-deck-builder` Phase 1.5 gate (path α)

### Behavior

Add a Phase 1.5 gate to `.agent/skills/consulting-deck-builder/SKILL.md` between Phase 1 (Storyboard) and Phase 2 (Content). After storyboard v1 draft, before Phase 2 entry, run an 8-section coverage check against the source workflow file.

### Why hand-coded

Path α (decided in brainstorm): hand-code now; document the canonical-aligned future path in DECISIONS.md.

Phase O (Commit 5) is designed to surface this kind of finding via checkpoint #14 (workflow contract followed). Future similar fixes should graduate via Phase O finding → `propose_harness_fix.py` → skill update — which IS the canonical compounding pattern (article line 762: "skill-update: {skill_name}, {one-line reason}").

But Phase O can only surface findings from a NEW engagement run, and there isn't one in this branch. Re-discovering Gap 10 on the next engagement just to feed it back through the loop is wasteful when the fix is already validated. DECISIONS entry handles canonical-discipline aspect.

### Skill change

Insert between Phase 1 exit and Phase 2 entry:

```markdown
## Phase 1.5 — Workflow contract reconciliation gate

Before Phase 2 entry, run an 8-section coverage check against the source
workflow file (e.g., `.agent/workflows/final-recommendations-deck.md` for
recommendation decks; pick the workflow that seeded the engagement).

Each missing or mis-framed section is a v1→v2 fix surfaced *before* the
storyboard is signed off — not after.

For each of the 8 sections (situation, complication, question, value-gap,
options, recommendation, risks, investment+next-steps):
1. Does the storyboard v1 cover this section?
2. Is it framed correctly (action-voice, value-explicit, From-To where
   applicable)?
3. If missing or mis-framed: revise storyboard v1 → v2 BEFORE Phase 2 entry.

Stops, asks: present 8-section reconciliation report to user; await
explicit y on each gap before proceeding.
```

### Skill version + manifest

- Bump `_template/SKILL.md`-style version frontmatter (`version: 2026-04-30`).
- Update `.agent/skills/_manifest.jsonl` entry for `consulting-deck-builder`.
- Skill linter regression test: ensure conformance check still passes.

### Files

```
.agent/skills/consulting-deck-builder/SKILL.md         (modified — Phase 1.5 added)
.agent/skills/_manifest.jsonl                          (modified — version bump)
.agent/memory/semantic/DECISIONS.md                    (append: Gap 10 entry — labels as one-time hand-code; documents future Phase O graduation path)
```

### Evidence-block scaffold

- **source:** fork-decisions
- **reference:** `.agent/memory/semantic/DECISIONS.md` 2026-04-29 Step 8.3 Phase 2 dry-run outcome entry (Gap 10 root cause); `docs/superpowers/plans/2026-04-27-step-8-3-gap-log.md` Gap 10 section
- **quote:** *"Gap 10 — Workflow audit ran after storyboard v2, not mid-storyboard ... Framework-lead's 8-section coverage audit fired *after* storyboard v2 was complete and identified 3 critical gaps ... v3 then required 6 structural moves to reconcile against the workflow contract. Each move had downstream consequences ..."*
- **justification:** Hand-coded fix lands the validated 8.3 finding without waiting for re-discovery via Phase O. DECISIONS entry documents that future similar fixes route through Phase O finding → propose_harness_fix → skill update (canonical compounding pattern, article line 762).

---

## Cross-cutting concerns

### Settings.json install propagation

Step 8.4.5's hooks live in `.claude/settings.json` of each install. `install.py` already propagates `adapters/claude-code/settings.json` to `<target>/.claude/settings.json`. Adding the new hook entries there ensures fresh installs get the gate. **Existing installs (HarnessX target) need manual sync** — flag as one-time post-install action; longer-term `sync-target.sh` (Phase J, already shipped) covers settings-file sync if extended.

### Test coverage targets

- Per commit: ≥1 test file per new tool/hook; coverage on happy path + 3 edge cases minimum.
- Cross-cutting: integration test that runs the full Loop A pipeline on a fixture (capture event → dream cycle → candidate → graduate to lessons.jsonl). Lives in `tests/test_loop_a_integration.py`.

### Documentation

- DECISIONS.md gets one entry per commit (6 entries total).
- WORKSPACE.md updated at each commit's start.
- `adapters/claude-code/CLAUDE.md` modified in Commit 2 only.
- `.agent/AGENTS.md` may need a one-line reference to canonical-sources.md (verify during plan-write).

### Rollout order recap

```
8.4.5 (canonical gate)
   ↓ enables discipline for all subsequent commits
Gap 11 (capture wiring)
   ↓ activates HARNESS_FEEDBACK.md as data source
Gap 9 (auto_dream filter)
   ↓ cleans the dream-cycle output for graduation
Phase H (cross-install graduate)
   ↓ closes Loop A end-to-end
Phase O (intent audit)
   ↓ closes Loop B
Gap 10 (Phase 1.5 gate)
   → demonstrates loop completion (v1 hand-code, v2+ via Phase O graduation)
```

---

## Plan-write next step

After spec approval, invoke `superpowers:writing-plans` skill to produce `docs/superpowers/plans/2026-04-30-step-8-4-harness-learning-loop-plan.md` with:
- Per-commit task breakdown (atomic commits, TDD where applicable)
- Test-driven sequencing (red → green → refactor per commit)
- Manual smoke / verification steps before each git commit
- DECISIONS.md entry text drafted per commit
- Provenance: each commit message includes evidence-citation (matches Step 8.4.5 discipline)

---

**Evidence:**
- **source:** fork-decisions
- **reference:** `.agent/memory/semantic/DECISIONS.md` 2026-04-30 canonical-sources protocol entry (lines ~371-388); 2026-04-29 Phase K entry (lines ~268-286); 2026-04-29 Step 8.3 Phase 2 dry-run outcome (lines ~238-265)
- **quote:** *"Step 8.3's audit revealed silent drift between what we INTENDED and what was ACTUALLY happening ... The fix wasn't more code — it was reading the source article carefully and recalibrating against canonical."* — `.agent/protocols/canonical-sources.md:9-13`
- **justification:** This spec aggregates 6 commits into one branch under the canonical-sources discipline. Each commit's evidence-block scaffold cites canonical (article, fork-decisions, or none-applies-because-bootstrap) appropriate to that commit. Cross-install dimensions (Phase H, Phase O) are labeled fork extensions; primitive-tuning (Gap 9, Gap 11) is labeled canonical-aligned with explicit article citations. The 8.4.5 gate is bootstrapping fork extension (canonically uncovered: gating one's own harness evolution). The whole spec is itself a harness-territory artifact and was produced under the discipline it documents.

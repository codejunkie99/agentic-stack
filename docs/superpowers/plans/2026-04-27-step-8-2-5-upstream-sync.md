# Step 8.2.5 — Upstream Fork Sync (v0.8.0 → v0.11.2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sync the agent-stack fork from base v0.8.0 (`a397568`) to upstream v0.11.2 (`8ba0293`), preserving all Step 8.x BCG/SDLC work, and port the BCG-conditional install logic from `install.sh` (deleted upstream) into the new manifest-driven `harness_manager/` Python package.

**Architecture:** Three-way merge of `upstream/master` into `master`. Resolve four real conflicts (`install.sh`, `_index.md`, `_manifest.jsonl`, `DECISIONS.md`) and let git auto-merge two (`AGENTS.md`, `.gitignore`). Discard our 175-line bash `install.sh` in favour of upstream's 38-line Python dispatcher; port the 61-line BCG propagation block as a new named `post_install` action `bcg_conditional_propagate` in `harness_manager/post_install.py`, registered in `harness_manager/schema.py`, and wired into `adapters/claude-code/adapter.json`. 92 ours-only files (BCG adapter, generic context, personas, knowledge-work skills) remain untouched; 58 upstream-only files (harness_manager package, data-layer + data-flywheel + design-md skills, codex adapter, pi rewrite, schemas, examples, docs, hooks) merge in clean. Smoke-test both adapter states (disabled/enabled) on fresh installs as exit criteria.

**Tech Stack:** git (3-way merge), bash (smoke tests + dispatcher), Python 3 (harness_manager package), JSON (adapter manifests + schema validation).

---

## Task 1: Pre-flight verification

**Files:**
- Read: working tree state via git

- [ ] **Step 1: Verify clean working tree, on master, remotes wired**

```bash
cd /Users/talwarpulkit/code/agent-stack
git status -s
git branch --show-current
git remote -v
```

Expected:
- `git status -s` returns empty (or only `?? .claude/scheduled_tasks.json` etc, all gitignored — no `M` or `??` for tracked content)
- `git branch --show-current` returns `master`
- Remotes: `origin → pulkittalwar/agentic-stack`, `upstream → codejunkie99/agentic-stack`

If working tree is dirty: stop and resolve before proceeding. Do NOT stash — surface to user.

- [ ] **Step 2: Refresh upstream**

```bash
git fetch upstream
git log master..upstream/master --oneline | wc -l
git merge-base master upstream/master | xargs git log -1 --oneline
```

Expected: ~59 commits behind, merge base `a397568` (v0.8.0). If commit count differs significantly from 59, upstream has moved further since 2026-04-27 — that's fine, the plan still applies, but flag the count to user.

---

## Task 2: Stage 1 — Per-tag classification doc

**Files:**
- Create: `docs/superpowers/plans/2026-04-27-step-8-2-5-classification.md`

- [ ] **Step 1: Generate per-tag commit list**

```bash
cd /Users/talwarpulkit/code/agent-stack
for tag in v0.9.0 v0.9.1 v0.10.0 v0.11.0 v0.11.1 v0.11.2; do
  prev=$(git describe --tags --abbrev=0 "$tag^" 2>/dev/null || echo "a397568")
  echo "=== $tag (since $prev) ==="
  git log --oneline "$prev..$tag"
  echo ""
done > /tmp/claude/825-tag-walk.txt
cat /tmp/claude/825-tag-walk.txt
```

Expected: ~6 sections, one per tag, each listing 5-15 commits.

- [ ] **Step 2: Write classification doc**

Create `docs/superpowers/plans/2026-04-27-step-8-2-5-classification.md` with structure:

```markdown
# Step 8.2.5 — Per-tag Classification (v0.9.0 → v0.11.2)

Classification of each tag's changes for the upstream fork sync.
Categories: TAKE-AS-IS / TAKE-WITH-ADAPTATION / SKIP-OURS-WIN.

## v0.9.0 — harness_manager Python backend
Take-as-is. Replaces install.sh + install.ps1 with manifest-driven
Python pkg. Our BCG block (61 lines) is the only adaptation needed —
ported as a new named post_install action (see Stage 4 of plan).

Notable commits:
- de06531 feat(harness-manager): Python backend (install/doctor/remove/status/cli)
- eafba1d feat(harness-manager): adapter.json manifests for all 10 adapters
- 2bbb873 feat(harness-manager): adapter.json schema + stdlib validator
- 80a00ac feat(install.sh): refactor to thin Python dispatcher

## v0.9.1 — pi adapter rewrite + minor fixes
Take-as-is. Pi memory-hook rewrite addresses formula crash + decay tz
bug; we don't customize pi.

## v0.10.0 — data-layer + data-flywheel + DESIGN.md
Take-as-is. Three new skills (data-layer, data-flywheel, design-md),
new schemas/, examples/, top-level test files. All additive, no
collision with our knowledge-work skill imports from Step 8.1.

## v0.11.0 → v0.11.2 — data-dashboard polish
Take-as-is. Terminal dashboard shown by default (v0.11.0), natural-
language dashboard (v0.11.2), brew formula bumps. No conflicts.

## Files we kept (no upstream collision)
- adapters/bcg/* (entire BCG adapter — 16 agents, 16 memory templates,
  context, protocols, skills, scripts, commands, templates)
- .agent/context/* (4 files: README, frameworks, glossary, quality-standards)
- .agent/personas/* (4 files: README, _template, executive-sponsor, program-director)
- .agent/skills/* (13 knowledge-work + SDLC skills imported in Steps 4-8)

## Conflicts (resolved per main plan)
- install.sh: our BCG block ported to harness_manager/post_install.py
- _index.md, _manifest.jsonl: mechanical merge (disjoint skill lists)
- DECISIONS.md: ours-wins (project history)
```

- [ ] **Step 3: Commit classification doc**

```bash
git add docs/superpowers/plans/2026-04-27-step-8-2-5-classification.md \
        docs/superpowers/plans/2026-04-27-step-8-2-5-upstream-sync.md
git commit -m "$(cat <<'EOF'
docs: Step 8.2.5 implementation plan + per-tag classification

Plan for syncing fork v0.8.0 -> v0.11.2 (59 commits, 6 tags). 4 real
conflicts identified, all resolution strategies pre-decided. Single
load-bearing port: install.sh BCG block -> harness_manager
post_install action. Smoke-test exit criteria for both adapter states.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Stage 2 — Initiate the merge

**Files:**
- Modify: working tree (introduces conflict markers in 4 files)

- [ ] **Step 1: Start the merge with no-commit, no-fast-forward**

```bash
cd /Users/talwarpulkit/code/agent-stack
git merge --no-commit --no-ff upstream/master
```

Expected output (paraphrased):
```
Auto-merging .agent/AGENTS.md
Auto-merging .agent/memory/semantic/DECISIONS.md
CONFLICT (content): Merge conflict in .agent/memory/semantic/DECISIONS.md
Auto-merging .agent/skills/_index.md
CONFLICT (content): Merge conflict in .agent/skills/_index.md
Auto-merging .agent/skills/_manifest.jsonl
CONFLICT (content): Merge conflict in .agent/skills/_manifest.jsonl
Auto-merging .gitignore
Auto-merging install.sh
CONFLICT (content): Merge conflict in install.sh
Automatic merge of [...] failed; fix conflicts and then commit the result.
```

If the conflict file list differs from these 4 — STOP. Re-run `git merge-tree` analysis, surface to user. Do NOT proceed with stale assumptions.

- [ ] **Step 2: Confirm conflict list**

```bash
git diff --name-only --diff-filter=U
```

Expected exact output:
```
.agent/memory/semantic/DECISIONS.md
.agent/skills/_index.md
.agent/skills/_manifest.jsonl
install.sh
```

---

## Task 4: Stage 3a — Resolve `.agent/skills/_manifest.jsonl`

**Files:**
- Modify: `.agent/skills/_manifest.jsonl`

- [ ] **Step 1: Inspect the conflict region**

```bash
cat .agent/skills/_manifest.jsonl
```

Conflict markers will surround upstream's manifest entries (with `data-flywheel`, `data-layer`, `design-md` skills) versus ours (with all 13 knowledge-work + SDLC skills). The two sets are disjoint by skill name — no entry collides.

- [ ] **Step 2: Build merged manifest**

The resolution rule: take the union of both skill manifests, preserve our entries unchanged, append upstream's three new entries (`data-flywheel`, `data-layer`, `design-md`).

```bash
# Extract ours-side entries (between <<<<<<< and =======)
git show :2:.agent/skills/_manifest.jsonl > /tmp/claude/manifest-ours.jsonl
# Extract theirs-side entries (between ======= and >>>>>>>)
git show :3:.agent/skills/_manifest.jsonl > /tmp/claude/manifest-theirs.jsonl
diff /tmp/claude/manifest-ours.jsonl /tmp/claude/manifest-theirs.jsonl
```

The diff shows: ours has 20 entries (all of theirs' base 8 in the merge-base PLUS the 12 we added in Step 8.1); theirs has 8 entries (the base 5 unchanged + 3 new: data-flywheel, data-layer, design-md). To merge: start from ours' 20 entries, add the 3 new ones from theirs.

```bash
# Identify the 3 new entries upstream added
comm -13 <(sort /tmp/claude/manifest-ours.jsonl) <(sort /tmp/claude/manifest-theirs.jsonl)
```

Expected: 3 lines, each a JSONL entry for `data-flywheel`, `data-layer`, `design-md`.

- [ ] **Step 3: Write the merged manifest**

```bash
cat /tmp/claude/manifest-ours.jsonl > .agent/skills/_manifest.jsonl
comm -13 <(sort /tmp/claude/manifest-ours.jsonl) <(sort /tmp/claude/manifest-theirs.jsonl) >> .agent/skills/_manifest.jsonl
# Verify no conflict markers remain
grep -E '^(<<<<<<<|=======|>>>>>>>)' .agent/skills/_manifest.jsonl
```

Expected: grep returns empty (exit code 1).

- [ ] **Step 4: Verify line count**

```bash
wc -l .agent/skills/_manifest.jsonl
```

Expected: 23 lines (20 ours + 3 theirs).

- [ ] **Step 5: Stage**

```bash
git add .agent/skills/_manifest.jsonl
```

---

## Task 5: Stage 3b — Resolve `.agent/skills/_index.md`

**Files:**
- Modify: `.agent/skills/_index.md`

- [ ] **Step 1: Inspect the conflict**

```bash
sed -n '/^<<<<<<</,/^>>>>>>>/p' .agent/skills/_index.md | head -100
```

Expected: conflict region listing skills. Same disjoint-by-name property as the manifest — ours lists all 13 knowledge-work + SDLC skills; theirs adds `data-flywheel`, `data-layer`, `design-md`.

- [ ] **Step 2: Resolve by union**

The structure is markdown with skill descriptions. Resolution: keep ours' structure intact, insert the three new skills into the correct alphabetical / categorical position. Read both versions to identify where upstream's three new skills logically belong.

```bash
git show :2:.agent/skills/_index.md > /tmp/claude/index-ours.md
git show :3:.agent/skills/_index.md > /tmp/claude/index-theirs.md
# Compare descriptions for the 3 new skills
grep -E "^### |data-flywheel|data-layer|design-md" /tmp/claude/index-theirs.md | head -30
```

Identify where to insert. The 3 new entries should land alphabetically. Use `Edit` tool to:
1. Remove all conflict markers from `.agent/skills/_index.md`
2. Keep ours' content intact
3. Insert each of the 3 new entries (`data-flywheel`, `data-layer`, `design-md`) at its correct alphabetical position

- [ ] **Step 3: Verify**

```bash
grep -E '^(<<<<<<<|=======|>>>>>>>)' .agent/skills/_index.md
grep -c "^### " .agent/skills/_index.md
```

Expected: no conflict markers, skill count = (ours' skill count + 3).

- [ ] **Step 4: Stage**

```bash
git add .agent/skills/_index.md
```

---

## Task 6: Stage 3c — Resolve `.agent/memory/semantic/DECISIONS.md`

**Files:**
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Resolve as ours-wins**

`DECISIONS.md` is the project's append-only decision log. Our 8.x entries are the canonical project history. Upstream's edits are downstream-of-fork additions to a file we own. Take ours unconditionally.

```bash
git checkout --ours .agent/memory/semantic/DECISIONS.md
grep -E '^(<<<<<<<|=======|>>>>>>>)' .agent/memory/semantic/DECISIONS.md
```

Expected: grep returns empty.

- [ ] **Step 2: Stage**

```bash
git add .agent/memory/semantic/DECISIONS.md
```

---

## Task 7: Stage 3d — Resolve `install.sh` (take upstream's dispatcher)

**Files:**
- Modify: `install.sh`

- [ ] **Step 1: Take upstream's version**

Our 175-line bash with the BCG-conditional propagation block goes away. The BCG logic will be ported to `harness_manager/post_install.py` in Tasks 9-14. Upstream's 38-line Python dispatcher is the new install.sh.

```bash
git checkout --theirs install.sh
wc -l install.sh
grep -E '^(<<<<<<<|=======|>>>>>>>)' install.sh
```

Expected: 38 lines, no conflict markers.

- [ ] **Step 2: Verify upstream dispatcher content**

```bash
head -40 install.sh | tail -10
```

Expected last lines: `exec python3 -m harness_manager.cli "$@"`. If different, STOP — upstream may have changed the dispatcher beyond what we analyzed at 2026-04-27.

- [ ] **Step 3: Stage**

```bash
git add install.sh
```

---

## Task 8: Stage 3e — Verify auto-merged files + spot-check

**Files:**
- Read: `.agent/AGENTS.md`, `.gitignore`, `adapters/pi/`, `adapters/claude-code/adapter.json`, `harness_manager/`

- [ ] **Step 1: Confirm no remaining conflicts**

```bash
git diff --name-only --diff-filter=U
```

Expected: empty.

- [ ] **Step 2: Spot-check `.agent/AGENTS.md` and `.gitignore` auto-merges**

```bash
grep -E '^(<<<<<<<|=======|>>>>>>>)' .agent/AGENTS.md .gitignore
git diff HEAD .agent/AGENTS.md .gitignore | head -30
```

Expected: no conflict markers; diffs show clean union of both sides' edits.

- [ ] **Step 3: Spot-check upstream-only adapter changes landed**

```bash
ls adapters/pi/                          # expect: AGENTS.md, README.md, adapter.json, memory-hook.ts
ls adapters/codex/                       # expect: AGENTS.md, README.md, adapter.json (new adapter)
ls harness_manager/ | head              # expect: __init__.py, cli.py, doctor.py, install.py, ...
cat adapters/claude-code/adapter.json    # expect upstream's manifest (no post_install yet)
```

Expected: all upstream-only files are present in the working tree.

- [ ] **Step 4: Spot-check upstream hook scripts landed**

```bash
ls .agent/harness/hooks/                 # expect: _episodic_io.py, on_failure.py, pi_post_tool.py, post_execution.py
git diff HEAD .agent/memory/auto_dream.py | head -20
```

Expected: new hooks present, modified memory scripts show upstream's changes.

---

## Task 9: Stage 4 — Complete the merge commit (BCG propagation broken; restored next)

**Files:**
- Commit: merge

- [ ] **Step 1: Commit the merge**

The merge commit captures all conflict resolutions and absorbs upstream history. BCG conditional propagation is BROKEN at this commit — the bash block was deleted and the harness_manager port hasn't landed yet. Tasks 10-14 land that port immediately.

Do NOT push yet. The two commits (merge + port) ship together.

```bash
git commit --no-edit -m "$(cat <<'EOF'
merge: sync fork to upstream codejunkie99/agentic-stack v0.11.2 — Step 8.2.5

Three-way merge of upstream/master (v0.8.0 .. v0.11.2). Conflicts:
- install.sh: took upstream (38-line Python dispatcher); BCG block to
  be re-introduced as post_install action in next commit
- .agent/skills/_index.md, _manifest.jsonl: union merge — ours' 13
  knowledge-work + SDLC skills + theirs' 3 new (data-flywheel,
  data-layer, design-md)
- .agent/memory/semantic/DECISIONS.md: took ours (project history)

Auto-merged: .agent/AGENTS.md, .gitignore.

Gained: harness_manager/ Python pkg, codex adapter, pi rewrite, data-
layer + data-flywheel + design-md skills, schemas, examples, docs,
new hooks (_episodic_io.py, pi_post_tool.py).

Kept untouched (92 ours-only files): all of adapters/bcg/,
.agent/context/, .agent/personas/, all 13 knowledge-work + SDLC
skill dirs, BCG agent-memory templates.

NOTE: BCG conditional propagation is broken at this commit. Restored
in the immediately-following commit by porting the bash block to a
new named post_install action.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
git log -1 --stat | head -20
```

Expected: merge commit landed with 2 parents (master + upstream/master).

---

## Task 10: Stage 4a — Write smoke test for BCG conditional propagation (RED)

**Files:**
- Create: `tests/test_bcg_conditional_propagate.py`

- [ ] **Step 1: Write the failing smoke test**

Upstream untracked `tests/` (commit `f1c362d`). We re-add it for our test. The test exercises the post_install action end-to-end against a fresh target install.

```bash
mkdir -p tests
```

Create `tests/test_bcg_conditional_propagate.py`:

```python
"""Smoke test for bcg_conditional_propagate post-install action.

Verifies that when source `.agent/config.json` has `bcg_adapter:
"enabled"`, a fresh install of the claude-code adapter propagates:
- 16 BCG consulting agents from adapters/bcg/agents/ -> target/.claude/agents/
- 1 BCG slash command from adapters/bcg/commands/ -> target/.claude/commands/
- 16 BCG agent-memory stubs from adapters/bcg/agent-memory-templates/
  -> target/.claude/agent-memory/ (copy-if-missing)

When `bcg_adapter: "disabled"` (default), none of the above propagate.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

STACK_ROOT = Path(__file__).resolve().parent.parent


def _run_install(target: Path, adapter: str = "claude-code") -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "harness_manager.cli", "install", adapter, str(target), "--yes"],
        cwd=str(STACK_ROOT),
        env={"PYTHONPATH": str(STACK_ROOT), "PATH": "/usr/bin:/bin:/usr/local/bin"},
        capture_output=True,
        text=True,
        check=False,
    )


def _set_config(value: str) -> None:
    """Temporarily set bcg_adapter flag on source .agent/config.json."""
    cfg_path = STACK_ROOT / ".agent" / "config.json"
    cfg = json.loads(cfg_path.read_text())
    cfg["bcg_adapter"] = value
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n")


def test_bcg_propagation_when_enabled():
    original_cfg = (STACK_ROOT / ".agent" / "config.json").read_text()
    try:
        _set_config("enabled")
        with tempfile.TemporaryDirectory(prefix="825-bcg-enabled-") as tmp:
            target = Path(tmp)
            result = _run_install(target)
            assert result.returncode == 0, f"install failed: {result.stderr}"

            agents_dir = target / ".claude" / "agents"
            commands_dir = target / ".claude" / "commands"
            memory_dir = target / ".claude" / "agent-memory"

            assert agents_dir.is_dir(), "no .claude/agents/ created"
            agent_count = len(list(agents_dir.glob("*.md")))
            assert agent_count >= 21, (
                f"expected 5 SDLC + 16 BCG = 21 agents, got {agent_count}"
            )

            bcg_agent = agents_dir / "partner-strategy.md"
            assert bcg_agent.is_file(), "partner-strategy.md (BCG) missing"

            assert commands_dir.is_dir(), "no .claude/commands/ created"
            assert (commands_dir / "sync-harness.md").is_file(), \
                "sync-harness.md (BCG slash command) missing"

            assert memory_dir.is_dir(), "no .claude/agent-memory/ created"
            memory_count = len(list(memory_dir.glob("*.md")))
            assert memory_count == 16, (
                f"expected 16 BCG agent-memory stubs, got {memory_count}"
            )
    finally:
        (STACK_ROOT / ".agent" / "config.json").write_text(original_cfg)


def test_no_bcg_propagation_when_disabled():
    original_cfg = (STACK_ROOT / ".agent" / "config.json").read_text()
    try:
        _set_config("disabled")
        with tempfile.TemporaryDirectory(prefix="825-bcg-disabled-") as tmp:
            target = Path(tmp)
            result = _run_install(target)
            assert result.returncode == 0, f"install failed: {result.stderr}"

            agents_dir = target / ".claude" / "agents"
            assert agents_dir.is_dir(), "no .claude/agents/ created"
            agent_count = len(list(agents_dir.glob("*.md")))
            assert agent_count == 5, (
                f"expected exactly 5 SDLC agents (no BCG), got {agent_count}"
            )

            commands_dir = target / ".claude" / "commands"
            assert not commands_dir.exists() or not list(commands_dir.glob("*.md")), \
                "BCG commands should not propagate when adapter disabled"

            memory_dir = target / ".claude" / "agent-memory"
            assert not memory_dir.exists() or not list(memory_dir.glob("*.md")), \
                "BCG agent-memory should not propagate when adapter disabled"
    finally:
        (STACK_ROOT / ".agent" / "config.json").write_text(original_cfg)


if __name__ == "__main__":
    test_bcg_propagation_when_enabled()
    print("PASS: bcg propagation when enabled")
    test_no_bcg_propagation_when_disabled()
    print("PASS: no bcg propagation when disabled")
```

- [ ] **Step 2: Run test, verify it fails (RED)**

```bash
cd /Users/talwarpulkit/code/agent-stack
python3 tests/test_bcg_conditional_propagate.py
```

Expected: FAIL with one of:
- `AssertionError: expected 5 SDLC + 16 BCG = 21 agents, got 5` (because no BCG propagation logic exists yet)
- Or assertion on `partner-strategy.md missing`
- Or `sync-harness.md missing`

If the test PASSES at this stage, STOP — the existing code already does the right thing (which would be unexpected); investigate.

---

## Task 11: Stage 4b — Add `bcg_conditional_propagate` to schema (still RED)

**Files:**
- Modify: `harness_manager/schema.py`

- [ ] **Step 1: Find VALID_POST_INSTALL_ACTIONS**

```bash
grep -n "VALID_POST_INSTALL_ACTIONS" harness_manager/schema.py
```

Expected: one definition line (a `set` literal containing `"openclaw_register_workspace"`).

- [ ] **Step 2: Add the new action name**

Use Edit tool:

Old:
```python
VALID_POST_INSTALL_ACTIONS = {"openclaw_register_workspace"}
```

New:
```python
VALID_POST_INSTALL_ACTIONS = {"openclaw_register_workspace", "bcg_conditional_propagate"}
```

- [ ] **Step 3: Verify schema accepts the new name**

```bash
python3 -c "from harness_manager.schema import VALID_POST_INSTALL_ACTIONS; assert 'bcg_conditional_propagate' in VALID_POST_INSTALL_ACTIONS; print('OK')"
```

Expected: `OK`.

---

## Task 12: Stage 4c — Implement `bcg_conditional_propagate` (GREEN path)

**Files:**
- Modify: `harness_manager/post_install.py`
- Modify: `harness_manager/install.py`

- [ ] **Step 1: Add the action function to post_install.py**

Find the end of the existing action definitions (just before the `ACTIONS` registry / `run` / `reverse` definitions). Use Edit to insert two new functions:

Insert after `openclaw_unregister_workspace` (which ends around line 230 in upstream):

```python
def bcg_conditional_propagate(
    target_root: Path | str,
    *,
    stack_root: Path | str | None = None,
    **_kwargs,
) -> dict:
    """Propagate BCG-adapter content into target/.claude/ when enabled.

    Reads target_root/.agent/config.json. If "bcg_adapter" == "enabled",
    copies adapters/bcg/{agents,commands}/*.md from stack_root into
    target/.claude/{agents,commands}/, and adapters/bcg/agent-memory-
    templates/*.md into target/.claude/agent-memory/ using copy-if-
    missing semantics so re-installs preserve in-progress per-agent
    memory.

    Replaces the bash propagation loop that lived in install.sh master
    pre-Step-8.2.5; the v0.9.0 manager-pkg refactor moved install logic
    to Python and this action restores the BCG conditional that the
    bash block carried.
    """
    import json
    target_root = Path(target_root)
    if stack_root is None:
        return {
            "action": "bcg_conditional_propagate",
            "status": "no_stack_root",
            "stderr": "stack_root not passed through from harness_manager.install",
        }
    stack_root = Path(stack_root)

    config_path = target_root / ".agent" / "config.json"
    if not config_path.exists():
        return {"action": "bcg_conditional_propagate", "status": "no_config"}

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return {
            "action": "bcg_conditional_propagate",
            "status": "bad_config",
            "stderr": str(e),
        }

    if config.get("bcg_adapter") != "enabled":
        return {"action": "bcg_conditional_propagate", "status": "disabled"}

    bcg_src = stack_root / "adapters" / "bcg"
    if not bcg_src.is_dir():
        return {"action": "bcg_conditional_propagate", "status": "no_bcg_dir"}

    counts = {"agents": 0, "commands": 0, "agent_memory": 0}

    for kind in ("agents", "commands"):
        src_dir = bcg_src / kind
        if not src_dir.is_dir():
            continue
        dst = target_root / ".claude" / kind
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.glob("*.md")):
            shutil.copy2(f, dst / f.name)
            counts[kind] += 1

    src_dir = bcg_src / "agent-memory-templates"
    if src_dir.is_dir():
        dst = target_root / ".claude" / "agent-memory"
        dst.mkdir(parents=True, exist_ok=True)
        for f in sorted(src_dir.glob("*.md")):
            if f.name == "README.md":
                continue
            target_file = dst / f.name
            if not target_file.exists():
                shutil.copy2(f, target_file)
                counts["agent_memory"] += 1

    return {
        "action": "bcg_conditional_propagate",
        "status": "ok",
        "counts": counts,
    }


def bcg_conditional_unpropagate(
    target_root: Path | str,
    *,
    stack_root: Path | str | None = None,
    **_kwargs,
) -> dict:
    """Reverse of bcg_conditional_propagate.

    On adapter `remove`, deletes the BCG agents and commands we
    installed (matched by filename against the source stack). Agent-
    memory files are preserved — those become user data once seeded.
    """
    target_root = Path(target_root)
    if stack_root is None:
        return {"action": "bcg_conditional_propagate", "status": "no_stack_root"}
    stack_root = Path(stack_root)

    bcg_src = stack_root / "adapters" / "bcg"
    if not bcg_src.is_dir():
        return {"action": "bcg_conditional_propagate", "status": "no_bcg_dir"}

    removed = 0
    for kind in ("agents", "commands"):
        src_dir = bcg_src / kind
        if not src_dir.is_dir():
            continue
        dst = target_root / ".claude" / kind
        for f in sorted(src_dir.glob("*.md")):
            target_file = dst / f.name
            if target_file.exists():
                target_file.unlink()
                removed += 1

    return {"action": "bcg_conditional_propagate", "status": "ok", "removed": removed}
```

- [ ] **Step 2: Register both functions in the ACTIONS dict**

Find the `ACTIONS` registry. Use Edit:

Old:
```python
ACTIONS = {
    "openclaw_register_workspace": (openclaw_register_workspace, openclaw_unregister_workspace),
}
```

New:
```python
ACTIONS = {
    "openclaw_register_workspace": (openclaw_register_workspace, openclaw_unregister_workspace),
    "bcg_conditional_propagate": (bcg_conditional_propagate, bcg_conditional_unpropagate),
}
```

If the exact `ACTIONS` literal in upstream differs (e.g. multi-line indent), preserve the existing style and just append the new key.

- [ ] **Step 3: Pass `stack_root` from install.py to post_install.run()**

```bash
grep -n "post_install_mod.run" harness_manager/install.py
```

Expected: a single line, around line 301: `result = post_install_mod.run(action_name, target_root)`.

Use Edit:

Old:
```python
        result = post_install_mod.run(action_name, target_root)
```

New:
```python
        result = post_install_mod.run(action_name, target_root, stack_root=stack_root)
```

If the same install.py also calls `post_install_mod.reverse(...)` (in the `remove` flow), apply the same kwarg there too:

```bash
grep -n "post_install_mod.reverse" harness_manager/*.py
```

If found in `remove.py` or elsewhere, edit similarly: add `stack_root=stack_root` kwarg. The `stack_root` variable should already be in scope wherever `post_install_mod` is called from.

---

## Task 13: Stage 4d — Wire `claude-code` adapter manifest

**Files:**
- Modify: `adapters/claude-code/adapter.json`

- [ ] **Step 1: Add the post_install action**

Use Edit. The current manifest has no `post_install` field.

Old:
```json
{
  "name": "claude-code",
  "description": "Claude Code (Anthropic) — CLAUDE.md instructions + .claude/settings.json PostToolUse + Stop hooks. Hook commands use $CLAUDE_PROJECT_DIR for cwd-stable resolution (closes #18).",
  "brain_root_primitive": "$CLAUDE_PROJECT_DIR",
  "files": [
    {
      "src": "CLAUDE.md",
      "dst": "CLAUDE.md",
      "merge_policy": "overwrite"
    },
    {
      "src": "settings.json",
      "dst": ".claude/settings.json",
      "merge_policy": "overwrite",
      "substitute": true
    }
  ]
}
```

New (add `post_install` array as the last field):
```json
{
  "name": "claude-code",
  "description": "Claude Code (Anthropic) — CLAUDE.md instructions + .claude/settings.json PostToolUse + Stop hooks. Hook commands use $CLAUDE_PROJECT_DIR for cwd-stable resolution (closes #18).",
  "brain_root_primitive": "$CLAUDE_PROJECT_DIR",
  "files": [
    {
      "src": "CLAUDE.md",
      "dst": "CLAUDE.md",
      "merge_policy": "overwrite"
    },
    {
      "src": "settings.json",
      "dst": ".claude/settings.json",
      "merge_policy": "overwrite",
      "substitute": true
    }
  ],
  "post_install": ["bcg_conditional_propagate"]
}
```

- [ ] **Step 2: Verify manifest validates**

```bash
python3 -c "
import json
from harness_manager import schema
m = json.loads(open('adapters/claude-code/adapter.json').read())
schema.validate_dict(m, 'adapters/claude-code/adapter.json')
print('manifest validates OK')
"
```

Expected: `manifest validates OK`. If it raises `ManifestError`, the action name doesn't match what we registered in Task 11 — recheck spelling.

---

## Task 14: Stage 4e — Run smoke test, verify GREEN, commit

**Files:**
- Run: `tests/test_bcg_conditional_propagate.py`

- [ ] **Step 1: Run the test**

```bash
cd /Users/talwarpulkit/code/agent-stack
python3 tests/test_bcg_conditional_propagate.py
```

Expected:
```
PASS: bcg propagation when enabled
PASS: no bcg propagation when disabled
```

If FAIL on the `enabled` test:
- Check that `target/.agent/config.json` got copied during install (it should — `.agent/` is copied wholesale by install.py line ~191)
- Check that `stack_root` is correctly passed through to the action (print debug from inside the function, or add a `print(f"DEBUG stack_root={stack_root}")` line)
- Check that the manifest validation passed in Task 13

If FAIL on the `disabled` test:
- The action correctly returns `{"status": "disabled"}` but agents may still be propagating from the SDLC roster — that's expected (5 SDLC agents). Verify the assertion is `== 5` not `>= 21`.

- [ ] **Step 2: Verify untouched-on-rerun (idempotence on enabled re-install)**

```bash
# Manual smoke for the agent-memory copy-if-missing semantic
TMP=$(mktemp -d -t 825-rerun-XXXXX)
python3 -c "
import json, pathlib
p = pathlib.Path('.agent/config.json')
cfg = json.loads(p.read_text())
cfg['bcg_adapter'] = 'enabled'
p.write_text(json.dumps(cfg, indent=2) + '\n')
"
python3 -m harness_manager.cli install claude-code "$TMP" --yes >/dev/null
echo "MARKER" >> "$TMP/.claude/agent-memory/analyst.md"
python3 -m harness_manager.cli install claude-code "$TMP" --yes >/dev/null
grep MARKER "$TMP/.claude/agent-memory/analyst.md"
# revert config
python3 -c "
import json, pathlib
p = pathlib.Path('.agent/config.json')
cfg = json.loads(p.read_text())
cfg['bcg_adapter'] = 'disabled'
p.write_text(json.dumps(cfg, indent=2) + '\n')
"
rm -rf "$TMP"
```

Expected: `MARKER` line is preserved across re-install (copy-if-missing semantic works).

- [ ] **Step 3: Commit the BCG port**

```bash
git add tests/test_bcg_conditional_propagate.py \
        harness_manager/schema.py \
        harness_manager/post_install.py \
        harness_manager/install.py \
        adapters/claude-code/adapter.json
git commit -m "$(cat <<'EOF'
feat: port BCG conditional propagation to harness_manager.post_install — Step 8.2.5

Restores BCG agent/command/agent-memory propagation that lived in the
deleted install.sh bash block. Implemented as a new named post_install
action `bcg_conditional_propagate`, registered in schema.py and wired
into adapters/claude-code/adapter.json.

Architecture: extends post_install.run() to pass stack_root through
kwargs so actions can read source-tree adapter content (BCG content
lives at adapters/bcg/, not in target's copied .agent/). Existing
openclaw actions absorb the new kwarg via **_kwargs without change.

Behaviour preserved from bash:
- agents/commands: overwrite-on-each-install (tracked propagation)
- agent-memory templates: copy-if-missing (preserves user-seeded data)
- README.md in agent-memory-templates excluded from propagation
- Gated on .agent/config.json `bcg_adapter` == "enabled"

Smoke-tested both adapter states; idempotent on re-install.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Stage 5a — Smoke-test full install (disabled adapter)

**Files:**
- Run: install.sh against `/tmp/claude/825-disabled/`

- [ ] **Step 1: Verify source config**

```bash
python3 -c "
import json
print(json.loads(open('.agent/config.json').read()).get('bcg_adapter'))
"
```

Expected: `disabled`. If `enabled`, revert before proceeding.

- [ ] **Step 2: Run fresh install**

```bash
rm -rf /tmp/claude/825-disabled/
mkdir -p /tmp/claude/825-disabled/
./install.sh claude-code /tmp/claude/825-disabled/ --yes
```

Expected: install completes without errors. Output mentions `+ .claude/agents/ (5 subagents)` (or similar; exact count is the SDLC roster).

- [ ] **Step 3: Verify expected outputs**

```bash
ls /tmp/claude/825-disabled/.claude/agents/ | wc -l   # expect 5 (SDLC only, no BCG)
ls /tmp/claude/825-disabled/.claude/commands/ 2>/dev/null | wc -l  # expect 0 or dir absent
ls /tmp/claude/825-disabled/.claude/agent-memory/ 2>/dev/null | wc -l  # expect 0 or dir absent
test -f /tmp/claude/825-disabled/.agent/context/frameworks.md && echo "OK: generic context loaded"
test -f /tmp/claude/825-disabled/CLAUDE.md && echo "OK: CLAUDE.md installed"
```

Expected:
- 5 SDLC agents
- 0 BCG commands / agent-memory
- Generic context (`.agent/context/frameworks.md`) present (this is part of `.agent/`, copied wholesale)
- CLAUDE.md present

If any expectation fails, STOP and investigate. Common issues:
- `harness_manager.cli install` may use a different argv shape than the bash dispatcher; check `--help`
- The `.agent/` may not be copied if install.py logic was different from what we read

---

## Task 16: Stage 5b — Smoke-test full install (enabled adapter)

**Files:**
- Run: install.sh with `bcg_adapter: "enabled"`

- [ ] **Step 1: Toggle source config (temporarily)**

```bash
python3 -c "
import json, pathlib
p = pathlib.Path('.agent/config.json')
cfg = json.loads(p.read_text())
cfg['bcg_adapter'] = 'enabled'
p.write_text(json.dumps(cfg, indent=2) + '\n')
print(json.dumps(cfg, indent=2))
"
```

Expected: config printed with `"bcg_adapter": "enabled"`.

- [ ] **Step 2: Run fresh install**

```bash
rm -rf /tmp/claude/825-enabled/
mkdir -p /tmp/claude/825-enabled/
./install.sh claude-code /tmp/claude/825-enabled/ --yes
```

Expected: install completes, mentions BCG propagation in output (e.g. `→ post-install: bcg_conditional_propagate ✓ ok`).

- [ ] **Step 3: Verify expected outputs**

```bash
ls /tmp/claude/825-enabled/.claude/agents/ | wc -l   # expect 21 (5 SDLC + 16 BCG)
test -f /tmp/claude/825-enabled/.claude/agents/partner-strategy.md && echo "OK: BCG agent present"
ls /tmp/claude/825-enabled/.claude/commands/ | wc -l   # expect 1 (sync-harness.md)
ls /tmp/claude/825-enabled/.claude/agent-memory/ | wc -l   # expect 16
```

Expected: all four counts match. If 21 fails, the action returned `disabled` despite config — debug stack_root/config-read.

- [ ] **Step 4: Revert source config**

```bash
python3 -c "
import json, pathlib
p = pathlib.Path('.agent/config.json')
cfg = json.loads(p.read_text())
cfg['bcg_adapter'] = 'disabled'
p.write_text(json.dumps(cfg, indent=2) + '\n')
"
git diff .agent/config.json
```

Expected: empty diff (config back to tracked default of "disabled").

- [ ] **Step 5: Cleanup smoke targets**

```bash
rm -rf /tmp/claude/825-disabled/ /tmp/claude/825-enabled/
```

---

## Task 17: Stage 6a — Append `DECISIONS.md` entry

**Files:**
- Modify: `.agent/memory/semantic/DECISIONS.md`
- Modify: `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`

- [ ] **Step 1: Append the Step 8.2.5 decision entry**

Append to `.agent/memory/semantic/DECISIONS.md`. The entry follows the same shape as Step 8.2.4's. Use Edit tool to append after the last decision entry. Required content:

```markdown

## 2026-04-27: Step 8.2.5 — sync fork to upstream v0.11.2 + port BCG to harness_manager

**Decision:** Synced agent-stack fork from base v0.8.0 (`a397568`) to upstream v0.11.2 (`8ba0293`) — 59 commits, 6 tags. Three-way merge with 4 conflict resolutions:

- `install.sh`: took upstream (38-line Python dispatcher) — discarded our 175-line bash with the BCG-conditional propagation block. Block re-introduced as new named post_install action `bcg_conditional_propagate` in `harness_manager/post_install.py`, registered in `harness_manager/schema.py`, wired into `adapters/claude-code/adapter.json`.
- `.agent/skills/_index.md`, `.agent/skills/_manifest.jsonl`: union merge (disjoint skill names — ours' 13 knowledge-work + SDLC + theirs' 3 new: data-flywheel, data-layer, design-md).
- `.agent/memory/semantic/DECISIONS.md`: ours-wins (project history).
- Auto-merged: `.agent/AGENTS.md`, `.gitignore`.

**Architecture preserved:** harness_manager's named-built-in post_install model (codex review flagged DSL creep; named built-ins are the constrained alternative). Extended `post_install.run()` to pass `stack_root` via kwargs — non-invasive change because all action functions absorb extra kwargs via `**_kwargs`. BCG action reads source-tree `adapters/bcg/` content because adapter manifests don't ship that content into target's copied `.agent/`.

**Behaviour preserved from bash:** agents/commands overwrite-on-install; agent-memory templates copy-if-missing (preserves user-seeded per-agent memory); README.md excluded from agent-memory propagation; gated on source `.agent/config.json` `bcg_adapter == "enabled"`.

**Gained from upstream:** harness_manager Python pkg (cli, doctor, install, manage_tui, post_install, remove, schema, state, status), data-layer + data-flywheel + design-md skills, codex adapter, pi adapter rewrite (closes formula crash + decay tz bug per #24), schemas/, examples/, new hooks (_episodic_io.py, pi_post_tool.py), Windows path-traversal security fix, Python 3.9 compat.

**Kept untouched (92 files):** all of `adapters/bcg/` (16 agents, 16 agent-memory templates, scripts, commands, protocols, context, templates, skills), `.agent/context/` (4 generic-consulting files from 8.2.4), `.agent/personas/` (executive-sponsor, program-director from 8.2.3), all 13 knowledge-work + SDLC skill dirs.

**Smoke-tested:** both adapter states on fresh installs into `/tmp/claude/825-{disabled,enabled}/`. Disabled → 5 SDLC agents, no BCG content. Enabled → 21 agents (5+16), 1 BCG slash command, 16 BCG agent-memory stubs. Idempotence verified: agent-memory MARKER line preserved across re-install.

**Rationale:** v0.9.0's harness_manager refactor is the architectural change that mattered most — install.sh became a thin dispatcher, real logic moved to a manifest-driven Python pkg. Re-extending the bash with our BCG block and ignoring the new pkg would have stranded us on a deprecated install path that brew formula no longer invokes. Porting to a named post_install action keeps us inside the upstream architecture, makes the BCG conditional reviewable by upstream (if we ever upstream the adapter), and is testable in isolation.

**Alternatives considered:** (a) Cherry-pick selected upstream commits — rejected; the harness_manager refactor is too coupled to its supporting commits to cherry-pick cleanly. (b) Rebase our 8.x onto upstream — rejected; conflict surface identical, but rewrites our publicly-visible 8.x history. (c) Generalize a `firm_overlay` mechanism in harness_manager — rejected as YAGNI; one named action is right-sized for one firm adapter. Refactor when a second firm appears. (d) Move BCG content into `.agent/firms/bcg/` so it gets copied as part of `.agent/` and the action only needs target_root — rejected; breaks the firm-adapter pattern established in Step 8.0 and would require restructuring the entire `adapters/bcg/` tree. Passing stack_root via kwargs is a one-line change with a much smaller blast radius.

**Status:** active

**Operationalized:** weekly upstream-sync cadence (Mon 9:13 local, durable cron `ba87d58c` + auto-memory `upstream_sync_cadence.md`) so this drift doesn't recur. Plan + per-tag classification doc checked into `docs/superpowers/plans/`.
```

- [ ] **Step 2: Append episodic learning**

Append a single JSONL line to `.agent/memory/episodic/AGENT_LEARNINGS.jsonl`:

```json
{"step": "8.2.5", "date": "2026-04-27", "kind": "fork-sync", "summary": "synced agent-stack fork v0.8.0 -> v0.11.2 (59 commits, 6 tags); ported install.sh BCG block to harness_manager.post_install named action bcg_conditional_propagate; smoke-tested disabled (5 SDLC) and enabled (21 agents, 1 cmd, 16 memory stubs); idempotence verified", "lesson": "weekly upstream-sync cadence prevents 6-tag drift; fork hygiene needs explicit cadence not implicit intent", "files_touched": ["install.sh", "harness_manager/schema.py", "harness_manager/post_install.py", "harness_manager/install.py", "adapters/claude-code/adapter.json", "tests/test_bcg_conditional_propagate.py", ".agent/skills/_index.md", ".agent/skills/_manifest.jsonl"]}
```

- [ ] **Step 3: Commit logging artifacts**

```bash
git add .agent/memory/semantic/DECISIONS.md .agent/memory/episodic/AGENT_LEARNINGS.jsonl
git commit -m "$(cat <<'EOF'
log: DECISIONS + episodic entry for Step 8.2.5 fork sync — Step 8.2.5

Captures sync rationale, conflict resolutions, alternatives considered,
smoke-test results. Episodic lesson: weekly cadence prevents recurrence.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Stage 6b — Update WORKSPACE.md

**Files:**
- Modify: `.agent/memory/working/WORKSPACE.md`

- [ ] **Step 1: Replace WORKSPACE.md current-step with "next: Step 8.3"**

Use Edit. Replace the entire content with:

```markdown
# Workspace (live task state)

> Live "where are we right now" file. Updated when we move between steps,
> hit a blocker, or change direction. For the durable history of *why* we
> did things, see `.agent/memory/semantic/DECISIONS.md`.

## Current step

**Step 8.3 — real-case dry-run on synced base (v0.11.2)**

Step 8.2.5 (fork sync) completed 2026-04-27. Base now at upstream
v0.11.2 plus our 8.x BCG/SDLC work plus harness_manager BCG port.
Plan + classification: `docs/superpowers/plans/2026-04-27-step-8-2-5-*`.

## Why now

The roster is complete (5 SDLC + 16 BCG agents, 17 skills, 6 workflows,
generic context, BCG adapter content) and the install path is current.
8.3 exercises the stack against a real consulting workflow to surface
gaps the unit-level smoke tests can't.

## Stage plan (TBD)

To be scoped at start of 8.3.

## Recurring cadence

- Weekly upstream sync check: every Monday morning. Mechanism:
  `CronCreate` (durable, 7-day TTL, ID `ba87d58c`, fires Mon 9:13 local)
  re-armed each fire, plus auto-memory entry `upstream_sync_cadence.md`
  so the cadence survives session restarts beyond the cron's lifetime.

## Recent upstream-sync checks

- 2026-04-27 — base WAS v0.8.0 (`a397568`); 59 commits behind across 6
  tags through v0.11.2; merged via Step 8.2.5. Base now v0.11.2 + 8.x
  + BCG harness_manager port.
```

- [ ] **Step 2: Commit**

```bash
git add .agent/memory/working/WORKSPACE.md
git commit -m "$(cat <<'EOF'
log: WORKSPACE.md → Step 8.3 ready, base now v0.11.2 + 8.x + BCG port

Step 8.2.5 closed. Live state advanced.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 19: Push to origin

**Files:**
- Push: `origin/master`

- [ ] **Step 1: Verify commit graph**

```bash
git log --oneline -10
git log --graph --oneline -20
```

Expected: 4 new commits since the pre-merge HEAD (plan doc, merge, BCG port, log+WORKSPACE — possibly 5 if the WORKSPACE update split). Merge commit visible in graph.

- [ ] **Step 2: Push**

```bash
git push origin master
```

Expected:
```
To https://github.com/pulkittalwar/agentic-stack.git
   77bc882..<new>  master -> master
```

- [ ] **Step 3: Confirm push landed**

```bash
git log origin/master..master
```

Expected: empty (origin caught up).

---

## Exit criteria

- [ ] All 19 tasks completed
- [ ] `git status -s` returns clean
- [ ] `tests/test_bcg_conditional_propagate.py` PASSES (both functions)
- [ ] Smoke `/tmp/claude/825-disabled/` shows 5 SDLC agents, no BCG
- [ ] Smoke `/tmp/claude/825-enabled/` shows 21 agents, 1 cmd, 16 memory stubs
- [ ] DECISIONS.md, WORKSPACE.md, AGENT_LEARNINGS.jsonl updated
- [ ] All commits pushed to `origin/master`

## Self-review notes

- Skill list collisions checked: ours' (analysis, architect, code-reviewer, context-search, document-assembly, draft-status-update, implementer, planner, product-discovery, requirements-writer, review, spec-reviewer, release-notes) vs theirs' (data-flywheel, data-layer, design-md) — disjoint, no name-level collision in `_index.md` or `_manifest.jsonl`.
- The `bcg_conditional_propagate` action takes `stack_root` via kwargs; existing `openclaw_register_workspace` swallows extra kwargs via `**_kwargs` so passing it through universally won't break that path.
- The `--yes` flag in install commands matches what the dispatcher accepts (per upstream install.sh comment block: `[--yes|--reconfigure|--force]`); if a different flag spelling is needed (e.g. `--non-interactive`), substitute when the test fails on first run.
- Agent count assertion uses `>= 21` for enabled (allows future SDLC additions) and `== 5` for disabled (strict — any extra means BCG leaked through).
- The plan does NOT update `DOMAIN_KNOWLEDGE.md`'s loop-#6 mention of phantom `upstream_sync.py` — that's a separate cleanup; flag for follow-up in WORKSPACE.md if it bothers reviewers.

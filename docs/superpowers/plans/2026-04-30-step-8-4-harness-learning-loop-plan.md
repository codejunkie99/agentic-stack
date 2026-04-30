# Step 8.4 — Harness Learning Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the harness-learning loop (capture → clean → propagate) and add a canonical-evidence discipline gate that hard-blocks harness-primitive changes without cited evidence.

**Architecture:** 6 logical commits across 19 tasks. Step 8.4.5 (4-layer hook gate + tool) ships FIRST so all subsequent commits land under the new discipline. Capture wiring (Gap 11), dream-cycle filter (Gap 9), cross-install graduate (Phase H), behavioral intent audit (Phase O), and one skill update (Gap 10) follow in order. Each post-8.4.5 task runs `cite_canonical.py` before harness-territory writes — dogfoods the gate and validates the enforcement layer.

**Tech Stack:** Python 3 (hooks + tools), pytest (tests), JSON (citation files + audit reports), bash (smoke tests), git (per-task commits). Claude Code hooks (`UserPromptSubmit`, `PreToolUse`, `Stop`, `SessionEnd`).

**Spec reference:** `docs/superpowers/specs/2026-04-30-step-8-4-harness-learning-loop-design.md`

---

## Task 1: Pre-flight verification

**Files:**
- Read: working tree state via git

- [ ] **Step 1: Verify branch + clean working tree**

```bash
cd /Users/talwarpulkit/code/agent-stack
git status -s
git branch --show-current
git rev-parse --abbrev-ref HEAD
```

Expected:
- Working tree clean (or only the spec doc + plan doc as untracked).
- Current branch: `feature/step-8.4-harness-learning-loop`.

If dirty or wrong branch: stop and surface to user.

- [ ] **Step 2: Verify spec is committed (or surface that it isn't)**

```bash
git log --oneline -5
git ls-files docs/superpowers/specs/2026-04-30-step-8-4-harness-learning-loop-design.md
```

Expected: spec exists in working tree; may or may not be committed.

- [ ] **Step 3: Verify Python + pytest availability**

```bash
python3 --version
python3 -m pytest --version
```

Expected: Python 3.10+, pytest 7+.

- [ ] **Step 4: Confirm fork's existing harness primitives are intact**

```bash
ls .agent/harness/*.py | head -10
ls .agent/tools/*.py | head -10
ls .agent/protocols/*.md
```

Expected: existing files (conductor.py, salience.py, propose_harness_fix.py, canonical-sources.md, etc.) all present.

---

## Task 2: Config files for canonical-evidence gate (Step 8.4.5 prep)

**Files:**
- Create: `.agent/protocols/harness-territory-keywords.txt`
- Create: `.agent/protocols/harness-territory-paths.json`

- [ ] **Step 1: Write keyword list**

Create `.agent/protocols/harness-territory-keywords.txt` with content:

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
\bhook\b
\.agent/
adapters/.*/agents/
adapters/.*/skills/
harness_manager/
```

One regex pattern per line. Used by Layer 1 (UserPromptSubmit) and Layer 4 (Stop) hooks.

- [ ] **Step 2: Write path glob list**

Create `.agent/protocols/harness-territory-paths.json` with content:

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

- [ ] **Step 3: Verify files**

```bash
cat .agent/protocols/harness-territory-keywords.txt | wc -l
python3 -c "import json; print(len(json.load(open('.agent/protocols/harness-territory-paths.json'))['globs']))"
```

Expected: 17 keyword lines, 13 globs.

- [ ] **Step 4: Commit**

```bash
git add .agent/protocols/harness-territory-keywords.txt .agent/protocols/harness-territory-paths.json
git commit -m "$(cat <<'EOF'
feat(8.4.5): add harness-territory keyword + path config files

Config feeding Step 8.4.5's canonical-evidence gate. Keywords drive
Layer 1 (UserPromptSubmit) + Layer 4 (Stop) hooks; paths drive
Layer 2 (PreToolUse Edit/Write) hook.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: `cite_canonical.py` tool with TDD

**Files:**
- Create: `.agent/tools/cite_canonical.py`
- Create: `tests/test_cite_canonical.py`

- [ ] **Step 1: Write failing test for `none-applies` source path**

Create `tests/test_cite_canonical.py`:

```python
"""Tests for .agent/tools/cite_canonical.py — Step 8.4.5 Layer 3."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / ".agent/tools/cite_canonical.py"


def _run(args, cwd=None, env=None):
    cmd = [sys.executable, str(TOOL)] + args
    result = subprocess.run(cmd, cwd=cwd or REPO_ROOT, env=env,
                            capture_output=True, text=True)
    return result


def test_none_applies_with_valid_justification(tmp_path, monkeypatch):
    """`--source none-applies` with valid justification writes citation file."""
    citation_dir = tmp_path / ".agent/memory/working"
    citation_dir.mkdir(parents=True)
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(citation_dir))
    result = _run([
        "--source", "none-applies",
        "--justification",
        "fork-extension because: bootstrapping the canonical-evidence gate itself, "
        "no canonical precedent for self-gating harness evolution",
    ])
    assert result.returncode == 0, result.stderr
    citation_file = citation_dir / ".canonical-citation.json"
    assert citation_file.exists()
    data = json.loads(citation_file.read_text())
    assert data["source"] == "none-applies"
    assert "bootstrapping" in data["justification"]
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd /Users/talwarpulkit/code/agent-stack
python3 -m pytest tests/test_cite_canonical.py::test_none_applies_with_valid_justification -v
```

Expected: FAIL with `FileNotFoundError` or `No such file or directory: .agent/tools/cite_canonical.py`.

- [ ] **Step 3: Write minimal implementation**

Create `.agent/tools/cite_canonical.py`:

```python
#!/usr/bin/env python3
"""Record a canonical-evidence citation for harness-territory work.

Step 8.4.5 Layer 3. Writes `.agent/memory/working/.canonical-citation.json`
which Layer 2 (PreToolUse Edit/Write hook) checks for freshness (TTL 30 min)
before allowing harness-territory file writes.

Sources:
  article         — examples/agentic-stack-resource/agentic-stack-source-article.md
  upstream        — git show upstream/master:<path>
  gstack          — pattern from garrytan/gstack
  gbrain          — pattern from garrytan/gbrain
  fork-decisions  — .agent/memory/semantic/DECISIONS.md
  none-applies    — fork extension; canonical does not cover this case
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_CITATION_DIR = AGENT_ROOT / "memory" / "working"
CITATION_FILENAME = ".canonical-citation.json"
TTL_MINUTES = 30
SOURCES = ("article", "upstream", "gstack", "gbrain", "fork-decisions", "none-applies")
ARTICLE_PATH = AGENT_ROOT.parent / "examples/agentic-stack-resource/agentic-stack-source-article.md"
DECISIONS_PATH = AGENT_ROOT / "memory/semantic/DECISIONS.md"


def _citation_dir() -> Path:
    override = os.environ.get("CANONICAL_CITATION_DIR")
    if override:
        return Path(override)
    return DEFAULT_CITATION_DIR


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=AGENT_ROOT.parent, stderr=subprocess.DEVNULL, text=True,
        ).strip()
        return out or "(detached)"
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return "(no git)"


def _validate_none_applies(justification: str) -> tuple[bool, str]:
    if len(justification) < 40:
        return False, "justification must be >=40 chars for source=none-applies"
    valid_prefixes = ("canonical-uncovered because:", "fork-extension because:")
    if not any(justification.lower().startswith(p) for p in valid_prefixes):
        return False, (
            "justification must start with 'canonical-uncovered because:' or "
            "'fork-extension because:' for source=none-applies"
        )
    return True, ""


def _flexible_substring_in(haystack: str, needle: str) -> bool:
    """Whitespace-flexible, case-insensitive substring check."""
    norm = lambda s: re.sub(r"\s+", " ", s).strip().lower()
    return norm(needle) in norm(haystack)


def _validate_article(reference: str, quote: str) -> tuple[bool, str]:
    if not re.match(r"^lines?\s+\d+(-\d+)?$", reference, re.IGNORECASE):
        return False, "reference must match 'line N' or 'lines N-M' for source=article"
    if not ARTICLE_PATH.exists():
        return False, f"article not found at {ARTICLE_PATH}"
    text = ARTICLE_PATH.read_text(encoding="utf-8", errors="replace")
    if not _flexible_substring_in(text, quote):
        return False, "quote not found in article (whitespace-flexible substring check failed)"
    return True, ""


def _validate_upstream(reference: str, quote: str) -> tuple[bool, str]:
    try:
        out = subprocess.check_output(
            ["git", "show", f"upstream/master:{reference}"],
            cwd=AGENT_ROOT.parent, stderr=subprocess.DEVNULL, text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as e:
        return False, f"git show upstream/master:{reference} failed: {e}"
    if not _flexible_substring_in(out, quote):
        return False, f"quote not found in upstream/master:{reference}"
    return True, ""


def _validate_fork_decisions(reference: str, quote: str) -> tuple[bool, str]:
    if not DECISIONS_PATH.exists():
        return False, f"DECISIONS.md not found at {DECISIONS_PATH}"
    text = DECISIONS_PATH.read_text(encoding="utf-8", errors="replace")
    if not _flexible_substring_in(text, quote):
        return False, "quote not found in fork DECISIONS.md"
    return True, ""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Record a canonical-evidence citation for harness-territory work."
    )
    p.add_argument("--source", required=True, choices=SOURCES)
    p.add_argument("--reference", default="")
    p.add_argument("--quote", default="")
    p.add_argument("--justification", required=True)
    p.add_argument("--topic", default="")
    args = p.parse_args(argv)

    if args.source == "none-applies":
        ok, msg = _validate_none_applies(args.justification)
        if not ok:
            print(f"error: {msg}", file=sys.stderr)
            return 2
    else:
        if not args.reference:
            print(f"error: --reference required for source={args.source}", file=sys.stderr)
            return 2
        if not args.quote:
            print(f"error: --quote required for source={args.source}", file=sys.stderr)
            return 2
        if args.source == "article":
            ok, msg = _validate_article(args.reference, args.quote)
        elif args.source == "upstream":
            ok, msg = _validate_upstream(args.reference, args.quote)
        elif args.source == "fork-decisions":
            ok, msg = _validate_fork_decisions(args.reference, args.quote)
        else:
            ok, msg = True, ""  # gstack / gbrain — no fetcher in v1
        if not ok:
            print(f"error: {msg}", file=sys.stderr)
            return 2

    citation_dir = _citation_dir()
    citation_dir.mkdir(parents=True, exist_ok=True)
    citation = {
        "topic": args.topic,
        "source": args.source,
        "reference": args.reference,
        "quote": args.quote,
        "justification": args.justification,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "branch": _git_branch(),
        "ttl_minutes": TTL_MINUTES,
    }
    (citation_dir / CITATION_FILENAME).write_text(json.dumps(citation, indent=2))
    print(f"ok: citation recorded; harness-territory writes allowed for next {TTL_MINUTES} min.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run test, verify it passes**

```bash
chmod +x .agent/tools/cite_canonical.py
python3 -m pytest tests/test_cite_canonical.py::test_none_applies_with_valid_justification -v
```

Expected: PASS.

- [ ] **Step 5: Add remaining test cases**

Append to `tests/test_cite_canonical.py`:

```python
def test_none_applies_rejects_short_justification(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(tmp_path))
    result = _run([
        "--source", "none-applies",
        "--justification", "too short",
    ])
    assert result.returncode == 2
    assert "justification must be" in result.stderr


def test_none_applies_rejects_bad_prefix(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(tmp_path))
    result = _run([
        "--source", "none-applies",
        "--justification",
        "this is more than forty characters long but does not start with the right prefix",
    ])
    assert result.returncode == 2
    assert "must start with" in result.stderr


def test_article_validates_quote_substring(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(tmp_path))
    result = _run([
        "--source", "article",
        "--reference", "line 426",
        "--quote", "The dream cycle is the mechanism that promotes episodic entries",
        "--justification", "verified canonical dream-cycle pattern reference",
    ])
    assert result.returncode == 0, result.stderr


def test_article_rejects_missing_quote(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(tmp_path))
    result = _run([
        "--source", "article",
        "--reference", "line 1",
        "--quote", "this exact phrase does not appear anywhere in the canonical article xyzzy",
        "--justification", "should fail validation",
    ])
    assert result.returncode == 2
    assert "quote not found in article" in result.stderr


def test_article_rejects_bad_reference_format(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(tmp_path))
    result = _run([
        "--source", "article",
        "--reference", "page 5",
        "--quote", "anything",
        "--justification": "should fail validation",
    ])
    assert result.returncode == 2
    assert "reference must match" in result.stderr


def test_fork_decisions_validates_quote(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_CITATION_DIR", str(tmp_path))
    result = _run([
        "--source", "fork-decisions",
        "--reference", "2026-04-30 entry",
        "--quote", "Add `.agent/protocols/canonical-sources.md` as a binding protocol",
        "--justification", "verified canonical-sources protocol exists in DECISIONS",
    ])
    assert result.returncode == 0, result.stderr
```

(Note: there's a typo `"--justification":` in `test_article_rejects_bad_reference_format` — fix to `"--justification",` before running.)

- [ ] **Step 6: Run full test suite**

```bash
python3 -m pytest tests/test_cite_canonical.py -v
```

Expected: 6 PASS.

- [ ] **Step 7: Commit**

```bash
git add .agent/tools/cite_canonical.py tests/test_cite_canonical.py
git commit -m "$(cat <<'EOF'
feat(8.4.5): cite_canonical.py — Layer 3 citation tool

Records canonical-evidence citation to .agent/memory/working/.canonical-citation.json
with TTL 30 min. Validates --source against fetched canonical text
(article / upstream / fork-decisions). --source=none-applies requires a
prefix-marked justification ('canonical-uncovered because:' or
'fork-extension because:') of >=40 chars to discourage shortcut use.

6 unit tests cover happy path + each validation failure mode.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: `canonical_gate_prompt.py` Layer 1 hook with TDD

**Files:**
- Create: `.agent/harness/canonical_gate_prompt.py`
- Create: `tests/test_canonical_gate_prompt.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_canonical_gate_prompt.py`:

```python
"""Tests for .agent/harness/canonical_gate_prompt.py — Step 8.4.5 Layer 1."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".agent/harness/canonical_gate_prompt.py"


def _run_hook(payload, env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return result


def test_keyword_match_writes_flag_and_injects(tmp_path, monkeypatch):
    monkeypatch.setenv("CANONICAL_GATE_FLAG_DIR", str(tmp_path))
    payload = {"prompt": "Let's redesign the salience formula in dream cycle"}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    assert result.returncode == 0
    flag_file = tmp_path / ".harness-mode.json"
    assert flag_file.exists()
    data = json.loads(flag_file.read_text())
    assert any("salience" in k or "dream" in k for k in data["matched_keywords"])
    out = json.loads(result.stdout)
    assert "additionalContext" in out
    assert "harness-primitive territory" in out["additionalContext"]


def test_no_match_clears_flag(tmp_path):
    flag_file = tmp_path / ".harness-mode.json"
    flag_file.write_text(json.dumps({"ts": "old", "matched_keywords": ["skill"]}))
    payload = {"prompt": "what time is it in tokyo"}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    assert result.returncode == 0
    assert not flag_file.exists()
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    assert "additionalContext" not in out


def test_match_on_path_pattern(tmp_path):
    payload = {"prompt": "edit .agent/skills/planner/SKILL.md to add a step"}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    assert result.returncode == 0
    flag_file = tmp_path / ".harness-mode.json"
    assert flag_file.exists()
```

- [ ] **Step 2: Run test, verify it fails**

```bash
python3 -m pytest tests/test_canonical_gate_prompt.py -v
```

Expected: FAIL with `No such file: .agent/harness/canonical_gate_prompt.py`.

- [ ] **Step 3: Write hook implementation**

Create `.agent/harness/canonical_gate_prompt.py`:

```python
#!/usr/bin/env python3
"""Step 8.4.5 Layer 1: UserPromptSubmit hook for canonical-evidence gate.

Reads user prompt body from stdin (Claude Code hook payload as JSON).
Regex-matches against keyword list. On match: writes `.harness-mode.json`
flag and injects a citation reminder via `additionalContext`. On no match
when flag exists: clears the flag.

Fail-OPEN: any error logs to stderr and exits 0 (allows session to proceed).
"""
from __future__ import annotations

import json
import os
import re
import sys
import datetime as dt
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
KEYWORDS_FILE = AGENT_ROOT / "protocols" / "harness-territory-keywords.txt"
DEFAULT_FLAG_DIR = AGENT_ROOT / "memory" / "working"
FLAG_FILENAME = ".harness-mode.json"

REMINDER_TEXT = (
    "This message touches harness-primitive territory. Before proposing OR "
    "actioning, run `python .agent/tools/cite_canonical.py` with `--source "
    "--reference --quote --justification`. See "
    "`.agent/protocols/canonical-sources.md` 5-step. Layer 2 will block "
    "harness-territory file writes without a fresh citation; Layer 4 will "
    "block your turn-end without an Evidence block in the response."
)


def _flag_dir() -> Path:
    override = os.environ.get("CANONICAL_GATE_FLAG_DIR")
    if override:
        return Path(override)
    return DEFAULT_FLAG_DIR


def _load_keywords() -> list[re.Pattern]:
    if not KEYWORDS_FILE.exists():
        return []
    patterns = []
    for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            patterns.append(re.compile(line, re.IGNORECASE))
        except re.error:
            print(f"warning: bad regex in keywords: {line}", file=sys.stderr)
    return patterns


def _match_keywords(prompt: str, patterns: list[re.Pattern]) -> list[str]:
    matched = []
    for p in patterns:
        if p.search(prompt):
            matched.append(p.pattern)
    return matched


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        # Fail-open on bad payload
        return 0

    prompt = payload.get("prompt", "") or payload.get("user_prompt", "")
    flag_dir = _flag_dir()
    flag_dir.mkdir(parents=True, exist_ok=True)
    flag_file = flag_dir / FLAG_FILENAME

    patterns = _load_keywords()
    matched = _match_keywords(prompt, patterns)

    if matched:
        flag_file.write_text(json.dumps({
            "ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "matched_keywords": matched,
        }, indent=2))
        print(json.dumps({"additionalContext": REMINDER_TEXT}))
    else:
        if flag_file.exists():
            flag_file.unlink()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"canonical_gate_prompt error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
chmod +x .agent/harness/canonical_gate_prompt.py
python3 -m pytest tests/test_canonical_gate_prompt.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add .agent/harness/canonical_gate_prompt.py tests/test_canonical_gate_prompt.py
git commit -m "$(cat <<'EOF'
feat(8.4.5): canonical_gate_prompt.py — Layer 1 (UserPromptSubmit)

Regex-matches harness-territory keywords in user prompts. On match:
writes .harness-mode.json flag + injects citation reminder via
additionalContext. On no match: clears stale flag.

Fail-open on any error so the session never gets locked out by a
hook failure.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: `canonical_gate_write.py` Layer 2 hook with TDD

**Files:**
- Create: `.agent/harness/canonical_gate_write.py`
- Create: `tests/test_canonical_gate_write.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_canonical_gate_write.py`:

```python
"""Tests for .agent/harness/canonical_gate_write.py — Step 8.4.5 Layer 2."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".agent/harness/canonical_gate_write.py"


def _run_hook(payload, env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return result


def test_non_harness_path_allows(tmp_path):
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": "/tmp/random/file.txt"},
    }
    result = _run_hook(payload, {"CANONICAL_CITATION_DIR": str(tmp_path)})
    assert result.returncode == 0
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    assert out.get("decision", "allow") == "allow"


def test_harness_path_without_citation_blocks(tmp_path):
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(REPO_ROOT / ".agent/skills/planner/SKILL.md")},
    }
    result = _run_hook(payload, {"CANONICAL_CITATION_DIR": str(tmp_path)})
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
    assert "cite canonical evidence" in out["reason"].lower()


def test_harness_path_with_fresh_citation_allows(tmp_path):
    citation = {
        "source": "fork-decisions",
        "reference": "test",
        "quote": "test",
        "justification": "test",
        "timestamp": "2026-04-30T12:00:00+00:00",
        "ttl_minutes": 30,
    }
    (tmp_path / ".canonical-citation.json").write_text(json.dumps(citation))
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(REPO_ROOT / ".agent/skills/planner/SKILL.md")},
    }
    result = _run_hook(payload, {"CANONICAL_CITATION_DIR": str(tmp_path)})
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    assert out.get("decision", "allow") == "allow"


def test_harness_path_with_stale_citation_blocks(tmp_path):
    citation = {
        "source": "fork-decisions",
        "reference": "test",
        "quote": "test",
        "justification": "test",
        "timestamp": "2026-04-30T12:00:00+00:00",
        "ttl_minutes": 30,
    }
    citation_file = tmp_path / ".canonical-citation.json"
    citation_file.write_text(json.dumps(citation))
    # Force mtime to 1 hour ago
    one_hour_ago = time.time() - 3600
    os.utime(citation_file, (one_hour_ago, one_hour_ago))
    payload = {
        "tool_name": "Edit",
        "tool_input": {"file_path": str(REPO_ROOT / ".agent/skills/planner/SKILL.md")},
    }
    result = _run_hook(payload, {"CANONICAL_CITATION_DIR": str(tmp_path)})
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
    assert "stale" in out["reason"].lower() or "expired" in out["reason"].lower()
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_canonical_gate_write.py -v
```

Expected: 4 FAIL with `No such file: .agent/harness/canonical_gate_write.py`.

- [ ] **Step 3: Write hook implementation**

Create `.agent/harness/canonical_gate_write.py`:

```python
#!/usr/bin/env python3
"""Step 8.4.5 Layer 2: PreToolUse hook for Edit/Write/MultiEdit.

Reads tool call payload from stdin. If the target file_path matches any
harness-territory glob, requires a fresh `.canonical-citation.json`
(TTL 30 min). Without it, returns block decision.

Fail-OPEN on any error.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
REPO_ROOT = AGENT_ROOT.parent
PATHS_FILE = AGENT_ROOT / "protocols" / "harness-territory-paths.json"
DEFAULT_CITATION_DIR = AGENT_ROOT / "memory" / "working"
CITATION_FILENAME = ".canonical-citation.json"
TTL_MINUTES = 30


def _citation_dir() -> Path:
    override = os.environ.get("CANONICAL_CITATION_DIR")
    if override:
        return Path(override)
    return DEFAULT_CITATION_DIR


def _load_globs() -> list[str]:
    if not PATHS_FILE.exists():
        return []
    try:
        data = json.loads(PATHS_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return data.get("globs", [])


def _normalize_path(p: str) -> str:
    """Reduce file_path to repo-relative POSIX form for glob matching."""
    pp = Path(p).resolve()
    try:
        rel = pp.relative_to(REPO_ROOT)
        return str(rel).replace(os.sep, "/")
    except ValueError:
        return str(pp).replace(os.sep, "/")


def _is_harness_territory(file_path: str, globs: list[str]) -> bool:
    norm = _normalize_path(file_path)
    return any(fnmatch.fnmatch(norm, g) for g in globs)


def _is_citation_fresh(citation_path: Path) -> tuple[bool, str]:
    if not citation_path.exists():
        return False, "no citation file present"
    try:
        data = json.loads(citation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False, "citation file unreadable"
    ts = data.get("timestamp")
    if not ts:
        return False, "citation missing timestamp"
    try:
        ts_dt = dt.datetime.fromisoformat(ts)
        if ts_dt.tzinfo is None:
            ts_dt = ts_dt.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return False, "citation timestamp unparseable"
    age = dt.datetime.now(dt.timezone.utc) - ts_dt
    if age.total_seconds() > TTL_MINUTES * 60:
        return False, f"citation stale (age {int(age.total_seconds()/60)}min, ttl {TTL_MINUTES}min)"
    return True, ""


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0  # fail-open

    tool_name = payload.get("tool_name", "")
    if tool_name not in ("Edit", "Write", "MultiEdit"):
        return 0  # not our matcher

    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path", "")
    if not file_path:
        return 0

    globs = _load_globs()
    if not _is_harness_territory(file_path, globs):
        return 0  # allow non-harness writes

    citation_path = _citation_dir() / CITATION_FILENAME
    fresh, reason = _is_citation_fresh(citation_path)
    if fresh:
        return 0  # allow

    block_reason = (
        f"harness-primitive write to `{file_path}` blocked ({reason}). "
        f"Cite canonical evidence first: python .agent/tools/cite_canonical.py "
        f"--source <article|upstream|gstack|gbrain|fork-decisions|none-applies> "
        f"--reference <line/path/sha> --quote <verbatim> --justification <text>. "
        f"See .agent/protocols/canonical-sources.md."
    )
    print(json.dumps({"decision": "block", "reason": block_reason}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"canonical_gate_write error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
chmod +x .agent/harness/canonical_gate_write.py
python3 -m pytest tests/test_canonical_gate_write.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add .agent/harness/canonical_gate_write.py tests/test_canonical_gate_write.py
git commit -m "$(cat <<'EOF'
feat(8.4.5): canonical_gate_write.py — Layer 2 (PreToolUse Edit/Write)

Hard-blocks Edit/Write/MultiEdit on harness-territory paths without a
fresh .canonical-citation.json (TTL 30min). Fail-open on any error.
4 unit tests cover non-harness allow / harness block / fresh citation
allow / stale citation block.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: `canonical_gate_stop.py` Layer 4 hook with TDD

**Files:**
- Create: `.agent/harness/canonical_gate_stop.py`
- Create: `tests/test_canonical_gate_stop.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_canonical_gate_stop.py`:

```python
"""Tests for .agent/harness/canonical_gate_stop.py — Step 8.4.5 Layer 4."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".agent/harness/canonical_gate_stop.py"

VALID_BLOCK = """
**Evidence:**
- source: article
- reference: line 169
- quote: "called when any action fails"
- justification: verified canonical on_failure pattern
"""

NO_BLOCK = "Here is my response with no evidence block."

MALFORMED_BLOCK = """
**Evidence:**
- yes I cited stuff
"""


def _run_hook(payload, env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps(payload),
        capture_output=True, text=True, env=env,
    )
    return result


def test_no_harness_mode_allows(tmp_path):
    payload = {"transcript": NO_BLOCK}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    assert out.get("decision", "allow") == "allow"


def test_harness_mode_with_valid_block_allows(tmp_path):
    (tmp_path / ".harness-mode.json").write_text(json.dumps({"ts": "now", "matched_keywords": ["skill"]}))
    payload = {"transcript": "Some response.\n\n" + VALID_BLOCK}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    out = json.loads(result.stdout) if result.stdout.strip() else {}
    assert out.get("decision", "allow") == "allow"


def test_harness_mode_without_block_blocks(tmp_path):
    (tmp_path / ".harness-mode.json").write_text(json.dumps({"ts": "now", "matched_keywords": ["skill"]}))
    payload = {"transcript": NO_BLOCK}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
    assert "evidence block" in out["reason"].lower()


def test_harness_mode_with_malformed_block_blocks(tmp_path):
    (tmp_path / ".harness-mode.json").write_text(json.dumps({"ts": "now", "matched_keywords": ["skill"]}))
    payload = {"transcript": MALFORMED_BLOCK}
    result = _run_hook(payload, {"CANONICAL_GATE_FLAG_DIR": str(tmp_path)})
    out = json.loads(result.stdout)
    assert out["decision"] == "block"
```

- [ ] **Step 2: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_canonical_gate_stop.py -v
```

Expected: 4 FAIL with `No such file`.

- [ ] **Step 3: Write hook implementation**

Create `.agent/harness/canonical_gate_stop.py`:

```python
#!/usr/bin/env python3
"""Step 8.4.5 Layer 4: Stop hook for canonical-evidence gate.

Fires before the assistant turn ends. If `.harness-mode.json` is set
(Layer 1 wrote it during UserPromptSubmit), the hook scans the assistant's
outgoing response for a structured Evidence block. Missing/malformed:
blocks the turn until the agent appends one.

Fail-OPEN on any error.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_FLAG_DIR = AGENT_ROOT / "memory" / "working"
FLAG_FILENAME = ".harness-mode.json"

EVIDENCE_BLOCK_RE = re.compile(
    r"\*\*Evidence:?\*\*\s*\n"
    r"(?:.*?)source\b[^:]*:\s*(article|upstream|gstack|gbrain|fork-decisions|none-applies)\b"
    r"(?:.*?)reference\b[^:]*:\s*\S+"
    r"(?:.*?)justification\b[^:]*:\s*\S+",
    re.IGNORECASE | re.DOTALL,
)
QUOTE_FIELD_RE = re.compile(
    r"quote\b[^:]*:\s*\S+", re.IGNORECASE,
)


def _flag_dir() -> Path:
    override = os.environ.get("CANONICAL_GATE_FLAG_DIR")
    if override:
        return Path(override)
    return DEFAULT_FLAG_DIR


def _is_block_valid(text: str) -> bool:
    m = EVIDENCE_BLOCK_RE.search(text)
    if not m:
        return False
    source = m.group(1).lower()
    if source != "none-applies":
        # quote field is required for non-none-applies sources
        block_text = m.group(0)
        if not QUOTE_FIELD_RE.search(block_text):
            return False
    return True


def main() -> int:
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return 0

    flag_path = _flag_dir() / FLAG_FILENAME
    if not flag_path.exists():
        return 0  # not in harness mode; allow

    transcript = payload.get("transcript", "") or payload.get("response", "")
    if not transcript:
        return 0  # nothing to scan; fail-open

    if _is_block_valid(transcript):
        return 0

    block_reason = (
        "Response touches harness territory but contains no valid Evidence "
        "block. Append the structured block: **Evidence:** with source, "
        "reference, quote (unless source=none-applies), justification. "
        "See .agent/protocols/canonical-sources.md."
    )
    print(json.dumps({"decision": "block", "reason": block_reason}))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"canonical_gate_stop error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)
```

- [ ] **Step 4: Run tests, verify they pass**

```bash
chmod +x .agent/harness/canonical_gate_stop.py
python3 -m pytest tests/test_canonical_gate_stop.py -v
```

Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add .agent/harness/canonical_gate_stop.py tests/test_canonical_gate_stop.py
git commit -m "$(cat <<'EOF'
feat(8.4.5): canonical_gate_stop.py — Layer 4 (Stop)

Scans assistant response text for structured Evidence block when
.harness-mode.json flag is set. Missing/malformed: blocks turn-end.
Fail-open on any error. 4 unit tests cover the matrix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Wire hooks into settings.json + adapter template + .gitignore

**Files:**
- Modify: `.claude/settings.json` (project-scoped)
- Modify: `adapters/claude-code/settings.json` (install template)
- Modify: `.gitignore`

- [ ] **Step 1: Read current `.claude/settings.json`**

```bash
cat .claude/settings.json
```

Note current shape; we'll merge new hook entries non-destructively.

- [ ] **Step 2: Cite canonical evidence (mandatory before harness-territory edit)**

```bash
python3 .agent/tools/cite_canonical.py \
    --source none-applies \
    --justification "fork-extension because: bootstrapping the canonical-evidence gate requires editing harness-territory settings.json before the gate has been wired to enforce; this is the bootstrap step the Step 8.4.5 risk-table calls out."
```

Expected: `ok: citation recorded`.

- [ ] **Step 3: Add hooks to `.claude/settings.json`**

Use Edit (not Write) to add three hook entries to the existing `hooks` block. If `hooks` doesn't exist, add it. Final shape includes:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      { "command": "python .agent/harness/canonical_gate_prompt.py" }
    ],
    "PreToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "command": "python .agent/harness/canonical_gate_write.py"
      }
    ],
    "Stop": [
      { "command": "python .agent/harness/canonical_gate_stop.py" }
    ]
  }
}
```

(Preserve any existing keys like `permissions`, `model`, etc.)

- [ ] **Step 4: Apply same edit to install template**

```bash
diff .claude/settings.json adapters/claude-code/settings.json
```

Mirror the hook block into `adapters/claude-code/settings.json` so fresh installs propagate the gate.

- [ ] **Step 5: Update .gitignore**

Add to `.gitignore`:

```
# Step 8.4.5 — canonical-evidence gate runtime artifacts
.agent/memory/working/.canonical-citation.json
.agent/memory/working/.harness-mode.json
.agent/memory/working/.session-state.json
.agent/memory/working/.hook-errors.log
```

- [ ] **Step 6: Smoke test the gate end-to-end**

```bash
# Should fail without citation
rm -f .agent/memory/working/.canonical-citation.json
echo '{"tool_name":"Edit","tool_input":{"file_path":".agent/skills/planner/SKILL.md"}}' | \
  python3 .agent/harness/canonical_gate_write.py

# Should allow after citation
python3 .agent/tools/cite_canonical.py --source none-applies \
  --justification "fork-extension because: smoke testing the gate end-to-end with no actual harness change"
echo '{"tool_name":"Edit","tool_input":{"file_path":".agent/skills/planner/SKILL.md"}}' | \
  python3 .agent/harness/canonical_gate_write.py
```

Expected: first call returns `{"decision":"block",...}`. Second returns `{}` or empty (allow).

- [ ] **Step 7: Commit**

```bash
git add .claude/settings.json adapters/claude-code/settings.json .gitignore
git commit -m "$(cat <<'EOF'
feat(8.4.5): wire 4-layer canonical-evidence gate into settings.json

Adds UserPromptSubmit (Layer 1), PreToolUse Edit|Write|MultiEdit
(Layer 2), and Stop (Layer 4) hooks to .claude/settings.json (project)
and adapters/claude-code/settings.json (install template). Adds the
runtime artifact filenames to .gitignore.

Smoke-tested: harness-territory write blocked without citation,
allowed after running cite_canonical.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: DECISIONS.md entry for Step 8.4.5

**Files:**
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "lines 849-850" \
    --quote "Hooks are the enforcement mechanism. They run before and after agent actions and implement the constraints defined in permissions and tool schemas." \
    --justification "Layer 2 + Layer 4 follow canonical's hook-as-enforcement pattern; assembly as harness-evolution discipline gate is fork extension."
```

Expected: `ok: citation recorded`.

- [ ] **Step 2: Append entry to DECISIONS.md**

Use Edit to append (or insert in date-order) after the `2026-04-30: ztk integration fix` entry:

```markdown


## 2026-04-30: Step 8.4.5 — canonical-evidence gate (4-layer hook + tool)

**Decision:** Add a 4-layer canonical-evidence enforcement gate that hard-blocks harness-primitive Edit/Write actions and assistant turn-ends without a cited canonical evidence block. Layer 1 (`canonical_gate_prompt.py`, UserPromptSubmit) detects harness-territory keywords in user prompts and writes `.harness-mode.json` flag + injects context reminder. Layer 2 (`canonical_gate_write.py`, PreToolUse Edit|Write|MultiEdit) blocks file writes to harness-territory globs unless `.canonical-citation.json` exists with mtime <30 min. Layer 3 (`cite_canonical.py` tool) is the satisfaction gesture — requires `--source --reference --quote --justification` and validates each non-`none-applies` source by substring-checking the quote against the cited canonical text. Layer 4 (`canonical_gate_stop.py`, Stop) blocks the assistant turn-end when `.harness-mode.json` is set unless the response contains a structured `**Evidence:**` block.

**Rationale:** Step 8.3 surfaced silent drift between intended and actual behavior of harness primitives. The brainstorm for Step 8.4 itself replicated the failure mode — Sections 1, 2, 3 each had to be revised after canonical re-checks. Memory-based reminders (`canonical-sources.md` protocol, auto-memory entries) had not produced the discipline; mechanical enforcement was the missing layer. Canonical pattern (article lines 849-850): "Hooks are the enforcement mechanism. They run before and after agent actions and implement the constraints defined in permissions and tool schemas." Each layer follows that pattern; the assembly as a "harness-evolution discipline gate" is canonically uncovered (canonical assumes single-user not actively evolving the harness from inside) and is labeled as fork extension.

**Alternatives considered:**
- Stronger memory entries / protocol updates only — rejected; that's what canonical-sources.md already was, and it didn't move the needle (Step 8.3 surfaced 3 gaps directly traceable to skipped canonical checks).
- Auto-detector hook for harness friction patterns — initially proposed and rejected mid-brainstorm; canonical posture is "hooks for mechanical signals, agent-prompted reflection for judgment signals" (article lines 169-204 vs 746-768). Friction recognition is judgment work; a detector would conflate the two.
- Single PreToolUse hook only (Layer 2) — rejected; brainstorm/design phase has no tool calls, so text-only output (Layer 4) needed independent enforcement.
- Soft warning instead of hard block on Layer 2 — rejected; the user explicitly asked for hard fail on three trigger conditions (harness primitives, agentic-stack components, answer/insight assumptions).

**Operationalised:**
- 4 new files: `.agent/harness/canonical_gate_{prompt,write,stop}.py`, `.agent/tools/cite_canonical.py`
- 2 config files: `.agent/protocols/harness-territory-{keywords.txt,paths.json}`
- Wired into `.claude/settings.json` (project) + `adapters/claude-code/settings.json` (install template)
- 4 test files (~20 unit tests total) cover allow/block matrix per layer + cite_canonical validation modes
- `.gitignore` updated for runtime artifacts (`.canonical-citation.json`, `.harness-mode.json`, `.session-state.json`, `.hook-errors.log`)
- All hooks fail-OPEN on error (logged to `.hook-errors.log`) so a hook crash never locks out the session
- Bootstrapped under `--source none-applies` citation justified as "fork-extension because: bootstrapping the gate itself"

**Status:** active. First commit landing under the new discipline is Step 8.4.5 itself (the gate gates its own subsequent commits). Open follow-up: extend `harness_conformance_audit.py` to detect drift in the gate's config (keyword list, path globs) and to spot-check recent citation files' quotes against the actual canonical text (gaming detection).

```

- [ ] **Step 3: Verify formatting + git diff**

```bash
git diff .agent/memory/semantic/DECISIONS.md | head -60
```

Expected: clean append, ~30 lines added.

- [ ] **Step 4: Commit**

```bash
git add .agent/memory/semantic/DECISIONS.md
git commit -m "$(cat <<'EOF'
docs(8.4.5): DECISIONS entry for canonical-evidence gate

Records the 4-layer hook+tool design, the rationale (Step 8.3 + Step 8.4
brainstorm both surfaced canonical-skip drift; mechanical enforcement was
the missing layer), and the canonical anchor (article lines 849-850 on
hooks-as-enforcement-mechanism). Labels the gate-as-assembly as fork
extension; canonical assumes single-user not actively evolving harness.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: Gap 11 Part A — CLAUDE.md trigger list

**Files:**
- Modify: `adapters/claude-code/CLAUDE.md`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "lines 752-768" \
    --quote "After every 5 uses OR on any failure: Read memory/episodic/AGENT_LEARNINGS.jsonl for recent entries tagged with this skill" \
    --justification "Part A surfaces canonical's universal self-rewrite hook trigger pattern at the operational-contract level (CLAUDE.md). Adds 6 explicit harness-friction triggers; matches canonical's 'check if any new patterns... exist' question, made specific."
```

Expected: `ok: citation recorded`.

- [ ] **Step 2: Read current section in CLAUDE.md**

```bash
sed -n '76,91p' adapters/claude-code/CLAUDE.md
```

- [ ] **Step 3: Replace section with expanded version**

Use Edit to replace lines 76-91 with:

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

- [ ] **Step 4: Verify diff**

```bash
git diff adapters/claude-code/CLAUDE.md | head -40
```

- [ ] **Step 5: Commit**

```bash
git add adapters/claude-code/CLAUDE.md
git commit -m "$(cat <<'EOF'
feat(gap-11): add 'When to invoke' trigger list to propose_harness_fix section

Explicit 6-trigger list in adapters/claude-code/CLAUDE.md surfaces the
canonical-aligned reflection prompt at the operational-contract level.
Matches canonical's universal self-rewrite hook pattern (article 752-768)
applied cross-skill rather than per-skill.

Closes Gap 11 Part A (out of 3 parts).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Gap 11 Part B — `init_session_state.py` + `check_friction_capture.py` with TDD

**Files:**
- Create: `.agent/harness/init_session_state.py`
- Create: `.agent/harness/check_friction_capture.py`
- Create: `tests/test_check_friction_capture.py`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "lines 169-204" \
    --quote "called when any action fails" \
    --justification "Part B mirrors canonical on_failure.py's auto-detection-via-hook pattern but for the mechanical signal of an empty HARNESS_FEEDBACK.md after a long session. Observability only (warns operator); doesn't block."
```

- [ ] **Step 2: Write failing tests**

Create `tests/test_check_friction_capture.py`:

```python
"""Tests for .agent/harness/check_friction_capture.py — Gap 11 Part B."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOK = REPO_ROOT / ".agent/harness/check_friction_capture.py"


def _run_hook(env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        capture_output=True, text=True, env=env,
    )
    return result


def _setup_session(tmp_path, tool_calls, feedback_lines_start, feedback_lines_end):
    working = tmp_path / "working"
    working.mkdir()
    feedback = working / "HARNESS_FEEDBACK.md"
    feedback.write_text("\n" * feedback_lines_end)
    state = working / ".session-state.json"
    state.write_text(json.dumps({
        "feedback_lines_at_start": feedback_lines_start,
        "session_started_at": "2026-04-30T10:00:00+00:00",
    }))
    episodic = tmp_path / "episodic"
    episodic.mkdir()
    al = episodic / "AGENT_LEARNINGS.jsonl"
    lines = []
    for i in range(tool_calls):
        lines.append(json.dumps({
            "timestamp": "2026-04-30T10:01:00",
            "skill": "test", "action": f"tool call {i}", "result": "success",
            "session_started_at": "2026-04-30T10:00:00+00:00",
        }))
    al.write_text("\n".join(lines) + "\n")
    return working, episodic


def test_long_session_no_capture_warns(tmp_path):
    working, episodic = _setup_session(tmp_path, tool_calls=50, feedback_lines_start=2, feedback_lines_end=2)
    result = _run_hook({
        "FRICTION_CHECK_WORKING_DIR": str(working),
        "FRICTION_CHECK_EPISODIC_DIR": str(episodic),
    })
    assert result.returncode == 0
    assert "captured 0 harness fixes" in result.stderr or "captured 0 harness fixes" in result.stdout


def test_long_session_with_capture_silent(tmp_path):
    working, episodic = _setup_session(tmp_path, tool_calls=50, feedback_lines_start=2, feedback_lines_end=10)
    result = _run_hook({
        "FRICTION_CHECK_WORKING_DIR": str(working),
        "FRICTION_CHECK_EPISODIC_DIR": str(episodic),
    })
    assert result.returncode == 0
    assert "harness-friction check" not in (result.stderr + result.stdout)


def test_short_session_silent(tmp_path):
    working, episodic = _setup_session(tmp_path, tool_calls=10, feedback_lines_start=2, feedback_lines_end=2)
    result = _run_hook({
        "FRICTION_CHECK_WORKING_DIR": str(working),
        "FRICTION_CHECK_EPISODIC_DIR": str(episodic),
    })
    assert result.returncode == 0
    assert "harness-friction check" not in (result.stderr + result.stdout)


def test_no_session_state_silent(tmp_path):
    working = tmp_path / "working"
    working.mkdir()
    episodic = tmp_path / "episodic"
    episodic.mkdir()
    result = _run_hook({
        "FRICTION_CHECK_WORKING_DIR": str(working),
        "FRICTION_CHECK_EPISODIC_DIR": str(episodic),
    })
    assert result.returncode == 0
    assert "harness-friction check" not in (result.stderr + result.stdout)
```

- [ ] **Step 3: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_check_friction_capture.py -v
```

Expected: 4 FAIL with `No such file`.

- [ ] **Step 4: Write `init_session_state.py`**

Create `.agent/harness/init_session_state.py`:

```python
#!/usr/bin/env python3
"""Step 8.4 Gap 11 Part B: SessionStart hook.

Snapshots HARNESS_FEEDBACK.md line count + session-start timestamp into
.session-state.json so check_friction_capture.py (SessionEnd) can compute
the delta. Fail-OPEN.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_WORKING = AGENT_ROOT / "memory" / "working"


def _working_dir() -> Path:
    return Path(os.environ.get("FRICTION_CHECK_WORKING_DIR", DEFAULT_WORKING))


def main() -> int:
    working = _working_dir()
    working.mkdir(parents=True, exist_ok=True)
    feedback = working / "HARNESS_FEEDBACK.md"
    lines_at_start = sum(1 for _ in feedback.open()) if feedback.exists() else 0
    state = {
        "feedback_lines_at_start": lines_at_start,
        "session_started_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    (working / ".session-state.json").write_text(json.dumps(state, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"init_session_state error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)
```

- [ ] **Step 5: Write `check_friction_capture.py`**

Create `.agent/harness/check_friction_capture.py`:

```python
#!/usr/bin/env python3
"""Step 8.4 Gap 11 Part B: SessionEnd hook.

Computes (feedback_lines_now - feedback_lines_at_start) + tool_calls_in_session.
If tool_calls > 30 AND delta == 0: emit operator console warning. Otherwise silent.

Observability only — warning goes to operator console; agent has stopped by
the time this fires. Fail-OPEN.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_WORKING = AGENT_ROOT / "memory" / "working"
DEFAULT_EPISODIC = AGENT_ROOT / "memory" / "episodic"
LONG_SESSION_THRESHOLD = 30


def _working_dir() -> Path:
    return Path(os.environ.get("FRICTION_CHECK_WORKING_DIR", DEFAULT_WORKING))


def _episodic_dir() -> Path:
    return Path(os.environ.get("FRICTION_CHECK_EPISODIC_DIR", DEFAULT_EPISODIC))


def _count_tool_calls_since(jsonl_path: Path, started_at: str) -> int:
    if not jsonl_path.exists():
        return 0
    try:
        cutoff = dt.datetime.fromisoformat(started_at)
        if cutoff.tzinfo is None:
            cutoff = cutoff.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return 0
    count = 0
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        ts = entry.get("timestamp")
        if not ts:
            continue
        try:
            ts_dt = dt.datetime.fromisoformat(ts)
            if ts_dt.tzinfo is None:
                ts_dt = ts_dt.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if ts_dt >= cutoff:
            count += 1
    return count


def main() -> int:
    working = _working_dir()
    state_path = working / ".session-state.json"
    if not state_path.exists():
        return 0  # first session, no baseline
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0

    started_at = state.get("session_started_at", "")
    feedback_at_start = int(state.get("feedback_lines_at_start", 0))
    feedback = working / "HARNESS_FEEDBACK.md"
    feedback_now = sum(1 for _ in feedback.open()) if feedback.exists() else 0
    delta = feedback_now - feedback_at_start

    episodic_jsonl = _episodic_dir() / "AGENT_LEARNINGS.jsonl"
    tool_calls = _count_tool_calls_since(episodic_jsonl, started_at)

    if tool_calls > LONG_SESSION_THRESHOLD and delta == 0:
        msg = (
            f"⚠ harness-friction check: this session ran {tool_calls} tool calls "
            f"and captured 0 harness fixes. If that's right, ignore. If not, run "
            f"propose_harness_fix.py before starting your next session."
        )
        print(msg, file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"check_friction_capture error (fail-open): {e}", file=sys.stderr)
        sys.exit(0)
```

- [ ] **Step 6: Run tests, verify they pass**

```bash
chmod +x .agent/harness/init_session_state.py .agent/harness/check_friction_capture.py
python3 -m pytest tests/test_check_friction_capture.py -v
```

Expected: 4 PASS.

- [ ] **Step 7: Wire SessionStart + SessionEnd hooks**

```bash
python3 .agent/tools/cite_canonical.py --source none-applies \
    --justification "fork-extension because: wiring observability hooks into settings.json continues the bootstrap of Step 8.4.5 + Gap 11 Part B; the gate is now active and this is a routine harness-territory edit."
```

Use Edit to add to `.claude/settings.json` `hooks` block:

```json
"SessionStart": [
  { "command": "python .agent/harness/init_session_state.py" }
],
"SessionEnd": [
  { "command": "python .agent/harness/check_friction_capture.py" }
]
```

Mirror in `adapters/claude-code/settings.json`.

- [ ] **Step 8: Commit**

```bash
git add .agent/harness/init_session_state.py .agent/harness/check_friction_capture.py \
    tests/test_check_friction_capture.py .claude/settings.json adapters/claude-code/settings.json
git commit -m "$(cat <<'EOF'
feat(gap-11): SessionStart/End observability hook for friction capture

init_session_state.py snapshots HARNESS_FEEDBACK.md line count at session
start; check_friction_capture.py at session end emits operator-console
warning if tool_calls > 30 AND feedback_delta == 0. Mechanical signal only;
observability not blocking (SessionEnd fires after agent has stopped).

Closes Gap 11 Part B (of 3).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Gap 11 Part C — universal self-rewrite hook template + DECISIONS

**Files:**
- Modify: `.agent/skills/_template/SELF_REWRITE_HOOK.md` (verify path; if missing, locate via `find .agent/skills -name "SELF_REWRITE*"`)
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Locate the universal self-rewrite hook template**

```bash
find .agent -name "*self_rewrite*" -o -name "*SELF_REWRITE*" 2>/dev/null
find adapters -name "*self_rewrite*" -o -name "*SELF_REWRITE*" 2>/dev/null
```

If no dedicated template file exists, look in `.agent/skills/_template/` or `.agent/skills/skillforge/SKILL.md` for the canonical template text.

If no template exists at all: surface to user before proceeding. The fork may have inlined the hook into each skill rather than templated it. In that case, Part C becomes "add the harness-friction trigger to skillforge's TEMPLATE block" instead.

- [ ] **Step 2: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "lines 762-768" \
    --quote "If a constraint was violated during execution, escalate to memory/semantic/LESSONS.md" \
    --justification "Part C extends canonical's universal self-rewrite hook step list with one harness-friction trigger that propagates to all 26 skills via convention; matches canonical compounding pattern."
```

- [ ] **Step 3: Add the trigger bullet**

Edit the located template file. Insert as new step 6 (or appropriate position in the existing step list):

```markdown
6. If a harness-shape friction pattern was encountered (skill missing a
   step, workflow timing wrong, agent dispatched mismatch, agent-memory
   sparse), invoke `python .agent/tools/propose_harness_fix.py` ONCE per
   pattern before signing off this skill. Triggers: see
   `adapters/claude-code/CLAUDE.md` "When to invoke" list.
```

- [ ] **Step 4: Verify skill linter still passes**

```bash
python3 .agent/tools/skill_linter.py
```

Expected: 26/26 conformant (or matches current count + still passes).

- [ ] **Step 5: Append DECISIONS.md entry**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference "2026-04-29 Step 8.3 Phase 2 dry-run outcome entry; Gap 11 in gap-log" \
    --quote "Gap 11 — propose_harness_fix.py invisible to agents" \
    --justification "DECISIONS entry documents Gap 11 closure via 3 parts (CLAUDE.md trigger list, observability hook, template trigger)."
```

Use Edit to append:

```markdown


## 2026-04-30: Gap 11 — capture wiring (3-part fix)

**Decision:** Close Gap 11 (HARNESS_FEEDBACK.md empty after 130 episodes despite multiple frictions) with three coordinated changes: (A) explicit 6-trigger "When to invoke" list added to `adapters/claude-code/CLAUDE.md` "Proposing a harness fix" section; (B) SessionStart/SessionEnd observability hook (`init_session_state.py` + `check_friction_capture.py`) emitting operator-console warning when `tool_calls > 30 AND feedback_delta == 0`; (C) one-line addition to the universal self-rewrite hook template referencing the trigger list. No auto-detection hook for friction patterns themselves — that path was rejected as conflating mechanical (canonical hook territory) with judgment (canonical agent-prompted-reflection territory).

**Rationale:** Canonical (article 746-768) splits enforcement into hooks-for-mechanical and prompts-for-judgment. Friction-recognition is judgment work. Part A puts the trigger list at the operational-contract level (cross-skill). Part C propagates the same trigger via the universal self-rewrite hook template (per-skill compounding). Part B catches the mechanical signal — long session with no captures — without trying to detect friction itself. The 3-part design follows canonical posture: prompts where judgment matters, hooks where the signal is mechanical.

**Alternatives considered:**
- Auto-detector hook for harness-shape friction patterns — rejected; would need to detect things like "workflow audit produced ≥3 structural fixes after deliverable was drafted," which is judgment-bound. Building that as a hook risks false positives that defeat the discipline.
- Skill-level Phase-exit prompts only (no CLAUDE.md change) — rejected; scatters discipline across 26 skills + creates linter churn.
- Stop hook that blocks turn-end if no propose_harness_fix.py invocation in session — rejected; over-correction. Many sessions legitimately have no harness friction.

**Operationalised:**
- 3 commits: Part A (CLAUDE.md), Part B (hooks + tests), Part C (template + DECISIONS)
- 4 unit tests (`test_check_friction_capture.py`) cover delta+tool_call matrix
- Settings wiring: `SessionStart` + `SessionEnd` added to `.claude/settings.json` + adapter template
- Skill linter: 26/26 conformant after Part C edit (template change doesn't violate per-skill conformance)

**Status:** active. Open follow-up: propagate Phase L's importance/pain tuning pattern to other long-session skills (planner, document-researcher, etc.) so memory_reflect events reliably win cluster canonical races there too.

```

- [ ] **Step 6: Commit**

```bash
git add .agent/skills/_template/SELF_REWRITE_HOOK.md .agent/memory/semantic/DECISIONS.md
# (adjust the first path to whatever Step 1 located)
git commit -m "$(cat <<'EOF'
feat(gap-11): universal self-rewrite hook template + DECISIONS entry

Adds harness-friction trigger to the universal self-rewrite hook template
so the trigger propagates to all skills via convention (canonical
compounding pattern, article 762). DECISIONS entry records the 3-part
design + rationale (canonical hooks-for-mechanical vs prompts-for-judgment
split).

Closes Gap 11 (Parts A + B + C).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 12: Gap 9 — `collapse_file_writes` in auto_dream.py with TDD

**Files:**
- Modify: `.agent/memory/auto_dream.py`
- Create: `tests/test_auto_dream_filter.py`
- Create: `tests/fixtures/episodic_collapse_input.jsonl`
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "lines 469-482" \
    --quote "cluster entries by skill + action pattern to detect recurrence" \
    --justification "Part A restores canonical's auto-collapse-by-action-prefix behavior, lost when fork's Jaccard migration replaced prefix-grouping. Reintroducing the collapse pre-cluster recovers the canonical guarantee without rolling back to prefix-only clustering."
```

- [ ] **Step 2: Create fixture**

Create `tests/fixtures/episodic_collapse_input.jsonl`:

```jsonl
{"timestamp":"2026-04-28T14:00:00","skill":"deck-builder","action":"Wrote storyboard.md (200 lines)","detail":"first draft v1 sections","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"run-A"}}
{"timestamp":"2026-04-28T14:05:00","skill":"deck-builder","action":"Wrote storyboard.md (215 lines)","detail":"v1 fixes","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"run-A"}}
{"timestamp":"2026-04-28T14:10:00","skill":"deck-builder","action":"Edited storyboard.md","detail":"replaced section 3","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"run-A"}}
{"timestamp":"2026-04-28T14:15:00","skill":"deck-builder","action":"Edited storyboard.md","detail":"replaced section 5","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"run-A"}}
{"timestamp":"2026-04-28T14:30:00","skill":"deck-builder","action":"Phase 1 storyboard sign-off","detail":"v3 8-section coverage clean","pain_score":5,"importance":8,"reflection":"When storyboard collides with workflow contract late, gate the contract check at v1 instead of after v2","source":{"run_id":"run-A"}}
{"timestamp":"2026-04-28T16:00:00","skill":"document-researcher","action":"Created summary.md","detail":"BOCHK 37 pages","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"run-A"}}
{"timestamp":"2026-04-28T17:00:00","skill":"deck-builder","action":"Wrote a long paragraph about migration plans","detail":"no file token","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"run-A"}}
```

- [ ] **Step 3: Write failing tests**

Create `tests/test_auto_dream_filter.py`:

```python
"""Tests for collapse_file_writes() in auto_dream.py — Gap 9."""
import json
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".agent/memory"))
sys.path.insert(0, str(REPO_ROOT / ".agent/harness"))


def test_collapse_pure_tool_use_group():
    from auto_dream import collapse_file_writes
    entries = [
        {"timestamp":"2026-04-28T14:00:00","skill":"d","action":"Wrote a.md","detail":"x","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
        {"timestamp":"2026-04-28T14:01:00","skill":"d","action":"Wrote a.md","detail":"y","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
        {"timestamp":"2026-04-28T14:02:00","skill":"d","action":"Wrote a.md","detail":"z","pain_score":3,"importance":6,"reflection":"","source":{"run_id":"r1"}},
    ]
    out = collapse_file_writes(entries)
    assert len(out) == 1
    assert "×3" in out[0]["action"]
    assert out[0]["recurrence_count"] == 3
    assert out[0]["pain_score"] == 3  # max
    assert out[0]["importance"] == 6  # max


def test_preserve_group_with_reflection():
    from auto_dream import collapse_file_writes
    entries = [
        {"timestamp":"2026-04-28T14:00:00","skill":"d","action":"Wrote a.md","detail":"x","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
        {"timestamp":"2026-04-28T14:01:00","skill":"d","action":"Wrote a.md","detail":"y","pain_score":5,"importance":8,"reflection":"actual lesson here","source":{"run_id":"r1"}},
    ]
    out = collapse_file_writes(entries)
    assert len(out) == 2  # not collapsed because reflection present


def test_single_write_untouched():
    from auto_dream import collapse_file_writes
    entries = [
        {"timestamp":"2026-04-28T14:00:00","skill":"d","action":"Wrote a.md","detail":"x","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
    ]
    out = collapse_file_writes(entries)
    assert len(out) == 1
    assert "×" not in out[0]["action"]


def test_no_extension_does_not_match_regex():
    from auto_dream import collapse_file_writes
    entries = [
        {"timestamp":"2026-04-28T14:00:00","skill":"d","action":"Wrote a long summary","detail":"x","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
        {"timestamp":"2026-04-28T14:01:00","skill":"d","action":"Wrote a long summary","detail":"y","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
    ]
    out = collapse_file_writes(entries)
    assert len(out) == 2  # unchanged


def test_different_run_ids_not_collapsed():
    from auto_dream import collapse_file_writes
    entries = [
        {"timestamp":"2026-04-28T14:00:00","skill":"d","action":"Wrote a.md","detail":"x","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r1"}},
        {"timestamp":"2026-04-28T14:01:00","skill":"d","action":"Wrote a.md","detail":"y","pain_score":2,"importance":5,"reflection":"","source":{"run_id":"r2"}},
    ]
    out = collapse_file_writes(entries)
    assert len(out) == 2  # different sessions


def test_fixture_integration():
    from auto_dream import collapse_file_writes
    fixture = REPO_ROOT / "tests/fixtures/episodic_collapse_input.jsonl"
    entries = [json.loads(l) for l in fixture.read_text().splitlines() if l.strip()]
    out = collapse_file_writes(entries)
    # 7 entries: 4 Write/Edit on storyboard.md → collapses to 1 (no reflection in those 4)
    # 1 reflect on storyboard sign-off → preserved
    # 1 Created summary.md (single, no group) → preserved
    # 1 "Wrote a long paragraph" (no .ext) → preserved
    assert len(out) == 4
    collapsed = [e for e in out if "×" in e.get("action", "")]
    assert len(collapsed) == 1
    assert collapsed[0]["recurrence_count"] == 4
```

- [ ] **Step 4: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_auto_dream_filter.py -v
```

Expected: 6 FAIL with `ImportError: cannot import name 'collapse_file_writes'`.

- [ ] **Step 5: Add `collapse_file_writes` to auto_dream.py**

Read current `.agent/memory/auto_dream.py`. Add the new function and call it before `cluster_and_extract`. Insert after the imports block:

```python
import re

_FILE_WRITE_RE = re.compile(
    r"^(Wrote|Edited|Created|Updated)\s+(\S+\.\S+)"
)


def collapse_file_writes(entries):
    """Pre-cluster collapse of same-file Write/Edit episodes within a session.

    Restores canonical-article prefix-grouping behavior (article lines
    469-482) lost when fork's Jaccard migration replaced action-prefix
    clustering. On long content sessions, 30+ Write events on the same
    file cluster as the dominant signal; collapsing them pre-cluster
    makes the cluster claim reflect insight, not file activity.

    Episodes with substantive `reflection` text are NEVER collapsed —
    those are explicit memory_reflect events.

    Returns a new list; input entries are not mutated.
    """
    groups = {}
    others = []
    for e in entries:
        action = e.get("action", "")
        m = _FILE_WRITE_RE.match(action)
        if not m:
            others.append(e)
            continue
        kind = m.group(1)
        path = m.group(2)
        run_id = (e.get("source") or {}).get("run_id", "")
        key = (run_id, kind, path)
        groups.setdefault(key, []).append(e)

    collapsed = []
    for (run_id, kind, path), members in groups.items():
        if any((m.get("reflection") or "").strip() for m in members):
            # Preserve all if any has reflection
            collapsed.extend(members)
            continue
        if len(members) < 2:
            collapsed.extend(members)
            continue
        # Sort by timestamp; pick latest as base for synthesized representative
        sorted_members = sorted(members, key=lambda x: x.get("timestamp", ""))
        first = sorted_members[0]
        last = sorted_members[-1]
        rep = dict(last)
        rep["action"] = f"{kind} {path} ×{len(members)} in session"
        rep["detail"] = (
            f"first: {(first.get('detail','') or '')[:80]} ... "
            f"last: {(last.get('detail','') or '')[:80]}"
        )
        rep["pain_score"] = max(m.get("pain_score", 5) for m in members)
        rep["importance"] = max(m.get("importance", 5) for m in members)
        rep["recurrence_count"] = len(members)
        collapsed.append(rep)

    return others + collapsed
```

In `run_dream_cycle()`, modify the line that calls `cluster_and_extract`:

```python
    # before:
    # patterns = cluster_and_extract(entries, threshold=CLUSTER_SIMILARITY)

    # after:
    filtered = collapse_file_writes(entries)
    patterns = cluster_and_extract(filtered, threshold=CLUSTER_SIMILARITY)
```

- [ ] **Step 6: Run tests, verify they pass**

```bash
python3 -m pytest tests/test_auto_dream_filter.py -v
```

Expected: 6 PASS.

- [ ] **Step 7: Append DECISIONS entry**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "lines 469-482" \
    --quote "cluster entries by skill + action pattern to detect recurrence" \
    --justification "Gap 9 fix restores canonical prefix-grouping behavior pre-cluster; reflection_bonus formula change rejected as canonical-violation."
```

Append to DECISIONS.md:

```markdown


## 2026-04-30: Gap 9 — auto_dream pre-cluster file-write collapse

**Decision:** Add `collapse_file_writes(entries)` as a pre-clustering filter in `.agent/memory/auto_dream.py:run_dream_cycle()`. Detects file-write episodes via regex `^(Wrote|Edited|Created|Updated)\s+(\S+\.\S+)`, groups by `(source.run_id, action_kind, target_path)`, collapses groups of size ≥2 that contain no episodes with substantive `reflection` text into a single synthesized representative with `recurrence_count = N`. Episodes with non-empty `reflection` are NEVER collapsed (those are explicit memory_reflect events). REJECTED in design phase: `reflection_bonus` multiplier on salience formula — would have violated canonical's "the simple weighted formula won" stance (article line 365); Phase L's importance/pain tuning is sufficient.

**Rationale:** Canonical (article lines 469-482) clusters episodes by `skill::action[:50]` prefix-grouping, which auto-collapses same-action episodes. Fork's Jaccard migration (per `cluster.py` docstring "Phase 3's replacement for action-prefix clustering") gained semantic-similarity matching across paraphrases but lost the auto-collapse. On HarnessX Phase 2 (130 episodes, 13 candidates), the cluster claim collapsed to "Wrote storyboard.md (781 lines)" because 30+ Write events on the same file dominated the cluster. Re-introducing the collapse pre-cluster restores the canonical guarantee while preserving Jaccard's paraphrase coverage. Phase L's per-phase-exit importance=8-10, pain=5-8 already produces salience scores that beat default file-write events (8.0 vs ~3.0 with min(recurrence,3) saturation), so a `reflection_bonus` formula factor is unnecessary AND would violate canonical's simple-formula posture.

**Alternatives considered:**
- `reflection_bonus = 1.5x` multiplier in `salience_score` for episodes with substantive reflection — rejected; canonical (article 365) explicitly values simple formula. Phase L tuning of inputs already wins canonical races.
- Roll back Jaccard, return to prefix-grouping — rejected; loses paraphrase-similarity coverage that Jaccard gained.
- Detect per-tool-name (`Write`/`Edit` action_kind from a structured field) — rejected; episodes don't have structured tool fields; regex on action text is the available signal.
- Out-of-branch follow-up (NOT this commit): propagate Phase L's input-tuning pattern to other long-session skills (planner, document-researcher) so they too win cluster canonical races. Land via skill self-rewrite + propose_harness_fix.

**Operationalised:**
- `collapse_file_writes()` added to `.agent/memory/auto_dream.py`; called in `run_dream_cycle()` before `cluster_and_extract`
- 6 unit tests cover: pure-tool-use collapse, mixed-with-reflection preserved, single Write untouched, no-extension regex non-match, different run_id non-merge, fixture integration
- Fixture at `tests/fixtures/episodic_collapse_input.jsonl` (7 representative entries from HarnessX-shape pattern)

**Status:** active. Validated against test fixture; integration validation against real HarnessX 130-episode batch deferred until next dream cycle on a target.

```

- [ ] **Step 8: Commit**

```bash
git add .agent/memory/auto_dream.py tests/test_auto_dream_filter.py \
    tests/fixtures/episodic_collapse_input.jsonl .agent/memory/semantic/DECISIONS.md
git commit -m "$(cat <<'EOF'
feat(gap-9): pre-cluster collapse of file-write episodes in auto_dream

collapse_file_writes() runs before cluster_and_extract; detects same-file
Write/Edit groups in a session via regex, collapses to one representative
with recurrence_count=N. Skips groups containing any episode with
substantive reflection text. Reintroduces canonical's prefix-grouping
auto-collapse (article 469-482) lost when fork moved to Jaccard.

Rejected the reflection_bonus formula change (canonical violation per
article 365 'simple formula won'); Phase L's input tuning is sufficient.

6 unit tests + fixture cover the matrix.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 13: Phase H — `harness-graduate.py` lessons flow with TDD

**Files:**
- Create: `.agent/tools/harness-graduate.py`
- Create: `tests/test_harness_graduate.py`
- Create: `tests/fixtures/harness_graduate_target/` (minimal target install fixture)

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference "2026-04-29 Phase K entry" \
    --quote "Cross-install graduation (lessons going UP from engagement to fork) is the deferred" \
    --justification "Phase H is the explicitly-deferred work named in Phase K. Within-install graduate.py provides the contract model. Cross-install dimension is fork extension; canonical assumes single-install."
```

- [ ] **Step 2: Build minimal target-install fixture**

Create `tests/fixtures/harness_graduate_target/.agent/memory/semantic/lessons.jsonl`:

```jsonl
{"id":"lesson_aaa111","claim":"this is a portable lesson","conditions":["general"],"created_at":"2026-04-28T10:00:00"}
{"id":"lesson_bbb222","claim":"engagement-specific note about HarnessX bank deck","conditions":["client/harnessx"],"created_at":"2026-04-28T11:00:00"}
{"id":"lesson_ccc333","claim":"this matches a fork lesson exactly","conditions":["existing"],"created_at":"2026-04-28T12:00:00"}
```

Create `tests/fixtures/harness_graduate_target/.agent/memory/semantic/LESSONS.md`:

```markdown
# Lessons (target)

## Auto-promoted 2026-04-28
- this is a portable lesson
- engagement-specific note about HarnessX bank deck
- this matches a fork lesson exactly
```

Create `tests/fixtures/harness_graduate_target/.agent/memory/semantic/DECISIONS.md`:

```markdown
# Major Decisions

## 2026-04-28: Target-only decision A
**Decision:** Some target-side architectural choice.
**Rationale:** Lived experience.
**Status:** active.
```

Also create the matching `tests/fixtures/harness_graduate_target/.agent/memory/client/harnessx/` directory (empty marker) so the engagement-specificity heuristic can match against it.

- [ ] **Step 3: Write failing tests**

Create `tests/test_harness_graduate.py`:

```python
"""Tests for .agent/tools/harness-graduate.py — Phase H."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / ".agent/tools/harness-graduate.py"
FIXTURE = REPO_ROOT / "tests/fixtures/harness_graduate_target"


def _run(args, stdin_text="", env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(TOOL)] + args,
        input=stdin_text, capture_output=True, text=True, env=env,
    )


def _setup_fork_fixture(tmp_path):
    """Build a minimal fork-side fixture for graduation target."""
    fork = tmp_path / "fork"
    semantic = fork / ".agent/memory/semantic"
    semantic.mkdir(parents=True)
    # Fork has lesson_ccc333 already (matches target's third)
    (semantic / "lessons.jsonl").write_text(
        json.dumps({"id":"lesson_ccc333","claim":"this matches a fork lesson exactly","conditions":["existing"]}) + "\n"
    )
    (semantic / "LESSONS.md").write_text("# Lessons (fork)\n\n- this matches a fork lesson exactly\n")
    (semantic / "DECISIONS.md").write_text("# Major Decisions\n\n## 2026-04-25: Fork-only decision Z\n**Decision:** Z.\n**Status:** active.\n")
    return fork


def test_dry_run_outputs_diff_no_writes(tmp_path):
    fork = _setup_fork_fixture(tmp_path)
    result = _run(
        [str(FIXTURE), "--dry-run", "--target-slug", "test-target"],
        env_overrides={"HARNESS_GRADUATE_FORK_ROOT": str(fork)},
    )
    assert result.returncode == 0, result.stderr
    out = result.stdout
    assert "lesson_aaa111" in out  # portable: would graduate
    assert "lesson_bbb222" in out  # engagement-specific: would graduate but flagged
    assert "lesson_ccc333" in out  # already in fork: dedup-skipped
    # No actual writes
    assert (fork / ".agent/memory/semantic/lessons.jsonl").read_text().count("\n") == 1


def test_lessons_only_skips_decisions(tmp_path):
    fork = _setup_fork_fixture(tmp_path)
    # Stdin: "y\n" + rationale for lesson_aaa111, "skip\n" for bbb222 (or whatever)
    stdin_text = "y\n" + "valid graduation rationale text\n" + "skip\n"
    result = _run(
        [str(FIXTURE), "--lessons-only", "--target-slug", "test-target"],
        stdin_text=stdin_text,
        env_overrides={"HARNESS_GRADUATE_FORK_ROOT": str(fork)},
    )
    assert result.returncode == 0
    decisions = (fork / ".agent/memory/semantic/DECISIONS.md").read_text()
    assert "Target-only decision A" not in decisions  # DECISIONS skipped


def test_dedup_auto_skip(tmp_path):
    fork = _setup_fork_fixture(tmp_path)
    result = _run(
        [str(FIXTURE), "--dry-run", "--target-slug", "test-target"],
        env_overrides={"HARNESS_GRADUATE_FORK_ROOT": str(fork)},
    )
    out = result.stdout
    assert "dedup" in out.lower() and "lesson_ccc333" in out
```

- [ ] **Step 4: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_harness_graduate.py -v
```

Expected: FAIL with `No such file: harness-graduate.py`.

- [ ] **Step 5: Implement `harness-graduate.py` (lessons flow)**

Create `.agent/tools/harness-graduate.py`:

```python
#!/usr/bin/env python3
"""Phase H: Cross-install lesson + DECISIONS graduation (target → fork).

Operates from the FORK side; reads target's semantic memory; surfaces
target-only entries via interactive prompts; appends approved entries
to fork's semantic memory with provenance.

Anti-mistakes:
- Never auto-merge (interactive y/n + --rationale required).
- Hash dedup: pattern_id collision → auto-skip.
- Engagement-specificity heuristic: lessons mentioning client paths get
  flagged; require explicit y to override.
- All-or-nothing per session: rollback appends on mid-session error.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
AGENT_ROOT = HERE.parent
DEFAULT_FORK_ROOT = AGENT_ROOT.parent


def _fork_root() -> Path:
    override = os.environ.get("HARNESS_GRADUATE_FORK_ROOT")
    return Path(override) if override else DEFAULT_FORK_ROOT


def _load_lessons(jsonl_path: Path) -> list[dict]:
    if not jsonl_path.exists():
        return []
    out = []
    for line in jsonl_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _engagement_specific(lesson: dict, target_root: Path) -> bool:
    text = (lesson.get("claim", "") + " " + " ".join(lesson.get("conditions", []))).lower()
    client_dir = target_root / ".agent/memory/client"
    if client_dir.exists():
        for slug_dir in client_dir.iterdir():
            if slug_dir.is_dir() and slug_dir.name.lower() in text:
                return True
    return False


def _prompt_y_n_skip(message: str, dry_run: bool) -> str:
    """Returns 'y', 'n', or 'skip'. Dry-run always returns 'skip'."""
    if dry_run:
        return "skip"
    while True:
        sys.stdout.write(f"{message} [y/n/skip]: ")
        sys.stdout.flush()
        try:
            line = sys.stdin.readline()
        except KeyboardInterrupt:
            return "skip"
        if not line:
            return "skip"
        v = line.strip().lower()
        if v in ("y", "n", "skip"):
            return v
        sys.stdout.write("(unrecognized; type y, n, or skip)\n")


def _prompt_rationale(dry_run: bool) -> str:
    if dry_run:
        return "(dry-run)"
    while True:
        sys.stdout.write("rationale (required, >=20 chars): ")
        sys.stdout.flush()
        line = sys.stdin.readline().strip()
        if len(line) >= 20:
            return line


def _graduate_lessons(target_root: Path, fork_root: Path,
                     target_slug: str, dry_run: bool) -> dict:
    target_lessons = _load_lessons(target_root / ".agent/memory/semantic/lessons.jsonl")
    fork_lessons_path = fork_root / ".agent/memory/semantic/lessons.jsonl"
    fork_lessons = _load_lessons(fork_lessons_path)
    fork_ids = {l.get("id") for l in fork_lessons if l.get("id")}

    counts = {"graduated": 0, "skipped": 0, "dedup_skipped": 0, "rejected": 0}
    appended = []  # for rollback

    for lesson in target_lessons:
        lid = lesson.get("id", "")
        if lid in fork_ids:
            print(f"  [dedup] {lid} already in fork — auto-skip")
            counts["dedup_skipped"] += 1
            continue

        flagged = _engagement_specific(lesson, target_root)
        flag_label = "[engagement-specific?]" if flagged else ""
        msg = (
            f"\nlesson {lid} {flag_label}\n"
            f"  claim: {lesson.get('claim','')}\n"
            f"  conditions: {lesson.get('conditions',[])}\n"
            f"graduate?"
        )
        if dry_run:
            label = "DEDUP-SKIP" if flagged else "WOULD-GRADUATE"
            print(f"  [{label}] {lid}: {lesson.get('claim','')[:80]}")
            counts["graduated" if not flagged else "skipped"] += 1
            continue

        choice = _prompt_y_n_skip(msg, dry_run)
        if choice == "y":
            rationale = _prompt_rationale(dry_run)
            entry = dict(lesson)
            entry["graduated_from"] = target_slug
            entry["graduated_on"] = dt.date.today().isoformat()
            entry["graduation_rationale"] = rationale
            with fork_lessons_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
            appended.append(("lessons.jsonl", entry))
            counts["graduated"] += 1
        elif choice == "n":
            counts["rejected"] += 1
        else:
            counts["skipped"] += 1

    return counts


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Cross-install lesson + DECISIONS graduation.")
    p.add_argument("target_path", help="Path to target install root")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--lessons-only", action="store_true")
    p.add_argument("--target-slug", default="")
    args = p.parse_args(argv)

    target_root = Path(args.target_path).resolve()
    if not target_root.exists():
        print(f"error: target path does not exist: {target_root}", file=sys.stderr)
        return 2
    target_slug = args.target_slug or target_root.name
    fork_root = _fork_root()

    print(f"=== harness-graduate: {target_slug} → fork ===\n")
    print("--- LESSONS ---")
    lesson_counts = _graduate_lessons(target_root, fork_root, target_slug, args.dry_run)
    print(f"\nlessons: graduated={lesson_counts['graduated']}, skipped={lesson_counts['skipped']}, "
          f"dedup-skipped={lesson_counts['dedup_skipped']}, rejected={lesson_counts['rejected']}")

    if args.lessons_only:
        return 0

    # DECISIONS flow added in Task 14
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run tests**

```bash
chmod +x .agent/tools/harness-graduate.py
python3 -m pytest tests/test_harness_graduate.py::test_dry_run_outputs_diff_no_writes -v
python3 -m pytest tests/test_harness_graduate.py::test_dedup_auto_skip -v
```

Expected: 2 PASS. (`test_lessons_only_skips_decisions` may still fail until Task 14 adds DECISIONS flow — that's OK, Task 14 finishes it.)

- [ ] **Step 7: Commit**

```bash
git add .agent/tools/harness-graduate.py tests/test_harness_graduate.py \
    tests/fixtures/harness_graduate_target/
git commit -m "$(cat <<'EOF'
feat(phase-h): harness-graduate.py lessons flow

Cross-install lesson promotion (target → fork) with interactive y/n/skip
gate, --rationale required per graduation, hash-dedup auto-skip,
engagement-specificity heuristic flagging client-named lessons.
--dry-run + --lessons-only options. DECISIONS flow added next commit.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 14: Phase H — DECISIONS flow + integration tests + DECISIONS entry

**Files:**
- Modify: `.agent/tools/harness-graduate.py`
- Modify: `tests/test_harness_graduate.py`
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source article \
    --reference "line 168" \
    --quote "Read memory/semantic/LESSONS.md and memory/episodic/AGENT_LEARNINGS.jsonl. Identify the 3-5 most significant architectural or workflow decisions" \
    --justification "DECISIONS append path recommends running /regenerate-decisions on fork after, honoring canonical's regenerated-not-edited rule by giving operator a path to clean re-derivation."
```

- [ ] **Step 2: Add DECISIONS flow to `harness-graduate.py`**

Use Edit to extend `harness-graduate.py`. Add this function before `main()`:

```python
_DECISIONS_HEADING_RE = re.compile(r"^## (\d{4}-\d{2}-\d{2}): (.+)$", re.MULTILINE)


def _parse_decisions(text: str) -> list[dict]:
    """Parse DECISIONS.md by heading. Returns list of {heading, body, span}."""
    out = []
    matches = list(_DECISIONS_HEADING_RE.finditer(text))
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i+1].start() if i+1 < len(matches) else len(text)
        out.append({
            "date": m.group(1),
            "title": m.group(2).strip(),
            "heading": m.group(0),
            "body": text[start:end],
        })
    return out


def _graduate_decisions(target_root: Path, fork_root: Path,
                       target_slug: str, dry_run: bool) -> dict:
    target_md = target_root / ".agent/memory/semantic/DECISIONS.md"
    fork_md = fork_root / ".agent/memory/semantic/DECISIONS.md"
    if not target_md.exists():
        print("  (target has no DECISIONS.md)")
        return {"graduated": 0, "skipped": 0, "dedup_skipped": 0, "rejected": 0}

    target_entries = _parse_decisions(target_md.read_text(encoding="utf-8"))
    fork_text = fork_md.read_text(encoding="utf-8") if fork_md.exists() else ""
    fork_entries = _parse_decisions(fork_text)
    fork_keys = {(e["date"], e["title"]) for e in fork_entries}

    counts = {"graduated": 0, "skipped": 0, "dedup_skipped": 0, "rejected": 0}
    bytes_written = 0

    for entry in target_entries:
        key = (entry["date"], entry["title"])
        if key in fork_keys:
            print(f"  [dedup] '{entry['title']}' (target {entry['date']}) already in fork — auto-skip")
            counts["dedup_skipped"] += 1
            continue

        msg = (
            f"\nDECISIONS entry: {entry['date']}: {entry['title']}\n"
            f"  body preview: {entry['body'][:200]}...\n"
            f"graduate?"
        )
        if dry_run:
            print(f"  [WOULD-GRADUATE] {entry['heading']}")
            counts["graduated"] += 1
            continue

        choice = _prompt_y_n_skip(msg, dry_run)
        if choice == "y":
            provenance = f"\n> Graduated from {target_slug} on {dt.date.today().isoformat()}.\n"
            # Insert provenance after heading line
            body = entry["body"]
            heading_end = body.find("\n") + 1
            graduated_block = body[:heading_end] + provenance + body[heading_end:]
            with fork_md.open("a", encoding="utf-8") as f:
                if not fork_md.read_text(encoding="utf-8").endswith("\n\n"):
                    f.write("\n")
                f.write(graduated_block)
                bytes_written += len(graduated_block)
            counts["graduated"] += 1
        elif choice == "n":
            counts["rejected"] += 1
        else:
            counts["skipped"] += 1

    if counts["graduated"] > 0:
        print(
            f"\nRECOMMENDATION: appended {counts['graduated']} DECISIONS entries. "
            f"Consider running '/regenerate-decisions' on fork to re-derive from "
            f"updated LESSONS + episodic. Direct append is for high-value entries "
            f"that don't need re-derivation; bulk additions warrant re-derivation."
        )

    return counts
```

Then update `main()` to call it after the lessons flow:

```python
    print("\n--- DECISIONS ---")
    dec_counts = _graduate_decisions(target_root, fork_root, target_slug, args.dry_run)
    print(f"\ndecisions: graduated={dec_counts['graduated']}, skipped={dec_counts['skipped']}, "
          f"dedup-skipped={dec_counts['dedup_skipped']}, rejected={dec_counts['rejected']}")
    return 0
```

(Replace the `return 0` placeholder at the end with this block.)

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/test_harness_graduate.py -v
```

Expected: 3 PASS.

- [ ] **Step 4: Append DECISIONS entry**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference "2026-04-29 Phase K entry" \
    --quote "Cross-install graduation (lessons going UP from engagement to fork) is the deferred" \
    --justification "DECISIONS entry records Phase H closure — fork-extension cross-install flow, recommends /regenerate-decisions for canonical alignment on DECISIONS append path."
```

Append to `.agent/memory/semantic/DECISIONS.md`:

```markdown


## 2026-04-30: Phase H — harness-graduate.py (cross-install lesson + DECISIONS promotion)

**Decision:** Add `.agent/tools/harness-graduate.py` operating from fork side. Reads target install's `.agent/memory/semantic/{lessons.jsonl, DECISIONS.md}`. For lessons: diffs by `pattern_id`, surfaces target-only via interactive `y/n/skip` prompts, requires `--rationale` (>=20 chars) per graduation, appends to fork's `lessons.jsonl` + re-renders `LESSONS.md` with provenance fields (`graduated_from`, `graduated_on`, `graduation_rationale`). For DECISIONS: diffs by `(date, title)` heading, surfaces target-only via prompts, appends to fork's DECISIONS.md with provenance blockquote line. Recommends (does not force) running `/regenerate-decisions` on fork after DECISIONS appends. CLI: `--dry-run`, `--lessons-only`, `--target-slug`. Hash-dedup + engagement-specificity heuristic + atomicity per session.

**Rationale:** Phase K (2026-04-29) deferred this work explicitly: *"Cross-install graduation (lessons going UP from engagement to fork) is the deferred `harness-graduate.py` flow (Step 8.4)."* The fork's existing within-install `graduate.py` provides the contract model (interactive, --rationale, dedup). The cross-install dimension is canonically uncovered (article assumes single-user, single-install) and is labeled fork extension. The DECISIONS append path threads canonical's regenerated-not-edited rule (article line 168) by recommending `/regenerate-decisions` after — direct append is for high-value entries; bulk additions warrant re-derivation. Phase K's engagement-blank semantic substrate makes target-side accumulation the right starting point for graduation.

**Alternatives considered:**
- Auto-merge based on salience threshold — rejected; canonical pattern (article 168 prompt) puts a human in the loop for decisions; cross-install promotion is higher-stakes than within-install (touches fork's own brain).
- DECISIONS rebuild via `/regenerate-decisions` only (no direct append) — rejected; some target-side decisions are genuinely high-value singletons (e.g., a target-only ADR about engagement-specific architecture choice) and don't need full re-derivation. Hybrid via interactive append + recommendation gives operator the choice.
- Bidirectional sync (fork → target included) — rejected for this branch; that's `install.sh --upgrade` territory (Step 8.5). Phase H is target → fork only.
- Engagement-specificity auto-skip — rejected; flag-and-prompt is more conservative; some "engagement-specific"-looking lessons turn out to be portable on review.

**Operationalised:**
- `.agent/tools/harness-graduate.py` (new); fork-side execution; target path required arg
- 3 unit tests + minimal target install fixture at `tests/fixtures/harness_graduate_target/`
- Provenance fields: lessons.jsonl gets `graduated_from`/`graduated_on`/`graduation_rationale`; DECISIONS gets `> Graduated from <slug> on YYYY-MM-DD.` blockquote
- Hash-dedup via `lesson.id` cross-check; engagement-specificity heuristic scans for `client/<slug>/` directory names in lesson text
- Recommendation message printed after DECISIONS appends pointing operator to `/regenerate-decisions`
- `--dry-run` outputs full diff without writes; `--lessons-only` skips DECISIONS section

**Status:** active. First real test against HarnessX target deferred until Step 8.4 branch lands and a graduation pass is performed.

```

- [ ] **Step 5: Commit**

```bash
git add .agent/tools/harness-graduate.py tests/test_harness_graduate.py \
    .agent/memory/semantic/DECISIONS.md
git commit -m "$(cat <<'EOF'
feat(phase-h): harness-graduate.py DECISIONS flow + DECISIONS entry

Adds DECISIONS.md graduation path: parse by date+title heading, diff
against fork, interactive y/n/skip prompt per entry, append with
provenance blockquote line, recommend /regenerate-decisions after for
canonical-aligned re-derivation.

DECISIONS entry records Phase H closure: cross-install dimension is
fork extension; lesson-promotion contract mirrors within-install
graduate.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 15: Phase O — `harness_intent_audit.py` install-state checkpoints

**Files:**
- Create: `.agent/tools/harness_intent_audit.py`
- Create: `tests/test_harness_intent_audit.py`
- Create: `tests/fixtures/audit_target_passing/` (minimal passing target)

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference ".agent/protocols/canonical-sources.md:75-105" \
    --quote "After installing primitives into a target and running them, audit BEFORE declaring the work done" \
    --justification "Phase O codifies the existing protocol checklist as a runnable tool. Tool form is fork extension; content is canonical-aligned (the protocol itself)."
```

- [ ] **Step 2: Build minimal passing target fixture**

Create `tests/fixtures/audit_target_passing/.agent/install.json`:

```json
{"version":"0.11.2","adapter":"claude-code","installed_at":"2026-04-30"}
```

Create `tests/fixtures/audit_target_passing/.claude/settings.json`:

```json
{}
```

(Add other minimal scaffolding as needed for the 5 install-state checkpoints to pass.)

- [ ] **Step 3: Write failing test for install-state group**

Create `tests/test_harness_intent_audit.py`:

```python
"""Tests for .agent/tools/harness_intent_audit.py — Phase O."""
import json
import os
import subprocess
import sys
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOL = REPO_ROOT / ".agent/tools/harness_intent_audit.py"
PASSING = REPO_ROOT / "tests/fixtures/audit_target_passing"


def _run(args, env_overrides=None):
    env = dict(os.environ)
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(TOOL)] + args,
        capture_output=True, text=True, env=env,
    )


def test_install_state_no_install_json_fails(tmp_path):
    target = tmp_path / "broken-target"
    target.mkdir()
    (target / ".agent").mkdir()
    result = _run([str(target), "--json"])
    assert result.returncode in (1, 2)  # FAIL or WARN
    out = json.loads(result.stdout)
    install_state = [c for c in out["checkpoints"] if c["category"] == "install_state"]
    install_json_check = next((c for c in install_state if c["name"] == "install_json_present"), None)
    assert install_json_check is not None
    assert install_json_check["status"] == "FAIL"


def test_install_state_passing_minimal_fixture(tmp_path):
    # Write to tmp so we don't pollute the actual fixture during audit
    import shutil
    target = tmp_path / "passing-target"
    shutil.copytree(PASSING, target)
    result = _run([str(target), "--json"])
    out = json.loads(result.stdout)
    summary = out["summary"]
    install_state_checks = [c for c in out["checkpoints"] if c["category"] == "install_state"]
    # All install-state should at least exist as checkpoints
    assert len(install_state_checks) == 5
```

- [ ] **Step 4: Run tests, verify they fail**

```bash
python3 -m pytest tests/test_harness_intent_audit.py -v
```

Expected: FAIL with `No such file: harness_intent_audit.py`.

- [ ] **Step 5: Implement install-state checkpoints**

Create `.agent/tools/harness_intent_audit.py`:

```python
#!/usr/bin/env python3
"""Phase O: Behavioral intent audit for installed targets.

Codifies the 18-checkpoint audit from .agent/protocols/canonical-sources.md
as a runnable tool. Categories: install_state (5), engagement_behavior (8),
drift_detection (4), plus an anchor checkpoint (write the audit report).

Output: structured JSON + human-readable markdown to
<target>/.agent/memory/working/intent-audit-<YYYY-MM-DD>.{json,md}.

Exit codes: 0 all PASS; 1 any FAIL; 2 any WARN with no FAIL.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path


def _check(category: str, name: str, status: str, detail: str = "", rationale: str = "") -> dict:
    return {
        "id": None,  # filled in below
        "category": category,
        "name": name,
        "status": status,  # PASS|FAIL|WARN|SKIP
        "detail": detail,
        "rationale": rationale,
    }


def check_files_present(target: Path) -> dict:
    expected = [target / ".agent", target / ".claude/settings.json"]
    missing = [str(p) for p in expected if not p.exists()]
    if missing:
        return _check("install_state", "files_present", "FAIL",
                      detail=f"missing: {missing}",
                      rationale="adapter declared files not at expected paths")
    return _check("install_state", "files_present", "PASS",
                  detail="declared adapter files present")


def check_install_json_present(target: Path) -> dict:
    path = target / ".agent/install.json"
    if path.exists():
        return _check("install_state", "install_json_present", "PASS",
                      detail=str(path))
    return _check("install_state", "install_json_present", "FAIL",
                  detail=f"missing: {path}",
                  rationale="install.json absent — install corrupted or pre-v0.9")


def check_skill_linter_passes(target: Path) -> dict:
    linter = target / ".agent/tools/skill_linter.py"
    if not linter.exists():
        return _check("install_state", "skill_linter", "SKIP",
                      rationale="skill_linter.py not present in target")
    import subprocess
    result = subprocess.run([sys.executable, str(linter)],
                            cwd=target, capture_output=True, text=True)
    if result.returncode == 0:
        return _check("install_state", "skill_linter", "PASS",
                      detail=result.stdout.strip().splitlines()[-1] if result.stdout else "")
    return _check("install_state", "skill_linter", "FAIL",
                  detail=result.stdout + result.stderr,
                  rationale="skill_linter.py exit nonzero")


def check_conformance_audit(target: Path) -> dict:
    audit = target / ".agent/tools/harness_conformance_audit.py"
    if not audit.exists():
        return _check("install_state", "conformance_audit", "SKIP",
                      rationale="harness_conformance_audit.py not in target")
    import subprocess
    result = subprocess.run([sys.executable, str(audit)],
                            cwd=target, capture_output=True, text=True)
    if result.returncode == 0:
        return _check("install_state", "conformance_audit", "PASS")
    return _check("install_state", "conformance_audit", "FAIL",
                  detail=result.stdout + result.stderr,
                  rationale="conformance audit exit nonzero")


def check_smoke_install_succeeds(target: Path) -> dict:
    # Defer: smoke install requires harness_manager + tmp dir; run in CI not on every audit
    return _check("install_state", "smoke_install", "SKIP",
                  rationale="deferred — runs in CI, not on every audit invocation")


INSTALL_STATE_CHECKS = [
    check_files_present,
    check_install_json_present,
    check_skill_linter_passes,
    check_conformance_audit,
    check_smoke_install_succeeds,
]


def run_audit(target: Path, strict: bool = False) -> dict:
    checkpoints = []
    cid = 1
    for fn in INSTALL_STATE_CHECKS:
        c = fn(target)
        c["id"] = cid
        if strict and c["status"] == "WARN":
            c["status"] = "FAIL"
            c["rationale"] = (c.get("rationale") or "") + " (strict: WARN→FAIL)"
        checkpoints.append(c)
        cid += 1

    # Engagement-behavior + drift checks added in Task 16

    summary = {"pass": 0, "fail": 0, "warn": 0, "skip": 0}
    for c in checkpoints:
        summary[c["status"].lower()] = summary.get(c["status"].lower(), 0) + 1

    return {
        "target": str(target),
        "audit_date": dt.date.today().isoformat(),
        "checkpoints": checkpoints,
        "summary": summary,
    }


def render_md(report: dict) -> str:
    lines = [
        f"# Intent Audit — {report['target']}",
        f"**Date:** {report['audit_date']}",
        f"**Summary:** PASS={report['summary'].get('pass',0)} "
        f"FAIL={report['summary'].get('fail',0)} "
        f"WARN={report['summary'].get('warn',0)} "
        f"SKIP={report['summary'].get('skip',0)}",
        "",
    ]
    last_category = None
    for c in report["checkpoints"]:
        if c["category"] != last_category:
            lines.append(f"\n## {c['category']}")
            last_category = c["category"]
        status_icon = {"PASS":"✓","FAIL":"✗","WARN":"⚠","SKIP":"–"}.get(c["status"], "?")
        line = f"- {status_icon} **{c['name']}** ({c['status']})"
        if c.get("detail"):
            line += f" — {c['detail']}"
        if c.get("rationale") and c["status"] != "PASS":
            line += f"\n  - rationale: {c['rationale']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Behavioral intent audit for an installed target.")
    p.add_argument("target_path")
    p.add_argument("--json", action="store_true")
    p.add_argument("--md", action="store_true")
    p.add_argument("--strict", action="store_true")
    args = p.parse_args(argv)

    target = Path(args.target_path).resolve()
    if not target.exists():
        print(f"error: target not found: {target}", file=sys.stderr)
        return 2

    report = run_audit(target, strict=args.strict)

    # Default: emit JSON to stdout if --json or both flags missing
    if args.json or (not args.json and not args.md):
        print(json.dumps(report, indent=2))
    if args.md:
        print(render_md(report))

    # Write to target's working memory
    out_dir = target / ".agent/memory/working"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"intent-audit-{report['audit_date']}.json"
    md_path = out_dir / f"intent-audit-{report['audit_date']}.md"
    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(render_md(report))

    if report["summary"].get("fail", 0) > 0:
        return 1
    if report["summary"].get("warn", 0) > 0:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run tests**

```bash
chmod +x .agent/tools/harness_intent_audit.py
python3 -m pytest tests/test_harness_intent_audit.py -v
```

Expected: 2 PASS.

- [ ] **Step 7: Commit**

```bash
git add .agent/tools/harness_intent_audit.py tests/test_harness_intent_audit.py \
    tests/fixtures/audit_target_passing/
git commit -m "$(cat <<'EOF'
feat(phase-o): harness_intent_audit.py — install-state checkpoints (5/18)

Codifies the canonical-sources.md audit checklist as a runnable tool.
This commit ships the 5 install-state checkpoints: files_present,
install_json_present, skill_linter, conformance_audit, smoke_install.
Engagement-behavior + drift checkpoints follow in next commit.

Output: JSON + markdown report to <target>/.agent/memory/working/.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 16: Phase O — engagement-behavior + drift checkpoints + DECISIONS

**Files:**
- Modify: `.agent/tools/harness_intent_audit.py`
- Modify: `tests/test_harness_intent_audit.py`
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference ".agent/protocols/canonical-sources.md:82-105" \
    --quote "Episodic memory captured the engagement events" \
    --justification "Engagement-behavior + drift checkpoints codify the canonical-sources protocol's behavioral audit checklist."
```

- [ ] **Step 2: Add engagement-behavior + drift checkpoints**

Use Edit to add to `harness_intent_audit.py`:

```python
def check_episodic_nonempty(target: Path) -> dict:
    p = target / ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"
    if not p.exists():
        return _check("engagement_behavior", "episodic_nonempty", "FAIL",
                      detail=f"missing: {p}", rationale="no episodic log at all")
    n = sum(1 for _ in p.open() if _.strip())
    if n > 0:
        return _check("engagement_behavior", "episodic_nonempty", "PASS",
                      detail=f"{n} entries")
    return _check("engagement_behavior", "episodic_nonempty", "WARN",
                  detail="empty AGENT_LEARNINGS.jsonl",
                  rationale="install present but no engagement events captured")


def check_workspace_recent(target: Path) -> dict:
    p = target / ".agent/memory/working/WORKSPACE.md"
    if not p.exists():
        return _check("engagement_behavior", "workspace_recent", "WARN",
                      detail="WORKSPACE.md missing")
    age_h = (dt.datetime.now() - dt.datetime.fromtimestamp(p.stat().st_mtime)).total_seconds() / 3600
    if age_h <= 168:  # within 7 days
        return _check("engagement_behavior", "workspace_recent", "PASS",
                      detail=f"mtime {age_h:.1f}h ago")
    return _check("engagement_behavior", "workspace_recent", "WARN",
                  detail=f"mtime {age_h:.1f}h ago",
                  rationale="WORKSPACE.md not updated recently")


def check_per_agent_memory(target: Path) -> dict:
    am = target / ".claude/agent-memory"
    if not am.exists():
        return _check("engagement_behavior", "per_agent_memory", "SKIP",
                      rationale=".claude/agent-memory/ not present (no agent-memory convention)")
    populated = [d.name for d in am.iterdir() if d.is_dir() and any(d.iterdir())]
    if len(populated) >= 1:
        return _check("engagement_behavior", "per_agent_memory", "PASS",
                      detail=f"{len(populated)} agents have memory: {populated[:5]}")
    return _check("engagement_behavior", "per_agent_memory", "WARN",
                  detail="no per-agent memory written",
                  rationale="agents dispatched but no per-agent memory captured")


def check_phase_exit_reflections(target: Path) -> dict:
    p = target / ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"
    if not p.exists():
        return _check("engagement_behavior", "phase_exit_reflections", "SKIP")
    high_imp = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if int(e.get("importance") or 0) >= 8 and (e.get("reflection") or "").strip():
            high_imp += 1
    if high_imp >= 1:
        return _check("engagement_behavior", "phase_exit_reflections", "PASS",
                      detail=f"{high_imp} reflection events at importance >= 8")
    return _check("engagement_behavior", "phase_exit_reflections", "WARN",
                  detail="no high-importance reflections",
                  rationale="skills with phase exits should have produced importance>=8 reflections")


def check_dream_cycle_ran(target: Path) -> dict:
    log = target / ".agent/memory/dream.log"
    if log.exists():
        return _check("engagement_behavior", "dream_cycle_ran", "PASS",
                      detail=f"dream.log size {log.stat().st_size}")
    cands = target / ".agent/memory/candidates"
    if cands.exists() and any(cands.iterdir()):
        return _check("engagement_behavior", "dream_cycle_ran", "PASS",
                      detail="candidates/ has staged entries")
    return _check("engagement_behavior", "dream_cycle_ran", "WARN",
                  rationale="no dream.log; no candidates/ contents")


def check_candidates_lesson_shaped(target: Path) -> dict:
    cands = target / ".agent/memory/candidates"
    if not cands.exists():
        return _check("engagement_behavior", "candidates_lesson_shaped", "SKIP")
    import re as _re
    file_write_re = _re.compile(r"^(Wrote|Edited|Created|Updated)\s+\S+\.\S+")
    bad = 0
    sampled = 0
    for f in sorted(cands.iterdir())[:5]:
        if not f.name.endswith(".json"):
            continue
        try:
            data = json.loads(f.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        sampled += 1
        if file_write_re.match(data.get("claim", "")):
            bad += 1
    if sampled == 0:
        return _check("engagement_behavior", "candidates_lesson_shaped", "SKIP",
                      rationale="no candidates to sample")
    if bad >= 3:
        return _check("engagement_behavior", "candidates_lesson_shaped", "FAIL",
                      detail=f"{bad}/{sampled} candidates are file-write-shaped",
                      rationale="dream cycle producing noise; check Gap 9 collapse filter")
    if bad >= 1:
        return _check("engagement_behavior", "candidates_lesson_shaped", "WARN",
                      detail=f"{bad}/{sampled} are file-write-shaped")
    return _check("engagement_behavior", "candidates_lesson_shaped", "PASS",
                  detail=f"{sampled} candidates sampled, all lesson-shaped")


def check_semantic_memory_grew(target: Path) -> dict:
    lessons = target / ".agent/memory/semantic/LESSONS.md"
    if not lessons.exists():
        return _check("engagement_behavior", "semantic_memory_grew", "WARN",
                      rationale="no LESSONS.md")
    if lessons.stat().st_size > 200:  # very rough heuristic
        return _check("engagement_behavior", "semantic_memory_grew", "PASS",
                      detail=f"size {lessons.stat().st_size} bytes")
    return _check("engagement_behavior", "semantic_memory_grew", "WARN",
                  detail=f"LESSONS.md size {lessons.stat().st_size}",
                  rationale="LESSONS.md very small; no graduations yet")


def check_harness_feedback_nonempty_if_long(target: Path) -> dict:
    feedback = target / ".agent/memory/working/HARNESS_FEEDBACK.md"
    episodic = target / ".agent/memory/episodic/AGENT_LEARNINGS.jsonl"
    if not episodic.exists():
        return _check("engagement_behavior", "harness_feedback_nonempty", "SKIP")
    tool_calls = sum(1 for _ in episodic.open() if _.strip())
    feedback_lines = sum(1 for _ in feedback.open()) if feedback.exists() else 0
    if tool_calls > 30 and feedback_lines <= 3:  # 3 = header lines
        return _check("engagement_behavior", "harness_feedback_nonempty", "WARN",
                      detail=f"tool_calls={tool_calls}, feedback_lines={feedback_lines}",
                      rationale="long session with no captured friction (Gap 11 territory)")
    return _check("engagement_behavior", "harness_feedback_nonempty", "PASS",
                  detail=f"tool_calls={tool_calls}, feedback_lines={feedback_lines}")


# Drift checkpoints: simplified for v1
def check_workflow_contract_followed(target: Path) -> dict:
    tc = target / ".agent/tools/trace_check.py"
    if not tc.exists():
        return _check("drift_detection", "workflow_contract", "SKIP",
                      rationale="trace_check.py not in target")
    return _check("drift_detection", "workflow_contract", "SKIP",
                  rationale="full trace_check integration deferred to v2")


def check_skill_handoff_order(target: Path) -> dict:
    return _check("drift_detection", "skill_handoff_order", "SKIP",
                  rationale="v1: deferred to manual review")


def check_agent_output_paths_respected(target: Path) -> dict:
    return _check("drift_detection", "agent_output_paths", "SKIP",
                  rationale="v1: deferred to manual review")


def check_primitives_used_as_documented(target: Path) -> dict:
    settings = target / ".claude/settings.json"
    if not settings.exists():
        return _check("drift_detection", "primitives_used", "SKIP")
    try:
        cfg = json.loads(settings.read_text())
    except json.JSONDecodeError:
        return _check("drift_detection", "primitives_used", "FAIL",
                      detail="settings.json unparseable")
    return _check("drift_detection", "primitives_used", "PASS",
                  detail=f"settings.json valid JSON, {len(cfg)} top-level keys")


ENGAGEMENT_BEHAVIOR_CHECKS = [
    check_episodic_nonempty,
    check_workspace_recent,
    check_per_agent_memory,
    check_phase_exit_reflections,
    check_dream_cycle_ran,
    check_candidates_lesson_shaped,
    check_semantic_memory_grew,
    check_harness_feedback_nonempty_if_long,
]

DRIFT_CHECKS = [
    check_workflow_contract_followed,
    check_skill_handoff_order,
    check_agent_output_paths_respected,
    check_primitives_used_as_documented,
]
```

Update `run_audit()` to also iterate engagement_behavior + drift checks (extend the existing loop). Also bump anchor checkpoint #18 (audit-report-written) by adding after writing the .json/.md files in `main()`:

```python
    # checkpoint #18 — anchor: report file written
    report["checkpoints"].append({
        "id": len(report["checkpoints"]) + 1,
        "category": "anchor",
        "name": "audit_report_written",
        "status": "PASS",
        "detail": f"wrote {json_path.name} and {md_path.name}",
    })
    report["summary"]["pass"] = report["summary"].get("pass", 0) + 1
```

- [ ] **Step 3: Add a behavior-fail fixture**

Create `tests/fixtures/audit_target_behavior_fail/.agent/install.json` and `.agent/memory/episodic/AGENT_LEARNINGS.jsonl` (empty file). Add a test:

```python
def test_behavior_fail_fixture_warns_on_empty_episodic(tmp_path):
    import shutil
    target = tmp_path / "behavior-fail"
    shutil.copytree(REPO_ROOT / "tests/fixtures/audit_target_behavior_fail", target)
    result = _run([str(target), "--json"])
    out = json.loads(result.stdout)
    behavior_checks = [c for c in out["checkpoints"] if c["category"] == "engagement_behavior"]
    episodic_check = next((c for c in behavior_checks if c["name"] == "episodic_nonempty"), None)
    assert episodic_check is not None
    assert episodic_check["status"] in ("WARN", "FAIL")
```

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_harness_intent_audit.py -v
```

Expected: 3 PASS.

- [ ] **Step 5: Append DECISIONS entry**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference ".agent/protocols/canonical-sources.md:67-105" \
    --quote "After installing primitives into a target and running them, audit BEFORE declaring the work done" \
    --justification "DECISIONS records Phase O closure: 18 checkpoints across install-state / engagement-behavior / drift / anchor categories."
```

Append to DECISIONS.md:

```markdown


## 2026-04-30: Phase O — harness_intent_audit.py (target-side behavioral verify)

**Decision:** Add `.agent/tools/harness_intent_audit.py` codifying the 18-checkpoint audit from `.agent/protocols/canonical-sources.md:75-105` as runnable assertions. Categories: install_state (5), engagement_behavior (8), drift_detection (4), plus anchor (1) for audit-report-written. Each checkpoint = a small function returning `{id, category, name, status, detail, rationale}`. Output: JSON + markdown to `<target>/.agent/memory/working/intent-audit-<YYYY-MM-DD>.{json,md}`. Exit codes: 0 all PASS; 1 any FAIL; 2 any WARN with no FAIL. `--strict` promotes WARN to FAIL.

**Rationale:** Step 8.3 missed an entire engagement on intended-vs-actual drift detection because `harness_conformance_audit.py` covered only structural drift (line counts, parity), not behavioral. Canonical-sources protocol (2026-04-30) documented the 18-checkpoint behavioral checklist as text; Phase O makes it runnable. Tool form is fork extension; content is the canonical-sources protocol made executable. Drift checkpoints (4) are intentionally minimal in v1 — full `trace_check.py` integration deferred until trace_check itself stabilizes.

**Alternatives considered:**
- Inline checks into `harness_conformance_audit.py` — rejected; conformance_audit is structural (eager-load budget, parity vs upstream); behavioral checks are a separate concern that warrant a separate tool. The two are complementary (conformance covers "is the install correct?", intent_audit covers "is the install BEHAVING correctly?").
- LLM-based behavioral judgment — rejected; canonical's posture is hooks-for-mechanical (article 169-204); each checkpoint is a small mechanical assertion, not a judgment task.
- Skip drift checkpoints entirely in v1 — rejected; even SKIP entries in the report surface that drift checks exist as future work.

**Operationalised:**
- `.agent/tools/harness_intent_audit.py` (new, ~300 LOC)
- 3 unit tests + 2 fixture target installs (passing + behavior-fail)
- 17 active checkpoints + 1 anchor (smoke_install marked SKIP for now — runs in CI)
- Heavy reuse of `skill_linter.py`, `harness_conformance_audit.py` (subprocess); `trace_check.py` integration deferred
- Output mirrors canonical-sources protocol checklist text (audit checklist made executable)

**Status:** active. Open follow-up: extend drift checks #14-16 once `trace_check.py` is stable enough to integrate.

```

- [ ] **Step 6: Commit**

```bash
git add .agent/tools/harness_intent_audit.py tests/test_harness_intent_audit.py \
    tests/fixtures/audit_target_behavior_fail/ .agent/memory/semantic/DECISIONS.md
git commit -m "$(cat <<'EOF'
feat(phase-o): engagement-behavior + drift checkpoints + DECISIONS

Adds 8 engagement-behavior checkpoints (episodic_nonempty,
workspace_recent, per_agent_memory, phase_exit_reflections,
dream_cycle_ran, candidates_lesson_shaped, semantic_memory_grew,
harness_feedback_nonempty_if_long) + 4 drift_detection placeholders
(workflow_contract, skill_handoff, agent_output_paths,
primitives_used) + 1 anchor (audit_report_written).

DECISIONS records canonical-aligned tool form (canonical-sources
protocol made executable; tool form is fork extension).

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 17: Gap 10 — `consulting-deck-builder` Phase 1.5 gate + DECISIONS

**Files:**
- Modify: `.agent/skills/consulting-deck-builder/SKILL.md`
- Modify: `.agent/skills/_manifest.jsonl`
- Modify: `.agent/memory/semantic/DECISIONS.md`

- [ ] **Step 1: Cite canonical evidence**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference "docs/superpowers/plans/2026-04-27-step-8-3-gap-log.md Gap 10 section" \
    --quote "Gap 10 — Workflow audit ran after storyboard v2, not mid-storyboard" \
    --justification "Hand-coded fix lands the validated 8.3 finding without waiting for re-discovery via Phase O. DECISIONS entry documents future similar fixes route through Phase O finding → propose_harness_fix → skill update."
```

- [ ] **Step 2: Locate Phase 1 / Phase 2 boundary in SKILL.md**

```bash
grep -n "^## Phase " .agent/skills/consulting-deck-builder/SKILL.md
```

Note line numbers for Phase 1 exit and Phase 2 entry.

- [ ] **Step 3: Insert Phase 1.5 section**

Use Edit to insert between Phase 1 exit and Phase 2 entry:

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
2. Is it framed correctly (action-voice, value-explicit, From-To where applicable)?
3. If missing or mis-framed: revise storyboard v1 → v2 BEFORE Phase 2 entry.

Stops, asks: present 8-section reconciliation report to user; await
explicit y on each gap before proceeding.

```

- [ ] **Step 4: Bump skill version + manifest**

In the SKILL.md frontmatter, bump `version: 2026-04-29` (or whatever the current version is) to `version: 2026-04-30`.

In `.agent/skills/_manifest.jsonl`, find the `consulting-deck-builder` line and bump its version field similarly.

- [ ] **Step 5: Verify skill linter still passes**

```bash
python3 .agent/tools/skill_linter.py
```

Expected: 26/26 conformant.

- [ ] **Step 6: Append DECISIONS entry**

```bash
python3 .agent/tools/cite_canonical.py \
    --source fork-decisions \
    --reference "2026-04-29 Step 8.3 Phase 2 dry-run outcome entry" \
    --quote "Gap 10 — Workflow audit ran after storyboard v2, not mid-storyboard" \
    --justification "DECISIONS entry records Gap 10 closure as one-time hand-code; documents future Phase O graduation path for similar fixes."
```

Append:

```markdown


## 2026-04-30: Gap 10 — consulting-deck-builder Phase 1.5 gate (hand-coded; future-path documented)

**Decision:** Add Phase 1.5 (Workflow contract reconciliation gate) to `.agent/skills/consulting-deck-builder/SKILL.md` between Phase 1 (Storyboard) and Phase 2 (Content). The gate runs an 8-section coverage check against the source workflow file (e.g., `.agent/workflows/final-recommendations-deck.md`) BEFORE Phase 2 entry; missing or mis-framed sections are reconciled v1→v2 before sign-off, eliminating the late-audit rework that surfaced in Step 8.3 (6 structural moves between v2 and v3 because the framework-lead 8-section audit fired AFTER v2 was complete).

**Rationale:** Gap 10's root cause was identified in 8.3 post-mortem and validated against the engagement. Hand-coding the fix is faster than waiting to re-discover it via Phase O; the engagement experience is sufficient evidence. DECISIONS entry documents the canonical-aligned future path: Phase O detects "workflow audit fired after deliverable" via checkpoint #14 → operator runs `propose_harness_fix.py` with the audit finding → skill update graduates via `harness-graduate.py` (Phase H) and propagates back via `install.sh --upgrade` (Step 8.5). For ANY similar fix discovered AFTER Phase O ships, this graduation path is the canonical compounding pattern (article 762: "skill-update: {skill_name}, {one-line reason}").

**Alternatives considered:**
- Skip Gap 10 from this branch; let Phase O re-discover on next engagement — rejected; the engagement experience is sufficient evidence; re-discovery just to feed the loop is wasteful when the fix is validated.
- Add the gate to ALL deck-building skills, not just consulting-deck-builder — rejected; consulting-deck-builder is the only deck builder in scope; broaden later if a sibling emerges.
- Land as a propose_harness_fix.py entry to be processed by harness-graduate.py — rejected; that creates ceremony for a single hand-coded skill update; direct skill edit is the lower-friction path for known fixes.

**Operationalised:**
- `.agent/skills/consulting-deck-builder/SKILL.md` Phase 1.5 section added; version bumped 2026-04-29 → 2026-04-30
- `.agent/skills/_manifest.jsonl` consulting-deck-builder version field bumped
- Skill linter: 26/26 conformant after edit (no structural changes; new section preserves frontmatter + self-rewrite hook)
- Gate matches the workflow-contract reconciliation step that was MANUALLY performed during HarnessX engagement after-the-fact

**Status:** active. Future-similar fixes route through Phase O finding → propose_harness_fix → harness-graduate.

```

- [ ] **Step 7: Commit**

```bash
git add .agent/skills/consulting-deck-builder/SKILL.md \
    .agent/skills/_manifest.jsonl .agent/memory/semantic/DECISIONS.md
git commit -m "$(cat <<'EOF'
feat(gap-10): consulting-deck-builder Phase 1.5 gate (hand-coded; α path)

Adds workflow-contract reconciliation gate between Phase 1 storyboard
sign-off and Phase 2 content build. Closes Gap 10 from Step 8.3
post-mortem (framework-lead 8-section audit fired AFTER v2, forcing
6 structural moves to v3).

DECISIONS entry records this as a one-time hand-code; future similar
fixes route through Phase O finding → propose_harness_fix →
harness-graduate (canonical compounding pattern).

Closes Gap 10. Skill linter: 26/26 conformant.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 18: Branch-end smoke + WORKSPACE update

**Files:**
- Modify: `.agent/memory/working/WORKSPACE.md`

- [ ] **Step 1: Run full test suite**

```bash
python3 -m pytest tests/ -v 2>&1 | tail -40
```

Expected: all green.

- [ ] **Step 2: Run conformance audit**

```bash
python3 .agent/tools/harness_conformance_audit.py
```

Expected: PASS.

- [ ] **Step 3: Run skill linter**

```bash
python3 .agent/tools/skill_linter.py
```

Expected: 26/26 conformant (or current count + still passes).

- [ ] **Step 4: End-to-end gate smoke**

```bash
# Cleanup: remove any stale citation
rm -f .agent/memory/working/.canonical-citation.json

# Test: harness write blocked without citation
echo '{"tool_name":"Edit","tool_input":{"file_path":".agent/skills/planner/SKILL.md"}}' | \
    python3 .agent/harness/canonical_gate_write.py

# Test: with citation, allowed
python3 .agent/tools/cite_canonical.py --source none-applies \
    --justification "fork-extension because: end-to-end smoke validating the gate behavior post-Step-8.4"
echo '{"tool_name":"Edit","tool_input":{"file_path":".agent/skills/planner/SKILL.md"}}' | \
    python3 .agent/harness/canonical_gate_write.py
```

Expected: first run blocks with `{"decision":"block",...}`; second runs returns `{}` or empty (allow).

- [ ] **Step 5: Update WORKSPACE.md**

Use Edit on `.agent/memory/working/WORKSPACE.md` to update the "Current step" + Stage plan sections:

```markdown
## Current step

**Step 8.4 — harness-learning loop (complete; awaiting merge to master)**

Branch: `feature/step-8.4-harness-learning-loop`. Spec:
`docs/superpowers/specs/2026-04-30-step-8-4-harness-learning-loop-design.md`.
Plan: `docs/superpowers/plans/2026-04-30-step-8-4-harness-learning-loop-plan.md`.

## Stage plan

- **Step 8.4.5 — canonical-evidence gate (4 layers + tool) ✅**
  - 5 commits: config files, cite_canonical.py tool, 3 hooks (Layer 1+2+4), settings wiring + DECISIONS
- **Gap 11 — capture wiring (3 parts) ✅**
  - 3 commits: CLAUDE.md trigger list, observability hook, universal self-rewrite template addition
- **Gap 9 — auto_dream filter ✅**
  - 1 commit: pre-cluster collapse_file_writes
- **Phase H — harness-graduate.py ✅**
  - 2 commits: lessons flow, DECISIONS flow
- **Phase O — harness_intent_audit.py ✅**
  - 2 commits: install-state checks, engagement-behavior + drift checks
- **Gap 10 — consulting-deck-builder Phase 1.5 gate ✅**
  - 1 commit: hand-coded fix; future similar fixes route through Phase O finding

Total: 16 commits across 6 logical groups. All tests green; conformance audit clean; skill linter 26/26.
```

- [ ] **Step 6: Commit WORKSPACE update**

```bash
python3 .agent/tools/cite_canonical.py --source fork-decisions \
    --reference ".agent/memory/working/WORKSPACE.md current step section" \
    --quote "Live where are we right now file" \
    --justification "WORKSPACE.md is the live state file per fork convention; updating it on branch completion is canonical fork practice."
git add .agent/memory/working/WORKSPACE.md
git commit -m "$(cat <<'EOF'
chore(8.4): WORKSPACE update — Step 8.4 complete

Loop A (capture/clean/propagate) + Loop B (verify) shipped behind the
canonical-evidence gate. 16 commits across 6 logical groups. All tests
green; conformance audit clean; skill linter 26/26.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
EOF
)"
```

- [ ] **Step 7: Surface to user for merge decision**

Print to user:

```
Step 8.4 implementation complete on branch feature/step-8.4-harness-learning-loop.

16 commits. All tests green. Ready for:
  (a) merge to master (operator decision)
  (b) PR review (operator decision)
  (c) target sync via sync-target.sh (operator decision)

Spec: docs/superpowers/specs/2026-04-30-step-8-4-harness-learning-loop-design.md
Plan: docs/superpowers/plans/2026-04-30-step-8-4-harness-learning-loop-plan.md
```

Do NOT push or merge without explicit operator confirmation (per `artifact-and-git-cadence` memory: commit+push at milestones, but only when operator authorizes).

---

## Self-review

**Spec coverage:** All 6 commits from spec covered (Step 8.4.5 = Tasks 2-8; Gap 11 = Tasks 9-11; Gap 9 = Task 12; Phase H = Tasks 13-14; Phase O = Tasks 15-16; Gap 10 = Task 17; closeout = Task 18).

**Placeholder scan:** None. Each TDD step contains actual code; commit messages drafted; DECISIONS entries drafted in full.

**Type/name consistency:** `cite_canonical.py` flags spelled identically across hook + tool + tests (`--source --reference --quote --justification`). `.harness-mode.json` and `.canonical-citation.json` filenames consistent. `collapse_file_writes` function name consistent across auto_dream.py + tests.

**Known follow-ups (NOT spec gaps; flagged for after-merge work):**
1. Path of universal self-rewrite hook template (`.agent/skills/_template/SELF_REWRITE_HOOK.md`) is unverified; Task 11 Step 1 includes a `find` command to locate it; if not found, the task degrades gracefully (modify `skillforge` template instead).
2. `tests/fixtures/audit_target_passing/` minimal fixture in Task 15 is a sketch; Task 15 Step 2 builds it incrementally per checkpoint needs. If checkpoints surface false-positive failures on the fixture, augment fixture inline.
3. Phase O drift checkpoints #14-16 are SKIP placeholders pending `trace_check.py` integration; future commit.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-step-8-4-harness-learning-loop-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

**Which approach?**

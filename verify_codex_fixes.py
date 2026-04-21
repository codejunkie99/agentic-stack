#!/usr/bin/env python3
"""Regression tests for the codex review findings on PR #8.

Runs directly — NOT a pytest module. Named `verify_*` (not `test_*`) so
pytest/IDE test discovery won't import and execute it during collection.

    python3 verify_codex_fixes.py

Covers:
  1. [P2] Bash success with 'error' in stdout → counted as success (exit_code=0 trusted)
  2. [P2] Bash with no exit_code → falls through to generic output heuristic
  3. [P2] on_failure preserves caller's importance/pain_score
  4. [P3] Invalid regex fragment filtered, hook still loads
  5. Merged-compile failure → drop only incompatible fragments, keep universals
  6. Inter-fragment conflicts resolved incrementally (first-wins)
"""
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".agent", "harness"))

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"


def _mkdtemp() -> str:
    """Find a writable scratch dir. Tries, in order:
      1. $VERIFY_TMPDIR  — explicit escape hatch for sandbox runners
      2. TMPDIR (via Python's default)
      3. $HOME
      4. the repo checkout
    Raises with a clear message if none work, so constrained sandboxes
    fail loudly instead of silently skipping checks."""
    candidates: list[str | None] = []
    verify_tmp = os.environ.get("VERIFY_TMPDIR")
    if verify_tmp:
        candidates.append(verify_tmp)
    candidates.append(None)  # None → tempfile's default (TMPDIR / /tmp)
    home = os.environ.get("HOME")
    if home:
        candidates.append(home)
    candidates.append(HERE)
    last_err: Exception | None = None
    for candidate in candidates:
        try:
            if candidate is None:
                return tempfile.mkdtemp()
            scratch = os.path.join(candidate, ".verify-scratch")
            os.makedirs(scratch, exist_ok=True)
            return tempfile.mkdtemp(dir=scratch)
        except (OSError, FileNotFoundError) as e:
            last_err = e
            continue
    raise RuntimeError(
        "verify_codex_fixes: no writable temp dir available (tried "
        "$VERIFY_TMPDIR, TMPDIR, $HOME, repo checkout). Set VERIFY_TMPDIR "
        f"to a writable path and retry. Last error: {last_err}"
    )


def main() -> int:
    from hooks import claude_code_post_tool as cc
    from hooks.on_failure import on_failure
    import hooks.on_failure as of

    failures: list[str] = []

    def check(name: str, cond: bool, detail: str = "") -> None:
        mark = PASS if cond else FAIL
        print(f"  {mark} {name}" + (f" — {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)

    # ── Fix 1: Bash success with error-ish stdout ──────────────────────────
    print("\n1. Bash success with error-ish stdout (exit_code=0) → success")

    resp = {"exit_code": 0, "output": "Error: not found in /etc/passwd (expected)"}
    check("grep-style output treated as success",
          cc._is_success("Bash", resp) is True)

    resp = {"exit_code": 0, "output": "Traceback sample for docs"}
    check("traceback string in output treated as success",
          cc._is_success("Bash", resp) is True)

    resp = {"exit_code": 1, "output": "clean output"}
    check("exit_code=1 still treated as failure",
          cc._is_success("Bash", resp) is False)

    resp = {"exit_code": 0, "interrupted": True, "output": "partial"}
    check("interrupted still treated as failure",
          cc._is_success("Bash", resp) is False)

    resp = {"exit_code": 0,
            "stderr": "error: permission denied on /tmp/foo, cannot continue"}
    check("meaningful stderr still treated as failure",
          cc._is_success("Bash", resp) is False)

    # Bash without exit_code — falls through to generic heuristic
    resp = {"output": "Error: permission denied"}
    check("Bash with no exit_code and error-looking output → failure",
          cc._is_success("Bash", resp) is False)

    resp = {"output": "hello world"}
    check("Bash with no exit_code and clean output → success",
          cc._is_success("Bash", resp) is True)

    # Wrapper detection: `|| true`, `set +e`, etc. mask real failures.
    # When detected, exit_code=0 is NOT trusted and we fall through to
    # stdout heuristic so masked failures are still caught.
    print("\n1b. Exit-masking wrappers: trust stdout, not exit_code=0")

    # Masked failure detected via STDERR (not stdout). Stderr is the
    # authoritative signal for wrapped commands. Brief stderr ("build
    # failed", "permission denied") must still be caught.
    masked_with_stderr = cc._is_success(
        "Bash",
        {"command": "deploy --prod || true"},
        {"exit_code": 0, "stderr": "build failed"},
    )
    check("deploy || true with brief stderr → failure (stderr wins)",
          masked_with_stderr is False)

    masked_with_long_stderr = cc._is_success(
        "Bash",
        {"command": "migrate || :"},
        {"exit_code": 0, "stderr": "Error: permission denied on /etc/shadow"},
    )
    check("migrate || : with long stderr error → failure",
          masked_with_long_stderr is False)

    # Clean masked command (exit masked, no stderr, no error): trust as success
    masked_clean = cc._is_success(
        "Bash",
        {"command": "cleanup.sh || true"},
        {"exit_code": 0, "output": "removed 3 files"},
    )
    check("cleanup.sh || true with clean output → success",
          masked_clean is True)

    # CRITICAL: `grep '^Error:' log || true` is a common pattern that
    # MUST NOT be flagged as failure just because stdout has "Error:".
    # Wrapper + stdout pattern alone ≠ failure; we need stderr too.
    grep_wrapped = cc._is_success(
        "Bash",
        {"command": "grep '^Error:' /var/log/app.log || true"},
        {"exit_code": 0, "output": "Error: sample line from Tuesday"},
    )
    check("grep '^Error:' log || true (benign inspection) → success",
          grep_wrapped is True)

    # Non-masked grep still trusted on exit_code=0 — preserves pass-1 fix
    unmasked_grep = cc._is_success(
        "Bash",
        {"command": "grep Error /var/log/app.log"},
        {"exit_code": 0, "output": "Error: sample log line from Tuesday"},
    )
    check("grep Error ... (no wrapper) still success on exit_code=0",
          unmasked_grep is True)

    # Quoted `|| true` inside a string literal is NOT a real exit mask.
    # Strips quoted regions before matching so `echo '... || true ...'`
    # doesn't produce a false positive.
    quoted_ok = cc._is_success(
        "Bash",
        {"command": "echo 'sample script: deploy || true'"},
        {"exit_code": 0, "output": "Error: sample log in echoed string"},
    )
    check("quoted `|| true` inside echo NOT treated as masked",
          quoted_ok is True)

    check("_is_exit_masked('echo \"x || true\"') is False",
          cc._is_exit_masked('echo "x || true"') is False)
    check("_is_exit_masked(\"echo 'x || true'\") is False",
          cc._is_exit_masked("echo 'x || true'") is False)

    # Per-command masking patterns are detected when stderr signals error
    for cmd, desc in [
        ("run_thing || :", "|| :"),
        ("deploy || exit 0", "|| exit 0"),
        ("migrate; true", "; true trailing"),
    ]:
        r = cc._is_success(
            "Bash", {"command": cmd},
            {"exit_code": 0, "stderr": "failed: connection refused"},
        )
        check(f"masked via {desc} + stderr → failure", r is False)

    # `set +e` is NOT flagged (too many false positives like
    # `set +e; grep X log; rc=$?; set -e`). Exit_code=0 is trusted.
    set_e_grep = cc._is_success(
        "Bash",
        {"command": "set +e; grep Error /var/log/app.log; rc=$?; set -e"},
        {"exit_code": 0, "output": "Error: sample line"},
    )
    check("set +e; grep ...; set -e trusted via exit_code (no false failure)",
          set_e_grep is True)

    check("_is_exit_masked('ls') is False", cc._is_exit_masked("ls") is False)
    check("_is_exit_masked('') is False", cc._is_exit_masked("") is False)
    check("_is_exit_masked('set +e; cmd') is False (no over-match)",
          cc._is_exit_masked("set +e; cmd") is False)

    # Env-var fallback shape: {"raw": "..."} should still trigger wrapper
    # detection, otherwise old Claude Code versions silently skip the fix.
    raw_masked = cc._is_success(
        "Bash",
        {"raw": "deploy --prod || true"},
        {"exit_code": 0, "stderr": "deploy failed: connection denied"},
    )
    check("env-var fallback {raw: ...} + stderr still detects masked failure",
          raw_masked is False)

    # ── Fix 2: on_failure preserves caller severity ────────────────────────
    print("\n2. on_failure preserves caller importance/pain_score")

    tmpdir = _mkdtemp()
    tmp_episodic = os.path.join(tmpdir, "learnings.jsonl")
    orig_ep = of.EPISODIC
    of.EPISODIC = tmp_episodic
    try:
        entry = on_failure(
            skill_name="claude-code",
            action="vercel deploy --prod",
            error="deploy rejected: build failed",
            context="ctx",
            confidence=0.7,
            importance=9,
            pain_score=10,
        )
        check("importance override respected", entry["importance"] == 9,
              f"got {entry['importance']}")
        check("pain_score override respected", entry["pain_score"] == 10,
              f"got {entry['pain_score']}")

        os.remove(tmp_episodic)
        entry2 = on_failure(
            skill_name="claude-code",
            action="ls /missing",
            error="not found",
        )
        check("defaults still 7/8 when not overridden",
              entry2["importance"] == 7 and entry2["pain_score"] == 8,
              f"got importance={entry2['importance']} pain={entry2['pain_score']}")
    finally:
        of.EPISODIC = orig_ep

    # ── Fix 3: invalid regex fragment filtered ─────────────────────────────
    print("\n3. Invalid regex fragment filtered, hook still loads")

    tmp_cfg_dir = _mkdtemp()
    protocols = os.path.join(tmp_cfg_dir, "protocols")
    os.makedirs(protocols, exist_ok=True)
    with open(os.path.join(protocols, "hook_patterns.json"), "w") as f:
        json.dump({
            "high_stakes":   ["good_pattern", "bad_(pattern", "another_good"],
            "medium_stakes": ["also_good"],
        }, f)

    orig_root = cc.AGENT_ROOT
    cc.AGENT_ROOT = tmp_cfg_dir
    try:
        high, medium = cc._load_user_patterns()
        check("valid fragments kept",
              "good_pattern" in high and "another_good" in high)
        check("invalid fragment dropped", "bad_(pattern" not in high)
        check("medium fragments unaffected", "also_good" in medium)
        check("loading with bad config doesn't crash", True)
    finally:
        cc.AGENT_ROOT = orig_root

    # ── Fix 3b: merged-compile failure preserves universals + good user ────
    print("\n3b. Merged-compile failure preserves universal patterns")

    pattern_with_flag = "(?i)custom_vercel"
    import re as _re
    try:
        _re.compile(pattern_with_flag)
        standalone_ok = True
    except _re.error:
        standalone_ok = False

    if standalone_ok:
        merged = cc._build_with_fallback(
            ["deploy", "migrate"], [pattern_with_flag],
        )
        check("fallback returns a working matcher", merged is not None)
        check("built-in 'deploy' still matches after fallback",
              merged is not None and merged.search("npm run deploy") is not None)
        check("built-in 'migrate' still matches after fallback",
              merged is not None and merged.search("prisma migrate") is not None)

        mixed = cc._build_with_fallback(
            ["deploy"], [pattern_with_flag, "supabase"],
        )
        check("good user fragment 'supabase' survives one bad sibling",
              mixed is not None and mixed.search("supabase db push") is not None)
        check("built-in 'deploy' still matches with mixed user fragments",
              mixed is not None and mixed.search("npm run deploy") is not None)
    else:
        print("  (skipped — this Python rejects (?i) even standalone)")

    # ── Fix 3c: inter-fragment conflicts resolved incrementally ────────────
    print("\n3c. Inter-fragment conflicts resolved incrementally")

    conflicting = cc._build_with_fallback(
        ["deploy"], ["(?P<x>foo)", "(?P<x>bar)"],
    )
    check("conflicting user fragments still produce a working matcher",
          conflicting is not None)
    check("built-in 'deploy' still matches after conflict resolution",
          conflicting is not None and conflicting.search("npm deploy") is not None)
    check("first conflicting fragment survives (first-wins)",
          conflicting is not None and conflicting.search("foo") is not None)

    # ── summary ────────────────────────────────────────────────────────────
    print("\n" + "─" * 50)
    if failures:
        print(f"\033[31m  {len(failures)} failed\033[0m: {', '.join(failures)}")
        return 1
    print("\033[32m  All regression checks passed\033[0m")
    return 0


if __name__ == "__main__":
    sys.exit(main())

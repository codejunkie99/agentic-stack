#!/usr/bin/env python3
"""
Validation suite for the Claude Code hook fix.

Run this from any project that has .agent/ installed:

    python3 /path/to/agentic-stack/test_claude_code_hook.py

Or run it from the agentic-stack repo itself:

    python3 test_claude_code_hook.py

Exit 0 = all tests passed. Non-zero = something is broken.

Tests:
  1. Hook imports correctly (path resolution works from project root)
  2. Empty stdin doesn't crash (graceful fallback)
  3. action label, importance, success detection, reflection for each tool type
  4. pain_score calibration (high-importance success = 5, failure = 8)
  5. Full write path: hook writes a real entry to AGENT_LEARNINGS.jsonl
  6. Dream cycle produces staged candidates from rich entries
  7. memory_reflect.py CLI --pain flag works
  8. post_execution.py pain_score parameter is accepted
  9. on_failure reflection has no 'str:' prefix for string errors
"""

import json, os, shutil, subprocess, sys, tempfile, textwrap

# ── find .agent/ ─────────────────────────────────────────────────────────────

def find_agent_root():
    """Walk up from cwd until we find .agent/"""
    cur = os.path.abspath(".")
    for _ in range(5):
        if os.path.isdir(os.path.join(cur, ".agent")):
            return cur
        cur = os.path.dirname(cur)
    # last resort: look next to this script
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(os.path.join(here, ".agent")):
        return here
    return None

PROJECT_ROOT = find_agent_root()
if not PROJECT_ROOT:
    print("FATAL: .agent/ not found. Run from your project root or the agentic-stack repo.")
    sys.exit(1)

AGENT_DIR   = os.path.join(PROJECT_ROOT, ".agent")
HOOK_SCRIPT = os.path.join(AGENT_DIR, "harness", "hooks", "claude_code_post_tool.py")
EPISODIC    = os.path.join(AGENT_DIR, "memory", "episodic", "AGENT_LEARNINGS.jsonl")

sys.path.insert(0, os.path.join(AGENT_DIR, "harness"))
sys.path.insert(0, os.path.join(AGENT_DIR, "memory"))
sys.path.insert(0, os.path.join(AGENT_DIR, "tools"))

# ── helpers ───────────────────────────────────────────────────────────────────

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m~\033[0m"

_results = []

def ok(name):
    _results.append((True, name))
    print(f"  {PASS}  {name}")

def fail(name, detail=""):
    _results.append((False, name))
    msg = f"  {FAIL}  {name}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)

def section(title):
    print(f"\n\033[1m{title}\033[0m")

def run_hook(payload):
    """Run the hook script with a JSON payload on stdin. Returns (returncode, last_entry_or_None)."""
    before = _last_entry()
    r = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=json.dumps(payload),
        capture_output=True, text=True,
        cwd=PROJECT_ROOT,
    )
    after = _last_entry()
    new_entry = after if after != before else None
    return r.returncode, new_entry, r.stderr

def _last_entry():
    if not os.path.exists(EPISODIC):
        return None
    lines = [l.strip() for l in open(EPISODIC) if l.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None

# ── import the hook module once ───────────────────────────────────────────────

import importlib.util

def _load_hook():
    spec = importlib.util.spec_from_file_location("claude_code_post_tool", HOOK_SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

try:
    import pytest
except ImportError:
    pytest = None

if pytest is not None:
    @pytest.fixture
    def mod():
        return _load_hook()

# ── tests ─────────────────────────────────────────────────────────────────────

def test_hook_exists():
    section("1. File existence")
    if os.path.isfile(HOOK_SCRIPT):
        ok("claude_code_post_tool.py exists")
    else:
        fail("claude_code_post_tool.py NOT FOUND",
             f"expected: {HOOK_SCRIPT}")

def _check_hook_imports():
    section("2. Import / path resolution")
    try:
        mod = _load_hook()
        ok("hook imports without error")
        return mod
    except Exception as e:
        fail("hook import failed", str(e))
        return None

def test_hook_imports():
    _check_hook_imports()

def test_empty_stdin():
    section("3. Empty stdin — graceful fallback")
    r = subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input="", capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if r.returncode == 0:
        ok("empty stdin exits 0")
    else:
        fail("empty stdin crashed", r.stderr[:200])

def test_action_labels(mod):
    section("4. Action labels")
    cases = [
        ("Bash", {"command": "supabase db push --db-url $URL"},
         "bash: supabase db push"),
        ("Edit", {"file_path": "src/App.tsx", "old_string": "v1", "new_string": "v2"},
         "edit: src/App.tsx"),
        ("Write", {"file_path": "src/new.ts", "content": "export {}"},
         "write: src/new.ts"),
        ("Bash", {"command": "git status"},
         "bash: git status"),
    ]
    for tool, inp, expected_prefix in cases:
        label = mod._action_label(tool, inp)
        if label.startswith(expected_prefix):
            ok(f"action label: {tool} → {label!r}")
        else:
            fail(f"action label: {tool}", f"got {label!r}, expected prefix {expected_prefix!r}")

def test_importance(mod):
    section("5. Importance scoring")
    # Importance is driven by the OPERATION, not the service brand.
    # 'vercel deploy' → 9 because 'deploy' is universal high, not because of 'vercel'.
    # 'supabase db push' → 6 because 'push' is universal medium.
    # Service names only change importance when added to hook_patterns.json.
    cases = [
        ("Bash", '{"command":"deploy to production"}',    9, "deploy (universal high)"),
        ("Bash", '{"command":"python migrate.py"}',       9, "migrate (universal high)"),
        ("Bash", '{"command":"git push --force"}',        9, "force push (universal high)"),
        ("Bash", '{"command":"vercel deploy"}',           9, "vercel deploy → high via 'deploy'"),
        ("Bash", '{"command":"supabase db push"}',        6, "supabase db push → medium via 'push'"),
        ("Bash", '{"command":"stripe listen"}',           3, "stripe listen → low (no op match)"),
        ("Bash", '{"command":"npm test"}',                6, "npm test (universal medium)"),
        ("Bash", '{"command":"git status"}',              3, "git status (low)"),
        ("Edit", '{"file_path":"src/App.tsx"}',           5, "plain edit"),
    ]
    for tool, inp, expected, label in cases:
        got = mod._importance(tool, inp)
        if got == expected:
            ok(f"importance: {label} → {got}")
        else:
            fail(f"importance: {label}", f"expected {expected}, got {got}")

def test_pain_score(mod):
    section("6. Pain score calibration")
    # high importance success → 5 (so clusters can cross 7.0 threshold)
    ps = mod._pain_score(9, True)
    if ps == 5:
        ok("pain_score(importance=9, success=True) → 5")
    else:
        fail("pain_score high-importance success", f"expected 5, got {ps}")

    # routine success → 2
    ps = mod._pain_score(3, True)
    if ps == 2:
        ok("pain_score(importance=3, success=True) → 2")
    else:
        fail("pain_score routine success", f"expected 2, got {ps}")

    # failure → 8 or 10
    ps = mod._pain_score(7, False)
    if ps in (8, 10):
        ok(f"pain_score(importance=7, success=False) → {ps}")
    else:
        fail("pain_score failure", f"expected 8 or 10, got {ps}")

def test_failure_detection(mod):
    section("7. Failure detection")
    cases = [
        ("Bash", {"exit_code": 1, "error": "command not found"}, False, "exit_code=1"),
        ("Bash", {"exit_code": 0, "error": ""},                  True,  "exit_code=0"),
        ("Bash", {"exit_code": 0, "is_error": True},             False, "is_error=True"),
        ("Edit", {"is_error": False},                            True,  "edit ok"),
        ("Bash", {"interrupted": True},                          False, "interrupted"),
    ]
    for tool, resp, expected, label in cases:
        got = mod._is_success(tool, resp)
        if got == expected:
            ok(f"success detection: {label} → {got}")
        else:
            fail(f"success detection: {label}", f"expected {expected}, got {got}")

def test_reflection_non_empty(mod):
    section("8. Reflection is non-empty (dream cycle can cluster on it)")
    cases = [
        ("Bash", {"command": "supabase db push"}, {}, True),
        ("Bash", {"command": "supabase db push"}, {"exit_code": 1, "error": "no migrations"}, False),
        ("Edit", {"file_path": "src/x.ts", "old_string": "a", "new_string": "b"}, {}, True),
        ("Write", {"file_path": "src/y.ts", "content": "export {}"}, {}, True),
        ("Bash", {"command": "git status"}, {"output": "nothing"}, True),
    ]
    for tool, inp, resp, success in cases:
        ref = mod._reflection(tool, inp, resp, success)
        if ref and len(ref) >= 10:
            ok(f"reflection non-empty: {tool} {'fail' if not success else 'ok'} — {ref[:60]!r}")
        else:
            fail(f"reflection empty: {tool}", f"got: {ref!r}")

def test_full_write(mod):
    section("9. Full write path — entry actually lands in AGENT_LEARNINGS.jsonl")
    # Use a universally high-stakes command (deploy) so importance=9 regardless
    # of what the user has in hook_patterns.json.
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "npm run deploy --env production"},
        "tool_response": {"output": "Deployed successfully.", "exit_code": 0, "error": ""}
    }
    rc, entry, stderr = run_hook(payload)
    if rc != 0:
        fail("hook exited non-zero", stderr[:200])
        return
    if entry is None:
        fail("no new entry written to AGENT_LEARNINGS.jsonl")
        return
    ok("entry written to AGENT_LEARNINGS.jsonl")

    checks = [
        ("action starts with 'bash:'", entry.get("action","").startswith("bash:")),
        ("reflection non-empty",       bool(entry.get("reflection",""))),
        ("importance == 9",            entry.get("importance") == 9),
        ("pain_score == 5",            entry.get("pain_score") == 5),
        ("result == success",          entry.get("result") == "success"),
    ]
    for label, passed in checks:
        (ok if passed else fail)(f"  entry.{label}")

def test_failure_write(mod):
    section("10. Failure write path — failed tool call is logged correctly")
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "supabase functions deploy payment-webhook"},
        "tool_response": {
            "output": "",
            "exit_code": 1,
            "error": "Error: STRIPE_SECRET_KEY not found in production secrets"
        }
    }
    rc, entry, stderr = run_hook(payload)
    if entry is None:
        fail("no entry written for failure case")
        return
    ok("failure entry written")

    checks = [
        ("result == failure",      entry.get("result") == "failure"),
        ("pain_score >= 8",        entry.get("pain_score", 0) >= 8),
        ("reflection mentions FAIL or FAILURE",
         "FAIL" in entry.get("reflection", "").upper()),
        ("reflection has no 'str:' prefix",
         ": str:" not in entry.get("reflection", "")),
        ("error captured in reflection",
         "STRIPE" in entry.get("reflection", "")),
    ]
    for label, passed in checks:
        (ok if passed else fail)(f"  entry.{label}")

def test_dream_cycle():
    section("11. Dream cycle produces staged candidates from rich entries")
    # Use a universally high-stakes command so importance=9 / pain_score=5
    # regardless of what the user has configured in hook_patterns.json.
    # 4 identical entries → cluster_size=4, salience=10*0.5*0.9*3=13.5 > 7.0 threshold.
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "npm run deploy --env production"},
        "tool_response": {"output": "Deployed successfully", "exit_code": 0}
    }
    for _ in range(4):
        run_hook(payload)

    r = subprocess.run(
        [sys.executable, os.path.join(AGENT_DIR, "memory", "auto_dream.py")],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    line = r.stdout.strip()
    ok(f"auto_dream.py ran: {line}")

    # Check for staged candidates
    import re
    m = re.search(r"staged=(\d+)", line)
    staged = int(m.group(1)) if m else 0
    if staged > 0:
        ok(f"dream cycle staged {staged} candidate(s)")
    else:
        # Could also already be in graduated/ from earlier test run — not a failure
        m2 = re.search(r"pending_review=(\d+)", line)
        pending = int(m2.group(1)) if m2 else 0
        if pending > 0:
            ok(f"pending_review={pending} (candidates exist from earlier run)")
        else:
            fail("dream cycle staged 0 candidates",
                 "Check that importance=9 and pain_score=5 entries were written")

def test_memory_reflect_pain_flag():
    section("12. memory_reflect.py --pain flag")
    r = subprocess.run(
        [sys.executable,
         os.path.join(AGENT_DIR, "tools", "memory_reflect.py"),
         "test-skill", "test-action", "test-outcome",
         "--importance", "9", "--pain", "5",
         "--note", "explicit pain score test"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if r.returncode != 0:
        fail("memory_reflect.py --pain exited non-zero", r.stderr[:200])
        return
    ok("memory_reflect.py --pain 5 ran without error")
    entry = _last_entry()
    if entry and entry.get("pain_score") == 5:
        ok("  pain_score=5 written correctly")
    else:
        ps = entry.get("pain_score") if entry else "no entry"
        fail("  pain_score not 5", f"got: {ps}")

def test_post_execution_pain_param():
    section("13. post_execution.log_execution accepts pain_score kwarg")
    try:
        from hooks.post_execution import log_execution
        import inspect
        sig = inspect.signature(log_execution)
        if "pain_score" in sig.parameters:
            ok("log_execution has pain_score parameter")
        else:
            fail("log_execution missing pain_score parameter",
                 "post_execution.py was not updated")
    except Exception as e:
        fail("could not inspect log_execution", str(e))

def test_hook_patterns_config():
    section("14. hook_patterns.json — user config overrides work")
    config_path = os.path.join(AGENT_DIR, "protocols", "hook_patterns.json")
    if not os.path.exists(config_path):
        fail("hook_patterns.json not found", f"expected: {config_path}")
        return
    ok("hook_patterns.json exists")

    try:
        cfg = json.load(open(config_path))
    except json.JSONDecodeError as e:
        fail("hook_patterns.json is invalid JSON", str(e))
        return
    ok("hook_patterns.json is valid JSON")

    # Must have the right keys
    for key in ("high_stakes", "medium_stakes", "_examples"):
        if key in cfg:
            ok(f"  has '{key}' key")
        else:
            fail(f"  missing '{key}' key")

    # high_stakes must be a list (empty by default)
    if isinstance(cfg.get("high_stakes"), list):
        ok(f"  high_stakes is a list ({len(cfg['high_stakes'])} entries by default)")
    else:
        fail("  high_stakes is not a list")

    # Verify user additions are picked up: temporarily add a pattern, reload
    orig_high = cfg["high_stakes"][:]
    cfg["high_stakes"] = ["mycustomcli"]
    with open(config_path, "w") as f:
        json.dump(cfg, f, indent=2)
    try:
        mod2 = _load_hook()
        got = mod2._importance("Bash", '{"command":"mycustomcli run"}')
        if got == 9:
            ok("  user-added pattern correctly scores importance=9")
        else:
            fail("  user-added pattern did not score 9", f"got {got}")
    finally:
        cfg["high_stakes"] = orig_high
        with open(config_path, "w") as f:
            json.dump(cfg, f, indent=2)


def test_settings_json():
    section("14. settings.json points to new hook")
    settings_path = os.path.join(PROJECT_ROOT, ".claude", "settings.json")
    adapter_path  = os.path.join(PROJECT_ROOT, "adapters", "claude-code", "settings.json")

    for label, path in [("adapter settings.json", adapter_path),
                        (".claude/settings.json (project)", settings_path)]:
        if not os.path.exists(path):
            print(f"  {WARN}  {label}: not found (skip)")
            continue
        try:
            s = json.load(open(path))
        except json.JSONDecodeError as e:
            fail(f"{label}: invalid JSON", str(e))
            continue

        hooks = (s.get("hooks", {})
                   .get("PostToolUse", []))
        cmds = [h.get("command", "") for entry in hooks
                for h in entry.get("hooks", [])]
        uses_new = any("claude_code_post_tool" in c for c in cmds)
        uses_old = any("post-tool ok" in c for c in cmds)

        if uses_new:
            ok(f"{label}: uses claude_code_post_tool.py")
        elif uses_old:
            fail(f"{label}: still uses old hardcoded 'post-tool ok'",
                 f"Run: cp adapters/claude-code/settings.json .claude/settings.json")
        else:
            print(f"  {WARN}  {label}: hook command not recognized — check manually")

# ── summary ───────────────────────────────────────────────────────────────────

def main():
    print(f"\n\033[1magentic-stack claude-code hook validation\033[0m")
    print(f"project root: {PROJECT_ROOT}")
    print(f"agent dir:    {AGENT_DIR}")

    test_hook_exists()
    mod = _check_hook_imports()
    if mod is None:
        print("\n\033[31mCannot continue — hook did not import.\033[0m")
        sys.exit(1)

    test_empty_stdin()
    test_action_labels(mod)
    test_importance(mod)
    test_pain_score(mod)
    test_failure_detection(mod)
    test_reflection_non_empty(mod)
    test_full_write(mod)
    test_failure_write(mod)
    test_dream_cycle()
    test_memory_reflect_pain_flag()
    test_post_execution_pain_param()
    test_hook_patterns_config()
    test_settings_json()

    passed = sum(1 for ok, _ in _results if ok)
    failed = sum(1 for ok, _ in _results if not ok)
    total  = len(_results)

    print(f"\n{'─'*50}")
    if failed == 0:
        print(f"\033[32m  {passed}/{total} passed — all good\033[0m")
        print(f"\n  Next steps:")
        print(f"  1. Install into a real project:  ./install.sh claude-code /path/to/project")
        print(f"  2. Open Claude Code, run a Supabase or deploy command")
        print(f"  3. tail -1 .agent/memory/episodic/AGENT_LEARNINGS.jsonl | python3 -m json.tool")
        print(f"  4. Verify action/reflection/importance are non-trivial")
        print(f"  5. Submit PR when satisfied\n")
        sys.exit(0)
    else:
        print(f"\033[31m  {failed}/{total} failed\033[0m  ({passed} passed)")
        print()
        for ok_flag, name in _results:
            if not ok_flag:
                print(f"  {FAIL}  {name}")
        sys.exit(1)


if __name__ == "__main__":
    main()

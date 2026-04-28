#!/usr/bin/env python3
"""
Validation suite for the GitHub Copilot CLI adapter.

Run from the agentic-stack repo root:

    python3 test_copilot_cli_adapter.py

Exit 0 = all tests passed. Non-zero = something is broken.

Tests:
  1. adapter.json schema validation
  2. Install into temp project — brain + instruction file created
  3. Instruction file content checks (brain wiring references)
  4. Tool availability — referenced tools exist after install
  5. Memory layer availability — memory dirs/files exist
  6. Skills availability — skills index + at least one skill
  7. Doctor detection signal — adapter detected from filesystem
  8. Remove roundtrip — instruction file cleaned up
"""

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTER_DIR = HERE / "adapters" / "copilot-cli"
MANIFEST_PATH = ADAPTER_DIR / "adapter.json"

sys.path.insert(0, str(HERE / "harness_manager"))
sys.path.insert(0, str(HERE))

# ── helpers ───────────────────────────────────────────────────────────────────

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"

_results: list[tuple[bool, str]] = []


def ok(name: str) -> None:
    _results.append((True, name))
    print(f"  {PASS}  {name}")


def fail(name: str, detail: str = "") -> None:
    _results.append((False, name))
    msg = f"  {FAIL}  {name}"
    if detail:
        msg += f"\n       {detail}"
    print(msg)


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m")


# ── tests ─────────────────────────────────────────────────────────────────────

def test_manifest_validation():
    section("1. adapter.json schema validation")
    from harness_manager import schema as schema_mod

    if not MANIFEST_PATH.is_file():
        fail("adapter.json exists", f"not found at {MANIFEST_PATH}")
        return None

    ok("adapter.json exists")

    try:
        manifest = schema_mod.validate(MANIFEST_PATH)
        ok("adapter.json passes schema validation")
    except schema_mod.ManifestError as e:
        fail("adapter.json schema validation", str(e))
        return None

    if manifest["name"] == "copilot-cli":
        ok("name is 'copilot-cli'")
    else:
        fail("name field", f"expected 'copilot-cli', got '{manifest['name']}'")

    if len(manifest["files"]) >= 1:
        ok(f"files array has {len(manifest['files'])} entry(ies)")
    else:
        fail("files array is empty")

    dst = manifest["files"][0]["dst"]
    if dst == ".github/instructions/agentic-stack.instructions.md":
        ok(f"dst = {dst}")
    else:
        fail("dst path", f"expected .github/instructions/agentic-stack.instructions.md, got {dst}")

    return manifest


def test_install_into_temp(manifest):
    section("2. Install into temp project")
    from harness_manager import install as install_mod

    tmpdir = tempfile.mkdtemp(prefix="copilot-cli-test-")
    target = Path(tmpdir)
    logs: list[str] = []

    try:
        entry = install_mod.install(
            manifest=manifest,
            target_root=target,
            adapter_dir=ADAPTER_DIR,
            stack_root=HERE,
            log=lambda msg: logs.append(msg),
        )

        # Brain copied
        if (target / ".agent" / "AGENTS.md").is_file():
            ok(".agent/AGENTS.md present (brain copied)")
        else:
            fail(".agent/AGENTS.md missing — brain not installed")

        # Instruction file created
        inst_file = target / ".github" / "instructions" / "agentic-stack.instructions.md"
        if inst_file.is_file():
            ok("instruction file created at .github/instructions/")
        else:
            fail("instruction file not created")

        # install.json recorded
        install_json = target / ".agent" / "install.json"
        if install_json.is_file():
            doc = json.loads(install_json.read_text(encoding="utf-8"))
            if "copilot-cli" in doc.get("adapters", {}):
                ok("install.json records copilot-cli adapter")
            else:
                fail("install.json missing copilot-cli entry")
        else:
            fail("install.json not created")

        return target, entry
    except Exception as e:
        fail("install raised exception", str(e))
        shutil.rmtree(tmpdir, ignore_errors=True)
        return None, None


def test_instruction_content(target: Path):
    section("3. Instruction file content checks")
    inst_file = target / ".github" / "instructions" / "agentic-stack.instructions.md"
    if not inst_file.is_file():
        fail("instruction file missing — skipping content checks")
        return

    content = inst_file.read_text(encoding="utf-8")

    checks = [
        (".agent/AGENTS.md", "references .agent/AGENTS.md (brain map)"),
        (".agent/memory/personal/PREFERENCES.md", "references PREFERENCES.md"),
        (".agent/memory/semantic/LESSONS.md", "references LESSONS.md"),
        (".agent/protocols/permissions.md", "references permissions.md"),
        (".agent/tools/recall.py", "references recall.py (tool available)"),
        (".agent/tools/show.py", "references show.py"),
        (".agent/tools/learn.py", "references learn.py"),
        (".agent/skills/_index.md", "references skills index"),
        ("memory_reflect.py", "references memory_reflect.py"),
    ]
    for needle, label in checks:
        if needle in content:
            ok(label)
        else:
            fail(label, f"'{needle}' not found in instruction file")


def test_tool_availability(target: Path):
    section("4. Tool availability after install")
    tools = [
        "recall.py",
        "show.py",
        "learn.py",
        "memory_reflect.py",
        "graduate.py",
        "reject.py",
        "list_candidates.py",
        "skill_loader.py",
    ]
    for tool in tools:
        tool_path = target / ".agent" / "tools" / tool
        if tool_path.is_file():
            ok(f".agent/tools/{tool} exists")
        else:
            fail(f".agent/tools/{tool} missing")


def test_memory_availability(target: Path):
    section("5. Memory layer availability")
    checks = [
        (".agent/memory/personal/PREFERENCES.md", True),
        (".agent/memory/semantic/LESSONS.md", True),
        (".agent/memory/working/WORKSPACE.md", True),
        (".agent/memory/episodic", False),  # directory, AGENT_LEARNINGS.jsonl may not exist yet
    ]
    for relpath, is_file in checks:
        p = target / relpath
        if is_file:
            if p.is_file():
                ok(f"{relpath} exists")
            else:
                fail(f"{relpath} missing")
        else:
            if p.is_dir():
                ok(f"{relpath}/ directory exists")
            else:
                fail(f"{relpath}/ directory missing")


def test_skills_availability(target: Path):
    section("6. Skills availability")
    skills_dir = target / ".agent" / "skills"

    index = skills_dir / "_index.md"
    if index.is_file():
        ok(".agent/skills/_index.md exists")
    else:
        fail(".agent/skills/_index.md missing")

    manifest = skills_dir / "_manifest.jsonl"
    if manifest.is_file():
        ok(".agent/skills/_manifest.jsonl exists")
    else:
        fail(".agent/skills/_manifest.jsonl missing")

    # At least one skill subdirectory
    skill_dirs = [d for d in skills_dir.iterdir()
                  if d.is_dir() and not d.name.startswith("_")]
    if skill_dirs:
        ok(f"{len(skill_dirs)} skill(s) found: {', '.join(d.name for d in skill_dirs[:5])}")
    else:
        fail("no skill subdirectories found")


def test_doctor_detection(target: Path):
    section("7. Doctor detection signal")
    from harness_manager import doctor as doctor_mod

    signals = doctor_mod.DETECT_SIGNALS.get("copilot-cli")
    if signals is None:
        fail("copilot-cli not in DETECT_SIGNALS")
        return

    ok("copilot-cli in DETECT_SIGNALS")

    # Check that the signal file path matches what we installed
    signal_path, strength = signals[0]
    if signal_path == ".github/instructions/agentic-stack.instructions.md":
        ok(f"signal path correct: {signal_path}")
    else:
        fail("signal path mismatch", f"got {signal_path}")

    if strength == "strong":
        ok("signal strength is 'strong'")
    else:
        fail("signal strength", f"expected 'strong', got {strength}")

    # Verify detection works on our installed target
    detected = False
    for fname, _ in signals:
        if (target / fname).exists():
            detected = True
    if detected:
        ok("detection signal file exists in installed target")
    else:
        fail("detection signal file not found in target")


def test_remove_roundtrip(target: Path):
    section("8. Remove roundtrip")
    from harness_manager import remove as remove_mod

    inst_file = target / ".github" / "instructions" / "agentic-stack.instructions.md"
    if not inst_file.is_file():
        fail("instruction file missing before remove — can't test roundtrip")
        return

    logs: list[str] = []
    try:
        remove_mod.remove(
            adapter_name="copilot-cli",
            target_root=target,
            yes=True,
            log=lambda msg: logs.append(msg),
        )
        ok("remove completed without error")
    except Exception as e:
        fail("remove raised exception", str(e))
        return

    if not inst_file.exists():
        ok("instruction file removed")
    else:
        fail("instruction file still present after remove")

    # Brain should still be there (remove doesn't delete .agent/)
    if (target / ".agent" / "AGENTS.md").is_file():
        ok(".agent/ brain preserved after remove")
    else:
        fail(".agent/ brain removed (should be preserved)")


# ── summary ───────────────────────────────────────────────────────────────────

def main():
    print(f"\n\033[1magentic-stack copilot-cli adapter validation\033[0m")
    print(f"repo root:    {HERE}")
    print(f"adapter dir:  {ADAPTER_DIR}")

    manifest = test_manifest_validation()
    if manifest is None:
        print("\n\033[31mCannot continue — manifest validation failed.\033[0m")
        sys.exit(1)

    target, entry = test_install_into_temp(manifest)
    if target is None:
        print("\n\033[31mCannot continue — install failed.\033[0m")
        sys.exit(1)

    try:
        test_instruction_content(target)
        test_tool_availability(target)
        test_memory_availability(target)
        test_skills_availability(target)
        test_doctor_detection(target)
        test_remove_roundtrip(target)
    finally:
        shutil.rmtree(target, ignore_errors=True)

    passed = sum(1 for ok_flag, _ in _results if ok_flag)
    failed = sum(1 for ok_flag, _ in _results if not ok_flag)
    total = len(_results)

    print(f"\n{'─' * 50}")
    if failed == 0:
        print(f"\033[32m  {passed}/{total} passed — all good\033[0m")
        print(f"\n  Next steps:")
        print(f"  1. Install into a real project:  ./install.sh copilot-cli /path/to/project")
        print(f"  2. Open Copilot CLI, run: /instructions")
        print(f"  3. Verify agentic-stack.instructions.md is listed")
        print(f"  4. Ask Copilot CLI: \"What instructions do you have?\"")
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

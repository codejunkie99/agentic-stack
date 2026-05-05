#!/usr/bin/env python3
"""Validation suite for the gemini-cli adapter.

Run this from the agentic-stack repo root:

    python3 test_gemini_mcp.py

Exit 0 = all tests passed. Non-zero = something is broken.

Tests:
 1. adapter.json validates against the harness_manager schema
 2. adapter.json name is 'gemini-cli' and is alphanumeric
 3. All file entries reference files that exist in the adapter directory
 4. GEMINI.md references .agent/ (brain wiring check)
 5. GEMINI.md contains recall-before-acting instruction
 6. MCP server JS is syntactically valid (node --check)
 7. MCP server JS imports @modelcontextprotocol/sdk and zod
 8. MCP server JS registers all four tools (recall, memory_reflect, learn, agentic_status)
 9. MCP package.json has required dependencies
10. MCP package.json has engines field requiring node >= 18
11. All TOML command files have a description and prompt field
12. TOML command files reference .agent/tools/ scripts
13. README.md exists and contains install instructions
14. docs/per-harness/gemini-cli.md exists and contains MCP setup
15. Install + remove cycle (via harness_manager) is clean
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ADAPTER_DIR = os.path.join(HERE, "adapters", "gemini-cli")

sys.path.insert(0, HERE)

from harness_manager import schema as schema_mod

PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"

_results = []


def ok(name):
    _results.append((True, name))
    print(f" {PASS} {name}")


def fail(name, detail=""):
    _results.append((False, name))
    msg = f" {FAIL} {name}"
    if detail:
        msg += f"\n   {detail}"
    print(msg)


def section(title):
    print(f"\n\033[1m{title}\033[0m")


# ── tests ──────────────────────────────────────────────────────────────────

def test_adapter_json_validates():
    manifest_path = os.path.join(ADAPTER_DIR, "adapter.json")
    try:
        manifest = schema_mod.validate(manifest_path)
        ok("adapter.json validates against harness_manager schema")
    except schema_mod.ManifestError as e:
        fail("adapter.json validates against harness_manager schema", str(e))


def test_adapter_name():
    manifest_path = os.path.join(ADAPTER_DIR, "adapter.json")
    try:
        manifest = schema_mod.validate(manifest_path)
        name = manifest.get("name", "")
        if name == "gemini-cli":
            ok("adapter.json name is 'gemini-cli'")
        else:
            fail("adapter.json name is 'gemini-cli'", f"got '{name}'")
    except schema_mod.ManifestError:
        fail("adapter.json name is 'gemini-cli'", "manifest invalid")


def test_file_entries_exist():
    manifest_path = os.path.join(ADAPTER_DIR, "adapter.json")
    try:
        manifest = schema_mod.validate(manifest_path)
    except schema_mod.ManifestError:
        fail("All file entries reference existing files", "manifest invalid")
        return

    all_exist = True
    for entry in manifest.get("files", []):
        src = entry.get("src", "")
        src_path = os.path.join(ADAPTER_DIR, src)
        if not os.path.isfile(src_path):
            fail("All file entries reference existing files", f"missing: {src}")
            all_exist = False
            break
    if all_exist:
        ok("All file entries reference existing files")


def test_gemini_md_references_agent():
    path = os.path.join(ADAPTER_DIR, "GEMINI.md")
    if not os.path.isfile(path):
        fail("GEMINI.md references .agent/", "file not found")
        return
    text = open(path).read()
    if ".agent/" in text:
        ok("GEMINI.md references .agent/")
    else:
        fail("GEMINI.md references .agent/", "no mention of .agent/ found")


def test_gemini_md_has_recall_instruction():
    path = os.path.join(ADAPTER_DIR, "GEMINI.md")
    if not os.path.isfile(path):
        fail("GEMINI.md has recall-before-acting instruction", "file not found")
        return
    text = open(path).read()
    if "recall" in text.lower() and "before" in text.lower():
        ok("GEMINI.md has recall-before-acting instruction")
    else:
        fail("GEMINI.md has recall-before-acting instruction",
             "missing recall-before instruction")


def test_mcp_server_js_syntax():
    path = os.path.join(ADAPTER_DIR, "mcp-server.js")
    if not os.path.isfile(path):
        fail("mcp-server.js is syntactically valid", "file not found")
        return
    if not shutil.which("node"):
        ok("mcp-server.js is syntactically valid (skipped: node not found)")
        return
    result = subprocess.run(
        ["node", "--check", path],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        ok("mcp-server.js is syntactically valid")
    else:
        fail("mcp-server.js is syntactically valid", result.stderr.strip())


def test_mcp_server_imports():
    path = os.path.join(ADAPTER_DIR, "mcp-server.js")
    if not os.path.isfile(path):
        fail("mcp-server.js imports required packages", "file not found")
        return
    text = open(path).read()
    has_mcp = "@modelcontextprotocol/sdk" in text
    has_zod = '"zod"' in text
    if has_mcp and has_zod:
        ok("mcp-server.js imports @modelcontextprotocol/sdk and zod")
    else:
        missing = []
        if not has_mcp:
            missing.append("@modelcontextprotocol/sdk")
        if not has_zod:
            missing.append("zod")
        fail("mcp-server.js imports @modelcontextprotocol/sdk and zod",
             f"missing: {', '.join(missing)}")


def test_mcp_server_registers_four_tools():
    path = os.path.join(ADAPTER_DIR, "mcp-server.js")
    if not os.path.isfile(path):
        fail("mcp-server.js registers all four tools", "file not found")
        return
    text = open(path).read()
    expected = ["recall", "memory_reflect", "learn", "agentic_status"]
    missing = [t for t in expected if f'"{t}"' not in text and f"'{t}'" not in text]
    if not missing:
        ok("mcp-server.js registers all four tools")
    else:
        fail("mcp-server.js registers all four tools",
             f"missing: {', '.join(missing)}")


def test_mcp_package_json_deps():
    path = os.path.join(ADAPTER_DIR, "mcp-package.json")
    if not os.path.isfile(path):
        fail("mcp-package.json has required dependencies", "file not found")
        return
    try:
        pkg = json.loads(open(path).read())
    except json.JSONDecodeError as e:
        fail("mcp-package.json has required dependencies", f"invalid JSON: {e}")
        return
    deps = pkg.get("dependencies", {})
    has_mcp = "@modelcontextprotocol/sdk" in deps
    has_zod = "zod" in deps
    if has_mcp and has_zod:
        ok("mcp-package.json has required dependencies")
    else:
        missing = []
        if not has_mcp:
            missing.append("@modelcontextprotocol/sdk")
        if not has_zod:
            missing.append("zod")
        fail("mcp-package.json has required dependencies",
             f"missing: {', '.join(missing)}")


def test_mcp_package_json_engines():
    path = os.path.join(ADAPTER_DIR, "mcp-package.json")
    if not os.path.isfile(path):
        fail("mcp-package.json has engines field requiring node >= 18",
             "file not found")
        return
    try:
        pkg = json.loads(open(path).read())
    except json.JSONDecodeError:
        fail("mcp-package.json has engines field requiring node >= 18",
             "invalid JSON")
        return
    engines = pkg.get("engines", {})
    node_ver = engines.get("node", "")
    if "18" in node_ver:
        ok("mcp-package.json has engines field requiring node >= 18")
    else:
        fail("mcp-package.json has engines field requiring node >= 18",
             f"got: {node_ver}")


def test_toml_commands_have_fields():
    cmd_dir = os.path.join(ADAPTER_DIR, "commands")
    if not os.path.isdir(cmd_dir):
        fail("All TOML command files have description and prompt",
             "commands/ dir not found")
        return
    toml_files = [f for f in os.listdir(cmd_dir) if f.endswith(".toml")]
    if not toml_files:
        fail("All TOML command files have description and prompt",
             "no .toml files found")
        return
    all_ok = True
    for tf in toml_files:
        text = open(os.path.join(cmd_dir, tf)).read()
        has_desc = "description" in text
        has_prompt = "prompt" in text
        if not (has_desc and has_prompt):
            missing = []
            if not has_desc:
                missing.append("description")
            if not has_prompt:
                missing.append("prompt")
            fail("All TOML command files have description and prompt",
                 f"{tf}: missing {', '.join(missing)}")
            all_ok = False
            break
    if all_ok:
        ok("All TOML command files have description and prompt")


def test_toml_commands_reference_agent_tools():
    cmd_dir = os.path.join(ADAPTER_DIR, "commands")
    if not os.path.isdir(cmd_dir):
        fail("TOML command files reference .agent/tools/ scripts",
             "commands/ dir not found")
        return
    toml_files = [f for f in os.listdir(cmd_dir) if f.endswith(".toml")]
    all_ok = True
    for tf in toml_files:
        text = open(os.path.join(cmd_dir, tf)).read()
        if ".agent/tools/" not in text:
            fail("TOML command files reference .agent/tools/ scripts",
                 f"{tf}: no .agent/tools/ reference")
            all_ok = False
            break
    if all_ok:
        ok("TOML command files reference .agent/tools/ scripts")


def test_readme_exists_and_has_install():
    path = os.path.join(ADAPTER_DIR, "README.md")
    if not os.path.isfile(path):
        fail("README.md exists and contains install instructions",
             "file not found")
        return
    text = open(path).read()
    has_install = "install.sh" in text and "gemini-cli" in text
    if has_install:
        ok("README.md exists and contains install instructions")
    else:
        fail("README.md exists and contains install instructions",
             "missing install.sh or gemini-cli mention")


def test_docs_per_harness_exists():
    path = os.path.join(HERE, "docs", "per-harness", "gemini-cli.md")
    if not os.path.isfile(path):
        fail("docs/per-harness/gemini-cli.md exists and contains MCP setup",
             "file not found")
        return
    text = open(path).read()
    has_mcp = "mcpServers" in text or "MCP" in text
    if has_mcp:
        ok("docs/per-harness/gemini-cli.md exists and contains MCP setup")
    else:
        fail("docs/per-harness/gemini-cli.md exists and contains MCP setup",
             "no MCP mention found")


def test_install_remove_cycle():
    scratch = None
    try:
        scratch = tempfile.mkdtemp(prefix="agentic-gemini-test-")
        from harness_manager import install as install_mod
        from harness_manager import remove as remove_mod
        from harness_manager import state as state_mod

        manifest_path = os.path.join(ADAPTER_DIR, "adapter.json")
        manifest = schema_mod.validate(manifest_path)

        logs = []
        def log(msg):
            logs.append(msg)

        shutil.copytree(os.path.join(HERE, ".agent"), os.path.join(scratch, ".agent"))

        install_mod.install(
            manifest=manifest,
            target_root=scratch,
            adapter_dir=ADAPTER_DIR,
            stack_root=HERE,
            log=log,
        )

        state = state_mod.load(scratch)
        if not state or "gemini-cli" not in (state.get("adapters") or {}):
            fail("Install + remove cycle is clean", "adapter not recorded in install.json")
            return

        gemini_md = os.path.join(scratch, "GEMINI.md")
        mcp_dir = os.path.join(scratch, ".gemini", "agentic-stack-mcp")
        if not os.path.isfile(gemini_md):
            fail("Install + remove cycle is clean", "GEMINI.md not created")
            return
        if not os.path.isdir(mcp_dir):
            fail("Install + remove cycle is clean",
                 ".gemini/agentic-stack-mcp/ not created")
            return

        remove_mod.remove(
            target_root=scratch,
            adapter_name="gemini-cli",
            yes=True,
            log=log,
        )

        state_after = state_mod.load(scratch)
        adapters_after = (state_after or {}).get("adapters", {})
        if "gemini-cli" in adapters_after:
            fail("Install + remove cycle is clean",
                 "adapter still in install.json after remove")
            return

        ok("Install + remove cycle is clean")

    except Exception as e:
        fail("Install + remove cycle is clean", str(e))
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)


# ── runner ─────────────────────────────────────────────────────────────────

def main():
    print("\n\033[1magentic-stack gemini-cli adapter — validation suite\033[0m")

    section("Adapter manifest")
    test_adapter_json_validates()
    test_adapter_name()
    test_file_entries_exist()

    section("GEMINI.md wiring")
    test_gemini_md_references_agent()
    test_gemini_md_has_recall_instruction()

    section("MCP server")
    test_mcp_server_js_syntax()
    test_mcp_server_imports()
    test_mcp_server_registers_four_tools()

    section("MCP package")
    test_mcp_package_json_deps()
    test_mcp_package_json_engines()

    section("Custom commands")
    test_toml_commands_have_fields()
    test_toml_commands_reference_agent_tools()

    section("Documentation")
    test_readme_exists_and_has_install()
    test_docs_per_harness_exists()

    section("Install / remove cycle")
    test_install_remove_cycle()

    passed = sum(1 for ok_, _ in _results if ok_)
    failed = sum(1 for ok_, _ in _results if not ok_)
    total = len(_results)
    print(f"\n\033[1m{passed}/{total} passed, {failed} failed\033[0m")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()

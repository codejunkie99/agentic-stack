#!/usr/bin/env python3
"""Validation suite for the tldraw skill + local snapshot store.

Run from the agentic-stack repo root:

    python3 test_tldraw_visual_memory.py

Exit 0 = all tests passed. Non-zero = something is broken.

Tests:
  1. SKILL.md exists and has valid YAML frontmatter with required fields
  2. _index.md references tldraw
  3. _manifest.jsonl has a valid tldraw entry
  4. store.py imports and the skill-local store is well-formed
  5. snapshot() writes a shape file, a jsonl record, and renders INDEX.md
  6. list_snapshots() surfaces the new record, filters by tag
  7. load_snapshot() round-trips shape data
  8. archive_snapshot() moves file + flips status, never deletes
  9. CLI: snapshot via stdin -> list -> archive roundtrip
 10. Feature flag: onboard_features.is_enabled('tldraw') respects the file
 11. adapter installs do not wire beta MCP by default
 12. skill_loader honors the tldraw feature flag
"""
from __future__ import annotations

import importlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
AGENT = os.path.join(HERE, ".agent")
TLDRAW = os.path.join(AGENT, "skills", "tldraw")
TOOLS = os.path.join(AGENT, "tools")

sys.path.insert(0, HERE)
sys.path.insert(0, TLDRAW)
sys.path.insert(0, TOOLS)

PASS = "\033[32m+\033[0m"
FAIL = "\033[31mx\033[0m"

_results: list[tuple[str, bool, str]] = []


def _check(name: str, cond: bool, detail: str = "") -> None:
    _results.append((name, bool(cond), detail))
    mark = PASS if cond else FAIL
    suffix = f" - {detail}" if detail else ""
    print(f"  {mark} {name}{suffix}")


def _section(title: str) -> None:
    print(f"\n{title}")


# ── 1. skill file ──────────────────────────────────────────────────────

def test_skill_file() -> None:
    _section("skill file")
    skill_path = os.path.join(AGENT, "skills", "tldraw", "SKILL.md")
    if not os.path.exists(skill_path):
        _check("SKILL.md exists", False, skill_path)
        return
    _check("SKILL.md exists", True)
    text = open(skill_path, encoding="utf-8").read()
    _check("starts with YAML frontmatter", text.startswith("---\n"))
    # Minimal parse: grab the first fenced block, split on colons.
    _, _, rest = text.partition("---\n")
    fm, _, _ = rest.partition("\n---")
    fields = {}
    for line in fm.splitlines():
        if ":" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip()
    for required in ("name", "version", "triggers", "tools", "constraints"):
        _check(f"frontmatter has `{required}`", required in fields)
    _check("name is tldraw", fields.get("name") == "tldraw")
    _check("body mentions self-rewrite hook",
           "Self-rewrite hook" in text or "self-rewrite hook" in text.lower())


# ── 2. skill registry ──────────────────────────────────────────────────

def test_registry() -> None:
    _section("skill registry")
    idx = os.path.join(AGENT, "skills", "_index.md")
    man = os.path.join(AGENT, "skills", "_manifest.jsonl")
    _check("_index.md mentions tldraw",
           "tldraw" in open(idx, encoding="utf-8").read())

    found = None
    for line in open(man, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as e:
            _check("_manifest.jsonl lines parse", False, str(e))
            return
        if row.get("name") == "tldraw":
            found = row
    _check("_manifest.jsonl has tldraw entry", found is not None)
    if found:
        _check("manifest triggers include 'draw'", "draw" in found.get("triggers", []))
        _check("manifest tools include get_canvas",
               "mcp.tldraw.get_canvas" in found.get("tools", []))
        _check("manifest carries feature_flag=tldraw",
               found.get("feature_flag") == "tldraw")


# ── 3. tldraw store module ─────────────────────────────────────────────

SAMPLE_SHAPES = [
    {"type": "geo", "geo": "rectangle", "x": 100, "y": 100,
     "w": 160, "h": 80, "text": "Start", "color": "blue"},
    {"type": "geo", "geo": "rectangle", "x": 400, "y": 100,
     "w": 160, "h": 80, "text": "End", "color": "green"},
    {"type": "arrow", "x": 260, "y": 140, "end": {"x": 400, "y": 140}},
]


def _isolated_visual_module():
    """Load store.py with its storage paths redirected into a tmp dir.

    We don't want tests writing into the real skill store. Rebinding
    module-level path constants to the tmpdir is the cleanest sandbox.
    """
    import store as vm  # type: ignore
    importlib.reload(vm)
    tmp = tempfile.mkdtemp(prefix="tldraw-store-test-")
    vm.SNAPSHOTS_DIR = os.path.join(tmp, "snapshots")
    vm.ARCHIVE_DIR = os.path.join(vm.SNAPSHOTS_DIR, "archive")
    vm.JSONL_PATH = os.path.join(tmp, "snapshots.jsonl")
    vm.INDEX_PATH = os.path.join(tmp, "INDEX.md")
    return vm, tmp


def test_visual_memory_api() -> None:
    _section("tldraw store — python API")
    _check("tldraw skill dir exists", os.path.isdir(TLDRAW))
    _check("store.py exists", os.path.exists(os.path.join(TLDRAW, "store.py")))

    vm, tmp = _isolated_visual_module()
    try:
        meta = vm.snapshot(SAMPLE_SHAPES, label="auth flow", tags=["arch", "auth"],
                           note="test")
        _check("snapshot returns metadata with id", bool(meta.get("id")))
        _check("snapshot label is sanitized", meta.get("label") == "auth-flow")
        _check("shape_count matches input", meta.get("shape_count") == len(SAMPLE_SHAPES))

        sid = meta["id"]
        shape_file = os.path.join(vm.SNAPSHOTS_DIR, f"{sid}.json")
        _check("shape file written", os.path.exists(shape_file))
        _check("INDEX.md rendered",
               os.path.exists(vm.INDEX_PATH)
               and sid in open(vm.INDEX_PATH, encoding="utf-8").read())

        # envelope form also accepted
        meta2 = vm.snapshot({"shapes": SAMPLE_SHAPES[:1]}, label="single")
        _check("envelope form accepted", meta2["shape_count"] == 1)

        rows = vm.list_snapshots()
        _check("list_snapshots returns both", len(rows) == 2)
        tagged = vm.list_snapshots(tag="auth")
        _check("list_snapshots filters by tag", len(tagged) == 1 and tagged[0]["id"] == sid)

        loaded = vm.load_snapshot(sid)
        _check("load_snapshot returns shapes", loaded.get("shapes") == SAMPLE_SHAPES)

        vm.archive_snapshot(sid)
        _check("archive moves file to archive/",
               not os.path.exists(shape_file)
               and os.path.exists(os.path.join(vm.ARCHIVE_DIR, f"{sid}.json")))
        active = vm.list_snapshots()
        _check("archived snapshot hidden from default list",
               all(r["id"] != sid for r in active))
        with_archived = vm.list_snapshots(include_archived=True)
        _check("archived snapshot visible with --all",
               any(r["id"] == sid and r.get("status") == "archived"
                   for r in with_archived))
        # archive preserves data
        loaded_after = vm.load_snapshot(sid)
        _check("archived snapshot still loadable", loaded_after.get("shapes") == SAMPLE_SHAPES)

        try:
            vm.load_snapshot("does-not-exist")
            _check("missing id raises", False, "no exception")
        except FileNotFoundError:
            _check("missing id raises", True)

        try:
            vm.load_snapshot("../does-not-exist")
            _check("path traversal id rejected", False, "no exception")
        except ValueError:
            _check("path traversal id rejected", True)

        try:
            vm.snapshot("not a list", label="bad")
            _check("non-list payload rejected", False, "no exception")
        except ValueError:
            _check("non-list payload rejected", True)

        # Regression: identical payloads captured in the same second must
        # not collide. An earlier payload-hash id design silently overwrote
        # the first snapshot's file while still appending a second metadata
        # row — corrupting the layer.
        from datetime import datetime, timezone
        fixed = datetime(2026, 4, 21, 12, 0, 0, tzinfo=timezone.utc)
        a = vm.snapshot(SAMPLE_SHAPES, label="dup", when=fixed)
        b = vm.snapshot(SAMPLE_SHAPES, label="dup", when=fixed)
        _check("same-second identical snapshots get distinct ids",
               a["id"] != b["id"])
        _check("both snapshot files exist on disk",
               os.path.exists(os.path.join(vm.SNAPSHOTS_DIR, f"{a['id']}.json"))
               and os.path.exists(os.path.join(vm.SNAPSHOTS_DIR, f"{b['id']}.json")))

        with open(vm.JSONL_PATH, "a", encoding="utf-8") as f:
            f.write("{broken json\n")
        rows = vm.list_snapshots(include_archived=True)
        _check("malformed JSONL line is skipped", len(rows) >= 4)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_concurrent_snapshots_keep_index_complete() -> None:
    _section("tldraw store — concurrency")
    vm, tmp = _isolated_visual_module()
    try:
        created: list[str] = []
        lock = threading.Lock()

        def worker(i: int) -> None:
            meta = vm.snapshot(SAMPLE_SHAPES, label=f"thread {i}", tags=["thread"])
            with lock:
                created.append(meta["id"])

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        rows = vm.list_snapshots()
        index_text = open(vm.INDEX_PATH, encoding="utf-8").read()
        _check("all concurrent snapshots wrote JSONL rows", len(rows) == 16)
        _check("all concurrent snapshot ids are unique", len(set(created)) == 16)
        _check("INDEX.md includes every concurrent snapshot",
               all(sid in index_text for sid in created))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 4. CLI ─────────────────────────────────────────────────────────────

def test_cli_roundtrip() -> None:
    _section("tldraw store — CLI")
    tmp = tempfile.mkdtemp(prefix="visual-cli-test-")
    try:
        env = os.environ.copy()
        # Run the CLI in a scratch cwd so it picks up an isolated module load
        # with redirected paths via a one-shot shim script.
        shim = os.path.join(tmp, "shim.py")
        with open(shim, "w", encoding="utf-8") as f:
            f.write(
                "import sys, os, json\n"
                f"sys.path.insert(0, {repr(TLDRAW)})\n"
                "import store as vm\n"
                f"vm.SNAPSHOTS_DIR = {repr(os.path.join(tmp, 'snapshots'))}\n"
                f"vm.ARCHIVE_DIR = {repr(os.path.join(tmp, 'snapshots', 'archive'))}\n"
                f"vm.JSONL_PATH = {repr(os.path.join(tmp, 'snapshots.jsonl'))}\n"
                f"vm.INDEX_PATH = {repr(os.path.join(tmp, 'INDEX.md'))}\n"
                "sys.exit(vm.main(sys.argv[1:]))\n"
            )

        payload = json.dumps({"shapes": SAMPLE_SHAPES})
        r = subprocess.run(
            [sys.executable, shim, "snapshot", "--label", "cli-test",
             "--tags", "cli,smoke", "--note", "via stdin"],
            input=payload, capture_output=True, text=True, env=env, timeout=20,
        )
        _check("CLI snapshot exits 0", r.returncode == 0,
               r.stderr.strip()[-200:] if r.returncode else "")
        meta = json.loads(r.stdout) if r.returncode == 0 else {}
        sid = meta.get("id", "")
        _check("CLI snapshot returns id", bool(sid))

        r = subprocess.run(
            [sys.executable, shim, "list", "--json"],
            capture_output=True, text=True, env=env, timeout=20,
        )
        _check("CLI list exits 0", r.returncode == 0)
        rows = json.loads(r.stdout) if r.returncode == 0 else []
        _check("CLI list shows the snapshot",
               any(row.get("id") == sid for row in rows))

        r = subprocess.run(
            [sys.executable, shim, "archive", sid],
            capture_output=True, text=True, env=env, timeout=20,
        )
        _check("CLI archive exits 0", r.returncode == 0,
               r.stderr.strip()[-200:] if r.returncode else "")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 5. feature flag ────────────────────────────────────────────────────

def test_feature_flag() -> None:
    _section("feature flag")
    import onboard_features as of
    tmp = tempfile.mkdtemp(prefix="feat-test-")
    try:
        _check("tldraw disabled by default", not of.is_enabled(tmp, "tldraw"))
        of.write_features(tmp, {"tldraw": {"enabled": True, "beta": True}})
        _check("tldraw enabled after opt-in", of.is_enabled(tmp, "tldraw"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ── 6. adapter MCP configs ─────────────────────────────────────────────

def test_mcp_configs() -> None:
    _section("adapter MCP wiring")
    shared = os.path.join(HERE, "adapters", "_shared", "tldraw-mcp.json")
    _check("shared mcp config exists", os.path.exists(shared), shared)
    data = json.load(open(shared, encoding="utf-8"))
    server = (data.get("mcpServers") or {}).get("tldraw") or {}
    _check("shared mcp config registers tldraw",
           isinstance(server, dict) and bool(server.get("command")))

    for adapter in ("claude-code", "cursor", "antigravity"):
        manifest_path = os.path.join(HERE, "adapters", adapter, "adapter.json")
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        dsts = [entry.get("dst", "") for entry in manifest.get("files", [])]
        _check(f"{adapter} does not install tldraw MCP by default",
               not any("mcp" in dst.lower() for dst in dsts))


def test_skill_loader_feature_flag() -> None:
    _section("skill loader feature flag")
    import skill_loader as sl  # type: ignore
    importlib.reload(sl)
    tmp = tempfile.mkdtemp(prefix="skill-loader-feature-")
    old_path = sl.FEATURES_PATH
    try:
        sl.FEATURES_PATH = os.path.join(tmp, ".features.json")
        with open(sl.FEATURES_PATH, "w", encoding="utf-8") as f:
            json.dump({"tldraw": {"enabled": False, "beta": True}}, f)
        loaded = sl.progressive_load("draw an architecture diagram")
        _check("tldraw skill disabled when feature flag is off",
               all(row["name"] != "tldraw" for row in loaded))

        with open(sl.FEATURES_PATH, "w", encoding="utf-8") as f:
            json.dump({"tldraw": {"enabled": True, "beta": True}}, f)
        loaded = sl.progressive_load("draw an architecture diagram")
        _check("tldraw skill loads when feature flag is on",
               any(row["name"] == "tldraw" for row in loaded))
    finally:
        sl.FEATURES_PATH = old_path
        shutil.rmtree(tmp, ignore_errors=True)


# ── main ───────────────────────────────────────────────────────────────

def main() -> int:
    print("tldraw + visual memory validation")
    test_skill_file()
    test_registry()
    test_visual_memory_api()
    test_concurrent_snapshots_keep_index_complete()
    test_cli_roundtrip()
    test_feature_flag()
    test_mcp_configs()
    test_skill_loader_feature_flag()

    passed = sum(1 for _, ok, _ in _results if ok)
    total = len(_results)
    print(f"\n{passed}/{total} passed")
    failing = [n for n, ok, _ in _results if not ok]
    if failing:
        for name in failing:
            print(f"  failing: {name}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Regression test for learn.py's manual-stage episodic mirror.

Standalone (stdlib `unittest`, no third-party test dependency) because this
project currently ships no test harness — this is intended as the first test
file, easy to run with `python3 -m unittest` from the repo root or to remove
if the maintainer prefers to merge the fix without it.

Adapted from the downstream Perpetua-Tools suite that proved this fix
(3 passing tests + 6 real-world learn.py invocations, all evidence_ids
verified to resolve).
"""

import importlib.util
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path


def _load_learn(base_dir):
    """Load .agent/tools/learn.py with BASE/CANDIDATES pointed at base_dir.

    Sibling modules (text.word_set, cluster.pattern_id) are stubbed so the
    test needs no part of the harness beyond learn.py itself.
    """
    for name, attrs in [
        ("text", {"word_set": lambda *a, **k: set()}),
        ("cluster", {"pattern_id": lambda claim, cond: "testcid" + str(abs(hash((claim, tuple(cond)))))[:6]}),
    ]:
        m = types.ModuleType(name)
        for k, v in attrs.items():
            setattr(m, k, v)
        sys.modules[name] = m

    module_path = Path(__file__).with_name("learn.py")
    spec = importlib.util.spec_from_file_location("learn_under_test", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.BASE = base_dir
    mod.CANDIDATES = os.path.join(base_dir, "memory", "candidates")
    os.makedirs(mod.CANDIDATES, exist_ok=True)
    os.makedirs(os.path.join(base_dir, "memory", "episodic"), exist_ok=True)
    return mod


def _episodic(base_dir):
    path = os.path.join(base_dir, "memory", "episodic", "AGENT_LEARNINGS.jsonl")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


class EpisodicMirrorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_stage_writes_one_episodic_mirror(self):
        mod = _load_learn(self.tmp)
        cid, _ = mod.stage("Serialize timestamps in UTC", ["timestamps", "utc"])
        entries = _episodic(self.tmp)
        mirrors = [e for e in entries if e.get("action") == f"manual-stage:{cid}"]
        self.assertEqual(len(mirrors), 1)

    def test_evidence_id_resolves_to_the_mirror(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage("Serialize timestamps in UTC", ["timestamps", "utc"])
        candidate = json.loads(Path(path).read_text())
        evidence_ts = candidate["evidence_ids"][0]
        matching = [e for e in _episodic(self.tmp) if e["timestamp"] == evidence_ts]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["evidence_ids"], [evidence_ts])

    def test_append_mirror_fails_open_on_write_error(self):
        mod = _load_learn(self.tmp)
        mod.BASE = os.path.join(self.tmp, "does-not-exist")
        # Must not raise even though the target directory is missing.
        mod._append_episodic_mirror("deadbeef", "claim", "2026-01-01T00:00:00+00:00")


if __name__ == "__main__":
    unittest.main()

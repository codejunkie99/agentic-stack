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
    test needs no part of the harness beyond learn.py itself. hooks._episodic_io
    is imported from the real tree (stdlib-only locked append helper).
    """
    harness_dir = str(Path(__file__).resolve().parents[1] / "harness")
    if harness_dir not in sys.path:
        sys.path.insert(0, harness_dir)
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
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _names(candidates, suffix):
    return sorted(
        name for name in os.listdir(candidates) if name.endswith(suffix)
    )


CLAIM = "Serialize timestamps in UTC"
CONDITIONS = ["timestamps", "utc"]


class EpisodicMirrorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_stage_writes_one_episodic_mirror(self):
        mod = _load_learn(self.tmp)
        cid, _ = mod.stage(CLAIM, CONDITIONS)
        entries = _episodic(self.tmp)
        mirrors = [e for e in entries if e.get("action") == f"manual-stage:{cid}"]
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [f"{cid}.json"])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])

    def test_evidence_id_resolves_to_the_mirror(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        candidate = json.loads(Path(path).read_text())
        evidence_ts = candidate["evidence_ids"][0]
        matching = [e for e in _episodic(self.tmp) if e["timestamp"] == evidence_ts]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["evidence_ids"], [evidence_ts])

    def test_success_fsyncs_jsonl_before_unlock_and_directory_twice(self):
        mod = _load_learn(self.tmp)
        import hooks._episodic_io as episodic_io

        if not episodic_io._HAVE_FLOCK:
            self.skipTest("fcntl flock not available")

        real_fsync = episodic_io.os.fsync

        dir_calls = []
        real_dir = mod._fsync_dir

        def _record_dir(directory):
            dir_calls.append(directory)
            return real_dir(directory)

        order = []
        real_flock = episodic_io.fcntl.flock

        def _record_flock(fd, operation):
            if operation == episodic_io.fcntl.LOCK_UN:
                order.append("unlock")
            else:
                order.append("lock")
            return real_flock(fd, operation)

        def _record_fsync(fd):
            order.append("fsync")
            return real_fsync(fd)

        episodic_io.os.fsync = _record_fsync
        episodic_io.fcntl.flock = _record_flock
        mod._fsync_dir = _record_dir
        try:
            mod.stage(CLAIM, CONDITIONS)
        finally:
            episodic_io.os.fsync = real_fsync
            episodic_io.fcntl.flock = real_flock
            mod._fsync_dir = real_dir
        self.assertIn("lock", order)
        lock_at = order.index("lock")
        unlock_at = order.index("unlock", lock_at)
        self.assertIn("fsync", order[lock_at + 1:unlock_at])
        self.assertEqual(dir_calls, [mod.CANDIDATES, mod.CANDIDATES])
        self.assertEqual(len(_names(mod.CANDIDATES, ".json")), 1)
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 1)

    def test_stage_fails_closed_when_mirror_write_errors(self):
        mod = _load_learn(self.tmp)

        def _boom(*_a, **_k):
            raise OSError("forced mirror-write failure")

        mod._append_episodic_mirror = _boom
        with self.assertRaises(OSError):
            mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_episodic(self.tmp), [])

    def test_real_append_jsonl_failure_leaves_no_temp(self):
        mod = _load_learn(self.tmp)
        episodic_path = os.path.join(
            self.tmp, "memory", "episodic", "AGENT_LEARNINGS.jsonl")
        os.mkdir(episodic_path)
        with self.assertRaises(OSError):
            mod.stage(CLAIM, CONDITIONS)
        self.assertTrue(os.path.isdir(episodic_path))
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])

    def test_stage_keeps_fsynced_candidate_when_publish_fails(self):
        mod = _load_learn(self.tmp)
        original_replace = mod.os.replace

        def _boom(*_a, **_k):
            raise OSError("forced publish failure")

        mod.os.replace = _boom
        try:
            with self.assertRaises(OSError) as caught:
                mod.stage(CLAIM, CONDITIONS)
        finally:
            mod.os.replace = original_replace

        self.assertIn("forced publish failure", str(caught.exception))
        self.assertIn("fsynced temp kept at", str(caught.exception))
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])
        staged = _names(mod.CANDIDATES, ".tmp")
        self.assertEqual(len(staged), 1)
        staged_path = os.path.join(mod.CANDIDATES, staged[0])
        self.assertIn(staged_path, str(caught.exception))
        self.assertIn(
            '"claim": "Serialize timestamps in UTC"',
            Path(staged_path).read_text(),
        )
        entries = _episodic(self.tmp)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["result"], "success")

    def test_retry_recovers_temp_without_a_second_mirror(self):
        mod = _load_learn(self.tmp)
        original_replace = mod.os.replace

        def _boom(*_a, **_k):
            raise OSError("forced publish failure")

        mod.os.replace = _boom
        try:
            with self.assertRaises(OSError):
                mod.stage(CLAIM, CONDITIONS)
        finally:
            mod.os.replace = original_replace

        failed = _episodic(self.tmp)
        self.assertEqual(len(failed), 1)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [f"{cid}.json"])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_episodic(self.tmp), failed)
        candidate = json.loads(Path(path).read_text())
        self.assertEqual(candidate["evidence_ids"], [failed[0]["timestamp"]])

    def test_repeat_stage_reuses_the_first_mirror(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        first = json.loads(Path(path).read_text())
        before = _episodic(self.tmp)
        self.assertEqual(len(before), 1)
        cid2, path2 = mod.stage(CLAIM, CONDITIONS)
        second = json.loads(Path(path2).read_text())
        self.assertEqual(cid2, cid)
        self.assertEqual(second["evidence_ids"], first["evidence_ids"])
        self.assertEqual(second["evidence_ids"], [before[0]["timestamp"]])
        self.assertEqual(_episodic(self.tmp), before)
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])

    def test_planted_newer_temp_replaces_older_json_without_a_third_mirror(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        published = json.loads(Path(path).read_text())
        later = "2099-01-01T00:00:00+00:00"
        newer = dict(published)
        newer["evidence_ids"] = [later]
        newer["staged_at"] = later
        Path(os.path.join(mod.CANDIDATES, f".{cid}.later.tmp")).write_text(
            json.dumps(newer))
        episodic_path = os.path.join(
            self.tmp, "memory", "episodic", "AGENT_LEARNINGS.jsonl")
        with open(episodic_path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "timestamp": later,
                "action": f"manual-stage:{cid}",
                "result": "success",
            }) + "\n")
        mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(json.loads(Path(path).read_text())["evidence_ids"], [later])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 2)

    def test_stale_temp_is_removed_when_published_json_is_newer(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        published = json.loads(Path(path).read_text())
        stale_ts = "2000-01-01T00:00:00+00:00"
        stale = dict(published)
        stale["evidence_ids"] = [stale_ts]
        stale["staged_at"] = stale_ts
        temp_path = os.path.join(mod.CANDIDATES, f".{cid}.stale.tmp")
        Path(temp_path).write_text(json.dumps(stale))
        episodic_path = os.path.join(
            self.tmp, "memory", "episodic", "AGENT_LEARNINGS.jsonl")
        with open(episodic_path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "timestamp": stale_ts,
                "action": f"manual-stage:{cid}",
                "result": "success",
            }) + "\n")
        before = _episodic(self.tmp)
        mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(json.loads(Path(path).read_text())["evidence_ids"],
                         published["evidence_ids"])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_episodic(self.tmp), before)

    def test_evidence_substring_does_not_resume_temp(self):
        mod = _load_learn(self.tmp)
        cid = mod.pattern_id(CLAIM, CONDITIONS)
        buried = "2026-01-01T00:00:00+00:00"
        temp_path = os.path.join(mod.CANDIDATES, f".{cid}.buried.tmp")
        Path(temp_path).write_text(json.dumps({
            "id": cid,
            "claim": CLAIM,
            "evidence_ids": [buried],
        }))
        episodic_path = os.path.join(
            self.tmp, "memory", "episodic", "AGENT_LEARNINGS.jsonl")
        with open(episodic_path, "a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "timestamp": "1999-01-01T00:00:00+00:00",
                "detail": f"see {buried} in prose only",
            }) + "\n")
        cid_out, path = mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(cid_out, cid)
        published = json.loads(Path(path).read_text())
        self.assertNotEqual(published["evidence_ids"], [buried])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        mirrors = [
            row for row in _episodic(self.tmp)
            if row.get("action") == f"manual-stage:{cid}"
        ]
        self.assertEqual(len(mirrors), 1)
        self.assertEqual(mirrors[0]["timestamp"], published["evidence_ids"][0])

    def test_corrupt_temp_is_deleted_then_fresh_stage_runs(self):
        mod = _load_learn(self.tmp)
        cid = mod.pattern_id(CLAIM, CONDITIONS)
        temp_path = os.path.join(mod.CANDIDATES, f".{cid}.corrupt.tmp")
        Path(temp_path).write_text("{not json")
        mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [f"{cid}.json"])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 1)

    def test_mirror_failure_before_temp_leaves_no_candidate(self):
        mod = _load_learn(self.tmp)

        def _mirror(*_a, **_k):
            raise OSError("forced mirror-write failure")

        mod._append_episodic_mirror = _mirror
        with self.assertRaises(OSError) as caught:
            mod.stage(CLAIM, CONDITIONS)
        self.assertIn("forced mirror-write failure", str(caught.exception))
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_episodic(self.tmp), [])

    def test_keyboard_interrupt_from_mirror_is_not_an_oserror(self):
        mod = _load_learn(self.tmp)

        def _mirror(*_a, **_k):
            raise KeyboardInterrupt

        mod._append_episodic_mirror = _mirror
        with self.assertRaises(KeyboardInterrupt):
            mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])

    def test_ambiguous_leftovers_fail_closed(self):
        mod = _load_learn(self.tmp)
        cid = mod.pattern_id(CLAIM, CONDITIONS)
        for suffix in ("a", "b"):
            Path(os.path.join(mod.CANDIDATES, f".{cid}.{suffix}.tmp")).write_text("{}")
        with self.assertRaises(OSError) as caught:
            mod.stage(CLAIM, CONDITIONS)
        message = str(caught.exception)
        self.assertIn("ambiguous leftover temps", message)
        self.assertIn(f".{cid}.a.tmp", message)
        self.assertIn(f".{cid}.b.tmp", message)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])
        self.assertEqual(len(_names(mod.CANDIDATES, ".tmp")), 2)
        self.assertEqual(_episodic(self.tmp), [])

    def test_fsync_failure_after_mirror_line_retries_without_a_second_row(self):
        mod = _load_learn(self.tmp)
        real_append = mod._append_episodic_mirror

        def _append(*args, **kwargs):
            real_fsync = mod.os.fsync

            def _boom(_fd):
                raise OSError("forced fsync failure")

            mod.os.fsync = _boom
            try:
                return real_append(*args, **kwargs)
            finally:
                mod.os.fsync = real_fsync

        mod._append_episodic_mirror = _append
        with self.assertRaises(OSError) as caught:
            mod.stage(CLAIM, CONDITIONS)
        self.assertIn("forced fsync failure", str(caught.exception))
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 1)
        mod._append_episodic_mirror = real_append
        cid, path = mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [f"{cid}.json"])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 1)
        candidate = json.loads(Path(path).read_text())
        self.assertEqual(
            candidate["evidence_ids"],
            [_episodic(self.tmp)[0]["timestamp"]],
        )

    def test_published_read_error_does_not_clobber_json(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        original = Path(path).read_text()
        before = _episodic(self.tmp)
        temp_path = os.path.join(mod.CANDIDATES, f".{cid}.newer.tmp")
        Path(temp_path).write_text(original)
        real_load = mod._load_json_object

        def _load(candidate_path):
            if os.path.abspath(candidate_path) == os.path.abspath(path):
                raise OSError("forced published read failure")
            return real_load(candidate_path)

        mod._load_json_object = _load
        with self.assertRaises(OSError) as caught:
            mod.stage(CLAIM, CONDITIONS)
        self.assertIn("forced published read failure", str(caught.exception))
        self.assertEqual(Path(path).read_text(), original)
        self.assertTrue(os.path.isfile(temp_path))
        self.assertEqual(_episodic(self.tmp), before)

    def test_corrupt_temp_beside_published_json_does_not_remirror(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        published = Path(path).read_text()
        before = _episodic(self.tmp)
        Path(os.path.join(mod.CANDIDATES, f".{cid}.corrupt.tmp")).write_text("{not json")
        mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(Path(path).read_text(), published)
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_episodic(self.tmp), before)

    def test_keyboard_interrupt_after_mirror_write_retries_without_second_mirror(self):
        mod = _load_learn(self.tmp)
        real_append = mod._append_episodic_mirror

        def _append(*args, **kwargs):
            real_append(*args, **kwargs)
            raise KeyboardInterrupt

        mod._append_episodic_mirror = _append
        with self.assertRaises(KeyboardInterrupt):
            mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 1)
        mod._append_episodic_mirror = real_append
        cid, resumed = mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(_names(mod.CANDIDATES, ".json"), [f"{cid}.json"])
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(len(_episodic(self.tmp)), 1)
        candidate = json.loads(Path(resumed).read_text())
        self.assertEqual(
            candidate["evidence_ids"],
            [_episodic(self.tmp)[0]["timestamp"]],
        )

    def test_append_jsonl_once_reuses_the_first_row(self):
        import hooks._episodic_io as episodic_io

        path = os.path.join(self.tmp, "once.jsonl")
        first = {"timestamp": "t1", "action": "manual-stage:abc"}
        second = {"timestamp": "t2", "action": "manual-stage:abc"}
        self.assertEqual(
            episodic_io.append_jsonl_once(
                path, first, match_action="manual-stage:abc")["timestamp"],
            "t1",
        )
        self.assertEqual(
            episodic_io.append_jsonl_once(
                path, second, match_action="manual-stage:abc")["timestamp"],
            "t1",
        )
        episodic_io.append_jsonl(path, second)
        rows = [
            json.loads(line)
            for line in Path(path).read_text().splitlines()
            if line.strip()
        ]
        self.assertEqual([row["timestamp"] for row in rows], ["t1", "t2"])

    def test_identical_resumable_temps_publish_once(self):
        mod = _load_learn(self.tmp)
        cid, path = mod.stage(CLAIM, CONDITIONS)
        published = Path(path).read_text()
        os.remove(path)
        for suffix in ("a", "b"):
            Path(os.path.join(mod.CANDIDATES, f".{cid}.{suffix}.tmp")).write_text(
                published)
        before = _episodic(self.tmp)
        mod.stage(CLAIM, CONDITIONS)
        self.assertEqual(Path(path).read_text(), published)
        self.assertEqual(_names(mod.CANDIDATES, ".tmp"), [])
        self.assertEqual(_episodic(self.tmp), before)

    def test_evidence_landed_reads_under_exclusive_lock(self):
        mod = _load_learn(self.tmp)
        import hooks._episodic_io as episodic_io

        path = os.path.join(
            self.tmp, "memory", "episodic", "AGENT_LEARNINGS.jsonl"
        )
        row = {"timestamp": "2026-09-26T00:00:00+00:00", "action": "test"}
        Path(path).write_text(json.dumps(row) + "\n")
        if not episodic_io._HAVE_FLOCK:
            self.skipTest("fcntl flock not available")

        order = []
        real_flock = episodic_io.fcntl.flock

        def _record_flock(fd, operation):
            if operation == episodic_io.fcntl.LOCK_UN:
                order.append("unlock")
            else:
                order.append("lock")
            return real_flock(fd, operation)

        episodic_io.fcntl.flock = _record_flock
        try:
            self.assertTrue(mod._evidence_landed(path, row["timestamp"]))
        finally:
            episodic_io.fcntl.flock = real_flock

        self.assertEqual(order, ["lock", "unlock"])

    def test_evidence_read_error_keeps_resumable_temp(self):
        mod = _load_learn(self.tmp)
        cid = mod.pattern_id(CLAIM, CONDITIONS)
        temp_path = os.path.join(mod.CANDIDATES, f".{cid}.pending.tmp")
        timestamp = "2026-09-26T00:00:00+00:00"
        Path(temp_path).write_text(json.dumps({
            "id": cid,
            "claim": CLAIM,
            "evidence_ids": [timestamp],
        }))
        real_check = mod.has_jsonl_timestamp
        mod.has_jsonl_timestamp = lambda *_a, **_k: (_ for _ in ()).throw(
            OSError("forced locked-read failure")
        )
        try:
            with self.assertRaises(OSError) as caught:
                mod.stage(CLAIM, CONDITIONS)
        finally:
            mod.has_jsonl_timestamp = real_check
        self.assertIn("forced locked-read failure", str(caught.exception))
        self.assertTrue(os.path.isfile(temp_path))
        self.assertEqual(_episodic(self.tmp), [])

    def test_missing_episodic_file_is_not_created(self):
        import hooks._episodic_io as episodic_io

        path = os.path.join(self.tmp, "memory", "episodic", "absent.jsonl")
        self.assertFalse(os.path.exists(path))
        self.assertFalse(
            episodic_io.has_jsonl_timestamp(path, "2026-09-26T00:00:00+00:00")
        )
        self.assertFalse(os.path.exists(path))


if __name__ == "__main__":
    unittest.main()

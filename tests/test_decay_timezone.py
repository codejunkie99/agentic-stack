"""Regression tests for the decay.py timezone fix.

PR #24 fixed an `aware vs naive datetime` crash on every clean pi exit (the
new `session_shutdown` hook surfaced it). This test pins the four shapes
decay needs to handle so the next refactor doesn't regress.
"""
import datetime
import os
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO_ROOT, ".agent", "memory"))
sys.path.insert(0, os.path.join(REPO_ROOT, ".agent", "harness"))

from decay import decay_old_entries  # noqa: E402


def _utc_iso(dt):
    return dt.isoformat()


class DecayTimezoneTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: __import__("shutil").rmtree(self.tmp, ignore_errors=True))
        # Anchors: now, yesterday, 200d ago. 200d > DECAY_DAYS (90).
        self.now_utc = datetime.datetime.now(datetime.timezone.utc)
        self.recent_utc = self.now_utc - datetime.timedelta(days=1)
        self.old_utc = self.now_utc - datetime.timedelta(days=200)

    def _entry(self, ts_str, *, salience_low=True):
        # pain_score / importance / recurrence drive salience_score().
        # Defaults here keep score < SALIENCE_FLOOR (2.0) so old entries
        # actually decay. Override for the "high-salience old entry" case.
        return {
            "timestamp": ts_str,
            "pain_score": 1 if salience_low else 9,
            "importance": 1 if salience_low else 9,
            "recurrence_count": 1,
        }

    def test_aware_utc_old_entry_archives(self):
        entries = [self._entry(_utc_iso(self.old_utc))]
        kept, archived = decay_old_entries(entries, self.tmp)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(archived), 1)

    def test_aware_utc_recent_entry_keeps(self):
        entries = [self._entry(_utc_iso(self.recent_utc))]
        kept, archived = decay_old_entries(entries, self.tmp)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(archived), 0)

    def test_naive_old_entry_treated_as_utc(self):
        # Pre-PR Python writers emitted naive timestamps. Decay must treat
        # them as UTC and archive correctly without crashing on aware-vs-naive.
        naive_old = self.old_utc.replace(tzinfo=None).isoformat()
        entries = [self._entry(naive_old)]
        kept, archived = decay_old_entries(entries, self.tmp)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(archived), 1)

    def test_mixed_naive_and_aware_no_crash(self):
        # The exact crash this PR fixes: comparing naive cutoff to aware
        # entry. Flip into the same pass to make sure both shapes coexist.
        entries = [
            self._entry(_utc_iso(self.old_utc)),
            self._entry(self.old_utc.replace(tzinfo=None).isoformat()),
            self._entry(_utc_iso(self.recent_utc)),
            self._entry(self.recent_utc.replace(tzinfo=None).isoformat()),
        ]
        kept, archived = decay_old_entries(entries, self.tmp)
        self.assertEqual(len(archived), 2)
        self.assertEqual(len(kept), 2)

    def test_malformed_timestamp_kept(self):
        # ValueError on fromisoformat → keep the entry, don't crash, don't archive.
        entries = [self._entry("not-a-date"), self._entry("")]
        kept, archived = decay_old_entries(entries, self.tmp)
        self.assertEqual(len(archived), 0)
        self.assertEqual(len(kept), 2)

    def test_archive_filename_uses_utc_date(self):
        # Pre-PR the archive filename used `datetime.date.today()` (local
        # date) while the cutoff above used UTC. Asymmetric. Filename now
        # tracks UTC so a tz-jumping user gets a deterministic path.
        entries = [self._entry(_utc_iso(self.old_utc))]
        kept, archived = decay_old_entries(entries, self.tmp)
        files = os.listdir(self.tmp)
        self.assertEqual(len(files), 1)
        expected_date = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        self.assertEqual(files[0], f"archive_{expected_date}.jsonl")


if __name__ == "__main__":
    unittest.main()

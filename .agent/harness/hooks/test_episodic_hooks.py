"""Hook regression tests for non-fatal episodic filesystem failures."""

import contextlib
import io
import sys
import unittest
from pathlib import Path

HARNESS = Path(__file__).resolve().parents[1]
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))

from hooks import on_failure, post_execution  # noqa: E402


class EpisodicHookTest(unittest.TestCase):
    def test_post_execution_sync_error_does_not_escape(self):
        original_append = post_execution.append_jsonl
        original_source = post_execution.build_source
        post_execution.append_jsonl = lambda *_a, **_k: (_ for _ in ()).throw(
            OSError("forced fsync failure")
        )
        post_execution.build_source = lambda skill: {"skill": skill}
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = post_execution.log_execution(
                    "test", "action", "result", True
                )
            self.assertEqual(result["result"], "success")
            self.assertIn("forced fsync failure", stderr.getvalue())
        finally:
            post_execution.append_jsonl = original_append
            post_execution.build_source = original_source

    def test_on_failure_sync_error_does_not_escape(self):
        original_append = on_failure.append_jsonl
        original_source = on_failure.build_source
        original_count = on_failure._count_recent_failures
        on_failure.append_jsonl = lambda *_a, **_k: (_ for _ in ()).throw(
            OSError("forced fsync failure")
        )
        on_failure.build_source = lambda skill: {"skill": skill}
        on_failure._count_recent_failures = lambda _skill: 0
        try:
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = on_failure.on_failure("test", "action", "boom")
            self.assertEqual(result["result"], "failure")
            self.assertIn("forced fsync failure", stderr.getvalue())
        finally:
            on_failure.append_jsonl = original_append
            on_failure.build_source = original_source
            on_failure._count_recent_failures = original_count


if __name__ == "__main__":
    unittest.main()

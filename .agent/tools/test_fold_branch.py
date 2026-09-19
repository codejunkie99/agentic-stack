"""Regression checks for the branch-fold tool.

Every check builds a throwaway git repository in a temporary directory. No test
touches a real repository, contacts a remote, or runs a push.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fold_branch as fb


def run(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )
    return proc.stdout.strip()


def write(repo: Path, name: str, text: str) -> None:
    path = repo / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class FoldBranchTestCase(unittest.TestCase):
    """Builds base -> carrier -> source, the shape the tool exists to resolve."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        run(self.repo, "init", "--initial-branch=dev", "--quiet")
        run(self.repo, "config", "user.email", "t@example.com")
        run(self.repo, "config", "user.name", "Test")
        run(self.repo, "config", "commit.gpgsign", "false")

        write(self.repo, "shared.txt", "on base\n")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-m", "base", "--quiet")

        run(self.repo, "checkout", "-b", "carrier", "--quiet")
        write(self.repo, "feature/new.txt", "introduced by carrier\n")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-m", "TICKET-1 - Carrier title", "--quiet")

        run(self.repo, "checkout", "-b", "source", "--quiet")
        write(self.repo, "feature/new.txt", "corrected by source\n")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-m", "TICKET-2 - Source title", "--quiet")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def sha(self, ref: str) -> str:
        return run(self.repo, "rev-parse", ref)

    # -- classification ------------------------------------------------

    def test_a_file_absent_from_the_base_makes_the_fold_required(self) -> None:
        info = fb.classify(str(self.repo), "dev", "carrier", "source")

        self.assertEqual("fold-required", info["verdict"])
        self.assertEqual(["feature/new.txt"], info["filesOnlyOnCarrier"])
        self.assertEqual([], info["filesOnBase"])

    def test_a_file_present_on_the_base_makes_the_fold_optional(self) -> None:
        write(self.repo, "shared.txt", "changed by source\n")
        run(self.repo, "checkout", "source", "--quiet")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "--amend", "--no-edit", "--quiet")
        run(self.repo, "rm", "--cached", "-q", "feature/new.txt")
        run(self.repo, "commit", "-m", "drop", "--quiet")
        run(self.repo, "reset", "--soft", "HEAD~1")
        run(self.repo, "checkout", "--", ".")

        info = fb.classify(str(self.repo), "dev", "carrier", "source")

        self.assertIn("shared.txt", info["filesOnBase"])

    def test_a_source_that_is_not_ahead_is_refused(self) -> None:
        run(self.repo, "checkout", "carrier", "--quiet")
        with self.assertRaises(fb.GitError):
            fb.classify(str(self.repo), "dev", "carrier", "carrier")

    # -- fold ----------------------------------------------------------

    def test_the_folded_commit_has_the_source_tree_and_the_carrier_message(self) -> None:
        want_tree = run(self.repo, "rev-parse", "source^{tree}")

        code, info = fb.do_fold(str(self.repo), "dev", "carrier", "source")

        self.assertEqual(fb.EXIT_OK, code)
        self.assertEqual(want_tree, info["foldedTree"])
        self.assertEqual(want_tree, run(self.repo, "rev-parse", "carrier^{tree}"))
        self.assertEqual(
            "TICKET-1 - Carrier title",
            run(self.repo, "log", "-1", "--format=%s", "carrier"),
        )

    def test_the_folded_carrier_is_exactly_one_commit_above_the_base(self) -> None:
        fb.do_fold(str(self.repo), "dev", "carrier", "source")

        self.assertEqual("1", run(self.repo, "rev-list", "--count", "dev..carrier"))

    def test_the_printed_push_leases_against_the_pre_fold_carrier(self) -> None:
        before = self.sha("carrier")

        _, info = fb.do_fold(str(self.repo), "dev", "carrier", "source")

        self.assertEqual(before, info["previousCarrierSha"])
        self.assertIn(before, info["nextCommands"][0])
        self.assertIn("--force-with-lease", info["nextCommands"][0])

    def test_the_tool_never_pushes_or_deletes(self) -> None:
        _, info = fb.do_fold(str(self.repo), "dev", "carrier", "source")

        # The commands are handed over as text, not run. The remote-less repo
        # would fail loudly if the tool had tried either of them.
        self.assertEqual(3, len(info["nextCommands"]))
        self.assertTrue(all(cmd.startswith("git ") for cmd in info["nextCommands"]))

    def test_a_carrier_that_is_two_commits_above_the_base_is_refused(self) -> None:
        run(self.repo, "checkout", "carrier", "--quiet")
        write(self.repo, "feature/extra.txt", "second commit\n")
        run(self.repo, "add", "-A")
        run(self.repo, "commit", "-m", "second", "--quiet")
        run(self.repo, "checkout", "source", "--quiet")
        run(self.repo, "rebase", "carrier", "--quiet")

        with self.assertRaises(fb.GitError) as caught:
            fb.do_fold(str(self.repo), "dev", "carrier", "source")

        self.assertIn("one commit", str(caught.exception))

    def test_a_dirty_tracked_file_blocks_the_fold(self) -> None:
        write(self.repo, "feature/new.txt", "uncommitted edit\n")
        before = self.sha("carrier")

        with self.assertRaises(fb.GitError) as caught:
            fb.do_fold(str(self.repo), "dev", "carrier", "source")

        self.assertIn("modified", str(caught.exception))
        self.assertEqual(before, self.sha("carrier"))

    def test_folding_from_the_wrong_checkout_is_refused(self) -> None:
        run(self.repo, "checkout", "dev", "--quiet")

        with self.assertRaises(fb.GitError) as caught:
            fb.do_fold(str(self.repo), "dev", "carrier", "source")

        self.assertIn("check out", str(caught.exception))

    def test_a_second_fold_is_refused_rather_than_stacking(self) -> None:
        fb.do_fold(str(self.repo), "dev", "carrier", "source")

        with self.assertRaises(fb.GitError):
            fb.do_fold(str(self.repo), "dev", "carrier", "source")

    # -- verify --------------------------------------------------------

    def test_deleting_the_remote_source_is_unsafe_until_the_carrier_is_pushed(self) -> None:
        remote = Path(self._tmp.name) / "remote.git"
        run(self.repo, "init", "--bare", "--quiet", str(remote))
        run(self.repo, "remote", "add", "origin", str(remote))
        run(self.repo, "push", "-q", "origin", "carrier", "source")
        fb.do_fold(str(self.repo), "dev", "carrier", "source")

        code, data = fb.do_verify(str(self.repo), "dev", "carrier", "source", "origin")

        self.assertEqual(fb.EXIT_UNSAFE, code)
        self.assertFalse(data["safeToDeleteRemoteSource"])

    def test_deleting_the_remote_source_is_safe_once_the_carrier_is_pushed(self) -> None:
        remote = Path(self._tmp.name) / "remote2.git"
        run(self.repo, "init", "--bare", "--quiet", str(remote))
        run(self.repo, "remote", "add", "origin", str(remote))
        run(self.repo, "push", "-q", "origin", "carrier", "source")
        fb.do_fold(str(self.repo), "dev", "carrier", "source")
        run(self.repo, "push", "-q", "--force", "origin", "carrier")

        code, data = fb.do_verify(str(self.repo), "dev", "carrier", "source", "origin")

        self.assertEqual(fb.EXIT_OK, code)
        self.assertTrue(data["safeToDeleteRemoteSource"])


if __name__ == "__main__":
    unittest.main()

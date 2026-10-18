#!/usr/bin/env python3
"""The trigger matcher must match whole words, never substrings of longer words.

Run from the agentic-stack repo root:

    python3 tests/test_skill_loader.py

The 2026-10-17 report: `bro` fired on "browser", `how` on "show", `aml` on
"yaml" and `vo` on "void", so an unrelated request pulled in the wrong skill.
"""
from __future__ import annotations

import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, ".agent", "tools"))

import skill_loader as sl  # noqa: E402


def manifest(*triggers):
    return [{"name": "probe", "triggers": list(triggers)}]


class WholeWord(unittest.TestCase):
    def matched(self, trigger, text):
        return bool(sl.match_triggers(text, manifest(trigger)))

    def test_short_word_does_not_match_inside_a_longer_word(self):
        for trigger, haystack in (("bro", "open the browser"), ("how", "show me"),
                                  ("aml", "edit the yaml file"), ("vo", "the void type")):
            with self.subTest(trigger=trigger):
                self.assertFalse(self.matched(trigger, haystack))

    def test_the_same_word_still_matches(self):
        for trigger, haystack in (("bro", "bro, restate that"), ("how", "how do i start"),
                                  ("aml", "run the aml check"), ("vo", "vo means value object")):
            with self.subTest(trigger=trigger):
                self.assertTrue(self.matched(trigger, haystack))

    def test_multi_word_trigger_respects_its_outer_boundaries(self):
        self.assertTrue(self.matched("net aspire", "use net aspire here"))
        self.assertFalse(self.matched("net aspire", "planet aspire to be"))

    def test_matching_is_case_insensitive(self):
        self.assertTrue(self.matched("design.md", "read the DESIGN.MD file"))

    def test_a_trigger_that_starts_with_a_symbol_still_matches(self):
        self.assertTrue(self.matched(".net aspire", "use .net aspire here"))

    def test_blank_triggers_never_match(self):
        self.assertEqual(sl.match_triggers("anything at all", manifest("", "   ")), [])


class RealManifest(unittest.TestCase):
    def test_a_normal_request_still_loads_its_skill(self):
        rows = sl.load_manifest()
        if not rows:
            self.skipTest("no skills/_manifest.jsonl in this checkout")
        names = {row["name"] for row in sl.match_triggers("draw an architecture diagram", rows)}
        self.assertIn("tldraw", names)


if __name__ == "__main__":
    unittest.main()

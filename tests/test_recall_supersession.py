"""recall.py must not surface superseded lessons alongside their replacement.

lessons.jsonl is append-only: supersession writes a NEW id whose
`supersedes` field points at the old one -- it never edits the old row.
The old row keeps `status: "accepted"` forever, so a naive per-row
`status == "accepted"` filter (recall's own dedupe already handles same-id
retraction, but not this different-id case) returns both the stale and
the replacement guidance for the same topic. Fixed by sharing
`render_lessons.superseded_by_map` between rendering and retrieval so
they never disagree about which lessons are currently retired.
"""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECALL = ROOT / ".agent" / "tools" / "recall.py"
RENDER_LESSONS = ROOT / ".agent" / "memory" / "render_lessons.py"


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _lesson(lesson_id, claim, conditions, status="accepted", supersedes=None):
    return {
        "id": lesson_id,
        "claim": claim,
        "conditions": conditions,
        "status": status,
        "supersedes": supersedes,
        "accepted_at": "2026-08-01T00:00:00+00:00",
    }


class RecallSupersessionTest(unittest.TestCase):
    def with_semantic_dir(self):
        tmp = tempfile.TemporaryDirectory()
        semantic_dir = Path(tmp.name) / ".agent" / "memory" / "semantic"
        semantic_dir.mkdir(parents=True)
        return tmp, semantic_dir

    def write_lessons(self, semantic_dir: Path, lessons):
        path = semantic_dir / "lessons.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for lesson in lessons:
                f.write(json.dumps(lesson) + "\n")

    def load_recall(self, semantic_dir: Path, module_name: str):
        recall = load_module(RECALL, module_name)
        recall.LESSONS_JSONL = str(semantic_dir / "lessons.jsonl")
        recall.LESSONS_MD = str(semantic_dir / "missing.md")
        return recall

    def test_superseded_lesson_is_excluded_from_structured_load(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)
        old_id, new_id = "lesson_old_git_tip", "lesson_new_git_tip"
        self.write_lessons(
            semantic_dir,
            [
                _lesson(old_id, "git branch -f silently no-ops on checked-out branch",
                        ["git branch -f"]),
                _lesson(new_id, "git branch -f refuses with exit 128 on checked-out branch",
                        ["git branch -f", "rollback"], supersedes=old_id),
            ],
        )
        recall = self.load_recall(semantic_dir, "recall_1")

        loaded = recall._load_structured()
        ids = [row["id"] for row in loaded]

        self.assertIn(new_id, ids)
        self.assertNotIn(old_id, ids)

    def test_recall_ranks_replacement_not_the_superseded_lesson(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)
        old_id, new_id = "lesson_old_git_tip", "lesson_new_git_tip"
        self.write_lessons(
            semantic_dir,
            [
                _lesson(
                    old_id,
                    "git branch -f <name> <sha> silently no-ops when checked out",
                    ["git branch -f", "cherry-pick loop"],
                ),
                _lesson(
                    new_id,
                    "git branch -f <name> <sha> refuses to move the checked-out "
                    "branch; use git update-ref then git restore",
                    ["git branch -f", "git update-ref", "rollback"],
                    supersedes=old_id,
                ),
            ],
        )
        recall = self.load_recall(semantic_dir, "recall_2")

        result, meta = recall.recall(
            "git branch -f cherry-pick rollback update-ref", top_k=5, min_score=0.01
        )
        returned_ids = [row.get("id") for row in result if row.get("id")]

        self.assertIn(new_id, returned_ids)
        self.assertNotIn(old_id, returned_ids)
        self.assertEqual(meta["considered"], 1)

    def test_provisional_supersession_does_not_retire_old_lesson(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)
        old_id, provisional_id = "lesson_active", "lesson_provisional"
        self.write_lessons(
            semantic_dir,
            [
                _lesson(old_id, "Keep using the established rollback procedure",
                        ["rollback"]),
                _lesson(
                    provisional_id,
                    "Experimental rollback procedure under review",
                    ["rollback"],
                    status="provisional",
                    supersedes=old_id,
                ),
            ],
        )
        recall = self.load_recall(semantic_dir, "recall_3")

        loaded = recall._load_structured()
        ids = [row["id"] for row in loaded]

        self.assertIn(old_id, ids)
        self.assertNotIn(provisional_id, ids)


class SupersededByMapTest(unittest.TestCase):
    """render_lessons.superseded_by_map is the single source of truth both
    rendering and recall share -- exercised directly so drift between the
    two consumers is caught here, not just at the recall integration level.
    """

    def test_only_accepted_supersessions_are_mapped(self):
        render_lessons = load_module(RENDER_LESSONS, "render_lessons_map_test")
        lessons = [
            _lesson("lesson_a", "a", []),
            _lesson("lesson_b", "b", [], supersedes="lesson_a"),
            _lesson("lesson_c", "c", []),
            _lesson("lesson_d", "d", [], status="provisional", supersedes="lesson_c"),
        ]

        mapping = render_lessons.superseded_by_map(lessons)

        self.assertEqual(mapping, {"lesson_a": "lesson_b"})


if __name__ == "__main__":
    unittest.main()

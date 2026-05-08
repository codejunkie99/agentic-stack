import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RETRACT_LESSON = ROOT / ".agent" / "tools" / "retract_lesson.py"
RENDER_LESSONS = ROOT / ".agent" / "memory" / "render_lessons.py"
RECALL = ROOT / ".agent" / "tools" / "recall.py"


def load_module(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RetractLessonTest(unittest.TestCase):
    def with_semantic_dir(self):
        tmp = tempfile.TemporaryDirectory()
        memory_root = Path(tmp.name) / ".agent" / "memory"
        semantic_dir = memory_root / "semantic"
        semantic_dir.mkdir(parents=True)
        return tmp, semantic_dir

    def write_lessons(self, semantic_dir: Path, lessons):
        path = semantic_dir / "lessons.jsonl"
        with path.open("w", encoding="utf-8") as f:
            for lesson in lessons:
                f.write(json.dumps(lesson) + "\n")

    def test_retract_lesson_appends_retracted_state_and_renders(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)

        lesson_id = "lesson_cache_retry_window"
        self.write_lessons(
            semantic_dir,
            [
                {
                    "id": lesson_id,
                    "claim": "Use retry windows for transient cache misses.",
                    "conditions": ["cache", "retry"],
                    "evidence_ids": ["ep_1"],
                    "status": "accepted",
                    "accepted_at": "2026-05-01T00:00:00+00:00",
                    "reviewer": "host-agent",
                    "rationale": "Repeatedly prevented flaky failures",
                    "cluster_size": 2,
                    "canonical_salience": 7.2,
                    "confidence": 0.71,
                    "support_count": 0,
                    "contradiction_count": 0,
                    "supersedes": None,
                    "source_candidate": "cand_1",
                }
            ],
        )

        retract = load_module(RETRACT_LESSON, "retract_lesson")
        render = load_module(RENDER_LESSONS, "render_lessons")

        updated, md_path = retract.retract_lesson(
            lesson_id=lesson_id,
            rationale="No longer valid after cache backend migration.",
            reviewer="utkarsh",
            semantic_dir=str(semantic_dir),
        )

        self.assertEqual(updated["status"], "retracted")
        self.assertEqual(updated["retracted_by"], "utkarsh")
        self.assertIn("retracted_at", updated)

        lessons = [l for l in render.load_lessons(str(semantic_dir)) if l.get("id") == lesson_id]
        self.assertEqual(len(lessons), 2)
        self.assertEqual(lessons[-1]["status"], "retracted")

        text = Path(md_path).read_text(encoding="utf-8")
        self.assertIn("status=retracted", text)
        self.assertIn("[RETRACTED] Use retry windows for transient cache misses.", text)

    def test_retracted_lesson_is_not_returned_by_recall(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)

        target_id = "lesson_retracted_timeout"
        keep_id = "lesson_keep_timeouts"
        self.write_lessons(
            semantic_dir,
            [
                {
                    "id": target_id,
                    "claim": "Always double timeout values before deploy.",
                    "conditions": ["timeout", "deploy"],
                    "evidence_ids": [],
                    "status": "accepted",
                    "accepted_at": "2026-05-01T00:00:00+00:00",
                    "reviewer": "host-agent",
                    "rationale": "old guidance",
                    "cluster_size": 1,
                    "canonical_salience": 6.8,
                    "confidence": 0.66,
                    "support_count": 0,
                    "contradiction_count": 0,
                    "supersedes": None,
                    "source_candidate": "cand_a",
                },
                {
                    "id": keep_id,
                    "claim": "Tune timeout values per upstream SLA, not globally.",
                    "conditions": ["timeout", "sla"],
                    "evidence_ids": [],
                    "status": "accepted",
                    "accepted_at": "2026-05-01T00:00:00+00:00",
                    "reviewer": "host-agent",
                    "rationale": "current guidance",
                    "cluster_size": 1,
                    "canonical_salience": 6.9,
                    "confidence": 0.7,
                    "support_count": 0,
                    "contradiction_count": 0,
                    "supersedes": None,
                    "source_candidate": "cand_b",
                },
            ],
        )

        retract = load_module(RETRACT_LESSON, "retract_lesson_2")
        retract.retract_lesson(
            lesson_id=target_id,
            rationale="Guideline is too broad and causes regressions.",
            reviewer="utkarsh",
            semantic_dir=str(semantic_dir),
        )

        recall = load_module(RECALL, "recall")
        recall.LESSONS_JSONL = str(semantic_dir / "lessons.jsonl")
        recall.LESSONS_MD = str(semantic_dir / "LESSONS.md")

        result, _meta = recall.recall("timeout deploy sla", top_k=10, min_score=0.01)
        ids = [row.get("id") for row in result]
        self.assertNotIn(target_id, ids)
        self.assertIn(keep_id, ids)

    def test_retract_requires_accepted_status(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)

        lesson_id = "lesson_provisional_only"
        self.write_lessons(
            semantic_dir,
            [
                {
                    "id": lesson_id,
                    "claim": "Try provisional lesson first.",
                    "conditions": [],
                    "evidence_ids": [],
                    "status": "provisional",
                    "accepted_at": "2026-05-01T00:00:00+00:00",
                    "reviewer": "host-agent",
                    "rationale": "needs more evidence",
                    "cluster_size": 1,
                    "canonical_salience": 5.0,
                    "confidence": 0.5,
                    "support_count": 0,
                    "contradiction_count": 0,
                    "supersedes": None,
                    "source_candidate": "cand_prov",
                }
            ],
        )

        retract = load_module(RETRACT_LESSON, "retract_lesson_3")
        with self.assertRaises(ValueError):
            retract.retract_lesson(
                lesson_id=lesson_id,
                rationale="cannot retract non-accepted",
                reviewer="utkarsh",
                semantic_dir=str(semantic_dir),
            )

    def test_retract_requires_non_empty_rationale(self):
        tmp, semantic_dir = self.with_semantic_dir()
        self.addCleanup(tmp.cleanup)

        lesson_id = "lesson_empty_rationale"
        self.write_lessons(
            semantic_dir,
            [
                {
                    "id": lesson_id,
                    "claim": "A rationale is required.",
                    "conditions": [],
                    "evidence_ids": [],
                    "status": "accepted",
                    "accepted_at": "2026-05-01T00:00:00+00:00",
                    "reviewer": "host-agent",
                    "rationale": "current guidance",
                    "cluster_size": 1,
                    "canonical_salience": 5.0,
                    "confidence": 0.5,
                    "support_count": 0,
                    "contradiction_count": 0,
                    "supersedes": None,
                    "source_candidate": "cand_rationale",
                }
            ],
        )

        retract = load_module(RETRACT_LESSON, "retract_lesson_4")
        with self.assertRaises(ValueError):
            retract.retract_lesson(
                lesson_id=lesson_id,
                rationale="   ",
                reviewer="utkarsh",
                semantic_dir=str(semantic_dir),
            )


if __name__ == "__main__":
    unittest.main()

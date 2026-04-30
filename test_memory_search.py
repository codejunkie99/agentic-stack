import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MEMORY_SEARCH = ROOT / ".agent" / "memory" / "memory_search.py"


def load_memory_search():
    spec = importlib.util.spec_from_file_location("memory_search", MEMORY_SEARCH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MemorySearchTest(unittest.TestCase):
    def with_memory_root(self):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name) / ".agent" / "memory"
        (root / "semantic").mkdir(parents=True)
        (root / "episodic").mkdir()
        (root / ".features.json").write_text(
            json.dumps({"memory_search_fts": {"enabled": True}}),
            encoding="utf-8",
        )

        module = load_memory_search()
        module.MEMORY_DIR = root
        module.INDEX_DIR = root / ".index"
        module.INDEX_PATH = module.INDEX_DIR / "memory.db"
        module.FEATURES_PATH = root / ".features.json"
        return tmp, root, module

    def test_short_cjk_query_matches_inside_longer_phrase(self):
        tmp, root, memory_search = self.with_memory_root()
        self.addCleanup(tmp.cleanup)

        (root / "semantic" / "LESSONS.md").write_text(
            "- 中文优先 when the user writes in Chinese.\n",
            encoding="utf-8",
        )

        rows = memory_search.search_fts5("中文")

        self.assertEqual(rows[0][0], "semantic/LESSONS.md")
        self.assertIn("中文优先", rows[0][1])

    def test_mixed_english_cjk_query_uses_fts5(self):
        tmp, root, memory_search = self.with_memory_root()
        self.addCleanup(tmp.cleanup)

        (root / "semantic" / "LESSONS.md").write_text(
            "- OpenClaw 飞书 document retrieval needs tab-aware recovery.\n",
            encoding="utf-8",
        )

        rows = memory_search.search_fts5("OpenClaw 飞书")

        self.assertEqual(rows[0][0], "semantic/LESSONS.md")
        self.assertIn("OpenClaw", rows[0][1])
        self.assertIn("飞书", rows[0][1])

    def test_deleted_memory_file_is_removed_on_rebuild(self):
        tmp, root, memory_search = self.with_memory_root()
        self.addCleanup(tmp.cleanup)

        note = root / "semantic" / "LESSONS.md"
        note.write_text("- Keep stale anchors out of search results.\n", encoding="utf-8")
        self.assertTrue(memory_search.search_fts5("stale anchors"))

        note.unlink()
        rows = memory_search.search_fts5("stale anchors")

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()

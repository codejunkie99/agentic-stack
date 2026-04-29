import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
RECALL_PATH = ROOT / ".agent" / "tools" / "recall.py"


def load_recall():
    spec = importlib.util.spec_from_file_location("agentic_recall", RECALL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RecallStemmingTest(unittest.TestCase):
    def test_recall_matches_morphological_variants_for_timestamp_lesson(self):
        recall = load_recall()

        for query in ("fix the timestamp bug", "timestamp serialization"):
            result, meta = recall.recall(query, top_k=3)
            claims = [r["claim"] for r in result]

            self.assertGreater(meta["returned"], 0)
            self.assertIn(
                "Always serialize timestamps in UTC to avoid cross-region comparison bugs",
                claims,
            )


if __name__ == "__main__":
    unittest.main()

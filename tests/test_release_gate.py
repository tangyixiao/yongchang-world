import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
CONFIGS = {"none", "sphere", "charters", "wave", "all"}


class ReleaseMatrixTest(unittest.TestCase):
    def test_matrix_has_fifteen_runs(self):
        data = json.loads((ROOT / "artifacts/observe/matrix-summary.json").read_text("utf-8"))
        self.assertEqual(len(data["runs"]), 15)
        self.assertEqual(set(data["configs"]), CONFIGS)
        self.assertEqual(set(data["seeds"]), {11, 23, 47})

    def test_each_matrix_run_has_three_checkpoints(self):
        data = json.loads((ROOT / "artifacts/observe/matrix-summary.json").read_text("utf-8"))
        for run in data["runs"]:
            self.assertEqual(run["checkpoint_years"], [1846, 1866, 1900])


class ReleaseDocsTest(unittest.TestCase):
    def test_release_docs_name_exact_baseline(self):
        text = (ROOT / "docs/release/v0.1-acceptance.md").read_text("utf-8")
        self.assertIn("1.13.11 (Matcha)", text)
        self.assertIn("没有预定1900—1950政治结局", text)
        self.assertIn("NMG", text)


if __name__ == "__main__":
    unittest.main()

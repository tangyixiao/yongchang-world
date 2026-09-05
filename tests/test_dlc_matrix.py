import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
CONFIGS = {
    "none": set(),
    "sphere": {"ep1_content"},
    "charters": {"mp1_content"},
    "wave": {"ep2_content"},
    "all": {"ep1_content", "mp1_content", "ep2_content"},
}
KNOWN_FEATURES = set().union(*CONFIGS.values())


class DlcMatrixTest(unittest.TestCase):
    def setUp(self):
        self.matrix_path = ROOT / "data/balance/dlc_matrix.json"
        self.text = "\n".join(
            path.read_text("utf-8")
            for path in (ROOT / "yongchang_world").rglob("*")
            if path.is_file() and path.suffix.lower() in {".txt", ".yml", ".yaml"}
        )

    def test_every_config_has_base_path(self):
        matrix = json.loads(self.matrix_path.read_text("utf-8"))
        self.assertEqual(set(matrix), set(CONFIGS))
        for name in CONFIGS:
            self.assertTrue(matrix[name]["base_startup"], name)
            self.assertIn("features", matrix[name])

    def test_dlc_gated_ids_are_known(self):
        features = set(re.findall(r"has_dlc_feature\s*=\s*([A-Za-z0-9_]+)", self.text))
        self.assertTrue(features)
        self.assertTrue(features <= KNOWN_FEATURES, features - KNOWN_FEATURES)

    def test_each_feature_has_a_gated_path_and_fallback(self):
        for feature in KNOWN_FEATURES:
            self.assertRegex(self.text, rf"has_dlc_feature\s*=\s*{feature}")
        compat = ROOT / "yongchang_world/common/scripted_effects/ywc_dlc_effects.txt"
        compat_text = compat.read_text("utf-8")
        self.assertIn("ywc_dlc_base_path", compat_text)
        self.assertIn("# no DLC fallback", compat_text)


if __name__ == "__main__":
    unittest.main()

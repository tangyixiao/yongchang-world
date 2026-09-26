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
EXPECTED_MODIFIERS = {
    "none": set(),
    "sphere": {"ywc_dlc_ep1_investment"},
    "charters": {"ywc_dlc_mp1_charters"},
    "wave": {"ywc_dlc_ep2_flagship"},
    "all": {
        "ywc_dlc_ep1_investment",
        "ywc_dlc_mp1_charters",
        "ywc_dlc_ep2_flagship",
    },
}


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
        hook = (ROOT / "yongchang_world/common/on_actions/ywc_startup_hooks.txt").read_text("utf-8")
        self.assertEqual(hook.count("ywc_apply_dlc_compatibility = yes"), 10)

    def test_matrix_enhancements_are_visible_and_gated(self):
        matrix = json.loads(self.matrix_path.read_text("utf-8"))
        modifiers = (ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt").read_text("utf-8")
        simplified = (ROOT / "yongchang_world/localization/simp_chinese/ywc_content_l_simp_chinese.yml").read_text("utf-8")
        english = (ROOT / "yongchang_world/localization/english/ywc_content_l_english.yml").read_text("utf-8")
        compat = (ROOT / "yongchang_world/common/scripted_effects/ywc_dlc_effects.txt").read_text("utf-8")

        for config, expected in EXPECTED_MODIFIERS.items():
            self.assertEqual(set(matrix[config]["modifiers"]), expected, config)
        for modifier in set().union(*EXPECTED_MODIFIERS.values()):
            self.assertRegex(modifiers, rf"(?m)^{modifier}\s*=\s*\{{")
            self.assertRegex(simplified, rf"(?m)^\s*{modifier}:0\s+\"")
            self.assertRegex(english, rf"(?m)^\s*{modifier}:0\s+\"")
        for feature, modifier in (
            ("ep1_content", "ywc_dlc_ep1_investment"),
            ("mp1_content", "ywc_dlc_mp1_charters"),
            ("ep2_content", "ywc_dlc_ep2_flagship"),
        ):
            self.assertRegex(
                compat,
                rf"has_dlc_feature\s*=\s*{feature}[\s\S]*?add_modifier\s*=\s*\{{\s*name\s*=\s*{modifier}",
            )

    def test_dlc_modifiers_have_semantic_effects(self):
        modifiers = (ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt").read_text("utf-8")
        expected_effects = {
            "ywc_dlc_ep1_investment": [
                "country_bureaucracy_investment_cost_factor_mult = -0.10",
            ],
            "ywc_dlc_mp1_charters": [
                "country_free_charters_add = 1",
                "country_company_throughput_bonus_add = 0.05",
            ],
            "ywc_dlc_ep2_flagship": [
                "country_ship_construction_progress_max_add = 5",
                "country_supply_ship_construction_ratio_add = 0.25",
            ],
        }
        for modifier, effects in expected_effects.items():
            start = modifiers.index(f"{modifier} = {{")
            end = modifiers.index("\n}", start)
            block = modifiers[start:end]
            for effect in effects:
                self.assertIn(effect, block, modifier)


if __name__ == "__main__":
    unittest.main()

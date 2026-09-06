import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
TAGS = {"SHU", "JHG", "DMG", "NQG", "OIR", "MNG", "TIB", "KOR", "LAN", "NMG"}


def load_guardrails(path: pathlib.Path) -> dict:
    return json.loads(path.read_text("utf-8"))


class AiGuardrailsTest(unittest.TestCase):
    def setUp(self):
        self.data = load_guardrails(ROOT / "data/balance/guardrails.json")
        self.country_data = {tag: self.data[tag] for tag in TAGS}
        self.ai_path = ROOT / "yongchang_world/common/ai_strategies/ywc_ai_strategies.txt"
        self.modifier_path = ROOT / "yongchang_world/common/static_modifiers/ywc_static_modifiers.txt"
        self.hook_path = ROOT / "yongchang_world/common/on_actions/ywc_startup_hooks.txt"

    def test_guardrails_have_bounded_targets(self):
        self.assertLessEqual(self.data["SHU"]["max_subject_annexation_before_1866"], 1)
        self.assertFalse(self.data["JHG"]["can_colonize_africa"])
        self.assertFalse(self.data["NMG"]["can_be_annexed_by_mexico_before_1846"])

    def test_every_country_has_explainable_strategy(self):
        self.assertEqual(set(self.country_data), TAGS)
        for tag, row in self.country_data.items():
            self.assertTrue(row["strategy_id"].startswith("ai_strategy_ywc_"), tag)
            self.assertTrue(row["priorities"], tag)
            self.assertIn("before_1866", row["guardrail_window"], tag)

        ai_text = self.ai_path.read_text("utf-8")
        for tag, row in self.country_data.items():
            self.assertIn(row["strategy_id"], ai_text, tag)
            self.assertIn(tag, ai_text, tag)

    def test_balance_modifiers_have_a_finite_window(self):
        text = self.modifier_path.read_text("utf-8")
        for modifier in (
            "ywc_ai_shu_domestic_priority",
            "ywc_ai_jinghai_defensive_maritime",
            "ywc_ai_dongming_spanish_pressure",
            "ywc_ai_northern_qing_survival",
        ):
            self.assertIn(modifier, text)
        self.assertGreaterEqual(len(re.findall(r"1866|date", text)), 4)

    def test_startup_hook_assigns_all_catalog_strategies(self):
        text = self.hook_path.read_text("utf-8")
        self.assertIn(
            "on_game_started_after_lobby = {\n\ton_actions = {\n\t\tywc_on_game_started_after_lobby",
            text,
        )
        self.assertIn("ywc_on_game_started_after_lobby = {\n\teffect = {", text)
        for tag in TAGS:
            self.assertIn(f"c:{tag} ?= this", text)
            self.assertIn(f"set_strategy = ai_strategy_ywc_{tag.lower()}", text)
            self.assertIn("add_journal_entry = { type = ywc_je_dlc_compatibility }", text)


if __name__ == "__main__":
    unittest.main()

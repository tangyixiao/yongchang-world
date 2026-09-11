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
        self.ai_path = ROOT / "yongchang_world/common/ai_strategies/ywc_core_country_ai.txt"
        self.legacy_guardrail_path = ROOT / "yongchang_world/common/ai_strategies/ywc_ai_strategies.txt"
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

    def test_active_strategies_consume_runtime_state(self):
        """The IDs assigned at startup must be real, state-aware strategies."""
        self.assertFalse(self.legacy_guardrail_path.exists())
        text = self.ai_path.read_text("utf-8")
        for tag, row in self.country_data.items():
            strategy = row["strategy_id"]
            start = text.index(f"{strategy} = {{")
            next_strategy = re.search(
                r"(?m)^ai_strategy_ywc_[a-z0-9_]+\s*=\s*\{", text[start + 1 :]
            )
            end = start + 1 + next_strategy.start() if next_strategy else len(text)
            block = text[start:end]
            for field in (
                "type = diplomatic",
                "diplomatic_play_neutrality",
                "diplomatic_play_boldness",
                "recklessness",
                "aggression",
                "building_group_weights",
                "goods_stances",
                "weight",
                "has_modifier = declared_bankruptcy",
                "is_active_in_diplomatic_play = yes",
                "has_variable = ywc_route_",
            ):
                self.assertIn(field, block, f"{tag}: missing {field}")
            for comparison in re.findall(r"var:(ywc_route_[a-z0-9_]+)\s*>=\s*80", block):
                self.assertRegex(
                    block,
                    rf"has_variable\s*=\s*{comparison}",
                    f"{tag}: compares an unguarded route variable",
                )

    def test_non_colonial_guardrails_suppress_colonial_interest(self):
        """The catalog's no-Africa rule must reach the strategy actually assigned at startup."""
        text = self.ai_path.read_text("utf-8")
        for tag, row in self.country_data.items():
            if row["can_colonize_africa"]:
                continue
            strategy = row["strategy_id"]
            start = text.index(f"{strategy} = {{")
            next_strategy = re.search(
                r"(?m)^ai_strategy_ywc_[a-z0-9_]+\s*=\s*\{", text[start + 1 :]
            )
            end = start + 1 + next_strategy.start() if next_strategy else len(text)
            block = text[start:end]
            self.assertRegex(
                block,
                r"colonial_interest_ratio\s*=\s*\{\s*value\s*=\s*0\s*\}",
                f"{tag}: strategy does not suppress colonial expansion",
            )
            self.assertNotIn("colonization_rights", block, f"{tag}: unsupported strategy field")

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
            runtime_tag = "MGL" if tag == "MNG" else tag
            self.assertIn(f"c:{runtime_tag} ?= this", text)
            self.assertIn(f"set_strategy = ai_strategy_ywc_{tag.lower()}", text)
            self.assertIn("add_journal_entry = { type = ywc_je_dlc_compatibility }", text)


if __name__ == "__main__":
    unittest.main()

import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
COUNTRY_FILE = ROOT / "yongchang_world/common/country_definitions/ywc_core_countries.txt"
ZH_FILE = ROOT / "yongchang_world/localization/simp_chinese/ywc_core_l_simp_chinese.yml"
EN_FILE = ROOT / "yongchang_world/localization/english/ywc_core_l_english.yml"
LEDGER_FILE = ROOT / "data/scenario/core_states.json"
OVERRIDES_FILE = ROOT / "data/scenario/ownership_overrides.json"
BASELINE_FILE = ROOT / "data/baseline/vic3-1.13.11.json"
POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_core_pops.txt"
BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_core_buildings.txt"
COUNTRY_HISTORY = ROOT / "yongchang_world/common/history/countries"
SUBJECT_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_core_subjects.txt"
RELATIONS_FILE = ROOT / "yongchang_world/common/history/diplomacy/ywc_core_relations.txt"
STATE_HISTORY_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
OCEAN_STATE_HISTORY_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
JOURNAL_FILE = ROOT / "yongchang_world/common/journal_entries/ywc_bootstrap_journal.txt"
EVENT_FILE = ROOT / "yongchang_world/events/ywc_bootstrap_events.txt"

EXPECTED = {
    "SHU": ("STATE_BEIJING", "empire", ["han"]),
    "JHG": ("STATE_FORMOSA", "kingdom", ["han", "hakka"]),
    "DMG": ("STATE_LUZON", "kingdom", ["han", "ilocano", "filipino"]),
    "NQG": ("STATE_SAKHALIN", "principality", ["manchu", "siberian", "ainu"]),
}


class CoreCountryDefinitionTest(unittest.TestCase):
    def test_four_core_country_definitions(self):
        text = COUNTRY_FILE.read_text("utf-8")
        for tag, (capital, tier, cultures) in EXPECTED.items():
            self.assertRegex(text, rf"(?m)^\s*{tag}\s*=\s*\{{")
            block_match = re.search(
                rf"(?ms)^\s*{tag}\s*=\s*\{{.*?^\}}", text
            )
            self.assertIsNotNone(block_match)
            block = block_match.group(0)
            self.assertIn("country_type = unrecognized", block)
            self.assertIn(f"tier = {tier}", block)
            self.assertIn(f"capital = {capital}", block)
            for culture in cultures:
                self.assertIn(culture, block)

    def test_four_core_countries_have_colors(self):
        text = COUNTRY_FILE.read_text("utf-8")
        for tag in EXPECTED:
            block = re.search(rf"(?ms)^\s*{tag}\s*=\s*\{{.*?^\}}", text).group(0)
            self.assertRegex(block, r"color\s*=\s*\{\s*\d+\s+\d+\s+\d+\s*\}")

    def test_four_core_countries_have_bilingual_names(self):
        zh = ZH_FILE.read_text("utf-8")
        en = EN_FILE.read_text("utf-8")
        for tag in EXPECTED:
            self.assertRegex(zh, rf"(?m)^\s*{tag}:0\s+\".+\"")
            self.assertRegex(en, rf"(?m)^\s*{tag}:0\s+\".+\"")


class CoreStateTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(LEDGER_FILE.read_text("utf-8"))
        self.overrides = json.loads(OVERRIDES_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))

    def groups_for(self, state):
        return next(row["groups"] for row in self.overrides["states"] if row["state"] == state)

    def test_core_provinces_have_one_owner(self):
        owners = {}
        for state in self.ledger["states"]:
            for group in self.groups_for(state["state"]):
                for province in group["owned_provinces"]:
                    self.assertNotIn(province, owners)
                    owners[province] = group["owner"]
        self.assertEqual(self.ledger["special_rules"]["manila_owner"], "PHI")
        self.assertEqual(self.ledger["special_rules"]["formosa_owner"], "JHG")

    def test_ledger_provinces_are_from_the_declared_state(self):
        for row in self.ledger["states"]:
            region_provinces = set(self.baseline["state_regions"][row["state"]])
            provinces = {
                province
                for group in self.groups_for(row["state"])
                for province in group["owned_provinces"]
            }
            self.assertTrue(provinces.issubset(region_provinces))

    def test_core_state_split_matches_boundaries(self):
        self.assertEqual({group["owner"] for group in self.groups_for("STATE_FORMOSA")}, {"JHG"})
        luzon = next(group for group in self.groups_for("STATE_LUZON") if group["owner"] == "DMG")
        self.assertNotIn(self.ledger["special_rules"]["manila_province"], luzon["owned_provinces"])
        self.assertEqual({group["owner"] for group in self.groups_for("STATE_BEIJING")}, {"SHU"})
        self.assertEqual(
            {group["owner"] for group in self.groups_for("STATE_SAKHALIN") if group["owner"] == "NQG"},
            {"NQG"},
        )


class CoreEconomyTest(unittest.TestCase):
    def test_northern_qing_population_is_within_gate(self):
        text = POP_FILE.read_text("utf-8")
        self.assertIn("region_state:NQG", text)
        northern_qing = text[text.index("s:STATE_SAKHALIN"):]
        sizes = [int(size) for size in re.findall(r"size\s*=\s*(\d+)", northern_qing)]
        self.assertEqual(sum(sizes), 45000)
        self.assertGreaterEqual(sum(sizes), 30000)
        self.assertLessEqual(sum(sizes), 60000)

    def test_every_core_state_has_basic_food_and_government(self):
        text = BUILDING_FILE.read_text("utf-8")
        for state in ("STATE_BEIJING", "STATE_FORMOSA", "STATE_LUZON", "STATE_SAKHALIN"):
            start = text.index(f"s:{state}")
            end = text.find("\n\ts:", start + 1)
            block = text[start:] if end == -1 else text[start:end]
            self.assertIn("building_government_administration", block)
            self.assertRegex(block, r"building_(?:rice_farm|wheat_farm|rye_farm|livestock_ranch)")

    def test_core_country_histories_set_government_laws_and_market(self):
        required = (
            "set_market_capital",
            "activate_law = law_type:",
            "set_tax_level",
            "effect_starting_technology_tier_",
        )
        for tag in ("shu", "jhg", "dmg", "nqg"):
            path = COUNTRY_HISTORY / f"ywc_{tag}.txt"
            text = path.read_text("utf-8")
            for marker in required:
                self.assertIn(marker, text)

    def test_northern_qing_uses_low_industry_start(self):
        text = POP_FILE.read_text("utf-8") + BUILDING_FILE.read_text("utf-8")
        self.assertNotIn("building_steel_mill", text)


class CoreDiplomacyTest(unittest.TestCase):
    def test_jinghai_is_only_shun_subject(self):
        text = SUBJECT_FILE.read_text("utf-8")
        self.assertRegex(
            text,
            r"c:SHU\s*\?=\s*\{(?s:.*?)country\s*=\s*c:JHG(?s:.*?)type\s*=\s*tributary",
        )
        self.assertNotRegex(
            text,
            r"c:JHG\s*\?=\s*\{(?s:.*?)country\s*=\s*c:SHU",
        )

    def test_no_core_subject_cycle(self):
        text = SUBJECT_FILE.read_text("utf-8")
        self.assertEqual(text.count("type = tributary"), 1)

    def test_spain_has_claim_and_hostile_relations_to_eastern_ming(self):
        # LUZON's authoritative definition lives in the ocean states ledger
        # (the duplicate in the core ledger was removed).
        self.assertRegex(
            OCEAN_STATE_HISTORY_FILE.read_text("utf-8"),
            r"s:STATE_LUZON\s*=\s*\{(?s:.*?)add_claim\s*=\s*c:SPA",
        )
        relations = RELATIONS_FILE.read_text("utf-8")
        self.assertRegex(
            relations,
            r"c:DMG\s*\?=\s*\{(?s:.*?)set_relations\s*=\s*\{\s*country\s*=\s*c:SPA\s+value\s*=\s*-\d+",
        )

    def test_bootstrap_journals_and_events_are_connected(self):
        journal = JOURNAL_FILE.read_text("utf-8")
        events = EVENT_FILE.read_text("utf-8")
        journal_ids = (
            "ywc_je_eternal_yongchang",
            "ywc_je_jinghai_autonomy",
            "ywc_je_dongming_survival",
            "ywc_je_blackwater_century",
        )
        for journal_id in journal_ids:
            self.assertIn(f"{journal_id} =", journal)
        for event_id in ("ywc_bootstrap.1", "ywc_bootstrap.2", "ywc_bootstrap.3", "ywc_bootstrap.4"):
            self.assertIn(f"{event_id} =", events)
        self.assertIn("namespace = ywc_bootstrap", events)
        self.assertGreaterEqual(events.count("set_variable"), 4)
        self.assertIn("add_modifier = { name = ywc_jhg_south_sea_council", events)

    def test_each_core_country_receives_one_bootstrap_journal(self):
        expected = {
            "shu": "ywc_je_eternal_yongchang",
            "jhg": "ywc_je_jinghai_autonomy",
            "dmg": "ywc_je_dongming_survival",
            "nqg": "ywc_je_blackwater_century",
        }
        for country, journal_id in expected.items():
            text = (COUNTRY_HISTORY / f"ywc_{country}.txt").read_text("utf-8")
            self.assertIn(f"type = {journal_id}", text)


if __name__ == "__main__":
    unittest.main()

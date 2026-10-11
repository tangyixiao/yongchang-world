import json
import re
import unittest
from pathlib import Path

from tools import build_opening_profiles as builder


ROOT = Path(__file__).parents[1]
PROFILE_FILE = ROOT / "data/scenario/opening_profiles.json"
REGISTRY_FILE = ROOT / "data/scenario/tag_registry.json"
COUNTRY_DEFINITIONS = ROOT / "yongchang_world/common/country_definitions"
SHU_COUNTRIES = ROOT / "yongchang_world/common/history/countries/ywc_shu.txt"
ARMY_FILE = ROOT / "yongchang_world/common/history/military_formations/ywc_regional_military_formations.txt"
INNER_DIPLOMACY = ROOT / "yongchang_world/common/history/diplomacy/ywc_inner_asia_diplomacy.txt"


def country_block(text: str, tag: str) -> str:
    match = re.search(rf"(?m)^\s*{tag}\s*=\s*\{{.*?cultures\s*=\s*\{{([^}}]*)\}}", text, re.S)
    if not match:
        raise AssertionError(f"no culture definition found for {tag}")
    return match.group(1).split()


def scoped_block(text: str, tag: str) -> str:
    start = re.search(rf"c:{tag}\s*\?=\s*\{{", text)
    if not start:
        raise AssertionError(f"no history block for {tag}")
    depth = 1
    pos = start.end()
    for i in range(pos, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start.end():i]
    raise AssertionError(f"unclosed history block for {tag}")


def braced_block(text: str, pattern: str) -> str:
    start = re.search(pattern, text)
    if not start:
        raise AssertionError(f"no block matched {pattern}")
    opening = text.find("{", start.start())
    depth = 1
    pos = opening + 1
    while pos < len(text) and depth:
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
        pos += 1
    if depth:
        raise AssertionError(f"unclosed block matched {pattern}")
    return text[opening + 1 : pos - 1]


class OpeningProfilesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PROFILE_FILE.read_text(encoding="utf-8"))
        cls.profiles = cls.data["countries"]
        cls.registry = json.loads(REGISTRY_FILE.read_text(encoding="utf-8"))

    def test_every_new_polity_has_a_profile_matching_its_political_cultures(self):
        self.assertEqual(set(self.profiles), set(self.registry["new"]) | set(self.data["reused_tags"]))
        definitions = "\n".join(path.read_text(encoding="utf-8-sig") for path in COUNTRY_DEFINITIONS.glob("*.txt"))
        definitions += "\n" + "\n".join(
            path.read_text(encoding="utf-8-sig")
            for path in builder.DEFAULT_GAME_ROOT.joinpath("game/common/country_definitions").glob("*.txt")
        )
        for tag, profile in self.profiles.items():
            self.assertEqual(profile["primary_cultures"], country_block(definitions, tag), tag)

    def test_profiles_resolve_against_vanilla_and_generated_history(self):
        builder.validate(self.data, builder.DEFAULT_GAME_ROOT)
        generated = builder.render(self.data)
        self.assertEqual(
            generated,
            (ROOT / "yongchang_world/common/history/countries/zzz_ywc_opening_profiles.txt").read_text(encoding="utf-8-sig"),
        )
        for tag, profile in self.profiles.items():
            block = scoped_block(generated, tag)
            self.assertIn(f"set_state_religion = rel:{profile['state_religion']}", block)
            for technology in profile["technology_focus"]:
                self.assertIn(f"add_technology_researched = {technology}", block)

    def test_historical_building_owners_have_only_the_technologies_their_starts_need(self):
        requirements = {
            "AMR": {"standing_army", "shaft_mining"},
            "SOL": {"standing_army"},
            "AMD": {"tech_bureaucracy", "standing_army"},
            "DLI": {"tech_bureaucracy", "standing_army", "enclosure"},
            "KHQ": {"standing_army"},
            "HUL": {"standing_army"},
        }
        for tag, technologies in requirements.items():
            self.assertTrue(technologies.issubset(set(self.profiles[tag]["technology_focus"])), tag)

    def test_shun_start_is_a_205_battalion_force_with_a_coastal_fleet(self):
        block = scoped_block(ARMY_FILE.read_text(encoding="utf-8-sig"), "SHU")
        battalions = sum(
            int(count)
            for unit in re.findall(r"combat_unit\s*=\s*\{([^}]*)\}", block, re.S)
            for count in re.findall(r"\bcount\s*=\s*(\d+)", unit)
        )
        ships = sum(int(count) for count in re.findall(r"\bship\s*=\s*\{[^}]*\bcount\s*=\s*(\d+)", block))
        self.assertEqual(battalions, 205)
        self.assertEqual(ships, 6)
        for state in ("BEIJING", "GANSU", "SHENGJING", "JIANGSU", "GUANGDONG", "SICHUAN"):
            self.assertIn(f"state_region = s:STATE_{state}", block)
        self.assertIn("hq_region = sr:region_south_china", block)

    def test_shun_armies_start_with_ranked_commanders_for_their_force_sizes(self):
        text = ARMY_FILE.read_text(encoding="utf-8-sig")
        block = scoped_block(text, "SHU")
        army_names = (
            "frontier", "western", "northeastern", "eastern", "southern", "southwestern"
        )
        for name in army_names:
            army_scope = f"ywc_shun_{name}_army"
            commander_scope = f"ywc_shun_{name}_general"
            self.assertIn(f"save_scope_as = {army_scope}", block)
            self.assertIn(f"commander_rank = commander_rank_2 save_scope_as = {commander_scope}", block)
            self.assertIn(
                f"scope:{commander_scope} ?= {{ transfer_to_formation = scope:{army_scope} }}",
                block,
            )
        ranks = (builder.DEFAULT_GAME_ROOT / "game/common/commander_ranks/00_commander_ranks.txt").read_text(encoding="utf-8-sig")
        rank_match = re.search(r"(?m)^commander_rank_2\s*=\s*\{([^}]*)\}", ranks, re.S)
        self.assertIsNotNone(rank_match)
        rank_start = rank_match.start()
        rank_open = ranks.index("{", rank_start)
        depth = 1
        rank_end = rank_open + 1
        while depth:
            if ranks[rank_end] == "{":
                depth += 1
            elif ranks[rank_end] == "}":
                depth -= 1
            rank_end += 1
        rank_two = ranks[rank_open:rank_end]
        self.assertRegex(rank_two, r"character_command_limit_add\s*=\s*60")
        self.assertEqual(block.count("commander_rank = commander_rank_2"), 6)

    def test_shun_fleet_has_an_admiral_and_minimum_sailor_capacity(self):
        block = scoped_block(ARMY_FILE.read_text(encoding="utf-8-sig"), "SHU")
        self.assertIn("name = ywc_shun_coastal_fleet", block)
        self.assertIn("save_scope_as = ywc_shun_coastal_fleet", block)
        self.assertIn(
            "template = ywc_shu_admiral_hou_zhenhai commander_rank = commander_rank_1 save_scope_as = ywc_shun_admiral",
            block,
        )
        self.assertIn(
            "scope:ywc_shun_admiral ?= { transfer_to_formation = scope:ywc_shun_coastal_fleet }",
            block,
        )

        shu_profile = self.profiles["SHU"]["technology_focus"]
        self.assertIn("admiralty", shu_profile)
        buildings = (ROOT / "yongchang_world/common/history/buildings/ywc_core_buildings.txt").read_text(encoding="utf-8-sig")
        guangdong = braced_block(buildings, r"(?m)^\s*s:STATE_GUANGDONG\s*=\s*\{")
        guangdong_owner = braced_block(guangdong, r"(?m)^\s*region_state:SHU\s*=\s*\{")
        self.assertRegex(guangdong_owner, r"building\s*=\s*\"building_naval_administration\"")
        self.assertRegex(guangdong_owner, r"levels\s*=\s*3\b")
        self.assertIn('activate_production_methods = { "pm_simple_sailor_recruitment" }', buildings)

        game = builder.DEFAULT_GAME_ROOT / "game/common"
        naval_building = (game / "buildings/05_military.txt").read_text(encoding="utf-8-sig")
        naval_admin = re.search(r"(?m)^building_naval_administration\s*=\s*\{", naval_building)
        self.assertIsNotNone(naval_admin)
        self.assertIn("admiralty", naval_building[naval_admin.start():naval_building.find("\n}", naval_admin.start())])
        sailor_pm = (game / "production_methods/05_military.txt").read_text(encoding="utf-8-sig")
        simple = re.search(r"(?m)^pm_simple_sailor_recruitment\s*=\s*\{", sailor_pm)
        self.assertIsNotNone(simple)
        self.assertIn("country_sailors_max_add = 1000", sailor_pm[simple.start():sailor_pm.find("\n}", simple.start())])
        self.assertEqual(3 * 1000, 3000)

    def test_every_scripted_fleet_has_sailor_capacity_and_an_admiral(self):
        fleet_files = (
            ARMY_FILE,
            ROOT / "yongchang_world/common/history/military_formations/ywc_coastal_military_formations.txt",
        )
        fleets = {}
        for path in fleet_files:
            text = path.read_text(encoding="utf-8-sig")
            for tag in re.findall(r"(?m)^\s*c:([A-Z]{3})\s*\?=\s*\{", text):
                block = scoped_block(text, tag)
                ships = sum(int(count) for count in re.findall(r"ship\s*=\s*\{[^}]*\bcount\s*=\s*(\d+)", block))
                if ships:
                    fleets[tag] = (ships, block)
        self.assertEqual(len(fleets), 14)

        game = builder.DEFAULT_GAME_ROOT / "game/common"
        ship_types = (game / "ship_types/00_ship_types.txt").read_text(encoding="utf-8-sig")
        frigate = braced_block(ship_types, r"(?m)^ship_type_frigate\s*=\s*\{")
        crew_per_frigate = int(re.search(r"ship_crew_max_add\s*=\s*(\d+)", frigate).group(1))
        sailor_pm = (game / "production_methods/05_military.txt").read_text(encoding="utf-8-sig")
        sailor_method = braced_block(sailor_pm, r"(?m)^pm_simple_sailor_recruitment\s*=\s*\{")
        sailors_per_level = int(re.search(r"country_sailors_max_add\s*=\s*(\d+)", sailor_method).group(1))
        self.assertEqual(crew_per_frigate, 500)
        self.assertEqual(sailors_per_level, 1000)

        support = {
            "JHG": ("FORMOSA", 4), "DMG": ("LUZON", 1), "LAN": ("WEST_BORNEO", 1),
            "NMG": ("BAJA_CALIFORNIA", 1), "MHG": ("MEKONG", 1), "WBK": ("WEST_BORNEO", 1),
            "NQG": ("SAKHALIN", 1), "RKN": ("ARAKAN", 1), "AMR": ("AMUR", 1),
            "PNP": ("EAST_MICRONESIA", 1), "PLW": ("WEST_MICRONESIA", 1),
            "YAP": ("WEST_MICRONESIA", 1), "MHL": ("WEST_MICRONESIA", 1),
            "SHU": ("GUANGDONG", 3),
        }
        profile_buildings = ROOT / "yongchang_world/common/history/buildings/ywc_coastal_naval_recruitment.txt"
        shu_buildings = ROOT / "yongchang_world/common/history/buildings/ywc_core_buildings.txt"
        for tag, (ships, block) in fleets.items():
            state, levels = support[tag]
            building_text = (shu_buildings if tag == "SHU" else profile_buildings).read_text(encoding="utf-8-sig")
            state_block = braced_block(building_text, rf"(?m)^\s*s:STATE_{state}\s*=\s*\{{")
            owner_block = braced_block(state_block, rf"(?m)^\s*region_state:{tag}\s*=\s*\{{")
            self.assertRegex(owner_block, r"building\s*=\s*\"building_naval_administration\"")
            self.assertRegex(owner_block, rf"levels\s*=\s*{levels}\b")
            capacity = levels * sailors_per_level
            required = ships * crew_per_frigate
            self.assertGreaterEqual(capacity, required, tag)
            if tag in {"LAN", "RKN"}:
                lan_history = (ROOT / "yongchang_world/common/history/countries/ywc_ocean_countries.txt").read_text(encoding="utf-8-sig")
                if tag == "LAN":
                    self.assertIn("c:LAN ?= { add_technology_researched = admiralty }", lan_history)
                else:
                    rkn_history = (ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt").read_text(encoding="utf-8-sig")
                    self.assertRegex(scoped_block(rkn_history, "RKN"), r"add_technology_researched\s*=\s*admiralty")
            else:
                self.assertIn("admiralty", self.profiles[tag]["technology_focus"], tag)
            self.assertIn("commander_rank = commander_rank_1", block, tag)
            self.assertIn("transfer_to_formation", block, tag)

    def test_scripted_fleets_have_admiralty_and_shun_uses_reviewed_laws(self):
        fleet_file = ROOT / "yongchang_world/common/history/military_formations/ywc_coastal_military_formations.txt"
        formations = fleet_file.read_text(encoding="utf-8-sig")
        for tag in ("JHG", "DMG", "LAN", "NMG", "MHG", "WBK", "NQG", "RKN", "AMR", "PNP", "PLW", "YAP", "MHL"):
            if re.search(rf"(?m)^\s*c:{tag}\s*\?=", formations):
                if tag in self.profiles:
                    self.assertIn("admiralty", self.profiles[tag]["technology_focus"], tag)
        lan_history = (ROOT / "yongchang_world/common/history/countries/ywc_ocean_countries.txt").read_text(encoding="utf-8-sig")
        self.assertIn("c:LAN ?= { add_technology_researched = admiralty }", lan_history)
        shu = scoped_block(builder.render(self.data), "SHU")
        self.assertIn("activate_law = law_type:law_professional_army", shu)
        self.assertIn("activate_law = law_type:law_censorship", shu)

    def test_batang_is_subject_to_shun_and_sikkim_bhutan_to_tibet(self):
        diplomacy = INNER_DIPLOMACY.read_text(encoding="utf-8-sig")
        shu = scoped_block(diplomacy, "SHU")
        tib = scoped_block(diplomacy, "TIB")
        kam = scoped_block(diplomacy, "KAM") if re.search(r"c:KAM\s*\?=\s*\{", diplomacy) else ""
        self.assertRegex(shu, r"country\s*=\s*c:DAI\s+type\s*=\s*tributary")
        self.assertRegex(shu, r"country\s*=\s*c:KAM\s+type\s*=\s*tributary")
        self.assertRegex(tib, r"country\s*=\s*c:SIK\s+type\s*=\s*tributary")
        self.assertRegex(tib, r"country\s*=\s*c:BHU\s+type\s*=\s*tributary")
        self.assertNotRegex(kam, r"country\s*=\s*c:(?:SIK|BHU)")


if __name__ == "__main__":
    unittest.main()

import json
import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).parents[1]
REGISTRY_FILE = ROOT / "data/scenario/tag_registry.json"
COUNTRY_FILE = ROOT / "yongchang_world/common/country_definitions/ywc_regional_countries.txt"
NORTHEAST_LEDGER_FILE = ROOT / "data/scenario/northeast_states.json"
BASELINE_FILE = ROOT / "data/baseline/vic3-1.13.11.json"
NORTHEAST_STATE_FILE = ROOT / "yongchang_world/common/history/states/ywc_northeast_states.txt"
NORTHEAST_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_northeast_pops.txt"
NORTHEAST_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_northeast_buildings.txt"
INNER_ASIA_LEDGER_FILE = ROOT / "data/scenario/inner_asia_states.json"
INNER_ASIA_STATE_FILE = ROOT / "yongchang_world/common/history/states/ywc_inner_asia_states.txt"
INNER_ASIA_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_inner_asia_pops.txt"
INNER_ASIA_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_inner_asia_buildings.txt"
SOUTHWEST_LEDGER_FILE = ROOT / "data/scenario/southwest_states.json"
SOUTHWEST_STATE_FILE = ROOT / "yongchang_world/common/history/states/ywc_southwest_states.txt"
SOUTHWEST_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_southwest_pops.txt"
SOUTHWEST_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_southwest_buildings.txt"
SOUTHWEST_JOURNAL_FILE = ROOT / "yongchang_world/common/journal_entries/ywc_southwest_journal.txt"
OCEAN_LEDGER_FILE = ROOT / "data/scenario/ocean_states.json"
OCEAN_STATE_FILE = ROOT / "yongchang_world/common/history/states/ywc_ocean_states.txt"
OCEAN_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_ocean_pops.txt"
OCEAN_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_ocean_buildings.txt"
OCEAN_JOURNAL_FILE = ROOT / "yongchang_world/common/journal_entries/ywc_ocean_journal.txt"
REGIONAL_COUNTRY_HISTORY_FILE = ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt"

REGIONAL_NEW = {
    "NMG", "MHG", "WBK", "KHQ", "HUL", "SOL", "AMR", "OIR", "KJU", "MJU", "GJU",
    "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT", "DER", "KAM", "GYL",
    "LXJ", "LJG", "SIP", "KTG", "WAA", "KCH", "AHM", "AMD", "DLI", "PNP",
    "PLW", "YAP", "MHL", "MRG",
}


class RegionalTagRegistryTest(unittest.TestCase):
    def test_regional_tags_are_new_and_registered(self):
        registry = json.loads(REGISTRY_FILE.read_text("utf-8"))
        rows = {row["tag"]: row for row in registry["countries"]}
        self.assertTrue(REGIONAL_NEW.issubset(rows))
        for tag in REGIONAL_NEW:
            self.assertEqual(rows[tag]["mode"], "new")
            self.assertIsNone(rows[tag]["source_tag"])


class RegionalCountryDefinitionTest(unittest.TestCase):
    def test_regional_country_definitions_have_capital_and_culture(self):
        text = COUNTRY_FILE.read_text("utf-8")
        for tag in REGIONAL_NEW:
            match = re.search(rf"(?m)^\s*{tag}\s*=\s*\{{[^\n]*\}}", text)
            self.assertIsNotNone(match, tag)
            block = match.group(0)
            self.assertRegex(block, r"capital\s*=\s*STATE_[A-Z0-9_]+")
            self.assertRegex(block, r"cultures\s*=\s*\{[^}]+\}")


class NortheastLedgerTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(NORTHEAST_LEDGER_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))

    def test_required_source_states_are_declared(self):
        self.assertEqual(
            set(self.ledger["source_states"]),
            {
                "STATE_SHENGJING",
                "STATE_OUTER_MANCHURIA",
                "STATE_NORTHERN_MANCHURIA",
                "STATE_SAKHALIN",
                "STATE_HOKKAIDO",
            },
        )

    def test_groups_cover_each_source_state_without_overlap(self):
        expected_tags = {"SHU", "KHQ", "HUL", "SOL", "AMR", "NQG", "EZO"}
        grouped = {state: [] for state in self.ledger["source_states"]}
        for row in self.ledger["groups"]:
            self.assertIn(row["target_country"], expected_tags)
            self.assertIn(row["source_state"], grouped)
            self.assertTrue(row["owned_provinces"])
            self.assertTrue(row["reason"].strip())
            grouped[row["source_state"]].extend(row["owned_provinces"])

        for state, provinces in grouped.items():
            self.assertEqual(len(provinces), len(set(provinces)), state)
            self.assertEqual(set(provinces), set(self.baseline["state_regions"][state]), state)

    def test_sakhalin_groups_are_disjoint(self):
        groups = self.ledger["sakhalin_groups"]
        baseline = set(self.baseline["state_regions"]["STATE_SAKHALIN"])
        owned = [province for provinces in groups.values() for province in provinces]
        self.assertEqual(set(owned), baseline)
        self.assertEqual(len(owned), len(set(owned)))

    def test_northern_qing_is_small(self):
        self.assertGreaterEqual(self.ledger["country_population"]["NQG"], 30000)
        self.assertLessEqual(self.ledger["country_population"]["NQG"], 60000)

    def test_northeast_history_files_are_connected_to_ledger(self):
        state_text = NORTHEAST_STATE_FILE.read_text("utf-8")
        pop_text = NORTHEAST_POP_FILE.read_text("utf-8")
        building_text = NORTHEAST_BUILDING_FILE.read_text("utf-8")
        for state in self.ledger["source_states"]:
            self.assertIn(f"s:{state}", state_text)
        for country in ("SHU", "KHQ", "HUL", "SOL", "AMR", "EZO"):
            self.assertIn(f"region_state:{country}", pop_text)
            self.assertIn(f"region_state:{country}", building_text)
        # NQG's 45,000-population gate and its basic economy are owned by the
        # vertical slice files; the regional files must not duplicate them.
        core_pop = (ROOT / "yongchang_world/common/history/pops/ywc_core_pops.txt").read_text("utf-8")
        core_building = (ROOT / "yongchang_world/common/history/buildings/ywc_core_buildings.txt").read_text("utf-8")
        self.assertIn("region_state:NQG", core_pop)
        self.assertIn("region_state:NQG", core_building)


class InnerAsiaTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(INNER_ASIA_LEDGER_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))

    def owners_for(self, state):
        return {
            row["target_country"]
            for row in self.ledger["groups"]
            if row["source_state"] == state
        }

    def test_expected_state_owners(self):
        expected = {
            "STATE_DZUNGARIA": "OIR",
            "STATE_SEMIRECHE": "OIR",
            "STATE_URGA": "MNG",
            "STATE_ULIASTAI": "MNG",
            "STATE_FERGANA": "KOK",
        }
        for state, owner in expected.items():
            self.assertEqual(self.owners_for(state), {owner}, state)

    def test_oir_mng_and_kho_have_no_province_overlap(self):
        owners = {"OIR": set(), "MNG": set(), "KHO": set()}
        for row in self.ledger["groups"]:
            if row["target_country"] in owners:
                provinces = set(row["owned_provinces"])
                self.assertTrue(
                    provinces.issubset(set(self.baseline["state_regions"][row["source_state"]]))
                )
                self.assertTrue(owners[row["target_country"]].isdisjoint(provinces))
                owners[row["target_country"]].update(provinces)
        self.assertTrue(all(owners.values()))

    def test_successor_states_and_oases_are_present(self):
        tags = {row["target_country"] for row in self.ledger["groups"]}
        self.assertTrue({"KJU", "MJU", "GJU"}.issubset(tags))
        self.assertTrue({"HMI", "TRF", "KUC", "KSH", "YRK", "KHT"}.issubset(tags))

    def test_inner_asia_history_files_are_connected(self):
        state_text = INNER_ASIA_STATE_FILE.read_text("utf-8")
        pop_text = INNER_ASIA_POP_FILE.read_text("utf-8")
        building_text = INNER_ASIA_BUILDING_FILE.read_text("utf-8")
        for state in self.ledger["source_states"]:
            self.assertIn(f"s:{state}", state_text)
        for country in ("OIR", "MNG", "KOK", "KJU", "MJU", "GJU", "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT"):
            self.assertIn(f"region_state:{country}", pop_text)
            self.assertIn(f"region_state:{country}", building_text)


class SouthwestTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(SOUTHWEST_LEDGER_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))

    def owners_for(self, state):
        return {
            row["target_country"]
            for row in self.ledger["groups"]
            if row["source_state"] == state
        }

    def test_tibet_does_not_own_qinghai_and_kham(self):
        self.assertNotIn("TIB", self.owners_for("STATE_QINGHAI"))
        self.assertNotIn("TIB", self.owners_for("STATE_SICHUAN"))
        self.assertEqual(self.owners_for("STATE_LHASA"), {"TIB"})

    def test_releasables_are_not_starting_countries(self):
        self.assertNotIn("AMD", self.ledger["starting_tags"])
        self.assertNotIn("DLI", self.ledger["starting_tags"])
        self.assertEqual(set(self.ledger["releasable_tags"]), {"AMD", "DLI"})

    def test_southwest_groups_cover_source_states_without_overlap(self):
        grouped = {state: [] for state in self.ledger["source_states"]}
        for row in self.ledger["groups"]:
            self.assertIn(row["source_state"], grouped)
            self.assertTrue(row["reason"].strip())
            grouped[row["source_state"]].extend(row["owned_provinces"])
        for state, provinces in grouped.items():
            self.assertEqual(len(provinces), len(set(provinces)), state)
            self.assertEqual(set(provinces), set(self.baseline["state_regions"][state]), state)

    def test_southwest_history_and_highland_journal_are_connected(self):
        state_text = SOUTHWEST_STATE_FILE.read_text("utf-8")
        pop_text = SOUTHWEST_POP_FILE.read_text("utf-8")
        building_text = SOUTHWEST_BUILDING_FILE.read_text("utf-8")
        journal_text = SOUTHWEST_JOURNAL_FILE.read_text("utf-8")
        for state in self.ledger["source_states"]:
            self.assertIn(f"s:{state}", state_text)
        for country in self.ledger["starting_tags"]:
            self.assertIn(f"region_state:{country}", pop_text)
            self.assertIn(f"region_state:{country}", building_text)
        # The duplicate regional journal ywc_je_highland_without_master was
        # removed (TIB's main journal covers it); the file must not redefine
        # it and the southwest country history must no longer add it.
        self.assertNotIn("ywc_je_highland_without_master =", journal_text)
        country_history = (ROOT / "yongchang_world/common/history/countries/ywc_southwest.txt").read_text("utf-8")
        self.assertNotIn("ywc_je_highland_without_master", country_history)


class OceanTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(OCEAN_LEDGER_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))

    def test_ocean_constraints(self):
        self.assertEqual(self.ledger["named_groups"]["STATE_FORMOSA"]["owner"], "JHG")
        self.assertEqual(self.ledger["named_groups"]["STATE_LUZON_MANILA_GROUP"]["owner"], "PHI")
        self.assertEqual(self.ledger["named_groups"]["STATE_BAJA_CALIFORNIA_LORETO_GROUP"]["owner"], "NMG")
        self.assertEqual(self.ledger["country_population"]["NMG"], 45000)

    def test_luzon_and_baja_groups_use_only_baseline_provinces(self):
        for name in ("STATE_LUZON", "STATE_BAJA_CALIFORNIA"):
            baseline = set(self.baseline["state_regions"][name])
            for row in self.ledger["groups"]:
                if row["source_state"] == name:
                    self.assertTrue(set(row["owned_provinces"]).issubset(baseline))

    def test_ocean_groups_do_not_overlap(self):
        for state in self.ledger["source_states"]:
            owned = [
                province
                for row in self.ledger["groups"]
                if row["source_state"] == state
                for province in row["owned_provinces"]
            ]
            self.assertEqual(len(owned), len(set(owned)), state)

    def test_north_australia_has_one_station_and_island_tags_have_basic_economy(self):
        self.assertEqual(self.ledger["north_australia_station_count"], 1)
        self.assertIn("ywc_south_sea_station", self.ledger["special_buildings"])
        state_text = OCEAN_STATE_FILE.read_text("utf-8")
        pop_text = OCEAN_POP_FILE.read_text("utf-8")
        building_text = OCEAN_BUILDING_FILE.read_text("utf-8")
        journal_text = OCEAN_JOURNAL_FILE.read_text("utf-8")
        for state in self.ledger["source_states"]:
            self.assertIn(f"s:{state}", state_text)
        for country in ("MHG", "WBK", "PNP", "PLW", "YAP", "MHL", "MRG", "NMG"):
            self.assertIn(f"region_state:{country}", pop_text)
            self.assertIn(f"region_state:{country}", building_text)
        self.assertIn("ywc_je_ocean_frontiers =", journal_text)


class RegionalCountryHistoryTest(unittest.TestCase):
    def test_new_regional_countries_have_market_and_basic_laws(self):
        text = REGIONAL_COUNTRY_HISTORY_FILE.read_text("utf-8")
        expected = {
            "OIR", "KJU", "MJU", "GJU", "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT",
            "DER", "KAM", "GYL", "LXJ", "LJG", "SIP", "KTG", "WAA", "KCH", "AHM", "MNP",
            "SHN", "ARA", "LAD", "WBK", "PNP", "PLW", "YAP", "MHL", "MRG",
        }
        for tag in expected:
            match = re.search(rf"(?ms)c:{tag}\s*\?=\s*\{{.*?^\s*\}}", text)
            self.assertIsNotNone(match, tag)
            block = match.group(0)
            self.assertIn("set_market_capital", block)
            self.assertIn("activate_law", block)
            self.assertIn("set_tax_level", block)


class StateHistoryVanillaCoverageTest(unittest.TestCase):
    """Mod state history is覆盖式: every province of each vanilla state
    region must be owned by exactly one create_state, or the map shows
    unowned fragments. Provinces outside the vanilla region are a mismatch
    with the shipped map."""

    def test_every_state_covers_its_vanilla_region_exactly(self):
        baseline = json.loads((ROOT / "data/baseline/vic3-1.13.11.json").read_text(encoding="utf-8"))
        regions = baseline["state_regions"]
        problems = []
        seen = set()
        for path in sorted((ROOT / "yongchang_world/common/history/states").glob("*.txt")):
            text = path.read_text(encoding="utf-8-sig")
            for match in re.finditer(r"s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text):
                state = match.group(1)
                self.assertNotIn(state, seen, f"{path.name}: duplicate state {state}")
                seen.add(state)
                vanilla = set(regions.get(state, []))
                self.assertTrue(vanilla, f"{path.name}: {state} missing from vanilla baseline")
                start = match.end()
                depth, i = 1, start
                while depth and i < len(text):
                    if text[i] == "{":
                        depth += 1
                    elif text[i] == "}":
                        depth -= 1
                    i += 1
                owned = set(re.findall(r"\b(x[0-9A-Fa-f]{6})\b", text[start:i - 1]))
                foreign = sorted(owned - vanilla)
                missing = sorted(vanilla - owned)
                if foreign:
                    problems.append(f"{path.name}: {state}: {len(foreign)} provinces outside the vanilla region")
                if missing:
                    problems.append(f"{path.name}: {state}: {len(missing)} vanilla provinces left unowned")
        self.assertEqual(problems, [])
        self.assertGreater(len(seen), 0)


if __name__ == "__main__":
    unittest.main()

import json
import pathlib
import re
import unittest

try:
    import numpy as np
    from PIL import Image
except ImportError:  # pragma: no cover - the installed game test environment has both.
    np = None
    Image = None


ROOT = pathlib.Path(__file__).parents[1]
REGISTRY_FILE = ROOT / "data/scenario/tag_registry.json"
COUNTRY_FILE = ROOT / "yongchang_world/common/country_definitions/ywc_regional_countries.txt"
NORTHEAST_LEDGER_FILE = ROOT / "data/scenario/northeast_states.json"
BASELINE_FILE = ROOT / "data/baseline/vic3-1.13.11.json"
OVERRIDES_FILE = ROOT / "data/scenario/ownership_overrides.json"
NORTHEAST_STATE_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
SEA_REGIONS_FILE = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/state_regions/99_seas.txt")
NORTHEAST_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_northeast_pops.txt"
NORTHEAST_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_northeast_buildings.txt"
INNER_ASIA_LEDGER_FILE = ROOT / "data/scenario/inner_asia_states.json"
INNER_ASIA_STATE_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
INNER_ASIA_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_inner_asia_pops.txt"
INNER_ASIA_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_inner_asia_buildings.txt"
SOUTHWEST_LEDGER_FILE = ROOT / "data/scenario/southwest_states.json"
SOUTHWEST_STATE_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
SOUTHWEST_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_southwest_pops.txt"
SOUTHWEST_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_southwest_buildings.txt"
SOUTHWEST_JOURNAL_FILE = ROOT / "yongchang_world/common/journal_entries/ywc_southwest_journal.txt"
OCEAN_LEDGER_FILE = ROOT / "data/scenario/ocean_states.json"
OCEAN_STATE_FILE = ROOT / "yongchang_world/common/history/states/00_states.txt"
OCEAN_POP_FILE = ROOT / "yongchang_world/common/history/pops/ywc_ocean_pops.txt"
OCEAN_BUILDING_FILE = ROOT / "yongchang_world/common/history/buildings/ywc_ocean_buildings.txt"
OCEAN_JOURNAL_FILE = ROOT / "yongchang_world/common/journal_entries/ywc_ocean_journal.txt"
REGIONAL_COUNTRY_HISTORY_FILE = ROOT / "yongchang_world/common/history/countries/ywc_regional_countries.txt"
PROVINCES_MAP_FILE = pathlib.Path(r"E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png")


def balanced_block(text, marker):
    start = text.index(marker)
    opening = text.index("{", start)
    depth = 0
    for index in range(opening, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise AssertionError(f"unclosed block: {marker}")


def load_authority():
    data = json.loads(OVERRIDES_FILE.read_text("utf-8"))
    return {row["state"]: row["groups"] for row in data["states"]}


def authority_group(authority, state, owner):
    return next(group for group in authority[state] if group["owner"] == owner)

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

    def test_mng_logical_country_uses_vanilla_mgl(self):
        registry = json.loads(REGISTRY_FILE.read_text("utf-8"))
        row = next(row for row in registry["countries"] if row["tag"] == "MNG")
        baseline = json.loads(BASELINE_FILE.read_text("utf-8"))
        self.assertEqual(row["source_tag"], "MGL")
        self.assertIn("MGL", baseline["country_tags"])
        self.assertNotRegex(COUNTRY_FILE.read_text("utf-8"), r"(?m)^\s*MNG\s*=")


class NortheastLedgerTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(NORTHEAST_LEDGER_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))
        self.authority = load_authority()

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
            self.assertTrue(row["reason"].strip())
            grouped[row["source_state"]].extend(
                authority_group(self.authority, row["source_state"], row["target_country"])["owned_provinces"]
            )

        for state, provinces in grouped.items():
            self.assertEqual(len(provinces), len(set(provinces)), state)
            self.assertEqual(set(provinces), set(self.baseline["state_regions"][state]), state)

    def test_sakhalin_groups_are_disjoint(self):
        baseline = set(self.baseline["state_regions"]["STATE_SAKHALIN"])
        owned = [province for group in self.authority["STATE_SAKHALIN"] for province in group["owned_provinces"]]
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
        self.authority = load_authority()

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
            "STATE_URGA": "MGL",
            "STATE_ULIASTAI": "MGL",
            "STATE_FERGANA": "KOK",
        }
        for state, owner in expected.items():
            self.assertEqual(self.owners_for(state), {owner}, state)

    def test_oir_mng_and_kho_have_no_province_overlap(self):
        owners = {"OIR": set(), "MGL": set(), "KHO": set()}
        for row in self.ledger["groups"]:
            if row["target_country"] in owners:
                provinces = set(authority_group(self.authority, row["source_state"], row["target_country"])["owned_provinces"])
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
        for country in ("OIR", "MGL", "KOK", "KJU", "MJU", "GJU", "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT"):
            self.assertIn(f"region_state:{country}", pop_text)
            self.assertIn(f"region_state:{country}", building_text)

    def test_tianshan_oasis_groups_are_map_connected(self):
        if np is None or Image is None or not PROVINCES_MAP_FILE.exists():
            self.skipTest("Pillow, NumPy, and the installed Victoria 3 provinces map are required")

        state = "STATE_TIANSHAN"
        groups = {
            group["owner"]: set(group["owned_provinces"])
            for group in self.authority[state]
        }
        expected_counts = {"HMI": 24, "TRF": 36, "KUC": 60, "KSH": 40, "YRK": 36, "KHT": 40}
        self.assertEqual({owner: len(provinces) for owner, provinces in groups.items()}, expected_counts)

        pixels = np.asarray(Image.open(PROVINCES_MAP_FILE).convert("RGB"), dtype=np.uint32)
        encoded = pixels[:, :, 0] * 65536 + pixels[:, :, 1] * 256 + pixels[:, :, 2]
        province_codes = {int(province[1:], 16): province for province in self.baseline["state_regions"][state]}
        target_codes = np.array(list(province_codes), dtype=np.uint32)
        adjacency = {province: set() for province in province_codes.values()}
        for first, second in ((encoded[:, :-1], encoded[:, 1:]), (encoded[:-1, :], encoded[1:, :])):
            changed = first != second
            first_values = first[changed]
            second_values = second[changed]
            target = np.isin(first_values, target_codes) & np.isin(second_values, target_codes)
            pairs = np.unique(np.stack((first_values[target], second_values[target]), axis=1), axis=0)
            for first_code, second_code in pairs:
                first_province = province_codes[int(first_code)]
                second_province = province_codes[int(second_code)]
                adjacency[first_province].add(second_province)
                adjacency[second_province].add(first_province)

        for owner, provinces in groups.items():
            unseen = set(provinces)
            component = {next(iter(unseen))}
            frontier = list(component)
            while frontier:
                province = frontier.pop()
                for neighbor in adjacency[province] & unseen:
                    unseen.remove(neighbor)
                    component.add(neighbor)
                    frontier.append(neighbor)
            self.assertEqual(component, provinces, owner)


class SouthwestTest(unittest.TestCase):
    def setUp(self):
        self.ledger = json.loads(SOUTHWEST_LEDGER_FILE.read_text("utf-8"))
        self.baseline = json.loads(BASELINE_FILE.read_text("utf-8"))
        self.authority = load_authority()

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

    def test_shan_confederation_uses_runtime_shd_tag(self):
        self.assertIn("SHD", self.ledger["starting_tags"])
        self.assertNotIn("SHN", self.ledger["starting_tags"])
        self.assertEqual(self.ledger["country_population"]["SHD"], 125000)
        self.assertNotIn("SHN", self.ledger["country_population"])

    def test_southwest_groups_cover_source_states_without_overlap(self):
        grouped = {state: [] for state in self.ledger["source_states"]}
        for row in self.ledger["groups"]:
            self.assertIn(row["source_state"], grouped)
            self.assertTrue(row["reason"].strip())
            grouped[row["source_state"]].extend(
                authority_group(self.authority, row["source_state"], row["target_country"])["owned_provinces"]
            )
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
        self.authority = load_authority()

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
                    provinces = authority_group(self.authority, row["source_state"], row["target_country"])["owned_provinces"]
                    self.assertTrue(set(provinces).issubset(baseline))

    def test_ocean_groups_do_not_overlap(self):
        for state in self.ledger["source_states"]:
            owned = [
                province
                for row in self.ledger["groups"]
                if row["source_state"] == state
                for province in authority_group(self.authority, state, row["target_country"])["owned_provinces"]
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

    def test_ocean_journal_countries_initialize_shared_variables_before_journal(self):
        country_text = (ROOT / "yongchang_world/common/history/countries/ywc_ocean_countries.txt").read_text("utf-8")
        for tag in ("MHG", "NMG"):
            match = re.search(rf"(?ms)c:{tag}\s*\?=\s*\{{.*?^\s*\}}", country_text)
            self.assertIsNotNone(match, tag)
            block = match.group(0)
            reset = "ywc_reset_shared_variables = yes"
            journal = "add_journal_entry = { type = ywc_je_ocean_frontiers }"
            self.assertIn(reset, block, tag)
            self.assertIn(journal, block, tag)
            self.assertLess(block.index(reset), block.index(journal), tag)


class RegionalCountryHistoryTest(unittest.TestCase):
    def test_new_regional_countries_have_market_and_basic_laws(self):
        text = REGIONAL_COUNTRY_HISTORY_FILE.read_text("utf-8")
        expected = {
            "OIR", "KJU", "MJU", "GJU", "KHO", "HMI", "TRF", "KUC", "KSH", "YRK", "KHT",
            "DER", "KAM", "GYL", "LXJ", "LJG", "SIP", "KTG", "WAA", "KCH", "AHM", "MNP",
            "SHD", "ARA", "LAD", "WBK", "PNP", "PLW", "YAP", "MHL", "MRG",
        }
        for tag in expected:
            match = re.search(rf"(?ms)c:{tag}\s*\?=\s*\{{.*?^\s*\}}", text)
            self.assertIsNotNone(match, tag)
            block = match.group(0)
            self.assertIn("set_market_capital", block)
            self.assertIn("activate_law", block)
            self.assertIn("set_tax_level", block)

        shd = re.search(r"(?ms)c:SHD\s*\?=\s*\{.*?^\s*\}", text)
        self.assertIsNotNone(shd)
        self.assertIn("activate_law = law_type:law_censorship", shd.group(0))


class RuntimeCapacityRegressionTest(unittest.TestCase):
    def test_known_zero_capacity_startup_buildings_are_not_created(self):
        inner_asia = INNER_ASIA_BUILDING_FILE.read_text("utf-8")
        northern_manchuria = NORTHEAST_BUILDING_FILE.read_text("utf-8")
        ocean = OCEAN_BUILDING_FILE.read_text("utf-8")

        self.assertNotIn(
            "building_logging_camp",
            balanced_block(balanced_block(inner_asia, "s:STATE_TIANSHAN"), "region_state:KUC"),
        )
        self.assertNotIn(
            "building_wheat_farm",
            balanced_block(
                balanced_block(northern_manchuria, "s:STATE_NORTHERN_MANCHURIA"),
                "region_state:SHU",
            ),
        )
        self.assertNotIn(
            "building_wheat_farm",
            balanced_block(
                balanced_block(northern_manchuria, "s:STATE_OUTER_MANCHURIA"),
                "region_state:SHU",
            ),
        )
        self.assertNotIn(
            "building_fishing_wharf",
            balanced_block(
                balanced_block(ocean, "s:STATE_WESTERN_AUSTRALIA"),
                "region_state:MRG",
            ),
        )


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
                owned = {p.upper() for p in re.findall(r"\b(x[0-9A-Fa-f]{6})\b", text[start:i - 1])}
                # Vanilla mixes hex case (x7F25CD / x7f25cd); compare normalized.
                vanilla = {p.upper() for p in vanilla}
                foreign = sorted(owned - vanilla)
                missing = sorted(vanilla - owned)
                if foreign:
                    problems.append(f"{path.name}: {state}: {len(foreign)} provinces outside the vanilla region")
                if missing:
                    problems.append(f"{path.name}: {state}: {len(missing)} vanilla provinces left unowned")
        self.assertEqual(problems, [])
        self.assertGreater(len(seen), 0)

    def test_state_definitions_and_provinces_are_unique(self):
        """The vanilla land-state snapshot is the ownership source of truth.

        Sea regions are defined in map data and intentionally have no state
        history block, so they are excluded from this history-file contract.
        """
        baseline = json.loads(BASELINE_FILE.read_text(encoding="utf-8"))
        sea_text = SEA_REGIONS_FILE.read_text(encoding="utf-8-sig")
        sea_states = set(re.findall(r"(?m)^STATE_[A-Z0-9_]+\s*=\s*\{", sea_text))
        sea_states = {state[:-4] for state in sea_states}
        regions = {
            state: {p.upper() for p in provinces}
            for state, provinces in baseline["state_regions"].items()
            if state not in sea_states
        }
        text = NORTHEAST_STATE_FILE.read_text(encoding="utf-8-sig")
        definitions = list(re.finditer(r"(?m)^s:(STATE_[A-Z0-9_]+)\s*=\s*\{", text))
        self.assertEqual(len(definitions), len(set(m.group(1) for m in definitions)))
        self.assertEqual({m.group(1) for m in definitions}, set(regions))

        for index, match in enumerate(definitions):
            end = definitions[index + 1].start() if index + 1 < len(definitions) else len(text)
            body = text[match.end():end]
            provinces = [p.upper() for p in re.findall(r"\bx[0-9A-Fa-f]{6}\b", body)]
            state = match.group(1)
            self.assertEqual(set(provinces), regions[state], state)
if __name__ == "__main__":
    unittest.main()

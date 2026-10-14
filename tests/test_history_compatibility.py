import re
import unittest
from pathlib import Path

from tools.build_history_compatibility import (
    ownership_by_state,
    strip_invalid_military_units,
    strip_invalid_region_states,
    strip_scenario_states,
    strip_unsupported_dlc_history,
)


class HistoryCompatibilityTest(unittest.TestCase):
    def test_removes_only_region_states_absent_from_current_ledger(self):
        source = """POPS = {
    s:STATE_TEST = {
        region_state:OLD = {
            create_pop = { culture = han size = 1 }
        }
        region_state:NEW = {
            create_pop = { culture = han size = 2 }
        }
    }
}
"""
        result, removed = strip_invalid_region_states(
            source, {"STATE_TEST": {"NEW"}}
        )
        self.assertEqual(removed, 1)
        self.assertNotIn("region_state:OLD", result)
        self.assertIn("region_state:NEW", result)

    def test_leaves_vanilla_state_history_untouched_when_all_owners_survive(self):
        source = "POPS = { s:STATE_TEST = { region_state:OLD = { } } }\n"
        result, removed = strip_invalid_region_states(
            source, {"STATE_TEST": {"OLD"}}
        )
        self.assertEqual(removed, 0)
        self.assertEqual(result, source)


    def test_mod_pop_and_building_region_states_match_the_final_state_ledger(self):
        root = Path(__file__).resolve().parents[1]
        history_root = root / "yongchang_world/common/history"
        owners = ownership_by_state(
            (history_root / "states/00_states.txt").read_text(encoding="utf-8-sig")
        )
        for group in ("pops", "buildings"):
            for path in sorted((history_root / group).glob("*.txt")):
                text = path.read_text(encoding="utf-8-sig")
                _, removed = strip_invalid_region_states(text, owners)
                self.assertEqual(removed, 0, f"invalid region_state in {path.name}")

    def test_rehomed_arakan_and_transbaikal_history_keeps_pop_and_building_data(self):
        root = Path(__file__).resolve().parents[1]
        pops = (root / "yongchang_world/common/history/pops/11_east_asia.txt").read_text(encoding="utf-8-sig")
        arakan = pops.split("s:STATE_ARAKAN = {", 1)[1].split("s:STATE_TOHOKU = {", 1)[0]
        self.assertIn("region_state:RKN = {", arakan)
        self.assertNotIn("region_state:BIC", arakan)
        self.assertEqual(sum(map(int, re.findall(r"size = (\d+)", arakan))), 214204)

        asia_buildings = (root / "yongchang_world/common/history/buildings/11_east_asia.txt").read_text(encoding="utf-8-sig")
        arakan_buildings = asia_buildings.split("s:STATE_ARAKAN={", 1)[1].split("s:STATE_SEOUL={", 1)[0]
        self.assertIn("region_state:RKN={", arakan_buildings)
        self.assertIn('building="building_opium_plantation"', arakan_buildings)
        self.assertIn('levels=1', arakan_buildings)

        siberia = (root / "yongchang_world/common/history/buildings/14_siberia.txt").read_text(encoding="utf-8-sig")
        self.assertNotIn("s:STATE_TUVA={", siberia)
        transbaikal = siberia.split("s:STATE_TRANS_BAIKAL={", 1)[1].split("\n\t}", 1)[0]
        self.assertIn("region_state:CHI", transbaikal)
        self.assertIn('country="c:CHI"', transbaikal)
        self.assertIn('region="STATE_TRANS_BAIKAL"', transbaikal)
        self.assertIn('building="building_iron_mine"', transbaikal)

    def test_removes_history_for_unknown_dlc_feature(self):
        source = """BUILDINGS = {
    if = {
        limit = { has_dlc_feature = ip4_content }
        create_building = { building = building_test level = 1 }
    }
    create_building = { building = building_base }
}
"""
        result, removed = strip_unsupported_dlc_history(source)
        self.assertEqual(removed, 1)
        self.assertNotIn("ip4_content", result)
        self.assertIn("building_base", result)

    def test_removes_the_complete_block_for_a_scenario_state(self):
        source = """POPS = {
    s:STATE_REPLACED = { region_state:OLD = { create_pop = { } } }
    s:STATE_VANILLA = { region_state:OLD = { create_pop = { } } }
}
"""
        result, removed = strip_scenario_states(source, {"STATE_REPLACED"})
        self.assertEqual(removed, 1)
        self.assertNotIn("STATE_REPLACED", result)
        self.assertIn("STATE_VANILLA", result)

    def test_removes_invalid_combat_units_but_keeps_surviving_formation(self):
        source = """MILITARY_FORMATIONS = {
    c:BUR ?= {
        create_military_formation = {
            type = army
            combat_unit = {
                state_region = s:STATE_SAFE
                count = 1
            }
            combat_unit = {
                state_region = s:STATE_REPLACED
                count = 1
            }
            save_scope_as = bur_army
        }
    }
}
"""
        result, removed = strip_invalid_military_units(
            source,
            {"STATE_SAFE": {"BUR"}, "STATE_REPLACED": {"ARA"}},
            {"BUR": {"STATE_SAFE"}, "ARA": {"STATE_REPLACED"}},
        )
        self.assertEqual(removed, 1)
        self.assertIn("STATE_SAFE", result)
        self.assertNotIn("STATE_REPLACED", result)
        self.assertIn("bur_army", result)

    def test_removes_country_without_any_surviving_state(self):
        source = """MILITARY_FORMATIONS = {
    c:CHI ?= {
        create_military_formation = { type = army }
    }
}
"""
        result, removed = strip_invalid_military_units(
            source, {"STATE_REPLACED": {"SHU"}}, {"SHU": {"STATE_REPLACED"}}
        )
        self.assertEqual(removed, 1)
        self.assertNotIn("c:CHI", result)


if __name__ == "__main__":
    unittest.main()

import unittest

from tools.build_history_compatibility import (
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

"""Non-skipping source contract and strict hook gate for NMG bay ports."""
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from nmg_bay_runtime import NmgBayWorld
from test_v03_nmg_school_runtime import literal_countries
from test_v03_nmg_bay_protocol import countries
from kor_partner_protocol_runtime import StateRef
from shu_kor_strict_review_runtime import field


class NmgBayLiteralGate(unittest.TestCase):
    def setUp(self):
        self.world = NmgBayWorld(literal_countries())

    def test_independent_hook_is_loaded_and_dispatches_for_both_countries(self):
        self.world.assert_bay_hook_loaded_once()
        before = dict(self.world.treasury)
        self.world.run_country_monthly("NMG")
        self.world.run_country_monthly("MEX")
        self.assertEqual(self.world.treasury, before)

    def test_catalog_has_eight_native_events_and_one_real_foreign_reply(self):
        arcs = [arc for arc in self.world.cat["arcs"]
                if arc.get("slug") == "v03_nmg_bay_ports"]
        self.assertEqual(len(arcs), 1, "authored bay arc is missing or duplicated")
        arc = arcs[0]
        self.assertEqual([e["id"] for e in arc["events"]],
                         [f"ywc_nmg.{n}" for n in range(1100, 1109)])
        self.assertEqual(len(arc["journals"]), 2)
        self.assertTrue(all(j["id"] in self.world.journal_defs for j in arc["journals"]))
        self.assertIn("ywc_nmg.1108", self.world.event_defs)

    def test_real_port_employee_is_on_captured_state_and_loses_eligibility_on_transfer(self):
        world = NmgBayWorld(countries())
        world.run_script("""
            every_scope_state = { limit = { owner = ROOT state_region = s:STATE_BAJA_CALIFORNIA }
                save_scope_as = bay_test_state }
            set_variable = { name = bay_test_pilot value = scope:bay_test_state }
        """, "NMG")
        ref = world.countries["NMG"]["bay_test_pilot"]
        self.assertIsInstance(ref, StateRef)
        query = """exists = var:bay_test_pilot var:bay_test_pilot = {
            owner = ROOT market_access >= .75
            any_scope_pop = { is_pop_type = laborers is_employed = yes
                workplace ?= { is_building_type = building_port occupancy >= .8
                    building_has_goods_shortage = no } }
        }"""
        self.assertTrue(world.check_script(query, "NMG"))
        state = world.countries["NMG"]["states"][0]
        dockworker = next(p for p in state["pops"] if p["type"] == "laborers")
        dockworker["workplace"]["occupancy"] = .79
        self.assertFalse(world.check_script(query, "NMG"))
        dockworker["workplace"]["occupancy"] = .8
        dockworker["employed"] = False
        self.assertFalse(world.check_script(query, "NMG"))
        dockworker["employed"] = True
        state["owner"] = "MEX"
        self.assertFalse(world.check_script(query, "NMG"))
        self.assertEqual(world.countries["NMG"]["bay_test_pilot"], ref)

    def test_three_authored_benefits_have_distinct_native_values(self):
        expected = {
            "ywc_nmg_bay_public_port": {"building_port_throughput_add": .10},
            "ywc_nmg_bay_supervised_port": {"building_port_throughput_add": .05, "state_trade_capacity_mult": .10},
            "ywc_nmg_bay_reduced_port": {"building_port_throughput_add": .025},
        }
        for name, modifiers in expected.items():
            with self.subTest(name=name):
                for key, value in modifiers.items():
                    self.assertEqual(float(field(self.world.modifier_defs[name], key)), value)


if __name__ == "__main__":
    unittest.main()

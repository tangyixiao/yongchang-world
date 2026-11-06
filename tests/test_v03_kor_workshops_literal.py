"""Literal current facts and a non-skipping real catalog RED for KOR industry."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kor_partner_protocol_runtime import StateRef
from kor_workshops_runtime import KorWorkshopsWorld
from shu_kor_strict_review_runtime import field
from test_v03_kor_provincial_revenue import current_facts


def fixture():
    state = current_facts("provincial")
    province = state["states"][0]
    province["market_access"] = .9
    office = next(b for b in province["buildings"] if b["type"] == "building_government_administration")
    factory = copy.deepcopy(office)
    factory.update(type="building_textile_mill", occupancy=.8, shortage=False,
                   weekly_profit=100, cash_reserves_ratio=.5)
    province["buildings"].append(factory)
    worker = copy.deepcopy(province["pops"][0])
    worker.update(type="laborers", employed=True, workplace=factory, standard_of_living=12)
    province["pops"].append(worker)
    subsistence = copy.deepcopy(office)
    subsistence.update(type="building_subsistence_farm", occupancy=.8, shortage=False,
                       active_production_methods=["pm_home_workshops_building_subsistence_farm"])
    province["buildings"].append(subsistence)
    peasant = copy.deepcopy(worker)
    peasant.update(type="peasants", workplace=subsistence, standard_of_living=9)
    province["pops"].append(peasant)
    return {"KOR": state, "CHI": {"states": []}}


def world():
    return KorWorkshopsWorld(countries=fixture())


class KorWorkshopsLiteral(unittest.TestCase):
    def test_each_stage_has_distinct_bilingual_story_and_public_cost_choices(self):
        w=world();arc=next(a for a in w.cat['arcs'] if a['slug']=='v03_kor_workshops_credit')
        for language in ('zh','en'):
            self.assertEqual(len({e['title'][language] for e in arc['events']}),8)
            self.assertEqual(len({e['desc'][language] for e in arc['events']}),8)
        opening=arc['events'][0];by_key={o['key']:o for o in opening['options']}
        for key in ('office_service','infrastructure','home_workshops'):
            self.assertIn('24',by_key[key]['cost_note']['en'])
        self.assertIn('no state service modifier',by_key['limited_preparation']['cost_note']['en'])
        review={o['key']:o for o in arc['events'][5]['options']}
        self.assertIn('half',review['reuse_military_review']['cost_note']['en'])
        self.assertIn('not recoverable loan principal',arc['events'][7]['desc']['en'])

    def test_real_card_is_present_with_eight_events_and_two_journals(self):
        w = world()
        arcs = [a for a in w.cat["arcs"] if a.get("slug") == "v03_kor_workshops_credit"]
        self.assertEqual(len(arcs), 1, "the authored KOR workshops card is absent")
        self.assertEqual([e["id"] for e in arcs[0]["events"]], [f"ywc_kor.{n}" for n in range(1110, 1118)])
        self.assertEqual(len(arcs[0]["journals"]), 2)

    def test_same_employed_worker_same_workplace_profit_and_living_standard(self):
        w = world()
        query = """any_scope_state = { owner = ROOT
            any_scope_pop = { is_pop_type = laborers is_employed = yes standard_of_living >= 10
                workplace ?= { is_building_type = building_textile_mill occupancy >= .5
                    weekly_profit > 0 cash_reserves_ratio >= .25 building_has_goods_shortage = no } }
        }"""
        self.assertTrue(w.check_script(query, "KOR"))
        province = w.countries["KOR"]["states"][0]
        worker = next(p for p in province["pops"] if p["type"] == "laborers")
        for target, field, bad in ((worker, "employed", False), (worker, "standard_of_living", 9),
                                   (worker["workplace"], "weekly_profit", 0),
                                   (worker["workplace"], "shortage", True)):
            previous = target[field]
            target[field] = bad
            self.assertFalse(w.check_script(query, "KOR"), field)
            target[field] = previous
        workplace = worker["workplace"]
        province["buildings"].remove(workplace)
        self.assertFalse(w.check_script(query, "KOR"), "a detached workplace cannot satisfy current employment")
        province["buildings"].append(workplace)
        for bad in ("yes", 1, None):
            worker["employed"] = bad
            with self.subTest(employed=bad), self.assertRaises(AssertionError):
                w.check_script(query, "KOR")
        worker["employed"] = True
        self.assertIsNone(w.state_scope)
        self.assertIsNone(w.pop_scope)
        self.assertIsNone(w.building_scope)

    def test_captured_original_state_is_not_replaced_after_transfer(self):
        w = world()
        w.run_script("""every_scope_state = { limit = { owner = ROOT state_region = s:STATE_SEOUL }
            save_scope_as = workshop_test_state }
            set_variable = { name = workshop_test_pilot value = scope:workshop_test_state }""", "KOR")
        selected = w.countries["KOR"]["workshop_test_pilot"]
        self.assertIsInstance(selected, StateRef)
        condition = "exists = var:workshop_test_pilot var:workshop_test_pilot = { owner = ROOT }"
        self.assertTrue(w.check_script(condition, "KOR"))
        w.countries["KOR"]["states"][0]["owner"] = "CHI"
        self.assertFalse(w.check_script(condition, "KOR"))
        self.assertEqual(w.countries["KOR"]["workshop_test_pilot"], selected)

    def test_old_workshop_requires_real_peasant_and_active_matching_production_method(self):
        w = world()
        query = """any_scope_state = { owner = ROOT any_scope_pop = {
            is_pop_type = peasants is_employed = yes standard_of_living >= 8
            workplace ?= { is_building_type = building_subsistence_farm occupancy >= .5
                building_has_goods_shortage = no
                has_active_production_method = pm_home_workshops_building_subsistence_farm } } }"""
        self.assertTrue(w.check_script(query, "KOR"))
        province = w.countries["KOR"]["states"][0]
        peasant = next(p for p in province["pops"] if p["type"] == "peasants")
        peasant["workplace"]["active_production_methods"].clear()
        self.assertFalse(w.check_script(query, "KOR"))

    def test_identical_region_healthy_second_state_cannot_supply_original_pilot(self):
        countries = fixture()
        original = countries["KOR"]["states"][0]
        second = copy.deepcopy(original)
        second["market_access"] = .4
        countries["KOR"]["states"].append(second)
        w = KorWorkshopsWorld(countries=countries)
        w.run_script("""every_scope_state = { limit = { owner = ROOT
                state_region = s:STATE_SEOUL market_access >= .8 }
            save_scope_as = workshop_test_state }
            set_variable = { name = workshop_test_pilot value = scope:workshop_test_state }""", "KOR")
        query = """exists = var:workshop_test_pilot var:workshop_test_pilot = { owner = ROOT
            any_scope_pop = { is_pop_type = laborers is_employed = yes
                workplace ?= { is_building_type = building_textile_mill occupancy >= .5
                    weekly_profit > 0 building_has_goods_shortage = no } } }"""
        self.assertTrue(w.check_script(query, "KOR"))
        next(p for p in original["pops"] if p["type"] == "laborers")["employed"] = False
        second["market_access"] = .9
        self.assertFalse(w.check_script(query, "KOR"))
        self.assertTrue(next(p for p in second["pops"] if p["type"] == "laborers")["employed"])

    def test_malformed_or_missing_economic_facts_fail_loudly_and_restore_scopes(self):
        for field, bad in (("weekly_profit", float("nan")), ("cash_reserves_ratio", True),
                           ("cash_reserves_ratio", 1.1)):
            with self.subTest(field=field, bad=bad):
                w = world()
                province = w.countries["KOR"]["states"][0]
                worker = next(p for p in province["pops"] if p["type"] == "laborers")
                worker["workplace"][field] = bad
                query = f"""any_scope_state = {{ owner = ROOT any_scope_pop = {{
                    is_pop_type = laborers is_employed = yes workplace ?= {{
                    is_building_type = building_textile_mill {field} >= 0 }} }} }}"""
                with self.assertRaises(AssertionError):
                    w.check_script(query, "KOR")
                self.assertIsNone(w.state_scope)
                self.assertIsNone(w.pop_scope)
                self.assertIsNone(w.building_scope)

    def test_authored_state_modifiers_are_removed_on_actual_owner_change(self):
        for name in ("ywc_kor_workshops_office_service", "ywc_kor_workshops_infrastructure",
                     "ywc_kor_workshops_home_workshops"):
            with self.subTest(modifier=name):
                w = world()
                w.run_script("""every_scope_state = { limit = { owner = ROOT state_region = s:STATE_SEOUL }
                    save_scope_as = workshop_test_state }
                    set_variable = { name = workshop_test_pilot value = scope:workshop_test_state }""", "KOR")
                state = w.countries["KOR"]; pilot = state["workshop_test_pilot"]
                w.run_script(f"var:workshop_test_pilot = {{ add_modifier = {{ name = {name} months = 24 }} }}", "KOR")
                self.assertIn((pilot, name), w.state_modifiers)
                state["states"][0]["owner"] = "CHI"
                w.run_state_owner_change(pilot)
                self.assertNotIn((pilot, name), w.state_modifiers)

    def test_authored_modifiers_have_distinct_nonzero_native_effects(self):
        w = world()
        expected = {
            "ywc_kor_workshops_office_service": ("building_group_bg_manufacturing_throughput_add", .05),
            "ywc_kor_workshops_infrastructure": ("state_infrastructure_add", 5),
            "ywc_kor_workshops_home_workshops": ("building_group_bg_subsistence_agriculture_peasants_standard_of_living_add", 1),
        }
        for name, (key, value) in expected.items():
            with self.subTest(modifier=name):
                self.assertEqual(float(field(w.modifier_defs[name], key)), value)


if __name__ == "__main__":
    unittest.main()

"""Literal unit coverage for ShuRuralWorld's three bounded native primitives.

Covers POP standard_of_living, BUILDING has_active_production_method, and the
strict country market_capital.market -> mg:<good> -> market_goods_pricier read,
plus scope restoration on True/False/exception, multi-good conjunction,
country isolation, and zero/nonfinite/wrong-type rejection. No business
predicate, fee, stage or readiness flag exists here.

Fixture note: the default world uses rural_facts() so every documented explicit
fact (grain price, POP SoL, active PM, state average_sol, truthful occupations
with actual same-object workplace links) is present before any deletion
negative removes exactly one target field.
"""
import copy
import unittest

from clausewitz_harness import parse
from shu_rural_runtime import ShuRuralWorld
from test_v03_shu_public_runtime import public_facts
from test_v03_tib_foundation_lifecycle import TibWorldFacts


RICE = "building_subsistence_rice_farm"
HOME_PM = "pm_home_workshops_building_subsistence_rice_farm"
POP_SOL = ("any_scope_state = { owner = ROOT any_scope_pop = { "
           "is_pop_type = peasants is_employed = yes standard_of_living >= 5 } }")
ACTIVE_PM = ("any_scope_state = { owner = ROOT any_scope_building = { "
             "is_building_type = " + RICE + " has_active_production_method = " + HOME_PM + " } }")
MARKET = "market_capital.market = { mg:grain = { market_goods_pricier <= .25 } }"


def rural_facts():
    state = public_facts()
    own = state["states"][0]
    own["owner"] = "SHU"
    own["average_sol"] = 12
    rice = {"type": RICE, "occupancy": 1, "shortage": False,
            "groups": ["bg_subsistence_agriculture"],
            "active_production_methods": [HOME_PM]}
    own["buildings"].append(rice)
    own["pops"][0]["standard_of_living"] = 12
    own["pops"].append({"primary": False, "acceptance": 5, "type": "peasants",
                        "employed": True, "wealth": 10, "literacy": .2,
                        "standard_of_living": 8, "workplace": rice})
    state["market"] = {"grain": {"pricier": .25}}
    return state


def world(state=None):
    w = ShuRuralWorld.__new__(ShuRuralWorld)
    TibWorldFacts.__init__(w, "", "", {"SHU": copy.deepcopy(rural_facts()) if state is None else state})
    w.tag, w.t, w.scope_ig = "SHU", "shu", None
    return w


def rice_building(w):
    return next(b for b in w.countries["SHU"]["states"][0]["buildings"]
                if b["type"] == RICE)


def check(w, text):
    return w.conditions(parse(text), "SHU")


def scopes(w):
    return (w.state_scope, w.pop_scope, w.building_scope, w.good_scope, w.scope_ig)


def scopes_reset(w):
    return all(value is None for value in scopes(w))


class ShuRuralPopStandardOfLiving(unittest.TestCase):
    def test_pop_sol_is_explicit_numeric_and_separate_from_state_average(self):
        w = world()
        self.assertTrue(check(w, POP_SOL))
        state = w.countries["SHU"]["states"][0]
        pop = state["pops"][1]
        pop["standard_of_living"] = 0
        self.assertTrue(check(w, POP_SOL.replace(">= 5", ">= 0")))
        self.assertFalse(check(w, POP_SOL))
        del pop["standard_of_living"]
        with self.assertRaises(AssertionError):
            check(w, POP_SOL.replace(">= 5", ">= 0"))
        self.assertTrue(scopes_reset(w))
        pop["standard_of_living"] = 8
        self.assertTrue(check(w, "any_scope_state = { owner = ROOT average_sol >= 10 }"))
        del state["average_sol"]
        with self.assertRaises(AssertionError):
            check(w, "any_scope_state = { owner = ROOT average_sol >= 10 }")
        self.assertTrue(check(w, POP_SOL))
        self.assertTrue(scopes_reset(w))

    def test_pop_sol_zero_allowed_but_bool_string_nan_inf_missing_fail_closed(self):
        for value in (0, 0.0, 8):
            w = world()
            w.countries["SHU"]["states"][0]["pops"][1]["standard_of_living"] = value
            self.assertTrue(check(w, POP_SOL.replace(">= 5", ">= 0")))
        for value in (True, False, "8", float("nan"), float("inf"), float("-inf"), None):
            w = world()
            w.countries["SHU"]["states"][0]["pops"][1]["standard_of_living"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                check(w, POP_SOL)
            self.assertTrue(scopes_reset(w))
        w = world()
        del w.countries["SHU"]["states"][0]["pops"][1]["standard_of_living"]
        with self.assertRaises(AssertionError):
            check(w, POP_SOL)
        self.assertTrue(scopes_reset(w))

    def test_pop_sol_outside_actual_pop_scope_fails_closed(self):
        w = world()
        with self.assertRaises(AssertionError):
            w.condition(("standard_of_living", ">=", "10"), "SHU")
        self.assertTrue(scopes_reset(w))
        w2 = world()
        with self.assertRaises(AssertionError):
            check(w2, "any_scope_state = { owner = ROOT standard_of_living >= 10 }")
        self.assertTrue(scopes_reset(w2))

    def test_pop_sol_malformed_query_operator_fails_closed(self):
        w = world()
        with self.assertRaises(AssertionError):
            w.condition(("standard_of_living", "=", ["10"]), "SHU")
        self.assertTrue(scopes_reset(w))


class ShuRuralActiveProductionMethod(unittest.TestCase):
    def test_active_pm_native_leaf_on_actual_workplace_and_building(self):
        w = world()
        self.assertTrue(check(w, ACTIVE_PM))
        self.assertTrue(check(w, "any_scope_state = { owner = ROOT any_scope_pop = { "
                                "is_pop_type = peasants is_employed = yes "
                                "workplace ?= { has_active_production_method = " + HOME_PM + " } } }"))
        pops = w.countries["SHU"]["states"][0]["pops"]
        self.assertIs(pops[1]["workplace"], rice_building(w))
        self.assertTrue(scopes_reset(w))

    def test_active_pm_explicit_empty_collection_is_false_but_missing_fails(self):
        w = world()
        rice_building(w)["active_production_methods"] = []
        self.assertFalse(check(w, ACTIVE_PM))
        self.assertTrue(scopes_reset(w))
        w2 = world()
        del rice_building(w2)["active_production_methods"]
        with self.assertRaises(AssertionError):
            check(w2, ACTIVE_PM)
        self.assertTrue(scopes_reset(w2))

    def test_active_pm_wrong_pm_nonmatching_and_malformed_fail_closed(self):
        w = world()
        self.assertFalse(check(w, ACTIVE_PM.replace(HOME_PM, "pm_potatoes")))
        self.assertTrue(scopes_reset(w))
        w2 = world()
        with self.assertRaises(AssertionError):
            w2.condition(("has_active_production_method", "!=", "pm_potatoes"), "SHU")
        with self.assertRaises(AssertionError):
            w2.condition(("has_active_production_method", "=", "potatoes"), "SHU")
        with self.assertRaises(AssertionError):
            w2.condition(("has_active_production_method", "=", "pm_"), "SHU")
        with self.assertRaises(AssertionError):
            w2.condition(("has_active_production_method", "=", 7), "SHU")
        self.assertTrue(scopes_reset(w2))

    def test_active_pm_valid_unknown_set_nonmatches_false(self):
        w = world()
        rice_building(w)["active_production_methods"] = {"pm_x"}
        self.assertFalse(check(w, ACTIVE_PM))
        self.assertTrue(scopes_reset(w))
        w2 = world()
        rice_building(w2)["active_production_methods"] = ["pm_x"]
        self.assertFalse(check(w2, ACTIVE_PM))
        self.assertTrue(check(w2, ACTIVE_PM.replace(HOME_PM, "pm_x")))
        self.assertTrue(scopes_reset(w2))

    def test_active_pm_malformed_facts_types_fail_closed(self):
        for value in ("pm_x", [7], [None], [True], [["pm_x"]], 5):
            w = world()
            rice_building(w)["active_production_methods"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                check(w, ACTIVE_PM)
            self.assertTrue(scopes_reset(w))


class ShuRuralMarketGrainPrice(unittest.TestCase):
    def test_market_price_strict_country_scope_native_scale(self):
        w = world()
        self.assertTrue(check(w, MARKET))
        self.assertFalse(check(w, MARKET.replace("<=", ">")))
        self.assertTrue(check(w, MARKET.replace("<=", ">=")))
        state = w.countries["SHU"]
        state["market"]["grain"]["pricier"] = 0
        self.assertTrue(check(w, MARKET))
        self.assertFalse(check(w, "market_capital.market = { mg:grain = { market_goods_pricier > 0 } }"))
        self.assertTrue(scopes_reset(w))

    def test_market_missing_facts_never_default_to_cheap_zero(self):
        for removal in ("market", "grain", "pricier"):
            w = world()
            state = w.countries["SHU"]
            if removal == "market":
                del state["market"]
            elif removal == "grain":
                del state["market"]["grain"]
            else:
                del state["market"]["grain"]["pricier"]
            with self.subTest(removal=removal), self.assertRaises(AssertionError):
                check(w, MARKET)
            self.assertTrue(scopes_reset(w))

    def test_market_price_wrong_types_and_nonfinite_fail_closed(self):
        for value in (True, ".25", float("nan"), float("inf"), None):
            w = world()
            w.countries["SHU"]["market"]["grain"]["pricier"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                check(w, MARKET)
            self.assertTrue(scopes_reset(w))

    def test_market_multi_good_children_are_conjunction_not_any(self):
        w = world()
        state = w.countries["SHU"]
        state["market"]["fabric"] = {"pricier": .5}
        both = ("market_capital.market = { mg:grain = { market_goods_pricier <= .25 } "
                "mg:fabric = { market_goods_pricier <= .5 } }")
        self.assertTrue(check(w, both))
        state["market"]["fabric"]["pricier"] = .6
        self.assertFalse(check(w, both))
        self.assertTrue(scopes_reset(w))
        state["market"]["fabric"]["pricier"] = .5
        self.assertFalse(check(w, "market_capital.market = { mg:grain = { market_goods_pricier <= .25 } mg:fabric = { market_goods_pricier <= .1 } }"))
        self.assertTrue(scopes_reset(w))

    def test_market_scope_restored_on_true_false_and_exception(self):
        for text in (MARKET,
                     MARKET.replace("<=", ">"),
                     "market_capital.market = { mg:grain = { imaginary_rural_price_predicate = yes } }"):
            w = world()
            w.good_scope = "leftover"
            if "imaginary" in text:
                with self.assertRaises(AssertionError):
                    check(w, text)
            else:
                self.assertIsInstance(check(w, text), bool)
            self.assertEqual(w.good_scope, "leftover")

    def test_market_country_isolation_no_borrowing_from_other_tag_or_state(self):
        w = world()
        w.countries["NMG"] = {"market": {"grain": {"pricier": 0}}}
        self.assertTrue(check(w, MARKET))
        w.countries["SHU"]["market"]["grain"]["pricier"] = .9
        self.assertFalse(check(w, MARKET))
        self.assertFalse(check(w, "market_capital.market = { mg:grain = { market_goods_pricier <= 0 } }"))
        w.countries["SHU"]["states"][0]["market"] = {"grain": {"pricier": 0}}
        self.assertFalse(check(w, "market_capital.market = { mg:grain = { market_goods_pricier <= 0 } }"))
        self.assertTrue(scopes_reset(w))

    def test_market_malformed_query_shapes_fail_closed(self):
        for text in ("market_capital.market = { }",
                     "market_capital.market = { mg:grain = { } }",
                     "market_capital.market = { grain = { market_goods_pricier <= .25 } }",
                     "market_capital.market ?= { mg:grain = { market_goods_pricier <= .25 } }",
                     "market_capital.market = { mg:grain ?= { market_goods_pricier <= .25 } }",
                     "market_capital.market = { mg: = { market_goods_pricier <= .25 } }"):
            w = world()
            with self.subTest(text=text), self.assertRaises(AssertionError):
                check(w, text)
            self.assertTrue(scopes_reset(w))

    def test_market_goods_pricier_outside_market_scope_fails_closed(self):
        w = world()
        with self.assertRaises(AssertionError):
            w.condition(("market_goods_pricier", "<=", ".25"), "SHU")
        self.assertTrue(scopes_reset(w))

    def test_unsupported_market_goods_measures_stay_unknown(self):
        w = world()
        with self.assertRaises(AssertionError):
            check(w, "market_capital.market = { mg:grain = { market_goods_exports > 0 } }")
        self.assertTrue(scopes_reset(w))

    def test_state_goods_and_urbanization_predicates_are_not_implemented(self):
        w = world()
        for text in ("any_scope_state = { owner = ROOT sg:grain = { state_goods_pricier < .1 } }",
                     "any_scope_state = { owner = ROOT urbanization >= 10 }"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                check(w, text)
            self.assertTrue(scopes_reset(w))


class ShuRuralScopeAndInheritance(unittest.TestCase):
    def test_all_scopes_restore_after_true_false_and_unknown_exception(self):
        for text in (POP_SOL,
                     POP_SOL.replace(">= 5", "<= 1"),
                     "any_scope_state = { owner = ROOT any_scope_pop = { imaginary_rural_pop_predicate = yes } }",
                     ACTIVE_PM,
                     ACTIVE_PM.replace(HOME_PM, "pm_other")):
            w = world()
            w.state_scope, w.pop_scope, w.building_scope = "leak", "leak", "leak"
            w.good_scope, w.scope_ig = "leak", "leak"
            if "imaginary" in text:
                with self.assertRaises(AssertionError):
                    check(w, text)
            else:
                self.assertIsInstance(check(w, text), bool)
            self.assertEqual(scopes(w), ("leak",) * 5)

    def test_existing_literal_leaves_inherit_exact_strict_parent_behavior(self):
        w = world()
        self.assertTrue(check(w, "has_law_or_variant = law_type:law_tenant_farmers"))
        self.assertTrue(check(w, "net_fixed_income >= 0 in_default = no is_at_war = no"))
        self.assertTrue(check(w, "any_scope_state = { owner = ROOT average_sol >= 10 }"))
        self.assertTrue(check(w, "any_scope_state = { owner = ROOT any_scope_pop = { "
                                "is_pop_type = bureaucrats is_employed = yes wealth >= 20 } }"))
        with self.assertRaises(AssertionError):
            check(w, "ywc_shu_rural_ready = yes")

    def test_same_state_jobs_positive_and_split_foreign_empty_unemployed_negatives(self):
        w = world()
        state = w.countries["SHU"]
        original = state["states"][0]
        food = {"type": "building_food_industry", "occupancy": 1,
                "shortage": False, "groups": ["bg_light_industry"]}
        original["buildings"].append(food)
        original["pops"].append({"primary": False, "acceptance": 5,
                                 "type": "laborers", "employed": True,
                                 "wealth": 12, "literacy": .3,
                                 "standard_of_living": 6, "workplace": food})
        combined = ("any_scope_state = { owner = ROOT "
                    "any_scope_pop = { is_pop_type = laborers is_employed = yes "
                    "workplace ?= { is_building_type = building_food_industry } } "
                    "any_scope_pop = { is_pop_type = bureaucrats is_employed = yes "
                    "workplace ?= { is_building_type = building_government_administration } } }")
        self.assertTrue(check(w, combined))
        self.assertTrue(scopes_reset(w))

        split = copy.deepcopy(state)
        del split["states"][0]["pops"][2]
        self.assertFalse(check(world(split), combined))

        foreign = copy.deepcopy(state)
        foreign["states"][0]["owner"] = "NMG"
        self.assertFalse(check(world(foreign), combined))

        empty = copy.deepcopy(state)
        empty["states"][0]["buildings"] = [
            b for b in empty["states"][0]["buildings"]
            if b["type"] != "building_food_industry"]
        empty["states"][0]["pops"][2]["workplace"] = None
        self.assertFalse(check(world(empty), combined))

        unemployed = copy.deepcopy(state)
        unemployed["states"][0]["pops"][2]["employed"] = False
        self.assertFalse(check(world(unemployed), combined))

        missing = copy.deepcopy(state)
        del missing["states"][0]["pops"][2]["workplace"]
        self.assertFalse(check(world(missing), combined))

    def test_unknown_keys_continue_to_strict_parent_failclosed(self):
        w = world()
        with self.assertRaises(AssertionError):
            check(w, "imaginary_rural_country_predicate = yes")
        self.assertTrue(check(w, "net_fixed_income >= 0"))


if __name__ == "__main__":
    unittest.main()

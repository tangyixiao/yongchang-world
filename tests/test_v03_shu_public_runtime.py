"""Primitive current facts and genuine existing SHU producers; no new card yet."""
import copy
import unittest

from clausewitz_harness import parse
from shu_public_runtime import ShuPublicWorld
from shu_kor_strict_review_runtime import facts
from test_v03_tib_foundation_lifecycle import TibWorldFacts
from test_v03_shu_merchant_obligations import repay
from test_v03_shu_provincial_contract import play, choose, month, finish_review
from test_v03_cross_era import early_result, enter_from_prior


IG = """any_interest_group = {
 is_interest_group_type = ig_intelligentsia is_in_government = yes
 ig_clout >= .10 ig_approval >= 0
}"""
OFFICE = """any_scope_state = {
 owner = ROOT state_region = s:STATE_SICHUAN
 any_scope_pop = { is_pop_type = bureaucrats is_employed = yes
 workplace ?= { is_building_type = building_government_administration
 occupancy >= .8 building_has_goods_shortage = no } }
}"""


def public_facts():
    state = facts()
    state["laws"].append("law_right_of_assembly")
    state["literacy_rate"] = .35
    state["states"][0].update(owner="SHU", turmoil=.10)
    for building in state["states"][0]["buildings"]:
        building["level"] = 1
    for group in state["igs"]:
        group.update(in_government=True, clout=.15)
    return state


def new_world():
    world = ShuPublicWorld()
    world.countries["SHU"] = public_facts()
    world.run("ywc_v03_initialize_country", "SHU")
    return world


def literal_world(state=None):
    world = ShuPublicWorld.__new__(ShuPublicWorld)
    TibWorldFacts.__init__(world, "", "", {"SHU": public_facts() if state is None else state})
    world.tag, world.t, world.scope_ig = "SHU", "shu", None
    return world


def check(world, text):
    return world.conditions(parse(text), "SHU")


def merchant_offer(world):
    arc = world.cat["arcs"][0]
    for number, key in ((1000, "pilot_state_sichuan"), (1001, "local_register"),
                        (1002, "time_limited_exemption"), (1003, "budget_queue"),
                        (1004, "local_mediation")):
        play(world, arc, number, key)
    return arc, world.deliver(arc, "ywc_shu.1005")


def complete_shared_provincial(world):
    arc = enter_from_prior(world)
    play(world, arc, 1101, "provincial_funding")
    play(world, arc, 1102, "provincial_self_raise")
    play(world, arc, 1104, "write_share_terms")
    month(world, arc, 6)
    finish_review(world, arc, outcome=2)


class ShuPublicNativeFacts(unittest.TestCase):
    def test_same_ig_must_supply_government_clout_and_approval_together(self):
        world = literal_world()
        self.assertTrue(check(world, IG))
        group = next(g for g in world.countries["SHU"]["igs"] if g["type"] == "ig_intelligentsia")
        group["in_government"] = False
        split = {**group, "in_government": True, "clout": .099}
        world.countries["SHU"]["igs"].append(split)
        self.assertFalse(check(world, IG))
        split.update(clout=.10, approval=-1)
        self.assertFalse(check(world, IG))
        split["approval"] = 0
        self.assertTrue(check(world, IG))
        self.assertIsNone(world.scope_ig)

    def test_missing_ig_fields_and_nonnative_numbers_are_rejected(self):
        for field in ("in_government", "clout", "approval"):
            world = literal_world()
            group = next(g for g in world.countries["SHU"]["igs"] if g["type"] == "ig_intelligentsia")
            del group[field]
            with self.subTest(field=field), self.assertRaises(AssertionError):
                check(world, IG)
            self.assertIsNone(world.scope_ig)
        for value in (True, "0.1", float("nan"), float("inf"), -.1, 1.1):
            world = literal_world()
            group = next(g for g in world.countries["SHU"]["igs"] if g["type"] == "ig_intelligentsia")
            group["clout"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                check(world, IG)

    def test_malformed_and_unknown_ig_query_stays_strict(self):
        world = literal_world()
        for text in ("any_interest_group = { }", "any_interest_group = { clout >= .1 }",
                     "any_interest_group = { ig_clout >= .1 ig_clout >= .2 }",
                     "any_interest_group = { is_in_government = perhaps }"):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                check(world, text)
            self.assertIsNone(world.scope_ig)

    def test_current_censorship_and_assembly_laws_are_native_membership_facts(self):
        world = literal_world()
        self.assertTrue(check(world, "has_law_or_variant = law_type:law_right_of_assembly"))
        self.assertFalse(check(world, "has_law = law_type:law_censorship"))
        state = world.countries["SHU"]
        state["laws"].remove("law_right_of_assembly")
        state["laws"].append("law_censorship")
        self.assertTrue(check(world, "has_law = law_type:law_censorship"))
        self.assertFalse(check(world, "has_law_or_variant = law_type:law_right_of_assembly"))
        for bad in (("has_law", "!=", "law_type:law_censorship"),
                    ("has_law", "=", []), ("has_law", "=", "ig_censorship")):
            with self.subTest(bad=bad), self.assertRaises(AssertionError):
                world.condition(bad, "SHU")
        del state["laws"]
        with self.assertRaises(AssertionError):
            check(world, "has_law = law_type:law_censorship")

    def test_original_owned_region_and_employed_workplace_cannot_borrow_other_state(self):
        world = literal_world()
        state = world.countries["SHU"]
        original = state["states"][0]
        other = copy.deepcopy(original)
        other["region"] = "s:STATE_BEIJING"
        foreign = copy.deepcopy(original)
        foreign["owner"] = "CHI"
        state["states"].extend((other, foreign))
        self.assertTrue(check(world, OFFICE))
        pop = original["pops"][0]
        pop["employed"] = False
        self.assertFalse(check(world, OFFICE))
        pop["employed"] = True
        pop["workplace"]["occupancy"] = .79
        self.assertFalse(check(world, OFFICE))
        pop["workplace"]["occupancy"] = 1
        original["owner"] = "CHI"
        self.assertFalse(check(world, OFFICE))
        original["owner"] = "SHU"
        self.assertTrue(check(world, OFFICE))

    def test_scope_restores_after_invalid_nested_numeric_fact(self):
        world = literal_world()
        world.countries["SHU"]["states"][0]["pops"][0]["workplace"]["occupancy"] = float("nan")
        with self.assertRaises(AssertionError):
            check(world, OFFICE)
        self.assertEqual((world.state_scope, world.pop_scope, world.building_scope, world.scope_ig),
                         (None, None, None, None))

    def test_missing_owner_employment_and_workplace_numeric_fields_do_not_default(self):
        for field in ("owner", "employed", "occupancy"):
            world = literal_world()
            state = world.countries["SHU"]["states"][0]
            target = state if field == "owner" else state["pops"][0]
            if field == "occupancy":
                target = target["workplace"]
            del target[field]
            with self.subTest(field=field), self.assertRaises(AssertionError):
                check(world, OFFICE)

    def test_turmoil_is_an_explicit_state_fraction_and_never_a_missing_calm_default(self):
        world = literal_world()
        self.assertTrue(check(world, "any_scope_state = { owner = ROOT turmoil <= .25 }"))
        state = world.countries["SHU"]["states"][0]
        state["turmoil"] = .250001
        self.assertFalse(check(world, "any_scope_state = { owner = ROOT turmoil <= .25 }"))
        for value in (None, True, "0", -.1, 1.01, float("nan"), float("inf")):
            state["turmoil"] = value
            with self.subTest(value=value), self.assertRaises(AssertionError):
                check(world, "any_scope_state = { owner = ROOT turmoil <= .25 }")
            self.assertIsNone(world.state_scope)
        del state["turmoil"]
        with self.assertRaises(AssertionError):
            check(world, "any_scope_state = { owner = ROOT turmoil <= .25 }")
        with self.assertRaises(AssertionError):
            check(world, "turmoil <= .25")

    def test_missing_country_numbers_and_booleans_are_not_free_qualification(self):
        for field in ("bureaucracy", "legitimacy", "authority", "net_fixed_income", "gold_reserves"):
            world = literal_world()
            del world.countries["SHU"][field]
            with self.subTest(field=field), self.assertRaises(AssertionError):
                check(world, field + " >= 0")
        for field in ("is_at_war", "in_default"):
            world = literal_world()
            del world.countries["SHU"][field]
            with self.subTest(field=field), self.assertRaises(AssertionError):
                check(world, field + " = no")

    def test_unknown_new_business_helper_has_no_ready_stub(self):
        world = literal_world()
        with self.assertRaises(AssertionError):
            check(world, "ywc_shu_public_deliberation_ready = yes")

    def test_named_numeric_thresholds_require_an_actual_current_value(self):
        world = literal_world()
        queries = (("scaled_debt >= var:literal_threshold", "literal_threshold", 0),
                   ("gold_reserves >= { value = var:literal_cost multiply = .5 }", "literal_cost", 1000),
                   ("any_scope_state = { owner = ROOT any_scope_pop = { wealth >= ROOT.literal_wealth } }",
                    "literal_wealth", 25))
        for text, name, amount in queries:
            with self.subTest(text=text):
                with self.assertRaises(AssertionError):
                    check(world, text)
                self.assertEqual((world.state_scope, world.pop_scope, world.building_scope),
                                 (None, None, None))
                world.countries["SHU"][name] = amount
                self.assertTrue(check(world, text))
                world.countries["SHU"][name] = True
                with self.assertRaises(AssertionError):
                    check(world, text)


class ShuPublicExistingHistory(unittest.TestCase):
    def test_actual_merchant_advance_and_twelve_repayments_keep_consultation_in_same_world(self):
        world = new_world()
        state = world.countries["SHU"]
        self.assertNotIn("ywc_shu_merchant_advance", state)
        arc, event = merchant_offer(world)
        before = world.treasury["SHU"]
        choose(world, arc, event, "accept_port_advance")
        principal = state["ywc_shu_merchant_principal"]
        self.assertGreater(principal, 0)
        self.assertEqual(world.treasury["SHU"] - before, principal)
        self.assertEqual(state["ywc_shu_merchant_advance_unpaid"], 1)
        self.assertTrue(check(world, "ywc_shu_merchant_consultation_source = yes"))
        before = world.treasury["SHU"]
        repay(world)
        self.assertAlmostEqual(world.treasury["SHU"] - before, -principal, places=5)
        self.assertEqual(state["ywc_shu_merchant_advance_repaid"], 1)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertTrue(check(world, "ywc_shu_merchant_consultation_source = yes"))
        for number, key in ((1006, "settle_as_provincial"), (1007, "provincial_retention"),
                            (1008, "review_in_peace"), (1009, "confirm_provincial_share")):
            play(world, arc, number, key)
        complete_shared_provincial(world)
        self.assertEqual(state["ywc_shu_prov_share_terms"], 1)
        self.assertEqual(state["ywc_shu_prov_meeting_fee_waived"], 1)
        self.assertEqual(state["ywc_v03_shu_v03_shu_provincial_contract_settled"], 1)
        self.assertTrue(check(world, "ywc_shu_merchant_consultation_source = yes"))
        self.assertTrue(check(world, IG))
        self.assertTrue(check(world, OFFICE))
        self.assertIs(world.countries["SHU"], state)

    def test_actual_fiscal_and_provincial_contracts_run_with_current_public_facts(self):
        for history in ("central", "shared"):
            with self.subTest(history=history):
                world = new_world()
                state = world.countries["SHU"]
                self.assertNotIn("ywc_v03_shu_v03_shu_fiscal_register_settled", state)
                early_result(world, history)
                complete_shared_provincial(world)
                self.assertEqual(state["ywc_shu_prov_outcome"], 2)
                self.assertEqual(state["ywc_v03_shu_v03_shu_provincial_contract_settled"], 1)
                self.assertEqual(state["ywc_shu_prov_share_terms"], 1)
                self.assertEqual(state["ywc_shu_prov_terms_pilot"], state["ywc_shu_v03_prov_pilot_state"])
                self.assertEqual(state["ywc_v03_active_arc_count"], 0)
                self.assertTrue(check(world, IG))
                self.assertTrue(check(world, OFFICE))
                self.assertIs(world.countries["SHU"], state)


if __name__ == "__main__":
    unittest.main()

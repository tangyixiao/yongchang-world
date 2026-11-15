"""Genuine SHU fiscal obligations consumed by public-deliberation source.

Producer results and payments are earned through original events, journals and
calendar callbacks in one world. Later updates change explicit current engine
facts, preserve all earned compatibility markers, and never seed new business.
"""
import copy
import unittest

from shu_public_runtime import ShuPublicWorld
from test_v03_cross_era import early_result, enter_from_prior
from test_v03_shu_merchant_obligations import repay
from test_v03_shu_provincial_contract import finish_review as finish_province
from test_v03_shu_public_runtime import (
    complete_shared_provincial, merchant_offer, new_world as producer_world,
)
from test_v03_shu_public_deliberation import (
    JES, L, P, choose, current_facts, deliberation_arc, finish_review, month,
    office, office_pop, option_legal, play, ready_for_review, world_facts,
)


FISCAL = "v03_shu_fiscal_register"
PROVINCE = "v03_shu_provincial_contract"
FISCAL_RESULT = "ywc_v03_shu_v03_shu_fiscal_register_outcome"


def set_current_facts(world, route="property", *, bare=False, staffing=None, cash=10000):
    """Replace only current facts; the real old business dict remains intact."""
    state = world.countries[world.tag]
    original = copy.deepcopy({key: value for key, value in state.items() if key.startswith("ywc_")})
    current = current_facts(route, bare)
    state.update(copy.deepcopy({key: value for key, value in current.items()
                                if not key.startswith("ywc_") and key != "gold_reserves"}))
    state["gold_reserves"] = cash - world.treasury[world.tag]
    if staffing is not None:
        office(world)["occupancy"] = staffing
    assert {key: state[key] for key in original} == original, "current facts changed earned history"


def current_snapshot(world):
    state = world.countries[world.tag]
    result = copy.deepcopy({key: value for key, value in state.items()
                            if not key.startswith("ywc_") and key != "gold_reserves"})
    result["available_cash"] = state["gold_reserves"] + world.treasury[world.tag]
    return result


def compatibility_snapshot(world):
    return copy.deepcopy({key: value for key, value in world.countries[world.tag].items()
                          if "compatibility" in key})


def earn_repaid_merchant_fiscal(world):
    arc, event = merchant_offer(world)
    state = world.countries[world.tag]
    before = world.treasury[world.tag]
    choose(world, arc, event, "accept_port_advance")
    principal = state["ywc_shu_merchant_principal"]
    assert principal > 0 and world.treasury[world.tag] - before == principal
    before = world.treasury[world.tag]
    repay(world)
    assert abs(world.treasury[world.tag] - before + principal) < .00001
    assert state["ywc_shu_merchant_advance_repaid"] == 1
    assert "ywc_shu_merchant_advance_unpaid" not in state
    for number, key in ((1006, "settle_as_provincial"), (1007, "provincial_retention"),
                        (1008, "review_in_peace"), (1009, "confirm_provincial_share")):
        play(world, arc, number, key)
    assert state[FISCAL_RESULT] == 2
    return principal


def earn_central_province(world, *, setback=False):
    arc = enter_from_prior(world)
    for number, key in ((1101, "central_funding"), (1102, "pay_relief_once"),
                        (1103, "establish_central")):
        play(world, arc, number, key)
    month(world, arc, 6)
    if not setback:
        finish_province(world, arc, outcome=1)
    else:
        play(world, arc, 1106, "settle_on_time")
        event = world.deliver(arc, "ywc_shu.1107")
        world.countries[world.tag]["bureaucracy"] = -1
        choose(world, arc, event, "close_setback")
    return arc


def after_witness_to_review(world, arc, *, limited=False):
    play(world, arc, 1123, "sign_budget")
    play(world, arc, 1124, "register_local_appeal" if limited else "register_public_appeal")
    return arc


def finish_after_review_payment(world, arc, outcome=1):
    play(world, arc, 1126, {1: "request_full", 2: "request_limited", 3: "request_setback"}[outcome])
    play(world, arc, 1127, {1: "close_full", 2: "close_limited", 3: "close_setback"}[outcome])


class ShuDeliberationCrossEra(unittest.TestCase):
    def world(self):
        world = producer_world()
        self.assertIsInstance(world, ShuPublicWorld)
        self.assertNotIn(P + "outcome", world.countries[world.tag])
        return world

    def assert_fiscal_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[FISCAL_RESULT], outcome)
        self.assertEqual(state["ywc_v03_shu_v03_shu_fiscal_register_settled"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))

    def assert_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))

    def assert_compatibility_preserved(self, world, original):
        actual = compatibility_snapshot(world)
        self.assertEqual({key: actual[key] for key in original}, original)

    def test_real_fiscal_local_two_and_central_one_differ_at_register_and_current_witness_with_same_facts(self):
        worlds = [self.world(), self.world()]
        for world, old in zip(worlds, ("shared", "central")):
            early_result(world, old)
            self.assert_fiscal_closed(world, 2 if old == "shared" else 1)
            set_current_facts(world)
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        compat = [compatibility_snapshot(world) for world in worlds]
        arcs, witnesses = [], []
        for world, charge in zip(worlds, (1000, 1500)):
            arc = deliberation_arc(world.cat)
            arcs.append(arc)
            play(world, arc, 1120, "property_representation")
            before = world.treasury[world.tag]
            play(world, arc, 1121, "pay_register")
            self.assertEqual(world.treasury[world.tag] - before, -charge)
            office(world)["occupancy"] = .5
            world.countries[world.tag]["gold_reserves"] = 10000 - world.treasury[world.tag]
            witnesses.append(world.deliver(arc, "ywc_shu.1122"))
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        self.assertTrue(option_legal(worlds[0], witnesses[0], "reuse_local_witness"))
        self.assertFalse(option_legal(worlds[0], witnesses[0], "new_witness"))
        self.assertFalse(option_legal(worlds[1], witnesses[1], "reuse_local_witness"))
        self.assertFalse(option_legal(worlds[1], witnesses[1], "new_witness"))
        choose(worlds[0], arcs[0], witnesses[0], "reuse_local_witness")
        office(worlds[1])["occupancy"] = .8
        choose(worlds[1], arcs[1], witnesses[1], "new_witness")
        for index, (world, arc) in enumerate(zip(worlds, arcs)):
            signature = world.deliver(arc, "ywc_shu.1123")
            office(world)["occupancy"] = .5
            self.assertEqual(option_legal(world, signature, "sign_budget"), index == 0)
            if index:
                office(world)["occupancy"] = .8
            choose(world, arc, signature, "sign_budget")
            play(world, arc, 1124, "register_public_appeal")
            month(world, arc, 6)
            finish_review(world, arc)
            self.assert_closed(world, 1)
            self.assert_compatibility_preserved(world, compat[index])

    def test_real_positive_local_outcome_missing_first_audit_loses_discount_and_old_witness(self):
        world = self.world()
        early_result(world, "shared")
        self.assert_fiscal_closed(world, 2)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_shu_first_audit"], 1)
        del state["ywc_shu_first_audit"]
        set_current_facts(world)
        before = world.treasury[world.tag]
        arc = deliberation_arc(world.cat)
        play(world, arc, 1120, "property_representation")
        play(world, arc, 1121, "pay_register")
        self.assertEqual(world.treasury[world.tag] - before, -1500)
        witness = world.deliver(arc, "ywc_shu.1122")
        self.assertFalse(option_legal(world, witness, "reuse_local_witness"))
        choose(world, arc, witness, "new_witness")
        after_witness_to_review(world, arc)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(world.treasury[world.tag] - before, -3000)
        self.assertEqual(state[FISCAL_RESULT], 2)
        self.assert_closed(world, 1)

    def test_lost_original_fiscal_pilot_cannot_lend_local_right_to_a_different_owned_pilot(self):
        world = self.world()
        early_result(world, "shared")
        set_current_facts(world)
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_shu_v03_pilot_state"], 1)
        second = copy.deepcopy(state["states"][0])
        second.update(owner="SHU", region="s:STATE_CHONGQING")
        state["states"].append(second)
        state["states"][0]["owner"] = "CHI"
        arc = deliberation_arc(world.cat)
        play(world, arc, 1120, "property_representation")
        self.assertEqual(state[P + "pilot"], 2)
        self.assertEqual(state["ywc_shu_v03_pilot_state"], 1)
        before = world.treasury[world.tag]
        play(world, arc, 1121, "pay_register")
        self.assertEqual(world.treasury[world.tag] - before, -1500)
        witness = world.deliver(arc, "ywc_shu.1122")
        self.assertFalse(option_legal(world, witness, "reuse_local_witness"))
        self.assertTrue(option_legal(world, witness, "new_witness"))
        choose(world, arc, witness, "new_witness")
        after_witness_to_review(world, arc)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assert_closed(world, 1)

    def test_current_local_employee_loss_disables_earned_witness_without_refunding_registration(self):
        world = self.world()
        early_result(world, "shared")
        set_current_facts(world, staffing=.5)
        arc = deliberation_arc(world.cat)
        play(world, arc, 1120, "property_representation")
        play(world, arc, 1121, "pay_register")
        event = world.deliver(arc, "ywc_shu.1122")
        self.assertTrue(option_legal(world, event, "reuse_local_witness"))
        cash = world.treasury[world.tag]
        office_pop(world)["employed"] = False
        self.assertFalse(option_legal(world, event, "reuse_local_witness"))
        self.assertEqual(world.treasury[world.tag], cash)
        office_pop(world)["employed"] = True
        choose(world, arc, event, "reuse_local_witness")
        signature = world.deliver(arc, "ywc_shu.1123")
        office(world)["occupancy"] = .49
        self.assertFalse(option_legal(world, signature, "sign_budget"))
        office(world)["occupancy"] = .5
        choose(world, arc, signature, "sign_budget")
        play(world, arc, 1124, "register_public_appeal")
        month(world, arc, 6)
        finish_review(world, arc)
        self.assert_closed(world, 1)

    def test_real_repaid_merchant_consultation_changes_review_price_under_equal_current_property_facts(self):
        worlds = [self.world(), self.world()]
        earn_repaid_merchant_fiscal(worlds[0])
        early_result(worlds[1], "shared")
        for world in worlds:
            self.assert_fiscal_closed(world, 2)
            set_current_facts(world, staffing=.5)
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        for world, review in zip(worlds, (1000, 1500)):
            before = world.treasury[world.tag]
            arc = ready_for_review(world, route="property", witness="reuse_local_witness")
            self.assertEqual(world.treasury[world.tag] - before, -1000)
            month(world, arc, 6)
            bill = world.deliver(arc, "ywc_shu.1125")
            cash = world.treasury[world.tag]
            choose(world, arc, bill, "pay_review")
            self.assertEqual(world.treasury[world.tag] - cash, -review)
            finish_after_review_payment(world, arc)
            self.assert_closed(world, 1)

    def test_each_real_repaid_merchant_component_is_needed_at_unpaid_review_execution(self):
        for missing in ("ywc_shu_merchant_advance_repaid", "ywc_shu_merchant_consultation",
                        "ywc_shu_merchant_principal"):
            with self.subTest(missing=missing):
                world = self.world()
                earn_repaid_merchant_fiscal(world)
                set_current_facts(world, staffing=.5)
                arc = ready_for_review(world, route="property", witness="reuse_local_witness")
                month(world, arc, 6)
                bill = world.deliver(arc, "ywc_shu.1125")
                state = world.countries[world.tag]
                state["gold_reserves"] = 1000 - world.treasury[world.tag]
                self.assertTrue(option_legal(world, bill, "pay_review"))
                del state[missing]
                self.assertFalse(option_legal(world, bill, "pay_review"))
                state["gold_reserves"] = 1500 - world.treasury[world.tag]
                self.assertTrue(option_legal(world, bill, "pay_review"))
                before = world.treasury[world.tag]
                choose(world, arc, bill, "pay_review")
                self.assertEqual(world.treasury[world.tag] - before, -1500)
                finish_after_review_payment(world, arc)
                self.assert_closed(world, 1)

    def test_actual_merchant_source_does_not_bypass_current_owner_or_post_or_explicit_restart(self):
        for loss in ("owner", "employee"):
            with self.subTest(loss=loss):
                world = self.world()
                earn_repaid_merchant_fiscal(world)
                set_current_facts(world, staffing=.5)
                arc = ready_for_review(world, route="property", witness="reuse_local_witness")
                month(world, arc, 6)
                bill = world.deliver(arc, "ywc_shu.1125")
                state = world.countries[world.tag]
                before = world.treasury[world.tag]
                if loss == "owner":
                    state["states"][0]["owner"] = "CHI"
                else:
                    office_pop(world)["employed"] = False
                self.assertFalse(option_legal(world, bill, "pay_review"))
                month(world, arc)
                self.assertEqual(state[P + "review_streak"], 0)
                if loss == "owner":
                    state["states"][0]["owner"] = "SHU"
                else:
                    office_pop(world)["employed"] = True
                event = world.deliver(arc, "ywc_shu.1125")
                choose(world, arc, event, "restart_review")
                month(world, arc, 6)
                finish_review(world, arc)
                self.assertEqual(world.treasury[world.tag] - before, -1000)
                self.assertEqual(state["ywc_shu_merchant_advance_repaid"], 1)
                self.assert_closed(world, 1)

    def test_real_provincial_share_is_an_independent_witness_source_rechecked_at_signature_and_late_request(self):
        for lose_at in (1123, 1126):
            with self.subTest(lose_at=lose_at):
                world = self.world()
                early_result(world, "central")
                complete_shared_provincial(world)
                state = world.countries[world.tag]
                self.assertEqual(state[FISCAL_RESULT], 1)
                self.assertEqual(state["ywc_shu_prov_outcome"], 2)
                self.assertEqual(state["ywc_shu_prov_meeting_fee_paid"], 1)
                set_current_facts(world, staffing=.5)
                arc = deliberation_arc(world.cat)
                for number, key in ((1120, "property_representation"), (1121, "pay_register"),
                                    (1122, "reuse_local_witness")):
                    play(world, arc, number, key)
                if lose_at == 1123:
                    event = world.deliver(arc, "ywc_shu.1123")
                    del state["ywc_shu_prov_share_terms"]
                    self.assertFalse(option_legal(world, event, "sign_budget"))
                    choose(world, arc, event, "withdraw_at_1123")
                    self.assertEqual(state[P + "outcome"], 4)
                else:
                    after_witness_to_review(world, arc)
                    month(world, arc, 6)
                    play(world, arc, 1125, "pay_review")
                    event = world.deliver(arc, "ywc_shu.1126")
                    del state["ywc_shu_prov_meeting_fee_paid"]
                    self.assertFalse(option_legal(world, event, "request_full"))
                    choose(world, arc, event, "request_setback")
                    play(world, arc, 1127, "close_setback")
                    self.assert_closed(world, 3)

    def test_real_central_provincial_budget_responsibility_is_rechecked_after_actual_review_payment(self):
        for lose_at in (1123, 1126):
            with self.subTest(lose_at=lose_at):
                world = self.world()
                early_result(world, "central")
                earn_central_province(world)
                state = world.countries[world.tag]
                self.assertEqual(state["ywc_shu_prov_outcome"], 1)
                self.assertEqual(state["ywc_shu_prov_central_paid"], 1)
                self.assertEqual(state["ywc_shu_prov_relief_paid"], 1)
                set_current_facts(world)
                if lose_at == 1123:
                    arc = deliberation_arc(world.cat)
                    for number, key in ((1120, "property_representation"),
                                        (1121, "pay_register"), (1122, "new_witness")):
                        play(world, arc, number, key)
                    event = world.deliver(arc, "ywc_shu.1123")
                    self.assertTrue(option_legal(world, event, "sign_budget"))
                    del state["ywc_shu_prov_relief_paid"]
                    self.assertFalse(option_legal(world, event, "sign_budget"))
                    choose(world, arc, event, "withdraw_at_1123")
                    self.assertEqual(state[P + "outcome"], 4)
                else:
                    arc = ready_for_review(world, route="property")
                    month(world, arc, 6)
                    play(world, arc, 1125, "pay_review")
                    event = world.deliver(arc, "ywc_shu.1126")
                    del state["ywc_shu_prov_relief_paid"]
                    self.assertFalse(option_legal(world, event, "request_full"))
                    choose(world, arc, event, "request_setback")
                    play(world, arc, 1127, "close_setback")
                    self.assert_closed(world, 3)

    def test_real_old_capped_withdrawn_setback_and_absent_histories_keep_finite_entry_and_earned_compatibility(self):
        for previous in ("capped", "withdrawn", "province_setback", "absent"):
            with self.subTest(previous=previous):
                world = self.world()
                state = world.countries[world.tag]
                if previous in ("capped", "withdrawn"):
                    early_result(world, previous)
                    self.assert_fiscal_closed(world, 3 if previous == "capped" else 4)
                elif previous == "province_setback":
                    early_result(world, "central")
                    earn_central_province(world, setback=True)
                    self.assertEqual(state["ywc_shu_prov_outcome"], 3)
                set_current_facts(world, bare=True)
                compat = compatibility_snapshot(world)
                before_facts = world_facts(world)
                before = world.treasury[world.tag]
                arc = ready_for_review(world, limited=True)
                month(world, arc, 6)
                finish_review(world, arc, outcome=2)
                self.assertEqual(world.treasury[world.tag] - before, -1000)
                self.assertEqual(world_facts(world), before_facts)
                self.assert_compatibility_preserved(world, compat)
                self.assert_closed(world, 2)


if __name__ == "__main__":
    unittest.main()

"""SHU port fiscal-rights carryover: sourced consultation waiver and halved central verification.

Regression tests only; the implementation agent must make these pass without
relaxing any older closure condition. Real 1005 merchant-advance acceptance is
the only accepted source of the consultation right; forged flags and negative
principal are explicit negative controls.
"""
import copy
import unittest

from shu_kor_strict_review_runtime import Strict, facts, runplan, field
from test_v03_shu_content import shu_monthly_effect
from test_v03_shu_merchant_obligations import replay_effect
from test_v03_shu_kor_c1_c4_strict import play


def step(world, arc, number, key):
    event = world.deliver(arc, "ywc_shu." + str(number))
    world.choose(arc, event, key, contexts=False)
    return event


def legal(world, event, name):
    return next(row["legal"] for row in world.options(event) if row["option"] == name)


def merchant_funded_port_offer(route="unified_customs"):
    """Play the real tax-register arc, take the 1005 merchant advance, then reach 1020."""
    world = Strict("shu"); world.countries["SHU"] = facts()
    state = world.countries["SHU"]
    arc0 = world.cat["arcs"][0]
    for number, key in ((1000, "pilot_state_sichuan"), (1001, "local_register"),
                        (1002, "time_limited_exemption"), (1003, "budget_queue"),
                        (1004, "local_mediation")):
        play(world, arc0, number, key)
    offer = world.deliver(arc0, "ywc_shu.1005")
    world.choose(arc0, offer, "accept_port_advance", contexts=False)
    for name in ("ywc_shu_merchant_advance", "ywc_shu_merchant_advance_unpaid",
                 "ywc_shu_merchant_consultation"):
        assert name in state, name
    assert state["ywc_shu_merchant_principal"] > 0
    # The register cannot complete while this advance is unpaid. Preserve the
    # consultation right through actual repayment before entering the port arc.
    for _ in range(12): month(world)
    assert "ywc_shu_merchant_advance_unpaid" not in state
    assert state["ywc_shu_merchant_advance_repaid"] == 1
    for number, key in ((1006, "settle_as_provincial"), (1007, "provincial_retention")):
        step(world, arc0, number, key)
    for _ in range(6): month(world)
    step(world, arc0, 1008, "review_in_peace")
    step(world, arc0, 1009, "confirm_provincial_share")
    assert state["ywc_v03_shu_v03_shu_fiscal_register_settled"] == 1
    arc = world.cat["arcs"][2]
    step(world, arc, 1018, route)
    step(world, arc, 1019, "publish_books")
    return world, arc, world.deliver(arc, "ywc_shu.1020")


def shortcut_port_offer(source=False):
    """Port offer without the real register run; source flags are isolated mutations."""
    world = Strict("shu"); state = facts()
    state["ywc_v03_shu_v03_shu_fiscal_register_settled"] = 1
    world.countries["SHU"] = state
    arc = world.cat["arcs"][2]
    step(world, arc, 1018, "unified_customs")
    step(world, arc, 1019, "publish_books")
    offer = world.deliver(arc, "ywc_shu.1020")
    if source:
        state.update({"ywc_shu_merchant_advance": 1, "ywc_shu_merchant_advance_unpaid": 1,
                      "ywc_shu_merchant_consultation": 1, "ywc_shu_merchant_principal": 800})
    return world, arc, offer, state


def zero_cash(world):
    world.countries["SHU"]["gold_reserves"] = -world.treasury["SHU"]


def central_register_port_to_1022():
    """Real central register result via the authored M1 plan, then port arc to 1022."""
    world = Strict("shu"); world.countries["SHU"] = facts()
    runplan(world, world.cat["arcs"][0])
    assert world.countries["SHU"].get("ywc_v03_shu_v03_shu_fiscal_register_outcome") == 1
    arc = world.cat["arcs"][2]
    step(world, arc, 1018, "unified_customs")
    step(world, arc, 1019, "publish_books")
    step(world, arc, 1020, "refuse_credit")
    step(world, arc, 1021, "current_law_review")
    return world, arc, world.deliver(arc, "ywc_shu.1022")


def month(world):
    world.advance_months(1); world.elapsed_months += 1
    world.execute(shu_monthly_effect(), "SHU")


class ShuPortCarryoverTests(unittest.TestCase):
    def test_verification_menu_rechecks_discount_when_only_half_the_cash_remains(self):
        for defect in ("non_central", "lost_pilot"):
            with self.subTest(defect=defect):
                world, arc, verify = central_register_port_to_1022()
                state = world.countries["SHU"]
                state["gold_reserves"] = 500 - world.treasury["SHU"]
                self.assertTrue(legal(world, verify, "pay_verification"))
                if defect == "non_central":
                    state.pop("ywc_shu_fiscal_outcome_central_audit", None)
                    state["ywc_shu_fiscal_outcome_provincial_share"] = 1
                    state["ywc_v03_shu_v03_shu_fiscal_register_outcome"] = 2
                else:
                    other = copy.deepcopy(state["states"][0])
                    other["region"] = "s:STATE_CHONGQING"
                    state["states"].append(other)
                    state["states"][0]["owned"] = False
                self.assertFalse(legal(world, verify, "pay_verification"))
                cash = world.treasury["SHU"]
                replay_effect(world, verify, "pay_verification")
                self.assertEqual(world.treasury["SHU"], cash)
                self.assertNotIn("ywc_shu_port_receipts_checked", state)
                self.assertEqual(state["ywc_shu_port_pending_event"], 1022)

    def test_recorded_waiver_can_finish_after_later_loss_of_the_old_source_record(self):
        world, arc, offer = merchant_funded_port_offer("merchant_share")
        state = world.countries["SHU"]; zero_cash(world)
        world.choose(arc, offer, "consult_only", contexts=False)
        self.assertIn("ywc_shu_port_fee_waived", state)
        cash = world.treasury["SHU"]
        # Explicit post-grant fault: historical source evidence is lost, not
        # the already resolved port fee. This must not invent a new liability.
        state.pop("ywc_shu_merchant_consultation")
        for number, key in ((1021, "current_law_review"), (1022, "pay_verification"),
                            (1023, "share_form"), (1024, "shared_burden")):
            step(world, arc, number, key)
        for _ in range(7): world.pulse(arc)
        final = world.deliver(arc, "ywc_shu.1025")
        self.assertTrue(legal(world, final, "settle_share"))
        world.choose(arc, final, "settle_share", contexts=False)
        self.assertEqual(state["ywc_shu_port_outcome"], 2)
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertNotIn("ywc_shu_port_fee_paid", state)
        self.assertEqual(state["ywc_shu_merchant_advance_repaid"], 1)

    def test_real_advance_source_waives_the_1020_consultation_fee_with_zero_cash(self):
        world, arc, offer = merchant_funded_port_offer()
        state = world.countries["SHU"]
        zero_cash(world)
        self.assertTrue(legal(world, offer, "consult_only"),
                        "a real 1005 advance source must keep the consultation usable without cash")
        cash = world.treasury["SHU"]; principal = state["ywc_shu_merchant_principal"]
        world.choose(arc, offer, "consult_only", contexts=False)
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertIn("ywc_shu_port_fee_waived", state)
        self.assertNotIn("ywc_shu_port_fee_paid", state)
        self.assertNotIn("ywc_shu_port_fee_amount", state)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1021)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state["ywc_shu_merchant_advance_repaid"], 1)
        self.assertEqual(state["ywc_shu_merchant_principal"], principal)
        step(world, arc, 1021, "current_law_review")
        verify = world.deliver(arc, "ywc_shu.1022")
        self.assertTrue(legal(world, verify, "pay_verification"),
                        "1022 must still read the sourced waiver")
        world.choose(arc, verify, "pay_verification", contexts=False)
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertIn("ywc_shu_port_fee_waived", state)
        self.assertNotIn("ywc_shu_port_fee_paid", state)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1023)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state["ywc_shu_merchant_principal"], principal)
        month(world)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state["ywc_shu_merchant_advance_repaid"], 1)
        self.assertNotIn("ywc_shu_merchant_repayment_months", state)
        self.assertEqual(world.treasury["SHU"], cash)

    def test_without_a_source_the_consultation_still_costs_half_and_writes_no_waiver(self):
        world, arc, offer, state = shortcut_port_offer(source=False)
        self.assertTrue(legal(world, offer, "consult_only"))
        cash = world.treasury["SHU"]
        world.choose(arc, offer, "consult_only", contexts=False)
        self.assertEqual(world.treasury["SHU"], cash - 500)
        self.assertEqual(state.get("ywc_shu_port_fee_paid"), 1)
        self.assertEqual(state.get("ywc_shu_port_fee_amount"), 500)
        self.assertNotIn("ywc_shu_port_fee_waived", state)

    def test_a_forged_consultation_flag_alone_cannot_waive_the_fee(self):
        # Explicit negative control: an isolated consultation flag without the
        # acceptance record and positive principal is not a source.
        world, arc, offer, state = shortcut_port_offer(source=False)
        state["ywc_shu_merchant_consultation"] = 1
        zero_cash(world)
        self.assertFalse(legal(world, offer, "consult_only"))
        cash = world.treasury["SHU"]
        replay_effect(world, offer, "consult_only")
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertNotIn("ywc_shu_port_fee_waived", state)
        self.assertNotIn("ywc_shu_port_fee_paid", state)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)

    def test_a_negative_principal_source_cannot_waive_the_fee(self):
        # Explicit negative control: acceptance + consultation with a broken
        # principal is not a real tax-book advance.
        world, arc, offer, state = shortcut_port_offer(source=False)
        state.update({"ywc_shu_merchant_advance": 1, "ywc_shu_merchant_advance_unpaid": 1,
                      "ywc_shu_merchant_consultation": 1, "ywc_shu_merchant_principal": -100})
        self.assertTrue(legal(world, offer, "consult_only"))
        cash = world.treasury["SHU"]
        world.choose(arc, offer, "consult_only", contexts=False)
        self.assertEqual(world.treasury["SHU"], cash - 500)
        self.assertEqual(state.get("ywc_shu_port_fee_paid"), 1)
        self.assertEqual(state.get("ywc_shu_port_fee_amount"), 500)
        self.assertNotIn("ywc_shu_port_fee_waived", state)

    def test_source_lost_after_display_falls_back_to_cash_and_blocks_a_free_advance(self):
        world, arc, offer = merchant_funded_port_offer()
        state = world.countries["SHU"]
        zero_cash(world)
        for name in ("ywc_shu_merchant_advance", "ywc_shu_merchant_advance_unpaid",
                     "ywc_shu_merchant_consultation", "ywc_shu_merchant_principal"):
            state.pop(name, None)
        self.assertFalse(legal(world, offer, "consult_only"),
                         "a source lost after display must be re-checked at execution")
        cash = world.treasury["SHU"]
        replay_effect(world, offer, "consult_only")
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertNotIn("ywc_shu_port_fee_waived", state)
        self.assertNotIn("ywc_shu_port_fee_paid", state)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)

    def test_real_central_register_result_with_the_pilot_halves_the_1022_fee(self):
        world, arc, verify = central_register_port_to_1022()
        state = world.countries["SHU"]
        cash = world.treasury["SHU"]
        self.assertTrue(legal(world, verify, "pay_verification"))
        world.choose(arc, verify, "pay_verification", contexts=False)
        self.assertEqual(world.treasury["SHU"], cash - 500)
        self.assertEqual(state.get("ywc_shu_port_fee_amount"), 500)
        self.assertEqual(state.get("ywc_shu_port_fee_paid"), 1)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1023)

    def test_a_non_central_result_or_lost_pilot_keeps_the_full_fee(self):
        # Explicit negative control: the settled marker with a non-central
        # register outcome is not a central result.
        for defect in ("provincial", "pilot_lost"):
            with self.subTest(defect=defect):
                world, arc, verify = central_register_port_to_1022()
                state = world.countries["SHU"]
                if defect == "provincial":
                    state["ywc_v03_shu_v03_shu_fiscal_register_outcome"] = 2
                    state.pop("ywc_shu_fiscal_outcome_central_audit", None)
                    state["ywc_shu_fiscal_outcome_provincial_share"] = 1
                else:
                    other = copy.deepcopy(state["states"][0])
                    other["region"] = "s:STATE_CHONGQING"
                    state["states"].append(other)
                    state["states"][0]["owned"] = False
                cash = world.treasury["SHU"]
                world.choose(arc, verify, "pay_verification", contexts=False)
                self.assertEqual(world.treasury["SHU"], cash - 1000, defect)
                self.assertEqual(state.get("ywc_shu_port_fee_amount"), 1000, defect)

    def test_half_mode_does_not_stack_the_central_discount_to_a_quarter(self):
        # Explicit negative control: a leftover half-fee mode must not multiply
        # with the central discount.
        world, arc, verify = central_register_port_to_1022()
        state = world.countries["SHU"]
        state["ywc_shu_port_fee_half_mode"] = 1
        cash = world.treasury["SHU"]
        world.choose(arc, verify, "pay_verification", contexts=False)
        self.assertEqual(world.treasury["SHU"], cash - 500)
        self.assertEqual(state.get("ywc_shu_port_fee_amount"), 500)

    def test_a_paid_fee_is_neither_refunded_nor_recharged_later(self):
        world, arc, offer, state = shortcut_port_offer(source=False)
        world.choose(arc, offer, "consult_only", contexts=False)
        after_consult = world.treasury["SHU"]
        self.assertEqual(state.get("ywc_shu_port_fee_amount"), 500)
        step(world, arc, 1021, "current_law_review")
        verify = world.deliver(arc, "ywc_shu.1022")
        self.assertTrue(legal(world, verify, "pay_verification"))
        world.choose(arc, verify, "pay_verification", contexts=False)
        self.assertEqual(world.treasury["SHU"], after_consult)
        self.assertEqual(state.get("ywc_shu_port_fee_amount"), 500)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1023)

    def test_stale_port_stages_cannot_reopen_the_credit_queue_with_the_right(self):
        for stage, pending in (("ywc_shu_port_law_verified", 1022),
                               ("ywc_shu_port_receipts_checked", 1023),
                               ("ywc_shu_port_settlement_choice", 1024),
                               ("ywc_shu_port_review", 1025)):
            with self.subTest(stage=stage):
                world, arc, offer, state = shortcut_port_offer(source=True)
                state[stage] = 1
                state["ywc_shu_port_pending_event"] = pending
                self.assertFalse(legal(world, offer, "consult_only"))
                cash = world.treasury["SHU"]
                replay_effect(world, offer, "consult_only")
                self.assertEqual(world.treasury["SHU"], cash)
                self.assertNotIn("ywc_shu_port_fee_waived", state)
                self.assertNotIn("ywc_shu_port_fee_paid", state)
                self.assertEqual(state.get("ywc_shu_port_pending_event"), pending)


if __name__ == "__main__":
    unittest.main()

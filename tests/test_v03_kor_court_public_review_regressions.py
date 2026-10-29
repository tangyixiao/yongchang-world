"""Reached sourcefix3 review regressions; all positive history is genuinely earned."""
import copy
import unittest

from test_v03_kor_court_public import (
    L, P, choose, force_option, group, new_world, option_legal,
)
from test_v03_kor_court_public_cross_era import (
    cash, close_after_payment, month, native_deliver, play, ready,
    revenue_world, school_world, set_current,
)


def current(world, suffix):
    return world.conditions(world.trigger_defs[P + suffix], world.tag)


def state_and_cash(world):
    return copy.deepcopy((world.countries[world.tag], world.treasury,
                          world.active, world.history))


def paid_world(limited=False):
    world = new_world()
    arc = ready(world, limited=limited)
    month(world, arc, 6)
    play(world, arc, 1125, "pay_review")
    state = world.countries[world.tag]
    expected = 500 if limited else 1000
    assert state[P + "petition_paid_amount"] == state[P + "review_paid_amount"] == expected
    assert state[P + "review_mature"] == 1 and state[P + "review_streak"] == 6
    return world, arc


class KorCourtPublicReviewRegressions(unittest.TestCase):
    def assert_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual((state[P + "outcome"], state[L + "outcome"], state[L + "settled"]),
                         (outcome, outcome, 1))

    def test_paid_late_new_opposition_and_suppressed_category_block_full_and_finite(self):
        for limited in (False, True):
            base, arc = paid_world(limited)
            for loss in ("opposition", "suppressed"):
                for stage in (1126, 1127):
                    with self.subTest(limited=limited, loss=loss, stage=stage):
                        world = copy.deepcopy(base)
                        suffix = "finite" if limited else "full"
                        if stage == 1127:
                            play(world, arc, 1126, "request_" + suffix)
                        event = native_deliver(world, arc, stage)
                        state = world.countries[world.tag]
                        action = ("close_" if stage == 1127 else "request_") + suffix
                        self.assertTrue(option_legal(world, event, action))
                        original_group = copy.deepcopy(group(world, "ig_trade_unions"))
                        original_movements = copy.deepcopy(state["movements"])

                        def change(lost):
                            if loss == "opposition":
                                ig = group(world, "ig_trade_unions")
                                ig.clear()
                                ig.update(dict(original_group, in_government=False, clout=.05, approval=-1)
                                          if lost else original_group)
                            else:
                                state["movements"][:] = (original_movements + [{
                                    "is_being_suppressed": True,
                                    "political_movement_radicalism": .25,
                                }] if lost else original_movements)

                        change(True)
                        self.assertTrue(current(world, "new_opposition_appeared" if loss == "opposition"
                                                else "new_suppressed_appeared"))
                        self.assertFalse(option_legal(world, event, action))
                        before = state_and_cash(world)
                        force_option(world, event, action)
                        self.assertEqual(state_and_cash(world), before)
                        self.assertEqual((state[P + "review_mature"], state[P + "review_streak"]), (1, 6))
                        self.assertEqual(state[P + "review_paid_amount"], 500 if limited else 1000)
                        if stage == 1127:
                            # A genuine cached full/finite request cannot close after loss.
                            # Restore only current facts: its original positive close is legal again.
                            change(False)
                            self.assertTrue(option_legal(world, event, action))
                            choose(world, arc, event, action)
                            self.assert_closed(world, 2 if limited else 1)
                            continue
                        self.assertTrue(option_legal(world, event, "request_setback"))
                        choose(world, arc, event, "request_setback")
                        final = native_deliver(world, arc, 1127)
                        self.assertTrue(option_legal(world, final, "close_setback"))
                        change(False)
                        self.assertFalse(option_legal(world, final, "close_setback"))
                        recovered = state_and_cash(world)
                        force_option(world, final, "close_setback")
                        self.assertEqual(state_and_cash(world), recovered)
                        change(True)
                        choose(world, arc, final, "close_setback")
                        self.assert_closed(world, 3)

    def test_genuine_school_does_not_adopt_school_price_duty_for_full_local_new_witness(self):
        world = school_world("cooperative")
        set_current(world, "local")
        arc = ready(world, "local", witness="new_professional_witness")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "petition_paid_amount"], 2000)
        month(world, arc, 6)
        before = cash(world)
        play(world, arc, 1125, "pay_review")
        self.assertEqual(before - cash(world), 1500)
        self.assertEqual((state[P + "witness_kind"], state[P + "review_paid_amount"]), (1, 1500))
        event = native_deliver(world, arc, 1126)
        self.assertTrue(option_legal(world, event, "request_full"))
        state["institutions"]["institution_schools"] = 0
        self.assertTrue(current(world, "selected_current_ready"))
        self.assertTrue(current(world, "witness_current_duty"))
        self.assertTrue(option_legal(world, event, "request_full"))
        self.assertFalse(option_legal(world, event, "request_setback"))
        self.assertNotEqual(state.get(P + "review_source_school"), 1)
        choose(world, arc, event, "request_full")
        play(world, arc, 1127, "close_full")
        self.assert_closed(world, 1)

    def test_genuine_written_history_does_not_adopt_written_duty_for_full_court_new_witness(self):
        world = revenue_world()
        set_current(world, "court")
        arc = ready(world, witness="new_professional_witness")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "petition_paid_amount"], 1000)
        month(world, arc, 6)
        before = cash(world)
        play(world, arc, 1125, "pay_review")
        self.assertEqual(before - cash(world), 1000)
        self.assertEqual((state[P + "witness_kind"], state[P + "review_paid_amount"]), (1, 1000))
        event = native_deliver(world, arc, 1126)
        self.assertTrue(option_legal(world, event, "request_full"))
        state["laws"] = [law for law in state["laws"]
                         if law not in ("law_proportional_taxation", "law_graduated_taxation")]
        state["laws"].append("law_land_based_taxation")
        self.assertTrue(current(world, "selected_current_ready"))
        self.assertTrue(current(world, "witness_current_duty"))
        self.assertTrue(option_legal(world, event, "request_full"))
        self.assertFalse(option_legal(world, event, "request_setback"))
        self.assertNotEqual(state.get(P + "petition_source_written_shares"), 1)
        choose(world, arc, event, "request_full")
        play(world, arc, 1127, "close_full")
        self.assert_closed(world, 1)

    def test_adopted_written_source_loss_blocks_actual_review_billing_without_fallback(self):
        world = revenue_world()
        arc = ready(world, "local", witness="new_professional_witness")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "petition_paid_amount"], 1000)
        self.assertEqual(state[P + "petition_source_written_shares"], 1)
        month(world, arc, 6)
        event = native_deliver(world, arc, 1125)
        self.assertTrue(option_legal(world, event, "pay_review"))
        investment = state["institutions"]["institution_schools"]
        state["institutions"]["institution_schools"] = 0
        self.assertTrue(current(world, "selected_current_ready"))
        self.assertTrue(current(world, "witness_current_duty"))
        self.assertFalse(current(world, "adopted_written_shares_current"))
        self.assertFalse(option_legal(world, event, "pay_review"))
        before = state_and_cash(world)
        force_option(world, event, "pay_review")
        self.assertEqual(state_and_cash(world), before)
        self.assertNotIn(P + "review_paid", state)
        self.assertEqual(state[P + "stage"], 1125)
        state["institutions"]["institution_schools"] = investment
        self.assertTrue(option_legal(world, event, "pay_review"))
        balance = cash(world)
        choose(world, arc, event, "pay_review")
        self.assertEqual(balance - cash(world), 1000)
        self.assertEqual((state[P + "review_paid_amount"], state[P + "stage"]), (1000, 1126))
        close_after_payment(world, arc)
        self.assert_closed(world, 1)


if __name__ == "__main__":
    unittest.main()

"""Real revenue option effects must reject stale event and receipt contexts."""
import copy
import unittest

from kor_partner_protocol_runtime import UnsupportedSubset
from test_v03_kor_provincial_revenue import new_world, revenue_arc, month
from test_v03_shu_provincial_contract import choose, force_option, option_legal

P = "ywc_kor_revenue_"
L = "ywc_v03_kor_v03_kor_provincial_revenue_"
RECEIPT = L + "last_event"
ACTIONS = {1100: "written_shares", 1101: "pay_charter", 1102: "settle_reviewer",
           1103: "sign", 1105: "review_responsibility", 1106: "verify", 1107: "request_full"}


def advance_real_event(world, arc, event, number):
    if number == 1104:
        if P + "review_paid" not in world.countries[world.tag]:
            choose(world, arc, event, "pay_review")
            event = world.deliver(arc, "ywc_kor.1104")
        choose(world, arc, event, "submit")
    else:
        choose(world, arc, event, ACTIONS[number])


def reach_real_event(number):
    world = new_world()
    arc = revenue_arc(world.cat)
    for current in range(1100, number + 1):
        if current == 1104:
            month(world, arc, 6)
        event = world.deliver(arc, f"ywc_kor.{current}")
        if current == number:
            return world, arc, event
        advance_real_event(world, arc, event, current)
    raise AssertionError(number)


def business_snapshot(world):
    return copy.deepcopy((world.countries, world.treasury, world.active, world.history))


class KorRevenueOptionReplay(unittest.TestCase):
    def test_withdraw_from_each_old_event_is_inert_after_real_progression(self):
        for number in range(1100, 1108):
            with self.subTest(event=number):
                world, arc, old_event = reach_real_event(number)
                self.assertTrue(option_legal(world, old_event, "withdraw"))
                advance_real_event(world, arc, old_event, number)
                self.assertFalse(option_legal(world, old_event, "withdraw"))
                before = business_snapshot(world)
                force_option(world, old_event, "withdraw")
                self.assertEqual(business_snapshot(world), before,
                                 "a stale option must not terminate the current stage")

    def test_withdraw_execution_rejects_wrong_receipt_and_missing_or_zero_phase(self):
        for number in range(1100, 1108):
            for corruption in ("receipt_zero", "receipt_other", "phase_missing", "phase_zero"):
                with self.subTest(event=number, corruption=corruption):
                    world, _, event = reach_real_event(number)
                    state = world.countries[world.tag]
                    self.assertTrue(option_legal(world, event, "withdraw"))
                    if corruption == "receipt_zero":
                        state[RECEIPT] = 0
                    elif corruption == "receipt_other":
                        state[RECEIPT] = 8 if number != 1107 else 1
                    elif corruption == "phase_missing":
                        state.pop(P + "phase")
                    else:
                        state[P + "phase"] = 0
                    before = business_snapshot(world)
                    try:
                        force_option(world, event, "withdraw")
                    except UnsupportedSubset:
                        # An absent native variable is deliberately strict in
                        # PartnerWorld. Rejection must still have no effects.
                        pass
                    self.assertEqual(business_snapshot(world), before,
                                     "an invalid context must not execute withdrawal")

    def test_current_withdraw_at_every_stage_releases_once_and_preserves_real_payments(self):
        for number in range(1100, 1108):
            with self.subTest(event=number):
                world, arc, event = reach_real_event(number)
                state = world.countries[world.tag]
                paid = {key: value for key, value in state.items()
                        if key.startswith(P) and (key.endswith("_paid") or key.endswith("_paid_amount"))}
                cash = dict(world.treasury)
                self.assertTrue(option_legal(world, event, "withdraw"))
                choose(world, arc, event, "withdraw")
                self.assertEqual(state[P + "outcome"], 4)
                self.assertEqual(state[L + "settled"], 1)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
                self.assertEqual(world.treasury, cash)
                self.assertEqual({key: state[key] for key in paid}, paid)
                settled = business_snapshot(world)
                force_option(world, event, "withdraw")
                world.run("ywc_kor_revenue_release_once", world.tag)
                self.assertEqual(business_snapshot(world), settled)


if __name__ == "__main__":
    unittest.main()

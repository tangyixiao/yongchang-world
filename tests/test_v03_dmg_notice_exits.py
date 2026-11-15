"""Real common-subjects notices retain response rights after scheduler ACK."""
import copy
import unittest

from test_v03_dmg_school_languages import new_world, play
from test_v03_shu_provincial_contract import choose, force_option, option_legal


BLOCKED_PLAN = ((1000, "common_qualification"), (1001, "first"),
                (1002, "reserved_posts"), (1003, "joint_hearing"),
                (1004, "first"), (1005, "first"), (1006, "common_qualification"),
                (1007, "first"), (1008, "first"))


def blocked_world():
    world = new_world()
    arc = next(a for a in world.cat["arcs"] if a["slug"] == "v03_dmg_common_subjects")
    for number, key in BLOCKED_PLAN:
        play(world, arc, number, key)
    return world, arc


class DmgCommonNoticeExits(unittest.TestCase):
    def test_real_opening_withdrawal_is_only_a_failed_terminal(self):
        world = new_world()
        arc = next(a for a in world.cat["arcs"] if a["slug"] == "v03_dmg_common_subjects")
        play(world, arc, 1000, "withdraw")
        state = world.countries[world.tag]
        self.assertEqual(world.history[world.tag][arc["journals"][0]["id"]], "failed")
        self.assertEqual(state["ywc_v03_dmg_v03_dmg_common_subjects_outcome"], 4)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))

    def test_real_twelve_month_notice_ack_keeps_repair_limited_and_withdraw_available(self):
        for key, outcome in (("continue_repair", None), ("limited_settlement", 5),
                             ("withdraw_breach", 4)):
            with self.subTest(key=key):
                world, arc = blocked_world()
                event = world.deliver(arc, "ywc_dmg.1009")
                state = world.countries[world.tag]
                self.assertNotIn("ywc_dmg_review_matured", state)
                self.assertNotIn("ywc_dmg_review_blocked_12_notice", state)
                self.assertNotIn("ywc_v03_dmg_inline_reservation", state)
                for available in ("continue_repair", "limited_settlement", "withdraw_breach"):
                    self.assertTrue(option_legal(world, event, available), available)
                before_cash = world.treasury[world.tag]
                choose(world, arc, event, key)
                self.assertEqual(world.treasury[world.tag], before_cash)
                if outcome is None:
                    self.assertNotIn("ywc_v03_dmg_v03_dmg_common_subjects_settled", state)
                    self.assertEqual(state["ywc_v03_active_arc_count"], 1)
                    self.assertIn("ywc_dmg_review_blocked_12_due", state)
                    before = copy.deepcopy((state, world.treasury))
                    for stale in ("continue_repair", "limited_settlement", "withdraw_breach"):
                        force_option(world, event, stale)
                    self.assertEqual((state, world.treasury), before)
                else:
                    self.assertEqual(state["ywc_v03_dmg_v03_dmg_common_subjects_outcome"], outcome)
                    self.assertEqual((state["ywc_v03_active_arc_count"],
                                      state["ywc_v03_visible_task_count"]), (0, 0))
                    before = copy.deepcopy((state, world.treasury))
                    for stale in ("continue_repair", "limited_settlement", "withdraw_breach"):
                        force_option(world, event, stale)
                    self.assertEqual((state, world.treasury), before)

    def test_real_thirty_six_month_notice_keeps_finite_exit_without_renewing_twelve(self):
        world, arc = blocked_world()
        state = world.countries[world.tag]
        for _ in range(4):
            event = world.deliver(arc, "ywc_dmg.1009")
            context = state.get("ywc_dmg_review_notice_response_context")
            if context == 36:
                break
            self.assertTrue(option_legal(world, event, "continue_repair"))
            choose(world, arc, event, "continue_repair")
        else:
            self.fail("actual blocked clock never delivered its 36-month response")
        self.assertFalse(option_legal(world, event, "continue_repair"))
        self.assertTrue(option_legal(world, event, "limited_settlement"))
        self.assertTrue(option_legal(world, event, "withdraw_breach"))
        choose(world, arc, event, "limited_settlement")
        self.assertEqual(state["ywc_v03_dmg_v03_dmg_common_subjects_outcome"], 5)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)


if __name__ == "__main__":
    unittest.main()

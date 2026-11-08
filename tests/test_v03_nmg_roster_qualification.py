"""Current qualification of a genuinely earned old NMG teaching roster.

The old office history is earned in the same source-interpreter world. The
current joint-school policy still needs half-staffed teaching capacity; reusing
its old bilingual officials must not silently select the fresh .8 academic hire.
"""
import copy
import unittest

from test_v03_nmg_parish_school import (
    L, P, cash, choose, deliver, employed_pop, finish_review, force_option,
    group, month, old_office_world, option_legal, play, ready_for_review,
    university,
)


CHOICE = "reuse_bilingual_roster"
HELPER = "ywc_nmg_school_reuse_roster"


def roster_popup():
    world = old_office_world(3, academics_occupancy=.5)
    arc = ready_for_review(world, number_through=1111)
    return world, arc, deliver(world, arc, 1112)


def current_loss(world, loss):
    state = world.countries["NMG"]
    if loss == "half_capacity":
        university(world)["occupancy"] = .49
    elif loss == "teaching_employee":
        employed_pop(world, "academics")["employed"] = False
    elif loss == "teaching_shortage":
        university(world)["shortage"] = True
    elif loss == "school_law":
        state["laws"].remove("law_public_schools")
        state["laws"].append("law_no_schools")
    elif loss == "civic_support":
        for kind in ("ig_intelligentsia", "ig_petty_bourgeoisie"):
            group(world, kind)["in_government"] = False
    elif loss == "income":
        state["net_fixed_income"] = -1
    else:
        raise AssertionError(loss)


def business_snapshot(world):
    return copy.deepcopy((world.countries, world.treasury, world.active,
                          world.history, world.modifiers))


LOSSES = ("half_capacity", "teaching_employee", "teaching_shortage",
          "school_law", "civic_support", "income")


class NmgRosterQualificationTests(unittest.TestCase):
    def test_roster_menu_rejects_below_half_but_keeps_the_earned_old_discount(self):
        world, _, event = roster_popup()
        state = world.countries["NMG"]
        self.assertEqual(state[P + "register_amount"], 500)
        self.assertTrue(option_legal(world, event, CHOICE))
        university(world)["occupancy"] = .49
        self.assertTrue(world.check_script(
            "ywc_nmg_school_prior_bilingual_contract = yes", "NMG"))
        self.assertFalse(option_legal(world, event, CHOICE))
        self.assertEqual(state[P + "register_amount"], 500)
        self.assertNotIn(P + "teacher_kind", state)

    def test_cached_roster_choice_rechecks_the_current_joint_policy(self):
        for loss in LOSSES:
            with self.subTest(loss=loss):
                world, _, event = roster_popup()
                self.assertTrue(option_legal(world, event, CHOICE))
                current_loss(world, loss)
                self.assertTrue(world.check_script(
                    "ywc_nmg_school_prior_bilingual_contract = yes", "NMG"))
                before = business_snapshot(world)
                force_option(world, event, CHOICE)
                self.assertEqual(business_snapshot(world), before)

    def test_direct_roster_helper_rechecks_the_current_joint_policy(self):
        for loss in LOSSES:
            with self.subTest(loss=loss):
                world, _, event = roster_popup()
                self.assertTrue(option_legal(world, event, CHOICE))
                current_loss(world, loss)
                before = business_snapshot(world)
                world.run(HELPER, "NMG")
                self.assertEqual(business_snapshot(world), before)

    def test_half_capacity_reuses_old_kind_three_and_completes_without_a_new_hire(self):
        world, arc, event = roster_popup()
        state = world.countries["NMG"]
        self.assertEqual(university(world)["occupancy"], .5)
        self.assertTrue(option_legal(world, event, CHOICE))
        self.assertFalse(option_legal(world, event, "hire_academic"))
        before = cash(world)
        choose(world, arc, event, CHOICE)
        self.assertEqual(cash(world), before)
        self.assertEqual(state[P + "teacher_kind"], 3)
        self.assertEqual(state[P + "stage"], 1113)
        for number, key in ((1113, "sign_curriculum"), (1114, "pay_wages"),
                            (1115, "audit_teaching_duties")):
            play(world, arc, number, key)
        month(world, arc, 6)
        finish_review(world, arc)
        self.assertEqual(state[P + "outcome"], 1)
        self.assertEqual(state[L + "settled"], 1)
        self.assertEqual(state[P + "teacher_kind"], 3)
        self.assertEqual(state[P + "register_amount"], 500)
        self.assertEqual(state[P + "wage_amount"], 1000)

    def test_rejected_roster_can_wait_then_restore_or_withdraw_without_new_cost(self):
        for recovery in ("restore", "withdraw"):
            with self.subTest(recovery=recovery):
                world, arc, event = roster_popup()
                state = world.countries["NMG"]
                before = cash(world)
                university(world)["occupancy"] = .49
                self.assertFalse(option_legal(world, event, CHOICE))
                choose(world, arc, event, "wait_and_defer")
                self.assertEqual(state[P + "stage"], 1112)
                self.assertNotIn(P + "teacher_kind", state)
                self.assertEqual(cash(world), before)
                if recovery == "restore":
                    university(world)["occupancy"] = .5
                    retry = deliver(world, arc, 1112)
                    choose(world, arc, retry, CHOICE)
                    self.assertEqual(state[P + "stage"], 1113)
                    self.assertEqual(state[P + "teacher_kind"], 3)
                else:
                    choose(world, arc, event, "withdraw")
                    self.assertEqual(state[P + "outcome"], 4)
                    self.assertEqual(state[L + "settled"], 1)
                    terminal = business_snapshot(world)
                    force_option(world, event, CHOICE)
                    world.run(HELPER, "NMG")
                    self.assertEqual(business_snapshot(world), terminal)
                self.assertEqual(cash(world), before)


if __name__ == "__main__":
    unittest.main()

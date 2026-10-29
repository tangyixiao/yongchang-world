"""Current peace and earned school/port qualifications remain live duties."""
import copy
import unittest

from test_v03_kor_provincial_revenue import (
    new_world, ready_for_review, month, play, P, choose, option_legal,
)
from test_v03_kor_revenue_cross_era import (
    history_world, earn_school, earn_ports, match_current_cash, revenue_open,
    native_play, native_month, native_deliver,
)
from test_v03_shu_provincial_contract import force_option


def snapshot(world):
    return copy.deepcopy((world.countries, world.treasury, world.active, world.history))


def earned_reviewer_world(kind, stage):
    world = history_world("provincial")
    if kind == "school":
        earn_school(world, "cooperative")
    else:
        earn_ports(world, "designated")
    match_current_cash(world)
    arc = revenue_open(world, "provincial")
    native_play(world, arc, 1102, "settle_reviewer")
    state = world.countries[world.tag]
    assert state[P + "reviewer"] == (1 if kind == "school" else 2)
    if stage >= 1105:
        native_play(world, arc, 1103, "sign")
        native_month(world, arc, 6)
        native_play(world, arc, 1104, "pay_review")
        native_play(world, arc, 1104, "submit")
        if stage == 1106:
            native_play(world, arc, 1105, "review_responsibility")
    event = native_deliver(world, arc, stage)
    return world, arc, event


def lose_actual_source_post(world, kind):
    building_type = "building_university" if kind == "school" else "building_port"
    for state in world.countries[world.tag]["states"]:
        for building in state["buildings"]:
            if building["type"] == building_type:
                building["occupancy"] = .79


class KorRevenueContractContinuity(unittest.TestCase):
    def assert_current_source_is_revalidated(self, world, arc, event, stage, kind, key):
        state = world.countries[world.tag]
        old_role = 1 if kind == "school" else 2
        self.assertEqual(state[P + "reviewer"], old_role)
        self.assertTrue(option_legal(world, event, key))
        lose_actual_source_post(world, kind)
        self.assertFalse(world.conditions(world.trigger_defs[P + "prior_" + kind], world.tag))
        # The new basic policy remains possible; only the claimed historical
        # reviewer has lost its current qualification.
        self.assertTrue(world.conditions(world.trigger_defs[P + "selected_current_ready"], world.tag))
        before = snapshot(world)
        if option_legal(world, event, key):
            choose(world, arc, event, key)
            self.assertEqual(state[P + "reviewer"], 4,
                             "advancement may use a new current reviewer, not stale school/port credit")
            self.assertEqual(state[P + "reviewer_pilot"], state[P + "pilot_state"])
            self.assertEqual(state[P + "stage"], stage + 1)
        else:
            force_option(world, event, key)
            self.assertEqual(snapshot(world), before,
                             "a blocked stale-source action must also reject cached execution")

    def test_war_interrupts_two_months_and_recovery_requires_a_fresh_explicit_restart(self):
        world = new_world()
        arc = ready_for_review(world)
        state = world.countries[world.tag]
        month(world, arc, 2)
        self.assertEqual(state[P + "review_streak"], 2)
        state["is_at_war"] = True
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        self.assertNotIn(P + "review_running", state)
        self.assertNotIn(P + "review_mature", state)
        self.assertEqual(state[P + "review_interrupted"], 1)
        state["is_at_war"] = False
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 0)
        event = world.deliver(arc, "ywc_kor.1104")
        choose(world, arc, event, "restart_review")
        world.pulse(arc)
        self.assertEqual(state[P + "review_streak"], 0)
        month(world, arc, 5)
        self.assertNotIn(P + "review_mature", state)
        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "review_mature"], 1)

    def test_full_final_choice_rejects_current_war_and_cached_setback_rejects_recovery(self):
        for route in ("provincial", "central", "project"):
            actual = new_world(route)
            arc = ready_for_review(actual, route)
            month(actual, arc, 6)
            play(actual, arc, 1104, "pay_review")
            play(actual, arc, 1104, "submit")
            play(actual, arc, 1105, "review_responsibility")
            play(actual, arc, 1106, "verify")
            event = actual.deliver(arc, "ywc_kor.1107")
            for loss in ("war", "default", "bankruptcy", "income"):
                with self.subTest(route=route, loss=loss):
                    # Reuse a genuinely earned paid/mature final context; only
                    # native present facts differ across these negative controls.
                    world = copy.deepcopy(actual)
                    state = world.countries[world.tag]
                    original_income = state["net_fixed_income"]
                    self.assertTrue(option_legal(world, event, "request_full"))
                    if loss == "war":
                        state["is_at_war"] = True
                    elif loss == "default":
                        state["in_default"] = True
                    elif loss == "income":
                        state["net_fixed_income"] = -1
                    else:
                        world.execute([("add_modifier", "=", [("name", "=", "declared_bankruptcy"),
                                                              ("months", "=", "12")])], world.tag)
                    self.assertFalse(option_legal(world, event, "request_full"))
                    self.assertTrue(option_legal(world, event, "request_setback"))
                    before = snapshot(world)
                    force_option(world, event, "request_full")
                    self.assertEqual(snapshot(world), before)
                    if loss == "war":
                        state["is_at_war"] = False
                    elif loss == "default":
                        state["in_default"] = False
                    elif loss == "income":
                        state["net_fixed_income"] = original_income
                    else:
                        world.execute([("remove_modifier", "=", "declared_bankruptcy")], world.tag)
                    self.assertFalse(option_legal(world, event, "request_setback"))
                    recovered = snapshot(world)
                    force_option(world, event, "request_setback")
                    self.assertEqual(snapshot(world), recovered)

    def test_sign_revalidates_genuinely_earned_school_and_port_reviewers(self):
        for kind in ("school", "ports"):
            with self.subTest(kind=kind):
                world, arc, event = earned_reviewer_world(kind, 1103)
                self.assert_current_source_is_revalidated(world, arc, event, 1103, kind, "sign")

    def test_late_responsibility_and_verification_revalidate_the_actual_old_source(self):
        for kind in ("school", "ports"):
            for stage, key in ((1105, "review_responsibility"), (1106, "verify")):
                with self.subTest(kind=kind, stage=stage):
                    world, arc, event = earned_reviewer_world(kind, stage)
                    self.assert_current_source_is_revalidated(world, arc, event, stage, kind, key)


if __name__ == "__main__":
    unittest.main()

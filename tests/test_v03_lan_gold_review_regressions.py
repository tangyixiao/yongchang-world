"""Independent real-source RED controls for the beyond-gold review findings.

The existing world loads the actual generated journals/events and authored
helpers. Payments, bounded choices, observation and settlement all execute
through those sources. Current occupancy and post-payment zero flags are
explicit counterfactual/fault inputs, never fabricated positive proof.
"""
import copy
import unittest

from test_v03_lan_beyond_gold import (
    P, choose, force_option, gold_arc, month, new_world, option_legal, play, reach_review,
    review_then_finish_event,
)
from test_v03_shu_provincial_contract import _option_effect, option_nodes
from shu_kor_strict_review_runtime import field


class LanGoldIndependentReviewRegressions(unittest.TestCase):
    def _assert_zero_paid_blocks_step(self, target, choice, paid, helper):
        for boundary in ("forced_option", "deep_helper"):
            world = new_world()
            arc = gold_arc()
            world.refresh(arc)
            for number, key in ((1120, "pay_seed"), (1121, "route_processing"),
                                (1122, "pay_basis"), (1123, "name_full")):
                if number == target:
                    break
                play(world, arc, number, key)
            event = world.deliver(arc, f"ywc_lan.{target}")
            state = world.countries[world.tag]
            self.assertEqual(state[P + paid + "_paid"], 1)
            self.assertEqual(state[P + paid + "_paid_amount"], 1000)
            self.assertEqual(world.treasury[world.tag], -1000 if target < 1123 else -2000)
            self.assertEqual(state[P + "stage"], target)
            self.assertTrue(option_legal(world, event, choice))

            if target == 1121 and boundary == "deep_helper":
                # The actual option supplies this argument immediately before
                # invoking choose_route. Execute only that authored argument
                # while payment is still valid, then fault the proof at the
                # helper boundary; no route/outcome/paid proof is invented.
                def walk(nodes):
                    for node in nodes:
                        yield node
                        if isinstance(node[2], list):
                            yield from walk(node[2])
                parameter = next(node for node in walk(_option_effect(option_nodes(event, choice)))
                                 if node[0] == "set_variable" and isinstance(node[2], list)
                                 and field(node[2], "name") == P + "route_choice")
                with world.popup_context(event):
                    world.execute([parameter], world.tag)
                self.assertEqual(state[P + "route_choice"], 1)

            state[P + paid + "_paid"] = 0
            if boundary == "forced_option":
                with self.subTest(event=target, boundary="current_option"):
                    self.assertFalse(option_legal(world, event, choice))
            before = copy.deepcopy((world.countries, world.treasury,
                                    world.modifiers, world.state_modifiers))
            if boundary == "forced_option":
                force_option(world, event, choice)
            else:
                with world.popup_context(event):
                    world.run(helper, world.tag)
            with self.subTest(event=target, boundary=boundary):
                self.assertEqual((world.countries, world.treasury,
                                  world.modifiers, world.state_modifiers), before,
                                 "zero paid proof must not charge or advance the real source")

    def test_zero_seed_payment_blocks_route_choice_and_deep_helper(self):
        self._assert_zero_paid_blocks_step(1121, "route_processing", "seed",
                                          "ywc_lan_gold_choose_route")

    def test_zero_seed_payment_blocks_basis_charge_and_deep_helper(self):
        self._assert_zero_paid_blocks_step(1122, "pay_basis", "seed",
                                          "ywc_lan_gold_pay_basis")

    def test_zero_basis_payment_blocks_responsibility_and_deep_helper(self):
        self._assert_zero_paid_blocks_step(1123, "name_full", "basis",
                                          "ywc_lan_gold_record_responsible")

    def test_zero_basis_payment_blocks_audit_start_and_deep_helper(self):
        self._assert_zero_paid_blocks_step(1124, "start_audit", "basis",
                                          "ywc_lan_gold_start_review")

    def _assert_zero_paid_cannot_settle(self, kind, predicate):
        world = new_world()
        arc = reach_review(world, "processing")
        state = world.countries[world.tag]
        self.assertEqual(state[P + "seed_paid"], 1)
        self.assertEqual(state[P + "basis_paid"], 1)
        self.assertEqual(state[P + "seed_paid_amount"], 1000)
        self.assertEqual(state[P + "basis_paid_amount"], 1000)
        self.assertEqual(world.treasury[world.tag], -2000)
        month(world, arc, 6)
        finish = review_then_finish_event(world, arc)
        self.assertTrue(world.condition((predicate, "=", "yes"), world.tag))
        self.assertTrue(option_legal(world, finish, "settle_established"))

        # Real source earned both positive receipts above. This explicit
        # representation fault must not remain positive payment evidence.
        state[P + kind + "_paid"] = 0
        with self.subTest(boundary="payment_proof"):
            self.assertFalse(world.condition((predicate, "=", "yes"), world.tag),
                             "a present zero paid flag cannot authorize settlement")
        with self.subTest(boundary="current_option"):
            self.assertFalse(option_legal(world, finish, "settle_established"))
        before = copy.deepcopy((world.countries, world.treasury,
                                world.modifiers, world.state_modifiers))
        force_option(world, finish, "settle_established")
        with self.subTest(boundary="forced_option"):
            self.assertEqual((world.countries, world.treasury,
                              world.modifiers, world.state_modifiers), before,
                             "the actual terminal helper must reject the zero proof")

    def test_real_seed_payment_zero_flag_cannot_authorize_settlement(self):
        self._assert_zero_paid_cannot_settle("seed", "ywc_lan_gold_seed_ready")

    def test_real_basis_payment_zero_flag_cannot_authorize_settlement(self):
        self._assert_zero_paid_cannot_settle("basis", "ywc_lan_gold_basis_ready")

    def test_bounded_processing_observes_real_sub_level_workplace(self):
        world = new_world()
        arc = reach_review(world, "processing", bounded=True)
        state = world.countries[world.tag]
        self.assertEqual(state[P + "seed_paid_amount"], 1000)
        self.assertEqual(state[P + "basis_paid_amount"], 1000)
        self.assertEqual(world.treasury[world.tag], -2000)
        self.assertEqual(state[P + "bounded"], 1)

        # Change a real current fact in the original captured pilot. Its
        # employed worker still points to this same food-industry building.
        pilot = state["states"][0]
        food = next(building for building in pilot["buildings"]
                    if building["type"] == "building_food_industry")
        food["occupancy"] = .5
        self.assertTrue(any(pop.get("employed") and pop.get("workplace") is food
                            for pop in pilot["pops"]))
        self.assertTrue(world.condition(("ywc_lan_gold_processing_sub", "=", "yes"), world.tag))
        self.assertFalse(world.condition(("ywc_lan_gold_processing_plus", "=", "yes"), world.tag))

        month(world, arc)
        self.assertEqual(state[P + "review_streak"], 1,
                         "the bounded audit must accept its real sub-level production")
        self.assertNotIn(P + "observation_interrupted", state)
        month(world, arc, 5)
        self.assertEqual(state[P + "review_streak"], 6)
        self.assertEqual(state[P + "observation_done"], 1)

    def test_real_compromise_applies_defined_country_and_pilot_modifiers(self):
        world = new_world()
        arc = reach_review(world, "processing", bounded=True)
        state = world.countries[world.tag]
        month(world, arc, 6)
        finish = review_then_finish_event(world, arc)
        self.assertTrue(option_legal(world, finish, "settle_compromise"))
        choose(world, arc, finish, "settle_compromise")
        self.assertEqual(state[P + "outcome"], 2)
        self.assertEqual(state["ywc_v03_lan_v03_lan_beyond_gold_settled"], 1)

        applied = [fields for tag, fields in world.modifiers if tag == world.tag]
        undefined = [fields.get("name") for fields in applied
                     if fields.get("name", "").startswith(P)
                     and fields["name"] not in world.modifier_defs]
        self.assertEqual(undefined, [],
                         "real settlement must not apply an undefined modifier ID")
        self.assertTrue(any(fields.get("name") == "ywc_lan_gold_compromise_country"
                            and str(fields.get("days")) == "730" for fields in applied))
        pilot = state[P + "pilot_state"]
        modifier = world.state_modifiers[(pilot, "ywc_lan_gold_compromise_state")]
        self.assertEqual(str(modifier["fields"]["days"]), "730")


if __name__ == "__main__":
    unittest.main()

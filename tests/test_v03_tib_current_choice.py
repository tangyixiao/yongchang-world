"""TIB opening payments execute against their current native qualification.

Worlds enter actual authored journals and receive real source popups. The
strict native business projection omits inline transport; physical generated
option effects are checked separately for parity with the interpreted bodies.
"""
import copy
from pathlib import Path
import unittest

from clausewitz_harness import parse
import test_v03_tib_foundation_lifecycle as tib_lifecycle


field = tib_lifecycle.field


ROOT = Path(__file__).resolve().parents[1]
SLUGS = {"register": "v03_tib_service_register",
         "grain": "v03_tib_grain_credit", "schools": "v03_tib_shared_schools"}
OPENING = {"register": 1000, "grain": 1010, "schools": 1020}
PRICES = {"register": (200, 150, 75), "grain": (200, 150, 300),
          "schools": (200, 150, 75)}


def option(event, key):
    return next(body for name, _, body in event if name == "option"
                and field(body, "name").endswith("." + key))


def executable(nodes):
    return [node for node in nodes if node[0] not in
            ("name", "trigger", "ai_chance", "custom_tooltip", "default_option")]


def snapshot(world, *, ignore_pending=None):
    state = copy.deepcopy(world.countries)
    if ignore_pending is not None:
        state["TIB"].pop(f"ywc_tib_{ignore_pending}_pending_event", None)
    return (state, copy.deepcopy(world.treasury), copy.deepcopy(world.modifiers),
            copy.deepcopy(world.active), copy.deepcopy(world.history))


def lose_current_fact(world, pre):
    state = world.countries["TIB"]
    if pre == "register":
        state["laws"].difference_update({"law_serfdom", "law_tenant_farmers"})
        state["laws"].add("law_homesteading")
    elif pre == "grain":
        state["states"][0]["buildings"] = []
    else:
        state["laws"].difference_update({"law_religious_schools", "law_public_schools",
                                         "law_private_schools"})
        state["laws"].add("law_no_schools")


class TibCurrentChoiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tib_lifecycle.TibStrictLifecycleTest.setUpClass()
        cls.driver = tib_lifecycle.TibStrictLifecycleTest()

    def opening(self, pre, route):
        arc = self.driver.arcs[SLUGS[pre]]
        world = self.driver.world(pre, route, 5000)
        state = world.countries["TIB"]
        # The old route3 unit recipe has both alternate land laws. Keep one
        # actual legal law in every positive world; no business state is added.
        if pre == "register" and route == 3:
            state["laws"].discard("law_serfdom")
        self.assertLessEqual(len(state["laws"] & {"law_serfdom", "law_tenant_farmers",
                                                   "law_homesteading"}), 1)
        self.driver.entry(arc, world)
        event = self.driver.deliver(world, arc, f"ywc_tib.{OPENING[pre]}")
        self.assertTrue(world.conditions(field(option(event, f"route_{route}"), "trigger"),
                                         "TIB"))
        return world, arc, event

    @staticmethod
    def invoke(world, event, pre, route, entry):
        if entry == "option":
            world.execute(executable(option(event, f"route_{route}")), "TIB")
        else:
            world.run(f"ywc_tib_choose_{pre}_{route}", "TIB")

    def assert_unpaid(self, world, pre, before):
        state = world.countries["TIB"]
        self.assertEqual(snapshot(world, ignore_pending=pre), before)
        self.assertNotIn(f"ywc_tib_{pre}_paid", state)
        self.assertNotIn(f"ywc_tib_{pre}_route", state)
        self.assertNotIn(f"ywc_tib_{pre}_stage", state)
        self.assertIn(state.get(f"ywc_tib_{pre}_pending_event"), (None, OPENING[pre]))

    def test_all_nine_legal_openings_keep_their_actual_price_and_pay_once(self):
        for pre in SLUGS:
            for route, expected in enumerate(PRICES[pre], 1):
                with self.subTest(pre=pre, route=route):
                    world, arc, event = self.opening(pre, route)
                    state = world.countries["TIB"]
                    self.assertEqual(state[f"ywc_tib_{pre}_route_cost_{route}"], expected)
                    self.driver.choose(world, arc, event, f"route_{route}")
                    self.assertEqual(world.treasury["TIB"], -expected)
                    self.assertEqual(state[f"ywc_tib_{pre}_paid"], 1)
                    self.assertEqual(state[f"ywc_tib_{pre}_route"], route)
                    self.assertEqual(state[f"ywc_tib_{pre}_pending_event"], OPENING[pre] + 1)
                    paid = snapshot(world)
                    self.invoke(world, event, pre, route, "option")
                    self.invoke(world, event, pre, route, "helper")
                    self.assertEqual(snapshot(world), paid)

    def test_all_nine_cached_options_and_helpers_reject_lost_current_qualification(self):
        for pre in SLUGS:
            for route in (1, 2, 3):
                for entry in ("option", "helper"):
                    with self.subTest(pre=pre, route=route, entry=entry):
                        world, _, event = self.opening(pre, route)
                        lose_current_fact(world, pre)
                        self.assertFalse(world.conditions(field(option(event, f"route_{route}"),
                                                                "trigger"), "TIB"))
                        before = snapshot(world, ignore_pending=pre)
                        self.invoke(world, event, pre, route, entry)
                        self.assert_unpaid(world, pre, before)

    def test_current_qualification_can_restore_and_retry_without_a_lost_fee(self):
        for pre in SLUGS:
            for route in (1, 2, 3):
                with self.subTest(pre=pre, route=route):
                    world, arc, event = self.opening(pre, route)
                    state = world.countries["TIB"]
                    facts = copy.deepcopy((state["laws"], state["states"]))
                    lose_current_fact(world, pre)
                    self.invoke(world, event, pre, route, "option")
                    self.assertEqual(world.treasury["TIB"], 0)
                    state["laws"], state["states"] = facts
                    retry = self.driver.deliver(world, arc, f"ywc_tib.{OPENING[pre]}")
                    self.driver.choose(world, arc, retry, f"route_{route}")
                    self.assertEqual(world.treasury["TIB"], -PRICES[pre][route - 1])
                    self.assertEqual(state[f"ywc_tib_{pre}_route"], route)

    def test_absent_zero_or_negative_captured_price_cannot_grant_payment_or_income(self):
        for pre in SLUGS:
            for route in (1, 2, 3):
                for bad in (None, 0, -1):
                    for entry in ("option", "helper"):
                        with self.subTest(pre=pre, route=route, cost=bad, entry=entry):
                            world, _, event = self.opening(pre, route)
                            state = world.countries["TIB"]
                            fee = f"ywc_tib_{pre}_route_cost_{route}"
                            if bad is None:
                                del state[fee]
                            else:
                                state[fee] = bad
                            before = snapshot(world, ignore_pending=pre)
                            try:
                                self.invoke(world, event, pre, route, entry)
                            except AssertionError as exc:
                                self.fail(f"source must refuse the unavailable price before reading it: {exc}")
                            self.assert_unpaid(world, pre, before)

    def test_real_withdrawal_rejects_held_opening_without_payment_or_revival(self):
        for pre in SLUGS:
            for route in (1, 2, 3):
                for entry in ("option", "helper"):
                    with self.subTest(pre=pre, route=route, entry=entry):
                        world, arc, event = self.opening(pre, route)
                        self.driver.choose(world, arc, event, "withdraw")
                        state = world.countries["TIB"]
                        self.assertEqual(state[f"ywc_v03_tib_{SLUGS[pre]}_outcome"], 4)
                        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
                        before = snapshot(world)
                        self.invoke(world, event, pre, route, entry)
                        self.assertEqual(snapshot(world), before)

    def test_paid_held_opening_cannot_rewind_a_later_earned_normal_queue(self):
        for pre in SLUGS:
            for route in (1, 2, 3):
                for entry in ("option", "helper"):
                    with self.subTest(pre=pre, route=route, entry=entry):
                        world, arc, event = self.opening(pre, route)
                        self.driver.choose(world, arc, event, f"route_{route}")
                        next_event = self.driver.deliver(world, arc,
                                                         f"ywc_tib.{OPENING[pre] + 1}")
                        self.driver.choose(world, arc, next_event, "review_next")
                        state = world.countries["TIB"]
                        self.assertEqual(state[f"ywc_tib_{pre}_pending_event"], OPENING[pre] + 2)
                        before = snapshot(world)
                        self.invoke(world, event, pre, route, entry)
                        self.assertEqual(snapshot(world), before)

    def test_actual_cash_default_and_bankruptcy_loss_still_rejects_without_progress(self):
        for pre in SLUGS:
            for loss in ("cash", "default", "bankruptcy"):
                with self.subTest(pre=pre, loss=loss):
                    world, _, event = self.opening(pre, 1)
                    state = world.countries["TIB"]
                    if loss == "cash":
                        state["gold_reserves"] = 0
                    elif loss == "default":
                        state["in_default"] = True
                    else:
                        world.modifiers.append(("TIB", {"modifier": "declared_bankruptcy"}))
                    before = snapshot(world, ignore_pending=pre)
                    self.invoke(world, event, pre, 1, "option")
                    self.assert_unpaid(world, pre, before)

    def test_nine_physical_option_effects_equal_the_interpreted_native_source(self):
        physical = {key: body for key, _, body in parse((ROOT /
                    "yongchang_world/events/ywc_v03_country_tib_events.txt")
                    .read_text(encoding="utf-8-sig"))}
        for pre in SLUGS:
            event_id = f"ywc_tib.{OPENING[pre]}"
            for route in (1, 2, 3):
                with self.subTest(pre=pre, route=route):
                    self.assertEqual(executable(option(physical[event_id], f"route_{route}")),
                                     executable(option(self.driver.events[event_id],
                                                       f"route_{route}")))


if __name__ == "__main__":
    unittest.main()

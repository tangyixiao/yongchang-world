"""MGL paid-obligation loss and qualification-window contracts.

All business state in these cases is created by the formal source. Only ordinary
world facts (laws, jobs, market and country relationships) change as fixtures.
"""
from __future__ import annotations

import unittest

from tests.test_v03_mgl_actual_source import (
    MGL_ARCS, PREFIX, TAG, _block, actual_mgl_admission_world,
    choose_actual_option, pulse_actual_journals,
)


def _advance_all_live_journals(world, target_ids=()):
    """Pulse every live MGL JE and handle any non-target event by legal source choice."""
    event_id = pulse_actual_journals(world)
    if event_id is None or event_id in target_ids:
        return event_id
    number = int(event_id.rsplit(".", 1)[1])
    suffix = {0: "dual", 1: "review", 3: "clarify", 5: "review", 6: "defer", 7: "defer"}.get(number % 10)
    if number % 10 in (2, 4):
        suffix = next((name for name in ("dual_terms", "arbitration_terms", "joint_terms")
                       if any(_block(option, "name").endswith("." + name)
                              for key, _, option in world.event_defs[event_id] if key == "option")), None)
    if suffix is None:
        raise AssertionError((event_id, "no authored transition selected for event"))
    choose_actual_option(world, event_id, suffix)
    return None


def _pulse(world, arc):
    target_ids = {entry["id"] for entry in arc["events"]}
    return _advance_all_live_journals(world, target_ids)


def _pulse_until_quiet(world, limit=20):
    """Run real all-live-JE pulses, resolving each emitted event legally."""
    for _ in range(limit):
        event_id = _advance_all_live_journals(world, set())
        if event_id is None:
            return
    raise AssertionError("native event queue did not reach a quiet source pulse")


def _choose_normal_wait(world, arc, event_id):
    """Take a real legal nonterminal choice while preserving the selected route."""
    if event_id in {arc["events"][6]["id"], arc["events"][7]["id"]}:
        choose_actual_option(world, event_id, "defer")
    elif event_id == arc["events"][1]["id"]:
        choose_actual_option(world, event_id, "review")
    else:
        choose_actual_option(world, event_id, "defer")


class MglObligationLossWindowsTests(unittest.TestCase):
    def _paid_route1(self, slug):
        world, evidence = actual_mgl_admission_world()
        arc = next(a for a in MGL_ARCS if a["slug"] == slug)
        prefix = PREFIX[slug]
        initial = arc["events"][0]["id"]
        # All three live root JEs pulse; other events advance through legal
        # authored choices until the selected arc's entry offer is delivered.
        for _ in range(24):
            event_id = _advance_all_live_journals(world, {initial})
            if event_id == initial:
                break
        self.assertEqual(event_id, initial)
        choose_actual_option(world, initial, "dual")
        self.assertEqual(world.countries[TAG][f"ywc_mgl_{prefix}_route_paid"], 1)
        self.assertEqual(world.countries[TAG][f"ywc_mgl_{prefix}_route"], 1)
        return world, arc, prefix, evidence

    def _paid_route(self, slug, suffix):
        world, evidence = actual_mgl_admission_world()
        arc = next(a for a in MGL_ARCS if a["slug"] == slug)
        prefix = PREFIX[slug]
        initial = arc["events"][0]["id"]
        for _ in range(24):
            event_id = _advance_all_live_journals(world, {initial})
            if event_id == initial:
                break
        self.assertEqual(event_id, initial)
        choose_actual_option(world, arc["events"][0]["id"], suffix)
        self.assertEqual(world.countries[TAG][f"ywc_mgl_{prefix}_route_paid"], 1)
        return world, arc, prefix, evidence

    def _wait_monthly_notice(self, world, arc, notice_event, limit=70):
        event_id = None
        for _ in range(limit):
            event_id = _pulse(world, arc)
            if event_id == notice_event:
                return event_id
            if event_id is not None:
                _choose_normal_wait(world, arc, event_id)
        return event_id

    def test_paid_36_month_notice_is_independently_delivered_by_live_source(self):
        world, arc, prefix, evidence = self._paid_route1("v03_mgl_pastoral_debt")
        state = world.countries[TAG]
        state["states"][0]["pops"][0]["employed"] = False
        self.assertIsNone(_pulse(world, arc))
        loss_day = world.calendar_day
        timer_key = f"ywc_mgl_{prefix}_blocked_36_due"
        self.assertIn(timer_key, state)
        # Keep the 12-month notice from consuming the shared major-event slot;
        # its actual native option is legally deferred when it arrives.
        event_id = self._wait_monthly_notice(world, arc, arc["events"][6]["id"], 30)
        self.assertEqual(event_id, arc["events"][6]["id"])
        choose_actual_option(world, event_id, "defer")
        event_id = self._wait_monthly_notice(world, arc, arc["events"][7]["id"], 80)
        self.assertEqual(event_id, arc["events"][7]["id"])
        self.assertGreaterEqual(world.calendar_day - loss_day, 1095,
                                "monthly source stepping may deliver after expiry, never before 1095 days")
        self.assertNotIn(timer_key, state, "the source 1095-day timer must be expired at actual delivery")
        self.assertNotIn(f"ywc_mgl_{prefix}_blocked_36_due", state,
                         "the actual source timer must have expired before notice delivery")
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_36_sent"], 1)
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})

    def test_unpaid_no_affordable_legal_offer_starts_real_early_notice_epoch(self):
        world, evidence = actual_mgl_admission_world()
        arc = next(a for a in MGL_ARCS if a["slug"] == "v03_mgl_pastoral_debt")
        prefix = PREFIX[arc["slug"]]
        # Ordinary market facts remove the authored debt entry predicate for
        # every route. No payment, route, term, or clock state is supplied.
        world.countries[TAG]["market"]["wool"]["exports"] = 0
        state = world.countries[TAG]
        self.assertIsNone(_pulse(world, arc))
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_12_started"], 1)
        self.assertNotIn(f"ywc_mgl_{prefix}_route_paid", state)
        self.assertNotIn(f"ywc_mgl_{prefix}_route", state)
        event_id = self._wait_monthly_notice(world, arc, arc["events"][6]["id"], 60)
        self.assertEqual(event_id, arc["events"][6]["id"])
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})

    def test_paid_local_route_does_not_inherit_entry_ranch_worker_requirement(self):
        world, arc, prefix, _ = self._paid_route("v03_mgl_pastoral_debt", "local")
        state = world.countries[TAG]
        pop = state["states"][0]["pops"][0]
        self.assertEqual(state[f"ywc_mgl_{prefix}_route"], 3)
        self.assertEqual(state[f"ywc_mgl_{prefix}_route_paid"], 1)
        pop["employed"] = False
        self.assertIsNone(_pulse(world, arc))
        self.assertNotIn(f"ywc_mgl_{prefix}_blocked_12_due", state,
                         "route-3 local execution has no current ranch-worker gate")

    def test_roads_late_loss_after_real_terms_resets_watch_and_fresh_six_month_boundary(self):
        # Roads is the approved path whose strict native queue reaches node 4
        # before terms; missing terms on the other arcs do not suppress it.
        world, evidence = actual_mgl_admission_world()
        arc = next(a for a in MGL_ARCS if a["slug"] == "v03_mgl_two_trade_roads")
        state = world.countries[TAG]
        event_id = None
        target_ids = {entry["id"] for entry in arc["events"][:6]}
        for _ in range(90):
            event_id = _advance_all_live_journals(world, target_ids)
            if event_id is None:
                continue
            number = int(event_id.rsplit(".", 1)[1])
            if event_id in {entry["id"] for entry in arc["events"]}:
                suffix = {1000: "dual", 1001: "review", 1002: "dual_terms",
                          1003: "clarify", 1004: "dual_terms", 1005: "review"}.get(number)
                self.assertIsNotNone(suffix, event_id)
                choose_actual_option(world, event_id, suffix)
            else:
                _choose_normal_wait(world, arc, event_id)
            if state.get("ywc_mgl_roads_terms_committed") == 1:
                break
        self.assertEqual(state.get("ywc_mgl_roads_route"), 1)
        self.assertEqual(state.get("ywc_mgl_roads_terms_committed"), 1)
        self.assertEqual(state.get("ywc_mgl_roads_node_2_route_read"), 1)
        self.assertEqual(state.get("ywc_mgl_roads_node_4_route_read"), 1)

        # One actual live JE pulse starts the authored observation watch.
        _pulse_until_quiet(world)
        self.assertEqual(world.months_until_expiry[TAG].get("ywc_mgl_roads_full_timer"), 6)
        state["states"][0]["market_access"] = 0.70
        _pulse_until_quiet(world)
        self.assertNotIn("ywc_mgl_roads_full_timer", world.months_until_expiry[TAG])
        self.assertEqual(state.get("ywc_mgl_roads_blocked_12_started"), 1)

        # Restore ordinary access. The live source review starts a genuinely
        # fresh six-month source timer. This content authors months, so the
        # exact harness boundary is month 5 versus month 6, not a fabricated
        # day-based 179/180 timer.
        state["states"][0]["market_access"] = 0.80
        _pulse_until_quiet(world)
        timer = "ywc_mgl_roads_full_timer"
        self.assertEqual(world.months_until_expiry[TAG].get(timer), 6)
        roads_je = world.journal_defs[arc["journals"][1]["id"]]
        monthly = _block(roads_je, "on_monthly_pulse")
        body = _block(monthly, "effect")
        world.advance_months(5)
        world.execute(body, TAG)
        self.assertEqual(world.months_until_expiry[TAG].get(timer), 1)
        self.assertNotIn("ywc_mgl_roads_full_mature", state)
        world.advance_months(1)
        world.execute(body, TAG)
        self.assertEqual(state.get("ywc_mgl_roads_full_mature"), 1)
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})

    def test_actual_route2_single_uses_its_own_law_and_sol_contract(self):
        from tests.test_v03_mgl_actual_source import _ordinary_facts

        facts = _ordinary_facts()
        facts["laws"].discard("law_tenant_farmers")
        facts["laws"].discard("law_serfdom")
        facts["laws"].add("law_homesteading")
        facts["states"][0]["average_sol"] = 8
        facts["states"][0]["market_access"] = 0.50
        facts["market"]["tea"]["exports"] = 1
        facts["relations"] = {"SHU": 0, "RUS": -10}
        facts["market"]["grain"]["pricier"] = 0.18
        facts["military_expenses_share"] = 0
        world, evidence = actual_mgl_admission_world(
            admission_order=["v03_mgl_pastoral_debt", "v03_mgl_two_trade_roads",
                            "v03_mgl_princes_monasteries"],
            ordinary_facts=facts,
        )
        state = world.countries[TAG]
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})
        initial = next(a for a in MGL_ARCS if a["slug"] == "v03_mgl_pastoral_debt")["events"][0]["id"]
        for _ in range(60):
            event_id = pulse_actual_journals(world)
            if event_id == initial:
                choose_actual_option(world, event_id, "single")
                break
            if event_id is not None:
                # These are still unpaid entry cards on the other live arcs.
                choose_actual_option(world, event_id, "defer")
        else:
            self.fail("actual legal debt route-2 offer did not arrive")
        self.assertEqual(state["states"][0]["average_sol"], 8,
                         "the authored entry SoL<10 fact is true at payment time")
        self.assertEqual(state.get("ywc_mgl_debt_route_paid"), 1)
        self.assertEqual(state.get("ywc_mgl_debt_route"), 2)
        self.assertNotIn("ywc_mgl_debt_node_2_route_read", state,
                         "payment alone must not fabricate the later route-read choice")
        self.assertTrue(world.condition(("ywc_mgl_debt_entry_2_ready", "=", "yes"), TAG))
        state["states"][0]["average_sol"] = 10
        self.assertFalse(world.condition(("ywc_mgl_debt_entry_2_ready", "=", "yes"), TAG),
                         "the entry SoL<10 predicate must fail after the ordinary post-payment recovery")
        self.assertFalse(world.condition(("ywc_mgl_debt_entry_1_ready", "=", "yes"), TAG),
                         "Homesteading keeps this distinct from route 1's Tenant Farmers entry contract")
        self.assertIn("law_homesteading", state["laws"])
        # Route 2's execution facts remain satisfied, while strict readiness
        # correctly remains term-gated until the actual later node-4 choice.
        self.assertTrue(state["states"][0]["pops"][0]["employed"])
        self.assertGreater(state["market"]["wool"]["exports"], 0)
        self.assertFalse(world.condition(("ywc_mgl_debt_one_ready", "=", "yes"), TAG))
        self.assertFalse(world.condition(("ywc_mgl_debt_full_ready", "=", "yes"), TAG))
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})

    def test_paid_early_loss_ages_from_real_loss_and_survives_terms_wait(self):
        # Employment is a real route-1 requirement in the authored debt contract.
        world, arc, prefix, evidence = self._paid_route1("v03_mgl_pastoral_debt")
        state = world.countries[TAG]
        state["states"][0]["pops"][0]["employed"] = False

        # First live JE pulse observes the loss and starts both authored clocks.
        self.assertIsNone(_pulse(world, arc))
        loss_day = world.calendar_day
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_12_started"], 1)
        world.advance_days(90)
        event_id = _pulse(world, arc)
        if event_id is not None:
            _choose_normal_wait(world, arc, event_id)
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_12_started"], 1)
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_36_started"], 1)
        self.assertIn(f"ywc_mgl_{prefix}_blocked_12_due", state)
        self.assertIn(f"ywc_mgl_{prefix}_blocked_36_due", state)
        self.assertNotIn(f"ywc_mgl_{prefix}_terms_committed", state)
        self.assertNotIn(f"ywc_mgl_{prefix}_blocked_12_notice_event", state)

        # The actual notice can only be emitted on a monthly source pulse.
        # A pulse may cross the exact expiry by up to one month, so check the
        # actual post-pulse timer and elapsed source days, not pre-pulse age.
        timer_key = f"ywc_mgl_{prefix}_blocked_12_due"
        event_id = None
        for _ in range(60):
            event_id = _pulse(world, arc)
            if event_id in {arc["events"][6]["id"], arc["events"][7]["id"]}:
                break
            if event_id is not None:
                _choose_normal_wait(world, arc, event_id)
        self.assertEqual(event_id, arc["events"][6]["id"])
        self.assertGreaterEqual(world.calendar_day - loss_day, 365)
        self.assertNotIn(timer_key, state, "the monthly pulse must observe the source timer already expired")
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})

    def test_recovered_qualification_clears_old_epoch_then_fresh_loss_restarts(self):
        world, arc, prefix, _ = self._paid_route1("v03_mgl_pastoral_debt")
        state = world.countries[TAG]
        pop = state["states"][0]["pops"][0]
        pop["employed"] = False
        self.assertIsNone(_pulse(world, arc))
        world.advance_days(90)
        event_id = _pulse(world, arc)
        if event_id is not None:
            _choose_normal_wait(world, arc, event_id)
        world.advance_days(200)
        pop["employed"] = True
        event_id = _pulse(world, arc)
        if event_id is not None:
            _choose_normal_wait(world, arc, event_id)
        for suffix in ("12_due", "36_due", "12_started", "36_started", "12_sent", "36_sent",
                       "12_notice_event", "36_notice_event"):
            self.assertNotIn(f"ywc_mgl_{prefix}_blocked_{suffix}", state,
                             "actual recovery must clear only stale blocked epoch state")
        self.assertEqual(state[f"ywc_mgl_{prefix}_route_paid"], 1)
        self.assertEqual(state[f"ywc_mgl_{prefix}_route"], 1)
        self.assertNotIn(f"ywc_mgl_{prefix}_terms_committed", state)

        pop["employed"] = False
        event_id = _pulse(world, arc)
        if event_id is not None:
            _choose_normal_wait(world, arc, event_id)
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_12_started"], 1)
        self.assertEqual(state[f"ywc_mgl_{prefix}_blocked_36_started"], 1)
        timer_key = f"ywc_mgl_{prefix}_blocked_12_due"
        remaining = world.days_until_expiry[TAG].get(timer_key)
        self.assertIsNotNone(remaining, "second loss did not create a fresh 365-day timer")
        second_loss_day = world.calendar_day
        event_id = None
        for _ in range(24):
            event_id = _pulse(world, arc)
            if event_id in {arc["events"][6]["id"], arc["events"][7]["id"]}:
                break
            if event_id is not None:
                _choose_normal_wait(world, arc, event_id)
        if event_id not in {arc["events"][6]["id"], arc["events"][7]["id"]}:
            for _ in range(12):
                event_id = _pulse(world, arc)
                if event_id in {arc["events"][6]["id"], arc["events"][7]["id"]}:
                    break
                if event_id is not None:
                    _choose_normal_wait(world, arc, event_id)
        self.assertEqual(event_id, arc["events"][6]["id"])
        self.assertGreaterEqual(world.calendar_day - second_loss_day, 365)
        self.assertNotIn(timer_key, state)


if __name__ == "__main__":
    unittest.main()

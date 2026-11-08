"""Permanent source-only contracts for MGL queue waiting and paid progression."""
from itertools import permutations
import unittest

from tests.test_v03_mgl_actual_source import (
    TAG, MGL_ARCS, PREFIX, actual_mgl_admission_world, pulse_actual_journals,
    choose_actual_option,
)
from tests.test_v03_mgl_actual_source import _ordinary_facts

ARCS = {arc["slug"]: arc for arc in MGL_ARCS}
SLUGS = tuple(ARCS)
EVENT_SUFFIX = {
    1000: ("dual", 1), 1001: ("review", 2), 1002: ("dual_terms", 3),
    1003: ("clarify", 4), 1004: ("dual_terms", 5), 1005: ("review", 6),
    1010: ("dual", 1), 1011: ("review", 2), 1012: ("arbitration_terms", 3),
    1013: ("clarify", 4), 1014: ("arbitration_terms", 5), 1015: ("review", 6),
    1020: ("dual", 1), 1021: ("review", 2), 1022: ("joint_terms", 3),
    1023: ("clarify", 4), 1024: ("joint_terms", 5), 1025: ("review", 6),
}
ROUTE2_SUFFIX = {
    1000: ("single", 1), 1001: ("review", 2), 1002: ("single_terms", 3),
    1003: ("clarify", 4), 1004: ("single_terms", 5), 1005: ("review", 6),
    1010: ("single", 1), 1011: ("review", 2), 1012: ("relief_terms", 3),
    1013: ("clarify", 4), 1014: ("relief_terms", 5), 1015: ("review", 6),
    1020: ("single", 1), 1021: ("review", 2), 1022: ("state_terms", 3),
    1023: ("clarify", 4), 1024: ("state_terms", 5), 1025: ("review", 6),
}


def _arc_for_event(event_id):
    number = int(event_id.rsplit(".", 1)[1])
    base = number // 10 * 10
    if base not in (1000, 1010, 1020):
        return None
    return {1000: SLUGS[0], 1010: SLUGS[1], 1020: SLUGS[2]}[base], number


def _route2_ordinary_facts():
    facts = _ordinary_facts()
    facts["states"][0]["market_access"] = 0.50
    facts["market"]["tea"]["exports"] = 1
    facts["relations"] = {"SHU": 0, "RUS": -10}
    facts["laws"].discard("law_tenant_farmers")
    facts["laws"].discard("law_serfdom")
    facts["laws"].add("law_homesteading")
    facts["states"][0]["average_sol"] = 8
    facts["market"]["grain"]["pricier"] = 0.18
    facts["military_expenses_share"] = 0
    return facts


def _assert_all_six_terminal(testcase, world, outcome):
    expected = [jid for arc in MGL_ARCS for jid in (arc["journals"][0]["id"], arc["journals"][1]["id"])]
    testcase.assertEqual(len(expected), 6)
    testcase.assertEqual(len(world.completed_journals), 7)  # legacy JE plus the six MGL queue JEs
    testcase.assertEqual(len(set(world.completed_journals)), 7)
    testcase.assertEqual(set(expected).issubset(world.completed_journals), True)
    testcase.assertEqual({jid: world.history[TAG].get(jid) for jid in expected},
                         {jid: "complete" for jid in expected})
    testcase.assertEqual(world.history[TAG].get("ywc_je_flavor_mng_balance_1"), "complete")
    state = world.countries[TAG]
    testcase.assertEqual({slug: state[f"ywc_v03_mgl_{slug}_outcome"] for slug in SLUGS},
                         {slug: outcome for slug in SLUGS})
    testcase.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


def _run_actual_paid_route_to_node5(admission_order, route=1, ordinary_facts=None):
    """Drive native live queues through selected route using only real source options."""
    world, admission = actual_mgl_admission_world(admission_order, ordinary_facts)
    state = world.countries[TAG]
    phase = list(admission_order)
    next_rank = {slug: 1 for slug in SLUGS}
    paid = {slug: 0 for slug in SLUGS}
    payment_month = {}
    blocked_start_day = {}
    path = []
    notices = []
    unexpected = []
    premature_terminal_state = []
    payment_day = {}

    def note_notice(event_id, slug):
        prefix = PREFIX[slug]
        started_day = blocked_start_day.get(slug, world.calendar_day)
        if state.get(f"ywc_mgl_{prefix}_blocked_12_started") and slug not in blocked_start_day:
            blocked_start_day[slug] = world.calendar_day
            started_day = world.calendar_day
        notices.append({"event": event_id, "world_month": world.story_month,
                        "relative_month": world.story_month - admission["root_admission_month"],
                        "world_day": world.calendar_day,
                        "relative_day": world.calendar_day - admission["root_admission_day"],
                        "payment_age_month": world.story_month - payment_month.get(slug, world.story_month),
                        "blocked_age_day": world.calendar_day - started_day})

    for _ in range(150):
        if not world.active_journals[TAG]:
            break
        event_id = pulse_actual_journals(world)
        for slug in SLUGS:
            prefix = PREFIX[slug]
            terms_key = f"ywc_mgl_{prefix}_terms_committed"
            if state.get(terms_key) in (1, 2, 3):
                continue
            forbidden = [f"ywc_mgl_{prefix}_{stage}_{suffix}"
                         for stage in ("full", "limited", "legacy")
                         for suffix in ("watch", "mature") if
                         f"ywc_mgl_{prefix}_{stage}_{suffix}" in state]
            outcome_key = f"ywc_v03_mgl_{slug}_outcome"
            if outcome_key in state:
                forbidden.append(outcome_key)
            for final_key in (f"ywc_mgl_{prefix}_full_ready", f"ywc_mgl_{prefix}_one_ready",
                              f"ywc_mgl_{prefix}_local_ready"):
                if world.condition((final_key, "=", "yes"), TAG):
                    forbidden.append(f"{final_key}=yes_without_terms")
            if forbidden:
                premature_terminal_state.append((slug, world.story_month, tuple(forbidden)))
        if event_id is None:
            continue
        number = int(event_id.rsplit(".", 1)[1])
        route_info = _arc_for_event(event_id)
        if route_info is None:
            prefix_number = number // 10 * 10
            slug = {1000: SLUGS[0], 1010: SLUGS[1], 1020: SLUGS[2]}.get(prefix_number)
            if slug is None:
                unexpected.append(event_id)
                continue
            # Only a queued 12/36 notice is expected while normal story stages wait.
            note_notice(event_id, slug)
            choose_actual_option(world, event_id, "defer")
            continue
        slug, number = route_info
        if number % 10 in (6, 7):
            note_notice(event_id, slug)
            choose_actual_option(world, event_id, "defer")
            continue
        selected = (EVENT_SUFFIX if route == 1 else ROUTE2_SUFFIX).get(number)
        if selected is None:
            unexpected.append(event_id)
            continue
        suffix, stage = selected
        expected_stage = next_rank[slug]
        if stage != expected_stage:
            # A native notice or repeat due event can interrupt the normal ladder.
            unexpected.append((event_id, "normal_queue_out_of_order", expected_stage))
            continue
        before = world.treasury[TAG]
        choose_actual_option(world, event_id, suffix)
        if stage == 1:
            paid[slug] += before - world.treasury[TAG]
            expected_fee = 200 if route == 1 else 100
            if paid[slug] != expected_fee:
                unexpected.append((event_id, "selected_route_actual_fee", paid[slug], expected_fee))
            # Grain's accepted success recipe changes this ordinary market fact only
            # after the real entry event and 200 fee have executed.
            if slug == SLUGS[2] and route == 1:
                state["market"]["grain"]["pricier"] = 0.10
            if slug == SLUGS[1] and route == 2:
                # Debt route 2 pays while the authored entry SoL is below 10;
                # execution requires the later ordinary fact to recover to >=10.
                state["states"][0]["average_sol"] = 10
        if stage == 5:
            terms_key = {SLUGS[0]: "ywc_mgl_roads_terms_committed",
                         SLUGS[1]: "ywc_mgl_debt_terms_committed",
                         SLUGS[2]: "ywc_mgl_grain_terms_committed"}[slug]
            if state.get(terms_key) != route:
                unexpected.append((event_id, "selected_route_terms_not_source_written", state.get(terms_key)))
        if stage == 1:
            payment_month[slug] = world.story_month
            payment_day[slug] = world.calendar_day
        prefix = PREFIX[slug]
        blocked_start = state.get(f"ywc_mgl_{prefix}_blocked_12_started")
        if blocked_start and slug not in blocked_start_day:
            blocked_start_day[slug] = world.calendar_day
        path.append({"arc": slug, "event": event_id, "option": suffix,
                     "world_month": world.story_month,
                     "relative_month": world.story_month - admission["root_admission_month"],
                     "world_day": world.calendar_day,
                     "relative_day": world.calendar_day - admission["root_admission_day"],
                     "payment_age_month": world.story_month - payment_month.get(slug, world.story_month),
                     "payment_age_day": world.calendar_day - payment_day.get(slug, world.calendar_day),
                     "blocked_started": blocked_start,
                     "blocked_age_day": world.calendar_day - blocked_start_day[slug] if slug in blocked_start_day else None})
        next_rank[slug] += 1
        if all(rank == 7 for rank in next_rank.values()):
            break
    return world, admission, path, notices, unexpected, paid, premature_terminal_state


class MglQueueWaitObligationContracts(unittest.TestCase):
    def test_healthy_unpaid_real_offers_may_defer_without_fake_watch_or_fee(self):
        for slug in SLUGS:
            order = (slug,) + tuple(other for other in SLUGS if other != slug)
            with self.subTest(target_arc=slug):
                world, admission = actual_mgl_admission_world(order)
                state = world.countries[TAG]
                self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
                for other, prefix in PREFIX.items():
                    self.assertTrue(world.condition((f"ywc_mgl_{prefix}_entry_1_ready", "=", "yes"), TAG), other)
                    self.assertGreaterEqual(state["gold_reserves"] + world.treasury[TAG],
                                            state[f"ywc_mgl_{prefix}_double_fee"])
                target_event = {SLUGS[0]: "ywc_mng.1000", SLUGS[1]: "ywc_mng.1010",
                                SLUGS[2]: "ywc_mng.1020"}[slug]
                event_id = None
                for _ in range(4):
                    event_id = pulse_actual_journals(world)
                    if event_id is not None:
                        break
                self.assertEqual(event_id, target_event, "source order should expose the chosen first offer")
                prefix = PREFIX[slug]
                option = next(v for k, _, v in world.event_defs[event_id] if k == "option" and
                              next((x for n, _, x in v if n == "name"), "") == event_id + ".dual")
                gate = next((v for k, _, v in option if k == "trigger"), [])
                self.assertTrue(world.conditions(gate, TAG), (event_id, "route1 offer must be legal"))
                choose_actual_option(world, event_id, "defer")
                self.assertEqual(state.get(f"ywc_mgl_{prefix}_route_paid", 0), 0)
                self.assertEqual(state.get(f"ywc_mgl_{prefix}_route", 0), 0)
                forbidden = [f"ywc_mgl_{prefix}_{name}" for name in
                             ("blocked_12_started", "blocked_12_due", "blocked_36_started", "blocked_36_due",
                              "full_watch", "limited_watch", "legacy_watch", "full_mature", "limited_mature",
                              "legacy_mature") if f"ywc_mgl_{prefix}_{name}" in state]
                self.assertEqual(forbidden, [], ("healthy unpaid offer/defer must not start watch", event_id, forbidden))
                self.assertNotIn(f"ywc_v03_mgl_{slug}_outcome", state)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
                self.assertEqual(world.treasury[TAG], 0)

    def test_three_real_paid_route1_arcs_do_not_start_false_blocked_notices_while_terms_wait(self):
        """Three source-rotation phases diagnose business pacing, not adapter fairness."""
        for order in (SLUGS, (SLUGS[1], SLUGS[2], SLUGS[0]), (SLUGS[2], SLUGS[0], SLUGS[1])):
            with self.subTest(phase=order):
                world, admission, path, notices, unexpected, paid, premature = _run_actual_paid_route_to_node5(order)
                self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
                self.assertEqual(paid, {slug: 200 for slug in SLUGS})
                self.assertEqual(len(path), 18, path)
                for slug in SLUGS:
                    reads = [row for row in path if row["arc"] == slug and
                             row["event"].endswith((".1002", ".1012", ".1022", ".1004", ".1014", ".1024"))]
                    self.assertEqual(len(reads), 2, reads)
                    self.assertTrue(all(row["payment_age_month"] >= 6 and row["payment_age_day"] >= 180
                                        for row in reads), reads)
                self.assertEqual(notices, [], ("normal queue waiting alone produced a blocked notice",
                                               notices[:3], f"total={len(notices)}", path[:11]))
                self.assertEqual(premature, [])
                self.assertEqual(unexpected, [])
                state = world.countries[TAG]
                self.assertEqual(state["ywc_mgl_roads_terms_committed"], 1)
                self.assertEqual(state["ywc_mgl_debt_terms_committed"], 1)
                self.assertEqual(state["ywc_mgl_grain_terms_committed"], 1)
                for slug in SLUGS:
                    prefix = PREFIX[slug]
                    self.assertEqual(state[f"ywc_mgl_{prefix}_route"], 1)
                    self.assertEqual(state[f"ywc_mgl_{prefix}_node_2_route_read"], 1)
                    self.assertEqual(state[f"ywc_mgl_{prefix}_node_4_route_read"], 1)
                # Actual monthly pulses own observation maturity and terminal/outcome writes.
                while world.active_journals[TAG]:
                    event_id = pulse_actual_journals(world)
                    self.assertIsNone(event_id, ("unexpected event during source maturity", event_id))
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
                self.assertEqual(world.active_journals[TAG], [])
                for slug in SLUGS:
                    self.assertEqual(state[f"ywc_v03_mgl_{slug}_outcome"], 1)
                _assert_all_six_terminal(self, world, 1)

    def test_actual_route2_uses_distinct_facts_fee_and_two_route_readings_for_outcome2(self):
        world, admission, path, notices, unexpected, paid, premature = _run_actual_paid_route_to_node5(
            SLUGS, route=2, ordinary_facts=_route2_ordinary_facts())
        self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
        self.assertEqual(paid, {slug: 100 for slug in SLUGS})
        self.assertEqual(world.treasury[TAG], -300)
        self.assertEqual(len(path), 18, path)
        for slug in SLUGS:
            readings = [row for row in path if row["arc"] == slug and
                        row["event"].endswith((".1002", ".1012", ".1022", ".1004", ".1014", ".1024"))]
            self.assertEqual(len(readings), 2, readings)
            self.assertTrue(all(row["payment_age_month"] >= 6 and row["payment_age_day"] >= 180
                                for row in readings), readings)
        self.assertEqual(notices, [], ("route2 valid selected obligations cannot be charged for waiting terms",
                                       notices[:3], f"total={len(notices)}"))
        self.assertEqual(unexpected, [])
        self.assertEqual(premature, [])
        state = world.countries[TAG]
        for slug in SLUGS:
            prefix = PREFIX[slug]
            self.assertEqual(state[f"ywc_mgl_{prefix}_route"], 2)
            self.assertEqual(state[f"ywc_mgl_{prefix}_terms_committed"], 2)
            self.assertEqual(state[f"ywc_mgl_{prefix}_node_2_route_read"], 2)
            self.assertEqual(state[f"ywc_mgl_{prefix}_node_4_route_read"], 2)
        while world.active_journals[TAG]:
            event_id = pulse_actual_journals(world)
            self.assertIsNone(event_id, ("unexpected event during route2 maturity", event_id))
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        self.assertEqual(world.active_journals[TAG], [])
        for slug in SLUGS:
            self.assertEqual(state[f"ywc_v03_mgl_{slug}_outcome"], 2)
        _assert_all_six_terminal(self, world, 2)

    def test_all_six_source_root_orders_keep_all_three_original_route_fees_exactly_once(self):
        for order in permutations(SLUGS):
            with self.subTest(order=order):
                world, admission, path, _notices, unexpected, paid, premature = _run_actual_paid_route_to_node5(order)
                self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
                self.assertEqual(paid, {slug: 200 for slug in SLUGS})
                self.assertEqual(sum(paid.values()), 600)
                self.assertEqual(premature, [])
                self.assertEqual(world.treasury[TAG], -600)
                for slug, arc in ARCS.items():
                    prefix = PREFIX[slug]
                    self.assertEqual(world.countries[TAG][f"ywc_mgl_{prefix}_route_paid"], 1)


if __name__ == "__main__":
    unittest.main()

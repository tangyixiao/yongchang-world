"""Actual-source MGL story through the generated inline native transport.

This is intentionally a permanent feature contract: while MGL remains
unregistered, assert_inline_supported reports an ordinary feature RED. The
separate source positive control at the bottom still runs without that feature.
"""
from __future__ import annotations

from itertools import permutations
import unittest

from tests import test_v03_mgl_actual_source as source
from tests.test_v03_mgl_inline_actual_source import (
    actual_mgl_inline_world,
    legal_ordinary_facts,
    validate_ordinary_facts,
    LAND_REFORM_LAWS,
    assert_inline_supported,
    choose_inline_option,
    pulse_inline_journals,
)


TAG = source.TAG
ARCS = tuple(arc["slug"] for arc in source.MGL_ARCS)
ARC_BY_SLUG = {arc["slug"]: arc for arc in source.MGL_ARCS}
PREFIX = source.PREFIX
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


def _route2_facts():
    facts = legal_ordinary_facts()
    facts["states"][0]["market_access"] = 0.50
    facts["market"]["tea"]["exports"] = 1
    facts["relations"] = {"SHU": 0, "RUS": -10}
    facts["laws"].discard("law_tenant_farmers")
    facts["laws"].discard("law_serfdom")
    facts["laws"].add("law_homesteading")
    facts["states"][0]["average_sol"] = 8
    facts["market"]["grain"]["pricier"] = 0.18
    facts["military_expenses_share"] = 0
    return validate_ordinary_facts(facts)


def _mandatory_story_stages(route):
    suffixes = EVENT_SUFFIX if route == 1 else ROUTE2_SUFFIX
    return {
        ARCS[0]: [(1000, suffixes[1000][0]), (1001, "review"),
                  (1002, suffixes[1002][0]), (1003, "clarify"),
                  (1004, suffixes[1004][0])],
        ARCS[1]: [(1010, suffixes[1010][0]), (1011, "review"),
                  (1012, suffixes[1012][0]), (1013, "clarify"),
                  (1014, suffixes[1014][0])],
        ARCS[2]: [(1020, suffixes[1020][0]), (1021, "review"),
                  (1022, suffixes[1022][0]), (1023, "clarify"),
                  (1024, suffixes[1024][0])],
    }


def _event_arc(event_id):
    number = int(event_id.rsplit(".", 1)[1])
    base = number // 10 * 10
    mapping = {1000: ARCS[0], 1010: ARCS[1], 1020: ARCS[2]}
    return (mapping[base], number) if base in mapping else (None, number)


def _assert_terminal(testcase, world, outcome):
    expected = [jid for arc in source.MGL_ARCS for jid in
                (arc["journals"][0]["id"], arc["journals"][1]["id"])]
    state = world.countries[TAG]
    testcase.assertEqual(len(world.completed_journals), 7)
    testcase.assertEqual(len(set(world.completed_journals)), 7)
    testcase.assertTrue(set(expected).issubset(world.completed_journals))
    testcase.assertTrue(all(world.history[TAG].get(jid) == "complete" for jid in expected))
    testcase.assertEqual(world.history[TAG].get(source.LEGACY_JE), "complete")
    testcase.assertEqual({slug: state[f"ywc_v03_mgl_{slug}_outcome"] for slug in ARCS},
                         {slug: outcome for slug in ARCS})
    testcase.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


def _drive_route(order, route, ordinary_facts=None):
    """Drive authored queues and options; never seed MGL-owned progress state."""
    world, admission = actual_mgl_inline_world(order, ordinary_facts)
    state = world.countries[TAG]
    next_stage = {slug: 1 for slug in ARCS}
    paid = {slug: 0 for slug in ARCS}
    payment_month, payment_day = {}, {}
    ledger, unknown, notices = [], [], []
    suffixes = EVENT_SUFFIX if route == 1 else ROUTE2_SUFFIX

    for _ in range(240):
        if not world.active_journals[TAG]:
            break
        event_id = pulse_inline_journals(world)
        if event_id is None:
            continue
        slug, number = _event_arc(event_id)
        if slug is None:
            if number not in (1006, 1007, 1016, 1017, 1026, 1027):
                unknown.append((event_id, "not-an-authored-notice"))
                continue
            notices.append((slug, event_id, world.story_month))
            choose_inline_option(world, event_id, "defer")
            continue
        if number % 10 in (6, 7):
            notices.append((slug, event_id, world.story_month))
            choose_inline_option(world, event_id, "defer")
            continue
        selected = suffixes.get(number)
        if selected is None:
            unknown.append((event_id, "no-authored-route-option"))
            continue
        suffix, stage = selected
        if stage != next_stage[slug]:
            unknown.append((event_id, "out-of-order", next_stage[slug], stage))
            continue
        before = world.treasury[TAG]
        choose_inline_option(world, event_id, suffix)
        fee = before - world.treasury[TAG]
        if stage == 1:
            paid[slug] += fee
            payment_month[slug], payment_day[slug] = world.story_month, world.calendar_day
            if slug == ARCS[2] and route == 1:
                state["market"]["grain"]["pricier"] = 0.10
            if slug == ARCS[1] and route == 2:
                state["states"][0]["average_sol"] = 10
        age_month = world.story_month - payment_month.get(slug, world.story_month)
        age_day = world.calendar_day - payment_day.get(slug, world.calendar_day)
        ledger.append({"arc": slug, "event": event_id, "option": suffix,
                       "month": world.story_month, "day": world.calendar_day,
                       "payment_age_month": age_month, "payment_age_day": age_day,
                       "fee_delta": fee})
        next_stage[slug] += 1
    return world, admission, ledger, notices, unknown, paid


def _qualify_all_entries(world):
    """Pay each real route-1 entry; defer later stages without setting state."""
    state = world.countries[TAG]
    paid = set()
    ledger = []
    for _ in range(120):
        if len(paid) == 3:
            return ledger
        event_id = pulse_inline_journals(world)
        if event_id is None:
            continue
        slug, number = _event_arc(event_id)
        if slug is None:
            raise AssertionError(("notice_before_qualification_loss", event_id))
        before = world.treasury[TAG]
        if number in (1000, 1010, 1020):
            if slug in paid:
                choose_inline_option(world, event_id, "defer")
                continue
            choose_inline_option(world, event_id, "dual")
            paid.add(slug)
            ledger.append({"arc": slug, "event": event_id, "fee": before - world.treasury[TAG],
                           "month": world.story_month, "day": world.calendar_day})
        elif number % 10 in (6, 7):
            raise AssertionError(("notice_before_loss", event_id))
        else:
            choose_inline_option(world, event_id, "defer")
    raise AssertionError(("actual_route1_entry_events_not_reached", paid, ledger))


def _lose_route1_qualifications(state):
    state["states"][0]["market_access"] = 0.60
    state["states"][0]["average_sol"] = 8
    state["market"]["tea"]["exports"] = 0
    state["market"]["wool"]["exports"] = 0
    state["market"]["grain"]["pricier"] = 0.30
    state["relations"] = {"SHU": -10, "RUS": -10}
    state["military_expenses_share"] = 0


def _restore_route1_qualifications(state):
    state["laws"].difference_update(LAND_REFORM_LAWS)
    state["laws"].add("law_tenant_farmers")
    validate_ordinary_facts(state)
    state["states"][0]["market_access"] = 0.80
    state["states"][0]["average_sol"] = 11
    state["market"]["tea"]["exports"] = 100
    state["market"]["wool"]["exports"] = 2
    state["market"]["grain"]["pricier"] = 0.10
    state["relations"] = {"SHU": 0, "RUS": 0}
    state["military_expenses_share"] = 0.15


def _deliver_actual_notice_journeys(testcase, *, restore_after_12):
    """Reach native notices from lost ordinary facts and acknowledge source options."""
    world, admission = actual_mgl_inline_world()
    state = world.countries[TAG]
    entry_ledger = _qualify_all_entries(world)
    testcase.assertEqual({row["arc"]: row["fee"] for row in entry_ledger},
                         {slug: 200 for slug in ARCS})
    loss_day = world.calendar_day
    _lose_route1_qualifications(state)
    received = {slug: set() for slug in ARCS}
    ledger = []
    for _ in range(180):
        event_id = pulse_inline_journals(world)
        if event_id is None:
            continue
        slug, number = _event_arc(event_id)
        if slug is None:
            raise AssertionError(("unmapped_actual_notice", event_id))
        if number % 10 in (6, 7):
            years = 12 if number % 10 == 6 else 36
            suffix = "defer" if years == 12 or restore_after_12 else "narrow"
            choose_inline_option(world, event_id, suffix)
            received[slug].add(years)
            ledger.append({"arc": slug, "event": event_id, "notice_months": years,
                           "option": suffix, "month": world.story_month,
                           "relative_loss_day": world.calendar_day - loss_day})
        else:
            choose_inline_option(world, event_id, "defer")
        if all(len(values) >= (1 if restore_after_12 else 2) for values in received.values()):
            if restore_after_12 or all({12, 36} <= values for values in received.values()):
                break
    expected = {12} if restore_after_12 else {12, 36}
    testcase.assertEqual(received, {slug: expected for slug in ARCS}, ledger)
    testcase.assertEqual(len([row for row in entry_ledger if row["fee"] == 200]), 3)
    if restore_after_12:
        _restore_route1_qualifications(state)
        for _ in range(4):
            event_id = pulse_inline_journals(world)
            if event_id is not None:
                choose_inline_option(world, event_id, "defer")
        for slug in ARCS:
            prefix = PREFIX[slug]
            testcase.assertFalse(state.get(f"ywc_mgl_{prefix}_blocked_12_due"))
            testcase.assertFalse(state.get(f"ywc_mgl_{prefix}_blocked_36_due"))
            testcase.assertFalse(state.get(f"ywc_mgl_{prefix}_blocked_12_notice_event"))
            testcase.assertFalse(state.get(f"ywc_mgl_{prefix}_blocked_36_notice_event"))
    else:
        # Narrowing is source-authored recovery after each real 36-month notice.
        for slug in ARCS:
            prefix = PREFIX[slug]
            testcase.assertEqual(state[f"ywc_mgl_{prefix}_narrowed"], 1)
            testcase.assertEqual(state[f"ywc_mgl_{prefix}_route"], 3)
        _restore_route1_qualifications(state)
        state["laws"].difference_update(LAND_REFORM_LAWS)
        state["laws"].add("law_serfdom")
        validate_ordinary_facts(state)
        for slug in ARCS:
            prefix = PREFIX[slug]
            testcase.assertTrue(world.condition((f"ywc_mgl_{prefix}_current_obligation_ready", "=", "yes"), TAG))
    return world, admission, entry_ledger, ledger


class MglInlineNativeStoryContracts(unittest.TestCase):
    def test_mandatory_story_event_map_is_constructible_without_feature(self):
        route1 = _mandatory_story_stages(1)
        route2 = _mandatory_story_stages(2)
        self.assertEqual([event for event, _ in route1[ARCS[0]]], [1000, 1001, 1002, 1003, 1004])
        self.assertEqual([event for event, _ in route2[ARCS[0]]], [1000, 1001, 1002, 1003, 1004])
        self.assertEqual(route1[ARCS[0]][2][1], "dual_terms")
        self.assertEqual(route2[ARCS[0]][2][1], "single_terms")
        self.assertEqual(route1[ARCS[1]][2][1], "arbitration_terms")
        self.assertEqual(route2[ARCS[1]][2][1], "relief_terms")
        self.assertEqual(route1[ARCS[2]][2][1], "joint_terms")
        self.assertEqual(route2[ARCS[2]][2][1], "state_terms")

    def test_source_only_positive_control_runs_without_inline_feature(self):
        """Keep fixture/parser failures separate from the ordinary feature RED."""
        world, evidence = source.actual_mgl_admission_world(ordinary_facts=legal_ordinary_facts())
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})
        self.assertEqual([row["event"] for row in evidence["legacy_trace"]],
                         list(source.LEGACY_EVENTS))
        self.assertEqual(evidence["legacy_terminal"]["complete"], True)
        self.assertTrue(all(row["shown"] and row["possible"] and row["immediate"]
                            for row in evidence["root_admissions"]))
        self.assertEqual(len(world.completed_journals), 1)

    def test_public_inline_feature_is_registered_for_complete_mgl_source(self):
        # This is the ordinary permanent feature RED until MGL is registered.
        # assert_inline_supported deliberately lets parse/fixture errors escape.
        rendered = assert_inline_supported(self)
        self.assertEqual(len(rendered["event_hooks"]), 24)

    def test_actual_joint_route1_and_route2_across_all_six_root_orders(self):
        # Six fresh admission permutations for each distinct real paid path.
        assert_inline_supported(self)
        for route, facts, outcome, expected_fee in (
                (1, None, 1, 200), (2, _route2_facts(), 2, 100)):
            for order in permutations(ARCS):
                with self.subTest(route=route, order=order):
                    suffixes = EVENT_SUFFIX if route == 1 else ROUTE2_SUFFIX
                    world, admission, ledger, notices, unknown, paid = _drive_route(order, route, facts)
                    self.assertEqual([row["arc"] for row in admission["root_admissions"]], list(order))
                    self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
                    self.assertEqual(paid, {slug: expected_fee for slug in ARCS})
                    self.assertGreaterEqual(len(ledger), 15, ledger)
                    self.assertLessEqual(len(ledger), 18, ledger)
                    self.assertEqual(notices, [], "healthy route waiting must not invent blocked notices")
                    self.assertEqual(unknown, [])
                    for slug in ARCS:
                        rows = [row for row in ledger if row["arc"] == slug]
                        mandatory = _mandatory_story_stages(route)
                        expected = mandatory[slug]
                        self.assertEqual([(int(row["event"].rsplit(".", 1)[1]), row["option"])
                                          for row in rows[:5]], expected, rows)
                        self.assertIn(len(rows), (5, 6), rows)
                        if len(rows) == 6:
                            self.assertEqual((rows[5]["event"], rows[5]["option"]),
                                             (f"ywc_mng.{expected[0][0] + 5}", "review"), rows)
                        readings = [row for row in rows if row["event"].endswith((".1002", ".1012", ".1022",
                                                                                 ".1004", ".1014", ".1024"))]
                        self.assertEqual(len(readings), 2, readings)
                        self.assertTrue(all(row["payment_age_month"] >= 6 and row["payment_age_day"] >= 180
                                            for row in readings), readings)
                        prefix = PREFIX[slug]
                        self.assertEqual(world.countries[TAG][f"ywc_mgl_{prefix}_route_paid"], 1)
                    state = world.countries[TAG]
                    self.assertEqual(world.treasury[TAG], -3 * expected_fee)
                    # Reach the real six-calendar-month boundary by ordinary
                    # shared monthly JE pulses only; no timer/cooldown seeding.
                    for _ in range(24):
                        if not world.active_journals[TAG]:
                            break
                        event_id = pulse_inline_journals(world)
                        self.assertIsNone(event_id, ("unexpected post-route delivery", event_id))
                    _assert_terminal(self, world, outcome)

    def test_authored_notice_options_exist_for_each_arc(self):
        """Bind legal defer/narrow/withdraw options to actual native notice bodies."""
        from tests.clausewitz_harness import parse
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        journal_file = root / "yongchang_world/common/journal_entries/ywc_v03_country_mgl_journal.txt"
        event_file = root / "yongchang_world/events/ywc_v03_country_mgl_events.txt"
        journals = {key: body for key, _, body in parse(journal_file.read_text(encoding="utf-8-sig"))}
        events = {key: body for key, _, body in parse(event_file.read_text(encoding="utf-8-sig"))
                  if key.startswith("ywc_mng.")}

        def option_names(nodes):
            found = []
            for key, _, value in nodes:
                if key == "name" and isinstance(value, str) and value.startswith("ywc_mng."):
                    found.append(value)
                if isinstance(value, list):
                    found.extend(option_names(value))
            return found

        names = [name for body in events.values() for name in option_names(body)]
        for arc in source.MGL_ARCS:
            for journal in arc["journals"]:
                self.assertIn(journal["id"], journals)
                pulse = next(value for key, _, value in journals[journal["id"]]
                             if key == "on_monthly_pulse")
                self.assertEqual(sum(1 for key, _, _ in pulse[0][2] if key in ("if", "else_if")), 11)
            for suffix in ("defer", "withdraw", "narrow"):
                self.assertTrue(any(name.endswith("." + suffix) for name in names), suffix)
        self.assertEqual(len(events), 24)

    def test_actual_12_month_notice_defer_then_ordinary_fact_restoration(self):
        assert_inline_supported(self)
        world, admission, entries, notices = _deliver_actual_notice_journeys(self, restore_after_12=True)
        self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
        self.assertEqual(len(entries), 3)
        self.assertTrue(all(row["notice_months"] == 12 and row["option"] == "defer"
                            for row in notices))

    def test_actual_12_and_36_month_notices_then_legal_narrow_recovery(self):
        assert_inline_supported(self)
        world, admission, entries, notices = _deliver_actual_notice_journeys(self, restore_after_12=False)
        self.assertEqual(admission["counts"], {"active": 3, "visible": 3})
        self.assertEqual(len(entries), 3)
        self.assertTrue(all(row["notice_months"] == 12 or
                            (row["notice_months"] == 36 and row["option"] == "narrow")
                            for row in notices))


if __name__ == "__main__":
    unittest.main()

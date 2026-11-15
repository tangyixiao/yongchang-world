"""Earn KOR's old contracts through native source before revenue consumes them.

Every calendar month runs the actual country on_action and journal pulse.
Neither monthly-ready counters nor public legacy markers stand in for paid
translation/veteran contracts, actual observations or original event choices.
"""
import copy
import unittest

from shu_kor_strict_review_runtime import field
from test_v03_kor_provincial_revenue import (
    P, L, JES, ROUTES, new_world, current_facts, office, office_pop, choose,
    option_legal, revenue_arc, world_facts,
)

MILITARY = "v03_kor_military_accounts"
SCHOOL = "v03_kor_school_factions"
PORTS = "v03_kor_controlled_ports"


def arc_for(world, slug):
    return next(arc for arc in world.cat["arcs"] if arc["slug"] == slug)


def native_month(world, arc, count=1):
    """One real calendar month, actual country on_action, actual JE pulse."""
    if not hasattr(world, "earned_monthly_ledger"):
        world.earned_monthly_ledger = []
    for _ in range(count):
        world.advance_months(1)
        stamp = (world.date.year, world.date.month)
        assert not world.earned_monthly_ledger or world.earned_monthly_ledger[-1]["month"] != stamp
        state = world.countries[world.tag]
        before = tuple(state.get("ywc_kor_" + kind + "_contract_paid_months", 0)
                       for kind in ("translation", "veteran"))
        treasury = world.treasury[world.tag]
        world.run_country_monthly(world.tag)
        world.pulse(arc)
        after = tuple(state.get("ywc_kor_" + kind + "_contract_paid_months", 0)
                      for kind in ("translation", "veteran"))
        increments = sum(new - old for old, new in zip(before, after))
        expected = -state.get("ywc_kor_weekly_cost", 0) * .0833333333 * increments
        delta = world.treasury[world.tag] - treasury
        assert abs(delta - expected) < 1e-6, ("monthly_contract_cash", stamp, before, after, delta, expected)
        assert all(0 <= new <= 12 for new in after), ("contract_cap", stamp, after)
        world.earned_monthly_ledger.append({"month": stamp, "before": before,
                                           "after": after, "cash_delta": delta})


def native_deliver(world, arc, number, attempts=120):
    """Receive a genuine generated callback without hidden virtual months."""
    expected = f"ywc_kor.{number}"
    for _ in range(attempts):
        native_month(world, arc)
        while world.events:
            tag, event_id = world.events.pop(0)
            event = world.event_defs[event_id]
            if not world.conditions(field(event, "trigger"), tag):
                continue
            assert (tag, event_id) == (world.tag, expected), ("unexpected_native_event", tag, event_id, expected)
            state = world.countries[world.tag]
            assert "ywc_v03_kor_inline_reservation" in state, ("missing_native_reservation", event_id)
            world.execute(field(event, "immediate"), tag)
            assert "ywc_v03_kor_inline_reservation" not in state, ("native_ack_missing", event_id)
            return event
    raise AssertionError(("native_event_not_reached", expected, world.date,
                          world.active[world.tag], world.trace[-8:]))


def native_play(world, arc, number, key, wait=None):
    for _ in range(8):
        event = native_deliver(world, arc, number)
        if option_legal(world, event, key):
            choose(world, arc, event, key)
            world.trace.append({"earned_event": f"ywc_kor.{number}", "key": key,
                                "date": world.date.isoformat()})
            return event
        assert wait is not None and option_legal(world, event, wait), ("earned_option_illegal", number, key)
        choose(world, arc, event, wait)
    raise AssertionError(("native_wait_exhausted", number, key))


def earn_military(world, route="provincial", withdraw=False):
    """Ten original choices, two genuine observation gates, actual installments."""
    arc = arc_for(world, MILITARY)
    opening = {"provincial": "provincial_share", "court": "court_supply",
               "limited": "limited_legacy"}[route]
    withdraw_at = 1006 if withdraw is True else withdraw
    roll = {"provincial": "province_roll", "court": "court_roll", "limited": "legacy_roll"}[route]
    for number, key in ((1000, opening), (1001, "pay_month"), (1002, roll),
                        (1003, "publish"), (1004, "fund_local"), (1005, "fund_transition")):
        native_play(world, arc, number, key)
    native_play(world, arc, 1006, "withdraw" if withdraw_at == 1006 else "begin_renewal")
    if withdraw_at != 1006:
        for number, key in ((1007, "fund_invoice_review"), (1008, "peace_ledger"),
                            (1009, "withdraw" if withdraw_at == 1009 else
                             {"court": "establish_court", "provincial": "establish_provincial",
                              "limited": "establish_limited"}[route])):
            native_play(world, arc, number, key)
    # Original country on_action continues the real selected installments
    # after settlement. No paid-month counter or positive marker is supplied.
    for _ in range(15):
        state = world.countries[world.tag]
        if all(state.get("ywc_kor_" + kind + "_contract_paid_months") == 12
               for kind in ("translation", "veteran")):
            break
        native_month(world, arc)
    return arc


def history_world(route="provincial", withdraw=False):
    world = new_world("provincial")
    assert "ywc_campaign_kor_c1_outcome" not in world.countries[world.tag]
    # Actual present military wage fact, not an earned story or consent flag.
    world.modifiers.append((world.tag, {"modifier": "military_wages_medium"}))
    earn_military(world, route, withdraw)
    return world


def match_current_cash(world, balance=100000):
    world.countries[world.tag]["gold_reserves"] = balance - world.treasury[world.tag]


def revenue_open(world, route="provincial", limited=False):
    arc = revenue_arc(world.cat)
    native_play(world, arc, 1100, "finite_target" if limited else ROUTES[route])
    native_play(world, arc, 1101, "pay_charter")
    return arc


def revenue_sign(world, arc):
    native_play(world, arc, 1102, "settle_reviewer")
    native_play(world, arc, 1103, "sign")


def revenue_finish(world, arc, outcome=1):
    native_month(world, arc, 6)
    native_play(world, arc, 1104, "pay_review")
    revenue_close_after_review(world, arc, outcome)


def revenue_close_after_review(world, arc, outcome=1):
    native_play(world, arc, 1104, "submit")
    native_play(world, arc, 1105, "review_responsibility")
    native_play(world, arc, 1106, "verify")
    native_play(world, arc, 1107, "request_full" if outcome == 1 else "request_finite")


def set_current_route_facts(world, route):
    """Change present laws/politics only; real state identities/history remain."""
    current = current_facts(route)
    state = world.countries[world.tag]
    for key in ("laws", "institutions", "igs", "bureaucracy", "legitimacy", "net_fixed_income"):
        state[key] = copy.deepcopy(current[key])
    office(world)["occupancy"] = .8


def earn_school(world, route="cooperative"):
    arc = arc_for(world, SCHOOL)
    for number, key in ((1010, "co_manage" if route == "cooperative" else "court_office"),
                        (1011, "record_old_invoice"), (1012, "share_review"),
                        (1013, "university_post" if route == "cooperative" else "office_post"),
                        (1014, "keep_docket"), (1015, "start_review")):
        native_play(world, arc, number, key)
    native_play(world, arc, 1016, "establish", wait="wait_for_observation")
    native_play(world, arc, 1017, "settle_established")
    return arc


def earn_ports(world, route="designated"):
    arc = arc_for(world, PORTS)
    for number, key in ((1018, "licensed_port" if route == "designated" else "general_customs"),
                        (1019, "record_exception"), (1020, "assign_auditors"),
                        (1021, "verify_full"), (1022, "repair")):
        native_play(world, arc, number, key)
    native_play(world, arc, 1023, "settle_full", wait="wait_for_observation")
    return arc


class KorRevenueCrossEra(unittest.TestCase):
    def assert_military_earned(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state["ywc_v03_kor_" + MILITARY + "_outcome"], outcome)
        self.assertEqual(state["ywc_v03_kor_" + MILITARY + "_settled"], 1)
        for kind in ("translation", "veteran"):
            self.assertEqual(state["ywc_kor_" + kind + "_contract_paid_months"], 12)
        self.assertTrue(world.earned_monthly_ledger)
        self.assertTrue(any(row["cash_delta"] < 0 for row in world.earned_monthly_ledger))
        if outcome != 4:
            for proof in ("audit_paid", "invoice_review_paid", "supply_account_accepted",
                          "audit_public", "review_complete", "service_review_complete",
                          "six_months_complete", "nine_months_complete"):
                self.assertEqual(state["ywc_kor_" + proof], 1)
            earned = [row["earned_event"] for row in world.trace if "earned_event" in row]
            self.assertEqual(earned[:10], [f"ywc_kor.{number}" for number in range(1000, 1010)])
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)

    def assert_revenue_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertTrue(all(world.history[world.tag][jid] == "complete" for jid in JES))

    def test_actual_provincial_and_court_histories_change_both_charter_and_reviewer(self):
        worlds = {route: history_world(route) for route in ("provincial", "court")}
        for route, world in worlds.items():
            self.assert_military_earned(world, 2 if route == "provincial" else 1)
            match_current_cash(world)
        self.assertEqual(world_facts(worlds["provincial"]), world_facts(worlds["court"]))
        for route, world in worlds.items():
            with self.subTest(old=route):
                arc = revenue_open(world)
                state = world.countries[world.tag]
                self.assertEqual(state[P + "charter_paid_amount"], 500 if route == "provincial" else 1000)
                office(world)["occupancy"] = .5
                event = native_deliver(world, arc, 1102)
                self.assertEqual(option_legal(world, event, "settle_reviewer"), route == "provincial")
                if route == "court":
                    office(world)["occupancy"] = .8
                choose(world, arc, event, "settle_reviewer")
                office(world)["occupancy"] = .8
                native_play(world, arc, 1103, "sign")
                revenue_finish(world, arc)
                self.assert_revenue_closed(world, 1)

    def test_actual_old_court_changes_central_review_from_fifteen_hundred_to_one_thousand(self):
        for route, expected in (("court", 1000), ("provincial", 1500)):
            with self.subTest(old=route):
                world = history_world(route)
                self.assert_military_earned(world, 1 if route == "court" else 2)
                set_current_route_facts(world, "central")
                match_current_cash(world)
                arc = revenue_open(world, "central")
                revenue_sign(world, arc)
                native_month(world, arc, 6)
                native_play(world, arc, 1104, "pay_review")
                self.assertEqual(world.countries[world.tag][P + "review_paid_amount"], expected)
                revenue_close_after_review(world, arc)
                self.assert_revenue_closed(world, 1)

    def test_current_court_barrack_loss_and_missing_earned_invoice_receipt_do_not_cache_discount(self):
        for lost in ("barrack", "invoice_receipt"):
            with self.subTest(lost=lost):
                world = history_world("court")
                self.assert_military_earned(world, 1)
                set_current_route_facts(world, "central")
                match_current_cash(world)
                arc = revenue_open(world, "central")
                revenue_sign(world, arc)
                native_month(world, arc, 6)
                state = world.countries[world.tag]
                event = native_deliver(world, arc, 1104)
                if lost == "barrack":
                    barrack = next(b for b in state["states"][0]["buildings"] if b["type"] == "building_barrack")
                    barrack["occupancy"] = .79
                    self.assertFalse(option_legal(world, event, "pay_review"))
                else:
                    del state["ywc_kor_invoice_review_paid"]
                    self.assertTrue(option_legal(world, event, "pay_review"))
                    choose(world, arc, event, "pay_review")
                    self.assertEqual(state[P + "review_paid_amount"], 1500)
                    self.assertEqual(state["ywc_v03_kor_" + MILITARY + "_outcome"], 1)

    def test_genuinely_earned_limited_and_withdrawn_military_and_absence_have_finite_revenue(self):
        for history in ("limited", "withdrawn1006", "withdrawn1009", "absent"):
            with self.subTest(history=history):
                world = new_world(bare=True) if history == "absent" else history_world(
                    "limited" if history == "limited" else "provincial",
                    withdraw={"withdrawn1006": 1006, "withdrawn1009": 1009}.get(history, False))
                if history != "absent":
                    self.assert_military_earned(world, 3 if history == "limited" else 4)
                match_current_cash(world)
                arc = revenue_open(world, limited=True)
                revenue_sign(world, arc)
                revenue_finish(world, arc, outcome=2)
                self.assert_revenue_closed(world, 2)
                state = world.countries[world.tag]
                self.assertEqual((state[P + "charter_paid_amount"], state[P + "review_paid_amount"]),
                                 (500, 500))

    def test_actual_school_and_ports_contracts_are_consumed_without_foreign_consent_fixtures(self):
        world = history_world("provincial")
        self.assert_military_earned(world, 2)
        earn_school(world)
        earn_ports(world)
        state = world.countries[world.tag]
        for slug in (SCHOOL, PORTS):
            self.assertEqual(state["ywc_v03_kor_" + slug + "_settled"], 1)
        for contract in ("prior_school", "prior_ports"):
            self.assertTrue(world.conditions(world.trigger_defs[P + contract], world.tag))
        match_current_cash(world)
        arc = revenue_open(world)
        revenue_sign(world, arc)
        revenue_finish(world, arc)
        self.assert_revenue_closed(world, 1)

    def test_real_school_contract_requires_earned_old_account_and_current_employer(self):
        for lost in ("old_account_read", "employer"):
            with self.subTest(lost=lost):
                world = history_world("provincial")
                earn_school(world)
                state = world.countries[world.tag]
                self.assertTrue(world.conditions(world.trigger_defs[P + "prior_school"], world.tag))
                if lost == "old_account_read":
                    del state["ywc_kor_school_old_account_read_2"]
                else:
                    university = next(b for b in state["states"][0]["buildings"] if b["type"] == "building_university")
                    university["occupancy"] = 0
                self.assertFalse(world.conditions(world.trigger_defs[P + "prior_school"], world.tag))


if __name__ == "__main__":
    unittest.main()

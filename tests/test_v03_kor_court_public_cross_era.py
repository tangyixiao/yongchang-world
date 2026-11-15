"""Genuine school/revenue producers consumed by KOR court-public source.

Prepared against the frozen plan and immutable ce03 old sources. No world is
constructed at import. Actual-source runs wait for root's terminal/binding gate.
"""
import copy
import unittest

from kor_partner_protocol_runtime import StateRef
from test_v03_kor_court_public import (
    CHANNELS, JES, L, P, ROUTES, choose, court_arc, current_facts, force_option,
    group, new_world, office, office_pop, option_legal, world_facts,
)
from test_v03_kor_revenue_cross_era import (
    arc_for, earn_military, earn_school, native_deliver, native_month, native_play,
    revenue_finish, revenue_open, revenue_sign, set_current_route_facts,
)

SCHOOL = "v03_kor_school_factions"
SCHOOL_L = "ywc_v03_kor_v03_kor_school_factions_"
REVENUE_L = "ywc_v03_kor_v03_kor_provincial_revenue_"
RP = "ywc_kor_revenue_"


def cash(world):
    return world.countries[world.tag]["gold_reserves"] + world.treasury[world.tag]


def set_cash(world, amount):
    world.countries[world.tag]["gold_reserves"] = amount - world.treasury[world.tag]


def university(world):
    return next(building for building in world.countries[world.tag]["states"][0]["buildings"]
                if building["type"] == "building_university")


def academic(world):
    return next(pop for pop in world.countries[world.tag]["states"][0]["pops"]
                if pop["type"] == "academics")


def history_snapshot(world):
    return copy.deepcopy({key: value for key, value in world.countries[world.tag].items()
                          if key.startswith("ywc_")})


def stable_producer_proof(world):
    """Earned immutable receipts/identities, excluding live timers/counters."""
    suffixes = ("started", "settled", "outcome")
    names = {prefix + suffix for prefix in (SCHOOL_L, REVENUE_L) for suffix in suffixes}
    names.update("ywc_kor_school_" + suffix for suffix in (
        "route", "established", "coop_paid", "office_paid", "filing_fee_paid",
        "old_invoice_paid", "old_account_read_2", "funding_decided",
        "appointment_decided", "six_months_complete", "employer", "employer_confirmed"))
    names.update(RP + suffix for suffix in (
        "outcome", "mode", "target", "pilot_state", "charter_paid", "charter_paid_amount",
        "review_paid", "review_paid_amount", "charter_pilot", "reviewer_pilot",
        "charter_mode", "charter_target"))
    state = world.countries[world.tag]
    return copy.deepcopy({key: value for key, value in state.items()
                          if key in names or "compatibility" in key})


def set_current(world, route="court", *, bare=False, balance=100000):
    """Update ordinary facts in the registered original state, preserving history."""
    state = world.countries[world.tag]
    earned = history_snapshot(world)
    facts = current_facts(route, bare)
    original = state["states"][0]
    sid = original["_sid"]
    replacement = copy.deepcopy(facts["states"][0])
    original.clear()
    original.update(replacement, _sid=sid)
    for key, value in facts.items():
        if key.startswith("ywc_") or key in ("states", "gold_reserves", "movements"):
            continue
        state[key] = copy.deepcopy(value)
    # The existing collection was supplied before construction. These tests
    # have no movement identity mutation or replacement-state shortcut.
    state["movements"][:] = copy.deepcopy(facts["movements"])
    if not bare:
        university(world)["occupancy"] = .8
    set_cash(world, balance)
    assert {key: state[key] for key in earned} == earned
    assert original["_sid"] == sid


def current_snapshot(world):
    result = world_facts(world)
    result["available_cash"] = cash(world)
    result["yearly_gross_income"] = world.countries[world.tag]["yearly_gross_income"]
    return result


def play(world, arc, number, key):
    """Use actual country callbacks and Gregorian months, including old debts."""
    return native_play(world, arc, number, key)


def month(world, arc, count=1):
    return native_month(world, arc, count)


def open_through_witness(world, route="court", *, limited=False, witness=None):
    arc = court_arc(world.cat)
    play(world, arc, 1120, "finite_petition" if limited else ROUTES[route])
    play(world, arc, 1121, "pay_petition")
    witness = witness or ("finite_clerk_witness" if limited else
                          "conservative_clerk_witness" if route == "conservative"
                          else "new_professional_witness")
    play(world, arc, 1122, witness)
    return arc


def ready(world, route="court", *, limited=False, witness=None):
    arc = open_through_witness(world, route, limited=limited, witness=witness)
    play(world, arc, 1123, "sign_responsibility")
    play(world, arc, 1124, "bounded_clerk_reply" if limited else CHANNELS[route])
    return arc


def close_after_payment(world, arc, outcome=1):
    suffix = {1: "full", 2: "finite", 3: "setback"}[outcome]
    play(world, arc, 1126, "request_" + suffix)
    play(world, arc, 1127, "close_" + suffix)


def finish(world, arc, outcome=1):
    state = world.countries[world.tag]
    play(world, arc, 1125, "advance_paid_review" if P + "review_paid" in state else "pay_review")
    close_after_payment(world, arc, outcome)


def military_world():
    """Earn the prerequisite original military history, never seed campaign flags."""
    world = new_world()
    world.modifiers.append((world.tag, {"modifier": "military_wages_medium"}))
    earn_military(world, "court")
    return world


def school_world(route="cooperative"):
    world = military_world()
    before = world.treasury[world.tag]
    earn_school(world, route)
    state = world.countries[world.tag]
    assert state[SCHOOL_L + "settled"] == 1
    assert state[SCHOOL_L + "outcome"] in (1, 2)
    assert state["ywc_kor_school_route"] == (1 if route == "cooperative" else 2)
    assert state["ywc_kor_school_old_invoice_paid"] == 1
    assert world.treasury[world.tag] < before
    world.court_producer_debit = world.treasury[world.tag] - before
    set_current(world)
    return world


def earn_revenue(world, route="provincial", *, limited=False):
    set_current_route_facts(world, route)
    arc = revenue_open(world, route, limited=limited)
    revenue_sign(world, arc)
    revenue_finish(world, arc, outcome=2 if limited else 1)
    state = world.countries[world.tag]
    assert state[REVENUE_L + "settled"] == 1
    assert state[REVENUE_L + "outcome"] == (2 if limited else 1)
    assert state[RP + "charter_paid_amount"] > 0 and state[RP + "review_paid_amount"] > 0
    return arc


def revenue_world(*, states=None):
    world = new_world("local", states=states)
    earn_revenue(world)
    state = world.countries[world.tag]
    assert (state[RP + "mode"], state[RP + "target"], state[RP + "outcome"]) == (1, 1, 1)
    reference = state[RP + "pilot_state"]
    assert isinstance(reference, StateRef)
    assert state[RP + "charter_pilot"] == state[RP + "reviewer_pilot"] == reference
    set_current(world, "local")
    return world


class KorCourtPublicCrossEra(unittest.TestCase):
    def assert_closed(self, world, outcome):
        state = world.countries[world.tag]
        self.assertEqual(state[P + "outcome"], outcome)
        self.assertEqual(state[L + "outcome"], outcome)
        self.assertEqual(state[L + "settled"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        self.assertFalse(any(journal in world.active[world.tag] for journal in JES))

    def assert_old_fields_preserved(self, world, earned):
        state = world.countries[world.tag]
        # The new line may add its own fields, never erase earned old contracts.
        self.assertEqual({key: state[key] for key in earned}, earned)

    def _school_pair(self, route, kind):
        # All share genuine military entry history; the third has genuinely no
        # school participation. The second chooses a NEW witness despite the
        # same real old school and must independently earn the .75 review price.
        worlds = [school_world(route), school_world(route), military_world()]
        set_current(worlds[2])
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[2]))
        self.assertTrue(all(office(w)["occupancy"] == .8 and university(w)["occupancy"] == .8
                            for w in worlds))
        for index, world in enumerate(worlds):
            with self.subTest(school_route=route, reuse_witness=index == 0,
                              has_actual_school=index < 2):
                earned = stable_producer_proof(world)
                arc = court_arc(world.cat)
                play(world, arc, 1120, "court_open")
                before = cash(world)
                play(world, arc, 1121, "pay_petition")
                self.assertEqual(before - cash(world), 1000)
                event = native_deliver(world, arc, 1122)
                reuse = "reuse_coop_witness" if route == "cooperative" else "reuse_office_witness"
                self.assertEqual(option_legal(world, event, reuse), index < 2)
                self.assertTrue(option_legal(world, event, "new_professional_witness"))
                choose(world, arc, event, reuse if index == 0 else "new_professional_witness")
                self.assertEqual(world.countries[world.tag][P + "witness_kind"], kind if index == 0 else 1)
                play(world, arc, 1123, "sign_responsibility")
                play(world, arc, 1124, "court_read_reply")
                month(world, arc, 6)
                before = cash(world)
                play(world, arc, 1125, "pay_review")
                self.assertEqual(before - cash(world), 750 if index < 2 else 1000)
                close_after_payment(world, arc)
                self.assert_closed(world, 1)
                self.assert_old_fields_preserved(world, earned)

    def test_genuine_cooperative_school_and_absence_differ_in_professional_source_and_review_price(self):
        self._school_pair("cooperative", 2)

    def test_genuine_official_school_and_absence_differ_in_professional_source_and_review_price(self):
        self._school_pair("official", 3)

    def test_each_school_receipt_and_joint_component_is_needed_for_unpaid_privileges(self):
        common = (SCHOOL_L + "started", SCHOOL_L + "settled", SCHOOL_L + "outcome",
                  "ywc_kor_school_established", "ywc_kor_school_filing_fee_paid",
                  "ywc_kor_school_old_invoice_paid", "ywc_kor_school_old_account_read_2",
                  "ywc_kor_school_funding_decided", "ywc_kor_school_appointment_decided",
                  "ywc_kor_school_six_months_complete", "ywc_kor_school_employer_confirmed")
        for route, paid in (("cooperative", "ywc_kor_school_coop_paid"),
                            ("official", "ywc_kor_school_office_paid")):
            for missing in (*common, paid):
                with self.subTest(route=route, missing=missing):
                    world = school_world(route)
                    state = world.countries[world.tag]
                    del state[missing]
                    arc = court_arc(world.cat)
                    play(world, arc, 1120, "court_open")
                    play(world, arc, 1121, "pay_petition")
                    event = native_deliver(world, arc, 1122)
                    reuse = "reuse_coop_witness" if route == "cooperative" else "reuse_office_witness"
                    self.assertFalse(option_legal(world, event, reuse))
                    choose(world, arc, event, "new_professional_witness")
                    play(world, arc, 1123, "sign_responsibility")
                    play(world, arc, 1124, "court_read_reply")
                    month(world, arc, 6)
                    before = cash(world)
                    play(world, arc, 1125, "pay_review")
                    self.assertEqual(before - cash(world), 1000)
                    close_after_payment(world, arc)
                    self.assert_closed(world, 1)

    def test_school_sources_keep_their_stricter_current_employer_threshold(self):
        for route in ("cooperative", "official"):
            with self.subTest(route=route):
                world = school_world(route)
                set_current(world, "local")
                arc = court_arc(world.cat)
                play(world, arc, 1120, "local_delegates")
                play(world, arc, 1121, "pay_petition")
                event = native_deliver(world, arc, 1122)
                reuse = "reuse_coop_witness" if route == "cooperative" else "reuse_office_witness"
                self.assertTrue(option_legal(world, event, reuse))
                source_post = university(world) if route == "cooperative" else office(world)
                source_post["occupancy"] = .79
                self.assertFalse(option_legal(world, event, reuse))
                # An otherwise legal fresh professional is still .8 in the other
                # workplace; this is no invented whole-contract .5 discount.
                self.assertTrue(option_legal(world, event, "new_professional_witness"))
                source_post["occupancy"] = .8
                choose(world, arc, event, reuse)
                play(world, arc, 1123, "sign_responsibility")
                play(world, arc, 1124, "local_open_reply")
                month(world, arc, 6)
                finish(world, arc)
                self.assert_closed(world, 1)

    def test_same_current_local_facts_real_written_revenue_changes_both_fees(self):
        worlds = [revenue_world(), new_world("local")]
        set_current(worlds[1], "local")
        self.assertEqual(current_snapshot(worlds[0]), current_snapshot(worlds[1]))
        for index, world in enumerate(worlds):
            earned = stable_producer_proof(world)
            arc = court_arc(world.cat)
            play(world, arc, 1120, "local_delegates")
            before = cash(world)
            play(world, arc, 1121, "pay_petition")
            self.assertEqual(before - cash(world), 1000 if index == 0 else 2000)
            play(world, arc, 1122, "new_professional_witness")
            play(world, arc, 1123, "sign_responsibility")
            play(world, arc, 1124, "local_open_reply")
            month(world, arc, 6)
            before = cash(world)
            play(world, arc, 1125, "pay_review")
            self.assertEqual(before - cash(world), 1000 if index == 0 else 1500)
            close_after_payment(world, arc)
            self.assert_closed(world, 1)
            self.assert_old_fields_preserved(world, earned)

    def test_each_earned_written_revenue_component_is_needed_at_the_unpaid_first_bill(self):
        fields = (REVENUE_L + "started", REVENUE_L + "settled", REVENUE_L + "outcome",
                  RP + "outcome", RP + "charter_paid", RP + "charter_paid_amount",
                  RP + "review_paid", RP + "review_paid_amount", RP + "review_mature",
                  RP + "charter_pilot", RP + "reviewer_pilot", RP + "charter_mode", RP + "charter_target")
        for missing in fields:
            with self.subTest(missing=missing):
                world = revenue_world()
                arc = court_arc(world.cat)
                play(world, arc, 1120, "local_delegates")
                event = native_deliver(world, arc, 1121)
                state = world.countries[world.tag]
                set_cash(world, 1000)
                self.assertTrue(option_legal(world, event, "pay_petition"))
                del state[missing]
                self.assertFalse(option_legal(world, event, "pay_petition"))
                before = copy.deepcopy((state, world.treasury, world.active, world.history))
                force_option(world, event, "pay_petition")
                self.assertEqual((state, world.treasury, world.active, world.history), before)
                set_cash(world, 100000)
                before = cash(world)
                choose(world, arc, event, "pay_petition")
                self.assertEqual(before - cash(world), 2000)
                play(world, arc, 1122, "new_professional_witness")
                play(world, arc, 1123, "sign_responsibility")
                play(world, arc, 1124, "local_open_reply")
                month(world, arc, 6)
                before = cash(world)
                play(world, arc, 1125, "pay_review")
                self.assertEqual(before - cash(world), 1500)
                close_after_payment(world, arc)
                self.assert_closed(world, 1)

        for current_loss in ("written_tax", "school_investment"):
            with self.subTest(current_old_terms=current_loss):
                world = revenue_world()
                arc = court_arc(world.cat)
                play(world, arc, 1120, "local_delegates")
                event = native_deliver(world, arc, 1121)
                state = world.countries[world.tag]
                if current_loss == "written_tax":
                    state["laws"].remove("law_proportional_taxation")
                    state["laws"].append("law_land_based_taxation")
                else:
                    state["institutions"]["institution_schools"] = 0
                self.assertFalse(world.conditions(world.trigger_defs[RP + "full_conditions"], world.tag))
                set_cash(world, 1000)
                self.assertFalse(option_legal(world, event, "pay_petition"))
                before = copy.deepcopy((state, world.treasury, world.active, world.history))
                force_option(world, event, "pay_petition")
                self.assertEqual((state, world.treasury, world.active, world.history), before)

    def test_adopted_school_source_is_rechecked_at_signature_reply_and_paid_late_setback(self):
        for route in ("cooperative", "official"):
            for lose_at in (1123, 1124, 1126):
                with self.subTest(route=route, lose_at=lose_at):
                    world = school_world(route)
                    reuse = "reuse_coop_witness" if route == "cooperative" else "reuse_office_witness"
                    arc = open_through_witness(world, witness=reuse)
                    if lose_at >= 1124:
                        play(world, arc, 1123, "sign_responsibility")
                    if lose_at == 1126:
                        play(world, arc, 1124, "court_read_reply")
                        month(world, arc, 6)
                        play(world, arc, 1125, "pay_review")
                    event = native_deliver(world, arc, lose_at)
                    state = world.countries[world.tag]
                    paid = cash(world)
                    del state["ywc_kor_school_old_account_read_2"]
                    action = {1123: "sign_responsibility", 1124: "court_read_reply", 1126: "request_full"}[lose_at]
                    self.assertFalse(option_legal(world, event, action))
                    before = copy.deepcopy((state, world.treasury, world.active, world.history))
                    force_option(world, event, action)
                    self.assertEqual((state, world.treasury, world.active, world.history), before)
                    if lose_at == 1126:
                        choose(world, arc, event, "request_setback")
                        play(world, arc, 1127, "close_setback")
                        self.assert_closed(world, 3)
                    else:
                        choose(world, arc, event, "withdraw")
                        self.assert_closed(world, 4)
                    self.assertEqual(cash(world), paid)

        for route in ("cooperative", "official"):
            with self.subTest(price_source=route, fresh_witness=True):
                world = school_world(route)
                arc = ready(world, witness="new_professional_witness")
                month(world, arc, 6)
                before = cash(world)
                play(world, arc, 1125, "pay_review")
                self.assertEqual(before - cash(world), 750)
                event = native_deliver(world, arc, 1126)
                state = world.countries[world.tag]
                paid = cash(world)
                # The occupational witness remains valid; only the independently
                # adopted discounted school source loses an ordinary current fact.
                if route == "cooperative":
                    university(world)["occupancy"] = .79
                else:
                    state["institutions"]["institution_schools"] = 0
                self.assertFalse(option_legal(world, event, "request_full"))
                self.assertTrue(option_legal(world, event, "request_setback"))
                choose(world, arc, event, "request_setback")
                play(world, arc, 1127, "close_setback")
                self.assert_closed(world, 3)
                self.assertEqual(cash(world), paid)

    def test_adopted_revenue_source_and_current_original_post_remain_live_before_and_after_payment(self):
        for lose_at in (1123, 1126):
            for loss in ("earned_amount", "old_school_investment", "owner"):
                with self.subTest(lose_at=lose_at, loss=loss):
                    world = revenue_world()
                    arc = open_through_witness(world, "local")
                    if lose_at == 1126:
                        play(world, arc, 1123, "sign_responsibility")
                        play(world, arc, 1124, "local_open_reply")
                        month(world, arc, 6)
                        play(world, arc, 1125, "pay_review")
                    event = native_deliver(world, arc, lose_at)
                    state = world.countries[world.tag]
                    paid = cash(world)
                    if loss == "earned_amount":
                        del state[RP + "review_paid_amount"]
                    elif loss == "old_school_investment":
                        state["institutions"]["institution_schools"] = 0
                    else:
                        state["states"][0]["owner"] = "CHI"
                    action = "sign_responsibility" if lose_at == 1123 else "request_full"
                    self.assertFalse(option_legal(world, event, action))
                    if lose_at == 1126:
                        choose(world, arc, event, "request_setback")
                        play(world, arc, 1127, "close_setback")
                        self.assert_closed(world, 3)
                    else:
                        choose(world, arc, event, "withdraw")
                        self.assert_closed(world, 4)
                    self.assertEqual(cash(world), paid)

        # Same saved old StateRef cannot lend a contract to a new owned pilot.
        states = current_facts("local")["states"]
        second = copy.deepcopy(states[0])
        second["region"] = "s:STATE_BUSAN"
        states.append(second)
        world = revenue_world(states=states)
        state = world.countries[world.tag]
        original = state[RP + "pilot_state"]
        original_state = next(row for row in state["states"] if row["_sid"] == original.sid)
        original_state["owner"] = "CHI"
        remaining = next(row for row in state["states"] if row["owner"] == "KOR")
        arc = court_arc(world.cat)
        play(world, arc, 1120, "local_delegates")
        self.assertEqual(state[RP + "pilot_state"], original)
        self.assertEqual(state[P + "pilot_state"], StateRef(remaining["_sid"]))
        self.assertNotEqual(state[P + "pilot_state"], original)
        before = cash(world)
        play(world, arc, 1121, "pay_petition")
        self.assertEqual(before - cash(world), 2000)
        play(world, arc, 1122, "new_professional_witness")
        play(world, arc, 1123, "sign_responsibility")
        play(world, arc, 1124, "local_open_reply")
        month(world, arc, 6)
        before = cash(world)
        play(world, arc, 1125, "pay_review")
        self.assertEqual(before - cash(world), 1500)
        close_after_payment(world, arc)
        self.assert_closed(world, 1)

    def test_real_old_finite_withdrawn_other_policy_and_absence_have_current_finite_exit(self):
        for previous in ("finite_revenue", "withdrawn_school", "central_revenue", "absent"):
            with self.subTest(previous=previous):
                world = new_world()
                state = world.countries[world.tag]
                if previous == "finite_revenue":
                    earn_revenue(world, limited=True)
                    self.assertEqual(state[REVENUE_L + "outcome"], 2)
                elif previous == "withdrawn_school":
                    world = military_world()
                    state = world.countries[world.tag]
                    native_play(world, arc_for(world, SCHOOL), 1010, "withdraw")
                    self.assertEqual(state[SCHOOL_L + "outcome"], 4)
                elif previous == "central_revenue":
                    earn_revenue(world, "central")
                    self.assertEqual((state[RP + "mode"], state[RP + "outcome"]), (2, 1))
                set_current(world, bare=True)
                earned = stable_producer_proof(world)
                before = cash(world)
                arc = ready(world, limited=True)
                month(world, arc, 6)
                finish(world, arc, 2)
                self.assertEqual(before - cash(world), 1000)
                self.assert_old_fields_preserved(world, earned)
                self.assert_closed(world, 2)

    def test_real_outstanding_military_installments_continue_and_are_not_cleared_by_new_court(self):
        world = new_world()
        world.modifiers.append((world.tag, {"modifier": "military_wages_medium"}))
        military = arc_for(world, "v03_kor_military_accounts")
        for number, key in ((1000, "court_supply"), (1001, "pay_month"), (1002, "court_roll"),
                            (1003, "publish"), (1004, "fund_local"), (1005, "fund_transition"),
                            (1006, "withdraw")):
            native_play(world, military, number, key)
        state = world.countries[world.tag]
        before = {kind: state["ywc_kor_" + kind + "_contract_paid_months"]
                  for kind in ("translation", "veteran")}
        self.assertTrue(any(count < 12 for count in before.values()))
        set_current(world)
        contract_keys = {key: copy.deepcopy(value) for key, value in state.items()
                         if key.startswith(("ywc_kor_translation_contract_", "ywc_kor_veteran_contract_"))
                         and not key.endswith("paid_months")}
        arc = ready(world)
        month(world, arc, 6)
        finish(world, arc)
        self.assert_closed(world, 1)
        for kind, count in before.items():
            self.assertGreaterEqual(state["ywc_kor_" + kind + "_contract_paid_months"], count)
            self.assertEqual(state["ywc_kor_" + kind + "_contract_paid_months"], 12)
        self.assertEqual({key: state[key] for key in contract_keys}, contract_keys)
        self.assertTrue(any(row["cash_delta"] < 0 for row in world.earned_monthly_ledger
                            if any(old < new for old, new in zip(row["before"], row["after"]))))


if __name__ == "__main__":
    unittest.main()

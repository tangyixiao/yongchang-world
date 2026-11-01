"""Permanent reached-review contracts; execute only after root's calendar gate.

Positive business history always comes from real old producers, event choices,
country callbacks and journal pulses. Only explicit negative proof cases alter
an already earned flag/amount/streak. No production/runtime helper is replaced.
"""
import copy
import unittest

from clausewitz_harness import parse
from test_v03_shu_rural_workshop import (
    P, L, new_world, workshop_arc, state, pilot, office, cash, choose,
    force_option, option_legal, play, deliver, month, ready_for_review,
    through_witness, reached,
)
from test_v03_shu_rural_cross_era import fiscal_world, province_world

T = "ywc_shu_v03_workshop_"


def current(world, suffix):
    return world.conditions(world.trigger_defs[T + suffix], world.tag)


def snapshot(world):
    return copy.deepcopy((state(world), world.treasury, world.active, world.history))


def paid_context(limited=False):
    world = new_world(bare=limited)
    arc = ready_for_review(world, limited=limited)
    month(world, arc, 6)
    play(world, arc, 1115, "pay_survey")
    event = deliver(world, arc, 1116)
    s = state(world)
    amount = 500 if limited else 1000
    assert s[P + "admin_paid"] == s[P + "survey_paid"] == 1
    assert s[P + "admin_paid_amount"] == s[P + "survey_paid_amount"] == amount
    assert s[P + "review_streak"] == 6 and s[P + "review_mature"] == 1
    return world, arc, event


def corrupt_earned(world, field, value):
    """Negative only: the unchanged context must already contain the field."""
    s = state(world)
    assert P + field in s, ("negative_field_was_not_earned", field)
    if value is None:
        del s[P + field]
    else:
        s[P + field] = value


def observed_calendar_month(world):
    """Read the existing native script value, not a duplicate Python calendar.

    This scratch observation variable has no business/queue/receipt meaning;
    remove it immediately after the native value evaluator supplies the result.
    """
    marker = "literal_rural_review_regression_observed_month"
    assert marker not in state(world)
    world.execute(parse("set_variable = { name = " + marker +
                        " value = ywc_nmg_current_calendar_month }"), world.tag)
    return state(world).pop(marker)


class ShuRuralReviewRegressions(unittest.TestCase):
    def assert_closed(self, world, outcome):
        s = state(world)
        self.assertEqual((s[P + "outcome"], s[L + "outcome"], s[L + "settled"]),
                         (outcome, outcome, 1))

    def assert_rejected_inert(self, world, event, action):
        self.assertFalse(option_legal(world, event, action))
        before = snapshot(world)
        force_option(world, event, action)
        self.assertEqual(snapshot(world), before)

    def test_requests_and_paid_advance_require_exact_both_fees_and_six_fresh_months(self):
        negatives = [(bill + suffix, value)
                     for bill in ("admin", "survey")
                     for suffix, values in (("_paid", (None, 0, 2)),
                                            ("_paid_amount", (None, 0)))
                     for value in values]
        negatives += [("review_streak", 5), ("review_streak", 0)]
        for limited in (False, True):
            base, arc, event = paid_context(limited)
            request = "request_limited" if limited else "request_full"
            self.assertTrue(option_legal(base, event, request))
            for field, value in negatives:
                with self.subTest(boundary="request", limited=limited, field=field, value=value):
                    w = copy.deepcopy(base)
                    corrupt_earned(w, field, value)
                    self.assert_rejected_inert(w, event, request)
            # Recount is a real earned transition, then six actual fresh months.
            choose(base, arc, event, "recount_1115")
            self.assertEqual(state(base)[P + "review_streak"], 0)
            month(base, arc, 5)
            self.assertNotIn(P + "review_mature", state(base))
            month(base, arc)
            paid_event = deliver(base, arc, 1115)
            self.assertTrue(option_legal(base, paid_event, "advance_paid_review"))
            for field, value in negatives:
                with self.subTest(boundary="free_advance", limited=limited, field=field, value=value):
                    w = copy.deepcopy(base)
                    corrupt_earned(w, field, value)
                    self.assert_rejected_inert(w, paid_event, "advance_paid_review")
            balance = cash(base)
            choose(base, arc, paid_event, "advance_paid_review")
            self.assertEqual(cash(base), balance)
            play(base, arc, 1116, request)
            play(base, arc, 1117, "close_limited" if limited else "close_full")
            self.assert_closed(base, 2 if limited else 1)

    def test_acceptance_and_survey_bill_recheck_current_witness_and_adopted_source(self):
        for witness in ("new", "fiscal", "province"):
            for number in (1114, 1115):
                with self.subTest(witness=witness, number=number):
                    w = (new_world() if witness == "new" else fiscal_world()
                         if witness == "fiscal" else province_world(False))
                    key = {"new": "new_witness", "fiscal": "reuse_fiscal_witness",
                           "province": "reuse_province_witness"}[witness]
                    arc = through_witness(w, witness=key)
                    play(w, arc, 1113, "sign_responsibility")
                    if number == 1115:
                        play(w, arc, 1114, "record_rural_duties")
                        month(w, arc, 6)
                    event = deliver(w, arc, number)
                    action = "record_rural_duties" if number == 1114 else "pay_survey"
                    self.assertTrue(option_legal(w, event, action))
                    if witness == "new":
                        building = office(w)
                        original = building["occupancy"]
                        building["occupancy"] = .79  # Ordinary current loss; policy .5 still holds.
                    else:
                        # Explicit negative on a genuinely earned source; not an
                        # allegation that normal gameplay erases the old receipt.
                        field = ("ywc_shu_local_audit_right" if witness == "fiscal"
                                 else "ywc_shu_prov_share_terms")
                        self.assertEqual(state(w)[field], 1)
                        original = state(w).pop(field)
                    self.assertTrue(current(w, "target_current"))
                    self.assertFalse(current(w, "witness_duty"))
                    self.assert_rejected_inert(w, event, action)
                    if witness == "new":
                        building["occupancy"] = original
                    else:
                        state(w)[field] = original  # Restore only the removed earned proof.
                    self.assertTrue(option_legal(w, event, action))
                    balance = cash(w)
                    choose(w, arc, event, action)
                    self.assertEqual(balance - cash(w), 0 if number == 1114 else 1000)
                    self.assertEqual(state(w)[P + "stage"], number + 1)

    def test_vanished_original_preserves_earned_honest_setback_without_replacing_state(self):
        for limited in (False, True):
            with self.subTest(limited=limited):
                w, arc, event = paid_context(limited)
                original = pilot(w)
                state(w)["states"].remove(original)
                self.assertFalse(current(w, "pilot_owned"))
                self.assertFalse(option_legal(w, event, "request_limited" if limited else "request_full"))
                self.assertTrue(current(w, "identity_earned"))
                self.assertTrue(option_legal(w, event, "request_setback"))
                choose(w, arc, event, "request_setback")
                final = deliver(w, arc, 1117)
                self.assertTrue(option_legal(w, final, "close_setback"))
                # Reintroduce the same original object, never a same-region substitute.
                state(w)["states"].append(original)
                self.assert_rejected_inert(w, final, "close_setback")
                state(w)["states"].remove(original)
                choose(w, arc, final, "close_setback")
                self.assert_closed(w, 3)

    def test_normal_wait_requeues_the_actual_own_stage_and_can_continue(self):
        w = new_world()
        arc = workshop_arc(w.cat)
        play(w, arc, 1110, "rural_processing")
        event = deliver(w, arc, 1111)
        balance = cash(w)
        choose(w, arc, event, "wait_at_1111")
        self.assertEqual(state(w)[P + "stage"], 1111)
        # A successful later native delivery proves continuation, independently
        # of whether requeue happens immediately or on a subsequent real pulse.
        again = deliver(w, arc, 1111)
        self.assertEqual(cash(w), balance)
        self.assertTrue(option_legal(w, again, "pay_admin"))
        choose(w, arc, again, "pay_admin")
        self.assertEqual(balance - cash(w), 1000)
        self.assertEqual(state(w)[P + "stage"], 1112)

    def test_wait_at_each_native_stage_redelivers_without_charging_or_advancing(self):
        for number in range(1110, 1118):
            with self.subTest(stage=number):
                w = new_world()
                arc, event = reached(w, number)
                action = f"wait_at_{number}"
                self.assertTrue(option_legal(w, event, action))
                balance = cash(w)
                choose(w, arc, event, action)
                self.assertEqual(state(w)[P + "stage"], number)
                again = deliver(w, arc, number)
                self.assertTrue(option_legal(w, again, action))
                self.assertEqual(state(w)[P + "stage"], number)
                self.assertEqual(cash(w), balance)

    def test_unpaid_interruption_restart_reaches_a_new_real_survey_request(self):
        w = new_world()
        arc = ready_for_review(w)
        month(w, arc, 2)
        building = office(w)
        original = building["occupancy"]
        building["occupancy"] = .79
        month(w, arc)
        self.assertIn(P + "review_interrupted", state(w))
        event = deliver(w, arc, 1115)
        building["occupancy"] = original
        self.assertTrue(option_legal(w, event, "restart_review"))
        choose(w, arc, event, "restart_review")
        self.assertEqual(state(w)[P + "review_streak"], 0)
        month(w, arc, 5)
        self.assertNotIn(P + "review_mature", state(w))
        month(w, arc)
        self.assertEqual(state(w)[P + "review_streak"], 6)
        survey = deliver(w, arc, 1115)
        balance = cash(w)
        choose(w, arc, survey, "pay_survey")
        self.assertEqual(balance - cash(w), 1000)
        play(w, arc, 1116, "request_full")
        play(w, arc, 1117, "close_full")
        self.assert_closed(w, 1)

    def test_same_calendar_month_repeated_callbacks_never_earn_extra_observations(self):
        w = new_world()
        arc = ready_for_review(w)
        initial = observed_calendar_month(w)
        # Move naturally to the next calendar month, then make one real pulse.
        # Starting its first day avoids a boundary crossing in the duplicate loop.
        for _ in range(32):
            w.advance_days(1)
            if observed_calendar_month(w) != initial:
                break
        else:
            self.fail("accepted calendar prerequisite did not advance within32days")
        month_id = observed_calendar_month(w)
        w.pulse(arc)
        baseline = state(w)[P + "review_streak"]
        w.pulse(arc)
        self.assertEqual(state(w)[P + "review_streak"], baseline)
        observations = []
        for _ in range(6):
            w.advance_days(2)
            self.assertEqual(observed_calendar_month(w), month_id)
            w.pulse(arc)
            observations.append(state(w)[P + "review_streak"])
        self.assertEqual(observations, [baseline] * 6)
        self.assertNotIn(P + "review_mature", state(w))

    def test_honest_setback_requires_exact_paid_and_six_month_history_after_current_loss(self):
        negatives = [("admin_paid", 0), ("survey_paid", 0),
                     ("admin_paid_amount", None), ("admin_paid_amount", 0),
                     ("survey_paid_amount", None), ("survey_paid_amount", 0),
                     ("review_streak", 5), ("review_streak", 0)]
        for limited in (False, True):
            base, arc, event = paid_context(limited)
            state(base)["is_at_war"] = True
            self.assertTrue(option_legal(base, event, "request_setback"))
            for field, value in negatives:
                with self.subTest(limited=limited, field=field, value=value):
                    w = copy.deepcopy(base)
                    corrupt_earned(w, field, value)
                    self.assert_rejected_inert(w, event, "request_setback")
            choose(base, arc, event, "request_setback")
            final = deliver(base, arc, 1117)
            self.assertTrue(option_legal(base, final, "close_setback"))
            state(base)["is_at_war"] = False
            self.assert_rejected_inert(base, final, "close_setback")
            state(base)["is_at_war"] = True
            choose(base, arc, final, "close_setback")
            self.assert_closed(base, 3)

    def test_zero_maturity_cannot_pay_request_advance_or_close(self):
        for limited in (False, True):
            with self.subTest(limited=limited, boundary="survey"):
                w = new_world(bare=limited)
                arc = ready_for_review(w, limited=limited)
                month(w, arc, 6)
                event = deliver(w, arc, 1115)
                self.assertEqual(state(w)[P + "review_mature"], 1)
                state(w)[P + "review_mature"] = 0
                self.assert_rejected_inert(w, event, "pay_survey")
            for setback in (False, True):
                with self.subTest(limited=limited, setback=setback, boundary="request_close"):
                    w, arc, event = paid_context(limited)
                    if setback:
                        state(w)["is_at_war"] = True
                    suffix = "setback" if setback else ("limited" if limited else "full")
                    request = "request_" + suffix
                    self.assertTrue(option_legal(w, event, request))
                    bad = copy.deepcopy(w)
                    state(bad)[P + "review_mature"] = 0
                    self.assert_rejected_inert(bad, event, request)
                    choose(w, arc, event, request)
                    final = deliver(w, arc, 1117)
                    self.assertTrue(option_legal(w, final, "close_" + suffix))
                    state(w)[P + "review_mature"] = 0
                    self.assert_rejected_inert(w, final, "close_" + suffix)
            w, arc, event = paid_context(limited)
            choose(w, arc, event, "recount_1115")
            month(w, arc, 6)
            event = deliver(w, arc, 1115)
            self.assertTrue(option_legal(w, event, "advance_paid_review"))
            state(w)[P + "review_mature"] = 0
            self.assert_rejected_inert(w, event, "advance_paid_review")

    def test_foreign_snapshot_of_same_region_cannot_finalize_full_or_finite(self):
        for limited in (False, True):
            base, arc, event = paid_context(limited)
            suffix = "limited" if limited else "full"
            for field in ("handler_pilot", "witness_pilot", "sign_pilot", "accept_pilot", "review_pilot"):
                with self.subTest(limited=limited, field=field):
                    w = copy.deepcopy(base)
                    other = copy.deepcopy(pilot(w))
                    state(w)["states"].append(other)
                    state(w)[P + field] = w._state_intern(other)
                    self.assert_rejected_inert(w, event, "request_" + suffix)
                    w = copy.deepcopy(base)
                    choose(w, arc, event, "request_" + suffix)
                    final = deliver(w, arc, 1117)
                    other = copy.deepcopy(pilot(w))
                    state(w)["states"].append(other)
                    state(w)[P + field] = w._state_intern(other)
                    self.assert_rejected_inert(w, final, "close_" + suffix)

    def test_foreign_snapshot_cannot_advance_an_already_paid_recount(self):
        for limited in (False, True):
            w, arc, event = paid_context(limited)
            choose(w, arc, event, "recount_1115")
            month(w, arc, 6)
            event = deliver(w, arc, 1115)
            self.assertTrue(option_legal(w, event, "advance_paid_review"))
            for field in ("handler_pilot", "witness_pilot", "sign_pilot", "accept_pilot", "review_pilot"):
                with self.subTest(limited=limited, field=field):
                    trial = copy.deepcopy(w)
                    other = copy.deepcopy(pilot(trial))
                    state(trial)["states"].append(other)
                    state(trial)[P + field] = trial._state_intern(other)
                    self.assert_rejected_inert(trial, event, "advance_paid_review")

    def test_zero_earned_old_proofs_block_new_survey_payment(self):
        for factory, witness, proof in (
            (fiscal_world, "reuse_fiscal_witness", "ywc_shu_first_audit"),
            (lambda: province_world(False), "reuse_province_witness", "ywc_shu_prov_meeting_fee_paid"),
        ):
            with self.subTest(proof=proof):
                w = factory()
                arc = through_witness(w, witness=witness)
                play(w, arc, 1113, "sign_responsibility")
                play(w, arc, 1114, "record_rural_duties")
                month(w, arc, 6)
                event = deliver(w, arc, 1115)
                self.assertTrue(option_legal(w, event, "pay_survey"))
                self.assertEqual(state(w)[proof], 1)
                state(w)[proof] = 0
                self.assert_rejected_inert(w, event, "pay_survey")

    def test_zero_in_each_genuinely_earned_old_boolean_invalidates_its_source(self):
        cases = (
            (fiscal_world, "fiscal_source_earned", (
                "ywc_v03_shu_v03_shu_fiscal_register_started", "ywc_shu_fiscal_outcome_provincial_share",
                "ywc_shu_register_resolved", "ywc_shu_first_audit", "ywc_shu_second_audit",
                "ywc_shu_settlement_review_mature", "ywc_shu_local_audit_right",
                "ywc_shu_merchant_advance_refused")),
            (lambda: province_world(False), "province_source_earned", (
                "ywc_shu_prov_charter_ready", "ywc_shu_prov_share_terms", "ywc_shu_prov_review_mature",
                "ywc_shu_prov_relief_local", "ywc_shu_prov_meeting_fee_paid")),
            (lambda: province_world(True), "province_source_earned", ("ywc_shu_prov_meeting_fee_waived",)),
            (lambda: province_world(False, national=True), "province_source_earned", ("ywc_shu_prov_relief_paid",)),
        )
        for factory, source, proofs in cases:
            base = factory()
            through_witness(base, witness="reuse_fiscal_witness" if source == "fiscal_source_earned" else "reuse_province_witness")
            self.assertTrue(current(base, source))
            for proof in proofs:
                with self.subTest(source=source, proof=proof):
                    w = copy.deepcopy(base)
                    self.assertEqual(state(w)[proof], 1)
                    state(w)[proof] = 0
                    self.assertFalse(current(w, source))

    def test_same_day_current_loss_interrupts_running_and_unpaid_mature_history(self):
        for count in (2, 6):
            with self.subTest(months=count):
                w = new_world()
                arc = ready_for_review(w)
                month(w, arc, count)
                self.assertEqual(state(w)[P + "review_streak"], count)
                self.assertIn(P + "review_ticked", state(w))
                office(w)["occupancy"] = .79
                w.pulse(arc)
                self.assertEqual(state(w)[P + "review_streak"], 0)
                self.assertNotIn(P + "review_mature", state(w))
                self.assertNotIn(P + "review_running", state(w))
                self.assertEqual(state(w)[P + "review_interrupted"], 1)
                office(w)["occupancy"] = 1
                month(w, arc, 4)
                self.assertNotIn(P + "review_mature", state(w))
        w = new_world()
        arc = ready_for_review(w)
        w.pulse(arc)
        self.assertEqual(state(w)[P + "review_streak"], 0)

    def test_setback_rejects_live_mismatched_earned_state_but_allows_actual_loss(self):
        for limited in (False, True):
            base, arc, event = paid_context(limited)
            state(base)["is_at_war"] = True
            self.assertTrue(option_legal(base, event, "request_setback"))
            for role in ("handler", "witness", "sign", "accept", "review"):
                with self.subTest(limited=limited, role=role, boundary="request"):
                    w = copy.deepcopy(base)
                    other = copy.deepcopy(pilot(w))
                    state(w)["states"].append(other)
                    state(w)[P + role + "_pilot"] = w._state_intern(other)
                    self.assert_rejected_inert(w, event, "request_setback")
                with self.subTest(limited=limited, role=role, boundary="close"):
                    w = copy.deepcopy(base)
                    choose(w, arc, event, "request_setback")
                    final = deliver(w, arc, 1117)
                    other = copy.deepcopy(pilot(w))
                    state(w)["states"].append(other)
                    state(w)[P + role + "_pilot"] = w._state_intern(other)
                    self.assert_rejected_inert(w, final, "close_setback")
            w, arc, event = paid_context(limited)
            original = pilot(w)
            state(w)["states"].remove(original)
            self.assertTrue(option_legal(w, event, "request_setback"))
            choose(w, arc, event, "request_setback")
            self.assertTrue(option_legal(w, deliver(w, arc, 1117), "close_setback"))

    def test_zero_old_started_or_settled_proof_cannot_authorize_survey(self):
        for factory, witness, proof in (
            (fiscal_world, "reuse_fiscal_witness", "ywc_v03_shu_v03_shu_fiscal_register_settled"),
            (lambda: province_world(False), "reuse_province_witness", "ywc_v03_shu_v03_shu_provincial_contract_started"),
            (lambda: province_world(False), "reuse_province_witness", "ywc_v03_shu_v03_shu_provincial_contract_settled"),
        ):
            with self.subTest(proof=proof):
                w = factory()
                arc = through_witness(w, witness=witness)
                play(w, arc, 1113, "sign_responsibility")
                play(w, arc, 1114, "record_rural_duties")
                month(w, arc, 6)
                event = deliver(w, arc, 1115)
                self.assertTrue(option_legal(w, event, "pay_survey"))
                self.assertEqual(state(w)[proof], 1)
                state(w)[proof] = 0
                self.assert_rejected_inert(w, event, "pay_survey")


if __name__ == "__main__":
    unittest.main()

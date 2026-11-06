"""SHU fiscal payer and debt carried through authored service events."""
import copy
import unittest

from clausewitz_harness import parse
from test_v03_shu_military_funding import reached_military, month, legal
from test_v03_shu_merchant_obligations import replay_effect


def step(world, arc, number, key):
    event = world.deliver(arc, "ywc_shu." + str(number))
    world.choose(arc, event, key, contexts=False)
    return event


def finish_fiscal(payer_choice):
    world, arc, event = reached_military()
    world.choose(arc, event, payer_choice, contexts=False)
    for number, key in ((1004, "local_mediation"), (1005, "refuse_private_advance"),
                        (1006, "settle_as_provincial"), (1007, "provincial_retention")):
        step(world, arc, number, key)
    world.advance_months(6); world.elapsed_months += 6
    step(world, arc, 1008, "review_in_peace")
    step(world, arc, 1009, "confirm_provincial_share")
    return world, world.cat["arcs"][1]


def service_to_compact(world, arc, seal="court_seal"):
    for number, key in ((1010, seal), (1011, "cap_arrears"), (1012, "professional_list")):
        step(world, arc, number, key)
    return world.deliver(arc, "ywc_shu.1013")


class ShuFundingCarryoverTests(unittest.TestCase):
    def test_fiscal_payer_changes_two_later_fees_without_fake_payment(self):
        results = {}
        for payer in ("budget_queue", "provincial_pay"):
            with self.subTest(payer=payer):
                world, arc = finish_fiscal(payer); state = world.countries["SHU"]
                compact = service_to_compact(world, arc)
                before = world.treasury["SHU"]
                world.choose(arc, compact, "provincial_compact", contexts=False)
                first_delta = world.treasury["SHU"] - before
                if payer == "provincial_pay":
                    self.assertEqual(state.get("ywc_shu_service_compact_fee_waived"), 1)
                    self.assertEqual(state.get("ywc_shu_service_local_voice"), 1)
                supply = world.deliver(arc, "ywc_shu.1014")
                before = world.treasury["SHU"]
                world.choose(arc, supply, "pay_local_share", contexts=False)
                second_delta = world.treasury["SHU"] - before
                self.assertEqual(state.get("ywc_shu_service_local_share"), 1)
                if payer == "provincial_pay":
                    self.assertEqual(state.get("ywc_shu_service_local_share_waived"), 1)
                    self.assertNotIn("ywc_shu_service_local_paid", state)
                else:
                    self.assertEqual(state.get("ywc_shu_service_local_paid"), 1)
                    self.assertNotIn("ywc_shu_service_local_share_waived", state)
                results[payer] = (first_delta, second_delta)
        self.assertEqual(results["budget_queue"], (-250, -250))
        self.assertEqual(results["provincial_pay"], (0, 0))

    def test_loss_of_fiscal_local_right_before_choice_does_not_waive_fee(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        state.pop("ywc_shu_local_audit_right")
        before = world.treasury["SHU"]
        world.choose(arc, compact, "provincial_compact", contexts=False)
        self.assertEqual(world.treasury["SHU"] - before, -250)
        self.assertNotIn("ywc_shu_service_compact_fee_waived", state)

    def test_lost_fiscal_pilot_does_not_supply_an_automatic_fee_waiver(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        state["gold_reserves"] = 0
        self.assertTrue(legal(world, compact, "provincial_compact"))
        other = copy.deepcopy(state["states"][0]); other["region"] = "s:STATE_CHONGQING"
        state["states"].append(other); state["states"][0]["owned"] = False
        self.assertFalse(legal(world, compact, "provincial_compact"))
        before = world.treasury["SHU"]
        replay_effect(world, compact, "provincial_compact")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_service_compact_fee_waived", state)
        self.assertNotIn("ywc_shu_service_contract_active", state)

    def test_fiscal_right_and_cash_lost_after_display_cannot_record_a_compact(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        state["gold_reserves"] = 0
        self.assertTrue(legal(world, compact, "provincial_compact"))
        state.pop("ywc_shu_local_audit_right")
        before = world.treasury["SHU"]
        replay_effect(world, compact, "provincial_compact")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_service_route", state)
        self.assertNotIn("ywc_shu_service_contract_active", state)
        self.assertNotIn("ywc_shu_service_route_recorded", state)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1013)

    def test_local_right_and_cash_lost_at_supply_choice_requeues_without_waiver(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        state["gold_reserves"] = 0
        self.assertTrue(legal(world, supply, "pay_local_share"))
        state.pop("ywc_shu_local_audit_right")
        before = world.treasury["SHU"]
        replay_effect(world, supply, "pay_local_share")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_service_local_paid", state)
        self.assertNotIn("ywc_shu_service_local_share_waived", state)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1014)

    def test_stale_local_share_cannot_charge_or_rewind_a_later_queue(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "pay_local_share", contexts=False)
        later = world.deliver(arc, "ywc_shu.1015")
        world.choose(arc, later, "vacant_cap", contexts=False)
        before = (world.treasury["SHU"], state.get("ywc_shu_service_pending_event"))
        replay_effect(world, supply, "pay_local_share")
        self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_service_pending_event")), before)

    def test_old_local_share_after_a_different_supply_choice_cannot_charge(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        later = world.deliver(arc, "ywc_shu.1015")
        world.choose(arc, later, "vacant_cap", contexts=False)
        before = (world.treasury["SHU"], state.get("ywc_shu_service_pending_event"))
        replay_effect(world, supply, "pay_local_share")
        self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_service_pending_event")), before)
        self.assertNotIn("ywc_shu_service_local_paid", state)

    def test_withdrawn_local_right_requires_a_real_coordination_fee(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        state.pop("ywc_shu_local_audit_right")
        before = world.treasury["SHU"]
        world.choose(arc, supply, "pay_local_share", contexts=False)
        self.assertEqual(world.treasury["SHU"] - before, -250)
        self.assertEqual(state.get("ywc_shu_service_local_paid"), 1)
        self.assertNotIn("ywc_shu_service_local_share_waived", state)

    def test_all_stale_compact_choices_preserve_later_route_and_queue(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "pay_local_share", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        world.choose(arc, appointment, "vacant_cap", contexts=False)
        before = (world.treasury["SHU"], state.get("ywc_shu_service_pending_event"), state.get("ywc_shu_service_route"))
        for key in ("professional", "provincial_compact", "legacy_cap"):
            replay_effect(world, compact, key)
            self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_service_pending_event"), state.get("ywc_shu_service_route")), before)

    def test_unmarked_old_supply_popup_preserves_completed_supply_evidence(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        old_supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, old_supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        state.pop("ywc_shu_service_appointment_offer_open")  # legacy immediate had no marker
        self.assertTrue(legal(world, old_supply, "dismiss_stale_supply"))
        before = world.treasury["SHU"]
        world.choose(arc, old_supply, "dismiss_stale_supply", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1015)
        self.assertEqual(world.treasury["SHU"], before)

    def test_open_supply_is_not_automatically_delivered_twice(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        self.assertEqual(state.get("ywc_shu_service_local_offer_open"), 1)
        world.advance_months(5); world.elapsed_months += 5; world.pulse(arc)
        self.assertNotEqual(state.get("ywc_shu_service_pending_event"), 1014)
        self.assertNotIn(("SHU", "ywc_shu.1014"), world.events)
        self.assertTrue(legal(world, supply, "check_supply"))
        world.choose(arc, supply, "check_supply", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1015)

    def test_open_appointment_does_not_redeliver_supply_or_charge(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        before = world.treasury["SHU"]
        world.advance_months(5); world.elapsed_months += 5; world.pulse(arc)
        self.assertNotEqual(state.get("ywc_shu_service_pending_event"), 1014)
        self.assertNotIn(("SHU", "ywc_shu.1014"), world.events)
        replay_effect(world, supply, "pay_local_share")
        self.assertEqual(world.treasury["SHU"], before)
        world.choose(arc, appointment, "vacant_cap", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1016)

    def test_all_stale_supply_choices_leave_later_queue_and_route_unchanged(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "pay_local_share", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        world.choose(arc, appointment, "vacant_cap", contexts=False)
        before = (world.treasury["SHU"], state.get("ywc_shu_service_pending_event"), state.get("ywc_shu_service_route"))
        for key in ("check_supply", "reduce_target", "pay_local_share"):
            replay_effect(world, supply, key)
            self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_service_pending_event"), state.get("ywc_shu_service_route")), before)

    def test_conflicting_supply_queue_is_not_rewritten_by_appointment_resume(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        world.deliver(arc, "ywc_shu.1015")
        self.assertEqual(state.get("ywc_shu_service_appointment_offer_open"), 1)
        state["ywc_shu_service_pending_event"] = 1014  # a conflicting saved/replayed queue
        notice = world.event_defs["ywc_shu.1016"]
        self.assertTrue(legal(world, notice, "resume_service_appointments"))
        replay_effect(world, notice, "resume_service_appointments")
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1014)
        old_supply = world.deliver(arc, "ywc_shu.1014")
        self.assertTrue(legal(world, old_supply, "dismiss_stale_supply"))
        world.choose(arc, old_supply, "dismiss_stale_supply", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1015)

    def test_recovery_consumes_same_id_notice_and_normal_queues_safely(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        state["army_size"] = 0; world.pulse(arc)
        world.advance_months(13); world.elapsed_months += 13
        world.choose(arc, appointment, "vacant_cap", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1016)
        world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)
        notice = world.deliver(arc, "ywc_shu.1016")
        self.assertNotIn("ywc_shu_service_notice_pending_event", state)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1016)
        self.assertTrue(legal(world, notice, "resume_service_appointments"))
        world.choose(arc, notice, "resume_service_appointments", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1014)

    def test_notice_cancelled_after_popup_close_preserves_the_current_stage(self):
        for stage in ("compact", "supply", "appointment"):
            with self.subTest(stage=stage):
                world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
                compact = service_to_compact(world, arc, seal="garrison_seal")
                popup = compact; key = "dismiss_stale_compact"; expected = 1013
                if stage != "compact":
                    world.choose(arc, compact, "provincial_compact", contexts=False)
                    popup = world.deliver(arc, "ywc_shu.1014")
                    key = "dismiss_stale_supply"; expected = 1014
                if stage == "appointment":
                    world.choose(arc, popup, "check_supply", contexts=False)
                    popup = world.deliver(arc, "ywc_shu.1015")
                    key = "dismiss_stale_appointment"; expected = 1015
                buildings = state["states"][0]["buildings"]
                office = next(b for b in buildings if b["type"] == "building_government_administration")
                buildings.remove(office); world.pulse(arc)
                world.advance_months(13); world.elapsed_months += 13; world.pulse(arc)
                self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)
                self.assertTrue(legal(world, popup, key))
                world.choose(arc, popup, key, contexts=False)
                self.assertEqual(state.get("ywc_shu_service_pending_event"), expected)
                self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)
                buildings.append(office); world.pulse(arc)
                self.assertNotIn("ywc_shu_service_notice_pending_event", state)
                self.assertEqual(state.get("ywc_shu_service_pending_event"), expected)

    def test_notice_accept_cap_continues_from_all_three_open_stages(self):
        for stage in ("compact", "supply", "appointment"):
            with self.subTest(stage=stage):
                world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
                compact = service_to_compact(world, arc, seal="garrison_seal")
                popup = compact; key = "dismiss_stale_compact"
                if stage != "compact":
                    world.choose(arc, compact, "provincial_compact", contexts=False)
                    popup = world.deliver(arc, "ywc_shu.1014"); key = "dismiss_stale_supply"
                if stage == "appointment":
                    world.choose(arc, popup, "check_supply", contexts=False)
                    popup = world.deliver(arc, "ywc_shu.1015"); key = "dismiss_stale_appointment"
                buildings = state["states"][0]["buildings"]
                office = next(b for b in buildings if b["type"] == "building_government_administration")
                buildings.remove(office); world.pulse(arc)
                world.advance_months(13); world.elapsed_months += 13; world.pulse(arc)
                world.choose(arc, popup, key, contexts=False)
                notice = world.deliver(arc, "ywc_shu.1016")
                world.choose(arc, notice, "accept_cap", contexts=False)
                self.assertEqual(state.get("ywc_shu_service_route"), 3)
                self.assertEqual(state.get("ywc_shu_service_pending_event"), 1014)
                self.assertEqual(state.get("ywc_shu_service_contract_active"), 1)
                buildings.append(office)
                again = world.deliver(arc, "ywc_shu.1014")
                self.assertTrue(legal(world, again, "check_supply"))

    def test_recovery_notice_returns_to_unanswered_appointment(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        self.assertEqual(state.get("ywc_shu_service_appointment_offer_open"), 1)
        buildings = state["states"][0]["buildings"]
        office = next(b for b in buildings if b["type"] == "building_government_administration")
        buildings.remove(office); world.pulse(arc)
        world.advance_months(13); world.elapsed_months += 13
        notice = world.deliver(arc, "ywc_shu.1016")
        buildings.append(office)
        world.choose(arc, notice, "resume_service_appointments", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1015)
        replay = world.deliver(arc, "ywc_shu.1015")
        self.assertTrue(legal(world, replay, "accept_appointments"))

    def test_unmarked_legacy_popups_can_requeue_their_own_phase(self):
        world, arc = finish_fiscal("provincial_pay"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc)
        state.pop("ywc_shu_service_compact_offer_open")
        state["ywc_v03_shu_event_dispatch"] = 1019  # a different arc may update the shared receipt
        self.assertTrue(legal(world, compact, "dismiss_stale_compact"))
        world.choose(arc, compact, "dismiss_stale_compact", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1013)
        compact = world.deliver(arc, "ywc_shu.1013")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        state.pop("ywc_shu_service_local_offer_open")
        self.assertTrue(legal(world, supply, "dismiss_stale_supply"))
        world.choose(arc, supply, "dismiss_stale_supply", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "pay_local_share", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        state.pop("ywc_shu_service_appointment_offer_open")
        self.assertTrue(legal(world, appointment, "dismiss_stale_appointment"))
        world.choose(arc, appointment, "dismiss_stale_appointment", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1015)
        appointment = world.deliver(arc, "ywc_shu.1015")
        self.assertTrue(legal(world, appointment, "accept_appointments"))

    def test_unmarked_appointment_without_unique_supply_evidence_returns_to_supply(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "reduce_target", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        state.pop("ywc_shu_service_appointment_offer_open")
        self.assertNotIn("ywc_shu_service_supply_checked", state)
        self.assertNotIn("ywc_shu_service_local_share", state)
        before = world.treasury["SHU"]
        self.assertTrue(legal(world, appointment, "reopen_reduced_supply"))
        world.choose(arc, appointment, "reopen_reduced_supply", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1014)
        self.assertEqual(world.treasury["SHU"], before)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        self.assertTrue(legal(world, appointment, "accept_appointments"))

    def test_arrears_do_not_force_downgrading_before_successor_review(self):
        world, arc = finish_fiscal("pay_partial_advance"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional")):
            step(world, arc, number, key)
        state["gold_reserves"] = 0; month(world)
        self.assertGreater(state["ywc_shu_military_installments_due"], state["ywc_shu_military_installments_paid"])
        supply = world.deliver(arc, "ywc_shu.1014")
        self.assertTrue(legal(world, supply, "check_supply"))
        world.choose(arc, supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        self.assertTrue(legal(world, appointment, "accept_appointments"))
        world.choose(arc, appointment, "accept_appointments", contexts=False)
        world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        self.assertEqual(state.get("ywc_shu_service_route"), 1)

    def test_reduced_appointment_losing_army_at_execution_requeues_safely(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        compact = service_to_compact(world, arc, seal="garrison_seal")
        world.choose(arc, compact, "provincial_compact", contexts=False)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "reduce_target", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        self.assertTrue(legal(world, appointment, "accept_appointments"))
        state["army_size"] = 0
        replay_effect(world, appointment, "accept_appointments")
        self.assertEqual(state.get("ywc_shu_service_pending_event"), 1015)
        self.assertNotIn("ywc_shu_service_contract_delivered", state)
        state["army_size"] = 10
        again = world.deliver(arc, "ywc_shu.1015")
        world.choose(arc, again, "accept_appointments", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_contract_delivered"), 1)

    def test_reduced_supply_execution_failures_requeue_without_a_charge(self):
        for failure in ("army", "cash"):
            with self.subTest(failure=failure):
                world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
                compact = service_to_compact(world, arc, seal="garrison_seal")
                world.choose(arc, compact, "provincial_compact", contexts=False)
                supply = world.deliver(arc, "ywc_shu.1014")
                world.choose(arc, supply, "reduce_target", contexts=False)
                appointment = world.deliver(arc, "ywc_shu.1015")
                world.choose(arc, appointment, "vacant_cap", contexts=False)
                notice = world.deliver(arc, "ywc_shu.1016")
                world.choose(arc, notice, "resume_service_appointments", contexts=False)
                supply = world.deliver(arc, "ywc_shu.1014")
                key = "check_supply" if failure == "army" else "pay_local_share"
                self.assertTrue(legal(world, supply, key))
                if failure == "army": state["army_size"] = 0
                else: state["gold_reserves"] = 0
                before = world.treasury["SHU"]
                replay_effect(world, supply, key)
                self.assertEqual(world.treasury["SHU"], before)
                self.assertEqual(state.get("ywc_shu_service_pending_event"), 1014)
                if failure == "army": state["army_size"] = 10
                else: state["gold_reserves"] = 100000
                again = world.deliver(arc, "ywc_shu.1014")
                self.assertTrue(legal(world, again, key))

    def test_professional_route_needs_staffed_barracks_and_can_wait_for_repair(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional")):
            step(world, arc, number, key)
        buildings = state["states"][0]["buildings"]
        barracks = next(b for b in buildings if b["type"] == "building_barrack")
        buildings.remove(barracks)
        supply = world.deliver(arc, "ywc_shu.1014")
        self.assertFalse(legal(world, supply, "check_supply"))
        self.assertTrue(legal(world, supply, "wait_for_supply"))
        world.choose(arc, supply, "wait_for_supply", contexts=False)
        buildings.append(barracks)
        supply = world.deliver(arc, "ywc_shu.1014")
        world.choose(arc, supply, "check_supply", contexts=False)
        appointment = world.deliver(arc, "ywc_shu.1015")
        buildings.remove(barracks)
        self.assertFalse(legal(world, appointment, "accept_appointments"))
        self.assertTrue(legal(world, appointment, "wait_for_appointments"))
        world.choose(arc, appointment, "wait_for_appointments", contexts=False)
        buildings.append(barracks)
        appointment = world.deliver(arc, "ywc_shu.1015")
        world.choose(arc, appointment, "accept_appointments", contexts=False)
        buildings.remove(barracks); world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        world.run("ywc_shu_service_close_success")
        self.assertNotIn("ywc_shu_service_outcome", state)

    def test_professional_review_interrupts_on_real_arrears_and_recovers(self):
        world, arc = finish_fiscal("pay_partial_advance"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional"),
                            (1014, "check_supply"), (1015, "accept_appointments")):
            step(world, arc, number, key)
        self.assertIn("ywc_shu_service_review", state)
        state["gold_reserves"] = 0
        month(world)
        self.assertGreater(state["ywc_shu_military_installments_due"], state["ywc_shu_military_installments_paid"])
        world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        self.assertNotIn("ywc_shu_service_review_mature", state)
        world.run("ywc_shu_service_close_success")
        self.assertNotIn("ywc_shu_service_outcome", state)
        notice = world.deliver(arc, "ywc_shu.1016")
        self.assertFalse(legal(world, notice, "retry_after_repair"))
        self.assertTrue(legal(world, notice, "wait_service_recovery"))
        replay_effect(world, notice, "retry_after_repair")
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        world.choose(arc, notice, "wait_service_recovery", contexts=False)
        state["gold_reserves"] = 100000
        for _ in range(11): month(world)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 12)
        notice = world.deliver(arc, "ywc_shu.1016")
        world.choose(arc, notice, "retry_after_repair", contexts=False)
        world.advance_months(6); world.elapsed_months += 6
        close = world.deliver(arc, "ywc_shu.1017")
        world.choose(arc, close, "settle_service", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_outcome"), 1)

    def test_cap_notice_cannot_overwrite_an_unrelated_later_queue(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional"),
                            (1014, "check_supply"), (1015, "accept_appointments")):
            step(world, arc, number, key)
        state["army_size"] = 0; world.pulse(arc)
        notice = world.deliver(arc, "ywc_shu.1016")
        state["ywc_shu_service_pending_event"] = 1017
        before = copy.deepcopy(state)
        self.assertFalse(legal(world, notice, "accept_cap"))
        replay_effect(world, notice, "accept_cap")
        self.assertEqual(state, before)

    def test_successor_cap_waits_for_real_capacity_before_restarting(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional"),
                            (1014, "check_supply"), (1015, "accept_appointments")):
            step(world, arc, number, key)
        state["army_size"] = 0; world.pulse(arc)
        notice = world.deliver(arc, "ywc_shu.1016")
        world.choose(arc, notice, "accept_cap", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_route"), 3)
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)
        self.assertNotIn("ywc_shu_service_review_due", state)
        before = copy.deepcopy(state)
        replay_effect(world, notice, "accept_cap")
        self.assertEqual(state, before)
        state["army_size"] = 10
        again = world.deliver(arc, "ywc_shu.1016")
        self.assertTrue(legal(world, again, "retry_after_repair"))
        world.choose(arc, again, "retry_after_repair", contexts=False)
        self.assertIn("ywc_shu_service_review_due", state)

    def test_retry_losing_readiness_at_execution_requeues_interruption_notice(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional"),
                            (1014, "check_supply"), (1015, "accept_appointments")):
            step(world, arc, number, key)
        state["army_size"] = 0; world.pulse(arc)
        state["army_size"] = 10
        notice = world.deliver(arc, "ywc_shu.1016")
        self.assertTrue(legal(world, notice, "retry_after_repair"))
        state["army_size"] = 0
        replay_effect(world, notice, "retry_after_repair")
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)
        self.assertNotIn("ywc_shu_service_review_due", state)
        state["army_size"] = 10
        again = world.deliver(arc, "ywc_shu.1016")
        world.choose(arc, again, "retry_after_repair", contexts=False)
        self.assertIn("ywc_shu_service_review_due", state)

    def test_1017_retry_losing_readiness_requeues_interruption_notice(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional"),
                            (1014, "check_supply"), (1015, "accept_appointments")):
            step(world, arc, number, key)
        world.advance_months(6); world.elapsed_months += 6
        close = world.deliver(arc, "ywc_shu.1017")
        state["army_size"] = 0; world.pulse(arc); state["army_size"] = 10
        world.deliver(arc, "ywc_shu.1016")  # notice is displayed and its queue acknowledged
        self.assertTrue(legal(world, close, "restart_service_review"))
        state["army_size"] = 0
        replay_effect(world, close, "restart_service_review")
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)
        self.assertNotIn("ywc_shu_service_review_due", state)

    def test_interrupted_1017_cannot_restart_before_arrears_are_repaired(self):
        world, arc = finish_fiscal("pay_partial_advance"); state = world.countries["SHU"]
        for number, key in ((1010, "court_seal"), (1011, "cap_arrears"),
                            (1012, "professional_list"), (1013, "professional"),
                            (1014, "check_supply"), (1015, "accept_appointments")):
            step(world, arc, number, key)
        world.advance_months(6); world.elapsed_months += 6
        close = world.deliver(arc, "ywc_shu.1017")
        state["gold_reserves"] = 0; month(world); world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        self.assertFalse(legal(world, close, "restart_service_review"))
        self.assertTrue(legal(world, close, "wait_service_review_recovery"))
        replay_effect(world, close, "restart_service_review")
        self.assertEqual(state.get("ywc_shu_service_review_interrupted"), 1)
        world.choose(arc, close, "wait_service_review_recovery", contexts=False)
        self.assertEqual(state.get("ywc_shu_service_notice_pending_event"), 1016)

    def test_route_specific_barracks_thresholds_and_actual_army(self):
        world, _ = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        state["ywc_shu_service_local_voice"] = 1
        barracks = next(b for b in state["states"][0]["buildings"] if b["type"] == "building_barrack")
        for route, minimum in ((1, 0.8), (2, 0.6), (3, 0.25)):
            with self.subTest(route=route):
                state["ywc_shu_service_route"] = route
                barracks["occupancy"] = minimum - 0.01
                self.assertFalse(world.conditions(parse("ywc_shu_v03_service_route_ready = yes"), "SHU"))
                barracks["occupancy"] = minimum
                self.assertTrue(world.conditions(parse("ywc_shu_v03_service_route_ready = yes"), "SHU"))
                barracks["shortage"] = True
                self.assertFalse(world.conditions(parse("ywc_shu_v03_service_route_ready = yes"), "SHU"))
                barracks["shortage"] = False
                state["army_size"] = 0
                self.assertFalse(world.conditions(parse("ywc_shu_v03_service_route_ready = yes"), "SHU"))
                state["army_size"] = 10

    def test_legacy_no_contract_is_not_treated_as_unpaid_and_corruption_is_blocked(self):
        world, arc = finish_fiscal("budget_queue"); state = world.countries["SHU"]
        state["ywc_shu_service_route"] = 1
        self.assertTrue(world.conditions(parse("ywc_shu_service_route_ready = yes"), "SHU"))
        state.update({"ywc_shu_military_contract_active": 1,
                      "ywc_shu_military_installment": -5,
                      "ywc_shu_military_installments_due": 1,
                      "ywc_shu_military_installments_paid": 1})
        self.assertFalse(world.conditions(parse("ywc_shu_service_route_ready = yes"), "SHU"))
        state["ywc_shu_service_route"] = 3
        self.assertTrue(world.conditions(parse("ywc_shu_service_route_ready = yes"), "SHU"))
        state["ywc_shu_service_route"] = 1
        state.pop("ywc_shu_military_contract_active")
        state.update({"ywc_shu_military_installment": 250, "ywc_shu_military_installments_due": 3,
                      "ywc_shu_military_installments_paid": 1})
        self.assertFalse(world.conditions(parse("ywc_shu_service_route_ready = yes"), "SHU"),
                         "an incomplete new ledger cannot pass just because its active marker disappeared")
        state.update({"ywc_shu_military_contract_fulfilled": 1,
                      "ywc_shu_military_installments_due": 12,
                      "ywc_shu_military_installments_paid": 12})
        self.assertTrue(world.conditions(parse("ywc_shu_service_route_ready = yes"), "SHU"))


if __name__ == "__main__":
    unittest.main()

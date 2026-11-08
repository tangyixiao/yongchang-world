"""SHU merchant advance and old-choice replay, using the authored event queue."""
import copy
import unittest

from shu_kor_strict_review_runtime import Strict, facts, field
from test_v03_shu_content import shu_monthly_effect
from test_v03_shu_kor_c1_c4_strict import play


def reached_offer(source="both"):
    world = Strict("shu"); world.countries["SHU"] = facts(); state = world.countries["SHU"]
    buildings = state["states"][0]["buildings"]
    if source in ("farm", "none"):
        state["states"][0]["buildings"] = [b for b in buildings if b["type"] != "building_port"]
    if source in ("port", "none"):
        state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"] if "bg_agriculture" not in b.get("groups", [])]
    arc = world.cat["arcs"][0]
    for number, key in ((1000, "pilot_state_sichuan"), (1001, "local_register"),
                        (1002, "time_limited_exemption"), (1003, "budget_queue"),
                        (1004, "local_mediation")):
        play(world, arc, number, key)
    return world, arc, world.deliver(arc, "ywc_shu.1005")


def option(event, key):
    return next(value for name, _, value in event if name == "option" and field(value, "name").endswith("." + key))


def replay_effect(world, event, key):
    world.execute([node for node in option(event, key) if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")], "SHU")


def repay(world):
    callback = shu_monthly_effect()
    for _ in range(12):
        world.advance_months(1); world.elapsed_months += 1
        world.execute(callback, "SHU")


class ShuMerchantObligationTests(unittest.TestCase):
    def test_a_live_port_or_farm_is_required_and_no_source_has_a_free_exit(self):
        for source in ("port", "farm", "none"):
            with self.subTest(source=source):
                world, arc, event = reached_offer(source)
                state = world.countries["SHU"]
                legal = {row["option"]: row["legal"] for row in world.options(event)}
                self.assertEqual(legal["accept_port_advance"], source != "none")
                self.assertTrue(legal["refuse_private_advance"])
                before = world.treasury["SHU"]
                if source == "none":
                    replay_effect(world, event, "accept_port_advance")
                    self.assertEqual(world.treasury["SHU"], before)
                    self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
                else:
                    world.choose(arc, event, "accept_port_advance", contexts=False)
                    self.assertGreater(world.treasury["SHU"], before)
                    self.assertEqual(state.get("ywc_shu_local_prepayment_offer", 0), int(source == "farm"))

    def test_unstaffed_short_or_unowned_sources_do_not_create_an_offer(self):
        for source in ("port", "farm"):
            for defect in ("unstaffed", "shortage", "unowned"):
                with self.subTest(source=source, defect=defect):
                    world, _, event = reached_offer(source)
                    state = world.countries["SHU"]["states"][0]
                    building = next(b for b in state["buildings"] if b["type"] == ("building_port" if source == "port" else "building_maize_farm"))
                    if defect == "unstaffed": building["occupancy"] = 0.49
                    if defect == "shortage": building["shortage"] = True
                    if defect == "unowned": state["owned"] = False
                    self.assertFalse(next(row["legal"] for row in world.options(event) if row["option"] == "accept_port_advance"))
                    before = world.treasury["SHU"]
                    replay_effect(world, event, "accept_port_advance")
                    self.assertEqual(world.treasury["SHU"], before)

    def test_a_recorded_choice_can_resume_only_its_own_stage(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "refuse_private_advance", contexts=False)
        state = world.countries["SHU"]
        state.pop("ywc_shu_pending_event")  # simulate a lost queue at the same stage
        replay_effect(world, event, "continue_recorded")
        self.assertEqual(state["ywc_shu_pending_event"], 1006)
        e6 = world.deliver(arc, "ywc_shu.1006")
        world.choose(arc, e6, "settle_as_provincial", contexts=False)
        later_pending = state.get("ywc_shu_pending_event")
        replay_effect(world, event, "continue_recorded")
        self.assertEqual(state.get("ywc_shu_pending_event"), later_pending)

    def test_replaying_continue_without_a_recorded_choice_cannot_skip_the_offer(self):
        world, _, event = reached_offer()
        state = world.countries["SHU"]
        self.assertNotIn("ywc_shu_pending_event", state)
        replay_effect(world, event, "continue_recorded")
        self.assertNotIn("ywc_shu_pending_event", state)
        self.assertNotIn("ywc_shu_merchant_advance", state)

    def test_narrowing_first_prevents_a_later_stale_loan(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "narrow_pilot", contexts=False)
        before = (world.treasury["SHU"], world.countries["SHU"].get("ywc_shu_pending_event"))
        replay_effect(world, event, "accept_port_advance")
        self.assertEqual((world.treasury["SHU"], world.countries["SHU"].get("ywc_shu_pending_event")), before)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", world.countries["SHU"])

    def test_old_accept_after_repayment_cannot_issue_the_principal_twice(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "accept_port_advance", contexts=False)
        repay(world); state = world.countries["SHU"]
        self.assertEqual(state.get("ywc_shu_merchant_advance_repaid"), 1)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        before = (world.treasury["SHU"], state.get("ywc_shu_pending_event"))
        replay_effect(world, event, "accept_port_advance")
        self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_pending_event")), before)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)

    def test_old_refusal_cannot_bypass_the_still_unpaid_advance(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "accept_port_advance", contexts=False)
        state = world.countries["SHU"]
        replay_effect(world, event, "refuse_private_advance")
        self.assertNotIn("ywc_shu_merchant_advance_refused", state)
        next_event = world.deliver(arc, "ywc_shu.1006")
        self.assertFalse(next(row["legal"] for row in world.options(next_event) if row["option"] == "settle_as_provincial"))
        replay_effect(world, next_event, "settle_as_provincial")
        self.assertNotIn("ywc_shu_second_audit", state)
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)

    def test_repaid_marker_without_consultation_cannot_offer_a_noop_local_audit(self):
        world, arc, offer = reached_offer()
        world.choose(arc, offer, "accept_port_advance", contexts=False)
        repay(world)
        state = world.countries["SHU"]
        state.pop("ywc_shu_merchant_consultation")
        audit = world.deliver(arc, "ywc_shu.1006")
        self.assertFalse(next(row["legal"] for row in world.options(audit) if row["option"] == "settle_as_provincial"))
        replay_effect(world, audit, "settle_as_provincial")
        self.assertNotIn("ywc_shu_second_audit", state)

    def test_contradictory_old_markers_do_not_satisfy_a_live_unpaid_debt(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "accept_port_advance", contexts=False)
        state = world.countries["SHU"]
        # Preserve a possible old save produced by the earlier replay bug.
        state.update({"ywc_shu_merchant_advance_refused": 1, "ywc_shu_merchant_advance_repaid": 1})
        next_event = world.deliver(arc, "ywc_shu.1006")
        self.assertFalse(next(row["legal"] for row in world.options(next_event) if row["option"] == "settle_as_provincial"))
        replay_effect(world, next_event, "settle_as_provincial")
        self.assertNotIn("ywc_shu_second_audit", state)
        repay(world)
        self.assertTrue(next(row["legal"] for row in world.options(next_event) if row["option"] == "settle_as_provincial"))

    def test_old_narrow_choice_with_a_pending_next_event_cannot_issue_a_loan(self):
        from pathlib import Path
        from clausewitz_harness import parse
        world, _, event = reached_offer()
        historical = Path("tests/fixtures/v03_shu_legacy_1005_narrow.txt").read_text(encoding="utf-8")
        world.execute(parse(historical), "SHU")
        state = world.countries["SHU"]
        self.assertNotIn("ywc_shu_merchant_advance_narrowed", state)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
        self.assertTrue(any(row["legal"] for row in world.options(event)), "a stale or legacy dialog must still be dismissible")
        before = world.treasury["SHU"]
        replay_effect(world, event, "accept_port_advance")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)

    def test_provincial_audit_can_consume_its_own_duplicate_queue(self):
        world, arc, offer = reached_offer()
        world.choose(arc, offer, "refuse_private_advance", contexts=False)
        audit = world.deliver(arc, "ywc_shu.1006")
        state = world.countries["SHU"]
        world.advance_months(1); world.elapsed_months += 1; world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
        world.choose(arc, audit, "settle_as_provincial", contexts=False)
        self.assertEqual(state.get("ywc_shu_second_audit"), 1)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1007)

    def test_old_1006_effect_cannot_rewind_a_later_queued_review(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "refuse_private_advance", contexts=False)
        e6 = world.deliver(arc, "ywc_shu.1006")
        world.choose(arc, e6, "settle_as_provincial", contexts=False)
        e7 = world.deliver(arc, "ywc_shu.1007")
        world.choose(arc, e7, "provincial_retention", contexts=False)
        state = world.countries["SHU"]
        for _ in range(9):
            world.advance_months(1); world.elapsed_months += 1; world.pulse(arc)
            if any(eid == "ywc_shu.1008" for _, eid in world.events): break
        self.assertTrue(any(eid == "ywc_shu.1008" for _, eid in world.events))
        before = (state.get("ywc_shu_pending_event"), list(world.events))
        state.update({"ywc_shu_merchant_advance": 1, "ywc_shu_merchant_advance_unpaid": 1,
                      "ywc_shu_merchant_advance_repaid": 1})
        replay_effect(world, e6, "settle_as_provincial")
        self.assertEqual((state.get("ywc_shu_pending_event"), world.events), before)

    def test_provincial_review_is_not_clickable_when_its_execution_guard_fails(self):
        for defect in ("later_queue", "chosen_mode", "later_stage"):
            with self.subTest(defect=defect):
                world, arc, offer = reached_offer()
                world.choose(arc, offer, "refuse_private_advance", contexts=False)
                audit = world.deliver(arc, "ywc_shu.1006")
                world.choose(arc, audit, "settle_as_provincial", contexts=False)
                review = world.deliver(arc, "ywc_shu.1007")
                state = world.countries["SHU"]
                if defect == "later_queue": state["ywc_shu_pending_event"] = 1008
                if defect == "chosen_mode": state["ywc_shu_settlement_mode"] = 3
                if defect == "later_stage": state["ywc_v03_shu_v03_shu_fiscal_register_last_event"] = 9
                self.assertFalse(next(row["legal"] for row in world.options(review) if row["option"] == "provincial_retention"))
                before = copy.deepcopy(state)
                replay_effect(world, review, "provincial_retention")
                self.assertEqual(state, before)

    def test_audit_can_wait_for_lost_capacity_even_without_merchant_debt(self):
        world, arc, offer = reached_offer()
        world.choose(arc, offer, "refuse_private_advance", contexts=False)
        audit = world.deliver(arc, "ywc_shu.1006")
        state = world.countries["SHU"]
        state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"] if b["type"] != "building_government_administration"]
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertTrue(next(row["legal"] for row in world.options(audit) if row["option"] == "wait_for_audit"))
        world.choose(arc, audit, "wait_for_audit", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
        self.assertNotIn("ywc_shu_second_audit", state)

    def test_stale_1007_cannot_start_provincial_review_with_unpaid_legacy_debt(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "refuse_private_advance", contexts=False)
        e6 = world.deliver(arc, "ywc_shu.1006")
        world.choose(arc, e6, "settle_as_provincial", contexts=False)
        e7 = world.deliver(arc, "ywc_shu.1007")
        state = world.countries["SHU"]
        self.assertTrue(next(row["legal"] for row in world.options(e7) if row["option"] == "provincial_retention"))
        state.update({"ywc_shu_merchant_advance": 1, "ywc_shu_merchant_advance_unpaid": 1,
                      "ywc_shu_merchant_advance_repaid": 1})
        self.assertFalse(next(row["legal"] for row in world.options(e7) if row["option"] == "provincial_retention"))
        replay_effect(world, e7, "provincial_retention")
        self.assertNotIn("ywc_shu_settlement_mode", state)
        self.assertNotIn("ywc_shu_settlement_review", state)
        world.run("ywc_shu_choose_provincial_settlement")
        self.assertNotIn("ywc_shu_settlement_mode", state)

    def test_stale_wait_does_not_rewind_another_queue_or_an_exited_arc(self):
        world, arc, offer = reached_offer()
        world.choose(arc, offer, "accept_port_advance", contexts=False)
        audit = world.deliver(arc, "ywc_shu.1006")
        state = world.countries["SHU"]
        for queued in (1001, 1007, 1008):
            with self.subTest(queued=queued):
                state["ywc_shu_pending_event"] = queued
                before = (state["ywc_shu_merchant_advance_unpaid"], world.treasury["SHU"],
                          world.months_until_expiry["SHU"]["ywc_shu_merchant_repayment_due"])
                replay_effect(world, audit, "wait_for_audit")
                self.assertEqual(state.get("ywc_shu_pending_event"), queued)
                self.assertEqual((state["ywc_shu_merchant_advance_unpaid"], world.treasury["SHU"],
                                  world.months_until_expiry["SHU"]["ywc_shu_merchant_repayment_due"]), before)
        state.pop("ywc_shu_pending_event")
        state["ywc_shu_arc_abandoned"] = 1
        replay_effect(world, audit, "wait_for_audit")
        self.assertNotIn("ywc_shu_pending_event", state)

    def test_thirty_six_month_fallback_does_not_skip_an_unanswered_initial_state(self):
        world = Strict("shu"); world.countries["SHU"] = facts()
        arc = world.cat["arcs"][0]
        event = world.deliver(arc, "ywc_shu.1000")
        world.advance_months(40); world.elapsed_months += 40; world.pulse(arc)
        self.assertNotEqual(world.countries["SHU"].get("ywc_shu_pending_event"), 1006)
        self.assertNotIn(("SHU", "ywc_shu.1006"), world.events)
        world.choose(arc, event, "pilot_state_sichuan", contexts=False)
        self.assertEqual(world.countries["SHU"].get("ywc_shu_pending_event"), 1001)

    def test_thirty_six_month_fallback_still_works_after_choosing_to_wait_for_office(self):
        world = Strict("shu"); world.countries["SHU"] = facts()
        arc = world.cat["arcs"][0]
        play(world, arc, 1000, "pilot_state_sichuan")
        state = world.countries["SHU"]
        state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"] if b["type"] != "building_government_administration"]
        office = world.deliver(arc, "ywc_shu.1001")
        world.choose(arc, office, "wait_for_office", contexts=False)
        world.advance_months(13); world.elapsed_months += 13
        reminder = world.deliver(arc, "ywc_shu.1001")
        world.choose(arc, reminder, "wait_for_office", contexts=False)
        world.advance_months(24); world.elapsed_months += 24
        fallback = world.deliver(arc, "ywc_shu.1006")
        self.assertTrue(next(row["legal"] for row in world.options(fallback) if row["option"] == "withdraw_after_failed_audit"))
        self.assertNotIn("ywc_shu_second_audit", state)

    def test_unpaid_advance_can_wait_and_retry_after_actual_monthly_repayment(self):
        world, arc, offer = reached_offer()
        world.choose(arc, offer, "accept_port_advance", contexts=False)
        state = world.countries["SHU"]
        audit = world.deliver(arc, "ywc_shu.1006")
        self.assertTrue(next(row["legal"] for row in world.options(audit) if row["option"] == "wait_for_audit"))
        timer_before = world.months_until_expiry["SHU"]["ywc_shu_merchant_repayment_due"]
        world.choose(arc, audit, "wait_for_audit", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
        self.assertEqual(world.months_until_expiry["SHU"]["ywc_shu_merchant_repayment_due"], timer_before)
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)
        world.treasury["SHU"] = 0; state["gold_reserves"] = 0
        repay(world)
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)
        state["gold_reserves"] = 1000; world.treasury["SHU"] = 1000
        world.advance_months(1); world.elapsed_months += 1; world.execute(shu_monthly_effect(), "SHU")
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state.get("ywc_shu_merchant_advance_repaid"), 1)
        retry = world.deliver(arc, "ywc_shu.1006")
        self.assertTrue(next(row["legal"] for row in world.options(retry) if row["option"] == "settle_as_provincial"))
        world.choose(arc, retry, "settle_as_provincial", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1007)
        replay_effect(world, audit, "wait_for_audit")
        self.assertEqual(state.get("ywc_shu_pending_event"), 1007)

    def test_unanswered_offer_resumes_after_pilot_loss_without_skipping_choice(self):
        world, arc, old_offer = reached_offer()
        state = world.countries["SHU"]
        replacement = copy.deepcopy(state["states"][0])
        replacement["region"] = "s:STATE_CHONGQING"
        state["states"].append(replacement)
        state["states"][0]["owned"] = False
        world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_resume_event"), 1005)
        reselect = world.deliver(arc, "ywc_shu.1001")
        world.choose(arc, reselect, "reselect_state_chongqing", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1005)
        before = world.treasury["SHU"]
        replay_effect(world, old_offer, "accept_port_advance")
        self.assertEqual(world.treasury["SHU"], before)
        new_offer = world.deliver(arc, "ywc_shu.1005")
        world.choose(arc, new_offer, "refuse_private_advance", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
        audit = world.deliver(arc, "ywc_shu.1006")
        self.assertTrue(next(row["legal"] for row in world.options(audit) if row["option"] == "settle_as_provincial"))

    def test_audit_deadlines_do_not_skip_an_unanswered_merchant_offer(self):
        world, arc, event = reached_offer()
        state = world.countries["SHU"]
        world.advance_months(40); world.elapsed_months += 40
        world.pulse(arc)
        self.assertNotEqual(state.get("ywc_shu_pending_event"), 1006)
        self.assertNotIn(("SHU", "ywc_shu.1006"), world.events)
        world.choose(arc, event, "refuse_private_advance", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)

    def test_second_audit_cannot_jump_over_an_unanswered_earlier_stage(self):
        world = Strict("shu"); world.countries["SHU"] = facts()
        arc = world.cat["arcs"][0]
        play(world, arc, 1000, "pilot_state_sichuan")
        play(world, arc, 1001, "local_register")
        event = world.deliver(arc, "ywc_shu.1002")
        world.advance_months(6); world.elapsed_months += 6; world.pulse(arc)
        self.assertNotEqual(world.countries["SHU"].get("ywc_shu_pending_event"), 1006)
        self.assertNotIn(("SHU", "ywc_shu.1006"), world.events)
        world.choose(arc, event, "time_limited_exemption", contexts=False)
        self.assertEqual(world.countries["SHU"].get("ywc_shu_pending_event"), 1003)

    def test_unanswered_offer_cannot_create_money_after_arc_exit(self):
        world, arc, event = reached_offer()
        state = world.countries["SHU"]
        state["ywc_shu_arc_abandoned"] = 1
        world.run("ywc_shu_close_as_breach")
        before = (world.treasury["SHU"], state.get("ywc_shu_pending_event"))
        replay_effect(world, event, "accept_port_advance")
        world.run("ywc_shu_accept_merchant_advance")
        self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_pending_event")), before)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)

    def test_stale_narrow_or_accept_cannot_override_a_later_queue(self):
        world, arc, event = reached_offer()
        world.choose(arc, event, "refuse_private_advance", contexts=False)
        e6 = world.deliver(arc, "ywc_shu.1006")
        world.choose(arc, e6, "settle_as_provincial", contexts=False)
        state = world.countries["SHU"]
        pending = state.get("ywc_shu_pending_event"); before = world.treasury["SHU"]
        for key in ("accept_port_advance", "narrow_pilot"):
            replay_effect(world, event, key)
            self.assertEqual((state.get("ywc_shu_pending_event"), world.treasury["SHU"]), (pending, before))
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)

    def test_source_lost_after_display_requeues_without_creating_money(self):
        world, arc, event = reached_offer("port")
        state = world.countries["SHU"]
        state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"] if b["type"] != "building_port"]
        before = world.treasury["SHU"]
        replay_effect(world, event, "accept_port_advance")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1005)


class ShuMerchantCalendarTests(unittest.TestCase):
    def test_new_advance_does_not_fall_due_before_twelve_calendar_months(self):
        from datetime import date
        from pathlib import Path
        from clausewitz_harness import parse
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"ywc_v03_shu_v03_shu_fiscal_register_last_event": 6})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1836, 1, 15))
        world.active["SHU"].append("ywc_je_v03_shu_register_pilot")
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_script("ywc_shu_accept_merchant_advance = yes", "SHU")
        self.assertEqual(world.treasury["SHU"], 1000)
        # Twelve pulses occur from 1 Feb to 1 Jan, before the 15 Jan anniversary.
        for offset in range(12):
            year = 1836 + (offset + 1) // 12; month = (offset + 1) % 12 + 1
            target = date(year, month, 1)
            world.advance_days((target - world.date).days); world.run_country_monthly("SHU")
        self.assertEqual(world.date, date(1837, 1, 1))
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], 1000)
        world.advance_days(31); world.run_country_monthly("SHU")
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertEqual(state.get("ywc_shu_merchant_advance_repaid"), 1)
        self.assertEqual(world.treasury["SHU"], 0)


if __name__ == "__main__":
    unittest.main()

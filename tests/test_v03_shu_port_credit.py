"""SHU port-credit maturity and source-queue regressions."""
import unittest

from clausewitz_harness import parse
from shu_kor_strict_review_runtime import Strict, facts
from test_v03_shu_content import shu_monthly_effect
from test_v03_shu_merchant_obligations import replay_effect


def step(world, arc, number, key):
    event = world.deliver(arc, "ywc_shu." + str(number))
    world.choose(arc, event, key, contexts=False)
    return event


def reached_port_offer():
    world = Strict("shu"); state = facts()
    state["ywc_v03_shu_v03_shu_fiscal_register_settled"] = 1
    world.countries["SHU"] = state
    arc = world.cat["arcs"][2]
    step(world, arc, 1018, "unified_customs")
    step(world, arc, 1019, "publish_books")
    return world, arc, world.deliver(arc, "ywc_shu.1020")


def legal(world, event, name):
    return next(row["legal"] for row in world.options(event) if row["option"] == name)


def reached_port_burden():
    world, arc, offer = reached_port_offer()
    world.choose(arc, offer, "refuse_credit", contexts=False)
    for number, key in ((1021, "current_law_review"), (1022, "pay_verification"),
                        (1023, "central_form")):
        step(world, arc, number, key)
    return world, arc


def month(world):
    world.advance_months(1); world.elapsed_months += 1
    world.execute(shu_monthly_effect(), "SHU")


class ShuPortCreditTests(unittest.TestCase):
    def test_shared_route_can_revisit_incomplete_terms_without_forgiving_costs(self):
        world = Strict("shu"); state = facts()
        state["ywc_v03_shu_v03_shu_fiscal_register_settled"] = 1
        state.update({"ywc_shu_merchant_advance_unpaid": 1,
                      "ywc_shu_merchant_principal": 800})
        world.countries["SHU"] = state; arc = world.cat["arcs"][2]
        for number, key in ((1018, "merchant_share"), (1019, "split_books"),
                            (1020, "refuse_credit"), (1021, "current_law_review"),
                            (1022, "pay_verification"), (1023, "central_form"),
                            (1024, "shared_burden")):
            step(world, arc, number, key)
        for _ in range(7): world.pulse(arc)
        settlement = world.deliver(arc, "ywc_shu.1025")
        self.assertFalse(legal(world, settlement, "settle_share"))
        recovery = next((row for row in world.options(settlement)
                         if row["option"] == "revisit_share_terms"), None)
        self.assertIsNotNone(recovery, "a reached shared route needs a way to finish its missing terms")
        self.assertTrue(recovery["legal"])
        cash = world.treasury["SHU"]; principal = state["ywc_shu_merchant_principal"]
        world.choose(arc, settlement, "revisit_share_terms", contexts=False)
        self.assertEqual(state["ywc_shu_port_pending_event"], 1023)
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertEqual(state["ywc_shu_merchant_principal"], principal)
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertIn("ywc_shu_port_fee_paid", state)
        self.assertNotIn("ywc_shu_port_review_mature", state)
        step(world, arc, 1023, "share_form")
        step(world, arc, 1024, "shared_burden")
        self.assertIn("ywc_shu_port_review_due", state)
        self.assertNotIn("ywc_shu_port_review_mature", state)
        for _ in range(7): world.pulse(arc)
        final = world.deliver(arc, "ywc_shu.1025")
        self.assertTrue(legal(world, final, "settle_share"))
        self.assertFalse(legal(world, final, "revisit_share_terms"))
        world.choose(arc, final, "settle_share", contexts=False)
        self.assertEqual(state["ywc_shu_port_outcome"], 2)
        replay_effect(world, settlement, "revisit_share_terms")
        self.assertNotIn("ywc_shu_port_pending_event", state)
        self.assertEqual(world.treasury["SHU"], cash)
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)

    def test_close_before_maturity_does_not_deduct_the_principal(self):
        world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
        world.choose(arc, offer, "merchant_advance", contexts=False)
        state.update({"ywc_shu_port_review_mature": 1, "ywc_shu_port_receipts_checked": 1,
                      "ywc_shu_port_fee_paid": 1})
        before = world.treasury["SHU"]
        world.run("ywc_shu_port_close_unified")
        self.assertEqual(state.get("ywc_shu_port_outcome"), 1)
        self.assertEqual(world.treasury["SHU"], before)
        self.assertIn("ywc_shu_port_advance_unpaid", state)

    def test_unpaid_advance_is_collected_after_withdrawal_and_twelve_months(self):
        world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
        world.choose(arc, offer, "merchant_advance", contexts=False)
        state["ywc_shu_port_withdrawn"] = 1; world.run("ywc_shu_port_close_withdrawn")
        for _ in range(11): month(world)
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], 1000)
        month(world)
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(state.get("ywc_shu_port_advance_repaid"), 1)
        self.assertEqual(world.treasury["SHU"], 0)
        month(world); self.assertEqual(world.treasury["SHU"], 0)

    def test_legacy_debt_gets_conservative_clock_without_inventing_a_signing_date(self):
        world = Strict("shu"); state = facts(); world.countries["SHU"] = state
        state.update({"ywc_shu_port_advance_accepted": 1, "ywc_shu_port_advance_unpaid": 1,
                      "ywc_shu_port_principal": 1000, "ywc_shu_port_repayment_months": 0})
        world.execute(shu_monthly_effect(), "SHU")
        self.assertIn("ywc_shu_port_repayment_due", state)
        for _ in range(11): month(world)
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], 0)
        month(world)
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], -1000)

    def test_existing_legacy_timer_is_not_reset_by_clock_migration(self):
        world = Strict("shu"); state = facts(); world.countries["SHU"] = state
        state.update({"ywc_shu_port_advance_unpaid": 1, "ywc_shu_port_principal": 1000,
                      "ywc_shu_port_repayment_due": 1})
        world.months_until_expiry["SHU"]["ywc_shu_port_repayment_due"] = 3
        world.execute(shu_monthly_effect(), "SHU")
        self.assertEqual(world.months_until_expiry["SHU"]["ywc_shu_port_repayment_due"], 3)
        self.assertEqual(state.get("ywc_shu_port_repayment_clock_initialized"), 1)
        for _ in range(3): month(world)
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], -1000)

    def test_invalid_saved_principal_never_generates_money_or_marks_payment(self):
        for principal in (None, 0, -1000):
            with self.subTest(principal=principal):
                world = Strict("shu"); state = facts(); world.countries["SHU"] = state
                state.update({"ywc_shu_port_advance_unpaid": 1, "ywc_shu_port_repayment_clock_initialized": 1})
                if principal is not None: state["ywc_shu_port_principal"] = principal
                world.execute(shu_monthly_effect(), "SHU")
                self.assertEqual(world.treasury["SHU"], 0)
                self.assertIn("ywc_shu_port_advance_unpaid", state)
                self.assertNotIn("ywc_shu_port_advance_repaid", state)

    def test_loan_requires_a_staffed_owned_port_and_valid_cost(self):
        for defect in ("unstaffed", "shortage", "unowned", "default", "negative_income", "bad_cost"):
            with self.subTest(defect=defect):
                world, _, offer = reached_port_offer(); state = world.countries["SHU"]
                location = state["states"][0]
                port = next(b for b in location["buildings"] if b["type"] == "building_port")
                if defect == "unstaffed": port["occupancy"] = 0.79
                if defect == "shortage": port["shortage"] = True
                if defect == "unowned": location["owned"] = False
                if defect == "default": state["in_default"] = True
                if defect == "negative_income": state["net_fixed_income"] = -1
                if defect == "bad_cost": state["ywc_shu_port_cost"] = -1000
                self.assertFalse(legal(world, offer, "merchant_advance"))
                before = world.treasury["SHU"]
                replay_effect(world, offer, "merchant_advance")
                self.assertEqual(world.treasury["SHU"], before)
                self.assertNotIn("ywc_shu_port_advance_unpaid", state)

    def test_unpaid_consultation_and_fee_helper_reject_missing_or_nonpositive_cost(self):
        for bad_cost in (None, 0, -1000):
            with self.subTest(cost=bad_cost):
                world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
                if bad_cost is None: state.pop("ywc_shu_port_cost", None)
                else: state["ywc_shu_port_cost"] = bad_cost
                self.assertFalse(legal(world, offer, "consult_only"))
                replay_effect(world, offer, "consult_only")
                state["ywc_shu_port_fee_half_mode"] = 1
                world.run("ywc_shu_pay_port_fee")
                self.assertEqual(world.treasury["SHU"], 0)
                self.assertNotIn("ywc_shu_port_fee_paid", state)
                self.assertNotIn("ywc_shu_port_consult_only", state)

    def test_old_refusal_and_old_acceptance_cannot_override_each_other(self):
        for chosen, replayed in (("merchant_advance", "refuse_credit"), ("refuse_credit", "merchant_advance")):
            with self.subTest(chosen=chosen):
                world, arc, event = reached_port_offer(); state = world.countries["SHU"]
                world.choose(arc, event, chosen, contexts=False)
                before = (world.treasury["SHU"], state.get("ywc_shu_port_pending_event"))
                replay_effect(world, event, replayed)
                self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_port_pending_event")), before)
                if chosen == "merchant_advance": self.assertNotIn("ywc_shu_port_advance_refused", state)
                else: self.assertNotIn("ywc_shu_port_advance_unpaid", state)

    def test_lost_port_before_execution_cannot_issue_a_loan(self):
        world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
        state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"] if b["type"] != "building_port"]
        self.assertFalse(legal(world, offer, "merchant_advance"))
        before = world.treasury["SHU"]
        replay_effect(world, offer, "merchant_advance")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)

    def test_unmarked_legacy_offer_can_be_safely_reopened(self):
        world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
        state.pop("ywc_shu_port_advance_offer_open", None)
        self.assertFalse(legal(world, offer, "merchant_advance"))
        self.assertTrue(legal(world, offer, "reopen_legacy_port_offer"))
        world.choose(arc, offer, "reopen_legacy_port_offer", contexts=False)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)
        again = world.deliver(arc, "ywc_shu.1020")
        self.assertTrue(legal(world, again, "refuse_credit"))

    def test_port_loss_notice_preserves_an_unanswered_credit_choice(self):
        world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
        port = state["states"][0]["buildings"].pop(
            next(i for i, b in enumerate(state["states"][0]["buildings"]) if b["type"] == "building_port"))
        world.pulse(arc)
        world.advance_months(13); world.elapsed_months += 13; world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_port_notice_pending_event"), 1024)
        world.choose(arc, offer, "dismiss_stale_port_offer", contexts=False)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)
        notice = world.deliver(arc, "ywc_shu.1024")
        state["states"][0]["buildings"].append(port)
        for option in ("central_burden", "shared_burden", "reduce_burden", "retry_after_repair"):
            self.assertFalse(legal(world, notice, option), option)
            replay_effect(world, notice, option)
            self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020, option)
            self.assertNotIn("ywc_shu_port_review", state, option)
        world.choose(arc, notice, "resume_pending_port_step", contexts=False)
        again = world.deliver(arc, "ywc_shu.1020")
        self.assertTrue(legal(world, again, "refuse_credit"))

    def test_port_review_maturity_does_not_overwrite_unanswered_credit(self):
        world, arc, _ = reached_port_offer(); state = world.countries["SHU"]
        state["ywc_shu_port_pending_event"] = 1020
        state["ywc_shu_port_review"] = 1
        world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)
        self.assertNotIn("ywc_shu_port_review_mature", state)

    def test_explicit_resume_repairs_an_early_stale_review_before_credit(self):
        world, arc, offer = reached_port_offer(); state = world.countries["SHU"]
        port = state["states"][0]["buildings"].pop(
            next(i for i, b in enumerate(state["states"][0]["buildings"]) if b["type"] == "building_port"))
        world.pulse(arc); world.advance_months(13); world.elapsed_months += 13; world.pulse(arc)
        notice = world.deliver(arc, "ywc_shu.1024")
        state.update({"ywc_shu_port_review": 1, "ywc_shu_port_review_mature": 1})
        self.assertFalse(legal(world, offer, "merchant_advance"))
        world.choose(arc, notice, "resume_pending_port_step", contexts=False)
        self.assertNotIn("ywc_shu_port_review", state)
        self.assertNotIn("ywc_shu_port_review_mature", state)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1020)
        state["states"][0]["buildings"].append(port)
        fresh = world.deliver(arc, "ywc_shu.1020")
        self.assertTrue(legal(world, fresh, "refuse_credit"))

    def test_old_credit_offer_is_not_legal_after_later_port_stages(self):
        for stage in ("ywc_shu_port_law_verified", "ywc_shu_port_receipts_checked",
                      "ywc_shu_port_settlement_choice", "ywc_shu_port_review"):
            with self.subTest(stage=stage):
                world, _, offer = reached_port_offer(); state = world.countries["SHU"]
                state[stage] = 1
                self.assertFalse(legal(world, offer, "merchant_advance"))
                replay_effect(world, offer, "merchant_advance")
                self.assertNotIn("ywc_shu_port_advance_unpaid", state)
                self.assertEqual(world.treasury["SHU"], 0)
        # Even a residual open-offer marker cannot jump over a later queue.
        for pending in range(1021, 1026):
            with self.subTest(pending=pending):
                world, _, offer = reached_port_offer(); state = world.countries["SHU"]
                state["ywc_shu_port_pending_event"] = pending
                self.assertIn("ywc_shu_port_advance_offer_open", state)
                self.assertFalse(legal(world, offer, "merchant_advance"))
                replay_effect(world, offer, "merchant_advance")
                self.assertEqual(state["ywc_shu_port_pending_event"], pending)
                self.assertNotIn("ywc_shu_port_advance_unpaid", state)
                self.assertEqual(world.treasury["SHU"], 0)

    def test_notice_cannot_consume_same_numbered_ordinary_burden_queue(self):
        world, arc = reached_port_burden(); state = world.countries["SHU"]
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1024)
        port = state["states"][0]["buildings"].pop(
            next(i for i, b in enumerate(state["states"][0]["buildings"]) if b["type"] == "building_port"))
        state["ywc_shu_port_notice_pending_event"] = 1024
        notice = world.deliver(arc, "ywc_shu.1024")
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1024)
        state["states"][0]["buildings"].append(port)
        self.assertFalse(legal(world, notice, "central_burden"))
        replay_effect(world, notice, "central_burden")
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1024)
        world.choose(arc, notice, "resume_pending_port_step", contexts=False)
        normal = world.deliver(arc, "ywc_shu.1024")
        self.assertTrue(legal(world, normal, "central_burden"))
        world.choose(arc, normal, "central_burden", contexts=False)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1025)

    def test_old_burden_popup_cannot_restart_a_mature_review(self):
        world, arc = reached_port_burden(); state = world.countries["SHU"]
        burden = world.deliver(arc, "ywc_shu.1024")
        world.choose(arc, burden, "central_burden", contexts=False)
        world.advance_months(7); world.elapsed_months += 7
        world.deliver(arc, "ywc_shu.1025")
        self.assertIn("ywc_shu_port_review_mature", state)
        for option in ("central_burden", "shared_burden", "reduce_burden", "retry_after_repair"):
            self.assertFalse(legal(world, burden, option), option)
            replay_effect(world, burden, option)
            self.assertNotIn("ywc_shu_port_review_due", state, option)
            self.assertIn("ywc_shu_port_review_mature", state, option)

    def test_interruption_notice_waits_when_the_port_is_still_lost(self):
        world, arc = reached_port_burden(); state = world.countries["SHU"]
        burden = world.deliver(arc, "ywc_shu.1024")
        world.choose(arc, burden, "central_burden", contexts=False)
        port = state["states"][0]["buildings"].pop(
            next(i for i, b in enumerate(state["states"][0]["buildings"]) if b["type"] == "building_port"))
        world.pulse(arc)
        notice = world.deliver(arc, "ywc_shu.1024")
        for option in ("central_burden", "shared_burden", "retry_after_repair"):
            self.assertFalse(legal(world, notice, option), option)
            replay_effect(world, notice, option)
            self.assertIn("ywc_shu_port_review_interrupted", state)
            self.assertNotIn("ywc_shu_port_review_due", state)
        self.assertTrue(legal(world, notice, "resume_pending_port_step"))
        world.choose(arc, notice, "resume_pending_port_step", contexts=False)
        self.assertEqual(state.get("ywc_shu_port_pending_event"), 1025)
        state["states"][0]["buildings"].append(port)

    def test_shared_burden_requires_recorded_sharing_or_review_right(self):
        world, arc = reached_port_burden(); state = world.countries["SHU"]
        burden = world.deliver(arc, "ywc_shu.1024")
        self.assertFalse(legal(world, burden, "shared_burden"))
        replay_effect(world, burden, "shared_burden")
        self.assertNotIn("ywc_shu_port_review", state)
        state["ywc_shu_port_local_share"] = 1
        self.assertTrue(legal(world, burden, "shared_burden"))
        world.choose(arc, burden, "shared_burden", contexts=False)
        self.assertEqual(state.get("ywc_shu_port_burden"), 2)


class ShuPortCalendarTests(unittest.TestCase):
    def test_new_port_loan_does_not_preserve_a_cleared_fiscal_arrears_modifier(self):
        from datetime import date
        from pathlib import Path
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"gold_reserves": 0, "ywc_shu_port_cost": 1000,
            "ywc_shu_port_advance_offer_open": 1, "ywc_shu_merchant_advance_unpaid": 1,
            "ywc_shu_merchant_principal": 1000, "ywc_shu_merchant_repayment_months": 11})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1837, 2, 1))
        world.active["SHU"].append("ywc_je_v03_shu_port_customs")
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_country_monthly("SHU")
        self.assertTrue(any(tag == "SHU" and row.get("modifier") == "ywc_shu_local_credit_arrears" for tag, row in world.modifiers))
        world.run_script("ywc_shu_accept_port_advance = yes", "SHU")
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        world.advance_days(28); world.run_country_monthly("SHU")
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        self.assertFalse(any(tag == "SHU" and row.get("modifier") == "ywc_shu_local_credit_arrears" for tag, row in world.modifiers))

    def test_new_loan_matures_after_twelve_calendar_months(self):
        from datetime import date
        from pathlib import Path
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"ywc_shu_port_cost": 1000, "ywc_shu_port_advance_offer_open": 1,
                                      "ywc_v03_shu_v03_shu_port_treasury_started": 1})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1836, 1, 15))
        world.active["SHU"].append("ywc_je_v03_shu_port_customs")
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_script("ywc_shu_accept_port_advance = yes", "SHU")
        self.assertEqual(world.treasury["SHU"], 1000)
        for offset in range(12):
            year = 1836 + (offset + 1) // 12; month_number = (offset + 1) % 12 + 1
            target = date(year, month_number, 1)
            world.advance_days((target - world.date).days); world.run_country_monthly("SHU")
        self.assertEqual(world.date, date(1837, 1, 1))
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], 1000)
        world.advance_days(31); world.run_country_monthly("SHU")
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], 0)

    def test_old_port_arrears_survive_repayment_of_the_fiscal_advance(self):
        from datetime import date
        from pathlib import Path
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"gold_reserves": 0,
            "ywc_v03_shu_v03_shu_port_treasury_started": 1, "ywc_shu_port_route": 1,
            "ywc_shu_scaled_debt_rise_months": 0, "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1, "ywc_shu_port_review_mature": 1, "ywc_shu_port_receipts_checked": 1,
            "ywc_shu_port_fee_paid": 1, "ywc_shu_port_advance_unpaid": 1,
            "ywc_shu_port_principal": 1000, "ywc_shu_merchant_advance_unpaid": 1,
            "ywc_shu_merchant_principal": 1000, "ywc_shu_merchant_repayment_months": 11})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1837, 2, 1))
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        legacy = Path("tests/fixtures/v03_shu_legacy_port_close.txt").read_text(encoding="utf-8")
        original = world.effects["ywc_shu_port_close_unified"]
        world.effects["ywc_shu_port_close_unified"] = parse(legacy)[0][2]
        world.run_script("ywc_shu_port_close_unified = yes", "SHU")
        world.effects["ywc_shu_port_close_unified"] = original
        self.assertTrue(any(tag == "SHU" and row.get("modifier") == "ywc_shu_local_credit_arrears" for tag,row in world.modifiers))
        state["gold_reserves"] = 1000
        world.run_country_monthly("SHU")
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        self.assertTrue(any(tag == "SHU" and row.get("modifier") == "ywc_shu_local_credit_arrears" for tag,row in world.modifiers))
        self.assertIn("ywc_shu_port_repayment_due", state)

    def test_two_credits_never_clear_each_others_arrears_in_the_model(self):
        from datetime import date
        from pathlib import Path
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"gold_reserves": 1000,
            "ywc_shu_merchant_advance_unpaid": 1, "ywc_shu_merchant_principal": 1000,
            "ywc_shu_merchant_repayment_months": 11,
            "ywc_shu_port_advance_unpaid": 1, "ywc_shu_port_principal": 1000,
            "ywc_shu_port_repayment_clock_initialized": 1})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1837, 2, 1))
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_country_monthly("SHU")
        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], -1000)
        self.assertTrue(any(tag == "SHU" and row.get("modifier") == "ywc_shu_port_credit_arrears" for tag,row in world.modifiers))
        state["gold_reserves"] += 1000
        world.advance_days(28); world.run_country_monthly("SHU")
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], -2000)

    def test_port_payment_keeps_a_separately_unpaid_fiscal_arrear(self):
        from datetime import date
        from pathlib import Path
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"gold_reserves": 1000,
            "ywc_shu_merchant_advance_unpaid": 1, "ywc_shu_merchant_principal": 2000,
            "ywc_shu_merchant_repayment_months": 11,
            "ywc_shu_port_advance_unpaid": 1, "ywc_shu_port_principal": 1000,
            "ywc_shu_port_repayment_clock_initialized": 1})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1837, 2, 1))
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_country_monthly("SHU")
        self.assertIn("ywc_shu_merchant_advance_unpaid", state)
        self.assertNotIn("ywc_shu_port_advance_unpaid", state)
        self.assertEqual(world.treasury["SHU"], -1000)
        self.assertTrue(any(tag == "SHU" and row.get("modifier") == "ywc_shu_local_credit_arrears" for tag,row in world.modifiers))


if __name__ == "__main__":
    unittest.main()

"""SHU military funding: real authored queue, cash and twelve-month obligation."""
import copy
import unittest

from shu_kor_strict_review_runtime import Strict, facts
from test_v03_shu_content import shu_monthly_effect
from test_v03_shu_kor_c1_c4_strict import play
from test_v03_shu_merchant_obligations import option, replay_effect


def reached_military():
    world = Strict("shu"); world.countries["SHU"] = facts()
    arc = world.cat["arcs"][0]
    for number, key in ((1000, "pilot_state_sichuan"), (1001, "local_register"),
                        (1002, "time_limited_exemption")):
        play(world, arc, number, key)
    return world, arc, world.deliver(arc, "ywc_shu.1003")


def legal(world, event, name):
    return next(row["legal"] for row in world.options(event) if row["option"] == name)


def month(world):
    world.advance_months(1); world.elapsed_months += 1
    world.execute(shu_monthly_effect(), "SHU")


class ShuMilitaryFundingTests(unittest.TestCase):
    def test_first_payment_requires_cash_and_safe_finances_at_display_and_execution(self):
        for defect in ("cash", "negative_income", "default", "bankruptcy", "bad_base"):
            with self.subTest(defect=defect):
                world, _, event = reached_military()
                state = world.countries["SHU"]
                if defect == "cash": state["gold_reserves"] = 0
                if defect == "negative_income": state["net_fixed_income"] = -1
                if defect == "bad_base": state["ywc_shu_fiscal_cost"] = -100
                if defect == "default": state["in_default"] = True
                if defect == "bankruptcy": world.modifiers.append(("SHU", {"modifier": "declared_bankruptcy"}))
                self.assertFalse(legal(world, event, "pay_partial_advance"))
                self.assertTrue(legal(world, event, "budget_queue"))
                before = world.treasury["SHU"]
                replay_effect(world, event, "pay_partial_advance")
                self.assertEqual(world.treasury["SHU"], before)
                self.assertNotIn("ywc_shu_military_payer", state)
                self.assertNotIn("ywc_shu_military_contract_active", state)
                self.assertNotEqual(state.get("ywc_shu_pending_event"), 1004)

    def test_twelve_installments_are_charged_once_and_not_completed_early(self):
        world, arc, event = reached_military()
        state = world.countries["SHU"]
        world.choose(arc, event, "pay_partial_advance", contexts=False)
        self.assertEqual(world.treasury["SHU"], -250)
        self.assertEqual(state.get("ywc_shu_military_payer"), 1)
        self.assertEqual(state.get("ywc_shu_military_contract_active"), 1)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 1)
        state["yearly_gross_income"] = 520000  # the committed rate remains the opening snapshot
        world.execute(shu_monthly_effect(), "SHU")
        self.assertEqual(world.treasury["SHU"], -250)
        for _ in range(11):
            month(world); previous = world.treasury["SHU"]
            world.execute(shu_monthly_effect(), "SHU")
            self.assertEqual(world.treasury["SHU"], previous, "same-month duplicate callback must not charge twice")
        self.assertEqual(world.treasury["SHU"], -3000)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 12)
        self.assertNotIn("ywc_shu_military_contract_fulfilled", state)
        month(world)
        self.assertEqual(state.get("ywc_shu_military_contract_fulfilled"), 1)
        self.assertNotIn("ywc_shu_military_contract_active", state)
        for _ in range(2): month(world)
        self.assertEqual(world.treasury["SHU"], -3000)

    def test_missed_installments_accrue_and_are_paid_after_the_arc_exits(self):
        world, arc, event = reached_military(); state = world.countries["SHU"]
        world.choose(arc, event, "pay_partial_advance", contexts=False)
        state["ywc_shu_arc_abandoned"] = 1
        world.run("ywc_shu_close_as_breach")
        state["gold_reserves"] = 0
        for _ in range(3): month(world)
        self.assertEqual(state.get("ywc_shu_military_installments_due"), 4)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 1)
        self.assertEqual(world.treasury["SHU"], -250)
        state["gold_reserves"] = 100000
        for _ in range(11): month(world)
        self.assertEqual(state.get("ywc_shu_military_installments_due"), 12)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 12)
        self.assertEqual(state.get("ywc_shu_military_contract_fulfilled"), 1)
        self.assertEqual(world.treasury["SHU"], -3000)

    def test_corrupt_contract_amount_does_not_create_money_or_fake_payment(self):
        for defect in ("missing", "zero", "negative"):
            with self.subTest(defect=defect):
                world, arc, event = reached_military(); state = world.countries["SHU"]
                world.choose(arc, event, "pay_partial_advance", contexts=False)
                if defect == "missing": state.pop("ywc_shu_military_installment")
                if defect == "zero": state["ywc_shu_military_installment"] = 0
                if defect == "negative": state["ywc_shu_military_installment"] = -250
                before = (world.treasury["SHU"], state["ywc_shu_military_installments_due"], state["ywc_shu_military_installments_paid"])
                month(world)
                self.assertEqual((world.treasury["SHU"], state["ywc_shu_military_installments_due"], state["ywc_shu_military_installments_paid"]), before)
                self.assertNotIn("ywc_shu_military_contract_fulfilled", state)

    def test_impossible_installment_counts_freeze_the_ledger(self):
        for defect in ("missing_due", "due_above_cap", "paid_above_due", "paid_below_one", "fractional_due", "fractional_paid"):
            with self.subTest(defect=defect):
                world, arc, event = reached_military(); state = world.countries["SHU"]
                world.choose(arc, event, "pay_partial_advance", contexts=False)
                if defect == "missing_due": state.pop("ywc_shu_military_installments_due")
                if defect == "due_above_cap": state["ywc_shu_military_installments_due"] = 13
                if defect == "paid_above_due": state["ywc_shu_military_installments_paid"] = 2
                if defect == "paid_below_one": state["ywc_shu_military_installments_paid"] = 0
                if defect == "fractional_due": state["ywc_shu_military_installments_due"] = 11.5
                if defect == "fractional_paid": state.update({"ywc_shu_military_installments_due": 2, "ywc_shu_military_installments_paid": 1.5})
                before = (world.treasury["SHU"], state.get("ywc_shu_military_installments_due"), state.get("ywc_shu_military_installments_paid"))
                month(world)
                self.assertEqual((world.treasury["SHU"], state.get("ywc_shu_military_installments_due"), state.get("ywc_shu_military_installments_paid")), before)
                self.assertNotIn("ywc_shu_military_contract_fulfilled", state)

    def test_default_pauses_actual_payment_without_erasing_due_installments(self):
        world, arc, event = reached_military(); state = world.countries["SHU"]
        world.choose(arc, event, "pay_partial_advance", contexts=False)
        state["in_default"] = True
        for _ in range(3): month(world)
        self.assertEqual(state.get("ywc_shu_military_installments_due"), 4)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 1)
        self.assertEqual(world.treasury["SHU"], -250)
        state["in_default"] = False; month(world)
        self.assertEqual(state.get("ywc_shu_military_installments_due"), 5)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 2)
        self.assertEqual(world.treasury["SHU"], -500)

    def test_old_one_time_payment_does_not_start_a_new_contract(self):
        world, arc, event = reached_military(); state = world.countries["SHU"]
        state.update({"ywc_shu_military_advance_paid": 1, "ywc_shu_military_payer": 1})
        before = world.treasury["SHU"]
        self.assertFalse(legal(world, event, "pay_partial_advance"))
        world.choose(arc, event, "continue_military_recorded", contexts=False)
        for _ in range(14): month(world)
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_military_contract_active", state)
        self.assertNotIn("ywc_shu_military_contract_fulfilled", state)

    def test_a_recorded_payer_cannot_be_changed_by_old_options(self):
        world, arc, event = reached_military(); state = world.countries["SHU"]
        world.choose(arc, event, "budget_queue", contexts=False)
        before = (state.get("ywc_shu_military_payer"), state.get("ywc_shu_pending_event"), world.treasury["SHU"])
        for key in ("pay_partial_advance", "provincial_pay", "budget_queue"):
            replay_effect(world, event, key)
            self.assertEqual((state.get("ywc_shu_military_payer"), state.get("ywc_shu_pending_event"), world.treasury["SHU"]), before)
        self.assertNotIn("ywc_shu_military_contract_active", state)

    def test_pilot_loss_blocks_new_contract_before_the_monthly_recovery(self):
        world, _, event = reached_military(); state = world.countries["SHU"]
        state["states"][0]["owned"] = False
        self.assertFalse(legal(world, event, "pay_partial_advance"))
        before = world.treasury["SHU"]
        replay_effect(world, event, "pay_partial_advance")
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_military_contract_active", state)
        self.assertTrue(any(row["legal"] and row["weight"] > 0 for row in world.options(event)))

    def test_unanswered_military_choice_returns_after_pilot_loss(self):
        world, arc, old_event = reached_military(); state = world.countries["SHU"]
        new_state = copy.deepcopy(state["states"][0]); new_state["region"] = "s:STATE_CHONGQING"
        state["states"].append(new_state); state["states"][0]["owned"] = False
        world.pulse(arc)
        self.assertEqual(state.get("ywc_shu_resume_event"), 1003)
        remaining = [row for row in world.options(old_event) if row["legal"] and row["weight"] > 0]
        self.assertEqual([row["option"] for row in remaining], ["dismiss_military_stale"])
        reselect = world.deliver(arc, "ywc_shu.1001")
        world.choose(arc, reselect, "reselect_state_chongqing", contexts=False)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1003)
        before = world.treasury["SHU"]
        replay_effect(world, old_event, "pay_partial_advance")
        self.assertEqual(world.treasury["SHU"], before)
        again = world.deliver(arc, "ywc_shu.1003")
        world.choose(arc, again, "provincial_pay", contexts=False)
        self.assertEqual(state.get("ywc_shu_military_payer"), 3)

    def test_old_failed_payment_can_be_reconciled_without_fabricating_payment(self):
        import json
        from pathlib import Path
        from clausewitz_harness import parse
        fixture = json.loads(Path("tests/fixtures/v03_shu_legacy_military_advance.json").read_text(encoding="utf-8"))
        world, arc, event = reached_military(); state = world.countries["SHU"]
        state["net_fixed_income"] = -1
        new_helper = world.effects["ywc_shu_pay_military_advance_once"]
        world.effects["ywc_shu_pay_military_advance_once"] = parse(fixture["helper"])[0][2]
        world.execute(parse(fixture["option_effect"].strip()[1:-1]), "SHU")
        world.effects["ywc_shu_pay_military_advance_once"] = new_helper
        self.assertEqual(world.treasury["SHU"], 0)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1004)
        self.assertNotIn("ywc_shu_military_payer", state)
        self.assertNotIn("ywc_shu_military_advance_paid", state)
        state["net_fixed_income"] = 100
        play(world, arc, 1004, "local_mediation")
        play(world, arc, 1005, "refuse_private_advance")
        play(world, arc, 1006, "settle_as_provincial")
        play(world, arc, 1007, "provincial_retention")
        world.advance_months(6); world.elapsed_months += 6
        review = world.deliver(arc, "ywc_shu.1008")
        world.choose(arc, review, "review_in_peace", contexts=False)
        close = world.deliver(arc, "ywc_shu.1009")
        self.assertFalse(legal(world, close, "confirm_provincial_share"))
        for blocked in ("later_queue", "merchant_unpaid", "old_paid", "active_contract", "lost_pilot"):
            with self.subTest(blocked=blocked):
                if blocked == "later_queue": state["ywc_shu_pending_event"] = 1008
                if blocked == "merchant_unpaid": state["ywc_shu_merchant_advance_unpaid"] = 1
                if blocked == "old_paid": state["ywc_shu_military_advance_paid"] = 1
                if blocked == "active_contract": state["ywc_shu_military_contract_active"] = 1
                if blocked == "lost_pilot": state["states"][0]["owned"] = False
                snapshot = copy.deepcopy(state); balance = world.treasury["SHU"]
                self.assertFalse(legal(world, close, "reconcile_legacy_military_budget"))
                replay_effect(world, close, "reconcile_legacy_military_budget")
                self.assertEqual((state, world.treasury["SHU"]), (snapshot, balance))
                if blocked == "later_queue": state.pop("ywc_shu_pending_event")
                if blocked == "merchant_unpaid": state.pop("ywc_shu_merchant_advance_unpaid")
                if blocked == "old_paid": state.pop("ywc_shu_military_advance_paid")
                if blocked == "active_contract": state.pop("ywc_shu_military_contract_active")
                if blocked == "lost_pilot": state["states"][0]["owned"] = True
        self.assertTrue(legal(world, close, "reconcile_legacy_military_budget"))
        before = world.treasury["SHU"]
        world.choose(arc, close, "reconcile_legacy_military_budget", contexts=False)
        self.assertEqual(state.get("ywc_shu_military_payer"), 2)
        self.assertEqual(state.get("ywc_shu_fiscal_outcome_provincial_share"), 1)
        self.assertEqual(world.treasury["SHU"], before)
        self.assertNotIn("ywc_shu_military_advance_paid", state)
        self.assertNotIn("ywc_shu_military_contract_active", state)
        replay_effect(world, close, "reconcile_legacy_military_budget")
        self.assertEqual(world.treasury["SHU"], before)

    def test_all_three_recorded_payers_allow_provincial_fiscal_settlement(self):
        for military_choice in ("pay_partial_advance", "budget_queue", "provincial_pay"):
            with self.subTest(payer=military_choice):
                world, arc, event = reached_military(); state = world.countries["SHU"]
                world.choose(arc, event, military_choice, contexts=False)
                play(world, arc, 1004, "local_mediation")
                play(world, arc, 1005, "refuse_private_advance")
                play(world, arc, 1006, "settle_as_provincial")
                play(world, arc, 1007, "provincial_retention")
                world.advance_months(6); world.elapsed_months += 6
                review = world.deliver(arc, "ywc_shu.1008")
                world.choose(arc, review, "review_in_peace", contexts=False)
                close = world.deliver(arc, "ywc_shu.1009")
                self.assertTrue(legal(world, close, "confirm_provincial_share"))
                world.choose(arc, close, "confirm_provincial_share", contexts=False)
                self.assertEqual(state.get("ywc_shu_fiscal_outcome_provincial_share"), 1)


class ShuMilitaryCalendarTests(unittest.TestCase):
    def test_contract_cannot_be_fulfilled_before_twelve_calendar_months(self):
        from datetime import date
        from pathlib import Path
        from clausewitz_harness import parse
        from kor_partner_protocol_runtime import PartnerWorld
        state = facts(); state.update({"ywc_v03_shu_v03_shu_fiscal_register_last_event": 4,
                                      "ywc_shu_fiscal_cost": 1000,
                                      "ywc_shu_v03_pilot_state": 1,
                                      "ywc_shu_fiscal_cost_captured": 1})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1836, 1, 15))
        world.active["SHU"].append("ywc_je_v03_shu_register_pilot")
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_script("ywc_shu_pay_military_advance_once = yes", "SHU")
        self.assertEqual(world.treasury["SHU"], -250)
        for offset in range(12):
            year = 1836 + (offset + 1) // 12; month_number = (offset + 1) % 12 + 1
            target = date(year, month_number, 1)
            world.advance_days((target - world.date).days); world.run_country_monthly("SHU")
            if offset == 0:  # February's pulse is earlier than one full month after signing.
                self.assertEqual(state.get("ywc_shu_military_installments_paid"), 1)
        self.assertEqual(world.date, date(1837, 1, 1))
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 12)
        self.assertEqual(world.treasury["SHU"], -3000)
        self.assertNotIn("ywc_shu_military_contract_fulfilled", state)
        world.advance_days(31); world.run_country_monthly("SHU")
        self.assertEqual(state.get("ywc_shu_military_contract_fulfilled"), 1)
        self.assertEqual(world.treasury["SHU"], -3000)
        world.run_country_monthly("SHU")
        self.assertEqual(world.treasury["SHU"], -3000)

    def test_two_debts_compete_for_cash_in_one_source_callback(self):
        from datetime import date
        from pathlib import Path
        from clausewitz_harness import parse
        from kor_partner_protocol_runtime import PartnerWorld, _add_months
        state = facts(); state.update({"ywc_v03_shu_v03_shu_fiscal_register_last_event": 4,
                                      "ywc_shu_fiscal_cost": 1000,
                                      "ywc_shu_v03_pilot_state": 1,
                                      "ywc_shu_fiscal_cost_captured": 1})
        world = PartnerWorld({"SHU": state}, tag="shu", start_date=date(1836, 1, 15))
        world.active["SHU"].append("ywc_je_v03_shu_register_pilot")
        actions = Path("yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig")
        world.merge_on_actions(parse(actions))
        world.run_script("ywc_shu_pay_military_advance_once = yes", "SHU")
        world.advance_days(5); state["ywc_v03_shu_v03_shu_fiscal_register_last_event"] = 6
        world.run_script("ywc_shu_accept_merchant_advance = yes", "SHU")
        for offset in range(12):
            year = 1836 + (offset + 1) // 12; month_number = (offset + 1) % 12 + 1
            target = date(year, month_number, 1)
            world.advance_days((target - world.date).days)
            state["gold_reserves"] = -world.treasury["SHU"]  # no available cash
            world.run_country_monthly("SHU")
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 1)
        world.advance_days(31)  # 1837-02-01, after both contracts reached their anniversaries
        state["gold_reserves"] = 1000 - world.treasury["SHU"]
        before = world.treasury["SHU"]
        world.run_country_monthly("SHU")
        self.assertEqual(world.treasury["SHU"] - before, -1000)
        self.assertEqual(state.get("ywc_shu_merchant_advance_repaid"), 1)
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 1)
        self.assertEqual(state.get("ywc_shu_military_installments_due"), 12)
        for _ in range(11):
            target = _add_months(world.date, 1)
            world.advance_days((target - world.date).days)
            state["gold_reserves"] = 1000 - world.treasury["SHU"]
            world.run_country_monthly("SHU")
        self.assertEqual(state.get("ywc_shu_military_installments_paid"), 12)
        self.assertEqual(state.get("ywc_shu_military_contract_fulfilled"), 1)


if __name__ == "__main__":
    unittest.main()

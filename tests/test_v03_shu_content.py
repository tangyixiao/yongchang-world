"""Focused offline checks for the first SHU fiscal-register content card."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from clausewitz_harness import PulseWorld


CATALOG_PATH = ROOT / "data/content/v03/countries/shu.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_shu_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_shu_triggers.txt"
EVENT_IDS = [f"ywc_shu.{number}" for number in range(1000, 1010)]
JE_IDS = ["ywc_je_v03_shu_register_pilot", "ywc_je_v03_shu_fiscal_settlement"]


class ShuContentCardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.arc = cls.catalog["arcs"][0]
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")

    def test_locked_identity_and_full_bilingual_card(self):
        self.assertEqual(self.catalog["key"], "country_shu")
        self.assertEqual(self.catalog["layer"], "country")
        self.assertEqual(self.catalog["runtime_tags"], ["SHU"])
        self.assertEqual(self.arc["slug"], "v03_shu_fiscal_register")
        self.assertEqual(self.arc["era"], "foundation")
        self.assertEqual([row["id"] for row in self.arc["events"]], EVENT_IDS)
        self.assertEqual([row["id"] for row in self.arc["journals"]], JE_IDS)
        for event in self.arc["events"]:
            self.assertTrue(event["title"]["zh"] and event["title"]["en"])
            self.assertTrue(event["desc"]["zh"] and event["desc"]["en"])
            self.assertGreaterEqual(len(event["options"]), 2)
        self.assertTrue(all(row["goal"].strip() != "{ always = yes }" for row in self.arc["journals"]))
        goal = self.arc["journals"][0]["goal"]
        self.assertIn("ywc_shu_register_pilot_resolved", goal)
        self.assertIn("ywc_shu_first_audit", goal)
        self.assertIn("ywc_shu_second_audit", goal)
        self.assertIn("ywc_shu_pilot_outcome = 3", goal)
        for i, event in enumerate(self.arc["events"], 1):
            self.assertIn(f"last_event value = {i}", event["immediate"])

    def test_weekly_income_cost_is_documented_and_each_charge_is_real_and_guarded(self):
        # The official yearly_gross_income script value is captured at opening and converted to a week.
        self.assertIn("value = yearly_gross_income", self.effects)
        self.assertIn("0.0192307692308", self.effects)
        self.assertIn("max = 100", self.effects)
        self.assertRegex(self.effects, r"add_treasury\s*=\s*\{\s*value\s*=\s*var:ywc_shu_fiscal_cost")
        self.assertIn("ywc_shu_audit_installment_paid", self.effects)
        self.assertIn("ywc_shu_compensation_paid", self.effects)
        note = self.catalog["arcs"][0]["events"][0]["options"][0]["cost_note"]["zh"]
        self.assertIn("年总收入÷52", note)
        self.assertIn("最低100", note)

    def test_route_outcomes_are_distinct_and_delayed_choices_have_two_readers(self):
        outcomes = ("central_audit", "provincial_share", "capped_legacy", "withdrawn_breach")
        for outcome in outcomes:
            self.assertIn(f"ywc_shu_fiscal_outcome_{outcome}", self.effects)
        # Verify delayed variables in executable gates/helpers, not self-declared reads metadata.
        e2 = self.arc["events"][1]
        e6 = self.arc["events"][6]
        e7 = self.arc["events"][7]
        e10 = self.arc["events"][9]
        second_audit = self.effects.split("ywc_shu_mark_first_audit = {", 1)[1].split("\nywc_shu_choose_landlord_compromise", 1)[0]
        self.assertIn("var:ywc_shu_audit_mode", second_audit)
        self.assertIn("ywc_shu_mark_first_audit = yes", e2["options"][0]["effect"])
        self.assertIn("ywc_shu_record_second_audit = yes", e6["options"][0]["effect"])
        self.assertIn("var:ywc_shu_audit_mode", e7["trigger"])
        self.assertIn("has_variable = ywc_shu_local_audit_right", e7["trigger"])
        provincial_close = self.effects.split("ywc_shu_close_as_provincial = {",1)[1].split("\nywc_shu_close_as_legacy",1)[0]
        self.assertIn("has_variable = ywc_shu_local_audit_right", provincial_close)
        self.assertIn("ywc_shu_close_as_provincial = yes", e10["options"][1]["effect"])
        self.assertIn("ywc_shu_first_audit", self.effects)
        self.assertIn("ywc_shu_second_audit", self.effects)
        second_audit = self.effects.split("ywc_shu_record_second_audit = {", 1)[1].split("\nywc_shu_start_settlement_review", 1)[0]
        self.assertLess(second_audit.index("ywc_shu_pay_audit_second_half_once = yes"), second_audit.index("set_variable = { name = ywc_shu_second_audit value = 1 }"))
        self.assertIn("ywc_shu_v03_real_execution_ready = yes", second_audit)
        self.assertIn("ywc_shu_settlement_review", self.effects)
        self.assertIn("days = 90", self.effects)
        self.assertIn("days = 180", self.effects)
        self.assertIn("days = 365", self.arc["journals"][0]["script"])
        self.assertIn("days = 1095", self.arc["journals"][0]["script"])
        self.assertIn("NOT = { has_variable = ywc_shu_blocked_12_due }", self.arc["journals"][0]["script"])
        self.assertIn("NOT = { has_variable = ywc_shu_blocked_36_due }", self.arc["journals"][0]["script"])
        wartime_choice = next(event for event in self.arc["events"] if event["id"] == "ywc_shu.1008")["options"][1]["effect"]
        self.assertIn("remove_variable = ywc_shu_settlement_review_due", wartime_choice)
        self.assertIn("ywc_shu_v03_real_execution_ready = yes", self.arc["journals"][1]["script"])
        self.assertIn("gold_reserves >= { value = var:ywc_shu_fiscal_cost multiply = 0.5 }", self.effects)
        self.assertIn("net_fixed_income >= 0", self.effects)

    def test_opening_and_resolution_helpers_are_idempotent_in_the_shared_harness(self):
        world = PulseWorld(self.effects, {"SHU": {}})
        world.run("ywc_shu_open_register_once")
        world.run("ywc_shu_open_register_once")
        self.assertEqual(world.countries["SHU"]["ywc_shu_register_open"], 1)
        for marker in ("ywc_shu_first_audit", "ywc_shu_second_audit", "ywc_shu_fiscal_outcome_central_audit", "ywc_shu_fiscal_outcome_provincial_share"):
            self.assertNotIn(marker, world.countries["SHU"], f"zero-valued flags must not look completed via has_variable: {marker}")
        self.assertEqual(world.events, [], "open helper only initializes state; JE activation owns its one-shot event")
        self.assertIn("set_variable = { name = ywc_shu_pending_event value = 1000 }", self.arc["journals"][0]["script"])
        self.assertIn("ywc_v03_can_deliver_major = yes", self.arc["journals"][0]["script"])
        # JE monthly pulse retains the queued event during shared cooldown, then dispatches it once eligible.
        self.assertIn("var:ywc_shu_pending_event = 1000", self.arc["journals"][0]["script"])
        self.assertIn("trigger_event = { id = ywc_shu.1000 }", self.arc["journals"][0]["script"])
        self.assertNotIn("ywc_shu_close_once", self.effects)

    def test_final_event_is_delivered_by_the_settlement_dispatcher(self):
        settlement = self.arc["journals"][1]["script"]
        self.assertIn("var:ywc_shu_pending_event = 1009", settlement)
        self.assertIn("trigger_event = { id = ywc_shu.1009 }", settlement)
        self.assertIn("ywc_shu_pending_event value = 1009", self.arc["events"][8]["options"][0]["effect"])

    def test_cost_base_is_captured_at_opening_once(self):
        world = PulseWorld(self.effects, {"SHU": {"yearly_gross_income": 52_000}})
        world.run("ywc_shu_open_register_once")
        self.assertAlmostEqual(world.countries["SHU"]["ywc_shu_fiscal_cost"], 1_000, places=5)
        world.countries["SHU"]["yearly_gross_income"] = 104_000
        world.run("ywc_shu_capture_cost_base")
        self.assertAlmostEqual(world.countries["SHU"]["ywc_shu_fiscal_cost"], 1_000, places=5)

    def test_first_audit_installment_is_charged_at_most_once(self):
        world = PulseWorld(self.effects, {"SHU": {"yearly_gross_income": 52_000, "net_fixed_income": 0, "gold_reserves": 10_000}})
        world.run("ywc_shu_pay_audit_half_once")
        charged = world.treasury["SHU"]
        world.run("ywc_shu_pay_audit_half_once")
        self.assertAlmostEqual(charged, -500, places=5)
        self.assertEqual(world.treasury["SHU"], charged)
        self.assertEqual(world.countries["SHU"]["ywc_shu_audit_installment_paid"], 1)

    def test_all_ten_event_deliveries_consume_the_shared_major_cooldown(self):
        for event in self.arc["events"]:
            self.assertIn("ywc_v03_can_deliver_major = yes", event["trigger"])
            self.assertIn("ywc_v03_mark_major_delivered = yes", event["immediate"])
            self.assertTrue(all("trigger_event =" not in option["effect"] for option in event["options"]))
        for journal in self.arc["journals"]:
            self.assertIn("ywc_v03_can_deliver_major = yes", journal["script"])

    def test_failed_or_war_exit_preserves_paid_debt_and_allows_one_close(self):
        lifecycle_stub = "\nywc_v03_release_arc_shu_v03_shu_fiscal_register = { set_variable = { name = ywc_v03_shu_v03_shu_fiscal_register_settled value = 1 } }\n"
        world = PulseWorld(self.effects + lifecycle_stub, {"SHU": {"ywc_shu_audit_mode": 1, "ywc_shu_advance_paid": 1,
                                                     "ywc_shu_fiscal_cost": 100, "ywc_shu_pilot_state_lost": 1}})
        world.run("ywc_shu_close_as_breach")
        self.assertEqual(world.countries["SHU"]["ywc_shu_fiscal_outcome_withdrawn_breach"], 1)
        self.assertEqual(world.countries["SHU"]["ywc_shu_advance_paid"], 1)
        world.run("ywc_shu_close_as_breach")
        self.assertEqual(sum(value for _, value in world.countries["SHU"].items() if re.fullmatch(r"ywc_shu_fiscal_outcome_.*", _) ), 1)


if __name__ == "__main__":
    unittest.main()

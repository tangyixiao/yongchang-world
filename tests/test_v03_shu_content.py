"""Focused offline checks for the first SHU fiscal-register content card."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))

from clausewitz_harness import PulseWorld, parse


CATALOG_PATH = ROOT / "data/content/v03/countries/shu.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_shu_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_shu_triggers.txt"
EVENT_IDS = [f"ywc_shu.{number}" for number in range(1000, 1010)]
JE_IDS = ["ywc_je_v03_shu_register_pilot", "ywc_je_v03_shu_fiscal_settlement"]


def pulse_effect_nodes(journal):
    top = parse(journal["script"])
    pulse = next(body for key, _, body in top if key == "on_monthly_pulse")
    effect = next(body for key, _, body in pulse if key == "effect")
    return effect


def shu_monthly_effect():
    """Follow the actual additive hook to its owned repayment effect."""
    source = parse((ROOT / "yongchang_world/common/on_actions/ywc_v03_shu_accounts.txt").read_text(encoding="utf-8-sig"))
    hook = next(body for key, _, body in source if key == "on_monthly_pulse_country")
    children = [name for key, _, body in hook if key == "on_actions" for name, _, _ in body]
    if children.count("ywc_v03_shu_accounts_monthly") != 1:
        raise AssertionError("the SHU repayment callback must be appended exactly once")
    child = next(body for key, _, body in source if key == "ywc_v03_shu_accounts_monthly")
    return next(body for key, _, body in child if key == "effect")


def parse_country_effect(script):
    # This review exercises country-card behavior; the cooldown write is owned by shared lifecycle code.
    script = script.replace("ywc_v03_mark_major_delivered = yes", "set_variable = { name = test_major_delivered value = 1 }")
    return parse(script[1:-1] if script.startswith("{") and script.endswith("}") else script)


def inject_fact_triggers(nodes):
    """Replace only non-executable scripted-trigger predicates with fixture facts."""
    facts = {
        "ywc_v03_can_deliver_major": "test_cooldown_clear",
        "ywc_shu_v03_unsettled": "test_unsettled",
        "ywc_shu_v03_real_execution_ready": "test_ready",
        "ywc_shu_v03_limited_execution_ready": "test_limited_ready",
        "ywc_shu_v03_has_pilot_state": "test_has_pilot",
        "ywc_shu_v03_has_candidate_state": "test_has_candidate",
        "ywc_shu_v03_finance_safe": "test_finance_safe",
    }
    result = []
    for key, comparison, value in nodes:
        if key in facts:
            result.append(("has_variable", "=", facts[key]))
        elif key == "ywc_shu_v03_settlement_execution_ready":
            result.append(("OR", "=", [
                ("AND", "=", [("var:ywc_shu_settlement_mode", "=", "3"),
                                ("has_variable", "=", "test_limited_ready")]),
                ("AND", "=", [("OR", "=", [("var:ywc_shu_settlement_mode", "=", "1"),
                                             ("var:ywc_shu_settlement_mode", "=", "2")]),
                                ("has_variable", "=", "test_ready")]),
            ]))
        elif key == "any_scope_state":
            result.append(("has_variable", "=", "test_owned_state"))
        elif isinstance(value, list):
            result.append((key, comparison, inject_fact_triggers(value)))
        else:
            result.append((key, comparison, value))
    return result


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
        self.assertIn("name = ywc_shu_fiscal_cost divide = 52", self.effects)
        self.assertIn("max = 100", self.effects)
        self.assertRegex(self.effects, r"add_treasury\s*=\s*\{\s*value\s*=\s*var:ywc_shu_fiscal_cost")
        self.assertIn("ywc_shu_audit_installment_paid", self.effects)
        self.assertIn("ywc_shu_compensation_paid", self.effects)
        note = self.catalog["arcs"][0]["events"][1]["options"][0]["cost_note"]["zh"]
        self.assertIn("年总收入÷52", note)
        self.assertTrue(any("年总收入÷52" in row["cost_note"]["zh"]
                            for event in self.arc["events"] for row in event["options"]))
        self.assertTrue(any("最低100" in row["cost_note"]["zh"]
                            for event in self.arc["events"] for row in event["options"]))

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

    def test_appeal_owner_and_merchant_decision_change_real_second_audit_eligibility(self):
        base = {"yearly_gross_income": 52_000, "gold_reserves": 2_000, "net_fixed_income": 0,
                "ywc_shu_audit_mode": 1, "ywc_shu_audit_installment_paid": 1,
                "ywc_shu_first_audit": 1, "test_ready": 1, "test_has_pilot": 1,
                "ywc_shu_appeal_owner": 2}
        world = PulseWorld(self.effects, {"SHU": base})
        world.run("ywc_shu_record_second_audit")
        self.assertNotIn("ywc_shu_second_audit", base)
        base["ywc_shu_appeal_owner"] = 1
        world.run("ywc_shu_record_second_audit")
        self.assertEqual(base.get("ywc_shu_second_audit"), 1)

        local = {"net_fixed_income": 0, "ywc_shu_audit_mode": 2, "ywc_shu_local_audit_right": 1,
                 "ywc_shu_first_audit": 1, "ywc_shu_appeal_owner": 2, "ywc_shu_merchant_advance": 1,
                 "ywc_shu_merchant_consultation": 1, "test_ready": 1, "test_has_pilot": 1}
        local_world = PulseWorld(self.effects, {"SHU": local})
        local_world.run("ywc_shu_record_second_audit")
        self.assertNotIn("ywc_shu_second_audit", local)
        local["ywc_shu_merchant_advance_refused"] = 1
        local_world.run("ywc_shu_record_second_audit")
        self.assertNotIn("ywc_shu_second_audit", local, "a refusal cannot cancel an accepted advance")
        local.pop("ywc_shu_merchant_advance")
        local_world.run("ywc_shu_record_second_audit")
        self.assertEqual(local.get("ywc_shu_second_audit"), 1)
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
        self.assertIn("ywc_shu_v03_settlement_execution_ready = yes", self.arc["journals"][1]["script"])
        limited = self.triggers.split("ywc_shu_v03_limited_execution_ready = {", 1)[1].split("\nywc_shu_v03_settlement_execution_ready", 1)[0]
        self.assertIn("ywc_shu_v03_has_pilot_state = yes", limited)
        self.assertIn("ywc_shu_v03_finance_safe = yes", limited)
        self.assertIn("NOT = { is_at_war = yes }", limited)
        self.assertIn("occupancy >= 0.25", limited)
        self.assertNotIn("ywc_shu_v03_has_tax_register_law", limited)
        self.assertNotIn("bureaucracy >=", limited)
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

    def test_final_choices_have_precondition_triggers(self):
        final_options = self.arc["events"][9]["options"]
        for option in final_options:
            if option["key"] == "withdraw_as_breach":
                self.assertNotIn("trigger", option, "withdrawal is the always-available valid exit")
            else:
                self.assertIn("trigger", option, option["key"])
        for key in ("establish_central", "confirm_provincial_share"):
            option = next(row for row in final_options if row["key"] == key)
            self.assertIn("NOT = { is_at_war = yes }", option["trigger"])
        self.assertIn("has_variable = ywc_shu_review_interrupted",
                      next(row["trigger"] for row in final_options
                           if row["key"] == "retry_after_interruption"))
        self.assertTrue(any("trigger" in option for option in self.arc["events"][8]["options"]))
        central = next(row for row in self.arc["events"][7]["options"] if row["key"] == "central_public_duties")
        provincial = next(row for row in self.arc["events"][7]["options"] if row["key"] == "provincial_retention")
        self.assertIn("ywc_shu_audit_mode = 1", central["trigger"])
        self.assertIn("ywc_shu_audit_mode = 2", provincial["trigger"])

    def test_settlement_close_rechecks_review_and_war_at_effect_time(self):
        state = {"ywc_shu_second_audit": 1, "ywc_shu_settlement_mode": 1,
                 "ywc_shu_pilot_outcome": 1, "ywc_shu_audit_installment_paid_second": 1,
                 "test_ready": 1, "test_has_pilot": 1, "test_finance_safe": 1,
                 "is_at_war": True}
        lifecycle_stub = "\nywc_v03_release_arc_shu_v03_shu_fiscal_register = { set_variable = { name = ywc_v03_shu_v03_shu_fiscal_register_settled value = 1 } }\n"
        world = PulseWorld(self.effects + lifecycle_stub, {"SHU": state})
        world.run("ywc_shu_close_as_central")
        self.assertNotIn("ywc_shu_fiscal_outcome_central_audit", state)
        state["is_at_war"] = False
        world.run("ywc_shu_close_as_central")
        self.assertNotIn("ywc_shu_fiscal_outcome_central_audit", state,
                         "a mature 180-day review is required even if the option effect is invoked directly")
        state["ywc_shu_settlement_review_mature"] = 1
        world.run("ywc_shu_close_as_central")
        self.assertEqual(state.get("ywc_shu_fiscal_outcome_central_audit"), 1)

    def test_merchant_repayment_runs_from_country_monthly_on_action_after_exit(self):
        effect = shu_monthly_effect()
        from shu_kor_strict_review_runtime import Strict, facts
        world = Strict("shu")
        world.countries["SHU"] = facts()
        world.countries["SHU"].update({"yearly_gross_income": 52_000, "gold_reserves": 2_000,
                                      "ywc_v03_shu_v03_shu_fiscal_register_last_event": 6,
                                      "ywc_shu_v03_pilot_state": 1})
        world.active["SHU"].append("ywc_je_v03_shu_register_pilot")
        world.run("ywc_shu_accept_merchant_advance")
        world.active["SHU"].clear()
        world.countries["SHU"]["ywc_shu_register_resolved"] = 1
        principal = world.countries["SHU"]["ywc_shu_merchant_principal"]
        self.assertAlmostEqual(world.treasury["SHU"], principal)
        for _ in range(11):
            world.advance_months(1)
            world.execute(effect, "SHU")
        self.assertNotIn("ywc_shu_merchant_advance_repaid", world.countries["SHU"])
        world.advance_months(1)
        world.execute(effect, "SHU")
        self.assertAlmostEqual(world.treasury["SHU"], 0)
        self.assertEqual(world.countries["SHU"].get("ywc_shu_merchant_advance_repaid"), 1)
        world.execute(effect, "SHU")
        self.assertAlmostEqual(world.treasury["SHU"], 0)

    def test_unpaid_merchant_advance_survives_exit_until_funds_allow_collection(self):
        effect = shu_monthly_effect()
        world = PulseWorld(self.effects, {"SHU": {"gold_reserves": 0, "ywc_shu_arc_abandoned": 1,
                              "ywc_shu_merchant_advance_unpaid": 1, "ywc_shu_merchant_principal": 250,
                              "ywc_shu_merchant_repayment_months": 11}})
        world.execute(effect, "SHU")
        self.assertNotIn("ywc_shu_merchant_advance_repaid", world.countries["SHU"])
        self.assertTrue(any(fields.get("modifier") == "ywc_shu_local_credit_arrears" for _, fields in world.modifiers))
        world.countries["SHU"]["gold_reserves"] = 250
        world.execute(effect, "SHU")
        self.assertEqual(world.countries["SHU"].get("ywc_shu_merchant_advance_repaid"), 1)
        self.assertFalse(any(fields.get("modifier") == "ywc_shu_local_credit_arrears" for _, fields in world.modifiers))

    def test_appeal_choice_applies_attributed_mutex_political_modifier(self):
        event = self.arc["events"][4]
        central = next(row for row in event["options"] if row["key"] == "central_appeal")
        local = next(row for row in event["options"] if row["key"] == "local_mediation")
        world = PulseWorld(self.effects, {"SHU": {}})
        world.execute(parse(central["effect"][1:-1]), "SHU")
        self.assertTrue(any(fields.get("modifier") == "ywc_shu_central_appeal_cost" for _, fields in world.modifiers))
        world.execute(parse(local["effect"][1:-1]), "SHU")
        active = {fields.get("modifier") for _, fields in world.modifiers}
        self.assertIn("ywc_shu_local_appeal_cost", active)
        self.assertNotIn("ywc_shu_central_appeal_cost", active)
        self.assertEqual(world.countries["SHU"]["ywc_shu_appeal_owner"], 2)
        self.assertIn("months = 24", local["effect"])
        modifiers = (ROOT / "yongchang_world/common/static_modifiers/ywc_v03_shu_modifiers.txt").read_text(encoding="utf-8-sig")
        self.assertRegex(modifiers, r"interest_group_ig_landowners_approval_add\s*=\s*-2\b")
        self.assertRegex(modifiers, r"interest_group_ig_armed_forces_approval_add\s*=\s*-2\b")
        self.assertRegex(modifiers, r"interest_group_ig_landowners_approval_add\s*=\s*-1\b")

    def test_landowner_settlement_routes_have_real_time_limited_group_effects(self):
        effects = (ROOT / "yongchang_world/common/static_modifiers/ywc_v03_shu_modifiers.txt").read_text(encoding="utf-8-sig")
        self.assertRegex(effects, r"ywc_shu_landowner_quota_compromise\s*=\s*\{\s*interest_group_ig_landowners_approval_add\s*=\s*1\s*\}")
        self.assertRegex(effects, r"ywc_shu_landowner_compensated\s*=\s*\{\s*interest_group_ig_landowners_approval_add\s*=\s*2\s*\}")
        self.assertRegex(effects, r"ywc_shu_landowner_old_exemption\s*=\s*\{\s*interest_group_ig_landowners_approval_add\s*=\s*3\s*\}")
        paid = {"yearly_gross_income": 52_000, "gold_reserves": 2_000, "net_fixed_income": 0}
        world = PulseWorld(self.effects, {"SHU": paid})
        world.run("ywc_shu_choose_compensated_collection")
        self.assertEqual(paid.get("ywc_shu_compensation_paid"), 1)
        self.assertTrue(any(fields.get("modifier") == "ywc_shu_landowner_compensated" for _, fields in world.modifiers))
        self.assertAlmostEqual(world.treasury["SHU"], -2_000)
        unpaid = {"yearly_gross_income": 52_000, "gold_reserves": 0, "net_fixed_income": 0}
        unpaid_world = PulseWorld(self.effects, {"SHU": unpaid})
        unpaid_world.run("ywc_shu_choose_compensated_collection")
        self.assertNotIn("ywc_shu_compensation_paid", unpaid)
        self.assertFalse(any(fields.get("modifier") == "ywc_shu_landowner_compensated" for _, fields in unpaid_world.modifiers))
        compromise_world = PulseWorld(self.effects, {"SHU": {}})
        compromise_world.run("ywc_shu_choose_landlord_compromise")
        self.assertTrue(any(fields.get("modifier") == "ywc_shu_landowner_quota_compromise" for _, fields in compromise_world.modifiers))

    def test_pilot_state_selection_is_player_chosen_from_fixed_owned_candidates(self):
        event = self.arc["events"][0]
        expected = {"sichuan", "chongqing", "yunnan", "guizhou"}
        selected = {row["key"].removeprefix("pilot_state_") for row in event["options"]
                    if row["key"].startswith("pilot_state_")}
        self.assertEqual(selected, expected)
        self.assertTrue(all("state_region = s:STATE_" in row["trigger"] for row in event["options"]
                            if row["key"].startswith("pilot_state_")))
        e8 = self.arc["events"][8]
        self.assertTrue(all(any(row["key"] == "reselect_state_" + candidate for row in e8["options"])
                            for candidate in expected))
        self.assertNotIn("random_scope_state", self.effects)
        triggers = self.triggers
        self.assertIn("state_region = s:STATE_SICHUAN", triggers)
        self.assertIn("state_region = s:STATE_CHONGQING", triggers)
        self.assertIn("state_region = s:STATE_YUNNAN", triggers)
        self.assertIn("state_region = s:STATE_GUIZHOU", triggers)
        event_one = self.arc["events"][1]
        self.assertIn("has_variable = ywc_shu_v03_pilot_state", event_one["trigger"])
        self.assertTrue(all("NOT = { var:ywc_shu_pilot_state_lost = 1 }" in row["trigger"]
                            for row in event_one["options"]
                            if not row["key"].startswith("reselect_")
                            and row["key"] != "withdraw_after_state_loss"))
        self.assertIn("var:ywc_shu_pilot_state_lost = 1",
                      next(row["trigger"] for row in event_one["options"]
                           if row["key"] == "withdraw_after_state_loss"))
        world = PulseWorld(self.effects, {"SHU": {"ywc_v03_shu_v03_shu_fiscal_register_last_event": 2}})
        world.run("ywc_shu_resume_after_pilot_reselection")
        self.assertEqual(world.countries["SHU"]["ywc_shu_pending_event"], 1002)

    def test_first_audit_does_not_require_later_appeal_or_merchant_decisions(self):
        state = {"ywc_shu_audit_mode": 1, "ywc_shu_audit_installment_paid": 1,
                 "test_ready": 1}
        lifecycle_stub = "\nywc_v03_release_arc_shu_v03_shu_fiscal_register = { set_variable = { name = ywc_v03_shu_v03_shu_fiscal_register_settled value = 1 } }\n"
        world = PulseWorld(self.effects + lifecycle_stub, {"SHU": state})
        world.run("ywc_shu_mark_first_audit")
        self.assertEqual(state.get("ywc_shu_first_audit"), 1)
        self.assertEqual(world.days_until_expiry["SHU"].get("ywc_shu_second_audit_due"), 90)

    def test_journal_monthly_pulse_extracts_and_executes_the_effect_body(self):
        for journal in self.arc["journals"]:
            pulse_effect_nodes(journal)

        pulse = inject_fact_triggers(pulse_effect_nodes(self.arc["journals"][0]))
        world = PulseWorld(self.effects, {"SHU": {"ywc_shu_pending_event": 1000}})
        world.execute(pulse, "SHU")
        self.assertEqual(world.events, [], "queued events wait while the shared cooldown is occupied")
        self.assertEqual(world.countries["SHU"]["ywc_shu_pending_event"], 1000)
        world.countries["SHU"]["test_cooldown_clear"] = 1
        world.execute(pulse, "SHU")
        self.assertEqual(world.events, [("SHU", "ywc_shu.1000")])
        self.assertNotIn("ywc_shu_pending_event", world.countries["SHU"])

        settlement = inject_fact_triggers(pulse_effect_nodes(self.arc["journals"][1]))
        followup = PulseWorld(self.effects, {"SHU": {"ywc_shu_pending_event": 1009, "test_cooldown_clear": 1}})
        followup.execute(settlement, "SHU")
        self.assertEqual(followup.events, [("SHU", "ywc_shu.1009")])
        self.assertNotIn("ywc_shu_pending_event", followup.countries["SHU"])

    def test_conservative_legacy_route_uses_smaller_goal_for_full_180_day_review(self):
        _, settlement = self.arc["journals"]
        pulse = inject_fact_triggers(pulse_effect_nodes(settlement))
        e6, e7, e8, e9 = self.arc["events"][6:10]
        pause = next(row for row in e6["options"] if row["key"] == "pause_as_legacy")
        cap = next(row for row in e7["options"] if row["key"] == "cap_old_dues")
        peace = next(row for row in e8["options"] if row["key"] == "review_in_peace")
        legacy = next(row for row in e9["options"] if row["key"] == "keep_capped_quotas")
        state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                 "test_has_pilot": 1, "test_has_candidate": 1,
                 "test_finance_safe": 1, "test_limited_ready": 1,
                 "ywc_shu_first_audit": 1}
        lifecycle_stub = "\nywc_v03_release_arc_shu_v03_shu_fiscal_register = { set_variable = { name = ywc_v03_shu_v03_shu_fiscal_register_settled value = 1 } }\n"
        test_effects = self.effects.replace("ywc_shu_v03_limited_execution_ready = yes", "has_variable = test_limited_ready")
        world = PulseWorld(test_effects + lifecycle_stub, {"SHU": state})
        world.journals.append(("SHU", [("type", "=", JE_IDS[0])]))
        world.journals.append(("SHU", [("type", "=", JE_IDS[1])]))

        self.assertTrue(world.conditions(inject_fact_triggers(parse(e6["trigger"][1:-1])), "SHU"))
        world.execute(parse_country_effect(e6["immediate"]), "SHU")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(pause["trigger"][1:-1])), "SHU"))
        world.execute(parse(pause["effect"][1:-1]), "SHU")
        self.assertEqual(state.get("ywc_shu_pilot_outcome"), 3)
        self.assertEqual(state.get("ywc_shu_register_pilot_resolved"), 1)

        journal_nodes = parse(settlement["script"])
        possible = next(body for key, _, body in journal_nodes if key == "possible")
        self.assertTrue(world.conditions(inject_fact_triggers(possible), "SHU"))
        immediate = next(body for key, _, body in journal_nodes if key == "immediate")
        world.execute(immediate, "SHU")
        self.assertEqual(state.get("ywc_shu_pending_event"), 1007)
        world.execute(pulse, "SHU")
        self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1007"))
        self.assertTrue(world.conditions(inject_fact_triggers(parse(e7["trigger"][1:-1])), "SHU"))
        world.execute(parse_country_effect(e7["immediate"]), "SHU")

        self.assertTrue(world.conditions(inject_fact_triggers(parse(cap["trigger"][1:-1])), "SHU"))
        world.execute(parse(cap["effect"][1:-1]), "SHU")
        self.assertEqual(world.days_until_expiry["SHU"].get("ywc_shu_settlement_review_due"), 180)
        for _ in range(5):
            world.advance_days(30)
            world.execute(pulse, "SHU")
            self.assertNotIn("ywc_shu_settlement_review_mature", state)
            self.assertNotIn("ywc_shu_pending_event", state)
        world.advance_days(30)
        world.execute(pulse, "SHU")
        self.assertEqual(state.get("ywc_shu_settlement_review_mature"), 1)
        self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1008"))

        world.execute(parse_country_effect(e8["immediate"]), "SHU")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(e8["trigger"][1:-1])), "SHU"))
        self.assertTrue(world.conditions(inject_fact_triggers(parse(peace["trigger"][1:-1])), "SHU"))
        world.execute(parse(peace["effect"][1:-1]), "SHU")
        world.execute(pulse, "SHU")
        self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1009"))
        world.execute(parse_country_effect(e9["immediate"]), "SHU")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(e9["trigger"][1:-1])), "SHU"))
        self.assertTrue(world.conditions(inject_fact_triggers(parse(legacy["trigger"][1:-1])), "SHU"))
        world.execute(parse(legacy["effect"][1:-1]), "SHU")
        self.assertEqual(state.get("ywc_shu_fiscal_outcome_capped_legacy"), 1)

    def test_legacy_delivery_before_readiness_has_defer_and_withdraw_paths(self):
        journal_one, settlement = self.arc["journals"]
        pulse = inject_fact_triggers(pulse_effect_nodes(settlement))
        e6, e7 = self.arc["events"][6:8]
        pause = next(row for row in e6["options"] if row["key"] == "pause_as_legacy")
        lifecycle_stub = "\nywc_v03_release_arc_shu_v03_shu_fiscal_register = { set_variable = { name = ywc_v03_shu_v03_shu_fiscal_register_settled value = 1 } }\n"
        test_effects = self.effects.replace("ywc_shu_v03_limited_execution_ready = yes", "has_variable = test_limited_ready")

        # Exercise both real readiness loss and pilot loss after the valid legacy choice.
        for pilot_lost in (False, True):
            with self.subTest(pilot_lost=pilot_lost):
                state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                         "test_has_pilot": 1, "test_has_candidate": 1,
                         "test_finance_safe": 1, "test_limited_ready": 1,
                         "ywc_shu_first_audit": 1}
                world = PulseWorld(test_effects + lifecycle_stub, {"SHU": state})
                world.journals.append(("SHU", [("type", "=", JE_IDS[0])]))
                world.journals.append(("SHU", [("type", "=", JE_IDS[1])]))
                world.execute(parse_country_effect(e6["immediate"]), "SHU")
                world.execute(parse(pause["effect"][1:-1]), "SHU")
                journal_nodes = parse(settlement["script"])
                immediate = next(body for key, _, body in journal_nodes if key == "immediate")
                world.execute(immediate, "SHU")
                world.execute(pulse, "SHU")
                self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1007"))
                world.execute(parse_country_effect(e7["immediate"]), "SHU")

                state.pop("test_limited_ready")
                if pilot_lost:
                    state.pop("test_has_pilot")
                self.assertTrue(world.conditions(inject_fact_triggers(parse(e7["trigger"][1:-1])), "SHU"))
                available = [row["key"] for row in e7["options"]
                             if "trigger" not in row or world.conditions(
                                 inject_fact_triggers(parse(row["trigger"][1:-1])), "SHU")]
                self.assertEqual(available, ["defer_until_ready", "withdraw_before_execution"])

                defer = next(row for row in e7["options"] if row["key"] == "defer_until_ready")
                world.execute(parse(defer["effect"][1:-1]), "SHU")
                self.assertEqual(state.get("ywc_shu_pending_event"), 1007)
                self.assertNotIn("ywc_shu_settlement_review", state)
                self.assertNotIn("ywc_shu_settlement_mode", state)

                state.pop("test_cooldown_clear")
                world.execute(pulse, "SHU")
                self.assertEqual(len(world.events), 1)  # shared major-event cooldown holds the retry
                self.assertEqual(state.get("ywc_shu_pending_event"), 1007)
                state["test_cooldown_clear"] = 1
                world.execute(pulse, "SHU")
                self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1007"))
                self.assertNotIn("ywc_shu_settlement_review", state)

                withdraw = next(row for row in e7["options"] if row["key"] == "withdraw_before_execution")
                world.execute(parse(withdraw["effect"][1:-1]), "SHU")
                self.assertEqual(state.get("ywc_shu_arc_abandoned"), 1)
                self.assertEqual(state.get("ywc_shu_fiscal_outcome_withdrawn_breach"), 1)
                self.assertEqual(state.get("ywc_v03_shu_v03_shu_fiscal_register_settled"), 1)

    def test_lost_pilot_suspends_queued_event_and_resumes_after_reselection(self):
        journal = self.arc["journals"][0]
        pulse = inject_fact_triggers(pulse_effect_nodes(journal))
        e1 = self.arc["events"][1]
        reselect = next(row for row in e1["options"] if row["key"] == "reselect_state_chongqing")
        state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                 "test_has_candidate": 1, "test_owned_state": 1, "ywc_shu_v03_pilot_state": 1,
                 "ywc_shu_pending_event": 1006,
                 "ywc_v03_shu_v03_shu_fiscal_register_last_event": 6}
        world = PulseWorld(self.effects, {"SHU": state})
        world.journals.append(("SHU", [("type", "=", JE_IDS[0])]))
        world.execute(pulse, "SHU")
        self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1001"))
        self.assertEqual(state.get("ywc_shu_resume_event"), 1006)
        self.assertNotIn("ywc_shu_pending_event", state)

        world.execute(parse_country_effect(e1["immediate"]), "SHU")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(e1["trigger"][1:-1])), "SHU"))
        self.assertTrue(world.conditions(inject_fact_triggers(parse(reselect["trigger"][1:-1])), "SHU"))
        world.execute(parse(reselect["effect"][1:-1]), "SHU")
        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
        self.assertNotIn("ywc_shu_first_audit", state)

        empty_state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                       "test_has_candidate": 1, "test_owned_state": 1, "ywc_shu_v03_pilot_state": 1,
                       "ywc_v03_shu_v03_shu_fiscal_register_last_event": 6}
        empty = PulseWorld(self.effects, {"SHU": empty_state})
        empty.journals.append(("SHU", [("type", "=", JE_IDS[0])]))
        empty.execute(pulse, "SHU")
        empty.execute(parse_country_effect(e1["immediate"]), "SHU")
        empty.execute(parse(reselect["effect"][1:-1]), "SHU")
        self.assertEqual(empty_state.get("ywc_shu_pending_event"), 1005)

        no_candidate = {"test_unsettled": 1, "test_cooldown_clear": 1,
                        "ywc_shu_v03_pilot_state": 1}
        no_state_world = PulseWorld(self.effects, {"SHU": no_candidate})
        no_state_world.journals.append(("SHU", [("type", "=", JE_IDS[0])]))
        no_state_world.execute(pulse, "SHU")
        self.assertEqual(no_state_world.events[-1], ("SHU", "ywc_shu.1001"))
        self.assertTrue(no_state_world.conditions(inject_fact_triggers(parse(e1["trigger"][1:-1])), "SHU"))
        exit_option = next(row for row in e1["options"] if row["key"] == "withdraw_after_state_loss")
        self.assertTrue(no_state_world.conditions(inject_fact_triggers(parse(exit_option["trigger"][1:-1])), "SHU"))

    def test_E1000_total_candidate_loss_dispatches_and_can_withdraw(self):
        journal = self.arc["journals"][0]
        pulse = inject_fact_triggers(pulse_effect_nodes(journal))
        e0 = self.arc["events"][0]
        state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                 "ywc_shu_pending_event": 1000}
        lifecycle_stub = "\nywc_v03_release_arc_shu_v03_shu_fiscal_register = { set_variable = { name = ywc_v03_shu_v03_shu_fiscal_register_settled value = 1 } }\n"
        world = PulseWorld(self.effects + lifecycle_stub, {"SHU": state})
        world.journals.append(("SHU", [("type", "=", JE_IDS[0])]))

        # This case starts after the JE claimed its slot but before E1000 arrived;
        # every candidate is now gone, so the monthly dispatcher must still deliver E1000.
        world.execute(pulse, "SHU")
        self.assertEqual(world.events, [("SHU", "ywc_shu.1000")])
        self.assertNotIn("ywc_shu_pending_event", state)
        self.assertTrue(world.conditions(inject_fact_triggers(parse(e0["trigger"][1:-1])), "SHU"))

        selections = [row for row in e0["options"] if row["key"].startswith("pilot_state_")]
        self.assertEqual(len(selections), 4)
        for row in selections:
            self.assertFalse(world.conditions(inject_fact_triggers(parse(row["trigger"][1:-1])), "SHU"))
        withdraw = next(row for row in e0["options"] if row["key"] == "withdraw_before_pilot")
        self.assertNotIn("trigger", withdraw)  # unconditional exit remains available with zero candidates
        world.execute(parse(withdraw["effect"][1:-1]), "SHU")
        self.assertEqual(state.get("ywc_shu_arc_abandoned"), 1)
        self.assertEqual(state.get("ywc_shu_fiscal_outcome_withdrawn_breach"), 1)
        self.assertEqual(state.get("ywc_v03_shu_v03_shu_fiscal_register_settled"), 1)

        # The inactive first start still requires a real candidate, so this escape
        # only applies to an already-active arc whose final candidate disappeared.
        possible = self.arc["journals"][0]["script"].split("possible = {", 1)[1].split("}", 1)[0]
        self.assertIn("ywc_shu_v03_has_candidate_state = yes", possible)

    def test_limited_review_failure_restarts_a_fresh_180_days(self):
        settlement = self.arc["journals"][1]
        pulse = inject_fact_triggers(pulse_effect_nodes(settlement))
        e8 = self.arc["events"][8]
        state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                 "test_has_pilot": 1, "test_finance_safe": 1,
                 "test_limited_ready": 1, "ywc_shu_settlement_mode": 3,
                 "ywc_shu_legacy_cap": 1, "ywc_shu_pilot_outcome": 3}
        world = PulseWorld(self.effects, {"SHU": state})
        world.journals.append(("SHU", [("type", "=", JE_IDS[1])]))
        world.run("ywc_shu_start_settlement_review")
        world.advance_days(60)
        state.pop("test_limited_ready")
        world.execute(pulse, "SHU")
        self.assertEqual(state.get("ywc_shu_review_interrupted"), 1)
        self.assertNotIn("ywc_shu_settlement_review_due", state)
        self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1008"))

        self.assertTrue(world.conditions(inject_fact_triggers(parse(e8["trigger"][1:-1])), "SHU"))
        world.execute(parse_country_effect(e8["immediate"]), "SHU")
        defer = next(row for row in e8["options"] if row["key"] == "limit_for_war")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(defer["trigger"][1:-1])), "SHU"))
        world.execute(parse(defer["effect"][1:-1]), "SHU")
        state["test_limited_ready"] = 1
        world.execute(pulse, "SHU")
        self.assertEqual(world.days_until_expiry["SHU"].get("ywc_shu_settlement_review_due"), 180)
        world.advance_days(179)
        world.execute(pulse, "SHU")
        self.assertNotIn("ywc_shu_settlement_review_mature", state)
        world.advance_days(1)
        world.execute(pulse, "SHU")
        self.assertEqual(state.get("ywc_shu_settlement_review_mature"), 1)

    def test_final_success_option_disables_in_war_and_stale_choice_returns_to_retry(self):
        settlement = self.arc["journals"][1]
        pulse = inject_fact_triggers(pulse_effect_nodes(settlement))
        final = self.arc["events"][9]
        central = next(row for row in final["options"] if row["key"] == "establish_central")
        state = {"test_unsettled": 1, "test_cooldown_clear": 1,
                 "test_has_pilot": 1, "test_ready": 1, "test_finance_safe": 1,
                 "ywc_shu_second_audit": 1, "ywc_shu_settlement_mode": 1,
                 "ywc_shu_pilot_outcome": 1, "ywc_shu_settlement_review": 1,
                 "ywc_shu_settlement_review_mature": 1,
                 "ywc_shu_audit_installment_paid_second": 1,
                 "ywc_shu_review_class": 1, "is_at_war": False}
        world = PulseWorld(self.effects, {"SHU": state})
        world.journals.append(("SHU", [("type", "=", JE_IDS[1])]))
        self.assertTrue(world.conditions(inject_fact_triggers(parse(central["trigger"][1:-1])), "SHU"))
        world.execute(parse_country_effect(final["immediate"]), "SHU")
        state["is_at_war"] = True
        self.assertFalse(world.conditions(inject_fact_triggers(parse(central["trigger"][1:-1])), "SHU"))
        world.execute(parse(central["effect"][1:-1]), "SHU")
        self.assertNotIn("ywc_shu_fiscal_outcome_central_audit", state)

        state.pop("test_cooldown_clear")
        world.execute(pulse, "SHU")
        self.assertEqual(state.get("ywc_shu_pending_event"), 1008)
        self.assertEqual(world.events, [], "the existing final-event cooldown must retain the interruption notice")
        retry = next(row for row in final["options"] if row["key"] == "retry_after_interruption")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(retry["trigger"][1:-1])), "SHU"))
        world.execute(parse(retry["effect"][1:-1]), "SHU")
        state["test_cooldown_clear"] = 1
        world.execute(pulse, "SHU")
        self.assertEqual(world.events[-1], ("SHU", "ywc_shu.1008"))
        interrupted = self.arc["events"][8]
        self.assertTrue(world.conditions(inject_fact_triggers(parse(interrupted["trigger"][1:-1])), "SHU"))
        world.execute(parse_country_effect(interrupted["immediate"]), "SHU")
        defer = next(row for row in interrupted["options"] if row["key"] == "limit_for_war")
        self.assertTrue(world.conditions(inject_fact_triggers(parse(defer["trigger"][1:-1])), "SHU"))
        world.execute(parse(defer["effect"][1:-1]), "SHU")
        state["is_at_war"] = False
        world.execute(pulse, "SHU")
        self.assertEqual(state.get("ywc_shu_settlement_review"), 1)
        self.assertEqual(world.days_until_expiry["SHU"].get("ywc_shu_settlement_review_due"), 180)

    def test_twelve_and_thirty_six_month_blockage_fallbacks_still_dispatch(self):
        pulse = inject_fact_triggers(pulse_effect_nodes(self.arc["journals"][0]))
        cases = (
            ({"ywc_shu_waiting_for_capacity": 1, "ywc_shu_blocked_36_due": 1, "test_cooldown_clear": 1}, "ywc_shu.1001"),
            ({"ywc_shu_blocked_12_due": 1, "ywc_shu_blocked_12_notice": 1, "ywc_shu_waiting_for_capacity": 1, "test_cooldown_clear": 1}, "ywc_shu.1006"),
        )
        for state, expected in cases:
            state["test_unsettled"] = 1
            world = PulseWorld(self.effects, {"SHU": state})
            world.execute(pulse, "SHU")
            self.assertEqual(world.events, [("SHU", expected)])
            self.assertNotIn("ywc_shu_pending_event", state)
            if expected == "ywc_shu.1006":
                world.countries["SHU"]["test_cooldown_clear"] = 1
                world.journals.append(("SHU", [("type", "=", "ywc_je_v03_shu_register_pilot")]))
                trigger = inject_fact_triggers(parse(self.arc["events"][6]["trigger"][1:-1]))
                self.assertTrue(world.conditions(trigger, "SHU"), "the 36-month fallback must satisfy its event trigger")

    def test_interrupted_review_restarts_a_fresh_180_day_period_after_recovery(self):
        pulse = inject_fact_triggers(pulse_effect_nodes(self.arc["journals"][1]))
        state = {
            "ywc_shu_settlement_mode": 1,
            "ywc_shu_wartime_deferral": 1,
            "ywc_shu_review_interrupted": 1,
            "is_at_war": False,
            "in_default": False,
            "net_fixed_income": 20,
            "test_ready": 1,
            "test_has_pilot": 1,
            "test_finance_safe": 1,
        }
        world = PulseWorld(self.effects, {"SHU": state})
        world.execute(pulse, "SHU")
        self.assertEqual(state.get("ywc_shu_settlement_review"), 1)
        self.assertEqual(state.get("ywc_shu_settlement_review_due"), 1)
        self.assertEqual(world.days_until_expiry["SHU"].get("ywc_shu_settlement_review_due"), 180)
        self.assertNotIn("ywc_shu_pending_event", state)
        world.advance_days(179)
        self.assertIn("ywc_shu_settlement_review_due", state)
        world.advance_days(1)
        self.assertNotIn("ywc_shu_settlement_review_due", state)

    def test_wartime_interrupt_resets_six_month_review_before_queued_notice(self):
        pulse = inject_fact_triggers(pulse_effect_nodes(self.arc["journals"][1]))
        state = {
            "ywc_shu_settlement_mode": 1,
            "ywc_shu_settlement_review": 1,
            "ywc_shu_settlement_review_due": 1,
            "is_at_war": True,
            "net_fixed_income": 10,
            "test_finance_safe": 1,
        }
        world = PulseWorld(self.effects, {"SHU": state})
        world.execute(pulse, "SHU")
        self.assertNotIn("ywc_shu_settlement_review_due", state)
        self.assertNotIn("ywc_shu_settlement_review", state)
        self.assertEqual(state.get("ywc_shu_review_interrupted"), 1)
        self.assertEqual(state.get("ywc_shu_pending_event"), 1008)
        self.assertEqual(world.events, [], "notice waits for cooldown after its state reset has already happened")
        state["test_unsettled"] = 1
        state["test_cooldown_clear"] = 1
        world.journals.append(("SHU", [("type", "=", JE_IDS[1])]))
        world.execute(pulse, "SHU")
        self.assertEqual(world.events, [("SHU", "ywc_shu.1008")])
        trigger = inject_fact_triggers(parse(self.arc["events"][8]["trigger"][1:-1]))
        self.assertTrue(world.conditions(trigger, "SHU"), "the interrupted marker must keep the queued event eligible after the review reset")

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

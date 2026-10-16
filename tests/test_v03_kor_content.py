"""Offline behavior checks for KOR's military accounts content card."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
from clausewitz_harness import PulseWorld, parse
from tools.build_v03_content import validate_catalogs

CATALOG_PATH = ROOT / "data/content/v03/countries/kor.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_kor_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_kor_triggers.txt"
SHARED_EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt"
LEGACY_JOURNAL_PATH = ROOT / "yongchang_world/common/journal_entries/ywc_kor.txt"
EVENT_IDS = [f"ywc_kor.{number}" for number in range(1000, 1010)]
JE_IDS = ["ywc_je_v03_kor_military_audit", "ywc_je_v03_kor_service_settlement"]


class KorPulseWorld(PulseWorld):
    """Run KOR's shipped monthly pulse with only engine-owned readiness mocked."""

    def condition(self, node, tag):
        key, comparison, value = node
        if key == "ywc_v03_can_deliver_major":
            return True
        if key == "ywc_kor_v03_unsettled":
            return "ywc_v03_kor_v03_kor_military_accounts_settled" not in self.countries[tag]
        if key in ("ywc_kor_v03_route_execution_ready", "ywc_kor_v03_has_owned_state"):
            return True
        return super().condition(node, tag)


class KorEffectWorld(PulseWorld):
    """Evaluate KOR-owned scripted gates from explicit current-state fixtures."""

    def condition(self, node, tag):
        key, comparison, value = node
        variables = self.countries[tag]
        if key == "ywc_kor_v03_has_owned_state":
            return bool(variables.get("owns_state", 1))
        if key == "ywc_kor_v03_finance_safe":
            return (
                variables.get("bureaucracy", 0) >= 0
                and variables.get("net_fixed_income", 0) >= 0
                and not variables.get("in_default", False)
                and not any(
                    modifier_tag == tag and fields.get("modifier") == "declared_bankruptcy"
                    for modifier_tag, fields in self.modifiers
                )
            )
        if key == "ywc_kor_v03_route_execution_ready":
            return bool(variables.get("test_route_ready", 1)) and self.condition(
                ("ywc_kor_v03_has_owned_state", "=", "yes"), tag
            ) and self.condition(("ywc_kor_v03_finance_safe", "=", "yes"), tag)
        if key == "ywc_kor_v03_court_execution_ready":
            return bool(variables.get("test_court_ready", 1))
        if key == "ywc_kor_v03_provincial_execution_ready":
            return bool(variables.get("test_provincial_ready", 1))
        if key in ("ywc_kor_v03_limited_execution_ready", "ywc_kor_v03_reduced_execution_ready"):
            return bool(variables.get("test_limited_ready", 1))
        return super().condition(node, tag)


class KorMilitaryAccountsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.arc = cls.catalog["arcs"][0]
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.shared_effects = SHARED_EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")
        cls.legacy_journal = LEGACY_JOURNAL_PATH.read_text(encoding="utf-8-sig")

    def test_locked_identity_complete_bilingual_card_and_no_empty_journal_gates(self):
        self.assertEqual(self.catalog["key"], "country_kor")
        self.assertEqual(self.catalog["runtime_tags"], ["KOR"])
        self.assertEqual(self.arc["slug"], "v03_kor_military_accounts")
        self.assertEqual(self.arc["era"], "foundation")
        self.assertEqual([row["id"] for row in self.arc["events"]], EVENT_IDS)
        self.assertEqual([row["id"] for row in self.arc["journals"]], JE_IDS)
        for event in self.arc["events"]:
            for field in ("title", "desc", "purpose"):
                self.assertTrue(event[field]["zh"] and event[field]["en"])
            self.assertGreaterEqual(len(event["options"]), 2)
            for option in event["options"]:
                for field in ("label", "cost_note", "consequence_note"):
                    self.assertTrue(option[field]["zh"] and option[field]["en"])
        for journal in self.arc["journals"]:
            self.assertTrue(journal["title"]["zh"] and journal["title"]["en"])
            self.assertNotEqual(journal["goal"].strip(), "{ always = yes }")
            self.assertNotEqual(journal["exit_conditions"].strip(), "{ always = yes }")
            root_fields = [key for key, _, _ in parse(journal["script"])]
            self.assertNotIn("goal", root_fields)
            self.assertNotIn("exit_conditions", root_fields)

    def test_real_army_execution_requires_staffed_supplied_barracks_and_budget(self):
        self.assertIn("any_scope_building", self.triggers)
        self.assertIn("is_building_type = building_barrack", self.triggers)
        self.assertIn("occupancy >= 0.8", self.triggers)
        self.assertIn("building_has_goods_shortage = no", self.triggers)
        self.assertIn("has_modifier = military_wages_medium", self.triggers)
        self.assertIn("has_modifier = military_wages_high", self.triggers)
        self.assertIn("net_fixed_income >= 0", self.triggers)
        self.assertIn("has_law_or_variant = law_type:law_professional_army", self.triggers)
        self.assertIn("any_scope_state", self.triggers)
        self.assertIn("ROOT", self.triggers)
        official = Path(r"E:\SteamLibrary\steamapps\common\Victoria 3\game")
        canals = (official / "common/journal_entries/00_canals.txt").read_text(encoding="utf-8-sig")
        sick_man = (official / "common/journal_entries/00_sick_man.txt").read_text(encoding="utf-8-sig")
        army_laws = (official / "common/laws/00_army_model.txt").read_text(encoding="utf-8-sig")
        global_history = (official / "common/history/global/00_global.txt").read_text(encoding="utf-8-sig")
        self.assertIn("any_scope_building", canals)
        self.assertIn("building_has_goods_shortage = yes", sick_man)
        self.assertIn("law_professional_army", army_laws)
        self.assertIn("value = yearly_gross_income", global_history)
        self.assertIn("ywc_kor_v03_has_translation_employer", self.triggers)
        self.assertIn("is_building_type = building_university", self.triggers)
        monthly_supply = next(body for key, _, body in parse(self.effects) if key == "ywc_kor_pay_monthly_supply")
        self.assertFalse(any(key == "add_treasury" for key, _, _ in monthly_supply), "army supply checks must not invent a recurring debit")

    def test_three_route_helpers_commit_distinct_policies_once(self):
        for helper, marker, route in (
            ("ywc_kor_choose_court_supply", "ywc_kor_court_command_commitment", 1),
            ("ywc_kor_choose_provincial_supply", "ywc_kor_provincial_report_right", 2),
            ("ywc_kor_choose_limited_legacy", "ywc_kor_legacy_ceiling", 3),
        ):
            world = PulseWorld(self.effects, {"KOR": {"yearly_gross_income": 52_000, "net_fixed_income": 0, "gold_reserves": 20_000}})
            world.run(helper, tag="KOR")
            first_treasury = world.treasury["KOR"]
            world.run(helper, tag="KOR")
            self.assertEqual(world.countries["KOR"]["ywc_kor_supply_route"], route)
            self.assertIn(marker, world.countries["KOR"])
            self.assertEqual(world.treasury["KOR"], first_treasury)
            self.assertAlmostEqual(first_treasury, -1_000, places=5)

    def test_audit_decisions_reach_their_next_event_through_real_je_pulse_and_trigger(self):
        pulse_file = self.arc["journals"][0]["script"]
        journal = next(body for key, _, body in parse(pulse_file) if key == "on_monthly_pulse")
        pulse = next(body for key, _, body in journal if key == "effect")
        event_1003 = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1003")
        event_1004 = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1004")
        event_1005 = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1005")
        trigger = parse(event_1004["trigger"].strip()[1:-1])
        next_trigger = parse(event_1005["trigger"].strip()[1:-1])

        for option_key in ("publish", "private", "reduce_rotations"):
            world = KorPulseWorld(self.effects + "\n" + self.shared_effects, {"KOR": {
                "ywc_v03_initialized": 1,
                "ywc_v03_active_arc_count": 1,
                "ywc_v03_visible_task_count": 1,
                "ywc_v03_kor_v03_kor_military_accounts_started": 1,
                "ywc_kor_supply_route": 1,
                "ywc_kor_intro_complete": 1,
                "ywc_kor_pending_event": 1003,
                "ywc_kor_weekly_cost": 100,
                "net_fixed_income": 0,
                "gold_reserves": 1000,
            }})
            world.execute(pulse, "KOR")
            self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1003"))
            option = next(row for row in event_1003["options"] if row["key"] == option_key)
            world.execute(parse(option["effect"].strip()[1:-1]), "KOR")
            world.execute(pulse, "KOR")
            self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1004"))
            self.assertTrue(
                world.conditions(trigger, "KOR"),
                f"{option_key} must leave E1004 eligible after the JE consumes pending_event",
            )
            # A normal E1004 choice schedules the next staged event and the same
            # authored JE dispatcher must deliver it with its trigger still valid.
            narrow_order = next(row for row in event_1004["options"] if row["key"] == "narrow_orders")
            world.execute(parse(narrow_order["effect"].strip()[1:-1]), "KOR")
            world.execute(pulse, "KOR")
            self.assertEqual(world.events[-1], ("KOR", "ywc_kor.1005"))
            self.assertTrue(world.conditions(next_trigger, "KOR"))

    def test_initial_audit_failure_requeues_and_user_can_exit(self):
        effects = self.effects + "\n" + self.shared_effects
        event = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1000")
        poor = PulseWorld(effects, {"KOR": {"yearly_gross_income": 52_000, "net_fixed_income": -1, "gold_reserves": 0, "ywc_v03_initialized": 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1}})
        poor_effect = next(o for o in event["options"] if o["key"] == "court_supply")["effect"]
        poor.execute(parse(poor_effect.strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_kor_supply_route", poor.countries["KOR"])
        self.assertEqual(poor.countries["KOR"]["ywc_kor_pending_event"], 1000)

        exit_world = KorEffectWorld(effects, {"KOR": {"ywc_v03_initialized": 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1}})
        exit_effect = next(o for o in event["options"] if o["key"] == "defer_or_withdraw")["effect"]
        exit_world.execute(parse(exit_effect.strip()[1:-1]), "KOR")
        self.assertEqual(exit_world.countries["KOR"]["ywc_v03_kor_v03_kor_military_accounts_outcome"], 4)
        self.assertEqual(exit_world.countries["KOR"]["ywc_v03_active_arc_count"], 0)

    def test_actual_weekly_cost_floor_and_guarded_payments(self):
        cost = PulseWorld(self.effects, {"KOR": {"yearly_gross_income": 52_000, "net_fixed_income": 0, "gold_reserves": 9_000}})
        cost.run("ywc_kor_capture_cost_base", tag="KOR")
        self.assertAlmostEqual(cost.countries["KOR"]["ywc_kor_weekly_cost"], 1_000, places=5)
        cost.countries["KOR"]["yearly_gross_income"] = 104_000
        cost.run("ywc_kor_capture_cost_base", tag="KOR")
        self.assertAlmostEqual(cost.countries["KOR"]["ywc_kor_weekly_cost"], 1_000, places=5)
        for helper, expected in (("ywc_kor_pay_audit_once", -1_000), ("ywc_kor_pay_invoice_once", -1_000)):
            world = PulseWorld(self.effects, {"KOR": {"yearly_gross_income": 52_000, "net_fixed_income": 0, "gold_reserves": 9_000}})
            world.run(helper, tag="KOR")
            charged = world.treasury["KOR"]
            world.run(helper, tag="KOR")
            self.assertAlmostEqual(charged, expected, places=5)
            self.assertEqual(world.treasury["KOR"], charged)
        poor = PulseWorld(self.effects, {"KOR": {"yearly_gross_income": 0, "net_fixed_income": -1, "gold_reserves": 0}})
        poor.run("ywc_kor_pay_audit_once", tag="KOR")
        self.assertEqual(poor.treasury["KOR"], 0)
        self.assertNotIn("ywc_kor_audit_paid", poor.countries["KOR"])

        exact_reserve = PulseWorld(self.effects, {"KOR": {
            "yearly_gross_income": 52_000,
            "net_fixed_income": 0,
            "gold_reserves": 1_000,
        }})
        exact_reserve.run("ywc_kor_pay_audit_once", tag="KOR")
        self.assertEqual(exact_reserve.countries["KOR"].get("ywc_kor_audit_paid"), 1)
        self.assertEqual(exact_reserve.treasury["KOR"], -1_000)

    def test_selected_contracts_cap_at_twelve_installments_across_pauses(self):
        state = {
            "yearly_gross_income": 52_000,
            "net_fixed_income": 0,
            "gold_reserves": 20_000,
            "ywc_kor_weekly_cost": 1_000,
            "ywc_kor_translation_contract_started": 1,
            "ywc_kor_translation_contract_paid_months": 0,
            "ywc_kor_veteran_contract_started": 1,
            "ywc_kor_veteran_contract_paid_months": 0,
        }
        world = PulseWorld(self.effects, {"KOR": state})

        def monthly_pulse():
            world.run("ywc_kor_pay_selected_contracts", tag="KOR")
            world.run("ywc_kor_pay_selected_contracts", tag="KOR")
            world.advance_months(1)

        for _ in range(6):
            monthly_pulse()
        treasury_before_pause = world.treasury["KOR"]
        world.countries["KOR"]["net_fixed_income"] = -1
        for _ in range(2):
            monthly_pulse()
        self.assertEqual(world.countries["KOR"]["ywc_kor_translation_contract_paid_months"], 6)
        self.assertEqual(world.countries["KOR"]["ywc_kor_veteran_contract_paid_months"], 6)
        self.assertAlmostEqual(world.treasury["KOR"], treasury_before_pause, places=5)
        recovery_event = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1008")
        recovery_effect = next(row for row in recovery_event["options"] if row["key"] == "restore_review")["effect"]
        world.execute(parse(recovery_effect.strip()[1:-1]), "KOR")
        self.assertEqual(world.countries["KOR"]["ywc_kor_translation_contract_paid_months"], 6)
        self.assertEqual(world.countries["KOR"]["ywc_kor_veteran_contract_paid_months"], 6)

        world.countries["KOR"]["net_fixed_income"] = 0
        for _ in range(18):
            monthly_pulse()
        final = world.countries["KOR"]
        self.assertEqual(final["ywc_kor_translation_contract_paid_months"], 12)
        self.assertEqual(final["ywc_kor_veteran_contract_paid_months"], 12)
        self.assertAlmostEqual(world.treasury["KOR"], -2_000, places=4)
        for _ in range(24):
            monthly_pulse()
        self.assertAlmostEqual(world.treasury["KOR"], -2_000, places=4)
        self.assertEqual(final["ywc_kor_translation_contract_paid_months"], 12)
        self.assertEqual(final["ywc_kor_veteran_contract_paid_months"], 12)

    def test_country_slot_claim_and_release_are_idempotent(self):
        world = PulseWorld(self.effects + "\n" + self.shared_effects, {"KOR": {}})
        world.run("ywc_kor_claim_military_accounts", tag="KOR")
        world.run("ywc_kor_claim_military_accounts", tag="KOR")
        self.assertEqual(world.countries["KOR"]["ywc_v03_active_arc_count"], 1)
        self.assertEqual(world.countries["KOR"]["ywc_v03_visible_task_count"], 1)
        world.countries["KOR"]["ywc_v03_kor_v03_kor_military_accounts_outcome"] = 1
        world.run("ywc_kor_release_military_accounts", tag="KOR")
        world.run("ywc_kor_release_military_accounts", tag="KOR")
        self.assertEqual(world.countries["KOR"]["ywc_v03_active_arc_count"], 0)
        self.assertEqual(world.countries["KOR"]["ywc_v03_visible_task_count"], 0)

    def test_close_helpers_read_saved_route_and_commit_one_distinct_result(self):
        outcomes = (
            (1, "ywc_kor_close_as_court_supply", "ywc_kor_outcome_court_supply"),
            (2, "ywc_kor_close_as_provincial_supply", "ywc_kor_outcome_provincial_supply"),
            (3, "ywc_kor_close_as_limited_legacy", "ywc_kor_outcome_limited_legacy"),
        )
        for route, helper, result in outcomes:
            policy = {1: {}, 2: {"ywc_kor_provincial_report_right": 1}, 3: {"ywc_kor_legacy_ceiling": 1}}[route]
            world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": {"ywc_v03_initialized": 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1, "ywc_kor_supply_route": route, "ywc_kor_review_complete": 1, "ywc_kor_service_review_complete": 1, "ywc_kor_six_months_complete": 1, "ywc_kor_nine_months_complete": 1, "ywc_kor_weekly_cost": 100, "gold_reserves": 100, "net_fixed_income": 0, "bureaucracy": 100, "test_route_ready": 1, **policy}})
            world.run(helper, tag="KOR")
            world.run(helper, tag="KOR")
            self.assertEqual(world.countries["KOR"][result], 1)
            self.assertEqual(sum(v for k, v in world.countries["KOR"].items() if k.startswith("ywc_kor_outcome_")), 1)

    def test_final_outcomes_recheck_current_readiness_and_finance(self):
        base = {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
            "ywc_kor_supply_route": 1,
            "ywc_kor_review_complete": 1,
            "ywc_kor_service_review_complete": 1,
            "ywc_kor_six_months_complete": 1,
            "ywc_kor_nine_months_complete": 1,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "test_route_ready": 1,
        }
        world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": dict(base)})
        world.run("ywc_kor_close_as_court_supply", tag="KOR")
        self.assertEqual(world.countries["KOR"].get("ywc_kor_outcome_court_supply"), 1)

        for invalidation in (
            {"test_route_ready": 0},
            {"bureaucracy": -1},
            {"net_fixed_income": -1},
            {"in_default": True},
            {"owns_state": 0},
        ):
            state = {**base, **invalidation}
            world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": state})
            world.run("ywc_kor_close_as_court_supply", tag="KOR")
            self.assertNotIn("ywc_kor_outcome_court_supply", state, invalidation)

        bankrupt_state = dict(base)
        bankrupt = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": bankrupt_state})
        bankrupt.modifiers.append(("KOR", {"modifier": "declared_bankruptcy"}))
        bankrupt.run("ywc_kor_close_as_court_supply", tag="KOR")
        self.assertNotIn("ywc_kor_outcome_court_supply", bankrupt_state)

        state = {**base, "owns_state": 0}
        world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": state})
        world.run("ywc_kor_close_as_breach", tag="KOR")
        self.assertEqual(state.get("ywc_kor_outcome_withdrawn_breach"), 1)

    def test_narrowed_target_has_a_real_limited_fallback_after_continuous_review(self):
        triggers = {key: body for key, _, body in parse(self.triggers)}
        route_ready = triggers["ywc_kor_v03_route_execution_ready"]
        facts = {
            "ywc_kor_v03_has_owned_state": "test_owned_state",
            "ywc_kor_v03_finance_safe": "test_finance_safe",
            "ywc_kor_v03_court_execution_ready": "test_court_ready",
            "ywc_kor_v03_provincial_execution_ready": "test_provincial_ready",
            "ywc_kor_v03_limited_execution_ready": "test_limited_ready",
            "ywc_kor_v03_reduced_execution_ready": "test_reduced_ready",
        }

        def inject(nodes):
            converted = []
            for key, comparison, value in nodes:
                if key in facts:
                    converted.append(("has_variable", "=", facts[key]))
                elif isinstance(value, list):
                    converted.append((key, comparison, inject(value)))
                else:
                    converted.append((key, comparison, value))
            return converted

        narrowed = PulseWorld("", {"KOR": {
            "ywc_kor_supply_route": 1,
            "ywc_kor_scope_narrowed": 1,
            "test_owned_state": 1,
            "test_finance_safe": 1,
            "test_reduced_ready": 1,
        }})
        self.assertTrue(narrowed.conditions(inject(route_ready), "KOR"))
        narrowed.countries["KOR"].pop("ywc_kor_scope_narrowed")
        self.assertFalse(narrowed.conditions(inject(route_ready), "KOR"))
        narrowed.countries["KOR"]["ywc_kor_scope_narrowed"] = 1
        narrowed.countries["KOR"].pop("test_reduced_ready")
        self.assertFalse(narrowed.conditions(inject(route_ready), "KOR"))
        reduced_trigger = triggers["ywc_kor_v03_reduced_execution_ready"]
        self.assertIn("ywc_kor_v03_has_staffed_border_office", str(reduced_trigger))

        state = {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
            "ywc_kor_supply_route": 1,
            "ywc_kor_scope_narrowed": 1,
            "ywc_kor_review_complete": 1,
            "ywc_kor_service_review_complete": 1,
            "ywc_kor_six_months_complete": 1,
            "ywc_kor_nine_months_complete": 1,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "test_route_ready": 1,
            "test_court_ready": 0,
            "test_limited_ready": 1,
        }
        world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": state})
        world.run("ywc_kor_close_as_court_supply", tag="KOR")
        self.assertNotIn("ywc_kor_outcome_court_supply", state)
        world.run("ywc_kor_close_as_limited_legacy", tag="KOR")
        self.assertEqual(state.get("ywc_kor_outcome_limited_legacy"), 1)

    def test_narrowed_nine_month_review_cannot_upgrade_to_full_court_result(self):
        journal = next(j for j in self.arc["journals"] if j["id"] == JE_IDS[1])
        pulse = next(body for key, _, body in parse(journal["script"]) if key == "on_monthly_pulse")
        pulse_effect = next(body for key, _, body in pulse if key == "effect")
        state = {
            "ywc_kor_review_complete": 1,
            "ywc_kor_supply_route": 1,
            "ywc_kor_scope_narrowed": 1,
            "ywc_kor_six_months_complete": 1,
            "ywc_kor_review_findings": 1,
            "ywc_kor_intro_complete": 1,
            "net_fixed_income": 0,
            "bureaucracy": 100,
            "gold_reserves": 1000,
            "test_route_ready": 1,
            "test_court_ready": 0,
            "test_limited_ready": 1,
        }
        pulser = KorPulseWorld(self.effects, {"KOR": dict(state)})
        for _ in range(10):
            pulser.execute(pulse_effect, "KOR")
            pulser.advance_months()
        self.assertEqual(pulser.countries["KOR"].get("ywc_kor_nine_months_complete"), 1)

        event8 = next(e for e in self.arc["events"] if e["id"] == "ywc_kor.1008")
        peace = next(o for o in event8["options"] if o["key"] == "peace_ledger")
        effect_world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": pulser.countries["KOR"]})
        effect_world.execute(parse(peace["effect"][1:-1]), "KOR")
        effect_world.countries["KOR"]["test_court_ready"] = 1

        event9 = next(e for e in self.arc["events"] if e["id"] == "ywc_kor.1009")
        full = next(o for o in event9["options"] if o["key"] == "establish_court")
        self.assertFalse(effect_world.conditions(parse(full["trigger"][1:-1]), "KOR"))
        effect_world.execute(parse(full["effect"][1:-1]), "KOR")
        effect_world.run("ywc_kor_close_as_court_supply", tag="KOR")
        self.assertNotIn("ywc_kor_outcome_court_supply", effect_world.countries["KOR"])
        narrowed = next(o for o in event9["options"] if o["key"] == "establish_narrowed_target")
        self.assertTrue(effect_world.conditions(parse(narrowed["trigger"][1:-1]), "KOR"))
        effect_world.execute(parse(narrowed["effect"][1:-1]), "KOR")
        self.assertEqual(effect_world.countries["KOR"].get("ywc_kor_outcome_limited_legacy"), 1)

    def test_signed_contracts_remain_bounded_debt_after_arc_release(self):
        action = parse((ROOT / "yongchang_world/common/on_actions/ywc_v03_kor_accounts.txt").read_text(encoding="utf-8-sig"))
        callback = next(body for key, _, body in action if key == "on_monthly_pulse_country")
        effect = next(body for key, _, body in callback if key == "effect")
        world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
            "ywc_v03_kor_v03_kor_military_accounts_outcome": 4,
            "ywc_kor_cost_captured": 1,
            "ywc_kor_weekly_cost": 1_000,
            "ywc_kor_translation_contract_started": 1,
            "ywc_kor_translation_contract_paid_months": 11,
            "ywc_kor_veteran_contract_started": 1,
            "ywc_kor_veteran_contract_paid_months": 11,
            "gold_reserves": 10_000,
            "net_fixed_income": 0,
        }})
        world.run("ywc_kor_release_military_accounts", tag="KOR")
        state = world.countries["KOR"]
        self.assertIn("ywc_kor_translation_contract_started", state)
        self.assertIn("ywc_kor_veteran_contract_started", state)
        self.assertEqual(state["ywc_kor_translation_contract_paid_months"], 11)
        self.assertEqual(state["ywc_kor_veteran_contract_paid_months"], 11)

        for _ in range(12):
            world.execute(effect, "KOR")
            world.advance_months(1)
        self.assertEqual(state["ywc_kor_translation_contract_paid_months"], 12)
        self.assertEqual(state["ywc_kor_veteran_contract_paid_months"], 12)
        self.assertAlmostEqual(world.treasury["KOR"], -166.6666666, places=3)
        paid_after_completion = world.treasury["KOR"]
        for _ in range(12):
            world.execute(effect, "KOR")
            world.advance_months(1)
        self.assertEqual(world.treasury["KOR"], paid_after_completion)
        self.assertIn("c:KOR ?= this", (ROOT / "yongchang_world/common/on_actions/ywc_v03_kor_accounts.txt").read_text(encoding="utf-8-sig"))

        no_funds = KorEffectWorld(self.effects, {"KOR": {
            "ywc_v03_kor_v03_kor_military_accounts_settled": 1,
            "ywc_kor_weekly_cost": 1_000,
            "ywc_kor_translation_contract_started": 1,
            "ywc_kor_translation_contract_paid_months": 3,
            "gold_reserves": 0,
            "net_fixed_income": 0,
        }})
        no_funds.execute(effect, "KOR")
        self.assertEqual(no_funds.countries["KOR"]["ywc_kor_translation_contract_paid_months"], 3)
        self.assertIn("ywc_kor_translation_contract_started", no_funds.countries["KOR"])

        successful_exit = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
            "ywc_v03_kor_v03_kor_military_accounts_outcome": 1,
            "ywc_kor_cost_captured": 1,
            "ywc_kor_weekly_cost": 1_000,
            "ywc_kor_translation_contract_started": 1,
            "ywc_kor_translation_contract_paid_months": 11,
            "gold_reserves": 10_000,
            "net_fixed_income": 0,
        }})
        successful_exit.run("ywc_kor_release_military_accounts", tag="KOR")
        self.assertIn("ywc_kor_translation_contract_started", successful_exit.countries["KOR"])
        successful_exit.execute(effect, "KOR")
        self.assertEqual(successful_exit.countries["KOR"]["ywc_kor_translation_contract_paid_months"], 12)
        self.assertAlmostEqual(successful_exit.treasury["KOR"], -83.3333333, places=3)

    def test_legacy_reform_pulse_waits_for_actual_new_arc_start(self):
        nodes = parse(self.legacy_journal)
        reform_1 = next(body for key, _, body in nodes if key == "ywc_je_flavor_kor_reform_1")
        pulse = next(body for key, _, body in reform_1 if key == "on_monthly_pulse")
        wrapped = next(body for key, _, body in pulse if key == "effect")
        chapter = next(body for key, _, body in wrapped if key == "if")
        limit = next(body for key, _, body in chapter if key == "limit")
        effects = self.effects + "\n" + self.shared_effects
        initialized_only = PulseWorld(effects, {"KOR": {"ywc_v03_initialized": 1}})
        started = PulseWorld(effects, {"KOR": {"ywc_v03_initialized": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1}})
        self.assertTrue(initialized_only.conditions(limit, "KOR"), "initialization alone must not pause old reform JE")
        self.assertFalse(started.conditions(limit, "KOR"), "the old monthly chapter pulse must pause after the KOR card actually starts")
        self.assertEqual(sum(key == "NOT" for key, _, _ in limit), 2)

    def test_journal_one_goal_has_valid_success_and_breach_or_paths(self):
        audit = self.arc["journals"][0]
        goal = parse(audit["goal"].strip()[1:-1])
        ready = PulseWorld("", {"KOR": {"ywc_kor_review_complete": 1}})
        breach = PulseWorld("", {"KOR": {"ywc_kor_outcome_withdrawn_breach": 1}})
        incomplete = PulseWorld("", {"KOR": {}})
        self.assertTrue(ready.conditions(goal, "KOR"))
        self.assertTrue(breach.conditions(goal, "KOR"))
        self.assertFalse(incomplete.conditions(goal, "KOR"))

    def test_event_1006_has_separate_six_month_and_blocked_prompt_paths(self):
        event = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1006")
        trigger = parse(event["trigger"].strip()[1:-1])
        prompt_gate = next(node for node in trigger if node[0] == "OR")
        intro_only = PulseWorld("", {"KOR": {"ywc_kor_intro_complete": 1}})
        six_months = PulseWorld("", {"KOR": {"ywc_kor_intro_complete": 1, "ywc_kor_six_months_complete": 1}})
        blocked_12 = PulseWorld("", {"KOR": {"ywc_kor_blocked_12_notice": 1}})
        blocked_36 = PulseWorld("", {"KOR": {"ywc_kor_blocked_36_notice": 1}})
        self.assertFalse(intro_only.condition(prompt_gate, "KOR"))
        self.assertTrue(six_months.condition(prompt_gate, "KOR"))
        self.assertTrue(blocked_12.condition(prompt_gate, "KOR"))
        self.assertTrue(blocked_36.condition(prompt_gate, "KOR"))

        exit_effect = next(row for row in event["options"] if row["key"] == "withdraw")["effect"]
        world = KorEffectWorld(self.effects + "\n" + self.shared_effects, {"KOR": {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
        }})
        world.execute(parse(exit_effect.strip()[1:-1]), "KOR")
        self.assertEqual(world.countries["KOR"]["ywc_v03_kor_v03_kor_military_accounts_outcome"], 4)
        self.assertEqual(world.countries["KOR"]["ywc_v03_active_arc_count"], 0)

    def test_release_bridges_outcomes_preserves_old_result_and_opens_reform_two_once(self):
        effects = self.effects + "\n" + self.shared_effects
        for outcome, legacy in ((1, 1), (2, 2), (3, 2), (4, 3)):
            state = {
                "ywc_v03_initialized": 1,
                "ywc_v03_active_arc_count": 1,
                "ywc_v03_visible_task_count": 1,
                "ywc_v03_kor_v03_kor_military_accounts_started": 1,
                "ywc_v03_kor_v03_kor_military_accounts_outcome": outcome,
            }
            world = PulseWorld(effects, {"KOR": state})
            world.run("ywc_kor_release_military_accounts", tag="KOR")
            world.run("ywc_kor_release_military_accounts", tag="KOR")
            self.assertEqual(world.countries["KOR"]["ywc_campaign_kor_c1_outcome"], legacy)
            self.assertEqual(len(world.journals), 1)
            self.assertEqual(dict((name, field) for name, _, field in world.journals[0][1])["type"], "ywc_je_flavor_kor_reform_2")

        preserved = {
            "ywc_v03_initialized": 1,
            "ywc_v03_active_arc_count": 1,
            "ywc_v03_visible_task_count": 1,
            "ywc_v03_kor_v03_kor_military_accounts_started": 1,
            "ywc_v03_kor_v03_kor_military_accounts_outcome": 4,
            "ywc_campaign_kor_c1_outcome": 77,
        }
        world = PulseWorld(effects, {"KOR": preserved})
        world.run("ywc_kor_release_military_accounts", tag="KOR")
        world.run("ywc_kor_bridge_military_accounts", tag="KOR")
        self.assertEqual(world.countries["KOR"]["ywc_campaign_kor_c1_outcome"], 77)
        self.assertEqual(len(world.journals), 1)

    def test_six_and_nine_month_gates_and_blocked_exit_are_wired(self):
        audit, settlement = self.arc["journals"]
        self.assertIn("months = 6", audit["script"])
        self.assertIn("months = 9", settlement["script"])
        self.assertIn("days = 365", audit["script"])
        self.assertIn("days = 1095", audit["script"])
        self.assertIn("NOT = { has_variable = ywc_kor_blocked_12_due }", audit["script"])
        self.assertIn("NOT = { has_variable = ywc_kor_blocked_36_due }", audit["script"])
        self.assertIn("ywc_v03_can_deliver_major = yes", audit["script"])
        self.assertIn("ywc_v03_can_deliver_major = yes", settlement["script"])
        for event in self.arc["events"]:
            self.assertIn("ywc_v03_can_deliver_major = yes", event["trigger"])
            self.assertIn("ywc_v03_mark_major_delivered = yes", event["immediate"])
        self.assertEqual(validate_catalogs({"country_kor": self.catalog}), [])
        self.assertIn("effect =", audit["script"])
        self.assertIn("effect =", settlement["script"])
        self.assertIn("remove_variable = ywc_kor_observation_timer", audit["script"])
        self.assertIn("remove_variable = ywc_kor_service_timer", settlement["script"])
        self.assertIn("ywc_kor_service_event_prompted", settlement["script"])
        self.assertIn("ywc_kor_review_event_prompted", audit["script"])
        self.assertNotIn("ywc_kor_review_event_prompted", settlement["script"])
        settlement_event = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1009")
        self.assertIn("restart_renewal", [row["key"] for row in settlement_event["options"]])

    def test_failed_month_resets_continuous_observation_inside_each_pulse(self):
        audit, settlement = self.arc["journals"]
        for journal, timer, started, complete in (
            (audit, "ywc_kor_observation_timer", "ywc_kor_observation_started", "ywc_kor_six_months_complete"),
            (settlement, "ywc_kor_service_timer", "ywc_kor_service_observation_started", "ywc_kor_nine_months_complete"),
        ):
            script = parse(journal["script"])
            pulse = next(body for key, _, body in script if key == "on_monthly_pulse")
            wrapped = next(body for key, _, body in pulse if key == "effect")
            failure = next(body for key, _, body in wrapped if key == "if")
            limit = next(body for key, _, body in failure if key == "limit")
            self.assertTrue(any(key == "NOT" for key, _, _ in limit))
            removed = [body for key, _, body in failure if key == "remove_variable"]
            self.assertIn(timer, removed)
            self.assertIn(started, removed)
            self.assertIn(complete, removed)

    def test_kor_scripts_are_parseable_without_touching_generated_files(self):
        parse(self.effects)
        parse(self.triggers)
        parse(self.legacy_journal)
        for journal in self.arc["journals"]:
            parse(journal["script"])
        for event in self.arc["events"]:
            for field in ("trigger", "immediate"):
                parse(event[field])
            for opt in event["options"]:
                parse(opt["effect"])
                parse(opt["trigger"])


if __name__ == "__main__":
    unittest.main()

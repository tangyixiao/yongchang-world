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

    def test_initial_audit_failure_requeues_and_user_can_exit(self):
        effects = self.effects + "\n" + self.shared_effects
        event = next(row for row in self.arc["events"] if row["id"] == "ywc_kor.1000")
        poor = PulseWorld(effects, {"KOR": {"yearly_gross_income": 52_000, "net_fixed_income": -1, "gold_reserves": 0, "ywc_v03_initialized": 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1}})
        poor_effect = next(o for o in event["options"] if o["key"] == "court_supply")["effect"]
        poor.execute(parse(poor_effect.strip()[1:-1]), "KOR")
        self.assertNotIn("ywc_kor_supply_route", poor.countries["KOR"])
        self.assertEqual(poor.countries["KOR"]["ywc_kor_pending_event"], 1000)

        exit_world = PulseWorld(effects, {"KOR": {"ywc_v03_initialized": 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1}})
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
            world = PulseWorld(self.effects + "\n" + self.shared_effects, {"KOR": {"ywc_v03_initialized": 1, "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1, "ywc_v03_kor_v03_kor_military_accounts_started": 1, "ywc_kor_supply_route": route, "ywc_kor_review_complete": 1, "ywc_kor_service_review_complete": 1, "ywc_kor_six_months_complete": 1, "ywc_kor_nine_months_complete": 1, "ywc_kor_weekly_cost": 100, "gold_reserves": 100, "net_fixed_income": 0, **policy}})
            world.run(helper, tag="KOR")
            world.run(helper, tag="KOR")
            self.assertEqual(world.countries["KOR"][result], 1)
            self.assertEqual(sum(v for k, v in world.countries["KOR"].items() if k.startswith("ywc_kor_outcome_")), 1)

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

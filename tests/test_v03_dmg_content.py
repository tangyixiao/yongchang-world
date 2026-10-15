"""Offline acceptance checks for DMG's common-subjects content card."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT))
from clausewitz_harness import PulseWorld, parse

CATALOG_PATH = ROOT / "data/content/v03/countries/dmg.json"
EFFECTS_PATH = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_dmg_effects.txt"
TRIGGERS_PATH = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_dmg_triggers.txt"
EVENT_IDS = [f"ywc_dmg.{number}" for number in range(1000, 1010)]
JE_IDS = ["ywc_je_v03_dmg_public_qualification", "ywc_je_v03_dmg_compact_review"]

class DmgContentCardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
        cls.arc = cls.catalog["arcs"][0]
        cls.effects = EFFECTS_PATH.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS_PATH.read_text(encoding="utf-8-sig")

    def test_locked_identity_and_complete_bilingual_card(self):
        self.assertEqual(self.catalog["key"], "country_dmg")
        self.assertEqual(self.catalog["layer"], "country")
        self.assertEqual(self.catalog["runtime_tags"], ["DMG"])
        self.assertEqual(self.arc["slug"], "v03_dmg_common_subjects")
        self.assertEqual(self.arc["era"], "foundation")
        self.assertEqual([row["id"] for row in self.arc["events"]], EVENT_IDS)
        self.assertEqual([row["id"] for row in self.arc["journals"]], JE_IDS)
        for event in self.arc["events"]:
            for field in ("title", "desc"):
                self.assertTrue(event[field]["zh"] and event[field]["en"])
            self.assertGreaterEqual(len(event["options"]), 3)
            for option in event["options"]:
                for field in ("label", "cost_note", "consequence_note"):
                    self.assertTrue(option[field]["zh"] and option[field]["en"])
        for journal in self.arc["journals"]:
            for field in ("title", "desc"):
                self.assertTrue(journal[field]["zh"] and journal[field]["en"])
            self.assertNotRegex(journal["script"], r"(?m)^\s*(complete|fail)\s*=")
            self.assertNotEqual(journal["goal"].strip(), "{ always = yes }")
            self.assertNotEqual(journal["exit_conditions"].strip(), "{ always = yes }")


    def test_reads_and_writes_are_backed_by_script_or_helper_references(self):
        authored = [self.effects, self.triggers]
        for journal in self.arc["journals"]:
            authored.extend([journal["script"], journal["goal"], journal["exit_conditions"]])
        for event in self.arc["events"]:
            authored.append(" ".join([event.get("trigger", ""), event.get("immediate", ""),
                                      *(option.get("effect", "") for option in event["options"]) ]))
        scripts = "\n".join(authored)
        for event in self.arc["events"]:
            for field in ("reads", "writes"):
                for symbol in event[field]:
                    self.assertIn(symbol, scripts, f"{event['id']} {field}: {symbol}")

    def test_scripts_use_real_acceptance_and_job_eligibility_checks(self):
        self.assertIn("any_scope_pop", self.triggers)
        self.assertIn("pop_acceptance", self.triggers)
        self.assertIn("acceptance_status_2", self.triggers)
        self.assertIn("any_scope_building", self.triggers)
        self.assertIn("building_government_administration", self.triggers)
        self.assertIn("building_barracks", self.triggers)
        self.assertIn("occupancy >= 0.8", self.triggers)
        self.assertIn("building_has_goods_shortage = no", self.triggers)
        # A cohort's acceptance and the presence of occupied jobs remain separate predicates.
        self.assertNotIn("ywc_dmg_v03_common_qualification_ready = {\n\tany_scope_pop", self.triggers)
        official = Path(r"E:\SteamLibrary\steamapps\common\Victoria 3\game\common\laws\00_citizenship.txt")
        if official.exists():
            self.assertIn("law_subjecthood", official.read_text(encoding="utf-8-sig"))


    def test_monthly_pulse_is_wrapped_and_six_month_clock_tracks_continuous_readiness(self):
        for journal in self.arc["journals"]:
            self.assertRegex(journal["script"], r"on_monthly_pulse\s*=\s*\{\s*effect\s*=\s*\{")
        public = self.arc["journals"][0]["script"]
        self.assertIn("ywc_dmg_v03_selected_route_ready = yes", public)
        self.assertIn("set_variable = { name = ywc_dmg_first_stage_due value = 1 months = 6 }", public)
        self.assertIn("remove_variable = ywc_dmg_first_stage_due", public)
        self.assertIn("has_variable = ywc_dmg_first_stage_ready_once", public)
        e6 = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1006")
        self.assertIn("ywc_dmg_first_stage_matured", e6["trigger"])
        self.assertIn("ywc_dmg_first_stage_matured", e6["trigger"])
        self.assertIn("NOT = { has_variable = ywc_dmg_review_due }", next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1009")["trigger"])


    def test_extracted_pulse_effect_runs_six_continuous_months_and_restarts_after_break(self):
        journal = self.arc["journals"][0]
        script_nodes = parse(journal["script"])
        pulse = next(body for key, _, body in script_nodes if key == "on_monthly_pulse")
        pulse_effect = next(body for key, _, body in pulse if key == "effect")
        self.assertTrue(pulse_effect)

        world = PulseWorld(self.effects, {"DMG": {
            "ywc_dmg_v03_selected_route_ready": 1,
            "ywc_dmg_blocked_12_due": 1,
            "ywc_dmg_blocked_36_due": 1,
        }})
        world.months_until_expiry["DMG"].update({
            "ywc_dmg_blocked_12_due": 12, "ywc_dmg_blocked_36_due": 36
        })
        base_condition = world.condition
        def condition(node, tag):
            key = node[0]
            if key == "ywc_dmg_v03_selected_route_ready":
                return bool(world.countries[tag].get("ywc_dmg_v03_selected_route_ready"))
            if key == "ywc_v03_can_deliver_major":
                return False  # keep the shared 90-day delivery gate closed in this offline simulation
            return base_condition(node, tag)
        world.condition = condition

        def pulse_month():
            world.execute(pulse_effect, "DMG")
        pulse_month()
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_first_stage_due"], 6)
        for _ in range(3):
            world.advance_months(1)
            pulse_month()
        world.countries["DMG"]["ywc_dmg_v03_selected_route_ready"] = 0
        pulse_month()
        self.assertNotIn("ywc_dmg_first_stage_due", world.countries["DMG"])
        self.assertNotIn("ywc_dmg_first_stage_matured", world.countries["DMG"])
        world.countries["DMG"]["ywc_dmg_v03_selected_route_ready"] = 1
        pulse_month()
        self.assertEqual(world.months_until_expiry["DMG"]["ywc_dmg_first_stage_due"], 6)
        for _ in range(5):
            world.advance_months(1)
            pulse_month()
        self.assertNotIn("ywc_dmg_first_stage_matured", world.countries["DMG"])
        world.advance_months(1)
        pulse_month()
        self.assertEqual(world.countries["DMG"]["ywc_dmg_first_stage_matured"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_pending_event"], 1006)

    def test_cost_is_income_based_once_and_old_status_route_has_separate_cost(self):
        self.assertIn("value = yearly_gross_income", self.effects)
        self.assertIn("0.0192307692308", self.effects)
        self.assertIn("max = 100", self.effects)
        self.assertRegex(self.effects, r"add_treasury\s*=\s*\{\s*value\s*=\s*var:ywc_dmg_[a-z_]+cost")
        self.assertIn("ywc_dmg_compensation_paid", self.effects)
        self.assertIn("ywc_dmg_status_orders_cost_paid", self.effects)
        opening = next(e for e in self.arc["events"] if e["id"] == "ywc_dmg.1000")
        self.assertIn("年总收入÷52", json.dumps(opening, ensure_ascii=False))
        self.assertIn("最低100", json.dumps(opening, ensure_ascii=False))

    def test_early_laws_do_not_fake_jobs_and_routes_remain_distinct(self):
        for outcome in ("common_qualification", "territorial_compact", "status_orders", "withdrawn_breach"):
            self.assertIn(f"ywc_dmg_outcome_{outcome}", self.effects)
        self.assertIn("ywc_dmg_v03_government_appointment_ready", self.triggers)
        self.assertIn("ywc_dmg_v03_military_appointment_ready", self.triggers)
        self.assertIn("bureaucracy >= 0", self.triggers)
        self.assertIn("ywc_dmg_appointment_actual", self.effects)
        self.assertIn("ywc_dmg_pay_compensation_once", self.effects)
        self.assertIn("NOT = { has_variable = ywc_dmg_compensation_paid }", self.effects)

    def test_country_helpers_are_idempotent_and_counted_once(self):
        world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000}})
        world.run("ywc_dmg_open_common_subjects_once", tag="DMG")
        world.run("ywc_dmg_open_common_subjects_once", tag="DMG")
        self.assertEqual(world.countries["DMG"]["ywc_dmg_arc_open"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_v03_active_arc_count"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_v03_visible_task_count"], 1)
        self.assertNotIn("ywc_dmg_outcome_common_qualification", world.countries["DMG"])

    def test_repeated_payments_are_idempotent_and_keep_income_proportional(self):
        world = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 52_000}})
        world.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        first = world.treasury["DMG"]
        self.assertAlmostEqual(first, -1_000, places=5)
        world.run("ywc_dmg_pay_public_registry_once", tag="DMG")
        self.assertEqual(world.treasury["DMG"], first)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_public_registry_paid"], 1)
        poor = PulseWorld(self.effects, {"DMG": {"yearly_gross_income": 104}})
        poor.run("ywc_dmg_snapshot_costs_once", tag="DMG")
        self.assertEqual(poor.countries["DMG"]["ywc_dmg_public_registry_cost"], 100)

    def test_outcomes_close_once_and_release_capacity_even_after_lost_state(self):
        effects = self.effects + "\nywc_v03_release_arc_dmg_v03_dmg_common_subjects = { set_variable = { name = ywc_v03_dmg_v03_dmg_common_subjects_settled value = 1 } }\n"
        world = PulseWorld(effects, {"DMG": {"ywc_dmg_route": 3, "ywc_dmg_compensation_paid": 1}})
        world.run("ywc_dmg_close_as_breach", tag="DMG")
        world.run("ywc_dmg_close_as_breach", tag="DMG")
        self.assertEqual(world.countries["DMG"]["ywc_dmg_outcome_withdrawn_breach"], 1)
        self.assertEqual(world.countries["DMG"]["ywc_dmg_compensation_paid"], 1)
        self.assertEqual(sum(v for k,v in world.countries["DMG"].items() if k.startswith("ywc_dmg_outcome_")), 1)

if __name__ == "__main__":
    unittest.main()

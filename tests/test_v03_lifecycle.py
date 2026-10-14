"""Offline execution tests for the shared v0.3 lifecycle scripts."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import PulseWorld


EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_effects.txt"
TRIGGERS = ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt"
SHU_EFFECTS = ROOT / "yongchang_world/common/scripted_effects/ywc_v03_shu_effects.txt"
STARTUP = ROOT / "yongchang_world/common/on_actions/ywc_v03_startup.txt"
MIGRATION = ROOT / "yongchang_world/common/decisions/ywc_v03_migration.txt"
LEGACY_SHU_JOURNAL = ROOT / "yongchang_world/common/journal_entries/ywc_shu.txt"
SHU_CATALOG = ROOT / "data/content/v03/countries/shu.json"


class V03LifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = EFFECTS.read_text(encoding="utf-8-sig")
        cls.triggers = TRIGGERS.read_text(encoding="utf-8-sig")

    def world(self, initial=None):
        return PulseWorld(self.effects, {"SHU": initial or {}})

    def test_country_initialization_is_idempotent_and_preserves_existing_state(self):
        world = self.world({"ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                            "ywc_v03_active_arc_count": 2,
                            "ywc_shu_fiscal_installment_paid": 1})
        world.run("ywc_v03_initialize_country")
        world.run("ywc_v03_initialize_country")
        self.assertEqual(world.countries["SHU"]["ywc_v03_active_arc_count"], 2)
        self.assertEqual(world.countries["SHU"]["ywc_shu_fiscal_installment_paid"], 1)

    def test_arc_claim_obeys_three_arc_and_six_task_caps_and_is_idempotent(self):
        world = self.world()
        world.run("ywc_v03_claim_arc_shu_v03_shu_fiscal_register")
        world.run("ywc_v03_claim_arc_shu_v03_shu_fiscal_register")
        state = world.countries["SHU"]
        self.assertEqual(state["ywc_v03_active_arc_count"], 1)
        self.assertEqual(state["ywc_v03_visible_task_count"], 1)
        self.assertTrue(world.conditions(self._trigger_body("ywc_v03_has_capacity"), "SHU"))

        full = self.world({"ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                           "ywc_v03_active_arc_count": 2,
                           "ywc_v03_visible_task_count": 6})
        self.assertFalse(full.conditions(self._trigger_body("ywc_v03_has_capacity"), "SHU"))
        full.run("ywc_v03_claim_arc_shu_v03_shu_fiscal_register")
        self.assertNotIn("ywc_v03_shu_v03_shu_fiscal_register_started", full.countries["SHU"])
        self.assertEqual(full.countries["SHU"]["ywc_v03_visible_task_count"], 6)

        arc_full = self.world({"ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                               "ywc_v03_active_arc_count": 3,
                               "ywc_v03_visible_task_count": 2})
        self.assertFalse(arc_full.conditions(self._trigger_body("ywc_v03_has_capacity"), "SHU"))

    def test_release_requires_a_real_outcome_and_only_decrements_once(self):
        world = self.world({"ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
                            "ywc_v03_active_arc_count": 1,
                            "ywc_v03_visible_task_count": 1,
                            "ywc_v03_shu_v03_shu_fiscal_register_started": 1})
        world.run("ywc_v03_release_arc_shu_v03_shu_fiscal_register")
        self.assertNotIn("ywc_v03_shu_v03_shu_fiscal_register_settled", world.countries["SHU"])
        world.countries["SHU"]["ywc_v03_shu_v03_shu_fiscal_register_outcome"] = 4
        world.run("ywc_v03_release_arc_shu_v03_shu_fiscal_register")
        world.run("ywc_v03_release_arc_shu_v03_shu_fiscal_register")
        state = world.countries["SHU"]
        self.assertEqual(state["ywc_v03_shu_v03_shu_fiscal_register_settled"], 1)
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)
        self.assertEqual(state["ywc_v03_shu_v03_shu_fiscal_register_outcome"], 4)
        self.assertNotIn("ywc_je_shu_fiscal_register_resolved", state)
        self.assertNotIn("ywc_je_shu_fiscal_register_failed", state)

    def test_shu_audit_charge_executes_once_from_the_authored_effect(self):
        # Annual gross income and gold reserves are injected facts. The cost formula, affordability
        # guard, one-time flag, and treasury write run from the actual SHU script.
        world = PulseWorld(SHU_EFFECTS.read_text(encoding="utf-8-sig"),
                           {"SHU": {"yearly_gross_income": 52_000, "gold_reserves": 2_000}})
        before = world.treasury["SHU"]
        world.run("ywc_shu_pay_audit_half_once")
        charged = world.treasury["SHU"]
        world.run("ywc_shu_pay_audit_half_once")
        self.assertAlmostEqual(charged - before, -500, places=6)
        self.assertEqual(world.treasury["SHU"], charged)
        self.assertEqual(world.countries["SHU"]["ywc_shu_audit_installment_paid"], 1)

    def test_shu_consolidation_review_resets_on_interruption_and_checks_real_conditions(self):
        # Static contract check: the harness intentionally does not simulate Clausewitz days.
        arc = json.loads(SHU_CATALOG.read_text(encoding="utf-8"))["arcs"][0]
        journals = {row["id"]: row["script"] for row in arc["journals"]}
        events = {row["id"]: row for row in arc["events"]}
        settlement = journals["ywc_je_v03_shu_fiscal_settlement"]
        shu_effects = SHU_EFFECTS.read_text(encoding="utf-8-sig")
        start_review_effect = shu_effects.split("ywc_shu_start_settlement_review = {", 1)[1].split("\nywc_shu_choose_central_settlement", 1)[0]
        self.assertIn("days = 180", start_review_effect)
        shu_triggers = (ROOT / "yongchang_world/common/scripted_triggers/ywc_v03_shu_triggers.txt").read_text(encoding="utf-8-sig")
        self.assertIn("has_law_or_variant = law_type:law_land_based_taxation", shu_triggers)
        self.assertIn("bureaucracy >= 0", shu_triggers)
        self.assertIn("is_building_type = building_government_administration", shu_triggers)
        self.assertIn("occupancy >= 0.8", shu_triggers)
        self.assertIn("building_has_goods_shortage = no", shu_triggers)
        for condition in (
            "is_at_war = yes", "in_default = yes", "net_fixed_income < 0",
            "NOT = { ywc_shu_v03_has_pilot_state = yes }",
        ):
            self.assertIn(condition, settlement)
        interrupted = next(option["effect"] for option in events["ywc_shu.1008"]["options"]
                           if option["key"] == "limit_for_war")
        self.assertIn("remove_variable = ywc_shu_settlement_review_due", interrupted)
        self.assertIn("remove_variable = ywc_shu_settlement_review", interrupted)
        resume_gate = "has_variable = ywc_shu_wartime_deferral NOT = { is_at_war = yes } NOT = { in_default = yes } net_fixed_income >= 0 ywc_shu_v03_real_execution_ready = yes"
        self.assertIn(resume_gate, settlement)
        restart_choices = [option["effect"] for option in events["ywc_shu.1007"]["options"]]
        self.assertTrue(any("ywc_shu_start_settlement_review = yes" in effect
                            for effect in restart_choices))

    def test_startup_is_tag_scoped_and_migration_is_explicit_and_idempotent(self):
        startup = STARTUP.read_text(encoding="utf-8-sig")
        decision = MIGRATION.read_text(encoding="utf-8-sig")
        self.assertIn("on_game_started_after_lobby", startup)
        self.assertIn("c:SHU = this", startup)
        self.assertIn("c:DMG = this", startup)
        self.assertIn("c:KOR = this", startup)
        self.assertIn("ywc_v03_initialize_country = yes", startup)
        self.assertNotIn("add_journal_entry", startup)
        self.assertIn("NOT = { has_variable = ywc_v03_initialized }", decision)
        self.assertIn("ywc_v03_migration_recorded", decision)
        self.assertIn("ywc_v03_initialize_country = yes", decision)
        for relative in (
            "yongchang_world/localization/simp_chinese/ywc_v03_migration_l_simp_chinese.yml",
            "yongchang_world/localization/english/ywc_v03_migration_l_english.yml",
        ):
            data = (ROOT / relative).read_bytes()
            self.assertTrue(data.startswith(b"\xef\xbb\xbf"), relative)
            self.assertIn("not refunded".encode() if "english" in relative else "不会退还".encode(), data)

    def test_legacy_court_one_stops_only_after_this_arc_starts(self):
        from clausewitz_harness import parse

        old_script = LEGACY_SHU_JOURNAL.read_text(encoding="utf-8-sig")
        journal = next(body for key, _, body in parse(old_script)
                       if key == "ywc_je_flavor_shu_court_1")
        pulse = next(body for key, _, body in journal if key == "on_monthly_pulse")
        pulse_effect = next(body for key, _, body in pulse if key == "effect")
        first_limit = next(body for key, _, body in pulse_effect if key == "if")
        first_limit = next(body for key, _, body in first_limit if key == "limit")

        world = self.world()
        world.run("ywc_v03_initialize_country")
        self.assertTrue(world.conditions(first_limit, "SHU"), "init must leave the old arc dispatchable")
        world.run("ywc_v03_claim_arc_shu_v03_shu_fiscal_register")
        self.assertFalse(world.conditions(first_limit, "SHU"), "started marker must stop old c1 dispatch")

    def test_real_outcomes_bridge_once_to_old_court_chapter_and_continue_court_two(self):
        for new_result, old_result, legacy_terminal in (
            (1, 1, "resolved"), (2, 2, "resolved"), (3, 2, "resolved"), (4, 3, "failed"),
        ):
            with self.subTest(new_result=new_result):
                world = self.world()
                world.run("ywc_v03_claim_arc_shu_v03_shu_fiscal_register")
                world.countries["SHU"]["ywc_v03_shu_v03_shu_fiscal_register_outcome"] = new_result
                world.run("ywc_v03_release_arc_shu_v03_shu_fiscal_register")
                world.run("ywc_v03_release_arc_shu_v03_shu_fiscal_register")
                state = world.countries["SHU"]
                self.assertEqual(state["ywc_campaign_shu_c1_outcome"], old_result)
                self.assertEqual(state[f"ywc_je_flavor_shu_court_1_{legacy_terminal}"], 1)
                other = "failed" if legacy_terminal == "resolved" else "resolved"
                self.assertNotIn(f"ywc_je_flavor_shu_court_1_{other}", state)
                court_two_adds = [item for item in world.journals
                                  if dict((key, value) for key, _, value in item[1]).get("type")
                                  == "ywc_je_flavor_shu_court_2"]
                self.assertEqual(len(court_two_adds), 1)

    def _trigger_body(self, name):
        from clausewitz_harness import parse

        return next(body for key, _, body in parse(self.triggers) if key == name)


if __name__ == "__main__":
    unittest.main()

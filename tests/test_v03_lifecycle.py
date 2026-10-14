"""Offline execution tests for the shared v0.3 lifecycle scripts."""
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
        # GDP and gold reserves are injected facts. The cost formula, affordability
        # guard, one-time flag, and treasury write run from the actual SHU script.
        world = PulseWorld(SHU_EFFECTS.read_text(encoding="utf-8-sig"),
                           {"SHU": {"gdp": 2_000_000, "gold_reserves": 2_000}})
        before = world.treasury["SHU"]
        world.run("ywc_shu_pay_audit_half_once")
        charged = world.treasury["SHU"]
        world.run("ywc_shu_pay_audit_half_once")
        self.assertEqual(charged - before, -500)
        self.assertEqual(world.treasury["SHU"], charged)
        self.assertEqual(world.countries["SHU"]["ywc_shu_audit_installment_paid"], 1)

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

    def _trigger_body(self, name):
        from clausewitz_harness import parse

        return next(body for key, _, body in parse(self.triggers) if key == name)


if __name__ == "__main__":
    unittest.main()

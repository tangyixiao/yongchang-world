"""The actual military budget entry initializes only missing numeric progress."""
import unittest

from kor_partner_protocol_runtime import PartnerWorld


def world_with(**progress):
    return PartnerWorld({"KOR": {"yearly_gross_income": 52000, "states": [], **progress}})


class KorCounterInitializationTests(unittest.TestCase):
    def test_fresh_capture_initializes_numeric_progress_without_awarding_business_state(self):
        world = world_with()
        world.run("ywc_kor_capture_cost_base", "KOR")
        state = world.countries["KOR"]
        self.assertEqual(state.get("ywc_kor_ready_supply_months"), 0)
        self.assertEqual(state["ywc_kor_weekly_cost"], 1000)
        self.assertEqual(state["ywc_kor_cost_captured"], 1)
        self.assertEqual(world.treasury["KOR"], 0)
        for name in ("ywc_kor_six_months_complete", "ywc_kor_nine_months_complete",
                     "ywc_kor_audit_paid", "ywc_kor_invoice_review_paid", "ywc_kor_any_outcome"):
            self.assertNotIn(name, state)

    def test_repeated_capture_preserves_both_existing_progress_values_and_income_snapshot(self):
        world = world_with(ywc_kor_ready_supply_months=7, ywc_kor_service_paid_months=2)
        world.run("ywc_kor_capture_cost_base", "KOR")
        state = world.countries["KOR"]
        state["yearly_gross_income"] = 104000
        before = dict(state)
        world.run("ywc_kor_capture_cost_base", "KOR")
        world.run("ywc_kor_capture_cost_base", "KOR")
        self.assertEqual(state, before)
        self.assertEqual(state["ywc_kor_ready_supply_months"], 7)
        self.assertEqual(state["ywc_kor_service_paid_months"], 2)
        self.assertEqual(state["ywc_kor_weekly_cost"], 1000)

    def test_already_captured_budget_can_fill_missing_progress_without_recapturing(self):
        world = world_with(ywc_kor_cost_captured=1, ywc_kor_weekly_cost=345)
        world.run("ywc_kor_capture_cost_base", "KOR")
        state = world.countries["KOR"]
        self.assertEqual(state.get("ywc_kor_ready_supply_months"), 0)
        self.assertEqual(state["ywc_kor_weekly_cost"], 345)
        self.assertEqual(state["ywc_kor_cost_captured"], 1)
        self.assertNotIn("ywc_kor_service_paid_months", state)


if __name__ == "__main__":
    unittest.main()

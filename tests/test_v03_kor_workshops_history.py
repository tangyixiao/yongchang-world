"""Earn the real KOR military and school histories in the workshops fact world."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v03_kor_workshops_literal import world
from test_v03_kor_revenue_cross_era import earn_military, earn_school


class KorWorkshopHistoryProducers(unittest.TestCase):
    def test_old_military_and_school_contracts_are_earned_through_real_events(self):
        w = world()
        state = w.countries["KOR"]
        self.assertNotIn("ywc_campaign_kor_c1_outcome", state)
        self.assertNotIn("ywc_kor_school_coop_paid", state)
        state["literacy_rate"] = .5  # Current population fact, not an earned story marker.
        w.modifiers.append(("KOR", {"modifier": "military_wages_medium"}))
        w.run("ywc_v03_initialize_country", "KOR")
        earn_military(w, "provincial")
        self.assertEqual(state["ywc_v03_kor_v03_kor_military_accounts_outcome"], 2)
        for kind in ("translation", "veteran"):
            self.assertEqual(state["ywc_kor_" + kind + "_contract_paid_months"], 12)
        earn_school(w, "cooperative")
        self.assertEqual(state["ywc_v03_kor_v03_kor_school_factions_outcome"], 1)
        self.assertEqual(state["ywc_v03_kor_v03_kor_school_factions_settled"], 1)
        self.assertTrue(w.conditions(w.trigger_defs["ywc_kor_revenue_prior_school_coop"], "KOR"))
        self.assertTrue(any(entry["cash_delta"] < 0 for entry in w.earned_monthly_ledger))
        earned = [(entry["earned_event"], entry["key"]) for entry in w.trace if "earned_event" in entry]
        self.assertIn(("ywc_kor.1000", "provincial_share"), earned)
        self.assertIn(("ywc_kor.1010", "co_manage"), earned)
        self.assertIn(("ywc_kor.1017", "settle_established"), earned)


if __name__ == "__main__":
    unittest.main()

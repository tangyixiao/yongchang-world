"""Exact calendar terms for independently signed JHG partnerships."""
import unittest
from datetime import date

from test_v03_jhg_escort_response import JhgWorld, base_countries, signed_partnership
from test_v03_jhg_share_response import JhgShareWorld, share_countries, select_option


class JhgContractTermTests(unittest.TestCase):
    def test_midmonth_escort_and_share_keep_the_full_120_month_term(self):
        for kind in ("escort", "share"):
            with self.subTest(kind=kind):
                countries = base_countries() if kind == "escort" else share_countries()
                world = JhgWorld(countries) if kind == "escort" else JhgShareWorld(countries)
                world.run_country_monthly("JHG")
                world.advance_days(14)
                if kind == "escort":
                    signed_partnership(world)
                else:
                    select_option(world, "ywc_jhg.1020", "project_share")
                    offer = world.jobs[-1]
                    self.assertTrue(world.display_job(offer))
                    world.choose_job(offer, "accept")
                trigger = f"ywc_jhg_{kind}_contract_active"
                world.advance_days((date(1846, 1, 1) - world.date).days)
                world.run_country_monthly("JHG")
                self.assertTrue(world.conditions(world.trigger_defs[trigger], "JHG"))
                world.advance_days(14)
                world.run_due_hidden()
                self.assertFalse(world.conditions(world.trigger_defs[trigger], "JHG"))


if __name__ == "__main__":
    unittest.main()

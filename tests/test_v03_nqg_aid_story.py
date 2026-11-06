"""Offline end-to-end source story for an actual NQG grain-aid partner."""
import json
import unittest
from pathlib import Path

from test_v03_nqg_aid_regressions import NqgAidFactsWorld
from test_v03_nqg_aid_response import base_countries, install_route


class NqgAidStoryTests(unittest.TestCase):
    def test_real_shu_answer_notice_signature_grain_and_winter_settlement(self):
        catalog = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_nqg_winter_court")
        countries = base_countries()
        state = countries["NQG"]
        for key in ("ywc_nqg_winter_fee", "ywc_nqg_winter_fee_paid", "ywc_nqg_winter_route", "ywc_nqg_winter_route_lock"):
            state.pop(key, None)
        state.update({"government_legitimacy": 80, "ywc_v03_active_arc_count": 0,
                      "ywc_v03_visible_task_count": 0, "ywc_campaign_nqg_c1_outcome": 1})
        world = NqgAidFactsWorld(countries)
        install_route(countries, "SHU")
        world.activate_entry(arc, arc["journals"][0]["id"])
        choices = {"ywc_nqg.1000": "grain_loan", "ywc_nqg.1001": "cap_exempt_clan",
                   "ywc_nqg.1002": "audit_districts", "ywc_nqg.1003": "cap_soldiers",
                   "ywc_nqg.1004": "let_market_run", "ywc_nqg.1005": "take_loan_terms",
                   "ywc_nqg.1006": "publish_count", "ywc_nqg.1007": "make_standing_rule",
                   "ywc_nqg.1008": "hold_buffer", "ywc_nqg.1030": "accept"}
        completed, trace = set(), []
        for month in range(120):
            world.run_due_hidden()
            world.run_country_monthly("NQG")
            world.pulse(arc)
            while True:
                jobs = [job for job in world.jobs if job.serial not in completed and job.due_day <= world.day
                        and job.event_id != "ywc_nqg.1032"]
                if not jobs:
                    break
                job = jobs[0]; completed.add(job.serial)
                self.assertTrue(world.display_job(job), (month, job.event_id))
                legal = world.job_options(job)
                if job.event_id == "ywc_nqg.1031":
                    choice = "sign_terms" if legal.get("sign_terms") else "review_status"
                elif job.event_id == "ywc_nqg.1009":
                    choice = "settle_full" if legal.get("settle_full") else "acknowledge_12_month_notice" if legal.get("acknowledge_12_month_notice") else "withdraw_after_36_month_notice" if legal.get("withdraw_after_36_month_notice") else None
                else:
                    choice = choices[job.event_id]
                self.assertTrue(choice and legal.get(choice), (month, job.event_id, choice, legal, trace))
                world.choose_job(job, choice)
                trace.append((month, job.event_id, job.recipient.tag, choice))
            world.refresh(arc)
            if state.get("ywc_v03_nqg_v03_nqg_winter_court_settled"):
                break
            world.advance_months(1)
        else:
            self.fail(("winter aid route did not settle", trace))
        for event_id in ("ywc_nqg.1000", "ywc_nqg.1030", "ywc_nqg.1031", "ywc_nqg.1005", "ywc_nqg.1009"):
            self.assertTrue(any(row[1] == event_id for row in trace), (event_id, trace))
        self.assertEqual(state["ywc_nqg_aid_contract_partner"], world.country_ref("SHU"))
        self.assertEqual(state["ywc_nqg_aid_paid_total"], 3000, (trace, state.get("ywc_nqg_aid_earned_count"), state.get("ywc_nqg_aid_window_ended_generation")))
        self.assertEqual(world.treasury["SHU"], 3000)
        self.assertEqual(state["ywc_v03_nqg_v03_nqg_winter_court_outcome"], 3)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))


if __name__ == "__main__":
    unittest.main()

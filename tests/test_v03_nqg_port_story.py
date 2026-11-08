"""Offline source journeys for the NQG port lease and domestic refusal path."""
import json
import unittest
from pathlib import Path

from test_v03_nqg_port_regressions import NqgPortFactsWorld
from test_v03_nqg_port_response import base_countries


class NqgPortStoryTests(unittest.TestCase):
    def test_actual_port_queue_with_partner_acceptance_or_refusal(self):
        catalog = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_nqg_northern_port")
        for answer in ("accept", "refuse"):
            with self.subTest(answer=answer):
                countries = base_countries()
                state = countries["NQG"]
                for key in ("ywc_nqg_port_fee", "ywc_nqg_port_fee_paid", "ywc_nqg_port_route",
                            "ywc_nqg_port_implementation_started", "ywc_nqg_port_route_lock"):
                    state.pop(key, None)
                state.update({"government_legitimacy": 80, "ywc_v03_active_arc_count": 0,
                              "ywc_v03_visible_task_count": 0, "ywc_campaign_nqg_c1_outcome": 1})
                world = NqgPortFactsWorld(countries)
                world.activate_entry(arc, arc["journals"][0]["id"])
                options = {"ywc_nqg.1020": "exclusive_lease", "ywc_nqg.1021": "by_tonnage",
                           "ywc_nqg.1022": "levy_users", "ywc_nqg.1023": "renegotiate" if answer == "accept" else "switch_open_berths",
                           "ywc_nqg.1024": "recognise_duties", "ywc_nqg.1025": "dismiss_gangs",
                           "ywc_nqg.1026": "renew" if answer == "accept" else "continue_domestic"}
                completed, trace, replies = set(), [], 0
                for month in range(100):
                    world.run_due_hidden(); world.run_country_monthly("NQG"); world.pulse(arc)
                    while True:
                        jobs = [job for job in world.jobs if job.serial not in completed and job.due_day <= world.day
                                and job.event_id != "ywc_nqg.1029"]
                        if not jobs:
                            break
                        job = jobs[0]; completed.add(job.serial)
                        self.assertTrue(world.display_job(job), (month, job.event_id))
                        legal = world.job_options(job)
                        if job.event_id == "ywc_nqg.1028":
                            choice = answer if replies == 0 else "accept"
                            replies += 1
                        elif job.event_id == "ywc_nqg.1027":
                            choice = "settle_full" if legal.get("settle_full") else "acknowledge_12_month_notice" if legal.get("acknowledge_12_month_notice") else None
                        else:
                            choice = options[job.event_id]
                        self.assertTrue(choice and legal.get(choice), (month, job.event_id, choice, legal, trace))
                        world.choose_job(job, choice)
                        trace.append((month, job.event_id, job.recipient.tag, choice))
                    world.refresh(arc)
                    if state.get("ywc_v03_nqg_v03_nqg_northern_port_settled"):
                        break
                    world.advance_months(1)
                else:
                    self.fail((answer, "port did not settle", trace))
                self.assertEqual(state["ywc_v03_nqg_v03_nqg_northern_port_outcome"], 3)
                self.assertEqual(state["ywc_nqg_port_route"], 2 if answer == "accept" else 1)
                self.assertEqual(replies, 3 if answer == "accept" else 1)
                self.assertEqual((world.treasury["NQG"], world.treasury["RUS"]), (-1500, 500) if answer == "accept" else (-1000, 0))
                self.assertEqual(world.history["NQG"], {j["id"]: "complete" for j in arc["journals"]})


if __name__ == "__main__":
    unittest.main()

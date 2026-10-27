"""JHG convoy journey through actual authored dispatch and partner responses.

The deterministic source interpreter models country facts and event scheduling;
it does not claim Victoria 3 engine or gameplay validation.
"""
import json
import unittest
from pathlib import Path

from test_v03_jhg_escort_response import JhgWorld, base_countries


class JhgEscortStoryTests(unittest.TestCase):
    def test_partner_loss_after_negotiation_can_switch_to_a_new_domestic_watch(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(row for row in catalog["arcs"] if row["slug"] == "v03_jhg_convoy_capacity")
        for choice, route in (("switch_main_lane", 1), ("switch_insurance", 3)):
            with self.subTest(choice=choice):
                countries = base_countries()
                state = countries["JHG"]
                for name in ("ywc_jhg_convoy_filing_fee", "ywc_jhg_convoy_filing_fee_paid",
                             "ywc_jhg_convoy_route", "ywc_jhg_convoy_implementation_started",
                             "ywc_jhg_convoy_route_lock"):
                    state.pop(name, None)
                state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                              "ywc_campaign_jhg_c1_outcome": 1})
                world = JhgWorld(countries)
                world.activate_entry(arc, arc["journals"][0]["id"])
                options = {"ywc_jhg.1010": "shared_escort", "ywc_jhg.1011": "main_lane",
                           "ywc_jhg.1012": "shared_escort", "ywc_jhg.1013": "main_lane",
                           "ywc_jhg.1014": "insurance", "ywc_jhg.1015": "explain_limits",
                           "ywc_jhg.1016": "main_lane", "ywc_jhg.1017": "hold_course",
                           "ywc_jhg.1030": "accept"}
                completed, trace, switched_at = set(), [], None
                partner_lost = False
                for month in range(100):
                    if not partner_lost and "ywc_je_v03_jhg_convoy_settlement" in world.active["JHG"]:
                        self.assertIn("ywc_jhg_convoy_six_months_complete", state)
                        countries["LAN"]["navy_size"] = 0
                        for building in countries["LAN"]["states"][0]["buildings"]:
                            if building["type"] == "building_port":
                                building["occupancy"] = 0.1
                        partner_lost = True
                    world.run_country_monthly("JHG")
                    world.pulse(arc)
                    while True:
                        jobs = [job for job in world.jobs if job.serial not in completed
                                and job.due_day <= world.day and job.event_id != "ywc_jhg.1031"]
                        if not jobs:
                            break
                        job = jobs[0]
                        completed.add(job.serial)
                        self.assertTrue(world.display_job(job), (month, job.event_id))
                        legal = world.job_options(job)
                        if job.event_id == "ywc_jhg.1018":
                            if switched_at is None:
                                self.assertFalse(legal.get("settle_full"))
                                self.assertFalse(legal.get("settle_partial"))
                                key, switched_at = choice, month
                            else:
                                key = "settle_partial" if legal.get("settle_partial") else "defer"
                        else:
                            key = options[job.event_id]
                        self.assertTrue(legal.get(key), (month, job.event_id, key, legal))
                        world.choose_job(job, key)
                        trace.append((month, job.event_id, key))
                        if key == choice:
                            self.assertEqual(state["ywc_jhg_convoy_route"], route)
                            self.assertNotIn("ywc_jhg_convoy_six_months_complete", state)
                            self.assertEqual(state["ywc_jhg_escort_contract_generation"], 1)
                            self.assertEqual((world.treasury["JHG"], world.treasury["LAN"]), (-1500, 500))
                    world.refresh(arc)
                    if state.get("ywc_jhg_v03_jhg_convoy_capacity_settled"):
                        break
                    world.advance_months(1)
                else:
                    self.fail((choice, "domestic fallback did not settle", trace))
                self.assertTrue(partner_lost)
                self.assertIsNotNone(switched_at)
                self.assertGreaterEqual(month - switched_at, 6)
                self.assertEqual(state["ywc_jhg_v03_jhg_convoy_capacity_outcome"], 2)
                self.assertEqual((world.treasury["JHG"], world.treasury["LAN"]), (-1500, 500))

    def test_real_admission_partner_answer_and_convoy_settlement(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(row for row in catalog["arcs"] if row["slug"] == "v03_jhg_convoy_capacity")
        cases = (("shared_escort", "LAN", False), ("shared_escort_dmg", "DMG", False),
                 ("shared_escort", "LAN", True))
        for opening, partner, interrupt in cases:
            with self.subTest(partner=partner, interrupt=interrupt):
                countries = base_countries()
                state = countries["JHG"]
                for name in ("ywc_jhg_convoy_filing_fee", "ywc_jhg_convoy_filing_fee_paid",
                             "ywc_jhg_convoy_route", "ywc_jhg_convoy_implementation_started",
                             "ywc_jhg_convoy_route_lock"):
                    state.pop(name, None)
                state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                              "ywc_campaign_jhg_c1_outcome": 1})
                world = JhgWorld(countries)
                world.activate_entry(arc, arc["journals"][0]["id"])
                options = {"ywc_jhg.1010": opening, "ywc_jhg.1011": "main_lane",
                           "ywc_jhg.1012": "shared_escort", "ywc_jhg.1013": "main_lane",
                           "ywc_jhg.1014": "insurance", "ywc_jhg.1015": "explain_limits",
                           "ywc_jhg.1016": "main_lane", "ywc_jhg.1017": "hold_course",
                           "ywc_jhg.1030": "accept"}
                completed_jobs, trace = set(), []
                interruption_start = None
                recovered_at = None
                for month in range(80):
                    if (interrupt and interruption_start is None and
                            "ywc_je_v03_jhg_convoy_settlement" in world.active["JHG"]):
                        self.assertIn("ywc_jhg_convoy_six_months_complete", state)
                        interruption_start = month
                        countries[partner]["navy_size"] = 0
                        for building in countries[partner]["states"][0]["buildings"]:
                            if building["type"] == "building_port":
                                building["occupancy"] = 0.1
                    if interruption_start is not None and month == interruption_start + 2:
                        countries[partner]["navy_size"] = 5
                        recovered_at = month
                    world.run_country_monthly("JHG")
                    world.pulse(arc)
                    if interruption_start is not None and month < interruption_start + 2:
                        self.assertEqual(state["ywc_jhg_escort_suspended_generation"], 1)
                        self.assertIn("ywc_je_v03_jhg_convoy_settlement", world.active["JHG"])
                        self.assertIn("ywc_jhg_convoy_six_months_complete", state)
                        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_convoy_current_target_ready"], "JHG"))
                    if recovered_at == month:
                        self.assertNotIn("ywc_jhg_escort_suspended_generation", state)
                        self.assertIn("ywc_jhg_convoy_six_months_complete", state)
                        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_convoy_current_target_ready"], "JHG"))
                    # Drain only actually dispatched, due jobs. A foreign answer
                    # may be queued while choosing the opening event.
                    while True:
                        jobs = [job for job in world.jobs if job.serial not in completed_jobs
                                and job.due_day <= world.day and job.event_id != "ywc_jhg.1031"]
                        if not jobs:
                            break
                        job = jobs[0]
                        completed_jobs.add(job.serial)
                        self.assertTrue(world.display_job(job), (month, job.event_id))
                        legal = world.job_options(job)
                        if job.event_id == "ywc_jhg.1018":
                            key = ("settle_partial" if legal.get("settle_partial") else
                                   "acknowledge_12_notice" if legal.get("acknowledge_12_notice") else "defer")
                        else:
                            key = options[job.event_id]
                        self.assertTrue(legal.get(key), (month, job.event_id, key, legal))
                        trace.append((month, job.event_id, job.recipient.tag, key))
                        world.choose_job(job, key)
                    world.refresh(arc)
                    if state.get("ywc_jhg_v03_jhg_convoy_capacity_settled"):
                        break
                    world.advance_months(1)
                else:
                    self.fail((partner, "convoy did not settle", trace))

                self.assertEqual([row[1] for row in trace], [
                    "ywc_jhg.1010", "ywc_jhg.1030", "ywc_jhg.1011", "ywc_jhg.1012",
                    "ywc_jhg.1013", "ywc_jhg.1014", "ywc_jhg.1015", "ywc_jhg.1016",
                    "ywc_jhg.1017", "ywc_jhg.1018"])
                self.assertEqual(trace[1][2:], (partner, "accept"))
                domestic_months = [month for month, _, tag, _ in trace if tag == "JHG"]
                self.assertTrue(all(b - a >= 3 for a, b in zip(domestic_months, domestic_months[1:])))
                self.assertEqual(state["ywc_jhg_convoy_route"], 2)
                self.assertEqual(state["ywc_jhg_escort_contract_partner"], world.country_ref(partner))
                self.assertEqual(state["ywc_jhg_v03_jhg_convoy_capacity_outcome"], 2)
                self.assertEqual(world.treasury["JHG"], -1500)
                self.assertEqual(world.treasury[partner], 500)
                self.assertEqual(world.treasury["DMG" if partner == "LAN" else "LAN"], 0)
                self.assertEqual(world.history["JHG"], {row["id"]: "complete" for row in arc["journals"]})
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
                if interrupt:
                    self.assertIsNotNone(recovered_at)
                    self.assertGreaterEqual(trace[-1][0] - recovered_at, 6)


if __name__ == "__main__":
    unittest.main()

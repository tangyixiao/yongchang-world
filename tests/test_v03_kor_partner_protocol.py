"""Source-driven acceptance for the KOR instructor partner protocol."""
import copy
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field


def protocol_world():
    countries = {tag: copy.deepcopy(facts()) for tag in ("KOR", "SHU", "JHG")}
    countries["KOR"]["ywc_kor_weekly_cost"] = 1200
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    return PartnerWorld(countries), countries


def send_offer(world, partner="SHU"):
    event = world.event_defs["ywc_kor.1004"]
    option = next(body for key, _, body in event if key == "option"
                  and field(body, "name").endswith(".offer_" + partner.lower()))
    world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "KOR")
    return world.jobs[-1]


class InstructorPartnerProtocolTests(unittest.TestCase):
    def test_actual_two_provider_choices_and_real_recipient_dispatch(self):
        for partner in ("SHU", "JHG"):
            with self.subTest(partner=partner):
                countries = {tag: copy.deepcopy(facts()) for tag in ("KOR", "SHU", "JHG")}
                countries["KOR"]["ywc_kor_weekly_cost"] = 1000
                for tag in countries:
                    countries[tag]["relations"] = {other: 10 for other in countries}
                world = PartnerWorld(countries)
                event = world.event_defs["ywc_kor.1004"]
                options = {field(body, "name").rsplit(".", 1)[-1]: body
                           for key, _, body in event if key == "option"}
                # Before implementation the genuine 1004 inquiry is the sole
                # foreign option. Execute it rather than failing on a missing
                # proposed helper or option name.
                source_option = options.get(f"offer_{partner.lower()}", options.get("foreign_offer"))
                self.assertIsNotNone(source_option)
                executable = [node for node in source_option
                              if node[0] not in ("name", "trigger", "ai_chance")]
                self.assertTrue(executable)
                world.execute(executable, "KOR")
                if "foreign_offer" in options:
                    self.assertEqual(countries["KOR"].get("ywc_kor_foreign_offer_pending"), 1)
                    self.assertEqual(countries["KOR"].get("ywc_kor_pending_event"), 1005)
                self.assertTrue(world.jobs, "1004 inquiry did not dispatch a foreign event")
                self.assertEqual(world.jobs[-1].event_id, "ywc_kor.1030")
                self.assertEqual(world.jobs[-1].recipient, world.country_ref(partner))
                self.assertTrue(world.display_job(world.jobs[-1]))
                self.assertTrue(world.job_options(world.jobs[-1])["accept"])
                world.choose_job(world.jobs[-1], "accept")
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_contract_partner"], world.country_ref(partner))
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_balance"], 1000)
                self.assertEqual(world.treasury["KOR"], 0)
                self.assertEqual(world.treasury[partner], 0)

    def test_actual_provider_requester_ownership_and_thresholds(self):
        for defect in ("requester_owner", "provider_owner", "requester_occupancy",
                       "provider_occupancy", "requester_shortage", "provider_shortage",
                       "subject", "hostile", "dead"):
            with self.subTest(defect=defect):
                world, countries = protocol_world()
                if defect == "requester_owner":
                    countries["KOR"]["states"][0]["owner"] = "SHU"
                elif defect == "provider_owner":
                    countries["SHU"]["states"][0]["owner"] = "KOR"
                elif defect.endswith("occupancy"):
                    tag = "KOR" if defect.startswith("requester") else "SHU"
                    for building in countries[tag]["states"][0]["buildings"]:
                        building["occupancy"] = 0.79
                elif defect.endswith("shortage"):
                    tag = "KOR" if defect.startswith("requester") else "SHU"
                    for building in countries[tag]["states"][0]["buildings"]:
                        building["shortage"] = True
                elif defect == "subject":
                    countries["KOR"]["is_subject"] = True
                elif defect == "hostile":
                    countries["SHU"]["relations"]["KOR"] = -1
                else:
                    countries["SHU"]["is_country_alive"] = False
                self.assertFalse(world.check_script("ywc_kor_instructor_can_offer_shu = yes"))
                world.run_script("ywc_kor_instructor_send_shu = yes")
                self.assertFalse(world.jobs)

    def test_send_and_silence_create_no_signed_cost_or_service(self):
        world, countries = protocol_world()
        job = send_offer(world)
        kor = countries["KOR"]
        self.assertEqual(kor["ywc_kor_instructor_state"], 1)
        self.assertNotIn("ywc_kor_instructor_contract_partner", kor)
        self.assertFalse(world.modifiers)
        self.assertEqual(sum(world.treasury.values()), 0)
        world.advance_months(3)
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_state"], 4)
        self.assertEqual(kor["ywc_kor_instructor_notice_reason"], 3)
        self.assertFalse(world.display_job(job))
        self.assertEqual(sum(world.treasury.values()), 0)

    def test_actual_accept_and_refuse_author_distinct_answers(self):
        for choice, answer, state in (("accept", 1, 2), ("refuse", 2, 3)):
            with self.subTest(choice=choice):
                world, countries = protocol_world()
                job = send_offer(world, "JHG")
                self.assertTrue(world.display_job(job))
                self.assertTrue(world.job_options(job)[choice])
                world.choose_job(job, choice)
                self.assertEqual(countries["JHG"]["ywc_kor_instructor_answer"], answer)
                self.assertEqual(countries["JHG"]["ywc_kor_instructor_answer_requester"], world.country_ref("KOR"))
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_state"], state)
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_notice_reason"], answer)
                self.assertEqual(sum(world.treasury.values()), 0)
                if choice == "refuse":
                    self.assertNotIn("ywc_kor_instructor_balance", countries["KOR"])

    def test_stale_answer_same_partner_and_aba_generation(self):
        world, countries = protocol_world()
        old = send_offer(world)
        self.assertTrue(world.display_job(old))
        world.choose_job(old, "refuse")
        middle = send_offer(world, "JHG")
        self.assertTrue(world.display_job(middle))
        world.choose_job(middle, "refuse")
        current = send_offer(world, "SHU")
        self.assertEqual([dict(j.saved)["ywc_kor_request_generation"] for j in (old, middle, current)], [1, 2, 3])
        for choice in ("accept", "refuse"):
            world.choose_job(old, choice)
            self.assertEqual(countries["KOR"]["ywc_kor_instructor_state"], 1)
            self.assertNotIn("ywc_kor_instructor_balance", countries["KOR"])
        self.assertTrue(world.display_job(current))
        world.choose_job(current, "accept")
        self.assertEqual(countries["KOR"]["ywc_kor_instructor_contract_generation"], 3)

    def test_answer_rechecks_live_eligibility_and_fixed_terms(self):
        world, countries = protocol_world()
        job = send_offer(world)
        self.assertTrue(world.display_job(job))
        countries["SHU"]["states"][0]["buildings"][1]["shortage"] = True
        self.assertFalse(world.job_options(job)["accept"])
        world.choose_job(job, "accept")
        self.assertNotIn("ywc_kor_instructor_balance", countries["KOR"])
        countries["SHU"]["states"][0]["buildings"][1]["shortage"] = False
        countries["KOR"]["ywc_kor_instructor_request_months"] = 11
        self.assertFalse(world.job_options(job)["accept"])
        countries["KOR"]["ywc_kor_instructor_request_months"] = 12
        world.choose_job(job, "accept")
        self.assertEqual(countries["KOR"]["ywc_kor_instructor_contract_total"], 1200)

    def test_timeout_subject_absence_and_domestic_continuation(self):
        for defect in ("timeout", "subject", "absence"):
            with self.subTest(defect=defect):
                world, countries = protocol_world()
                send_offer(world)
                if defect == "timeout":
                    world.advance_months(3)
                elif defect == "subject":
                    countries["KOR"]["is_subject"] = True
                else:
                    world.remove_country("SHU")
                world.run_country_monthly()
                self.assertIn(countries["KOR"]["ywc_kor_instructor_state"], (4, 5))
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_notice_event"], 1031)
                self.assertNotIn("ywc_kor_instructor_balance", countries["KOR"])

    def test_actual_domestic_path_keeps_original_translation_veteran_costs(self):
        world, countries = protocol_world()
        kor = countries["KOR"]
        option = next(body for key, _, body in world.event_defs["ywc_kor.1004"]
                      if key == "option" and field(body, "name").endswith(".fund_local"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "KOR")
        self.assertIn("ywc_kor_translation_contract_started", kor)
        self.assertEqual(kor["ywc_kor_local_translation_funded"], 1)
        self.assertEqual(kor["ywc_kor_pending_event"], 1005)
        self.assertNotIn("ywc_kor_instructor_contract_partner", kor)
        self.assertEqual(sum(world.treasury.values()), 0)


if __name__ == "__main__":
    unittest.main()

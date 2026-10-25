"""Execution of the authored KOR consent, monthly ledger, and endpoint."""
import copy
from dataclasses import replace
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field


def signed_world(partner="SHU", total=1200):
    countries = {tag: copy.deepcopy(facts()) for tag in ("KOR", "SHU", "JHG")}
    countries["KOR"]["ywc_kor_weekly_cost"] = total
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    world = PartnerWorld(countries)
    event = world.event_defs["ywc_kor.1004"]
    choice = next(body for key, _, body in event if key == "option" and field(body, "name").endswith(".offer_" + partner.lower()))
    world.execute([node for node in choice if node[0] not in ("name", "trigger", "ai_chance")], "KOR")
    job = world.jobs[-1]
    assert world.display_job(job)
    world.choose_job(job, "accept")
    return world, countries


class InstructorLifecycleTests(unittest.TestCase):
    def test_first_real_monthly_muster_starts_term_and_one_endpoint(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        self.assertNotIn("ywc_kor_instructor_service_start_month", kor)
        self.assertEqual(world.treasury["KOR"], 0)
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 1)
        self.assertEqual(kor["ywc_kor_instructor_balance"], 1100)
        self.assertEqual(world.treasury["KOR"], -100)
        self.assertEqual(world.treasury["SHU"], 100)
        self.assertEqual(len([job for job in world.jobs if job.event_id == "ywc_kor.1032"]), 1)
        self.assertTrue(any(owner == "KOR" and fields.get("name") == "ywc_v03_kor_paid_instructor_training"
                            for owner, fields in world.modifiers))
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 1)
        self.assertEqual(len([job for job in world.jobs if job.event_id == "ywc_kor.1032"]), 1)

    def test_twelve_matched_transfers_final_remainder_and_no_thirteenth(self):
        world, countries = signed_world(total=1000)
        kor = countries["KOR"]
        for month in range(12):
            if month:
                world.advance_months()
            before_kor, before_shu = world.treasury["KOR"], world.treasury["SHU"]
            world.run_country_monthly()
            self.assertEqual(world.treasury["KOR"] - before_kor,
                             -(world.treasury["SHU"] - before_shu))
            self.assertEqual(kor["ywc_kor_instructor_paid_count"], month + 1)
        self.assertAlmostEqual(kor["ywc_kor_instructor_paid_total"], 1000)
        self.assertAlmostEqual(kor["ywc_kor_instructor_balance"], 0)
        self.assertAlmostEqual(world.treasury["SHU"], 1000)
        world.advance_months()
        world.run_due_hidden()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 12)
        self.assertAlmostEqual(world.treasury["SHU"], 1000)
        self.assertFalse(world.modifiers)
        self.assertEqual(kor["ywc_kor_instructor_service_ended_generation"],
                         kor["ywc_kor_instructor_contract_generation"])

    def test_calendar_duplicates_skips_and_year_rollover(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        world.run_country_monthly()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 1)
        world.advance_months(3)
        world.run_country_monthly()
        self.assertEqual((kor["ywc_kor_instructor_due_count"], kor["ywc_kor_instructor_paid_count"]), (4, 2))
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 2)
        for _ in range(9):
            world.advance_months()
            world.run_country_monthly()
        self.assertEqual(world.date.year, 1837)
        self.assertEqual(kor["ywc_kor_instructor_due_count"], 12)
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 11)

    def test_arrears_recovery_never_extends_service(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        world.run_country_monthly()
        countries["KOR"]["gold_reserves"] = 0
        for _ in range(11):
            world.advance_months()
            world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_due_count"], 12)
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 1)
        self.assertFalse(world.modifiers)
        countries["KOR"]["gold_reserves"] = 100000
        world.advance_months()
        world.run_due_hidden()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 2)
        self.assertEqual(kor["ywc_kor_instructor_balance"], 1000)
        self.assertFalse(world.modifiers)

    def test_dead_missing_recreated_creditor_freezes_both_treasuries(self):
        for defect in ("dead", "missing", "recreated"):
            with self.subTest(defect=defect):
                world, countries = signed_world()
                world.run_country_monthly()
                old = world.country_ref("SHU")
                if defect == "dead":
                    countries["SHU"]["is_country_alive"] = False
                else:
                    world.remove_country("SHU")
                    if defect == "recreated":
                        world.add_country("SHU", copy.deepcopy(facts()))
                before = dict(world.treasury)
                world.advance_months()
                world.run_country_monthly()
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_creditor_invalid_generation"], 1)
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_paid_count"], 1)
                self.assertEqual(world.treasury["KOR"], before["KOR"])
                self.assertEqual(countries["KOR"]["ywc_kor_instructor_contract_partner"], old)
                self.assertFalse(world.modifiers)
                if defect == "recreated":
                    self.assertEqual(world.treasury["SHU"], 0)

    def test_subject_relations_provider_changes_preserve_liability(self):
        for defect in ("subject", "relations", "provider_shortage"):
            with self.subTest(defect=defect):
                world, countries = signed_world()
                world.run_country_monthly()
                if defect == "subject":
                    countries["KOR"]["is_subject"] = True
                elif defect == "relations":
                    countries["SHU"]["relations"]["KOR"] = -1
                else:
                    for building in countries["SHU"]["states"][0]["buildings"]:
                        building["shortage"] = True
                world.advance_months()
                world.run_country_monthly()
                kor = countries["KOR"]
                self.assertEqual(kor["ywc_kor_instructor_paid_count"], 2)
                self.assertEqual(kor["ywc_kor_instructor_balance"], 1000)
                self.assertFalse(world.modifiers)
                countries["KOR"]["is_subject"] = False
                countries["SHU"]["relations"]["KOR"] = 10
                for building in countries["SHU"]["states"][0]["buildings"]:
                    building["shortage"] = False
                world.advance_months()
                world.run_country_monthly()
                self.assertTrue(world.modifiers)

    def test_withdrawal_success_settlement_and_old_account_readers(self):
        for ending in ("breach", "settlement"):
            with self.subTest(ending=ending):
                world, countries = signed_world()
                world.run_country_monthly()
                kor = countries["KOR"]
                balance = kor["ywc_kor_instructor_balance"]
                if ending == "breach":
                    world.run_script("ywc_kor_instructor_withdraw_service = yes")
                    self.assertFalse(world.modifiers)
                    self.assertEqual(kor["ywc_kor_instructor_service_withdrawn_generation"], 1)
                else:
                    world.run_script("ywc_kor_release_military_accounts = yes")
                    self.assertTrue(world.modifiers)
                world.run_script("ywc_kor_school_record_old_account = yes")
                self.assertEqual(kor["ywc_kor_school_old_account_instructor_generation"], 1)
                self.assertEqual(kor["ywc_kor_school_old_account_instructor_paid_count"], 1)
                self.assertEqual(kor["ywc_kor_school_old_account_instructor_balance"], balance)
                world.advance_months()
                world.run_country_monthly()
                self.assertEqual(kor["ywc_kor_instructor_paid_count"], 2)

    def test_endpoint_before_after_refresh_and_missing_timer(self):
        for order in ("endpoint_first", "monthly_first"):
            with self.subTest(order=order):
                world, countries = signed_world()
                world.run_country_monthly()
                kor = countries["KOR"]
                kor.pop("ywc_kor_instructor_service_term_active")
                world.advance_months(12)
                if order == "endpoint_first":
                    world.run_due_hidden()
                    world.run_country_monthly()
                else:
                    world.run_country_monthly()
                    world.run_due_hidden()
                self.assertEqual(kor["ywc_kor_instructor_service_ended_generation"], 1)
                self.assertFalse(world.modifiers)
                self.assertEqual(kor["ywc_kor_instructor_paid_count"], 2)

    def test_late_final_benefit_clipped_at_exact_endpoint(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        for i in range(12):
            if i:
                world.advance_months()
            world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 12)
        self.assertTrue(world.modifiers)
        world.advance_months()
        self.assertFalse(world.modifiers)
        world.run_country_monthly()
        self.assertFalse(world.modifiers)
        world.run_due_hidden()
        self.assertEqual(kor["ywc_kor_instructor_service_ended_generation"], 1)

    def test_old_endpoint_cannot_end_renewed_contract(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        world.run_country_monthly()
        old_end = next(job for job in world.jobs if job.event_id == "ywc_kor.1032")
        for _ in range(11):
            world.advance_months()
            world.run_country_monthly()
        world.advance_months()
        world.run_due_hidden()
        self.assertEqual(kor["ywc_kor_instructor_balance"], 0)
        world.run_script("ywc_kor_instructor_send_shu = yes")
        new_offer = world.jobs[-1]
        self.assertTrue(world.display_job(new_offer))
        world.choose_job(new_offer, "accept")
        self.assertEqual(kor["ywc_kor_instructor_contract_generation"], 2)
        world.run_country_monthly()
        self.assertTrue(world.modifiers)
        world.jobs.append(replace(old_end, serial=len(world.jobs) + 1, due_day=world.day))
        world.run_due_hidden()
        self.assertTrue(world.modifiers)
        self.assertNotEqual(kor.get("ywc_kor_instructor_service_ended_generation"), 2)

    def test_missing_wrong_endpoint_context_is_inert(self):
        for defect in ("missing", "wrong_generation", "wrong_owner"):
            with self.subTest(defect=defect):
                world, countries = signed_world()
                world.run_country_monthly()
                endpoint = next(job for job in world.jobs if job.event_id == "ywc_kor.1032")
                saved = dict(endpoint.saved)
                if defect == "missing":
                    saved.pop("ywc_kor_service_end_generation")
                elif defect == "wrong_generation":
                    saved["ywc_kor_service_end_generation"] = 999
                else:
                    saved["ywc_kor_service_end_owner"] = world.country_ref("JHG")
                world.jobs.remove(endpoint)
                world.jobs.append(replace(endpoint, saved=tuple(sorted(saved.items())), due_day=world.day))
                world.run_due_hidden()
                self.assertTrue(world.modifiers)
                self.assertNotIn("ywc_kor_instructor_service_ended_generation", countries["KOR"])


if __name__ == "__main__":
    unittest.main()

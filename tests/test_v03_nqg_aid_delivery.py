"""Source-level aid-notice delivery, with distinct queue and frozen identity."""
import unittest
from dataclasses import replace

from shu_kor_strict_review_runtime import field
from test_v03_nqg_aid_response import NqgAidWorld, base_countries, install_route, send_inquiry

WINTER = "ywc_je_v03_nqg_winter_court"


def answered_world():
    countries = base_countries()
    world = NqgAidWorld(countries)
    install_route(countries, "SHU")
    offer = send_inquiry(world)
    assert world.display_job(offer)
    world.choose_job(offer, "accept")
    return world, countries


def pulse_aid_notice(world):
    state = world.countries["NQG"]
    if WINTER not in world.active["NQG"]:
        world.active["NQG"].append(WINTER)
    state["ywc_v03_nqg_inline_live_winter_court_1"] = 1
    before = len(world.jobs)
    with world._chain(world.country_ref("NQG")):
        world.execute(field(field(world.journal_defs[WINTER], "on_monthly_pulse"), "effect"), "NQG")
    return world.jobs[before:]


class NqgAidDeliveryTests(unittest.TestCase):
    def test_notice_waits_for_the_shared_major_event_cooldown(self):
        countries = base_countries(); world = NqgAidWorld(countries)
        install_route(countries, "SHU")
        world.run_script("set_variable = { name = ywc_v03_major_event_cooldown value = 1 days = 90 }", "NQG")
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertFalse([j for j in world.jobs if j.event_id == "ywc_nqg.1031"])
        self.assertEqual(countries["NQG"]["ywc_nqg_winter_aid_notice_event"], 1031)
        self.assertFalse(pulse_aid_notice(world))
        world.advance_days(90)
        jobs = pulse_aid_notice(world)
        self.assertEqual([j.event_id for j in jobs], ["ywc_nqg.1031"])
        self.assertTrue(world.display_job(jobs[0]))
        self.assertIn("ywc_v03_major_event_cooldown", countries["NQG"])

    def test_old_dispatched_notice_cannot_borrow_the_new_notice_serial(self):
        world, countries = answered_world()
        old = pulse_aid_notice(world)[-1]
        self.assertEqual(old.event_id, "ywc_nqg.1031")
        old_serial = dict(old.saved)["ywc_nqg_winter_aid_notice_serial"]
        countries["SHU"]["relations"]["NQG"] = -1
        world.run_country_monthly("NQG")
        self.assertGreater(countries["NQG"]["ywc_nqg_winter_aid_notice_serial"], old_serial)
        self.assertFalse(world.display_job(old))
        self.assertEqual(countries["NQG"]["ywc_nqg_winter_aid_notice_event"], 1031)
        world.advance_days(1)
        new = pulse_aid_notice(world)[-1]
        self.assertEqual(new.event_id, "ywc_nqg.1031")
        self.assertGreater(dict(new.saved)["ywc_nqg_winter_aid_notice_serial"], old_serial)
        self.assertTrue(world.display_job(new))
        self.assertTrue(world.job_options(new)["review_status"])
        world.choose_job(new, "review_status")
        self.assertNotIn("ywc_nqg_winter_aid_notice_open_serial", countries["NQG"])

    def test_ack_requires_actual_notice_body_and_preserves_the_normal_queue(self):
        world, countries = answered_world()
        state = countries["NQG"]
        ordinary = state["ywc_nqg_winter_pending"]
        job = pulse_aid_notice(world)[-1]
        candidate = int(dict(job.saved)["ywc_nqg_winter_aid_notice_candidate"])
        with world._chain(world.country_ref("NQG"), job.saved):
            world.run(f"ywc_v03_nqg_inline_callback_{candidate}", "NQG")
        self.assertEqual(state["ywc_nqg_winter_aid_notice_event"], 1031)
        self.assertEqual(state["ywc_nqg_winter_pending"], ordinary)
        self.assertTrue(world.display_job(job))
        self.assertNotIn("ywc_nqg_winter_aid_notice_event", state)
        self.assertEqual(state["ywc_nqg_winter_pending"], ordinary)
        world.choose_job(job, "review_status")
        self.assertNotIn("ywc_nqg_winter_aid_notice_open_serial", state)

    def test_incorrect_frozen_scope_or_epoch_fails_before_delivery(self):
        for defect in ("serial", "epoch", "partner"):
            with self.subTest(defect=defect):
                world, countries = answered_world()
                job = pulse_aid_notice(world)[-1]
                if defect == "epoch":
                    countries["NQG"]["ywc_v03_nqg_inline_reservation_epoch"] += 1
                else:
                    name = "ywc_nqg_winter_aid_notice_serial" if defect == "serial" else "ywc_nqg_winter_aid_notice_partner"
                    job = replace(job, saved=tuple((key, value) for key, value in job.saved if key != name))
                self.assertFalse(world.display_job(job))
                self.assertNotIn("ywc_nqg_winter_aid_notice_open_serial", countries["NQG"])
                self.assertEqual(countries["NQG"]["ywc_nqg_winter_aid_notice_event"], 1031)

    def test_each_winter_phase_owns_a_separate_frozen_notice_candidate(self):
        sites = (("ywc_je_v03_nqg_winter_court", "ywc_v03_nqg_inline_live_winter_court_1"),
                 ("ywc_je_v03_nqg_winter_review", "ywc_v03_nqg_inline_live_winter_court_2"),
                 ("ywc_je_v03_nqg_winter_settlement", "ywc_v03_nqg_inline_live_winter_court_3"))
        candidates = set()
        for journal, witness in sites:
            with self.subTest(journal=journal):
                world, countries = answered_world()
                world.active["NQG"].append(journal)
                countries["NQG"][witness] = 1
                with world._chain(world.country_ref("NQG")):
                    world.execute(field(field(world.journal_defs[journal], "on_monthly_pulse"), "effect"), "NQG")
                job = world.jobs[-1]
                self.assertEqual(job.event_id, "ywc_nqg.1031")
                candidates.add(dict(job.saved)["ywc_nqg_winter_aid_notice_candidate"])
                self.assertTrue(world.display_job(job))
                self.assertTrue(world.job_options(job)["sign_terms"])
        self.assertEqual(len(candidates), 3)

    def test_lost_partner_notice_is_delivered_without_forging_a_recipient(self):
        world, countries = answered_world()
        world.remove_country("SHU")
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_state"], 5)
        job = pulse_aid_notice(world)[-1]
        self.assertEqual(dict(job.saved)["ywc_nqg_winter_aid_notice_partner_available"], 0)
        self.assertTrue(world.display_job(job))
        self.assertFalse(world.job_options(job).get("sign_terms"))
        self.assertTrue(world.job_options(job)["domestic_route"])

    def test_accepted_offer_expiry_starts_only_when_the_notice_is_delivered(self):
        world, countries = answered_world()
        world.run_script("set_variable = { name = ywc_v03_major_event_cooldown value = 1 months = 4 }", "NQG")
        for _ in range(4):
            world.advance_months(1); world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_state"], 2)
        job = pulse_aid_notice(world)[-1]
        self.assertTrue(world.display_job(job))
        self.assertTrue(world.job_options(job)["sign_terms"])
        world.advance_months(3); world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_state"], 4)


if __name__ == "__main__":
    unittest.main()

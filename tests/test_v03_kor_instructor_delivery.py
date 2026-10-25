"""Source-driven KOR instructor notice delivery and immutable local choices."""
import copy
from dataclasses import replace
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field


def world_with_notice(partner="SHU"):
    countries = {tag: copy.deepcopy(facts()) for tag in ("KOR", "SHU", "JHG")}
    countries["KOR"]["ywc_kor_weekly_cost"] = 1200
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    world = PartnerWorld(countries)
    offer = next(body for key, _, body in world.event_defs["ywc_kor.1004"]
                 if key == "option" and field(body, "name").endswith(".offer_" + partner.lower()))
    world.execute([node for node in offer if node[0] not in ("name", "trigger", "ai_chance")], "KOR")
    world.display_job(world.jobs[-1])
    world.choose_job(world.jobs[-1], "accept")
    return world, countries


def pulse_military_notice(world, journal="ywc_je_v03_kor_military_audit"):
    kor = world.countries["KOR"]
    world.active["KOR"].append(journal)
    kor["ywc_v03_kor_inline_live_military_audit"] = 1
    kor["ywc_kor_audit_public"] = 1  # The preceding native 1003 audit phase.
    with world._chain(world.country_ref("KOR")):
        world.execute(field(field(world.journal_defs[journal], "on_monthly_pulse"), "effect"), "KOR")
    if world.jobs[-1].event_id == "ywc_kor.1005":
        self_job = world.jobs[-1]
        assert world.display_job(self_job)
        world.choose_job(self_job, "retain_border")
        world.advance_days(90)
        with world._chain(world.country_ref("KOR")):
            world.execute(field(field(world.journal_defs[journal], "on_monthly_pulse"), "effect"), "KOR")
    return world.jobs[-1]


def pending_delivery_world(partner="SHU"):
    world, countries = world_with_notice(partner)
    job = pulse_military_notice(world)
    assert job.event_id == "ywc_kor.1031"
    return world, countries, job


def source_notice_sender(world, journal):
    source = field(field(world.journal_defs[journal], "on_monthly_pulse"), "effect")
    sender = [node for node in source if node[0] == "if" and "ywc_kor_instructor_notice_live" in str(node)]
    assert len(sender) == 1
    with world._chain(world.country_ref("KOR")):
        world.execute(sender, "KOR")
    return world.jobs[-1]


class InstructorDeliveryTests(unittest.TestCase):
    def test_predispatch_candidate_reachable_without_event_scopes(self):
        world, countries = world_with_notice()
        kor = countries["KOR"]
        self.assertEqual(kor["ywc_kor_instructor_notice_event"], 1031)
        self.assertNotIn("ywc_kor_notice_serial", kor)
        self.assertTrue(world.check_script("ywc_v03_can_deliver_major = yes"))
        self.assertTrue(world.check_script("ywc_kor_instructor_notice_live = yes"))
        job = pulse_military_notice(world)
        self.assertEqual(job.event_id, "ywc_kor.1031", (kor, [item.event_id for item in world.jobs]))
        self.assertEqual(job.recipient, world.country_ref("KOR"))
        self.assertIn("ywc_kor_notice_serial", dict(job.saved))
        self.assertTrue(world.display_job(job))
        self.assertNotIn("ywc_kor_instructor_notice_event", kor)
        self.assertTrue(world.job_options(job)["continue_status"])
        world.choose_job(job, "continue_status")
        self.assertNotIn("ywc_kor_instructor_notice_open_serial", kor)

    def test_actual_two_sites_candidate_identity_and_normal_queue_conservation(self):
        world, countries, first = pending_delivery_world()
        kor = countries["KOR"]
        self.assertEqual(dict(first.saved)["ywc_kor_notice_candidate"], 8)
        self.assertTrue(world.display_job(first))
        self.assertEqual(kor["ywc_v03_kor_v03_kor_military_accounts_last_event"], 6)
        self.assertNotIn("ywc_kor_pending_event", kor)
        world.choose_job(first, "continue_status")
        world.active["KOR"].remove("ywc_je_v03_kor_military_audit")
        world.active["KOR"].append("ywc_je_v03_kor_service_settlement")
        kor.pop("ywc_v03_kor_inline_live_military_audit", None)
        kor["ywc_v03_kor_inline_live_service_settlement"] = 1
        world.advance_days(90)
        world.run_script("set_variable = { name = ywc_kor_instructor_notice_reason value = 5 } ywc_kor_instructor_publish_notice = yes")
        world.run_script("ywc_v03_kor_inline_prepare = yes")
        second = source_notice_sender(world, "ywc_je_v03_kor_service_settlement")
        self.assertEqual(second.event_id, "ywc_kor.1031")
        self.assertEqual(dict(second.saved)["ywc_kor_notice_candidate"], 13)
        self.assertTrue(world.display_job(second))
        self.assertEqual(kor.get("ywc_v03_kor_v03_kor_military_accounts_last_event"), 6)

    def test_absence_snapshot_delivers_domestic_menu(self):
        world, countries = world_with_notice()
        world.remove_country("SHU")
        world.run_country_monthly()
        countries["KOR"].pop("ywc_kor_pending_event", None)
        countries["KOR"].pop("ywc_kor_instructor_notice_partner", None)
        job = pulse_military_notice(world)
        self.assertEqual(job.event_id, "ywc_kor.1031")
        self.assertEqual(dict(job.saved)["ywc_kor_notice_partner_available"], 0)
        self.assertTrue(world.display_job(job))
        self.assertTrue(world.job_options(job)["narrow_orders"])
        world.choose_job(job, "narrow_orders")
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_narrowed"], 1)

    def test_capture_is_immutable_across_same_id_generation_replacement(self):
        world, countries, old = pending_delivery_world()
        old_serial = dict(old.saved)["ywc_kor_notice_serial"]
        world.run_script("set_variable = { name = ywc_kor_instructor_notice_reason value = 5 } ywc_kor_instructor_publish_notice = yes")
        self.assertGreater(countries["KOR"]["ywc_kor_instructor_notice_serial"], old_serial)
        self.assertFalse(world.display_job(old))
        self.assertEqual(dict(old.saved)["ywc_kor_notice_serial"], old_serial)
        self.assertNotIn("ywc_kor_local_translation_funded", countries["KOR"])

    def test_partial_body_wrong_epoch_and_missing_capture_cannot_ack(self):
        for defect in ("no_body", "epoch", "missing_serial"):
            with self.subTest(defect=defect):
                world, countries, job = pending_delivery_world()
                kor = countries["KOR"]
                queue = kor["ywc_kor_instructor_notice_event"]
                if defect == "epoch":
                    kor["ywc_v03_kor_inline_reservation_epoch"] += 1
                elif defect == "missing_serial":
                    job = replace(job, saved=tuple((k, v) for k, v in job.saved if k != "ywc_kor_notice_serial"))
                if defect != "no_body":
                    self.assertFalse(world.display_job(job))
                else:
                    world.run_script("ywc_v03_kor_inline_ack_8 = yes")
                self.assertEqual(kor["ywc_kor_instructor_notice_event"], queue)

    def test_chosen_option_checks_serial_generation_state_after_signature(self):
        world, countries, job = pending_delivery_world()
        self.assertTrue(world.display_job(job))
        kor = countries["KOR"]
        old_pending = kor.get("ywc_kor_pending_event")
        world.run_script("set_variable = { name = ywc_kor_instructor_notice_reason value = 5 } ywc_kor_instructor_publish_notice = yes")
        for choice in ("fund_local", "narrow_orders", "retry_shu"):
            world.choose_job(job, choice)
        self.assertNotIn("ywc_kor_local_translation_funded", kor)
        self.assertNotIn("ywc_kor_procurement_narrowed", kor)
        self.assertEqual(kor.get("ywc_kor_pending_event"), old_pending)
        self.assertEqual(kor["ywc_kor_instructor_contract_generation"], 1)

    def test_signed_status_progression_uses_new_serial(self):
        world, countries, first = pending_delivery_world()
        self.assertTrue(world.display_job(first))
        old_serial = countries["KOR"]["ywc_kor_instructor_notice_open_serial"]
        countries["KOR"]["gold_reserves"] = 0
        world.advance_days(90)
        world.run_country_monthly()
        self.assertEqual(countries["KOR"]["ywc_kor_instructor_notice_reason"], 5)
        self.assertGreater(countries["KOR"]["ywc_kor_instructor_notice_serial"], old_serial)
        world.choose_job(first, "fund_local")
        self.assertNotIn("ywc_kor_local_translation_funded", countries["KOR"])

    def test_optional_partner_identity_death_and_new_incarnation(self):
        world, countries, job = pending_delivery_world()
        self.assertTrue(world.display_job(job))
        world.remove_country("SHU")
        world.choose_job(job, "narrow_orders")
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_narrowed"], 1)
        world.add_country("SHU", copy.deepcopy(facts()))
        countries["KOR"]["ywc_kor_instructor_notice_partner"] = world.country_ref("SHU")
        world.choose_job(job, "fund_local")
        self.assertNotIn("ywc_kor_local_translation_funded", countries["KOR"])

    def test_phase_transition_and_expiry_retry_retains_notice(self):
        world, countries, job = pending_delivery_world()
        kor = countries["KOR"]
        self.assertTrue(world.display_job(job))
        world.active["KOR"].clear()
        world.choose_job(job, "continue_status")
        self.assertNotIn("ywc_kor_instructor_notice_open_serial", kor)
        world.run_script("set_variable = { name = ywc_kor_instructor_notice_reason value = 5 } ywc_kor_instructor_publish_notice = yes")
        self.assertEqual(kor["ywc_kor_instructor_notice_event"], 1031)
        self.assertEqual(kor["ywc_kor_instructor_contract_generation"], 1)

    def test_foreign_response_and_hidden_endpoint_have_no_kor_ack(self):
        world, countries = world_with_notice()
        self.assertEqual(countries["KOR"]["ywc_kor_instructor_contract_generation"], 1)
        world.run_country_monthly()
        endpoint = next(job for job in world.jobs if job.event_id == "ywc_kor.1032")
        self.assertNotIn("ywc_kor_notice_candidate", dict(endpoint.saved))
        world.advance_months(12)
        world.run_due_hidden()
        self.assertEqual(countries["KOR"]["ywc_kor_instructor_service_ended_generation"], 1)
        self.assertFalse(any(name.startswith("ywc_v03_kor_inline_callback_") for name in countries["SHU"]))


if __name__ == "__main__":
    unittest.main()

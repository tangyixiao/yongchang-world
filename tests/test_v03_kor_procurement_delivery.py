"""Source-driven KOR procurement notice delivery and immutable local choices."""
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import field

from tests.test_v03_kor_procurement_lifecycle import (
    base_countries,
    install_route,
    pulse_procurement_notice,
    send_inquiry,
    signed_world,
)
from tests.test_v03_kor_instructor_delivery import pulse_military_notice


def quoted_world(partner="SHU"):
    """Inquiry sent and foreign answer accepted: the 1034 notice is published
    but not yet delivered through the inline scheduler."""
    countries = base_countries()
    world = PartnerWorld(countries)
    install_route(countries, partner)
    send_inquiry(world, partner)
    offer = world.jobs[-1]
    assert offer.event_id == "ywc_kor.1033" and world.display_job(offer)
    world.choose_job(offer, "accept")
    return world, countries


def pending_delivery_world(partner="SHU"):
    world, countries = quoted_world(partner)
    job = pulse_procurement_notice(world)
    assert job.event_id == "ywc_kor.1034", (job.event_id, [j.event_id for j in world.jobs])
    return world, countries, job


def source_notice_sender(world, journal):
    source = field(field(world.journal_defs[journal], "on_monthly_pulse"), "effect")
    sender = [node for node in source if node[0] == "if" and "ywc_kor_procurement_notice_live" in str(node)]
    assert len(sender) == 1
    with world._chain(world.country_ref("KOR")):
        world.execute(sender, "KOR")
    return world.jobs[-1]


def rearm_delivery(world):
    """Clear the major-event delivery cooldown and advance the scheduler round
    without crossing procurement calendar months."""
    world.run_script("remove_variable = ywc_v03_major_event_cooldown "
                     "ywc_v03_kor_inline_prepare = yes")


class ProcurementDeliveryTests(unittest.TestCase):
    def test_predispatch_candidate_reachable_without_event_scopes(self):
        world, countries = quoted_world()
        kor = countries["KOR"]
        self.assertEqual(kor["ywc_kor_procurement_notice_event"], 1034)
        self.assertEqual(kor["ywc_kor_procurement_notice_serial"], 1)
        self.assertNotIn("ywc_kor_procurement_notice_open_serial", kor)
        self.assertTrue(world.check_script("ywc_v03_can_deliver_major = yes"))
        self.assertTrue(world.check_script("ywc_kor_procurement_notice_live = yes"))
        job = pulse_procurement_notice(world)
        self.assertEqual(job.event_id, "ywc_kor.1034")
        self.assertEqual(job.recipient, world.country_ref("KOR"))
        saved = dict(job.saved)
        self.assertEqual(saved["ywc_kor_procurement_notice_candidate"], 9)
        self.assertEqual(saved["ywc_kor_procurement_notice_serial"], 1)
        self.assertEqual(saved["ywc_kor_procurement_notice_partner_available"], 1)
        self.assertEqual(saved["ywc_kor_procurement_notice_partner"], world.country_ref("SHU"))
        self.assertTrue(world.display_job(job))
        self.assertNotIn("ywc_kor_procurement_notice_event", kor)
        self.assertEqual(kor["ywc_kor_procurement_notice_open_serial"], 1)
        self.assertTrue(world.job_options(job)["review_status"])
        world.choose_job(job, "review_status")
        self.assertNotIn("ywc_kor_procurement_notice_open_serial", kor)

    def test_service_settlement_site_reserves_its_own_candidate(self):
        world, countries, first = pending_delivery_world()
        kor = countries["KOR"]
        self.assertEqual(dict(first.saved)["ywc_kor_procurement_notice_candidate"], 9)
        self.assertTrue(world.display_job(first))
        world.choose_job(first, "review_status")
        world.active["KOR"].remove("ywc_je_v03_kor_military_audit")
        world.active["KOR"].append("ywc_je_v03_kor_service_settlement")
        kor.pop("ywc_v03_kor_inline_live_military_audit", None)
        kor["ywc_v03_kor_inline_live_service_settlement"] = 1
        world.run_script("set_variable = { name = ywc_kor_procurement_notice_reason value = 5 } "
                         "ywc_kor_procurement_publish_notice = yes")
        rearm_delivery(world)
        second = source_notice_sender(world, "ywc_je_v03_kor_service_settlement")
        self.assertEqual(second.event_id, "ywc_kor.1034")
        self.assertEqual(dict(second.saved)["ywc_kor_procurement_notice_candidate"], 14)
        self.assertTrue(world.display_job(second))
        # Each site's delivery carried its own frozen, immutable capture: a
        # fresh reservation epoch and the newest notice serial.
        self.assertEqual(dict(second.saved)["ywc_kor_procurement_notice_epoch"],
                         dict(first.saved)["ywc_kor_procurement_notice_epoch"] + 1)
        self.assertGreater(dict(second.saved)["ywc_kor_procurement_notice_serial"],
                           dict(first.saved)["ywc_kor_procurement_notice_serial"])

    def test_absence_snapshot_delivers_domestic_menu(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        world.remove_country("SHU")
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_creditor_invalid_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 5)
        rearm_delivery(world)
        job = pulse_procurement_notice(world)
        self.assertEqual(job.event_id, "ywc_kor.1034")
        self.assertEqual(dict(job.saved)["ywc_kor_procurement_notice_partner_available"], 0)
        self.assertTrue(world.display_job(job))
        options = world.job_options(job)
        self.assertFalse(options.get("accept_quote", False))
        self.assertTrue(options["domestic_route"])
        world.choose_job(job, "domestic_route")
        self.assertEqual(kor["ywc_kor_pending_event"], 1008)
        # The domestic continuation never touches the latched earned liability.
        self.assertEqual(kor["ywc_kor_procurement_creditor_invalid_generation"], 1)
        self.assertEqual(sum(world.treasury.values()), 0)

    def test_capture_is_immutable_across_serial_replacement(self):
        world, countries, old = pending_delivery_world()
        old_serial = dict(old.saved)["ywc_kor_procurement_notice_serial"]
        self.assertTrue(world.display_job(old))
        world.run_script("set_variable = { name = ywc_kor_procurement_notice_reason value = 5 } "
                         "ywc_kor_procurement_publish_notice = yes")
        self.assertGreater(countries["KOR"]["ywc_kor_procurement_notice_serial"], old_serial)
        self.assertFalse(world.display_job(old))
        self.assertEqual(dict(old.saved)["ywc_kor_procurement_notice_serial"], old_serial)
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_notice_open_serial"], old_serial)

    def test_wrong_epoch_missing_capture_and_reservation_cannot_ack(self):
        for defect in ("epoch", "missing_serial", "wrong_reservation"):
            with self.subTest(defect=defect):
                world, countries, job = pending_delivery_world()
                kor = countries["KOR"]
                queue = kor["ywc_kor_procurement_notice_event"]
                if defect == "epoch":
                    kor["ywc_v03_kor_inline_reservation_epoch"] += 1
                elif defect == "missing_serial":
                    job = replace_job_without(job, "ywc_kor_procurement_notice_serial")
                else:
                    kor["ywc_v03_kor_inline_reservation"] = 8
                self.assertFalse(world.display_job(job), defect)
                self.assertNotIn("ywc_kor_procurement_notice_open_serial", kor)
                self.assertNotIn("ywc_v03_kor_inline_callback_9", kor)
                self.assertEqual(kor["ywc_kor_procurement_notice_event"], queue)

    def test_stale_displayed_choices_are_guarded_after_a_serial_bump(self):
        world, countries, job = pending_delivery_world()
        self.assertTrue(world.display_job(job))
        kor = countries["KOR"]
        world.run_script("set_variable = { name = ywc_kor_procurement_notice_reason value = 5 } "
                         "ywc_kor_procurement_publish_notice = yes")
        old_pending = kor.get("ywc_kor_pending_event")
        for choice in ("accept_quote", "decline_quote", "domestic_route", "retry_shu"):
            world.choose_job(job, choice)
        self.assertNotIn("ywc_kor_procurement_contract_generation", kor)
        self.assertNotIn("ywc_kor_procurement_narrowed", kor)
        self.assertEqual(kor.get("ywc_kor_pending_event"), old_pending)
        self.assertEqual(kor["ywc_kor_procurement_state"], 2)
        self.assertEqual(sum(world.treasury.values()), 0)

    def test_shu_jhg_shu_switch_never_replays_an_old_quote_or_notice(self):
        countries = base_countries()
        world = PartnerWorld(countries)
        install_route(countries, "SHU")
        send_inquiry(world, "SHU")
        first_quote = world.jobs[-1]
        self.assertTrue(world.display_job(first_quote))
        world.choose_job(first_quote, "accept")
        first_notice = pulse_procurement_notice(world)
        self.assertEqual(dict(first_notice.saved)["ywc_kor_procurement_notice_generation"], 1)
        self.assertTrue(world.display_job(first_notice))
        # Side-switch: decline, re-inquire with JHG, accept. Declining books
        # the domestic continuation event; the delivery fixture clears that
        # marker so the scheduler can dispatch the next generation's notice.
        world.choose_job(first_notice, "decline_quote")
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_state"], 7)
        countries["KOR"].pop("ywc_kor_pending_event", None)
        install_route(countries, "JHG")
        send_inquiry(world, "JHG")
        second_quote = world.jobs[-1]
        self.assertTrue(world.display_job(second_quote))
        world.choose_job(second_quote, "accept")
        rearm_delivery(world)
        second_notice = pulse_procurement_notice(world)
        self.assertEqual(second_notice.event_id, "ywc_kor.1034")
        self.assertEqual(dict(second_notice.saved)["ywc_kor_procurement_notice_generation"], 2)
        self.assertTrue(world.display_job(second_notice))
        # And back to SHU: a third generation owns the current terms.
        world.choose_job(second_notice, "decline_quote")
        countries["KOR"].pop("ywc_kor_pending_event", None)
        install_route(countries, "SHU")
        send_inquiry(world, "SHU")
        third_quote = world.jobs[-1]
        generations = [dict(job.saved)["ywc_kor_procurement_request_generation"]
                       for job in (first_quote, second_quote, third_quote)]
        self.assertEqual(generations, [1, 2, 3])
        self.assertTrue(world.display_job(third_quote))
        # Every superseded chain is inert: the first SHU quote can never
        # authorize against the third generation, and the stale notice
        # snapshots cannot sign or cancel anything.
        world.choose_job(first_quote, "accept")
        self.assertNotIn("ywc_kor_procurement_quote_generation", countries["KOR"])
        world.choose_job(first_notice, "accept_quote")
        self.assertNotIn("ywc_kor_procurement_contract_generation", countries["KOR"])
        world.choose_job(second_notice, "decline_quote")
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_state"], 1)
        world.choose_job(third_quote, "accept")
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_quote_generation"], 3)

    def test_instructor_and_procurement_queues_notices_and_debts_independent(self):
        countries = base_countries()
        world = PartnerWorld(countries)
        install_route(countries, "SHU")
        # Instructor contract on the same world.
        offer = next(body for key, _, body in world.event_defs["ywc_kor.1004"]
                     if key == "option" and field(body, "name").endswith(".offer_shu"))
        world.execute([node for node in offer if node[0] not in ("name", "trigger", "ai_chance")], "KOR")
        instructor_job = world.jobs[-1]
        self.assertTrue(world.display_job(instructor_job))
        world.choose_job(instructor_job, "accept")
        # Procurement inquiry on the same world.
        send_inquiry(world, "SHU")
        quote = world.jobs[-1]
        self.assertTrue(world.display_job(quote))
        world.choose_job(quote, "accept")
        kor = countries["KOR"]
        self.assertEqual(kor["ywc_kor_instructor_contract_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_generation"], 1)
        # The shared military pulse dispatches the instructor notice first
        # (its helper also runs the native 1005 intro phase out of the way).
        job = pulse_military_notice(world)
        self.assertEqual(job.event_id, "ywc_kor.1031")
        self.assertTrue(world.display_job(job))
        world.choose_job(job, "continue_status")
        self.assertNotIn("ywc_kor_instructor_notice_event", kor)
        self.assertEqual(kor["ywc_kor_procurement_notice_event"], 1034)
        rearm_delivery(world)
        second = pulse_procurement_notice(world)
        self.assertEqual(second.event_id, "ywc_kor.1034")
        self.assertTrue(world.display_job(second))
        world.choose_job(second, "accept_quote")
        self.assertEqual(kor["ywc_kor_procurement_contract_generation"], 1)
        # One country-monthly settles both ledgers independently.
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_instructor_paid_count"], 1)
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 1)
        self.assertAlmostEqual(kor["ywc_kor_instructor_balance"], 1100)
        self.assertAlmostEqual(kor["ywc_kor_procurement_paid_total"], 400)
        self.assertAlmostEqual(world.treasury["KOR"], -500)
        self.assertAlmostEqual(world.treasury["SHU"], 500)
        # The two notice queues never cross-write each other's names: the
        # instructor's last notice keeps its own serial and reason while the
        # procurement signature published its own.
        self.assertNotIn("ywc_kor_instructor_notice_event", kor)
        self.assertEqual(kor["ywc_kor_instructor_notice_reason"], 1)
        self.assertEqual(kor["ywc_kor_instructor_notice_serial"], 1)
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 7)
        self.assertEqual(kor["ywc_kor_procurement_notice_serial"], 2)

    def test_foreign_response_and_hidden_endpoint_have_no_kor_ack(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        endpoint = next(job for job in world.jobs if job.event_id == "ywc_kor.1035")
        saved = dict(endpoint.saved)
        self.assertEqual(saved["ywc_kor_procurement_end_generation"], 1)
        self.assertEqual(saved["ywc_kor_procurement_end_owner"], world.country_ref("KOR"))
        world.advance_months(3)
        world.run_due_hidden()
        self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
        self.assertFalse(any(name.startswith("ywc_v03_kor_inline_callback_") for name in kor))
        self.assertFalse(any(name.startswith("ywc_v03_kor_inline_callback_") for name in countries["SHU"]))

    def test_domestic_route_choice_retains_signed_liability(self):
        world, countries = signed_world()
        world.run_country_monthly()
        kor = countries["KOR"]
        earned = kor["ywc_kor_procurement_earned_total"]
        rearm_delivery(world)
        job = pulse_procurement_notice(world)
        self.assertEqual(job.event_id, "ywc_kor.1034")
        self.assertTrue(world.display_job(job))
        world.choose_job(job, "domestic_route")
        self.assertEqual(kor["ywc_kor_pending_event"], 1008)
        self.assertAlmostEqual(kor["ywc_kor_procurement_earned_total"], earned)
        self.assertAlmostEqual(kor["ywc_kor_procurement_paid_total"], earned)
        self.assertAlmostEqual(world.treasury["SHU"], earned)
        # The domestic invoice review stays executable at its existing cost.
        countries["KOR"]["gold_reserves"] = 100000
        world.run_script("ywc_kor_pay_invoice_once = yes")
        self.assertEqual(countries["KOR"]["ywc_kor_invoice_review_paid"], 1)


def replace_job_without(job, key):
    from dataclasses import replace
    return replace(job, saved=tuple((k, v) for k, v in job.saved if k != key))


if __name__ == "__main__":
    unittest.main()

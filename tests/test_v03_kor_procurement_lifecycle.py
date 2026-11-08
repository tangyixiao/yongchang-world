"""Execution of the authored KOR procurement signature, monthly ledger and endpoint."""
import copy
from dataclasses import replace
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field


def arms_facts():
    data = copy.deepcopy(facts())
    data["states"][0]["buildings"] = [b for b in data["states"][0]["buildings"]
                                      if b["type"] != "building_arms_industry"]
    data["states"][0]["buildings"].append(
        {"type": "building_arms_industry", "occupancy": 1, "shortage": False, "groups": []})
    return data


def base_countries(total=1200):
    countries = {tag: arms_facts() for tag in ("KOR", "SHU", "JHG")}
    countries["KOR"]["ywc_kor_weekly_cost"] = total
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    for tag in ("SHU", "JHG"):
        countries[tag]["states"][0]["port"] = True
    return countries


def arm_supply_route(countries):
    """Certifiable route readiness for full-success outcomes. Set only after
    the JE pulse ran: the fixture skips the JE's own supply ledger, and the
    procurement installments must stay the only treasury movers here. The
    limited route (3) executes with the fixture's staffed supplied barracks."""
    countries["KOR"]["ywc_kor_supply_route"] = 3


def install_route(countries, source_tag="SHU", value=8.0):
    source = countries[source_tag]["states"][0]
    dest = countries["KOR"]["states"][0]
    source["production"] = {"small_arms": 40.0}
    source["exports"] = [{"target": dest["_sid"], "goods": "small_arms", "value": value}]
    dest["imports"] = [{"source": source["_sid"], "goods": "small_arms", "value": value}]


def pulse_procurement_notice(world, journal="ywc_je_v03_kor_military_audit"):
    kor = world.countries["KOR"]
    if journal not in world.active["KOR"]:
        world.active["KOR"].append(journal)
    kor["ywc_v03_kor_inline_live_military_audit"] = 1
    kor["ywc_kor_audit_public"] = 1  # The preceding native 1003 audit phase.
    with world._chain(world.country_ref("KOR")):
        world.execute(field(field(world.journal_defs[journal], "on_monthly_pulse"), "effect"), "KOR")
    return world.jobs[-1]


def signed_world(partner="SHU", total=1200):
    countries = base_countries(total)
    world = PartnerWorld(countries)
    install_route(countries, partner)
    event = world.event_defs["ywc_kor.1007"]
    choice = next(body for key, _, body in event if key == "option"
                  and field(body, "name").endswith(".quote_" + partner.lower()))
    world.execute([node for node in choice if node[0] not in ("name", "trigger", "ai_chance")], "KOR")
    offer = world.jobs[-1]
    assert offer.event_id == "ywc_kor.1033" and world.display_job(offer)
    world.choose_job(offer, "accept")
    notice = pulse_procurement_notice(world)
    assert notice.event_id == "ywc_kor.1034", (notice.event_id, [j.event_id for j in world.jobs])
    assert world.display_job(notice)
    world.choose_job(notice, "accept_quote")
    return world, countries


def send_inquiry(world, partner="SHU"):
    event = world.event_defs["ywc_kor.1007"]
    choice = next(body for key, _, body in event if key == "option"
                  and field(body, "name").endswith(".quote_" + partner.lower()))
    world.execute([node for node in choice if node[0] not in ("name", "trigger", "ai_chance")], "KOR")


class ProcurementLifecycleTests(unittest.TestCase):
    def test_signature_captures_exact_route_objects_and_schedules_endpoint(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        self.assertEqual(kor["ywc_kor_procurement_state"], 6)
        self.assertEqual(kor["ywc_kor_procurement_contract_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_contract_total"], 1200)
        self.assertEqual(kor["ywc_kor_procurement_contract_partner"], world.country_ref("SHU"))
        self.assertEqual(kor["ywc_kor_procurement_source_state"].sid,
                         countries["SHU"]["states"][0]["_sid"])
        self.assertEqual(kor["ywc_kor_procurement_dest_state"].sid,
                         countries["KOR"]["states"][0]["_sid"])
        self.assertNotEqual(kor["ywc_kor_procurement_source_market"],
                            kor["ywc_kor_procurement_dest_market"])
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 0)
        self.assertEqual(kor["ywc_kor_procurement_paid_total"], 0)
        endpoint = [job for job in world.jobs if job.event_id == "ywc_kor.1035"]
        self.assertEqual(len(endpoint), 1)
        self.assertEqual(dict(endpoint[0].saved)["ywc_kor_procurement_end_generation"], 1)
        self.assertEqual(dict(endpoint[0].saved)["ywc_kor_procurement_end_owner"],
                         world.country_ref("KOR"))
        self.assertEqual(endpoint[0].recipient, world.country_ref("KOR"))
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 7)
        self.assertEqual(sum(world.treasury.values()), 0)

    def test_signature_requires_actual_current_bilateral_flow(self):
        for defect in ("third_country_only", "wrong_good", "reverse_flow", "no_receipt",
                       "production_without_imports", "same_market"):
            with self.subTest(defect=defect):
                countries = base_countries()
                world = PartnerWorld(countries)
                if defect == "third_country_only":
                    install_route(countries, "JHG")
                elif defect == "wrong_good":
                    install_route(countries, "SHU")
                    countries["SHU"]["states"][0]["exports"][0]["goods"] = "artillery"
                    countries["KOR"]["states"][0]["imports"][0]["goods"] = "artillery"
                elif defect == "reverse_flow":
                    install_route(countries, "SHU")
                    kor_state = countries["KOR"]["states"][0]
                    shu_state = countries["SHU"]["states"][0]
                    shu_state["production"] = {}
                    shu_state["exports"] = []
                    shu_state["imports"] = [{"source": kor_state["_sid"], "goods": "small_arms", "value": 8}]
                    kor_state["production"] = {"small_arms": 40}
                    kor_state["exports"] = [{"target": shu_state["_sid"], "goods": "small_arms", "value": 8}]
                    kor_state["imports"] = []
                elif defect == "no_receipt":
                    install_route(countries, "SHU")
                    countries["KOR"]["states"][0]["imports"] = []
                elif defect == "production_without_imports":
                    install_route(countries, "SHU")
                    countries["KOR"]["states"][0]["imports"] = []
                    countries["SHU"]["states"][0]["exports"] = []
                else:
                    # A shared market is no foreign procurement at all: the
                    # inquiry itself is ineligible, exactly as the protocol
                    # module requires for live eligibility.
                    install_route(countries, "SHU")
                    countries["SHU"]["market"] = "m_KOR"
                send_inquiry(world, "SHU")
                if defect == "same_market":
                    self.assertFalse(world.jobs)
                    self.assertNotIn("ywc_kor_procurement_generation", countries["KOR"])
                    continue
                offer = world.jobs[-1]
                self.assertTrue(world.display_job(offer))
                world.choose_job(offer, "accept")
                notice = pulse_procurement_notice(world)
                self.assertTrue(world.display_job(notice))
                options = world.job_options(notice)
                self.assertFalse(options.get("accept_quote", False), defect)
                world.choose_job(notice, "accept_quote")
                self.assertNotIn("ywc_kor_procurement_contract_generation", countries["KOR"])
                self.assertEqual(sum(world.treasury.values()), 0)

    def test_provider_ownership_of_shared_market_never_satisfies_the_flow(self):
        countries = base_countries()
        world = PartnerWorld(countries)
        install_route(countries, "JHG")
        countries["SHU"]["market"] = "m_JHG"
        send_inquiry(world, "SHU")
        offer = world.jobs[-1]
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        notice = pulse_procurement_notice(world)
        self.assertTrue(world.display_job(notice))
        self.assertFalse(world.job_options(notice).get("accept_quote", False))
        world.choose_job(notice, "accept_quote")
        self.assertNotIn("ywc_kor_procurement_contract_generation", countries["KOR"])

    def test_three_inspections_pay_exact_installments_and_never_a_fourth(self):
        world, countries = signed_world(total=1000)
        arm_supply_route(countries)
        kor = countries["KOR"]
        for month in range(3):
            if month:
                world.advance_months()
            before_kor, before_shu = world.treasury["KOR"], world.treasury["SHU"]
            world.run_country_monthly()
            self.assertAlmostEqual(world.treasury["KOR"] - before_kor,
                                   -(world.treasury["SHU"] - before_shu))
            self.assertEqual(kor["ywc_kor_procurement_earned_count"], month + 1)
            self.assertEqual(kor["ywc_kor_procurement_paid_count"], month + 1)
        self.assertAlmostEqual(kor["ywc_kor_procurement_earned_total"], 1000)
        self.assertAlmostEqual(kor["ywc_kor_procurement_paid_total"], 1000)
        self.assertAlmostEqual(world.treasury["SHU"], 1000)
        world.advance_months()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 3)
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 3)
        self.assertAlmostEqual(world.treasury["SHU"], 1000)
        self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_success"], 1)
        self.assertEqual(kor["ywc_kor_pending_event"], 1008)

    def test_calendar_duplicate_guard_and_year_rollover(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        world.run_country_monthly()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 1)
        self.assertEqual(kor["ywc_kor_procurement_last_processed_calendar_month"],
                         world.date.year * 12 + world.date.month - 1)
        # Thirteen months later the window has long ended: the one honest
        # terminator closes it and evaluates the partial outcome.
        world.advance_months(13)
        self.assertEqual(world.date.year, 1837)
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 1)
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 1)
        self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_partial"], 1)
        self.assertNotIn("ywc_kor_procurement_success", kor)

    def test_underfunded_month_earns_invoice_but_pays_only_after_recovery(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        countries["KOR"]["gold_reserves"] = 0
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 1)
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 0)
        self.assertAlmostEqual(world.treasury["KOR"], 0)
        self.assertAlmostEqual(world.treasury["SHU"], 0)
        # Recovery inside the window pays the earned installments.
        world.advance_months()
        countries["KOR"]["gold_reserves"] = 500
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 1)
        self.assertAlmostEqual(world.treasury["KOR"], -400)
        self.assertAlmostEqual(world.treasury["SHU"], 400)
        # Broke again: the third installment is earned but never paid in-window.
        world.advance_months()
        countries["KOR"]["gold_reserves"] = 0
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 3)
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 1)
        # The window closes at the first monthly past the third opportunity.
        world.advance_months()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_partial"], 1)
        self.assertEqual(countries["KOR"]["ywc_kor_scope_narrowed"], 1)
        # Arrears remain collectible after the window closes.
        countries["KOR"]["gold_reserves"] = 100000
        world.advance_months()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 2)
        self.assertAlmostEqual(world.treasury["SHU"], 800)

    def test_flow_loss_suspends_accrual_and_recovery_resumes_inside_window(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 1)
        old_serial = kor["ywc_kor_procurement_notice_serial"]
        countries["KOR"]["states"][0]["imports"] = []
        world.advance_months()
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 1)
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 5)
        self.assertGreater(kor["ywc_kor_procurement_notice_serial"], old_serial)
        self.assertFalse(world.modifiers)
        world.advance_months()
        countries["KOR"]["states"][0]["imports"] = [
            {"source": countries["SHU"]["states"][0]["_sid"], "goods": "small_arms", "value": 8}]
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 6)
        self.assertEqual(kor["ywc_kor_procurement_earned_count"], 2)
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 2)

    def test_state_conquest_and_market_change_suspend_the_signed_route(self):
        for defect in ("conquest", "market_owner_replaced", "production_lost"):
            with self.subTest(defect=defect):
                world, countries = signed_world()
                kor = countries["KOR"]
                world.run_country_monthly()
                if defect == "conquest":
                    countries["SHU"]["states"][0]["owner"] = "JHG"
                elif defect == "market_owner_replaced":
                    countries["SHU"]["states"][0]["market"] = "m_new"
                else:
                    countries["SHU"]["states"][0]["production"] = {}
                world.advance_months()
                world.run_country_monthly()
                self.assertEqual(kor["ywc_kor_procurement_earned_count"], 1)
                self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 5)
                # Earned debt is retained; recovery only to the original objects.
                self.assertAlmostEqual(kor["ywc_kor_procurement_earned_total"], 400)

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
                        world.add_country("SHU", arms_facts())
                before = dict(world.treasury)
                world.advance_months()
                world.run_country_monthly()
                kor = countries["KOR"]
                self.assertEqual(kor["ywc_kor_procurement_creditor_invalid_generation"], 1)
                self.assertEqual(kor["ywc_kor_procurement_paid_count"], 1)
                self.assertAlmostEqual(world.treasury["KOR"], before["KOR"])
                self.assertEqual(kor["ywc_kor_procurement_contract_partner"], old)
                if defect == "dead":
                    # The already credited creditor balance is retained.
                    self.assertAlmostEqual(world.treasury["SHU"], 400)
                elif defect == "recreated":
                    self.assertEqual(world.treasury["SHU"], 0)

    def test_endpoint_orders_and_wrong_contexts(self):
        for case in ("endpoint_first", "monthly_first", "missing", "wrong_generation", "wrong_owner"):
            with self.subTest(case=case):
                world, countries = signed_world()
                arm_supply_route(countries)
                world.run_country_monthly()
                world.advance_months()
                world.run_country_monthly()
                world.advance_months()
                world.run_country_monthly()
                kor = countries["KOR"]
                self.assertEqual(kor["ywc_kor_procurement_paid_count"], 3)
                endpoint = next(job for job in world.jobs if job.event_id == "ywc_kor.1035")
                saved = dict(endpoint.saved)
                if case == "missing":
                    saved.pop("ywc_kor_procurement_end_generation")
                elif case == "wrong_generation":
                    saved["ywc_kor_procurement_end_generation"] = 999
                elif case == "wrong_owner":
                    saved["ywc_kor_procurement_end_owner"] = world.country_ref("JHG")
                world.jobs.remove(endpoint)
                endpoint = replace(endpoint, saved=tuple(sorted(saved.items())), due_day=world.day)
                world.jobs.append(endpoint)
                world.advance_months()
                if case == "monthly_first":
                    world.run_country_monthly()
                    world.run_due_hidden()
                else:
                    world.run_due_hidden()
                    if case in ("missing", "wrong_generation", "wrong_owner"):
                        # A wrong endpoint context ends nothing.
                        self.assertNotIn("ywc_kor_procurement_window_ended_generation", kor)
                    world.run_country_monthly()
                # The monthly window close is the honest terminator in every
                # ordering; the endpoint never writes outcomes itself.
                self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
                self.assertEqual(kor["ywc_kor_procurement_success"], 1)
                self.assertEqual(kor["ywc_kor_procurement_paid_count"], 3)
                self.assertEqual(len([job for job in world.jobs if job.event_id == "ywc_kor.1035"]), 1)

    def test_zero_paid_window_suspends_with_domestic_continuation(self):
        world, countries = signed_world()
        kor = countries["KOR"]
        countries["SHU"]["states"][0]["production"] = {}
        for _ in range(4):
            world.advance_months()
            world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_paid_count"], 0)
        self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_suspended"], 1)
        self.assertNotIn("ywc_kor_procurement_success", kor)
        self.assertEqual(kor["ywc_kor_pending_event"], 1008)
        # The domestic routes remain executable at their existing costs.
        countries["KOR"]["gold_reserves"] = 100000
        world.run_script("ywc_kor_pay_invoice_once = yes")
        self.assertEqual(countries["KOR"]["ywc_kor_invoice_review_paid"], 1)

    def test_signed_debt_survives_military_settlement(self):
        world, countries = signed_world()
        world.run_country_monthly()
        kor = countries["KOR"]
        earned = kor["ywc_kor_procurement_earned_total"]
        # Consume the open signature notice before settling, so nothing can
        # republish one afterwards. The first delivery set the major-event
        # cooldown; the test clears that delivery fixture (advancing days
        # would cross procurement calendar months) and re-arms the scheduler.
        world.run_script("remove_variable = ywc_v03_major_event_cooldown "
                         "ywc_v03_kor_inline_prepare = yes")
        notice = pulse_procurement_notice(world)
        self.assertEqual(notice.event_id, "ywc_kor.1034")
        self.assertTrue(world.display_job(notice))
        world.choose_job(notice, "review_status")
        self.assertNotIn("ywc_kor_procurement_notice_event", kor)
        # The release effect decrements the shared arc bookkeeping that the
        # JE's own claim step initializes in real play.
        world.run_script("set_variable = { name = ywc_v03_kor_v03_kor_military_accounts_started value = 1 } "
                         "set_variable = { name = ywc_v03_kor_v03_kor_military_accounts_outcome value = 1 } "
                         "set_variable = { name = ywc_v03_active_arc_count value = 1 } "
                         "set_variable = { name = ywc_v03_visible_task_count value = 1 } "
                         "ywc_kor_release_military_accounts = yes")
        self.assertEqual(kor["ywc_v03_kor_v03_kor_military_accounts_settled"], 1)
        world.advance_months()
        world.run_country_monthly()
        # Settlement stops new accrual and notices but never deletes earned
        # procurement debt; the credited creditor balance is retained.
        self.assertEqual(kor["ywc_kor_procurement_earned_total"], earned)
        self.assertAlmostEqual(world.treasury["SHU"], 400)
        self.assertNotIn("ywc_kor_procurement_notice_event", kor)
        self.assertNotIn("ywc_kor_procurement_notice_open_serial", kor)

    def test_renewal_requires_settled_ended_contract(self):
        world, countries = signed_world()
        arm_supply_route(countries)
        kor = countries["KOR"]
        world.run_country_monthly()
        for _ in range(3):
            world.advance_months()
            world.run_country_monthly()
        self.assertAlmostEqual(kor["ywc_kor_procurement_paid_total"], 1200)
        self.assertEqual(kor["ywc_kor_procurement_window_ended_generation"], 1)
        old_endpoint = [job for job in world.jobs if job.event_id == "ywc_kor.1035"]
        self.assertEqual(len(old_endpoint), 1)
        world.run_script("ywc_kor_procurement_send_shu = yes")
        offer = world.jobs[-1]
        self.assertEqual(dict(offer.saved)["ywc_kor_procurement_request_generation"], 2)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(kor["ywc_kor_procurement_quote_generation"], 2)
        # The old generation's endpoint can never end the renewed contract.
        world.advance_months(3)
        world.run_due_hidden()
        self.assertEqual(kor["ywc_kor_procurement_contract_generation"], 1)
        self.assertNotEqual(kor.get("ywc_kor_procurement_window_ended_generation"), 2)


if __name__ == "__main__":
    unittest.main()

"""JHG tribute project-sharing: actual SHU response and two-sided cost.

These tests interpret the authored scripts and model country facts; they do not
assert that the Victoria 3 engine or its UI has been run.
"""
import copy
import json
import unittest
from pathlib import Path

from shu_kor_strict_review_runtime import field
from test_v03_jhg_escort_response import JhgWorld, base_countries, option_body


def share_countries():
    countries = base_countries()
    countries["SHU"] = copy.deepcopy(countries["LAN"])
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    countries["JHG"].update({"is_subject": True, "overlord": "SHU",
                             "ywc_jhg_tribute_filing_fee": 600,
                             "ywc_jhg_tribute_filing_fee_paid": 1,
                             "ywc_jhg_tribute_route": 0})
    return countries


class JhgShareWorld(JhgWorld):
    def condition(self, node, tag):
        key, op, value = node
        if key == "government_legitimacy":
            return self.compare(self.countries[tag]["legitimacy"], op, float(value))
        if key == "any_country" and self.countries[tag].get("test_no_allies"):
            return False
        return super().condition(node, tag)


def select_option(world, event_id, key):
    option = option_body(world, event_id, key)
    world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")


class JhgShareResponseTests(unittest.TestCase):
    def make_offer(self, countries=None):
        countries = countries or share_countries()
        world = JhgShareWorld(countries)
        select_option(world, "ywc_jhg.1020", "project_share")
        offer = world.jobs[-1]
        self.assertEqual((offer.event_id, offer.recipient.tag), ("ywc_jhg.1026", "SHU"))
        self.assertTrue(world.display_job(offer))
        return world, countries, offer

    def test_generic_ally_cannot_satisfy_project_sharing_without_a_real_answer(self):
        from test_v03_jhg_foundation import EFFECTS_PATH, JhgTerminalWorld
        state = {"ywc_jhg_tribute_route": 2, "engine_is_subject": True,
                 "engine_partners": [{"diplomatic_pacts": ["alliance"],
                                      "relations_to_root": 60, "gold_reserves": 10000}]}
        world = JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"), {"JHG": state})
        self.assertFalse(world.conditions(world.triggers["ywc_jhg_tribute_route_two_ready"], "JHG"))
        self.assertFalse(world.conditions(world.triggers["ywc_jhg_tribute_limited_route_execution_ready"], "JHG"))

    def test_project_offer_requires_shu_reply_and_real_both_sides_payment(self):
        countries = share_countries()
        world = JhgShareWorld(countries)
        select_option(world, "ywc_jhg.1020", "project_share")
        self.assertEqual(world.jobs[-1].event_id, "ywc_jhg.1026")
        offer = world.jobs[-1]
        self.assertEqual(offer.recipient.tag, "SHU")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_tribute_route_two_ready"], "JHG"))
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(world.treasury["JHG"], -600)
        self.assertEqual(world.treasury["SHU"], -600)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_tribute_route_two_ready"], "JHG"))
        world.choose_job(offer, "accept")
        world.run_country_monthly("JHG")
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-600, -600))

    def test_refusal_leaves_domestic_choices_and_does_not_charge_project(self):
        countries = share_countries()
        world = JhgShareWorld(countries)
        select_option(world, "ywc_jhg.1020", "project_share")
        offer = world.jobs[-1]
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))
        for key in ("fixed_share", "ambiguity"):
            option = option_body(world, "ywc_jhg.1022", key)
            self.assertTrue(world.conditions(field(option, "trigger"), "JHG"), key)

    def test_both_budgets_must_be_able_to_pay_before_either_is_debited(self):
        for broke in ("JHG", "SHU"):
            with self.subTest(broke=broke):
                world, countries, offer = self.make_offer()
                countries[broke]["gold_reserves"] = 0
                world.choose_job(offer, "accept")
                self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))
                self.assertNotIn("ywc_jhg_share_contract_generation", countries["JHG"])
                self.assertEqual(countries["JHG"]["ywc_jhg_share_state"], 2)
                countries[broke]["gold_reserves"] = 1000
                world.run_country_monthly("JHG")
                self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-600, -600))
                self.assertEqual(countries["JHG"]["ywc_jhg_share_contract_generation"], 1)

    def test_stale_terms_and_replaced_offer_cannot_pay_or_advance(self):
        for changed in ("ywc_jhg_share_quote_jhg_cost", "ywc_jhg_share_quote_shu_cost",
                        "ywc_jhg_share_quote_term", "ywc_jhg_share_quote_serial"):
            with self.subTest(changed=changed):
                world, countries, offer = self.make_offer()
                countries["JHG"][changed] += 1
                self.assertFalse(world.job_options(offer)["accept"])
                world.choose_job(offer, "accept")
                self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))
                self.assertNotIn("ywc_jhg_share_contract_generation", countries["JHG"])
        world, countries, first = self.make_offer()
        world.choose_job(first, "refuse")
        select_option(world, "ywc_jhg.1022", "request_shu")
        second = world.jobs[-1]
        self.assertTrue(world.display_job(second))
        world.choose_job(first, "accept")
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))
        world.choose_job(second, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_share_contract_generation"], 2)
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-600, -600))

    def test_subject_loss_or_partner_replacement_invalidates_unsigned_offer(self):
        for mode in ("independent", "different_overlord", "reincarnated_shu"):
            with self.subTest(mode=mode):
                world, countries, offer = self.make_offer()
                if mode == "independent":
                    countries["JHG"]["is_subject"] = False
                elif mode == "different_overlord":
                    countries["JHG"]["overlord"] = "DMG"
                else:
                    replacement = copy.deepcopy(countries["SHU"])
                    world.remove_country("SHU")
                    world.add_country("SHU", replacement)
                world.run_country_monthly("JHG")
                self.assertEqual(countries["JHG"]["ywc_jhg_share_state"], 7)
                world.choose_job(offer, "accept")
                self.assertNotIn("ywc_jhg_share_contract_generation", countries["JHG"])
                self.assertEqual(world.treasury["JHG"], 0)

    def test_independence_callback_invalidates_an_unsigned_offer_before_status_reverts(self):
        world, countries, offer = self.make_offer()
        countries["JHG"]["is_subject"] = False
        world.run_on_action("on_become_independent", "JHG")
        countries["JHG"]["is_subject"] = True
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_jhg_share_contract_generation", countries["JHG"])
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))

    def test_independence_callback_keeps_a_signed_project_and_both_paid_costs(self):
        world, countries, offer = self.make_offer()
        world.choose_job(offer, "accept")
        countries["JHG"]["is_subject"] = False
        world.run_on_action("on_become_independent", "JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_share_contract_generation"], 1)
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-600, -600))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_share_contract_active"], "JHG"))

    def test_a_stale_maturity_marker_cannot_bypass_the_settlement_stage(self):
        countries = share_countries()
        world = JhgShareWorld(countries)
        state = countries["JHG"]
        state.update({"ywc_jhg_v03_jhg_tribute_autonomy_started": 1,
                      "ywc_jhg_tribute_route": 3,
                      "ywc_jhg_tribute_six_months_complete": 1,
                      "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1})
        for key in ("settle_full", "settle_partial"):
            option = option_body(world, "ywc_jhg.1025", key)
            self.assertFalse(world.conditions(field(option, "trigger"), "JHG"))
            select_option(world, "ywc_jhg.1025", key)
            self.assertNotIn("ywc_jhg_v03_jhg_tribute_autonomy_settled", state)
        self.assertEqual(state["ywc_v03_active_arc_count"], 1)

    def test_refusal_and_accepted_but_unpaid_can_switch_without_late_payment(self):
        for answer in ("refuse", "accept"):
            for fallback, route in (("fixed_share", 1), ("ambiguity", 3)):
                with self.subTest(answer=answer, fallback=fallback):
                    world, countries, offer = self.make_offer()
                    if answer == "accept":
                        countries["SHU"]["gold_reserves"] = 0
                    world.choose_job(offer, answer)
                    select_option(world, "ywc_jhg.1022", fallback)
                    self.assertEqual(countries["JHG"]["ywc_jhg_tribute_route"], route)
                    self.assertEqual(countries["JHG"]["ywc_jhg_tribute_pending_event"], 1023)
                    countries["SHU"]["gold_reserves"] = 1000
                    world.run_country_monthly("JHG")
                    world.choose_job(offer, "accept")
                    self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))
                    self.assertNotIn("ywc_jhg_share_contract_generation", countries["JHG"])

    def test_signed_costs_survive_subject_loss_and_expire_without_double_debit(self):
        world, countries, offer = self.make_offer()
        world.choose_job(offer, "accept")
        countries["JHG"]["is_subject"] = False
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_share_suspended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_share_contract_active"], "JHG"))
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-600, -600))
        select_option(world, "ywc_jhg.1022", "fixed_share")
        world.advance_months(120)
        world.run_country_monthly("JHG")
        world.run_due_hidden()
        self.assertEqual(countries["JHG"]["ywc_jhg_share_ended_generation"], 1)
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-600, -600))

    def test_live_or_suspended_contract_blocks_replacement_until_expiry(self):
        world, countries, offer = self.make_offer()
        world.choose_job(offer, "accept")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_share_can_offer"], "JHG"))
        countries["SHU"]["relations"]["JHG"] = -1
        world.run_country_monthly("JHG")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_share_can_offer"], "JHG"))
        countries["SHU"]["relations"]["JHG"] = 10
        world.advance_months(120)
        world.run_country_monthly("JHG")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_share_can_offer"], "JHG"))
        select_option(world, "ywc_jhg.1022", "request_shu")
        second = world.jobs[-1]
        self.assertTrue(world.display_job(second))
        world.choose_job(second, "accept")
        world.run_due_hidden()
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_share_contract_active"], "JHG"))
        self.assertEqual(countries["JHG"]["ywc_jhg_share_contract_generation"], 2)
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-1200, -1200))

    def test_expired_offer_never_funds_the_project(self):
        world, countries, offer = self.make_offer()
        world.advance_months(4)
        world.run_country_monthly("JHG")
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_jhg_share_contract_generation", countries["JHG"])
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (0, 0))

    def test_offer_text_discloses_both_actual_amounts_and_the_term(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        event = next(e for arc in catalog["arcs"] for e in arc["events"] if e["id"] == "ywc_jhg.1026")
        for language in ("zh", "en"):
            for token in ("120", "ywc_jhg_share_request_jhg_cost", "ywc_jhg_share_request_shu_cost"):
                self.assertIn(token, event["desc"][language])

    def test_actual_tribute_queue_reaches_settlement_after_answer_or_refusal(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_jhg_tribute_autonomy")
        for answer, fallback in (("accept", None), ("refuse", "fixed_share"), ("refuse", "ambiguity")):
            with self.subTest(answer=answer, fallback=fallback):
                countries = share_countries()
                state = countries["JHG"]
                for key in ("ywc_jhg_tribute_filing_fee", "ywc_jhg_tribute_filing_fee_paid", "ywc_jhg_tribute_route"):
                    state.pop(key, None)
                state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                              "ywc_campaign_jhg_c1_outcome": 1})
                world = JhgShareWorld(countries)
                world.activate_entry(arc, arc["journals"][0]["id"])
                choices = {"ywc_jhg.1020": "project_share", "ywc_jhg.1021": "fixed_share",
                           "ywc_jhg.1022": "project_share" if fallback is None else fallback,
                           "ywc_jhg.1023": "ambiguity", "ywc_jhg.1024": "hold_course",
                           "ywc_jhg.1026": answer}
                completed, trace = set(), []
                for month in range(80):
                    world.run_country_monthly("JHG")
                    world.pulse(arc)
                    while True:
                        jobs = [job for job in world.jobs if job.serial not in completed
                                and job.due_day <= world.day and job.event_id != "ywc_jhg.1027"]
                        if not jobs:
                            break
                        job = jobs[0]
                        completed.add(job.serial)
                        self.assertTrue(world.display_job(job), (month, job.event_id))
                        legal = world.job_options(job)
                        key = ("settle_partial" if legal.get("settle_partial") else "defer") if job.event_id == "ywc_jhg.1025" else choices[job.event_id]
                        self.assertTrue(legal.get(key), (month, job.event_id, key, legal))
                        world.choose_job(job, key)
                        trace.append((month, job.event_id, job.recipient.tag, key))
                    world.refresh(arc)
                    if state.get("ywc_jhg_v03_jhg_tribute_autonomy_settled"):
                        break
                    world.advance_months(1)
                else:
                    self.fail((answer, fallback, "tribute did not settle", trace))
                self.assertEqual([x[1] for x in trace[:6]], ["ywc_jhg.1020", "ywc_jhg.1026", "ywc_jhg.1021", "ywc_jhg.1022", "ywc_jhg.1023", "ywc_jhg.1024"])
                self.assertTrue(all(row[1] == "ywc_jhg.1025" for row in trace[6:]))
                self.assertEqual(trace[-1][3], "settle_partial")
                self.assertGreaterEqual(trace[-1][0] - trace[5][0], 6)
                self.assertEqual(trace[1][2:], ("SHU", answer))
                self.assertEqual(state["ywc_jhg_v03_jhg_tribute_autonomy_outcome"], 2)
                self.assertEqual(state["ywc_jhg_tribute_route"], 2 if fallback is None else 1 if fallback == "fixed_share" else 3)
                self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-2000, -1000) if answer == "accept" else (-1000, 0))
                self.assertEqual(world.history["JHG"], {row["id"]: "complete" for row in arc["journals"]})

    def test_independent_domestic_plan_can_advance_without_forging_a_relationship(self):
        countries = share_countries()
        countries["JHG"]["is_subject"] = False
        world = JhgShareWorld(countries)
        for route, key in ((1, "fixed_share"), (3, "ambiguity")):
            countries["JHG"]["ywc_jhg_tribute_route"] = route
            option = option_body(world, "ywc_jhg.1021", "continue_domestic")
            self.assertTrue(world.conditions(field(option, "trigger"), "JHG"))
            select_option(world, "ywc_jhg.1021", "continue_domestic")
            self.assertEqual(countries["JHG"]["ywc_jhg_tribute_pending_event"], 1022)
            select_option(world, "ywc_jhg.1022", key)
            self.assertEqual(countries["JHG"]["ywc_jhg_tribute_pending_event"], 1023)
        self.assertFalse(countries["JHG"]["is_subject"])

    def test_stale_domestic_choice_on_notice_preserves_the_normal_queue(self):
        countries = share_countries()
        state = countries["JHG"]
        state.update({"ywc_jhg_tribute_settlement_stage": 1, "ywc_jhg_tribute_route": 3,
                      "ywc_jhg_tribute_pending_event": 1023,
                      "ywc_jhg_tribute_notice_delivery_active": 1, "ywc_jhg_tribute_notice_delivery_36": 1})
        world = JhgShareWorld(countries)
        select_option(world, "ywc_jhg.1025", "switch_ambiguity")
        self.assertEqual(state["ywc_jhg_tribute_pending_event"], 1023)
        self.assertNotIn("ywc_jhg_tribute_notice_delivery_active", state)
        self.assertNotIn("ywc_jhg_tribute_notice_delivery_36", state)

    def test_late_signed_partner_loss_offers_domestic_recovery_without_refund(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_jhg_tribute_autonomy")
        for key, route in (("switch_fixed_share", 1), ("switch_ambiguity", 3)):
            with self.subTest(key=key):
                countries = share_countries()
                state = countries["JHG"]
                for name in ("ywc_jhg_tribute_filing_fee", "ywc_jhg_tribute_filing_fee_paid", "ywc_jhg_tribute_route"):
                    state.pop(name, None)
                state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                              "ywc_campaign_jhg_c1_outcome": 1})
                world = JhgShareWorld(countries)
                world.activate_entry(arc, arc["journals"][0]["id"])
                choices = {"ywc_jhg.1020": "project_share", "ywc_jhg.1021": "fixed_share",
                           "ywc_jhg.1022": "project_share", "ywc_jhg.1023": "ambiguity",
                           "ywc_jhg.1024": "hold_course", "ywc_jhg.1026": "accept"}
                completed, trace = set(), []
                lost, switched_at = False, None
                for month in range(80):
                    if not lost and state.get("ywc_jhg_tribute_settlement_stage"):
                        countries["SHU"]["relations"]["JHG"] = -1
                        lost = True
                    world.run_country_monthly("JHG")
                    world.pulse(arc)
                    while True:
                        jobs = [job for job in world.jobs if job.serial not in completed
                                and job.due_day <= world.day and job.event_id != "ywc_jhg.1027"]
                        if not jobs:
                            break
                        job = jobs[0]
                        completed.add(job.serial)
                        self.assertTrue(world.display_job(job), (month, job.event_id))
                        legal = world.job_options(job)
                        if job.event_id == "ywc_jhg.1025":
                            if switched_at is None:
                                self.assertFalse(legal.get("settle_partial"))
                                choice, switched_at = key, month
                            else:
                                choice = "settle_partial" if legal.get("settle_partial") else "defer"
                        else:
                            choice = choices[job.event_id]
                        self.assertTrue(legal.get(choice), (month, job.event_id, choice, legal))
                        world.choose_job(job, choice)
                        trace.append((month, job.event_id, choice))
                        if choice == key:
                            self.assertEqual(state["ywc_jhg_tribute_route"], route)
                            self.assertNotIn("ywc_jhg_tribute_six_months_complete", state)
                            self.assertEqual(state["ywc_jhg_share_contract_generation"], 1)
                    world.refresh(arc)
                    if state.get("ywc_jhg_v03_jhg_tribute_autonomy_settled"):
                        break
                    world.advance_months(1)
                else:
                    self.fail((key, "domestic recovery did not settle", trace))
                self.assertTrue(lost)
                self.assertGreaterEqual(month - switched_at, 6)
                self.assertEqual(state["ywc_jhg_v03_jhg_tribute_autonomy_outcome"], 2)
                self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-2000, -1000))

    def test_lost_overlord_before_answer_can_reach_independent_ambiguity_settlement(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_jhg_tribute_autonomy")
        countries = share_countries()
        state = countries["JHG"]
        for name in ("ywc_jhg_tribute_filing_fee", "ywc_jhg_tribute_filing_fee_paid", "ywc_jhg_tribute_route"):
            state.pop(name, None)
        state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                      "ywc_campaign_jhg_c1_outcome": 1, "test_no_allies": True})
        world = JhgShareWorld(countries)
        world.activate_entry(arc, arc["journals"][0]["id"])
        choices = {"ywc_jhg.1020": "project_share", "ywc_jhg.1021": "switch_ambiguity",
                   "ywc_jhg.1022": "ambiguity", "ywc_jhg.1023": "ambiguity",
                   "ywc_jhg.1024": "hold_course"}
        completed, trace = set(), []
        for month in range(80):
            world.run_country_monthly("JHG")
            world.pulse(arc)
            while True:
                jobs = [job for job in world.jobs if job.serial not in completed and job.due_day <= world.day]
                if not jobs:
                    break
                job = jobs[0]
                completed.add(job.serial)
                if job.event_id == "ywc_jhg.1026":
                    self.assertFalse(world.display_job(job))
                    continue
                self.assertTrue(world.display_job(job), (month, job.event_id))
                legal = world.job_options(job)
                choice = ("settle_partial" if legal.get("settle_partial") else "defer") if job.event_id == "ywc_jhg.1025" else choices[job.event_id]
                self.assertTrue(legal.get(choice), (month, job.event_id, choice, legal))
                world.choose_job(job, choice)
                trace.append((month, job.event_id, choice))
                if job.event_id == "ywc_jhg.1020":
                    state["is_subject"] = False
            world.refresh(arc)
            if state.get("ywc_jhg_v03_jhg_tribute_autonomy_settled"):
                break
            world.advance_months(1)
        else:
            self.fail(("independent domestic fallback did not settle", trace))
        self.assertEqual(state["ywc_jhg_tribute_route"], 3)
        self.assertEqual(state["ywc_jhg_v03_jhg_tribute_autonomy_outcome"], 2)
        self.assertNotIn("ywc_jhg_share_contract_generation", state)
        self.assertEqual((world.treasury["JHG"], world.treasury["SHU"]), (-1000, 0))
        self.assertFalse(state["is_subject"])

    def test_observation_does_not_mature_while_ordinary_queue_remains_at_1021(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_jhg_tribute_autonomy")
        countries = share_countries()
        state = countries["JHG"]
        for name in ("ywc_jhg_tribute_filing_fee", "ywc_jhg_tribute_filing_fee_paid", "ywc_jhg_tribute_route"):
            state.pop(name, None)
        state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                      "ywc_campaign_jhg_c1_outcome": 1})
        world = JhgShareWorld(countries)
        world.activate_entry(arc, arc["journals"][0]["id"])
        completed, deferred = set(), 0
        for month in range(15):
            world.run_country_monthly("JHG")
            world.pulse(arc)
            while True:
                jobs = [job for job in world.jobs if job.serial not in completed and job.due_day <= world.day]
                if not jobs:
                    break
                job = jobs[0]; completed.add(job.serial)
                self.assertTrue(world.display_job(job))
                choice = {"ywc_jhg.1020": "project_share", "ywc_jhg.1026": "accept", "ywc_jhg.1021": "defer"}[job.event_id]
                world.choose_job(job, choice)
                deferred += choice == "defer"
            self.assertNotIn("ywc_jhg_tribute_settlement_stage", state)
            self.assertNotIn("ywc_jhg_tribute_six_months_complete", state)
            self.assertNotIn("ywc_jhg_tribute_observation_timer", state)
            world.advance_months(1)
        self.assertGreaterEqual(deferred, 2)

    def test_notice_lower_target_never_skips_real_tribute_stages_or_the_new_watch(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_jhg_tribute_autonomy")
        countries = share_countries()
        state = countries["JHG"]
        for name in ("ywc_jhg_tribute_filing_fee", "ywc_jhg_tribute_filing_fee_paid", "ywc_jhg_tribute_route"):
            state.pop(name, None)
        state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                      "ywc_campaign_jhg_c1_outcome": 1})
        world = JhgShareWorld(countries)
        world.activate_entry(arc, arc["journals"][0]["id"])
        completed, trace = set(), []
        lowered, hold_month = False, None
        for month in range(100):
            world.run_country_monthly("JHG")
            world.pulse(arc)
            while True:
                jobs = [job for job in world.jobs if job.serial not in completed and job.due_day <= world.day
                        and job.event_id != "ywc_jhg.1027"]
                if not jobs:
                    break
                job = jobs[0]; completed.add(job.serial)
                self.assertTrue(world.display_job(job), (month, job.event_id))
                legal = world.job_options(job)
                if job.event_id == "ywc_jhg.1025":
                    if hold_month is None:
                        self.assertFalse(legal.get("settle_full"), trace)
                        self.assertFalse(legal.get("settle_partial"), trace)
                    if hold_month is not None and legal.get("settle_partial"):
                        choice = "settle_partial"
                    elif legal.get("limited_36_settlement") and not lowered:
                        choice, lowered = "limited_36_settlement", True
                    elif legal.get("acknowledge_12_notice"):
                        choice = "acknowledge_12_notice"
                    else:
                        choice = "defer"
                elif job.event_id == "ywc_jhg.1021":
                    choice = "fixed_share" if lowered else "defer"
                else:
                    choice = {"ywc_jhg.1020": "project_share", "ywc_jhg.1026": "accept",
                              "ywc_jhg.1022": "project_share", "ywc_jhg.1023": "ambiguity",
                              "ywc_jhg.1024": "hold_course"}[job.event_id]
                self.assertTrue(legal.get(choice), (month, job.event_id, choice, legal))
                world.choose_job(job, choice)
                trace.append((month, job.event_id, choice))
                if job.event_id == "ywc_jhg.1026":
                    countries["SHU"]["relations"]["JHG"] = -1
                if choice == "limited_36_settlement":
                    self.assertEqual(state["ywc_jhg_tribute_pending_event"], 1021)
                    countries["SHU"]["relations"]["JHG"] = 10
                if job.event_id == "ywc_jhg.1024":
                    hold_month = month
            world.refresh(arc)
            if state.get("ywc_jhg_v03_jhg_tribute_autonomy_settled"):
                break
            world.advance_months(1)
        else:
            relevant = {k: v for k, v in state.items() if k.startswith(("ywc_jhg_tribute_", "ywc_jhg_share_"))}
            self.fail(("tribute did not settle after notice and ordinary stages", trace, relevant,
                       world.conditions(world.trigger_defs["ywc_jhg_tribute_current_target_ready"], "JHG")))
        self.assertTrue(lowered)
        self.assertIsNotNone(hold_month)
        self.assertGreaterEqual(month - hold_month, 6)
        for event_id in ("ywc_jhg.1021", "ywc_jhg.1022", "ywc_jhg.1023", "ywc_jhg.1024"):
            self.assertTrue(any(row[1] == event_id and row[2] != "defer" for row in trace), trace)

    def test_1024_choice_does_not_count_an_extra_blocked_month(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        arc = next(a for a in catalog["arcs"] if a["slug"] == "v03_jhg_tribute_autonomy")
        countries = share_countries(); state = countries["JHG"]
        for name in ("ywc_jhg_tribute_filing_fee", "ywc_jhg_tribute_filing_fee_paid", "ywc_jhg_tribute_route"):
            state.pop(name, None)
        state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
                      "ywc_campaign_jhg_c1_outcome": 1})
        world = JhgShareWorld(countries)
        world.activate_entry(arc, arc["journals"][0]["id"])
        choices = {"ywc_jhg.1020": "project_share", "ywc_jhg.1026": "accept",
                   "ywc_jhg.1021": "fixed_share", "ywc_jhg.1022": "project_share",
                   "ywc_jhg.1023": "ambiguity", "ywc_jhg.1024": "hold_course"}
        completed = set()
        for _ in range(30):
            world.run_country_monthly("JHG")
            world.pulse(arc)
            while True:
                jobs = [job for job in world.jobs if job.serial not in completed and job.due_day <= world.day]
                if not jobs:
                    break
                job = jobs[0]; completed.add(job.serial)
                self.assertTrue(world.display_job(job))
                choice = choices[job.event_id]
                self.assertTrue(world.job_options(job).get(choice))
                before = state.get("ywc_jhg_tribute_blocked_months")
                world.choose_job(job, choice)
                if job.event_id == "ywc_jhg.1023":
                    countries["SHU"]["relations"]["JHG"] = -1
                if job.event_id == "ywc_jhg.1024":
                    self.assertIsNotNone(before)
                    self.assertEqual(state["ywc_jhg_tribute_blocked_months"], before)
                    return
            world.advance_months(1)
        self.fail("the real 1024 event was not dispatched")


if __name__ == "__main__":
    unittest.main()

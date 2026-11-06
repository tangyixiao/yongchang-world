"""Actual NMG partner responses and fiscal obligations, offline source model."""
import copy
import math
import unittest
from datetime import date
from pathlib import Path

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field
from clausewitz_harness import parse


def base_countries(fee=600):
    countries = {tag: copy.deepcopy(facts()) for tag in ("NMG", "MEX", "JHG")}
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    countries["NMG"].update({"is_subject": True, "overlord": "MEX",
                             "ywc_nmg_revenue_quota": fee, "ywc_nmg_revenue_quota_paid": 1,
                             "ywc_nmg_revenue_route": 0})
    return countries


class NmgPartnerWorld(PartnerWorld):
    def __init__(self, countries, start_date=date(1836, 1, 1)):
        super().__init__(countries, tag="nmg", start_date=start_date)
        root = Path("yongchang_world/common")
        for rel, destination in (("script_values/ywc_v03_nmg_values.txt", self.named_values),
                                 ("on_actions/ywc_v03_nmg_accounts.txt", self.on_actions),
                                 ("static_modifiers/ywc_v03_nmg_modifiers.txt", self.modifier_defs)):
            path = root / rel
            if path.exists():
                body = parse(path.read_text(encoding="utf-8-sig"))
                if rel.startswith("on_actions/"):
                    self.merge_on_actions(body)
                else:
                    destination.update({key: value for key, _, value in body})

    def _value(self, token, *, optional=False):
        if token == "relations_threshold:poor":
            return -50  # explicit bounded fixture for the engine-owned threshold
        if isinstance(token, list) and any(key == "floor" for key, _, _ in token):
            floors = [node for node in token if node[0] == "floor"]
            if floors != [("floor", "=", "yes")] or token[-1] != floors[0]:
                raise AssertionError(("unsupported floor value", token))
            return math.floor(super()._value(token[:-1], optional=optional))
        return super()._value(token, optional=optional)

    def condition(self, node, tag):
        key, op, value = node
        if key == "is_subject_of":
            if self._current is None:
                with self._chain(self.country_ref(tag)):
                    return self.condition(node, tag)
            actual = self._value("overlord", optional=True)
            target = self._value(value, optional=True)
            return self.countries[tag].get("is_subject", False) and self._present(actual) and actual == target
        return super().condition(node, tag)


def option(world, event_id, key):
    return next(body for name, _, body in world.event_defs[event_id]
                if name == "option" and field(body, "name").endswith("." + key))


def choose(world, event_id, key):
    body = option(world, event_id, key)
    world.execute([node for node in body if node[0] not in ("name", "trigger", "ai_chance")], "NMG")


def choose_legal(world, event_id, key):
    body = option(world, event_id, key)
    assert world.conditions(field(body, "trigger"), "NMG"), (event_id, key)
    choose(world, event_id, key)


def accepted_fixed(world):
    choose_legal(world, "ywc_nmg.1020", "fixed")
    offer = world.jobs[-1]
    assert offer.event_id == "ywc_nmg.1030" and world.display_job(offer)
    world.choose_job(offer, "accept")
    return offer


def live_revenue_world(countries=None):
    countries = base_countries() if countries is None else countries
    state = countries["NMG"]
    for key in ("ywc_nmg_revenue_quota_paid", "ywc_nmg_revenue_quota", "ywc_nmg_revenue_route"):
        state.pop(key, None)
    state.update({"ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0})
    world = NmgPartnerWorld(countries)
    arc = next(a for a in world.cat["arcs"] if a["slug"] == "v03_nmg_autonomy_revenue")
    world.activate_entry(arc, arc["journals"][0]["id"])
    return world, arc


def run_live_month(world, arc, handled, select, extra_monthlies=()):
    """Pulse the authored JE and deliver actual jobs, including foreign answers."""
    world.run_country_monthly("NMG")
    for tag in extra_monthlies:
        world.run_country_monthly(tag)
    world.pulse(arc)
    index = 0
    while index < len(world.jobs):
        job = world.jobs[index]; index += 1
        if job.serial in handled or not world.display_job(job):
            continue
        handled.add(job.serial)
        if field(world.event_defs[job.event_id], "hidden") == "yes":
            continue
        choices = world.job_options(job)
        key = select(world, job, choices)
        if key is None:  # Explicitly hold a displayed popup for stale-choice tests.
            continue
        assert choices.get(key), (world.elapsed_months, job.event_id, key, choices)
        world.choose_job(job, key)
    world.refresh(arc)
    world.advance_months(1)


class NmgPartnerResponseTests(unittest.TestCase):
    def test_local_fixed_marker_does_not_prove_mexican_consent(self):
        countries = base_countries()
        countries["NMG"].update({"ywc_nmg_revenue_route": 1, "ywc_nmg_revenue_audit_strict": 1,
                                  "ywc_nmg_revenue_share": 3, "ywc_nmg_revenue_stage3": 1})
        world = NmgPartnerWorld(countries)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))

    def test_fixed_proposal_goes_to_the_actual_mexican_overlord(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "fixed")
        self.assertTrue(world.jobs)
        self.assertEqual((world.jobs[-1].event_id, world.jobs[-1].recipient.tag), ("ywc_nmg.1030", "MEX"))

    def test_fixed_acceptance_creates_sixty_real_matched_remittances_once(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        offer = accepted_fixed(world)
        state = countries["NMG"]
        self.assertEqual(state["ywc_nmg_mexshare_contract_partner"], world.country_ref("MEX"))
        self.assertEqual(state["ywc_nmg_mexshare_contract_monthly"], 20)
        self.assertEqual(state["ywc_nmg_mexshare_contract_term"], 60)
        self.assertEqual(state["ywc_nmg_mexshare_contract_right"], 1)
        world.choose_job(offer, "accept")
        for month in range(60):
            if month: world.advance_months(1)
            world.run_country_monthly("NMG")
            world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_mexshare_paid_total"], 1200)
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (-1200, 1200))

    def test_fixed_default_accrues_arrears_and_blocks_a_new_offer(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        countries["NMG"]["in_default"] = True
        world.run_country_monthly("NMG")
        state = countries["NMG"]
        self.assertEqual(state["ywc_nmg_mexshare_earned_total"], 20)
        self.assertEqual(state["ywc_nmg_mexshare_paid_total"], 0)
        self.assertEqual(world.treasury["MEX"], 0)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_mexshare_can_offer"], "NMG"))
        countries["NMG"]["in_default"] = False
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_mexshare_earned_total"], 40)
        self.assertEqual(state["ywc_nmg_mexshare_paid_total"], 40)
        self.assertEqual(world.treasury["MEX"], 40)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_mexshare_agreement_current"], "NMG"))

    def test_fixed_proposal_cannot_advance_or_accept_after_terms_change(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "fixed")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        advance = option(world, "ywc_nmg.1022", "close_account")
        self.assertFalse(world.conditions(field(advance, "trigger"), "NMG"))
        choose(world, "ywc_nmg.1022", "close_account")
        self.assertNotIn("ywc_nmg_revenue_stage2", countries["NMG"])
        countries["NMG"]["ywc_nmg_mexshare_quote_monthly"] += 1
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nmg_mexshare_contract_generation", countries["NMG"])
        self.assertEqual(world.treasury["MEX"], 0)

    def test_each_captured_term_and_old_recipient_blocks_stale_acceptance(self):
        for name in ("generation", "serial", "quote_monthly", "quote_term", "quote_right"):
            with self.subTest(changed=name):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                choose_legal(world, "ywc_nmg.1020", "fixed")
                offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
                countries["NMG"]["ywc_nmg_mexshare_" + name] += 1
                world.choose_job(offer, "accept")
                self.assertNotIn("ywc_nmg_mexshare_contract_generation", countries["NMG"])
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "fixed")
        old = world.jobs[-1]; world.remove_country("MEX")
        world.add_country("MEX", base_countries()["MEX"])
        self.assertFalse(world.display_job(old))
        self.assertNotIn("ywc_nmg_mexshare_contract_generation", countries["NMG"])

    def test_limited_cash_pays_one_due_instalment_then_catches_up_when_funded(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        countries["NMG"]["in_default"] = True
        world.run_country_monthly("NMG")
        world.advance_months(1); world.run_country_monthly("NMG")
        countries["NMG"].update({"in_default": False, "gold_reserves": 20})
        world.advance_months(1); world.run_country_monthly("NMG")
        state = countries["NMG"]
        self.assertEqual((state["ywc_nmg_mexshare_earned_total"], state["ywc_nmg_mexshare_paid_total"]), (60, 20))
        self.assertEqual(world.treasury["MEX"], 20)
        state["gold_reserves"] = 100000
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual((state["ywc_nmg_mexshare_earned_total"], state["ywc_nmg_mexshare_paid_total"]), (80, 80))
        self.assertEqual(world.treasury["MEX"], 80)

    def test_fixed_preparation_fee_is_new_affordable_and_paid_only_once(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        heavy = option(world, "ywc_nmg.1025", "carry_heavy")
        countries["NMG"]["gold_reserves"] = 0
        self.assertFalse(world.conditions(field(heavy, "trigger"), "NMG"))
        countries["NMG"]["gold_reserves"] = 600
        self.assertTrue(world.conditions(field(heavy, "trigger"), "NMG"))
        choose(world, "ywc_nmg.1025", "carry_heavy")
        choose(world, "ywc_nmg.1025", "carry_heavy")
        self.assertEqual(world.treasury["NMG"], -600)
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_share"], 3)

    def test_midmonth_term_has_full_sixty_pulses_and_old_endpoint_cannot_end_renewal(self):
        countries = base_countries(); world = NmgPartnerWorld(countries, date(1836, 1, 15))
        accepted_fixed(world)
        old_end = next(job for job in world.jobs if job.event_id == "ywc_nmg.1031")
        world.advance_days(17)
        for month in range(60):
            if month: world.advance_months(1)
            world.run_country_monthly("NMG")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_count"], 60)
        self.assertEqual(world.treasury["MEX"], 1200)
        world.advance_days(14); world.run_due_hidden()
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_mexshare_can_offer"], "NMG"))
        world.run_script("ywc_nmg_mexshare_send = yes", "NMG")
        new_offer = world.jobs[-1]; self.assertTrue(world.display_job(new_offer))
        world.choose_job(new_offer, "accept")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_contract_generation"], 2)
        with world._chain(old_end.recipient, old_end.saved):
            world.execute(field(world.event_defs[old_end.event_id], "immediate"), "NMG")
        self.assertNotEqual(countries["NMG"].get("ywc_nmg_mexshare_ended_generation"), 2)
        self.assertIn("ywc_nmg_mexshare_term_timer", countries["NMG"])

    def test_expired_term_keeps_arrears_and_blocks_renewal_until_paid(self):
        countries = base_countries(); world = NmgPartnerWorld(countries, date(1836, 1, 15))
        accepted_fixed(world)
        world.advance_days(17); world.run_country_monthly("NMG")
        for _ in range(58):
            world.advance_months(1); world.run_country_monthly("NMG")
        countries["NMG"]["in_default"] = True
        world.advance_months(1); world.run_country_monthly("NMG")
        world.advance_days(14); world.run_due_hidden()
        state = countries["NMG"]
        self.assertEqual((state["ywc_nmg_mexshare_earned_total"], state["ywc_nmg_mexshare_paid_total"]), (1200, 1180))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_mexshare_can_offer"], "NMG"))
        countries["NMG"]["in_default"] = False
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_mexshare_paid_total"], 1200)
        self.assertEqual(world.treasury["MEX"], 1200)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_mexshare_can_offer"], "NMG"))

    def test_subject_change_cancels_unsigned_but_keeps_signed_debt_due(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "fixed")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        countries["NMG"].update({"is_subject": False, "overlord": None})
        world.run_on_action("on_become_independent", "NMG"); world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nmg_mexshare_contract_generation", countries["NMG"])

        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        world.run_country_monthly("NMG")
        self.assertTrue(any(row.get("name") == "ywc_nmg_local_port_budget_right" for _, row in world.modifiers))
        countries["NMG"].update({"is_subject": False, "overlord": None, "in_default": True})
        world.run_on_action("on_become_independent", "NMG")
        self.assertFalse(any(row.get("name") == "ywc_nmg_local_port_budget_right" for _, row in world.modifiers))
        world.advance_months(1); world.run_country_monthly("NMG")
        countries["NMG"]["in_default"] = False
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_total"], 60)
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_paid_total"], 60)
        self.assertEqual(world.treasury["MEX"], 60)
        self.assertFalse(any(row.get("name") == "ywc_nmg_local_port_budget_right" for _, row in world.modifiers))

    def test_lost_creditor_latches_and_never_rebinds_to_a_recreated_mex(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        countries["NMG"]["gold_reserves"] = 0
        world.run_country_monthly("NMG")
        world.remove_country("MEX")
        world.advance_months(1); world.run_country_monthly("NMG")
        state = countries["NMG"]
        self.assertEqual(state["ywc_nmg_mexshare_creditor_invalid_generation"], 1)
        self.assertEqual(state["ywc_nmg_mexshare_earned_total"], 20)
        world.add_country("MEX", base_countries()["MEX"])
        state["gold_reserves"] = 100000
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(state["ywc_nmg_mexshare_paid_total"], 0)
        self.assertEqual(world.treasury["MEX"], 0)

    def test_fiscal_office_right_is_active_only_while_terms_are_current(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        world.run_country_monthly("NMG")
        active = lambda: any(tag == "NMG" and row.get("name") == "ywc_nmg_local_port_budget_right"
                             for tag, row in world.modifiers)
        self.assertTrue(active())
        countries["NMG"]["in_default"] = True
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertFalse(active())

    def test_domestic_plan_can_advance_without_a_foreign_partner(self):
        countries = base_countries()
        countries["NMG"].update({"is_subject": False, "overlord": None})
        countries["NMG"].pop("ywc_nmg_revenue_quota_paid")
        world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "domestic")
        self.assertEqual(world.treasury["NMG"], -600)
        self.assertEqual(world.jobs, [])
        for event, key in (("1021", "audit_strict"), ("1022", "close_account_domestic"),
                           ("1023", "local_plan"), ("1024", "local_record"),
                           ("1025", "retain_local_budget"), ("1026", "conclude")):
            choice = option(world, "ywc_nmg." + event, key)
            self.assertTrue(world.conditions(field(choice, "trigger"), "NMG"), (event, key))
            choose(world, "ywc_nmg." + event, key)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))
        self.assertEqual(world.treasury["MEX"], 0)
        self.assertFalse(any(row.get("name") == "ywc_nmg_local_port_budget_right" for _, row in world.modifiers))

    def test_refused_fixed_offer_can_switch_domestic_without_refund_or_stale_acceptance(self):
        countries = base_countries(); countries["NMG"].pop("ywc_nmg_revenue_quota_paid")
        world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "fixed")
        offer = world.jobs[-1]
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        choose(world, "ywc_nmg.1022", "switch_domestic")
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_route"], 4)
        self.assertNotIn("ywc_nmg_mexshare_contract_generation", countries["NMG"])
        self.assertEqual(world.treasury["NMG"], -600)

    def test_refused_fixed_offer_can_be_reissued_without_a_second_filing_fee(self):
        countries = base_countries(); countries["NMG"].pop("ywc_nmg_revenue_quota_paid")
        world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "fixed")
        old = world.jobs[-1]; self.assertTrue(world.display_job(old))
        world.choose_job(old, "refuse")
        choose(world, "ywc_nmg.1021", "audit_strict")
        choose(world, "ywc_nmg.1022", "reopen")
        choose(world, "ywc_nmg.1020", "fixed")
        offers = [job for job in world.jobs if job.event_id == "ywc_nmg.1030"]
        self.assertEqual(len(offers), 2)
        self.assertTrue(world.display_job(offers[-1]))
        world.choose_job(old, "accept")
        self.assertNotIn("ywc_nmg_mexshare_contract_generation", countries["NMG"])
        world.choose_job(offers[-1], "accept")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_contract_generation"], 2)
        self.assertEqual(world.treasury["NMG"], -600)

    def test_switching_domestic_does_not_cancel_signed_fixed_arrears(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        countries["NMG"]["in_default"] = True
        world.run_country_monthly("NMG")
        countries["NMG"]["in_default"] = False
        countries["NMG"]["gold_reserves"] = 0
        choose_legal(world, "ywc_nmg.1022", "switch_domestic")
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_route"], 4)
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_total"], 20)
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_paid_total"], 0)
        countries["NMG"]["gold_reserves"] = 100000
        world.advance_months(1); world.run_country_monthly("NMG")
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_earned_total"], 40)
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_paid_total"], 40)
        self.assertEqual(world.treasury["MEX"], 40)

    def test_stale_share_choice_cannot_charge_or_override_domestic_progress(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        choose(world, "ywc_nmg.1022", "switch_domestic")
        pending = countries["NMG"]["ywc_nmg_revenue_pending"]
        choose(world, "ywc_nmg.1025", "carry_heavy")
        choose(world, "ywc_nmg.1025", "share_even")
        self.assertEqual(world.treasury["NMG"], 0)
        self.assertNotIn("ywc_nmg_revenue_share", countries["NMG"])
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_pending"], pending)

    def test_notice_switch_preserves_opening_queue_and_does_not_skip_audit(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose(world, "ywc_nmg.1020", "fixed")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        choose(world, "ywc_nmg.1021", "defer")
        choose(world, "ywc_nmg.1022", "reopen")
        state = countries["NMG"]
        state["ywc_nmg_revenue_notice_response_context"] = 1
        state["ywc_nmg_revenue_notice_return_event"] = 1020
        choose(world, "ywc_nmg.1029", "switch_domestic")
        self.assertEqual(state["ywc_nmg_revenue_pending"], 1020)
        self.assertNotIn("ywc_nmg_revenue_stage2", state)
        self.assertNotIn("ywc_nmg_revenue_audit_strict", state)
        self.assertNotIn("ywc_nmg_revenue_audit_public", state)
        for event, key in (("1020", "domestic"), ("1021", "audit_strict"),
                           ("1022", "close_account_domestic"), ("1023", "local_plan"),
                           ("1024", "local_record"), ("1025", "retain_local_budget"),
                           ("1026", "conclude")):
            choose(world, "ywc_nmg." + event, key)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))

    def test_limited_popup_does_not_offer_full_settlement(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "fixed")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "refuse")
        choose_legal(world, "ywc_nmg.1021", "audit_strict")
        choose_legal(world, "ywc_nmg.1022", "switch_domestic")
        for event, key in (("1023", "local_plan"), ("1024", "local_record"),
                           ("1025", "retain_local_budget"), ("1026", "conclude")):
            choose_legal(world, "ywc_nmg." + event, key)
        countries["NMG"]["ywc_nmg_revenue_six_months_complete"] = 1
        self.assertFalse(world.conditions(field(option(world, "ywc_nmg.1027", "settle_full"), "trigger"), "NMG"))
        self.assertTrue(world.conditions(field(option(world, "ywc_nmg.1027", "settle_partial"), "trigger"), "NMG"))

    def test_stale_notice_close_cannot_overwrite_unrelated_pending_work(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        state = countries["NMG"]
        state.update({"ywc_v03_nmg_v03_nmg_autonomy_revenue_started": 1,
                      "ywc_nmg_revenue_limited_selected": 1, "ywc_nmg_revenue_route": 4,
                      "ywc_nmg_revenue_stage2": 1, "ywc_nmg_revenue_pending": 1023,
                      "ywc_nmg_revenue_notice_response_context": 1,
                      "ywc_nmg_revenue_notice_return_event": 1023,
                      "ywc_nmg_revenue_last_event": 1029})
        self.assertFalse(world.conditions(field(option(world, "ywc_nmg.1029", "close_partial"), "trigger"), "NMG"))
        choose(world, "ywc_nmg.1029", "close_partial")  # stale selection after conditions change
        self.assertEqual(state["ywc_nmg_revenue_pending"], 1023)
        self.assertNotIn("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled", state)

    def test_domestic_walk_out_returns_to_the_live_negotiation_queue(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "domestic")
        choose_legal(world, "ywc_nmg.1021", "audit_strict")
        choose_legal(world, "ywc_nmg.1022", "close_account_domestic")
        choose_legal(world, "ywc_nmg.1023", "local_plan")
        choose_legal(world, "ywc_nmg.1024", "local_record")
        choose_legal(world, "ywc_nmg.1025", "retain_local_budget")
        choose_legal(world, "ywc_nmg.1026", "walk_out")
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_pending"], 1023)
        self.assertEqual(countries["NMG"]["relations"]["MEX"], 10)

    def test_live_independent_domestic_walk_out_revisits_negotiation(self):
        countries = base_countries()
        countries["NMG"].update({"is_subject": False, "overlord": None})
        countries.pop("MEX")
        world, arc = live_revenue_world(countries); handled = set(); seen = []; walked = False
        def select(w, job, options):
            nonlocal walked
            number = job.event_id.split(".")[-1]; seen.append(number)
            if number == "1026":
                if not walked:
                    walked = True
                    return "walk_out"
                return "conclude"
            if number == "1027": return "settle_full" if options.get("settle_full") else "wait_retry"
            return {"1020": "domestic", "1021": "audit_strict", "1022": "close_account_domestic",
                    "1023": "local_plan", "1024": "local_record", "1025": "retain_local_budget"}[number]
        for _ in range(55):
            run_live_month(world, arc, handled, select)
            if world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
        self.assertTrue(walked)
        self.assertGreaterEqual(seen.count("1023"), 2)
        self.assertEqual(world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 3)

    def test_late_domestic_fallback_can_complete_a_missing_local_audit(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        state = countries["NMG"]
        state.update({"ywc_nmg_revenue_route": 4, "ywc_nmg_revenue_stage3": 1,
                      "ywc_nmg_revenue_share": 4, "ywc_nmg_revenue_pending": 1027})
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))
        choose_legal(world, "ywc_nmg.1027", "review_local_audit")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))
        self.assertNotIn("ywc_nmg_revenue_six_months_complete", state)

    def test_live_fixed_chain_reaches_full_settlement_after_a_real_mexican_answer(self):
        world, arc = live_revenue_world(); handled = set(); seen = []
        choices = {"1020": "fixed", "1030": "accept", "1021": "audit_strict",
                   "1022": "close_account", "1023": "press_quota", "1024": "use_temperature",
                   "1025": "carry_heavy", "1026": "conclude"}
        def select(w, job, options):
            number = job.event_id.split(".")[-1]; seen.append(number)
            if number == "1027": return "settle_full" if options.get("settle_full") else "wait_retry"
            return choices[number]
        for _ in range(40):
            run_live_month(world, arc, handled, select)
            if world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
        state = world.countries["NMG"]
        self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 3)
        self.assertIn("1030", seen)
        self.assertGreater(world.treasury["MEX"], 0)
        self.assertIn("ywc_nmg_mexshare_contract_generation", state)

    def test_live_36_month_notice_switch_preserves_opening_and_finishes_partial(self):
        world, arc = live_revenue_world(); handled = set(); seen_12 = False; switched = False
        def select(w, job, options):
            nonlocal seen_12, switched
            number = job.event_id.split(".")[-1]
            if number == "1030": return "refuse"
            if number == "1020":
                return "domestic" if switched else ("fixed" if not w.countries["NMG"].get("ywc_nmg_revenue_quota_paid") else "wait_for_funds")
            if number == "1021": return "audit_strict" if switched else "defer"
            if number == "1022": return "close_account_domestic" if switched else "reopen"
            if number == "1028":
                seen_12 = True
                return "defer"
            if number == "1029":
                self.assertTrue(seen_12)
                state = w.countries["NMG"]
                self.assertEqual(state.get("ywc_nmg_revenue_pending"), 1020)
                self.assertEqual(state.get("ywc_nmg_revenue_notice_return_event"), 1020)
                self.assertNotIn("ywc_nmg_revenue_stage2", state)
                switched = True
                return "switch_domestic"
            if number == "1027":
                self.assertFalse(options.get("settle_full"))
                return "settle_partial" if options.get("settle_partial") else "wait_retry"
            return {"1023": "local_plan", "1024": "local_record", "1025": "retain_local_budget", "1026": "conclude"}[number]
        for _ in range(85):
            run_live_month(world, arc, handled, select)
            if world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
        self.assertTrue(switched)
        self.assertEqual(world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 2)


if __name__ == "__main__":
    unittest.main()

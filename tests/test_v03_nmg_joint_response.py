"""NMG joint-project response and two-ended funding in the offline source model."""
import unittest
from datetime import date

from test_v03_nmg_partner_response import (NmgPartnerWorld, accepted_fixed, base_countries, choose_legal,
                                           live_revenue_world, option, run_live_month)
from shu_kor_strict_review_runtime import field


def accept_joint(world, choice):
    choose_legal(world, "ywc_nmg.1020", choice)
    offer = world.jobs[-1]
    assert offer.event_id == "ywc_nmg.1030" and world.display_job(offer)
    assert world.job_options(offer)["accept_joint"]
    world.choose_job(offer, "accept_joint")
    return offer


class NmgJointResponseTests(unittest.TestCase):
    def test_domestic_markers_alone_do_not_prove_partner_consent(self):
        countries = base_countries()
        countries["NMG"].update({"ywc_nmg_revenue_route": 2, "ywc_nmg_revenue_audit_strict": 1,
                                 "ywc_nmg_revenue_share": 2, "ywc_nmg_revenue_stage3": 1})
        world = NmgPartnerWorld(countries)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_revenue_route_ready"], "NMG"))

    def test_mexico_and_jinghai_are_explicit_independent_choices(self):
        for key, target in (("joint", "MEX"), ("joint_jhg", "JHG")):
            with self.subTest(target=target):
                world = NmgPartnerWorld(base_countries())
                self.assertTrue(world.conditions(field(option(world, "ywc_nmg.1020", key), "trigger"), "NMG"))
                choose_legal(world, "ywc_nmg.1020", key)
                self.assertEqual((world.jobs[-1].event_id, world.jobs[-1].recipient.tag), ("ywc_nmg.1030", target))

    def test_equal_project_funds_are_paid_by_each_actual_country_once(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg")
        state = countries["NMG"]
        self.assertEqual(state["ywc_nmg_jointproject_contract_partner"], world.country_ref("JHG"))
        self.assertEqual(state["ywc_nmg_jointproject_contract_own_monthly"], 10)
        self.assertEqual(state["ywc_nmg_jointproject_contract_partner_monthly"], 10)
        self.assertEqual(state["ywc_nmg_jointproject_contract_term"], 60)
        for tag in ("NMG", "JHG", "NMG", "JHG"):
            world.run_country_monthly(tag)
        self.assertEqual((world.treasury["NMG"], world.treasury["JHG"], world.treasury["MEX"]), (-10, -10, 0))
        self.assertEqual(state["ywc_nmg_jointproject_own_paid_total"], 10)
        self.assertEqual(state["ywc_nmg_jointproject_partner_paid_total"], 10)

    def test_nmg_heavier_quote_is_frozen_in_the_partner_answer(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg_heavy")
        state = countries["NMG"]
        self.assertEqual(state["ywc_nmg_jointproject_contract_own_monthly"], 20)
        self.assertEqual(state["ywc_nmg_jointproject_contract_partner_monthly"], 10)
        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
        self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), (-20, -10))

    def test_partner_default_accrues_own_arrears_and_blocks_project_benefit(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint")
        countries["MEX"]["in_default"] = True
        for tag in ("NMG", "MEX"): world.run_country_monthly(tag)
        self.assertEqual(world.treasury["NMG"], -10)
        self.assertEqual(world.treasury["MEX"], 0)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_partner_earned_total"], 10)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_partner_paid_total"], 0)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_jointproject_agreement_current"], "NMG"))

    def test_recovery_catches_up_both_owner_orders_and_only_then_grants_benefit(self):
        for order in (("NMG", "MEX"), ("MEX", "NMG")):
            with self.subTest(order=order):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                accept_joint(world, "joint")
                countries["MEX"]["in_default"] = True
                for tag in order: world.run_country_monthly(tag)
                self.assertFalse(any(t == "NMG" and row.get("name") == "ywc_nmg_revenue_joint_project" for t, row in world.modifiers))
                countries["MEX"]["in_default"] = False
                world.advance_months(1)
                for tag in order: world.run_country_monthly(tag)
                state = countries["NMG"]
                self.assertEqual((state["ywc_nmg_jointproject_partner_earned_total"], state["ywc_nmg_jointproject_partner_paid_total"]), (20, 20))
                self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (-20, -20))
                self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_jointproject_agreement_current"], "NMG"))
                self.assertTrue(any(t == "NMG" and row.get("name") == "ywc_nmg_revenue_joint_project" for t, row in world.modifiers))

    def test_current_month_needs_both_separate_pulses_before_the_benefit(self):
        for order in (("NMG", "JHG"), ("JHG", "NMG")):
            with self.subTest(order=order):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                accept_joint(world, "joint_jhg")
                world.run_country_monthly(order[0])
                self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_jointproject_agreement_current"], "NMG"))
                self.assertFalse(any(t == "NMG" and row.get("name") == "ywc_nmg_revenue_joint_project" for t, row in world.modifiers))
                world.run_country_monthly(order[1])
                self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_jointproject_agreement_current"], "NMG"))
                self.assertTrue(any(t == "NMG" and row.get("name") == "ywc_nmg_revenue_joint_project" for t, row in world.modifiers))

    def test_jinghai_is_eligible_after_independence_and_without_mexico(self):
        countries = base_countries()
        countries["NMG"].update({"is_subject": False, "overlord": None})
        countries.pop("MEX")
        world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg")
        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_jointproject_agreement_current"], "NMG"))

    def test_each_captured_amount_term_scope_and_serial_must_still_match(self):
        for name in ("generation", "serial", "quote_own", "quote_partner", "quote_term", "quote_scope"):
            with self.subTest(name=name):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                choose_legal(world, "ywc_nmg.1020", "joint_jhg")
                offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
                countries["NMG"]["ywc_nmg_jointproject_" + name] += 1
                world.choose_job(offer, "accept_joint")
                self.assertNotIn("ywc_nmg_jointproject_contract_generation", countries["NMG"])
                self.assertNotIn("ywc_nmg_jointproject_provider_generation", countries["JHG"])

    def test_partner_recreation_never_retargets_the_project(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg")
        countries["NMG"]["in_default"] = True
        world.run_country_monthly("NMG")
        world.run_country_monthly("JHG")
        world.remove_country("JHG")
        world.advance_months(1); world.run_country_monthly("NMG")
        state = countries["NMG"]
        self.assertEqual(state["ywc_nmg_jointproject_partner_invalid_generation"], 1)
        self.assertEqual(state["ywc_nmg_jointproject_own_earned_total"], 10)
        world.add_country("JHG", base_countries()["JHG"])
        state["in_default"] = False
        world.advance_months(1); world.run_country_monthly("NMG"); world.run_country_monthly("JHG")
        self.assertEqual(state["ywc_nmg_jointproject_own_paid_total"], 0)
        self.assertEqual(world.treasury["JHG"], 0)

    def test_owner_loss_latches_on_both_sides_even_if_same_object_returns(self):
        for order in (("NMG", "JHG"), ("JHG", "NMG")):
            with self.subTest(order=order):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                accept_joint(world, "joint_jhg")
                for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                countries["NMG"]["is_country_alive"] = False
                world.advance_months(1); world.run_country_monthly("JHG")
                self.assertEqual(countries["JHG"]["ywc_nmg_jointproject_provider_invalid_generation"], 1)
                countries["NMG"]["is_country_alive"] = True
                world.advance_months(1)
                for tag in order: world.run_country_monthly(tag)
                self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_partner_invalid_generation"], 1)
                self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), (-10, -10))
                self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_jointproject_agreement_current"], "NMG"))
                self.assertFalse(any(t == "NMG" and row.get("name") == "ywc_nmg_revenue_joint_project" for t, row in world.modifiers))

    def test_new_owner_can_reuse_a_latched_provider_only_if_old_debt_is_clear(self):
        for debt in (False, True):
            with self.subTest(old_debt=debt):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                old = accept_joint(world, "joint_jhg")
                countries["JHG"]["in_default"] = debt
                for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                world.remove_country("NMG")
                world.advance_months(1); world.run_country_monthly("JHG")
                world.add_country("NMG", base_countries()["NMG"])
                countries["JHG"]["in_default"] = False
                available = world.conditions(world.trigger_defs["ywc_nmg_jointproject_jhg_eligible"], "NMG")
                self.assertEqual(available, not debt)
                if not debt:
                    choose_legal(world, "ywc_nmg.1020", "joint_jhg")
                    new = world.jobs[-1]; self.assertTrue(world.display_job(new))
                    world.choose_job(old, "accept_joint")
                    self.assertNotIn("ywc_nmg_jointproject_contract_generation", countries["NMG"])
                    world.choose_job(new, "accept_joint")
                    self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_partner"], world.country_ref("JHG"))

    def test_lost_partner_can_be_replaced_only_after_old_balances_are_clear(self):
        for debt in (False, True):
            with self.subTest(old_debt=debt):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                accept_joint(world, "joint_jhg")
                old_end = next(job for job in world.jobs if job.event_id == "ywc_nmg.1031")
                countries["NMG"]["in_default"] = debt
                for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                world.remove_country("JHG")
                world.advance_months(1); world.run_country_monthly("NMG")
                countries["NMG"]["in_default"] = False
                eligible = world.conditions(world.trigger_defs["ywc_nmg_jointproject_mex_eligible"], "NMG")
                self.assertEqual(eligible, not debt)
                if debt:
                    self.assertGreater(countries["NMG"]["ywc_nmg_jointproject_own_earned_total"],
                                       countries["NMG"]["ywc_nmg_jointproject_own_paid_total"])
                    continue
                choose_legal(world, "ywc_nmg.1020", "joint")
                new = world.jobs[-1]; self.assertTrue(world.display_job(new))
                # An old scheduled endpoint cannot invalidate the new inquiry.
                with world._chain(old_end.recipient, old_end.saved):
                    world.execute(field(world.event_defs[old_end.event_id], "immediate"), "NMG")
                world.choose_job(new, "accept_joint")
                self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_generation"], 2)
                self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_partner"], world.country_ref("MEX"))

    def test_invalidated_partner_cannot_be_charged_again_during_replacement(self):
        for old_default in (False, True):
            with self.subTest(old_partner_in_default=old_default):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                accept_joint(world, "joint_jhg")
                for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                countries["JHG"]["is_country_alive"] = False
                world.advance_months(1); world.run_country_monthly("NMG")
                self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_partner_invalid_generation"], 1)
                countries["JHG"].update({"is_country_alive": True, "in_default": old_default})
                choose_legal(world, "ywc_nmg.1020", "joint")
                self.assertEqual(world.jobs[-1].recipient.tag, "MEX")
                self.assertEqual(world.treasury["JHG"], -10)
                self.assertEqual(countries["JHG"]["ywc_nmg_jointproject_provider_paid_total"], 10)
                self.assertEqual(countries["JHG"]["ywc_nmg_jointproject_provider_invalid_generation"], 1)
                self.assertEqual(countries["JHG"]["ywc_nmg_jointproject_provider_ended_generation"], 1)

    def test_refusal_and_domestic_fallback_leave_no_project_expenses(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "joint_jhg")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        choose_legal(world, "ywc_nmg.1022", "switch_domestic")
        world.choose_job(offer, "accept_joint")
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_route"], 4)
        self.assertNotIn("ywc_nmg_jointproject_contract_generation", countries["NMG"])
        self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), (0, 0))

    def test_refusal_can_reissue_to_a_different_partner_without_old_answer_replay(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "joint")
        old = world.jobs[-1]; self.assertTrue(world.display_job(old))
        world.choose_job(old, "refuse")
        choose_legal(world, "ywc_nmg.1020", "joint_jhg_heavy")
        new = world.jobs[-1]; self.assertTrue(world.display_job(new))
        world.choose_job(old, "accept_joint")
        self.assertNotIn("ywc_nmg_jointproject_contract_generation", countries["NMG"])
        world.choose_job(new, "accept_joint")
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_generation"], 2)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_partner"], world.country_ref("JHG"))

    def test_mexico_jinghai_mexico_replay_cannot_sign_the_third_offer(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "joint")
        first = world.jobs[-1]; self.assertTrue(world.display_job(first)); world.choose_job(first, "refuse")
        choose_legal(world, "ywc_nmg.1020", "joint_jhg")
        second = world.jobs[-1]; self.assertTrue(world.display_job(second)); world.choose_job(second, "refuse")
        choose_legal(world, "ywc_nmg.1020", "joint_heavy")
        third = world.jobs[-1]; self.assertTrue(world.display_job(third))
        world.choose_job(first, "accept_joint")
        self.assertNotIn("ywc_nmg_jointproject_contract_generation", countries["NMG"])
        world.choose_job(third, "accept_joint")
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_generation"], 3)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_partner"], world.country_ref("MEX"))
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_own_monthly"], 20)

    def test_project_share_totals_remain_bounded_by_twice_the_maximum_fee(self):
        countries = base_countries(fee=1_000_000_000); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg_heavy")
        state = countries["NMG"]
        self.assertLessEqual(state["ywc_nmg_jointproject_contract_own_monthly"] * 60, 2_000_000_000.1)
        self.assertLessEqual(state["ywc_nmg_jointproject_contract_partner_monthly"] * 60, 1_000_000_000.1)

    def test_small_fee_captures_whole_currency_values_shown_in_the_offer(self):
        countries = base_countries(fee=100); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg_heavy")
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_own_monthly"], 2)
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_contract_partner_monthly"], 1)
        countries = base_countries(fee=100); world = NmgPartnerWorld(countries)
        accepted_fixed(world)
        self.assertEqual(countries["NMG"]["ywc_nmg_mexshare_contract_monthly"], 3)

    def test_signed_project_survives_domestic_fallback_and_subject_change(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint")
        countries["MEX"]["in_default"] = True
        for tag in ("NMG", "MEX"): world.run_country_monthly(tag)
        choose_legal(world, "ywc_nmg.1022", "switch_domestic")
        self.assertEqual(countries["NMG"]["ywc_nmg_revenue_route"], 4)
        countries["NMG"].update({"is_subject": False, "overlord": None})
        world.execute(field(world.on_actions["on_become_independent"], "effect"), "NMG")
        countries["MEX"]["in_default"] = False
        world.advance_months(1)
        for tag in ("NMG", "MEX"): world.run_country_monthly(tag)
        self.assertEqual((world.treasury["NMG"], world.treasury["MEX"]), (-20, -20))
        self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_partner_paid_total"], 20)

    def test_midmonth_end_pays_each_side_at_most_sixty_times_in_both_orders(self):
        for order in (("hidden", "pulse"), ("pulse", "hidden")):
            with self.subTest(order=order):
                countries = base_countries(); world = NmgPartnerWorld(countries, date(1836, 1, 15))
                accept_joint(world, "joint_jhg")
                world.advance_days(17)
                for month in range(60):
                    if month: world.advance_months(1)
                    for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                world.advance_days(14)
                for item in order:
                    if item == "hidden": world.run_due_hidden()
                    else:
                        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                state = countries["NMG"]
                self.assertEqual(state["ywc_nmg_jointproject_own_earned_count"], 60)
                self.assertEqual(countries["JHG"]["ywc_nmg_jointproject_provider_earned_count"], 60)
                self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), (-600, -600))
                self.assertEqual(state["ywc_nmg_jointproject_ended_generation"], 1)

    def test_expired_project_arrears_block_renewal_until_partner_really_pays(self):
        countries = base_countries(); world = NmgPartnerWorld(countries, date(1836, 1, 15))
        accept_joint(world, "joint_jhg")
        old_end = next(job for job in world.jobs if job.event_id == "ywc_nmg.1031")
        world.advance_days(17)
        for month in range(60):
            if month: world.advance_months(1)
            if month == 59: countries["JHG"]["in_default"] = True
            for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
        world.advance_days(14); world.run_due_hidden()
        state = countries["NMG"]
        self.assertEqual((state["ywc_nmg_jointproject_partner_earned_total"], state["ywc_nmg_jointproject_partner_paid_total"]), (600, 590))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nmg_jointproject_jhg_eligible"], "NMG"))
        countries["JHG"]["in_default"] = False
        world.advance_months(1); world.run_country_monthly("JHG")
        self.assertEqual(state["ywc_nmg_jointproject_partner_paid_total"], 600)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nmg_jointproject_jhg_eligible"], "NMG"))
        accept_joint(world, "joint_jhg")
        self.assertEqual(state["ywc_nmg_jointproject_contract_generation"], 2)
        with world._chain(old_end.recipient, old_end.saved):
            world.execute(field(world.event_defs[old_end.event_id], "immediate"), "NMG")
        self.assertNotEqual(state.get("ywc_nmg_jointproject_ended_generation"), 2)
        self.assertIn("ywc_nmg_jointproject_term_timer", state)

    def test_live_joint_routes_reach_settlement_with_the_chosen_partner(self):
        for choice, partner in (("joint", "MEX"), ("joint_jhg_heavy", "JHG")):
            with self.subTest(choice=choice):
                countries = base_countries()
                if partner == "JHG":
                    countries["NMG"].update({"is_subject": False, "overlord": None})
                    countries.pop("MEX")
                world, arc = live_revenue_world(countries); handled = set(); seen = []
                sequence = {"1020": choice, "1030": "accept_joint", "1021": "audit_strict",
                            "1022": "close_account_joint", "1023": "project_plan",
                            "1024": "project_record", "1025": "share_even", "1026": "conclude"}
                def select(w, job, choices):
                    number = job.event_id.split(".")[-1]; seen.append((number, job.recipient.tag))
                    if number == "1027": return "settle_full" if choices.get("settle_full") else "wait_retry"
                    return sequence[number]
                for _ in range(50):
                    run_live_month(world, arc, handled, select, (partner,))
                    if world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
                state = world.countries["NMG"]
                self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 3)
                self.assertIn(("1030", partner), seen)
                self.assertGreater(state["ywc_nmg_jointproject_own_paid_total"], 0)
                self.assertGreater(state["ywc_nmg_jointproject_partner_paid_total"], 0)
                self.assertEqual(state["ywc_nmg_jointproject_contract_partner"], world.country_ref(partner))

    def test_live_expired_agreements_can_be_renewed_in_settlement_stage(self):
        for kind in ("fixed", "joint"):
            with self.subTest(kind=kind):
                world, arc = live_revenue_world(); handled = set(); renew_opened = False; menu_seen = False
                partner = "MEX" if kind == "fixed" else "JHG"
                sequence = {"1020": "fixed" if kind == "fixed" else "joint_jhg",
                            "1030": "accept" if kind == "fixed" else "accept_joint",
                            "1021": "audit_strict", "1022": "close_account" if kind == "fixed" else "close_account_joint",
                            "1023": "press_quota" if kind == "fixed" else "project_plan",
                            "1024": "use_temperature" if kind == "fixed" else "project_record",
                            "1025": "carry_heavy" if kind == "fixed" else "share_even", "1026": "conclude"}
                def select(w, job, choices):
                    nonlocal renew_opened, menu_seen
                    number = job.event_id.split(".")[-1]
                    if number == "1027":
                        if choices.get("renew_agreement") and not renew_opened:
                            renew_opened = True
                            return "renew_agreement"
                        if menu_seen and choices.get("settle_full"): return "settle_full"
                        return "wait_retry"
                    if number == "1032":
                        menu_seen = True
                        return "fixed" if kind == "fixed" else "joint_jhg"
                    if number == "1028": return "defer"
                    if number == "1029":
                        if choices.get("renew_agreement") and not renew_opened:
                            renew_opened = True
                            return "renew_agreement"
                        return "wait_retry"
                    return sequence[number]
                for _ in range(110):
                    run_live_month(world, arc, handled, select, (partner,) if kind == "joint" else ())
                    if world.countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
                state = world.countries["NMG"]
                self.assertTrue(renew_opened and menu_seen)
                self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 3)
                prefix = "mexshare" if kind == "fixed" else "jointproject"
                self.assertEqual(state[f"ywc_nmg_{prefix}_contract_generation"], 2)

    def test_notice_renewal_keeps_negotiation_queue_and_old_menu_cannot_replay(self):
        from test_v03_nmg_partner_response import choose
        countries = base_countries(); world = NmgPartnerWorld(countries)
        choose_legal(world, "ywc_nmg.1020", "joint")
        offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "refuse")
        state = countries["NMG"]
        state.update({"ywc_v03_nmg_v03_nmg_autonomy_revenue_started": 1,
                      "ywc_nmg_revenue_stage2": 1, "ywc_nmg_revenue_pending": 1024,
                      "ywc_nmg_revenue_notice_response_context": 1,
                      "ywc_nmg_revenue_notice_return_event": 1024, "ywc_nmg_revenue_last_event": 1029})
        choose_legal(world, "ywc_nmg.1029", "renew_agreement")
        self.assertEqual(state["ywc_nmg_revenue_pending"], 1024)
        self.assertNotIn("ywc_nmg_revenue_notice_response_context", state)
        menu = world.jobs[-1]; self.assertEqual(menu.event_id, "ywc_nmg.1032")
        self.assertTrue(world.display_job(menu)); world.choose_job(menu, "joint_jhg")
        self.assertEqual(state["ywc_nmg_revenue_pending"], 1024)
        inquiry_count = len([j for j in world.jobs if j.event_id == "ywc_nmg.1030"])
        world.choose_job(menu, "joint")  # stale response after the menu serial changed
        self.assertEqual(len([j for j in world.jobs if j.event_id == "ywc_nmg.1030"]), inquiry_count)

    def test_old_renewal_menu_cannot_send_after_settlement_or_stage_change(self):
        for mutation in ("settled", "stage3"):
            with self.subTest(mutation=mutation):
                countries = base_countries(); world = NmgPartnerWorld(countries)
                choose_legal(world, "ywc_nmg.1020", "joint")
                offer = world.jobs[-1]; self.assertTrue(world.display_job(offer)); world.choose_job(offer, "refuse")
                state = countries["NMG"]
                state.update({"ywc_v03_nmg_v03_nmg_autonomy_revenue_started": 1,
                              "ywc_nmg_revenue_stage2": 1, "ywc_nmg_revenue_last_event": 1023})
                choose_legal(world, "ywc_nmg.1023", "renew_agreement")
                menu = world.jobs[-1]; self.assertTrue(world.display_job(menu))
                key = "ywc_v03_nmg_v03_nmg_autonomy_revenue_settled" if mutation == "settled" else "ywc_nmg_revenue_stage3"
                state[key] = 1
                before = len([j for j in world.jobs if j.event_id == "ywc_nmg.1030"])
                world.choose_job(menu, "joint_jhg")
                self.assertEqual(len([j for j in world.jobs if j.event_id == "ywc_nmg.1030"]), before)

    def test_live_held_menu_after_withdrawal_cannot_create_a_new_project(self):
        countries = base_countries()
        countries["NMG"].update({"is_subject": False, "overlord": None})
        countries.pop("MEX")
        world, arc = live_revenue_world(countries); handled = set(); held = None; opened = False
        sequence = {"1020": "joint_jhg", "1030": "accept_joint", "1021": "audit_strict",
                    "1022": "close_account_joint", "1023": "project_plan", "1024": "project_record",
                    "1025": "share_even", "1026": "conclude", "1028": "defer", "1029": "withdraw"}
        def select(w, job, choices):
            nonlocal held, opened
            number = job.event_id.split(".")[-1]
            if number == "1032":
                held = job
                return None
            if number == "1027":
                if choices.get("renew_agreement") and not opened:
                    opened = True
                    return "renew_agreement"
                return "defer" if opened else "wait_retry"
            return sequence[number]
        for _ in range(100):
            run_live_month(world, arc, handled, select, ("JHG",))
            if countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
        self.assertIsNotNone(held)
        self.assertEqual(countries["NMG"].get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 1)
        self.assertFalse(world.job_options(held)["joint_jhg"])
        offers = len([j for j in world.jobs if j.event_id == "ywc_nmg.1030"])
        treasury = (world.treasury["NMG"], world.treasury["JHG"])
        world.choose_job(held, "joint_jhg")
        world.advance_months(1)
        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
        self.assertEqual(len([j for j in world.jobs if j.event_id == "ywc_nmg.1030"]), offers)
        self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), treasury)

    def test_live_lost_fully_paid_jinghai_project_can_switch_to_mexico(self):
        world, arc = live_revenue_world(); handled = set(); removed = False; opened = False
        sequence = {"1020": "joint_jhg", "1030": "accept_joint", "1021": "audit_strict",
                    "1022": "close_account_joint", "1023": "project_plan", "1024": "project_record",
                    "1025": "share_even", "1026": "conclude", "1032": "joint"}
        def select(w, job, choices):
            nonlocal opened
            number = job.event_id.split(".")[-1]
            if number == "1027":
                if choices.get("renew_agreement") and not opened:
                    opened = True
                    return "renew_agreement"
                return "settle_full" if opened and choices.get("settle_full") else "wait_retry"
            if number == "1028": return "defer"
            if number == "1029": return "wait_retry"
            return sequence[number]
        for _ in range(70):
            state = world.countries["NMG"]
            if not removed and state.get("ywc_nmg_revenue_stage3"):
                world.remove_country("JHG")
                removed = True
            run_live_month(world, arc, handled, select, ("MEX",) if removed else ("JHG",))
            if state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_settled"): break
        state = world.countries["NMG"]
        self.assertTrue(removed and opened)
        self.assertEqual(state.get("ywc_v03_nmg_v03_nmg_autonomy_revenue_outcome"), 3)
        self.assertEqual(state["ywc_nmg_jointproject_contract_generation"], 2)
        self.assertEqual(state["ywc_nmg_jointproject_contract_partner"], world.country_ref("MEX"))
        self.assertLess(world.treasury["MEX"], 0)

    def test_first_month_missed_before_anniversary_is_accrued_once_at_endpoint(self):
        for order in (("hidden", "pulse"), ("pulse", "hidden")):
            with self.subTest(order=order):
                countries = base_countries(); world = NmgPartnerWorld(countries, date(1836, 1, 1))
                accept_joint(world, "joint_jhg")
                for _ in range(59):
                    world.advance_months(1)
                    for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                world.advance_months(1)
                for item in order:
                    if item == "hidden": world.run_due_hidden()
                    else:
                        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
                self.assertEqual(countries["NMG"]["ywc_nmg_jointproject_own_earned_count"], 60)
                self.assertEqual(countries["JHG"]["ywc_nmg_jointproject_provider_earned_count"], 60)
                self.assertEqual((world.treasury["NMG"], world.treasury["JHG"]), (-600, -600))

    def test_changed_partner_terms_block_stale_stage_advance(self):
        countries = base_countries(); world = NmgPartnerWorld(countries)
        accept_joint(world, "joint_jhg")
        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
        opening = option(world, "ywc_nmg.1022", "close_account_joint")
        self.assertTrue(world.conditions(field(opening, "trigger"), "NMG"))
        countries["JHG"]["in_default"] = True
        world.advance_months(1)
        for tag in ("NMG", "JHG"): world.run_country_monthly(tag)
        self.assertFalse(world.conditions(field(opening, "trigger"), "NMG"))
        # Selecting an old popup after default must not set stage 2.
        from test_v03_nmg_partner_response import choose
        choose(world, "ywc_nmg.1022", "close_account_joint")
        self.assertNotIn("ywc_nmg_revenue_stage2", countries["NMG"])


if __name__ == "__main__":
    unittest.main()

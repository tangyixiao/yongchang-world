"""Regression cases for real NQG port-treaty terms and partner decisions."""
import unittest
from datetime import date
import copy
import json
from pathlib import Path

from kor_partner_protocol_runtime import _add_months
from shu_kor_strict_review_runtime import field
from test_v03_nqg_aid_response import NqgAidWorld, option_body
from test_v03_nqg_port_response import base_countries, port_world, run_option, signed_lease


class NqgPortFactsWorld(NqgAidWorld):
    def condition(self, node, tag):
        key, operator, value = node
        if key == "government_legitimacy":
            return self.compare(self.countries[tag][key], operator, float(value))
        return super().condition(node, tag)


class NqgPortRegressions(unittest.TestCase):
    def test_free_hold_requires_previously_paid_escort_on_this_lease(self):
        world, countries = port_world()
        signed_lease(world)
        before = len(world.jobs)
        option = option_body(world, "ywc_nqg.1023", "hold_terms")
        self.assertFalse(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([n for n in option if n[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertEqual(len(world.jobs), before)
        self.assertNotIn("ywc_nqg_port_treaty_escort_ready", countries["NQG"])
        self.assertEqual((world.treasury["NQG"], world.treasury["RUS"]), (0, 0))

    def test_midmonth_lease_and_amendment_last_their_full_captured_terms(self):
        for amended, years in ((False, 10), (True, 5)):
            with self.subTest(amended=amended):
                world, countries = port_world()
                world.run_country_monthly("NQG")
                world.advance_days(14)
                signed_lease(world)
                if amended:
                    offer = run_option(world, "ywc_nqg.1026", "amend")
                    self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
                world.advance_days((date(1836 + years, 1, 1) - world.date).days)
                world.run_country_monthly("NQG")
                self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
                world.advance_days(14)
                world.run_due_hidden()
                self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_land_adjacent_partner_can_be_invited_without_a_coastal_port(self):
        world, countries = port_world()
        countries["RUS"]["states"][0]["port"] = False
        for building in countries["RUS"]["states"][0]["buildings"]:
            if building["type"] == "building_port": building["occupancy"] = 0.1
        world.market_ref("m_RUS")
        world.markets["m_RUS"]["adjacent"].add("m_NQG")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_can_offer_rus"], "NQG"))
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_partner_market_change_suspends_and_only_the_same_market_recovers(self):
        world, countries = port_world()
        signed_lease(world)
        partner = countries["RUS"]
        market = partner.get("market", "m_RUS")
        partner["market"] = "m_other"
        world.run_country_monthly("NQG")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_lease_suspended_generation"], 1)
        partner["market"] = market
        world.run_country_monthly("NQG")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_partner_market_change_invalidates_the_displayed_offer(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))
        countries["RUS"]["market"] = "m_replaced"
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_state"], 5)

    def test_becoming_subject_invalidates_an_unsigned_port_offer_immediately(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["is_subject"] = True
        world.run_on_action("on_become_subject", "NQG")
        countries["NQG"]["is_subject"] = False
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])

    def test_becoming_subject_preserves_a_signed_lease_ledger(self):
        world, countries = port_world(); signed_lease(world)
        countries["NQG"]["is_subject"] = True
        world.run_on_action("on_become_subject", "NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_generation"], 1)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_partner"], world.country_ref("RUS"))

    def test_different_partner_port_cannot_substitute_for_captured_capacity(self):
        world, countries = port_world()
        signed_lease(world)
        first = countries["RUS"]["states"][0]
        second = copy.deepcopy(first); second.pop("_sid")
        countries["RUS"]["states"].append(second); world._register_states("RUS")
        first["port"] = False
        for building in first["buildings"]:
            if building["type"] == "building_port": building["occupancy"] = 0.1
        world.run_country_monthly("NQG")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_lease_suspended_generation"], 1)
        first["port"] = True
        for building in first["buildings"]:
            if building["type"] == "building_port": building["occupancy"] = 0.8
        world.run_country_monthly("NQG")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_port_narrative_matches_payment_and_preserves_sovereignty(self):
        data = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        events = {e["id"]: e for arc in data["arcs"] for e in arc["events"]}
        reply = next(o for o in events["ywc_nqg.1028"]["options"] if o["key"] == "accept")
        self.assertIn("transferred", reply["cost_note"]["en"].lower())
        self.assertIn("insufficient", reply["cost_note"]["en"].lower())
        self.assertIn("不会自动改变主权", events["ywc_nqg.1024"]["desc"]["zh"])
        self.assertIn("before", events["ywc_nqg.1026"]["desc"]["en"].lower())

    def test_local_port_choices_do_not_claim_unimplemented_economic_effects(self):
        data = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        events = {e["id"]: e for arc in data["arcs"] for e in arc["events"]}
        for event_id, key in (("ywc_nqg.1020", "open_berths"), ("ywc_nqg.1020", "high_duty"),
                              ("ywc_nqg.1021", "by_tonnage"), ("ywc_nqg.1021", "by_call")):
            option = next(o for o in events[event_id]["options"] if o["key"] == key)
            with self.subTest(event=event_id, option=key):
                self.assertIn("record", option["consequence_note"]["en"].lower())
                self.assertNotRegex(option["consequence_note"]["en"].lower(), r"revenue rises|pay more|\bgain\b|higher administrative cost")

    def test_foreign_reply_shows_the_saved_port_and_numeric_offer_terms(self):
        data = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        event = next(e for arc in data["arcs"] for e in arc["events"] if e["id"] == "ywc_nqg.1028")
        for language in ("zh", "en"):
            text = event["desc"][language]
            self.assertIn("SCOPE.sState('ywc_nqg_port_treaty_request_port').GetName", text)
            for name in ("kind", "berth", "duty", "term", "cost"):
                self.assertIn("SCOPE.GetValue('ywc_nqg_port_treaty_request_" + name + "')", text)

    def test_foreign_ai_response_weights_read_relations_and_finances(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))

        def weight(key):
            nodes = field(option_body(world, "ywc_nqg.1028", key), "ai_chance")
            result = float(field(nodes, "base"))
            with world._chain(offer.recipient, world._displayed[offer]):
                for name, _, modifier in nodes:
                    if name == "modifier" and world.conditions(field(modifier, "trigger"), "RUS"):
                        result += float(field(modifier, "add"))
            return result

        low_relation = weight("accept")
        countries["RUS"]["relations"]["NQG"] = 60
        self.assertGreater(weight("accept"), low_relation)
        normal_refusal = weight("refuse")
        countries["RUS"]["net_fixed_income"] = -1
        self.assertGreater(weight("refuse"), normal_refusal)

    def test_old_offer_cannot_accept_changed_captured_terms(self):
        for field_name in ("ywc_nqg_port_treaty_quote_berth", "ywc_nqg_port_treaty_quote_duty",
                           "ywc_nqg_port_treaty_quote_term", "ywc_nqg_port_treaty_quote_cost",
                           "ywc_nqg_port_treaty_quote_serial"):
            with self.subTest(field=field_name):
                world, countries = port_world()
                offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
                self.assertTrue(world.display_job(offer))
                countries["NQG"][field_name] += 1
                self.assertFalse(world.job_options(offer)["accept"])
                world.choose_job(offer, "accept")
                self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])

    def test_status_serial_is_bound_to_reply_and_changes_only_on_transition(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertIn("ywc_nqg_port_treaty_request_serial", dict(offer.saved))
        self.assertEqual(dict(offer.saved)["ywc_nqg_port_treaty_request_serial"], 1)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_serial"], 3)
        self.assertEqual(countries["RUS"]["ywc_nqg_port_treaty_answer_serial"], 1)
        world.choose_job(offer, "accept")
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_serial"], 3)

    def test_lease_offer_captures_the_actual_port_state_and_market(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        captured = dict(offer.saved)
        self.assertIn("ywc_nqg_port_treaty_request_port", captured)
        self.assertIn("ywc_nqg_port_treaty_request_market", captured)
        self.assertEqual(captured["ywc_nqg_port_treaty_request_port"].sid,
                         countries["NQG"]["states"][0]["_sid"])

    def test_displayed_offer_cannot_retarget_after_port_owner_or_market_changes(self):
        for change in ("owner", "market"):
            with self.subTest(change=change):
                world, countries = port_world()
                offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
                self.assertTrue(world.display_job(offer))
                port = countries["NQG"]["states"][0]
                port[change] = "JHG" if change == "owner" else "different_market"
                self.assertFalse(world.job_options(offer)["accept"])
                world.choose_job(offer, "accept")
                self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])

    def test_each_eligible_port_partner_can_be_selected(self):
        for option, tag in (("exclusive_lease", "RUS"), ("exclusive_lease_jap", "JAP"),
                            ("exclusive_lease_jhg", "JHG")):
            with self.subTest(partner=tag):
                world, _ = port_world()
                keys = {field(body, "name").rsplit(".", 1)[-1]
                        for name, _, body in world.event_defs["ywc_nqg.1020"] if name == "option"}
                self.assertIn(option, keys)
                offer = run_option(world, "ywc_nqg.1020", option)
                self.assertEqual(offer.recipient.tag, tag)

    def test_reopened_opening_can_switch_a_paid_domestic_route_to_the_selected_lease(self):
        world, countries = port_world()
        countries["NQG"]["ywc_nqg_port_route"] = 1
        countries["NQG"]["gold_reserves"] = 0
        option = option_body(world, "ywc_nqg.1020", "exclusive_lease_jap")
        self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_route"], 2)
        self.assertEqual(len([job for job in world.jobs if job.event_id == "ywc_nqg.1028"]), 1)
        self.assertEqual(world.jobs[-1].recipient.tag, "JAP")
        self.assertEqual(world.treasury["NQG"], 0)

    def test_live_lease_cannot_be_replaced_with_another_initial_offer(self):
        world, countries = port_world()
        signed_lease(world)
        original = countries["NQG"]["ywc_nqg_port_treaty_contract_partner"]
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_can_offer_rus"], "NQG"))
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_partner"], original)

    def test_recreated_country_tag_does_not_rebind_a_signed_lease(self):
        world, countries = port_world()
        signed_lease(world)
        old_partner = countries["NQG"]["ywc_nqg_port_treaty_contract_partner"]
        replacement = base_countries()["RUS"]
        world.remove_country("RUS")
        world.run_country_monthly("NQG")
        world.add_country("RUS", replacement)
        self.assertNotEqual(old_partner, world.country_ref("RUS"))
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_lease_suspended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_another_staffed_port_cannot_replace_the_captured_port(self):
        world, countries = port_world()
        signed_lease(world)
        first = countries["NQG"]["states"][0]
        second = copy.deepcopy(first)
        second.pop("_sid")
        countries["NQG"]["states"].append(second)
        world._register_states("NQG")
        for building in first["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_lease_suspended_generation"], 1)
        for building in first["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.8
        world.run_country_monthly("NQG")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_stale_opening_does_not_overwrite_the_active_lease_or_current_queue(self):
        world, countries = port_world()
        signed_lease(world)
        countries["NQG"]["ywc_nqg_port_pending"] = 1026
        countries["NQG"]["ywc_nqg_port_stage"] = 1026
        previous_jobs = len(world.jobs)
        run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertEqual(len(world.jobs), previous_jobs)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_pending"], 1026)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_stage"], 1026)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_partner"], world.country_ref("RUS"))

    def test_paid_escort_terms_transfer_once_to_the_actual_counterpart(self):
        world, countries = port_world()
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(world.treasury["NQG"], -300)
        self.assertEqual(world.treasury["RUS"], 300)
        world.choose_job(offer, "accept")
        world.run_country_monthly("NQG")
        self.assertEqual(world.treasury["NQG"], -300)
        self.assertEqual(world.treasury["RUS"], 300)

    def test_accepted_escort_waits_for_funds_and_keeps_the_old_lease(self):
        world, countries = port_world()
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["gold_reserves"] = 0
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_escort_ready", countries["NQG"])
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        self.assertEqual(world.treasury["NQG"], 0)
        countries["NQG"]["gold_reserves"] = 100000
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_escort_ready"], 1)
        self.assertEqual(world.treasury["NQG"], -300)
        self.assertEqual(world.treasury["RUS"], 300)
        world.choose_job(offer, "accept")
        world.run_country_monthly("NQG")
        self.assertEqual(world.treasury["NQG"], -300)
        self.assertEqual(world.treasury["RUS"], 300)

    def test_confirming_paid_escort_terms_does_not_charge_again(self):
        world, _ = port_world()
        signed_lease(world)
        first = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(first))
        world.choose_job(first, "accept")
        second = run_option(world, "ywc_nqg.1023", "hold_terms")
        self.assertTrue(world.display_job(second))
        world.choose_job(second, "accept")
        self.assertEqual(world.treasury["NQG"], -300)
        self.assertEqual(world.treasury["RUS"], 300)

    def test_stale_renewal_does_not_claim_or_advance_a_lapsed_lease(self):
        world, countries = port_world()
        signed_lease(world)
        world.advance_months(120)
        world.run_country_monthly("NQG")
        countries["NQG"]["ywc_nqg_port_pending"] = 1026
        countries["NQG"]["ywc_nqg_port_stage"] = 1026
        option = option_body(world, "ywc_nqg.1026", "renew")
        self.assertFalse(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertNotIn("ywc_nqg_port_st1026_renew", countries["NQG"])
        self.assertEqual(countries["NQG"]["ywc_nqg_port_pending"], 1026)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_stage"], 1026)

    def test_pending_renewal_cannot_be_settled_as_an_accepted_lease(self):
        world, countries = port_world()
        signed_lease(world)
        countries["NQG"]["ywc_nqg_port_six_months_complete"] = 1
        full = world.trigger_defs["ywc_nqg_port_full_ready"]
        self.assertTrue(world.conditions(full, "NQG"))
        offer = run_option(world, "ywc_nqg.1026", "renew")
        self.assertTrue(world.display_job(offer))
        self.assertFalse(world.conditions(full, "NQG"))
        world.choose_job(offer, "accept")
        self.assertTrue(world.conditions(full, "NQG"))

    def test_amended_lease_schedules_its_hidden_endpoint_at_sixty_months(self):
        world, countries = port_world()
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1026", "amend")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        generation = countries["NQG"]["ywc_nqg_port_treaty_contract_generation"]
        endpoint = next(job for job in world.jobs if job.event_id == "ywc_nqg.1029"
                        and dict(job.saved)["ywc_nqg_port_treaty_end_generation"] == generation)
        self.assertEqual(endpoint.due_day, (_add_months(date(1836, 1, 1), 60) - date(1836, 1, 1)).days)

    def test_old_due_endpoint_cannot_end_a_renewed_lease(self):
        world, countries = port_world()
        signed_lease(world)
        world.advance_months(60)
        world.run_country_monthly("NQG")
        offer = run_option(world, "ywc_nqg.1026", "renew")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_generation"], 2)
        world.advance_months(60)
        world.run_due_hidden()
        world.run_country_monthly("NQG")
        self.assertNotIn("ywc_nqg_port_treaty_lease_ended_generation", countries["NQG"])
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_refusal_offers_actual_domestic_multi_berth_and_high_duty_switches(self):
        for key, route in (("switch_open_berths", 1), ("switch_high_duty", 3)):
            with self.subTest(route=route):
                countries = base_countries()
                countries["NQG"]["laws"].append("law_isolationism")
                countries["NQG"]["government_legitimacy"] = 50
                world = NqgPortFactsWorld(countries)
                offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
                self.assertTrue(world.display_job(offer))
                world.choose_job(offer, "refuse")
                keys = {field(body, "name").rsplit(".", 1)[-1]
                        for name, _, body in world.event_defs["ywc_nqg.1023"] if name == "option"}
                self.assertIn(key, keys)
                option = option_body(world, "ywc_nqg.1023", key)
                self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
                world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
                self.assertEqual(countries["NQG"]["ywc_nqg_port_route"], route)
                self.assertEqual(countries["NQG"]["ywc_nqg_port_fee_paid"], 1)
                self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_route_execution_ready"], "NQG"))

    def test_refusal_can_switch_from_reopened_opening_without_a_second_fee(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        countries["NQG"]["gold_reserves"] = 0
        option = option_body(world, "ywc_nqg.1020", "open_berths")
        self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_route"], 1)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_fee_paid"], 1)
        self.assertEqual(world.treasury["NQG"], 0)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_route_execution_ready"], "NQG"))

    def test_pending_escort_answer_cannot_be_counted_as_recognised_terms(self):
        world, countries = port_world()
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["ywc_nqg_port_pending"] = 1024
        countries["NQG"]["ywc_nqg_port_stage"] = 1024
        option = option_body(world, "ywc_nqg.1024", "recognise_duties")
        self.assertFalse(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertNotIn("ywc_nqg_port_st1024_recognise_duties", countries["NQG"])
        self.assertEqual(countries["NQG"]["ywc_nqg_port_pending"], 1024)

    def test_declining_the_pending_terms_invalidates_the_old_foreign_reply(self):
        world, countries = port_world()
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(offer))
        option = option_body(world, "ywc_nqg.1024", "decline_terms")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_escort_ready", countries["NQG"])
        self.assertEqual(world.treasury["NQG"], 0)
        self.assertEqual(world.treasury["RUS"], 0)

    def test_withdrawing_cancels_unsigned_work_but_keeps_the_signed_lease(self):
        world, countries = port_world()
        countries["NQG"].update({"ywc_v03_nqg_v03_nqg_northern_port_started": 1,
                                  "ywc_v03_active_arc_count": 1,
                                  "ywc_v03_visible_task_count": 1})
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(offer))
        option = option_body(world, "ywc_nqg.1023", "withdraw")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_escort_ready", countries["NQG"])
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_partner"], world.country_ref("RUS"))
        self.assertEqual(world.treasury["NQG"], 0)
        self.assertEqual(world.treasury["RUS"], 0)

    def test_partner_losing_staff_and_market_access_cannot_accept(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))
        for building in countries["RUS"]["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])

    def test_unpaid_escort_cannot_sign_after_partner_loses_capacity(self):
        world, countries = port_world()
        signed_lease(world)
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["gold_reserves"] = 0
        world.choose_job(offer, "accept")
        for building in countries["RUS"]["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        countries["NQG"]["gold_reserves"] = 100000
        world.run_country_monthly("NQG")
        self.assertNotIn("ywc_nqg_port_treaty_escort_ready", countries["NQG"])
        self.assertEqual(world.treasury["NQG"], 0)
        self.assertEqual(world.treasury["RUS"], 0)

    def test_subject_transition_cannot_sign_a_displayed_lease_offer(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["is_subject"] = True
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])
        world.run_country_monthly("NQG")
        self.assertNotIn("ywc_nqg_port_treaty_request_timer", countries["NQG"])
        countries["NQG"]["is_subject"] = False
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", countries["NQG"])

    def test_subject_transition_cancels_renewal_but_preserves_existing_lease(self):
        world, countries = port_world()
        signed_lease(world)
        renewal = run_option(world, "ywc_nqg.1026", "renew")
        self.assertTrue(world.display_job(renewal))
        countries["NQG"]["is_subject"] = True
        world.choose_job(renewal, "accept")
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_generation"], 1)
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_partner"], world.country_ref("RUS"))
        self.assertNotIn("ywc_nqg_port_treaty_request_timer", countries["NQG"])


if __name__ == "__main__":
    unittest.main()

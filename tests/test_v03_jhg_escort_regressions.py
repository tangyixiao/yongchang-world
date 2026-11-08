"""Regression checks for actual escort terms and their payment."""
import json
import unittest
from pathlib import Path

from kor_partner_protocol_runtime import UnsupportedSubset
from shu_kor_strict_review_runtime import field
from test_v03_jhg_escort_response import JhgWorld, base_countries, option_body, run_option, signed_partnership


class JhgEscortRegressionTests(unittest.TestCase):
    def test_limited_shared_route_does_not_accept_an_uncontracted_generic_ally(self):
        from test_v03_jhg_foundation import EFFECTS_PATH, JhgTerminalWorld
        state = {"ywc_jhg_convoy_route": 2, "navy_size": 5,
                 "engine_partners": [{"diplomatic_pacts": ["alliance"],
                                      "relations_to_root": 60, "army_size": 5}]}
        world = JhgTerminalWorld(EFFECTS_PATH.read_text(encoding="utf-8-sig"), {"JHG": state})
        self.assertFalse(world.conditions(world.triggers["ywc_jhg_convoy_limited_route_execution_ready"], "JHG"))

    def test_limited_shared_route_accepts_the_actual_signed_partner(self):
        world = JhgWorld(base_countries())
        signed_partnership(world)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_convoy_limited_route_execution_ready"], "JHG"))

    def test_late_settlement_exposes_guarded_domestic_fallbacks(self):
        world = JhgWorld(base_countries())
        signed_partnership(world)
        world.active["JHG"].append("ywc_je_v03_jhg_convoy_settlement")
        for key in ("switch_main_lane", "switch_insurance"):
            option = option_body(world, "ywc_jhg.1018", key)
            self.assertTrue(world.conditions(field(option, "trigger"), "JHG"), key)

    def test_stale_domestic_choice_on_notice_preserves_the_normal_queue(self):
        countries = base_countries()
        world = JhgWorld(countries)
        world.active["JHG"].append("ywc_je_v03_jhg_convoy_settlement")
        state = countries["JHG"]
        state.update({"ywc_jhg_convoy_route": 1, "ywc_jhg_convoy_pending_event": 1016,
                      "ywc_jhg_convoy_notice_delivery_active": 1, "ywc_jhg_convoy_notice_delivery_12": 1})
        option = option_body(world, "ywc_jhg.1018", "switch_insurance")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        self.assertEqual(state["ywc_jhg_convoy_pending_event"], 1016)
        self.assertNotIn("ywc_jhg_convoy_notice_delivery_active", state)
        self.assertNotIn("ywc_jhg_convoy_notice_delivery_12", state)

    def test_replacement_contract_cannot_inherit_an_old_partner_watch(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        state = countries["JHG"]
        state["ywc_jhg_convoy_six_months_complete"] = 1
        world.advance_months(120)
        world.run_country_monthly("JHG")
        offer = run_option(world, "ywc_jhg.1012", "request_dmg")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_two_ready"], "JHG"))
        world.advance_days(179)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_two_ready"], "JHG"))
        world.advance_days(1)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_two_ready"], "JHG"))

    def test_domestic_disruption_still_clears_the_completed_watch(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        state = countries["JHG"]
        state["ywc_jhg_convoy_six_months_complete"] = 1
        countries["LAN"]["navy_size"] = 0
        for building in countries["LAN"]["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        state["navy_size"] = 0
        world.run_country_monthly("JHG")
        world.run("ywc_jhg_convoy_invalidate_stale_watch", "JHG")
        self.assertNotIn("ywc_jhg_convoy_six_months_complete", state)

    def test_become_subject_callback_invalidates_an_unsigned_escort_before_it_can_revert(self):
        countries = base_countries()
        countries["SHU"] = dict(countries["LAN"])
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        countries["JHG"].update({"is_subject": True, "overlord": "SHU"})
        world.execute(field(world.on_actions["on_become_subject"], "effect"), "JHG")
        countries["JHG"]["is_subject"] = False
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual((world.treasury["JHG"], world.treasury["LAN"]), (0, 0))

    def test_first_blocked_month_does_not_require_a_preseeded_counter(self):
        countries = base_countries()
        countries["JHG"]["ywc_jhg_convoy_route"] = 0
        world = JhgWorld(countries)
        try:
            world.run("ywc_jhg_convoy_monthly_review", "JHG")
        except UnsupportedSubset as exc:
            self.fail(f"the first blocked month must initialize its counter: {exc}")
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_blocked_months"], 1)

    def test_court_and_convoy_hold_choices_do_not_add_a_second_blocked_month(self):
        for stem, event_id in (("court", "ywc_jhg.1006"), ("convoy", "ywc_jhg.1017")):
            with self.subTest(stem=stem):
                countries = base_countries()
                countries["JHG"][f"ywc_jhg_{stem}_route"] = 0
                world = JhgWorld(countries)
                world.run(f"ywc_jhg_{stem}_monthly_review", "JHG")
                state = countries["JHG"]
                self.assertEqual(state[f"ywc_jhg_{stem}_blocked_months"], 1)
                option = option_body(world, event_id, "hold_course")
                world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
                self.assertEqual(state[f"ywc_jhg_{stem}_blocked_months"], 1)

    def test_saved_numeric_dispatch_values_exist_even_when_zero(self):
        world = JhgWorld(base_countries())
        with world._chain(world.country_ref("JHG"), (("positive", 20), ("zero", 0))):
            self.assertTrue(world.condition(("exists", "=", "scope:positive"), "JHG"))
            self.assertTrue(world.condition(("exists", "=", "scope:zero"), "JHG"))
            self.assertFalse(world.condition(("exists", "=", "scope:missing"), "JHG"))

    def test_new_escort_events_name_jinghai_in_both_languages(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        events = [event for arc in catalog["arcs"] for event in arc["events"]
                  if event["id"] in {"ywc_jhg.1030", "ywc_jhg.1031"}]
        self.assertEqual(len(events), 2)
        text = json.dumps(events, ensure_ascii=False)
        self.assertNotIn("准噶尔", text)
        self.assertNotIn("Dzungar", text)
        self.assertIn("靖海", text)
        self.assertIn("Jinghai", text)

    def test_offer_explains_its_duration_coverage_and_cost_in_both_languages(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        event = next(event for arc in catalog["arcs"] for event in arc["events"]
                     if event["id"] == "ywc_jhg.1030")
        for language, half in (("zh", "一半"), ("en", "half")):
            with self.subTest(language=language):
                text = event["desc"][language].lower()
                self.assertIn("120", text)
                self.assertIn("2", text)
                self.assertIn(half, text)
                self.assertIn("SCOPE.GetValue('ywc_jhg_escort_request_cost')".lower(), text)

    def test_opening_discloses_the_actual_filing_fee_formula(self):
        catalog = json.loads(Path("data/content/v03/countries/jhg.json").read_text(encoding="utf-8"))
        event = next(event for arc in catalog["arcs"] for event in arc["events"] if event["id"] == "ywc_jhg.1010")
        for option in event["options"]:
            if option["key"] not in ("shared_escort", "shared_escort_dmg"):
                continue
            for lang in ("zh", "en"):
                for term in ("52", "100", "1,000,000,000"):
                    self.assertIn(term, option["cost_note"][lang], (option["key"], lang, term))

    def test_signed_cost_is_transferred_once_to_the_actual_partner(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = signed_partnership(world)
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)
        self.assertEqual(world.treasury["DMG"], 0)
        world.choose_job(offer, "accept")
        world.run_country_monthly("JHG")
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)

    def test_cannot_sign_or_pay_until_the_captured_cost_is_affordable(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        countries["JHG"]["gold_reserves"] = 0
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)
        countries["JHG"]["gold_reserves"] = 100000
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_generation"], 1)
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)

    def test_live_or_suspended_contract_blocks_replacement_until_its_term_ends(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        can_offer = world.trigger_defs["ywc_jhg_escort_can_offer_dmg"]
        self.assertFalse(world.conditions(can_offer, "JHG"))
        world.remove_country("LAN")
        world.run_country_monthly("JHG")
        self.assertFalse(world.conditions(can_offer, "JHG"))
        world.advance_months(120)
        world.run_country_monthly("JHG")
        self.assertTrue(world.conditions(can_offer, "JHG"))

    def test_late_old_endpoint_cannot_end_a_new_generation(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        world.advance_months(120)
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_ended_generation"], 1)
        second = run_option(world, "ywc_jhg.1012", "request_dmg")
        self.assertTrue(world.display_job(second))
        world.choose_job(second, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_generation"], 2)
        world.run_due_hidden()
        self.assertNotIn("ywc_jhg_escort_ended_generation", countries["JHG"])
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        self.assertEqual(world.treasury["JHG"], -600)
        self.assertEqual(world.treasury["LAN"], 300)
        self.assertEqual(world.treasury["DMG"], 300)

    def test_same_generation_serial_tracks_real_status_changes_once(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertIn("ywc_jhg_escort_request_serial", dict(offer.saved))
        self.assertEqual(dict(offer.saved)["ywc_jhg_escort_request_serial"], 1)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_serial"], 3)
        self.assertIn("ywc_jhg_escort_answer_serial", countries["LAN"])
        self.assertEqual(countries["LAN"]["ywc_jhg_escort_answer_serial"], 1)
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_offer_serial"], 1)
        world.choose_job(offer, "accept")
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_serial"], 3)
        countries["LAN"]["navy_size"] = 0
        for building in countries["LAN"]["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        world.run_country_monthly("JHG")
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_serial"], 4)
        countries["LAN"]["navy_size"] = 5
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_serial"], 5)
        world.advance_months(120)
        world.run_country_monthly("JHG")
        world.run_due_hidden()
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_serial"], 6)

    def test_changed_quote_cannot_be_accepted_using_an_old_event(self):
        for changed in ("ywc_jhg_escort_quote_cost", "ywc_jhg_escort_quote_term",
                        "ywc_jhg_escort_quote_lanes", "ywc_jhg_escort_quote_serial"):
            with self.subTest(changed=changed):
                countries = base_countries()
                world = JhgWorld(countries)
                offer = run_option(world, "ywc_jhg.1010", "shared_escort")
                self.assertTrue(world.display_job(offer))
                countries["JHG"][changed] += 1
                self.assertFalse(world.job_options(offer)["accept"])
                world.choose_job(offer, "accept")
                self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
                self.assertEqual(world.treasury["JHG"], 0)
                self.assertEqual(world.treasury["LAN"], 0)

    def test_partner_requires_a_navy_or_an_operating_staffed_port(self):
        countries = base_countries()
        for tag in ("LAN", "DMG"):
            countries[tag]["navy_size"] = 0
            for building in countries[tag]["states"][0]["buildings"]:
                if building["type"] == "building_port":
                    building["occupancy"] = 0.1
        world = JhgWorld(countries)
        eligible_lan = world.trigger_defs["ywc_jhg_escort_can_offer_lan"]
        eligible_dmg = world.trigger_defs["ywc_jhg_escort_can_offer_dmg"]
        self.assertFalse(world.conditions(eligible_lan, "JHG"))
        self.assertFalse(world.conditions(eligible_dmg, "JHG"))
        for building in countries["LAN"]["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 1
        self.assertTrue(world.conditions(eligible_lan, "JHG"))
        self.assertFalse(world.conditions(eligible_dmg, "JHG"))

    def test_stale_opening_choice_cannot_charge_without_an_eligible_partner(self):
        countries = base_countries()
        for tag in ("LAN", "DMG"):
            countries[tag]["navy_size"] = 0
            countries[tag]["states"][0]["port"] = False
            for building in countries[tag]["states"][0]["buildings"]:
                if building["type"] == "building_port":
                    building["occupancy"] = 0.1
        countries["JHG"].pop("ywc_jhg_convoy_filing_fee_paid")
        countries["JHG"]["ywc_jhg_convoy_route"] = 0
        world = JhgWorld(countries)
        option = option_body(world, "ywc_jhg.1010", "shared_escort")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_route"], 0)
        self.assertNotIn("ywc_jhg_convoy_filing_fee_paid", countries["JHG"])
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_pending_event"], 1010)

    def test_player_can_choose_either_eligible_partner(self):
        for key, target in (("shared_escort", "LAN"), ("shared_escort_dmg", "DMG")):
            with self.subTest(target=target):
                countries = base_countries()
                world = JhgWorld(countries)
                keys = {field(body, "name").rsplit(".", 1)[-1]
                        for name, _, body in world.event_defs["ywc_jhg.1010"] if name == "option"}
                self.assertIn(key, keys)
                offer = run_option(world, "ywc_jhg.1010", key)
                self.assertEqual(offer.recipient.tag, target)

    def test_refused_shared_route_cannot_advance_as_if_a_contract_exists(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        option = option_body(world, "ywc_jhg.1012", "shared_escort")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_pending_event"], 1012)
        self.assertNotIn("ywc_jhg_convoy_negotiated_shared_escort", countries["JHG"])

    def test_refusal_offers_real_single_lane_and_insurance_choices(self):
        for key, route in (("main_lane", 1), ("insurance", 3)):
            with self.subTest(route=route):
                countries = base_countries()
                world = JhgWorld(countries)
                offer = run_option(world, "ywc_jhg.1010", "shared_escort")
                self.assertTrue(world.display_job(offer))
                world.choose_job(offer, "refuse")
                keys = {field(body, "name").rsplit(".", 1)[-1]
                        for name, _, body in world.event_defs["ywc_jhg.1012"] if name == "option"}
                self.assertIn(key, keys)
                option = option_body(world, "ywc_jhg.1012", key)
                self.assertTrue(world.conditions(field(option, "trigger"), "JHG"))
                world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
                self.assertEqual(countries["JHG"]["ywc_jhg_convoy_route"], route)
                self.assertEqual(countries["JHG"]["ywc_jhg_convoy_pending_event"], 1013)
                self.assertEqual(countries["JHG"]["ywc_jhg_convoy_filing_fee_paid"], 1)

    def test_partner_or_insurance_path_does_not_require_an_owned_staffed_port_at_1011(self):
        for answer, key, route in (("accept", "shared_escort", 2), ("refuse", "insurance", 3)):
            with self.subTest(answer=answer):
                countries = base_countries()
                for building in countries["JHG"]["states"][0]["buildings"]:
                    if building["type"] == "building_port":
                        building["occupancy"] = 0.1
                world = JhgWorld(countries)
                offer = run_option(world, "ywc_jhg.1010", "shared_escort")
                self.assertTrue(world.display_job(offer))
                world.choose_job(offer, answer)
                keys = {field(body, "name").rsplit(".", 1)[-1]
                        for name, _, body in world.event_defs["ywc_jhg.1011"] if name == "option"}
                self.assertIn(key, keys)
                option = option_body(world, "ywc_jhg.1011", key)
                self.assertTrue(world.conditions(field(option, "trigger"), "JHG"))
                world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
                self.assertEqual(countries["JHG"]["ywc_jhg_convoy_route"], route)
                self.assertEqual(countries["JHG"]["ywc_jhg_convoy_pending_event"], 1012)
                self.assertEqual(countries["JHG"]["ywc_jhg_convoy_filing_fee_paid"], 1)

    def test_replaced_lan_dmg_lan_offers_reject_old_answer_jobs(self):
        countries = base_countries()
        world = JhgWorld(countries)
        first = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(first))
        world.choose_job(first, "refuse")
        second = run_option(world, "ywc_jhg.1012", "request_dmg")
        self.assertEqual(second.recipient.tag, "DMG")
        self.assertTrue(world.display_job(second))
        world.choose_job(second, "refuse")
        third = run_option(world, "ywc_jhg.1012", "request_lan")
        self.assertEqual(third.recipient.tag, "LAN")
        self.assertTrue(world.display_job(third))
        world.choose_job(first, "accept")
        world.choose_job(second, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_state"], 1)
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        world.choose_job(third, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_generation"], 3)
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)

    def test_confirming_a_signed_partnership_neither_sends_nor_pays_again(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        existing_jobs = list(world.jobs)
        option = option_body(world, "ywc_jhg.1012", "shared_escort")
        self.assertTrue(world.conditions(field(option, "trigger"), "JHG"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        self.assertEqual(world.jobs, existing_jobs)
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_pending_event"], 1013)

    def test_changing_to_insurance_cancels_an_accepted_but_unpaid_offer(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        countries["JHG"]["gold_reserves"] = 0
        world.choose_job(offer, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_state"], 2)
        countries["JHG"]["gold_reserves"] = 100000
        option = option_body(world, "ywc_jhg.1012", "insurance")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        world.run_country_monthly("JHG")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_route"], 3)
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)

    def test_reopened_opening_cancels_an_unsigned_offer_before_switching_routes(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        option = option_body(world, "ywc_jhg.1010", "insurance")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        world.choose_job(offer, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_convoy_route"], 3)
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)

    def test_withdrawing_the_arc_cancels_an_unanswered_offer(self):
        countries = base_countries()
        countries["JHG"].update({"ywc_jhg_v03_jhg_convoy_capacity_started": 1,
                                  "ywc_v03_active_arc_count": 1,
                                  "ywc_v03_visible_task_count": 1})
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        option = option_body(world, "ywc_jhg.1012", "withdraw")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertNotIn("ywc_jhg_escort_request_timer", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)

    def test_withdrawing_preserves_a_signed_and_paid_partnership(self):
        countries = base_countries()
        countries["JHG"].update({"ywc_jhg_v03_jhg_convoy_capacity_started": 1,
                                  "ywc_v03_active_arc_count": 1,
                                  "ywc_v03_visible_task_count": 1})
        world = JhgWorld(countries)
        signed_partnership(world)
        option = option_body(world, "ywc_jhg.1012", "withdraw")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_generation"], 1)
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)

    def test_subject_transition_cancels_unsigned_inquiry(self):
        for old_subject in (False, True):
            with self.subTest(old_subject=old_subject):
                countries = base_countries()
                countries["JHG"]["is_subject"] = old_subject
                if old_subject:
                    countries["SHU"] = base_countries()["JHG"]
                    countries["JHG"]["overlord"] = "SHU"
                world = JhgWorld(countries)
                offer = run_option(world, "ywc_jhg.1010", "shared_escort")
                self.assertTrue(world.display_job(offer))
                countries["JHG"]["is_subject"] = not old_subject
                world.choose_job(offer, "accept")
                world.run_country_monthly("JHG")
                self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
                self.assertNotIn("ywc_jhg_escort_request_timer", countries["JHG"])
                self.assertEqual(world.treasury["JHG"], 0)
                self.assertEqual(world.treasury["LAN"], 0)

    def test_subject_transition_does_not_erase_a_paid_signed_contract(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        countries["JHG"]["is_subject"] = True
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_generation"], 1)
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))

    def test_changed_overlord_cancels_an_unsigned_subject_inquiry(self):
        countries = base_countries()
        countries["SHU"] = base_countries()["JHG"]
        countries["JHG"]["is_subject"] = True
        countries["JHG"]["overlord"] = "SHU"
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        countries["JHG"]["overlord"] = "DMG"
        world.choose_job(offer, "accept")
        world.run_country_monthly("JHG")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertNotIn("ywc_jhg_escort_request_timer", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)

    def test_a_dead_requester_cannot_sign_or_pay_a_displayed_offer(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        countries["JHG"]["is_country_alive"] = False
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)

    def test_foreign_ai_weights_respond_to_relationship_and_finances(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))

        def weight(key):
            option = option_body(world, "ywc_jhg.1030", key)
            nodes = field(option, "ai_chance")
            result = float(field(nodes, "base"))
            with world._chain(offer.recipient, world._displayed[offer]):
                for name, _, modifier in nodes:
                    if name == "modifier" and world.conditions(field(modifier, "trigger"), "LAN"):
                        result += float(field(modifier, "add"))
            return result

        low_relation = weight("accept")
        countries["LAN"]["relations"]["JHG"] = 60
        self.assertGreater(weight("accept"), low_relation)
        healthy_refusal = weight("refuse")
        countries["LAN"]["net_fixed_income"] = -1
        self.assertGreater(weight("refuse"), healthy_refusal)

    def test_offer_and_contract_capture_the_configured_coverage(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        captured = dict(offer.saved)
        self.assertIn("ywc_jhg_escort_request_lanes", captured)
        self.assertEqual(captured["ywc_jhg_escort_request_lanes"], 2)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_contract_lanes"], 2)
        self.assertEqual(countries["LAN"]["ywc_jhg_escort_answer_lanes"], 2)

    def test_unpaid_offer_cannot_sign_after_partner_loses_escort_capacity(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        countries["JHG"]["gold_reserves"] = 0
        world.choose_job(offer, "accept")
        countries["LAN"]["navy_size"] = 0
        for building in countries["LAN"]["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        countries["JHG"]["gold_reserves"] = 100000
        world.run_country_monthly("JHG")
        self.assertNotIn("ywc_jhg_escort_contract_generation", countries["JHG"])
        self.assertEqual(world.treasury["JHG"], 0)
        self.assertEqual(world.treasury["LAN"], 0)

    def test_recreated_partner_never_revives_an_old_contract(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        old_partner = countries["JHG"]["ywc_jhg_escort_contract_partner"]
        replacement = base_countries()["LAN"]
        world.remove_country("LAN")
        world.run_country_monthly("JHG")
        world.add_country("LAN", replacement)
        self.assertNotEqual(old_partner, world.country_ref("LAN"))
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_suspended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))

    def test_signed_partner_losing_capacity_suspends_until_it_recovers(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        partner = countries["LAN"]
        partner["navy_size"] = 0
        for building in partner["states"][0]["buildings"]:
            if building["type"] == "building_port":
                building["occupancy"] = 0.1
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        world.run_country_monthly("JHG")
        self.assertEqual(countries["JHG"]["ywc_jhg_escort_suspended_generation"], 1)
        partner["navy_size"] = 5
        world.run_country_monthly("JHG")
        self.assertNotIn("ywc_jhg_escort_suspended_generation", countries["JHG"])
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        self.assertEqual(world.treasury["JHG"], -300)
        self.assertEqual(world.treasury["LAN"], 300)


if __name__ == "__main__":
    unittest.main()

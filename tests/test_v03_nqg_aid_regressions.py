"""Source-level regressions for the winter grain-aid inquiry."""
import unittest
import json
from pathlib import Path

from shu_kor_strict_review_runtime import field
from test_v03_nqg_aid_response import NqgAidWorld, base_countries, install_route, option_body, pulse_winter, send_inquiry, signed_world


class NqgAidFactsWorld(NqgAidWorld):
    def condition(self, node, tag):
        key, operator, value = node
        if key == "government_legitimacy":
            return self.compare(self.countries[tag][key], operator, float(value))
        return super().condition(node, tag)


class NqgAidRegressions(unittest.TestCase):
    def test_signed_valid_bilateral_flow_qualifies_and_1005_progresses_without_resigning(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_aid_contract_active"], "NQG"))
        option = option_body(world, "ywc_nqg.1005", "take_loan_terms")
        self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([n for n in option if n[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertEqual(nqg["ywc_nqg_winter_pending"], 1006)
        self.assertEqual(nqg["ywc_nqg_aid_contract_generation"], 1)
        self.assertEqual((world.treasury["NQG"], world.treasury["SHU"]), (0, 0))
        countries["NQG"]["states"][0]["imports"] = []
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_aid_contract_active"], "NQG"))
        install_route(countries, "SHU")
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_aid_contract_active"], "NQG"))

    def test_midmonth_signature_gets_three_real_subsequent_monthly_opportunities(self):
        from datetime import date
        countries = base_countries()
        world = NqgAidWorld(countries, start_date=date(1836, 1, 1))
        world.run_country_monthly("NQG")
        world.advance_days(14)
        install_route(countries, "SHU")
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        notice = pulse_winter(world)
        self.assertTrue(world.display_job(notice)); world.choose_job(notice, "sign_terms")
        for index, when in enumerate((date(1836, 2, 1), date(1836, 3, 1), date(1836, 4, 1)), 1):
            world.advance_days((when - world.date).days)
            world.run_country_monthly("NQG")
            self.assertEqual(countries["NQG"]["ywc_nqg_aid_paid_count"], index)
        self.assertEqual((world.treasury["NQG"], world.treasury["SHU"]), (-900, 900))

    def test_repaid_expired_agreement_can_be_replaced_without_old_endpoint_touching_it(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        old_end = next(j for j in world.jobs if j.event_id == "ywc_nqg.1032")
        for i in range(3):
            if i: world.advance_months(1)
            world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 900)
        world.advance_months(1)
        world.run_due_hidden()
        self.assertEqual(nqg["ywc_nqg_aid_window_ended_generation"], 1)
        status = pulse_winter(world)
        self.assertTrue(world.display_job(status))
        self.assertTrue(world.job_options(status)["retry_rus"])
        world.choose_job(status, "retry_rus")
        install_route(countries, "RUS")
        offer = [j for j in world.jobs if j.event_id == "ywc_nqg.1030"][-1]
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        world.advance_days(90)
        notice = pulse_winter(world)
        self.assertTrue(world.display_job(notice))
        self.assertTrue(world.job_options(notice)["sign_terms"])
        world.choose_job(notice, "sign_terms")
        self.assertEqual(nqg["ywc_nqg_aid_contract_generation"], 2)
        self.assertEqual(nqg["ywc_nqg_aid_contract_partner"], world.country_ref("RUS"))
        with world._chain(world.country_ref("NQG"), old_end.saved):
            world.run("ywc_nqg_aid_end_window", "NQG")
        self.assertNotEqual(nqg.get("ywc_nqg_aid_window_ended_generation"), 2)
        self.assertIn("ywc_nqg_aid_window_active", nqg)
        self.assertEqual((world.treasury["NQG"], world.treasury["SHU"], world.treasury["RUS"]), (-900, 900, 0))

    def test_unpaid_earned_debt_blocks_replacement_even_after_creditor_loss(self):
        world, countries = signed_world()
        world.run_country_monthly("NQG")
        countries["NQG"]["gold_reserves"] = 0
        world.advance_months(1); world.run_country_monthly("NQG")
        self.assertGreater(countries["NQG"]["ywc_nqg_aid_earned_total"], countries["NQG"]["ywc_nqg_aid_paid_total"])
        world.remove_country("SHU")
        world.advance_months(3); world.run_country_monthly("NQG")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_aid_clear_to_inquire"], "NQG"))

    def test_real_grain_flow_earns_debt_during_default_and_payment_waits(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        nqg["in_default"] = True
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_earned_total"], 300)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 0)
        self.assertEqual(world.treasury["SHU"], 0)
        nqg["in_default"] = False
        world.advance_months(1); world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_earned_total"], 600)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 300)

    def test_becoming_subject_invalidates_an_unsigned_offer_before_status_reverts(self):
        countries = base_countries(); world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["is_subject"] = True
        world.run_on_action("on_become_subject", "NQG")
        countries["NQG"]["is_subject"] = False
        world.choose_job(offer, "accept")
        self.assertNotIn("ywc_nqg_aid_contract_generation", countries["NQG"])
        self.assertNotEqual(countries["NQG"]["ywc_nqg_aid_state"], 2)

    def test_becoming_subject_preserves_an_already_signed_aid_obligation(self):
        world, countries = signed_world()
        state = countries["NQG"]
        state["is_subject"] = True
        world.run_on_action("on_become_subject", "NQG")
        self.assertEqual(state["ywc_nqg_aid_contract_generation"], 1)
        world.run_country_monthly("NQG")
        self.assertEqual(state["ywc_nqg_aid_paid_total"], 300)
        self.assertEqual(world.treasury["SHU"], 300)
    def test_selected_provider_eligibility_uses_its_own_real_facts(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        eligible = world.trigger_defs["ywc_nqg_aid_can_offer_shu"]
        self.assertTrue(world.conditions(eligible, "NQG"))
        countries["SHU"]["relations"]["NQG"] = -1
        self.assertFalse(world.conditions(eligible, "NQG"))
        countries["SHU"]["relations"]["NQG"] = 0
        countries["SHU"]["states"][0]["production"] = {"grain": 0}
        self.assertFalse(world.conditions(eligible, "NQG"))
        countries["SHU"]["states"][0]["production"] = {"grain": 1}
        self.assertTrue(world.conditions(eligible, "NQG"))
        countries["SHU"]["market"] = "m_NQG"
        self.assertFalse(world.conditions(eligible, "NQG"))

    def test_grain_provider_sees_the_captured_repayment_total(self):
        data = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        event = next(e for arc in data["arcs"] for e in arc["events"] if e["id"] == "ywc_nqg.1030")
        for language in ("zh", "en"):
            self.assertIn("SCOPE.GetValue('ywc_nqg_aid_request_total')", event["desc"][language])

    def test_grain_provider_ai_weights_read_relations_and_finances(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))

        def weight(key):
            nodes = field(option_body(world, "ywc_nqg.1030", key), "ai_chance")
            result = float(field(nodes, "base"))
            with world._chain(offer.recipient, world._displayed[offer]):
                for name, _, modifier in nodes:
                    if name == "modifier" and world.conditions(field(modifier, "trigger"), "SHU"):
                        result += float(field(modifier, "add"))
            return result

        ordinary = weight("accept")
        countries["SHU"]["relations"]["NQG"] = 60
        self.assertGreater(weight("accept"), ordinary)
        healthy = weight("refuse")
        countries["SHU"]["net_fixed_income"] = -1
        self.assertGreater(weight("refuse"), healthy)

    def test_valid_unanswered_inquiry_survives_a_month_and_can_be_accepted(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        world.advance_months(1)
        world.run_country_monthly("NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_state"], 1)
        self.assertIn("ywc_nqg_aid_request_timer", countries["NQG"])
        self.assertTrue(world.display_job(offer))
        self.assertTrue(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_state"], 2)

    def test_inquiry_serial_is_captured_and_changes_on_response_once(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertIn("ywc_nqg_aid_request_serial", dict(offer.saved))
        self.assertEqual(dict(offer.saved)["ywc_nqg_aid_request_serial"], 1)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_serial"], 2)
        self.assertEqual(countries["SHU"]["ywc_nqg_aid_answer_serial"], 1)
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_aid_serial"], 2)

    def test_player_can_choose_each_eligible_grain_provider(self):
        for key, partner in (("grain_loan", "SHU"), ("grain_loan_rus", "RUS"), ("grain_loan_jap", "JAP")):
            with self.subTest(partner=partner):
                countries = base_countries()
                world = NqgAidWorld(countries)
                keys = {field(body, "name").rsplit(".", 1)[-1]
                        for name, _, body in world.event_defs["ywc_nqg.1000"] if name == "option"}
                self.assertIn(key, keys)
                option = option_body(world, "ywc_nqg.1000", key)
                self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
                world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
                self.assertEqual(world.jobs[-1].recipient.tag, partner)

    def test_stale_choice_cannot_charge_when_its_provider_is_ineligible(self):
        countries = base_countries()
        countries["NQG"].pop("ywc_nqg_winter_fee_paid")
        countries["NQG"].pop("ywc_nqg_winter_route")
        countries["SHU"]["states"][0]["production"] = {"grain": 0}
        world = NqgAidWorld(countries)
        option = option_body(world, "ywc_nqg.1000", "grain_loan")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertNotIn("ywc_nqg_winter_fee_paid", countries["NQG"])
        self.assertNotIn("ywc_nqg_winter_route", countries["NQG"])
        self.assertEqual(world.treasury["NQG"], 0)
        self.assertFalse(world.jobs)

    def test_paid_domestic_route_can_request_another_provider_without_a_second_fee(self):
        countries = base_countries()
        countries["NQG"]["ywc_nqg_winter_route"] = 1
        countries["NQG"]["gold_reserves"] = 0
        world = NqgAidWorld(countries)
        option = option_body(world, "ywc_nqg.1000", "grain_loan_rus")
        self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        self.assertEqual(countries["NQG"]["ywc_nqg_winter_route"], 3)
        self.assertEqual(world.jobs[-1].recipient.tag, "RUS")
        self.assertEqual(world.treasury["NQG"], 0)

    def test_reopened_opening_switches_to_domestic_and_cancels_pending_offer(self):
        for key, route in (("cap_stipend", 1), ("local_share", 2)):
            with self.subTest(route=route):
                countries = base_countries()
                countries["NQG"]["government_legitimacy"] = 50
                countries["NQG"]["states"][0]["market_access"] = 1
                world = NqgAidFactsWorld(countries)
                offer = send_inquiry(world)
                self.assertTrue(world.display_job(offer))
                option = option_body(world, "ywc_nqg.1000", key)
                self.assertTrue(world.conditions(field(option, "trigger"), "NQG"))
                world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
                world.choose_job(offer, "accept")
                self.assertEqual(countries["NQG"]["ywc_nqg_winter_route"], route)
                self.assertNotEqual(countries["NQG"].get("ywc_nqg_aid_state"), 2)
                self.assertEqual(world.treasury["NQG"], 0)

    def test_subject_transition_blocks_an_already_displayed_foreign_answer(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["is_subject"] = True
        self.assertFalse(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertNotEqual(countries["NQG"].get("ywc_nqg_aid_state"), 2)

    def test_provider_cannot_accept_after_market_or_access_becomes_invalid(self):
        for change in ("same_market", "no_access"):
            with self.subTest(change=change):
                countries = base_countries()
                world = NqgAidWorld(countries)
                offer = send_inquiry(world)
                self.assertTrue(world.display_job(offer))
                if change == "same_market":
                    countries["SHU"]["market"] = "m_NQG"
                else:
                    countries["SHU"]["states"][0]["port"] = False
                self.assertFalse(world.job_options(offer)["accept"])
                world.choose_job(offer, "accept")
                self.assertNotEqual(countries["NQG"].get("ywc_nqg_aid_state"), 2)

    def test_domestic_fallback_invalidates_an_unanswered_foreign_offer(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        option = option_body(world, "ywc_nqg.1005", "refuse_loan_terms")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_winter_route"], 1)
        self.assertNotEqual(countries["NQG"].get("ywc_nqg_aid_state"), 2)
        self.assertNotIn("ywc_nqg_aid_contract_generation", countries["NQG"])

    def test_refusal_cancels_an_offer_even_if_the_route_was_already_changed(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        countries["NQG"]["ywc_nqg_winter_route"] = 1
        option = option_body(world, "ywc_nqg.1005", "refuse_loan_terms")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_winter_route"], 1)
        self.assertNotEqual(countries["NQG"].get("ywc_nqg_aid_state"), 2)

    def test_withdrawal_invalidates_unsigned_aid_without_creating_a_contract(self):
        countries = base_countries()
        countries["NQG"].update({"ywc_v03_nqg_v03_nqg_winter_court_started": 1,
                                  "ywc_v03_active_arc_count": 1,
                                  "ywc_v03_visible_task_count": 1})
        world = NqgAidWorld(countries)
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        option = option_body(world, "ywc_nqg.1000", "withdraw")
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        world.choose_job(offer, "accept")
        self.assertNotEqual(countries["NQG"].get("ywc_nqg_aid_state"), 2)
        self.assertNotIn("ywc_nqg_aid_contract_generation", countries["NQG"])

    def test_signed_repayments_continue_after_winter_arc_withdrawal(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        nqg.update({"ywc_v03_nqg_v03_nqg_winter_court_started": 1,
                    "ywc_v03_active_arc_count": 1, "ywc_v03_visible_task_count": 1})
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 300)
        world.run("ywc_nqg_winter_close_as_breach", "NQG")
        self.assertEqual(nqg["ywc_v03_nqg_v03_nqg_winter_court_settled"], 1)
        for _ in range(2):
            world.advance_months(1)
            world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_earned_total"], 900)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 900)
        self.assertEqual(world.treasury["NQG"], -900)
        self.assertEqual(world.treasury["SHU"], 900)


if __name__ == "__main__":
    unittest.main()

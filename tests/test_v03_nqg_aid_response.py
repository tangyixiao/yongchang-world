"""NQG winter grain aid: a real partner reply, captured terms, an actual grain
flow, three monthly installments and a domestic fallback that never fakes aid."""
import copy
import unittest
from pathlib import Path

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field
from clausewitz_harness import parse

ROOT = Path(__file__).resolve().parents[1]
WINTER = "ywc_je_v03_nqg_winter_court"


def nqg_facts(fee=300):
    data = copy.deepcopy(facts())
    data["ywc_nqg_winter_fee"] = fee
    data["ywc_nqg_winter_fee_paid"] = 1
    data["ywc_nqg_winter_route"] = 3
    data["ywc_nqg_winter_route_lock"] = 1
    data["states"][0]["production"] = {"grain": 10.0}
    return data


def base_countries(fee=300):
    countries = {tag: nqg_facts(fee) for tag in ("NQG", "SHU", "RUS", "JAP")}
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    for tag in ("SHU", "RUS", "JAP"):
        countries[tag]["states"][0]["production"] = {"grain": 40.0}
        countries[tag]["states"][0]["port"] = True
    return countries


def install_route(countries, source_tag="SHU", value=8.0, good="grain"):
    source = countries[source_tag]["states"][0]
    dest = countries["NQG"]["states"][0]
    source["exports"] = [{"target": dest["_sid"], "goods": good, "value": value}]
    dest["imports"] = [{"source": source["_sid"], "goods": good, "value": value}]


class NqgAidWorld(PartnerWorld):
    """PartnerWorld with the NQG calendar value and monthly on_action loaded."""

    def __init__(self, countries, events="", start_date=None):
        if start_date is None:
            from datetime import date
            start_date = date(1836, 1, 1)
        super().__init__(countries, events=events, start_date=start_date, tag="nqg")
        for rel in ("yongchang_world/common/script_values/ywc_v03_nqg_values.txt",
                    "yongchang_world/common/static_modifiers/ywc_v03_nqg_modifiers.txt"):
            path = ROOT / rel
            self.named_values.update({key: body for key, _, body in parse(path.read_text(encoding="utf-8-sig"))}
                                     if path.exists() else {})
        self.on_actions.update({key: body for key, _, body
                                in parse((ROOT / "yongchang_world/common/on_actions/ywc_v03_nqg_accounts.txt")
                                         .read_text(encoding="utf-8-sig"))})


def option_body(world, event_id, key):
    event = world.event_defs[event_id]
    return next(body for name, _, body in event
                if name == "option" and field(body, "name").endswith("." + key))


def send_inquiry(world):
    body = option_body(world, "ywc_nqg.1000", "grain_loan")
    world.execute([node for node in body if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
    return world.jobs[-1]


def pulse_winter(world):
    nqg = world.countries["NQG"]
    if WINTER not in world.active["NQG"]:
        world.active["NQG"].append(WINTER)
    nqg["ywc_v03_nqg_inline_live_winter_court_1"] = 1
    before = len(world.jobs)
    with world._chain(world.country_ref("NQG")):
        world.execute(field(field(world.journal_defs[WINTER], "on_monthly_pulse"), "effect"), "NQG")
    notices = [job for job in world.jobs[before:] if job.event_id == "ywc_nqg.1031"]
    assert len(notices) == 1, ("actual aid notice not dispatched", [job.event_id for job in world.jobs[before:]])
    return notices[0]


def accepted_world(partner="SHU", fee=300):
    countries = base_countries(fee)
    world = NqgAidWorld(countries)
    install_route(countries, partner)
    offer = send_inquiry(world)
    assert offer.event_id == "ywc_nqg.1030", offer.event_id
    assert offer.recipient.tag == partner
    assert world.display_job(offer), "the invited partner must see the real inquiry"
    world.choose_job(offer, "accept")
    return world, countries, pulse_winter(world)


class NqgAidReplyTest(unittest.TestCase):
    def test_local_marker_alone_cannot_take_the_loan_terms(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        # The old pact/reserve heuristic is satisfied, but no partner ever replied.
        countries["NQG"]["ywc_nqg_winter_loan_ready_marker"] = 1
        body = option_body(world, "ywc_nqg.1005", "take_loan_terms")
        world.execute([node for node in body if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
        nqg = countries["NQG"]
        self.assertNotIn("ywc_nqg_aid_contract_generation", nqg)
        self.assertNotEqual(nqg.get("ywc_nqg_winter_pending"), 1006)
        self.assertNotIn("ywc_nqg_aid_contract_total", nqg)

    def test_offer_accept_sign_flow_installments_and_endpoint(self):
        world, countries, notice = accepted_world()
        nqg = countries["NQG"]
        self.assertEqual(nqg["ywc_nqg_aid_state"], 2)
        self.assertEqual(nqg["ywc_nqg_aid_quote_total"], 900)
        self.assertEqual(nqg["ywc_nqg_aid_partner"], world.country_ref("SHU"))
        self.assertEqual(nqg["ywc_nqg_winter_aid_notice_reason"], 1)
        self.assertTrue(world.display_job(notice))
        world.choose_job(notice, "sign_terms")
        self.assertEqual(nqg["ywc_nqg_aid_state"], 6)
        self.assertEqual(nqg["ywc_nqg_aid_contract_total"], 900)
        self.assertEqual(nqg["ywc_nqg_aid_contract_generation"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_source_state"].sid,
                         countries["SHU"]["states"][0]["_sid"])
        self.assertEqual(nqg["ywc_nqg_aid_dest_state"].sid,
                         countries["NQG"]["states"][0]["_sid"])
        self.assertNotEqual(nqg["ywc_nqg_aid_source_market"], nqg["ywc_nqg_aid_dest_market"])
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 0)
        endpoint = [job for job in world.jobs if job.event_id == "ywc_nqg.1032"]
        self.assertEqual(len(endpoint), 1)
        self.assertEqual(dict(endpoint[0].saved)["ywc_nqg_aid_end_generation"], 1)
        self.assertEqual(sum(world.treasury.values()), 0)

        for index in range(3):
            if index:
                world.advance_months(1)
            world.run_country_monthly("NQG")
            self.assertEqual(nqg["ywc_nqg_aid_paid_count"], index + 1)
        world.advance_months(1)
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 3)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 900)
        self.assertEqual(nqg["ywc_nqg_aid_earned_total"], 900)
        self.assertEqual(world.treasury["SHU"], 900)
        self.assertEqual(world.treasury["NQG"], -900)

    def test_signature_requires_the_actual_bilateral_grain_flow(self):
        for defect in ("wrong_good", "third_country", "same_market", "no_import", "no_production"):
            with self.subTest(defect=defect):
                countries = base_countries()
                world = NqgAidWorld(countries)
                install_route(countries, "SHU")
                offer = send_inquiry(world)
                self.assertEqual(offer.event_id, "ywc_nqg.1030")
                self.assertTrue(world.display_job(offer))
                world.choose_job(offer, "accept")
                # Damage the actual flow only after an eligible partner's
                # captured acceptance, so this tests signature attribution.
                if defect == "wrong_good":
                    install_route(countries, "SHU", good="small_arms")
                elif defect == "third_country":
                    install_route(countries, "RUS")
                elif defect == "same_market":
                    install_route(countries, "SHU")
                    countries["SHU"]["market"] = countries["NQG"].get("market", "m_NQG")
                elif defect == "no_import":
                    install_route(countries, "SHU")
                    countries["NQG"]["states"][0]["imports"] = []
                elif defect == "no_production":
                    install_route(countries, "SHU")
                    countries["SHU"]["states"][0]["production"] = {"grain": 0.0}
                notice = pulse_winter(world)
                self.assertTrue(world.display_job(notice))
                options = world.job_options(notice)
                self.assertFalse(options.get("sign_terms"), defect)
                world.choose_job(notice, "domestic_route")
                self.assertNotIn("ywc_nqg_aid_contract_generation", countries["NQG"])


if __name__ == "__main__":
    unittest.main()


def signed_world(partner="SHU", fee=300):
    world, countries, notice = accepted_world(partner, fee)
    assert world.display_job(notice)
    world.choose_job(notice, "sign_terms")
    assert countries["NQG"].get("ywc_nqg_aid_contract_generation") == 1
    return world, countries


class NqgAidFallbackTest(unittest.TestCase):
    def test_refusal_keeps_the_domestic_route_executable(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        install_route(countries, "SHU")
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        nqg = countries["NQG"]
        self.assertEqual(nqg["ywc_nqg_aid_state"], 3)
        self.assertEqual(nqg["ywc_nqg_winter_aid_notice_reason"], 2)
        notice = pulse_winter(world)
        self.assertTrue(world.display_job(notice))
        world.choose_job(notice, "domestic_route")
        self.assertEqual(nqg["ywc_nqg_winter_route"], 1)
        self.assertIn("ywc_nqg_winter_stance_cap_stipend", nqg)
        self.assertNotIn("ywc_nqg_aid_contract_generation", nqg)
        self.assertEqual(nqg["ywc_nqg_winter_fee_paid"], 1)

    def test_unanswered_inquiry_expires_and_keeps_the_fallback(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        install_route(countries, "SHU")
        send_inquiry(world)
        world.advance_months(4)
        world.run_country_monthly("NQG")
        nqg = countries["NQG"]
        self.assertEqual(nqg["ywc_nqg_aid_state"], 4)
        self.assertEqual(nqg["ywc_nqg_winter_aid_notice_reason"], 3)
        self.assertNotIn("ywc_nqg_aid_partner", nqg)
        notice = pulse_winter(world)
        self.assertTrue(world.display_job(notice))
        world.choose_job(notice, "domestic_route")
        self.assertEqual(nqg["ywc_nqg_winter_route"], 1)


class NqgAidContractTest(unittest.TestCase):
    def test_no_fourth_installment_after_the_window(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        for index in range(3):
            if index:
                world.advance_months(1)
            world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 3)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 900)
        world.advance_months(1)
        world.run_due_hidden()
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 3)
        self.assertEqual(nqg["ywc_nqg_aid_window_ended_generation"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_success"], 1)
        self.assertEqual(world.treasury["SHU"], 900)

    def test_underfunded_month_earns_but_pays_after_recovery(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        nqg["gold_reserves"] = 10
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_earned_count"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 0)
        nqg["gold_reserves"] = 100000
        world.advance_months(1)
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_earned_count"], 2)
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 300)
        world.advance_months(1)
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 2)
        self.assertEqual(nqg["ywc_nqg_aid_paid_total"], 600)

    def test_creditor_death_freezes_collection_and_keeps_the_obligation(self):
        world, countries = signed_world()
        nqg = countries["NQG"]
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 1)
        world.remove_country("SHU")
        world.advance_months(1)
        world.run_country_monthly("NQG")
        world.advance_months(1)
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_aid_paid_count"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_earned_count"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_creditor_invalid_generation"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_contract_generation"], 1)

    def test_retry_after_refusal_starts_a_new_generation(self):
        countries = base_countries()
        world = NqgAidWorld(countries)
        install_route(countries, "SHU")
        offer = send_inquiry(world)
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        notice = pulse_winter(world)
        self.assertTrue(world.display_job(notice))
        world.choose_job(notice, "retry_rus")
        nqg = countries["NQG"]
        self.assertEqual(nqg["ywc_nqg_aid_generation"], 2)
        self.assertEqual(nqg["ywc_nqg_aid_state"], 1)
        self.assertEqual(nqg["ywc_nqg_aid_partner"], world.country_ref("RUS"))
        self.assertNotIn("ywc_nqg_aid_quote_generation", nqg)
        # The old notice's open serial was consumed; its choices cannot act.
        options = world.job_options(notice)
        self.assertFalse(options.get("sign_terms"))
        self.assertFalse(options.get("review_status"))
        self.assertFalse(options.get("decline"))

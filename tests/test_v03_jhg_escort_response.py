"""JHG shared escort: a captured partnership replaces the old any-ally marker."""
import copy
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field
from clausewitz_harness import parse

ROOT_PATH = "yongchang_world"


def jhg_facts(fee=600):
    data = copy.deepcopy(facts())
    data["ywc_jhg_convoy_filing_fee"] = fee
    data["ywc_jhg_convoy_filing_fee_paid"] = 1
    data["ywc_jhg_convoy_route"] = 2
    data["ywc_jhg_convoy_implementation_started"] = 1
    data["ywc_jhg_convoy_route_lock"] = 1
    data["navy_size"] = 10
    data["laws"] = list(data["laws"]) + ["law_merchant_navy"]
    return data


def base_countries(fee=600):
    countries = {tag: jhg_facts(fee) for tag in ("JHG", "LAN", "DMG")}
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    for tag in ("LAN", "DMG"):
        countries[tag]["navy_size"] = 10
        countries[tag]["states"][0]["port"] = True
    countries["JHG"]["states"][0]["port"] = True
    return countries


class JhgWorld(PartnerWorld):
    def __init__(self, countries, events="", start_date=None):
        if start_date is None:
            from datetime import date
            start_date = date(1836, 1, 1)
        super().__init__(countries, events=events, start_date=start_date, tag="jhg")
        from pathlib import Path
        for rel in ("common/script_values/ywc_v03_jhg_values.txt",
                    "common/on_actions/ywc_v03_jhg_accounts.txt"):
            path = Path(ROOT_PATH) / rel
            body = {key: value for key, _, value in parse(path.read_text(encoding="utf-8-sig"))}
            if rel.endswith("values.txt"):
                self.named_values.update(body)
            else:
                self.on_actions.update(body)


def option_body(world, event_id, key):
    event = world.event_defs[event_id]
    return next(body for name, _, body in event
                if name == "option" and field(body, "name").endswith("." + key))


def run_option(world, event_id, key):
    body = option_body(world, event_id, key)
    world.execute([node for node in body if node[0] not in ("name", "trigger", "ai_chance")], "JHG")
    return world.jobs[-1]


def signed_partnership(world):
    offer = run_option(world, "ywc_jhg.1010", "shared_escort")
    assert offer.event_id == "ywc_jhg.1030", offer.event_id
    assert world.display_job(offer), "the eligible partner must see the escort inquiry"
    world.choose_job(offer, "accept")
    return offer


class JhgEscortResponseTest(unittest.TestCase):
    def test_shared_escort_requires_the_captured_partner_answer(self):
        countries = base_countries()
        world = JhgWorld(countries)
        # The old any-ally marker is satisfied by a generic ally, but route 2 is
        # not ready until the invited partner actually answers.
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        offer = signed_partnership(world)
        self.assertEqual(offer.recipient.tag, "LAN")
        jhg = countries["JHG"]
        self.assertEqual(jhg["ywc_jhg_escort_state"], 6)
        self.assertEqual(jhg["ywc_jhg_escort_contract_partner"], world.country_ref("LAN"))
        self.assertEqual(jhg["ywc_jhg_escort_contract_cost"], 300)
        self.assertEqual(jhg["ywc_jhg_escort_contract_term"], 120)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_two_ready"], "JHG"))
        endpoints = [job for job in world.jobs if job.event_id == "ywc_jhg.1031"]
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(dict(endpoints[0].saved)["ywc_jhg_escort_end_generation"], 1)

    def test_refusal_keeps_the_single_lane_and_insurance_routes(self):
        countries = base_countries()
        world = JhgWorld(countries)
        offer = run_option(world, "ywc_jhg.1010", "shared_escort")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        jhg = countries["JHG"]
        self.assertEqual(jhg["ywc_jhg_escort_state"], 3)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_two_ready"], "JHG"))
        jhg["ywc_jhg_convoy_route"] = 1
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_one_ready"], "JHG"))
        jhg["ywc_jhg_convoy_route"] = 3
        self.assertTrue(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_three_ready"], "JHG"))
        self.assertEqual(jhg["ywc_jhg_convoy_filing_fee_paid"], 1)

    def test_unanswered_inquiry_expires_without_a_partnership(self):
        countries = base_countries()
        world = JhgWorld(countries)
        run_option(world, "ywc_jhg.1010", "shared_escort")
        world.advance_months(4)
        world.run_country_monthly("JHG")
        jhg = countries["JHG"]
        self.assertEqual(jhg["ywc_jhg_escort_state"], 4)
        self.assertNotIn("ywc_jhg_escort_contract_generation", jhg)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_convoy_route_two_ready"], "JHG"))

    def test_partner_death_suspends_and_the_term_ends(self):
        countries = base_countries()
        world = JhgWorld(countries)
        signed_partnership(world)
        jhg = countries["JHG"]
        world.remove_country("LAN")
        world.run_country_monthly("JHG")
        self.assertEqual(jhg["ywc_jhg_escort_suspended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_jhg_escort_contract_active"], "JHG"))
        # The signed term still closes independently of the suspension.
        world.advance_months(120)
        world.run_country_monthly("JHG")
        self.assertEqual(jhg["ywc_jhg_escort_ended_generation"], 1)


if __name__ == "__main__":
    unittest.main()

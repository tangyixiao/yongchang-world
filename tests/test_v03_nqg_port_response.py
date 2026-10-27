"""NQG northern port treaty: captured lease/escort/renewal answers, exact
object identity after signature, and the multi-berth/high-duty fallbacks."""
import copy
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field
from test_v03_nqg_aid_response import NqgAidWorld, option_body


def port_facts(fee=600):
    data = copy.deepcopy(facts())
    data["ywc_nqg_port_fee"] = fee
    data["ywc_nqg_port_fee_paid"] = 1
    data["ywc_nqg_port_route"] = 2
    data["ywc_nqg_port_implementation_started"] = 1
    data["ywc_nqg_port_route_lock"] = 1
    return data


def base_countries(fee=600):
    countries = {tag: port_facts(fee) for tag in ("NQG", "RUS", "JAP", "JHG")}
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    for tag in ("NQG", "RUS", "JAP", "JHG"):
        countries[tag]["states"][0]["port"] = True
    return countries


def port_world(partner="RUS"):
    countries = base_countries()
    world = NqgAidWorld(countries)
    return world, countries


def run_option(world, event_id, key):
    body = option_body(world, event_id, key)
    world.execute([node for node in body if node[0] not in ("name", "trigger", "ai_chance")], "NQG")
    return world.jobs[-1]


def signed_lease(world):
    offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
    assert offer.event_id == "ywc_nqg.1028", offer.event_id
    assert world.display_job(offer), "the eligible partner must see the lease inquiry"
    world.choose_job(offer, "accept")
    return offer


class NqgPortTreatyTest(unittest.TestCase):
    def test_lease_is_signed_only_against_the_captured_partner_answer(self):
        world, countries = port_world()
        nqg = countries["NQG"]
        offer = signed_lease(world)
        self.assertEqual(offer.recipient.tag, "RUS")
        self.assertEqual(nqg["ywc_nqg_port_treaty_state"], 6)
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_partner"], world.country_ref("RUS"))
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_berth"], 0.5)
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_term"], 120)
        self.assertEqual(nqg["ywc_nqg_port_treaty_dest_state"].sid,
                         countries["NQG"]["states"][0]["_sid"])
        self.assertNotEqual(nqg["ywc_nqg_port_treaty_dest_market"], None)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_lease_ready"], "NQG"))
        endpoints = [job for job in world.jobs if job.event_id == "ywc_nqg.1029"]
        self.assertEqual(len(endpoints), 1)
        self.assertEqual(dict(endpoints[0].saved)["ywc_nqg_port_treaty_end_generation"], 1)

    def test_refusal_leaves_multi_berth_and_high_duty_executable(self):
        world, countries = port_world()
        nqg = countries["NQG"]
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        self.assertEqual(nqg["ywc_nqg_port_treaty_state"], 3)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_lease_ready"], "NQG"))
        # Multi-berth route still executes from the real staffed port and trade law.
        nqg["ywc_nqg_port_route"] = 1
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_route_execution_ready"], "NQG"))
        # The refusal leaves no treaty contract that could block the high-duty
        # route; that route's own law/legitimacy gate is checked in-game.
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", nqg)
        self.assertEqual(nqg["ywc_nqg_port_fee_paid"], 1)

    def test_unanswered_lease_inquiry_expires_without_a_contract(self):
        world, countries = port_world()
        run_option(world, "ywc_nqg.1020", "exclusive_lease")
        world.advance_months(4)
        world.run_country_monthly("NQG")
        nqg = countries["NQG"]
        self.assertEqual(nqg["ywc_nqg_port_treaty_state"], 4)
        self.assertNotIn("ywc_nqg_port_treaty_contract_generation", nqg)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_lease_ready"], "NQG"))

    def test_state_change_suspends_and_only_the_same_object_recovers(self):
        world, countries = port_world()
        signed_lease(world)
        nqg = countries["NQG"]
        countries["NQG"]["states"][0]["owner"] = "RUS"
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_port_treaty_lease_suspended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        countries["NQG"]["states"][0].pop("owner")
        world.run_country_monthly("NQG")
        self.assertNotIn("ywc_nqg_port_treaty_lease_suspended_generation", nqg)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_partner_death_suspends_the_signed_lease(self):
        world, countries = port_world()
        signed_lease(world)
        nqg = countries["NQG"]
        world.remove_country("RUS")
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_port_treaty_lease_suspended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_lease_term_ends_and_blocks_route_two(self):
        world, countries = port_world()
        signed_lease(world)
        nqg = countries["NQG"]
        world.advance_months(120)
        world.run_country_monthly("NQG")
        self.assertEqual(nqg["ywc_nqg_port_treaty_lease_ended_generation"], 1)
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_lease_ready"], "NQG"))

    def test_escort_renegotiation_captures_scope_and_cost(self):
        world, countries = port_world()
        signed_lease(world)
        nqg = countries["NQG"]
        offer = run_option(world, "ywc_nqg.1023", "renegotiate")
        self.assertEqual(offer.event_id, "ywc_nqg.1028")
        self.assertEqual(offer.recipient.tag, "RUS")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(nqg["ywc_nqg_port_treaty_escort_ready"], 1)
        self.assertEqual(nqg["ywc_nqg_port_treaty_escort_cost"], 300)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_escort_refusal_leaves_the_lease_intact(self):
        world, countries = port_world()
        signed_lease(world)
        nqg = countries["NQG"]
        offer = run_option(world, "ywc_nqg.1023", "hold_terms")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "refuse")
        self.assertNotIn("ywc_nqg_port_treaty_escort_ready", nqg)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))

    def test_renewal_extends_and_amend_shortens_the_captured_term(self):
        world, countries = port_world()
        signed_lease(world)
        nqg = countries["NQG"]
        world.advance_months(60)
        offer = run_option(world, "ywc_nqg.1026", "renew")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_generation"], 2)
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_term"], 120)
        self.assertTrue(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        offer = run_option(world, "ywc_nqg.1026", "amend")
        self.assertTrue(world.display_job(offer))
        world.choose_job(offer, "accept")
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_generation"], 3)
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_term"], 60)
        self.assertEqual(nqg["ywc_nqg_port_treaty_contract_berth"], 0.6)

    def test_renewal_is_not_sent_after_the_lease_lapsed(self):
        world, countries = port_world()
        signed_lease(world)
        world.advance_months(120)
        world.run_country_monthly("NQG")
        before = len([job for job in world.jobs if job.event_id == "ywc_nqg.1028"])
        run_option(world, "ywc_nqg.1026", "renew")
        after = len([job for job in world.jobs if job.event_id == "ywc_nqg.1028"])
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()

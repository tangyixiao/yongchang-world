"""Source-driven acceptance for the KOR 1007 procurement partner protocol."""
import copy
import unittest

from kor_partner_protocol_runtime import PartnerWorld
from shu_kor_strict_review_runtime import facts, field


def arms_facts():
    data = facts()
    data["states"][0]["buildings"] = [b for b in data["states"][0]["buildings"]
                                      if b["type"] != "building_arms_industry"]
    data["states"][0]["buildings"].append(
        {"type": "building_arms_industry", "occupancy": 1, "shortage": False, "groups": []})
    return data


def procurement_world(total=1200):
    countries = {tag: arms_facts() for tag in ("KOR", "SHU", "JHG")}
    countries["KOR"]["ywc_kor_weekly_cost"] = total
    for tag in countries:
        countries[tag]["relations"] = {other: 10 for other in countries}
    # Plausible access by default: the providers keep a live port district.
    for tag in ("SHU", "JHG"):
        countries[tag]["states"][0]["port"] = True
    return PartnerWorld(countries), countries


def install_route(countries, source_tag="SHU"):
    """Real bilateral state flow: source production and exports, KOR imports."""
    source = countries[source_tag]["states"][0]
    dest = countries["KOR"]["states"][0]
    source["production"] = {"small_arms": 40}
    source["exports"] = [{"target": dest["_sid"], "goods": "small_arms", "value": 8}]
    dest["imports"] = [{"source": source["_sid"], "goods": "small_arms", "value": 8}]


def send_quote(world, partner="SHU"):
    event = world.event_defs["ywc_kor.1007"]
    option = next(body for key, _, body in event if key == "option"
                  and field(body, "name").endswith(".quote_" + partner.lower()))
    executable = [node for node in option if node[0] not in ("name", "trigger", "ai_chance")]
    world.execute(executable, "KOR")
    return world.jobs[-1] if world.jobs else None


def answer_quote(world, countries, partner="SHU", choice="accept"):
    job = send_quote(world, partner)
    assert job.event_id == "ywc_kor.1033" and job.recipient == world.country_ref(partner)
    assert world.display_job(job)
    world.choose_job(job, choice)
    return job


class ProcurementPartnerProtocolTests(unittest.TestCase):
    def test_actual_1007_quote_options_dispatch_genuine_partner_quotation(self):
        """Regression for the captured RED: the old seek_foreign_quote behavior
        only wrote marker variables and dispatched no partner quotation."""
        for partner in ("SHU", "JHG"):
            with self.subTest(partner=partner):
                world, countries = procurement_world()
                event = world.event_defs["ywc_kor.1007"]
                options = {field(body, "name").rsplit(".", 1)[-1]: body
                           for key, _, body in event if key == "option"}
                self.assertIn("quote_shu", options)
                self.assertIn("quote_jhg", options)
                self.assertNotIn("seek_foreign_quote", options)
                # Live eligibility is independently visible per partner.
                self.assertTrue(world.check_script("ywc_kor_procurement_can_offer_shu = yes"))
                self.assertTrue(world.check_script("ywc_kor_procurement_can_offer_jhg = yes"))
                job = send_quote(world, partner)
                self.assertIsNotNone(job, "1007 foreign inquiry dispatched no partner quotation")
                self.assertEqual(job.event_id, "ywc_kor.1033")
                self.assertEqual(job.recipient, world.country_ref(partner))
                self.assertNotIn("ywc_kor_procurement_notice_event", countries["KOR"])
                kor = countries["KOR"]
                self.assertEqual(kor["ywc_kor_procurement_state"], 1)
                self.assertEqual(kor["ywc_kor_procurement_generation"], 1)
                self.assertEqual(kor["ywc_kor_procurement_total"], countries["KOR"]["ywc_kor_weekly_cost"])
                self.assertEqual(kor["ywc_kor_procurement_booked"], 1)
                self.assertEqual(sum(world.treasury.values()), 0)

    def test_accept_captures_exact_immutable_terms_and_publishes_notice(self):
        world, countries = procurement_world()
        answer_quote(world, countries, "SHU", "accept")
        shu = countries["SHU"]
        kor = countries["KOR"]
        self.assertEqual(shu["ywc_kor_procurement_answer"], 1)
        self.assertEqual(shu["ywc_kor_procurement_answer_generation"], 1)
        self.assertEqual(shu["ywc_kor_procurement_answer_total"], 1200)
        self.assertEqual(shu["ywc_kor_procurement_answer_requester"], world.country_ref("KOR"))
        self.assertEqual(kor["ywc_kor_procurement_state"], 2)
        self.assertEqual(kor["ywc_kor_procurement_quote_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_quote_total"], 1200)
        self.assertEqual(kor["ywc_kor_procurement_notice_event"], 1034)
        self.assertEqual(kor["ywc_kor_procurement_notice_serial"], 1)
        self.assertEqual(kor["ywc_kor_procurement_notice_generation"], 1)
        self.assertEqual(kor["ywc_kor_procurement_notice_request_state"], 2)
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 1)
        self.assertEqual(sum(world.treasury.values()), 0)
        self.assertFalse(world.modifiers)

    def test_refuse_publishes_refusal_and_clears_captured_quote_terms(self):
        world, countries = procurement_world()
        answer_quote(world, countries, "JHG", "refuse")
        kor = countries["KOR"]
        self.assertEqual(countries["JHG"]["ywc_kor_procurement_answer"], 2)
        self.assertEqual(kor["ywc_kor_procurement_state"], 3)
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 2)
        self.assertNotIn("ywc_kor_procurement_quote_generation", kor)
        self.assertNotIn("ywc_kor_procurement_quote_total", kor)
        self.assertNotIn("ywc_kor_procurement_request_timer", kor)
        self.assertEqual(sum(world.treasury.values()), 0)

    def test_live_eligibility_defects_block_the_inquiry_without_jobs(self):
        for defect in ("dead", "hostile", "subject", "capacity", "shortage",
                       "same_market", "no_access"):
            with self.subTest(defect=defect):
                world, countries = procurement_world()
                if defect == "dead":
                    countries["SHU"]["is_country_alive"] = False
                elif defect == "hostile":
                    countries["SHU"]["relations"]["KOR"] = -1
                elif defect == "subject":
                    countries["KOR"]["is_subject"] = True
                elif defect == "capacity":
                    countries["SHU"]["states"][0]["buildings"][-1]["occupancy"] = 0.79
                elif defect == "shortage":
                    countries["SHU"]["states"][0]["buildings"][-1]["shortage"] = True
                elif defect == "same_market":
                    countries["SHU"]["market"] = "m_KOR"
                else:
                    countries["SHU"]["states"][0]["port"] = False
                self.assertFalse(world.check_script("ywc_kor_procurement_can_offer_shu = yes"))
                world.run_script("ywc_kor_procurement_send_shu = yes")
                self.assertFalse(world.jobs)

    def test_port_and_market_adjacency_each_grant_access(self):
        for access in ("port", "adjacent"):
            with self.subTest(access=access):
                world, countries = procurement_world()
                countries["SHU"]["states"][0]["port"] = access == "port"
                if access == "adjacent":
                    world.markets.setdefault("m_SHU", {"owner": "SHU", "adjacent": set()})["adjacent"].add("m_KOR")
                self.assertTrue(world.check_script("ywc_kor_procurement_can_offer_shu = yes"))
                job = send_quote(world, "SHU")
                self.assertIsNotNone(job)
    def test_stale_answers_cannot_rewrite_a_newer_generation(self):
        world, countries = procurement_world()
        stale = send_quote(world, "SHU")
        self.assertTrue(world.display_job(stale))
        world.choose_job(stale, "accept")
        self.assertEqual(countries["KOR"]["ywc_kor_procurement_state"], 2)
        # KOR switches partners; each new inquiry owns a new generation.
        reset = ("set_variable = { name = ywc_kor_procurement_state value = 3 } "
                 "remove_variable = ywc_kor_procurement_quote_generation "
                 "remove_variable = ywc_kor_procurement_quote_total "
                 "remove_variable = ywc_kor_procurement_partner")
        world.run_script(reset)
        middle = send_quote(world, "JHG")
        world.run_script(reset)
        current = send_quote(world, "SHU")
        generations = [dict(job.saved)["ywc_kor_procurement_request_generation"] for job in (stale, middle, current)]
        self.assertEqual(generations, [1, 2, 3])
        # A superseded foreign answer can no longer even display against the
        # current generation, and the displayed stale answer cannot authorize.
        self.assertFalse(world.display_job(middle))
        kor = countries["KOR"]
        self.assertTrue(world.display_job(current))
        world.choose_job(stale, "accept")
        self.assertEqual(kor["ywc_kor_procurement_state"], 1)
        self.assertNotIn("ywc_kor_procurement_quote_generation", kor)
        world.choose_job(current, "accept")
        self.assertEqual(kor["ywc_kor_procurement_quote_generation"], 3)

    def test_expired_inquiry_is_marked_expired_once_with_serial_bump(self):
        world, countries = procurement_world()
        send_quote(world, "SHU")
        kor = countries["KOR"]
        self.assertNotIn("ywc_kor_procurement_notice_serial", kor)
        world.advance_months(3)
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_state"], 4)
        self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 3)
        self.assertEqual(kor["ywc_kor_procurement_notice_event"], 1034)
        self.assertEqual(kor["ywc_kor_procurement_notice_serial"], 1)
        world.run_country_monthly()
        self.assertEqual(kor["ywc_kor_procurement_notice_serial"], 1)

    def test_subject_transition_and_partner_loss_cancel_unsigned_work(self):
        for defect in ("subject", "partner_death", "merger"):
            with self.subTest(defect=defect):
                world, countries = procurement_world()
                answer_quote(world, countries, "SHU", "accept")
                kor = countries["KOR"]
                self.assertEqual(kor["ywc_kor_procurement_state"], 2)
                if defect == "subject":
                    kor["is_subject"] = True
                elif defect == "partner_death":
                    countries["SHU"]["is_country_alive"] = False
                else:
                    countries["SHU"]["market"] = "m_KOR"
                world.run_country_monthly()
                self.assertEqual(kor["ywc_kor_procurement_state"], 5)
                self.assertEqual(kor["ywc_kor_procurement_notice_reason"], 4)
                self.assertNotIn("ywc_kor_procurement_partner", kor)
                self.assertNotIn("ywc_kor_procurement_request_timer", kor)
                self.assertEqual(sum(world.treasury.values()), 0)


if __name__ == "__main__":
    unittest.main()

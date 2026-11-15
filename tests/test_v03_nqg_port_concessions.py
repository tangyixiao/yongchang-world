"""Captured-state port concession lifecycle, tested without the game engine."""
import copy
import unittest
from datetime import date

from clausewitz_harness import parse
from kor_partner_protocol_runtime import StateRef
from shu_kor_strict_review_runtime import field
from test_v03_nqg_port_response import base_countries, port_world, run_option, signed_lease


BASE = "ywc_nqg_port_concession_50"
AMENDED = "ywc_nqg_port_concession_60"


def state_names(world, state):
    return {name for (ref, name), _ in getattr(world, "state_modifiers", {}).items() if ref == state}


def captured(world, countries):
    return StateRef(countries["NQG"]["states"][0]["_sid"])


class NqgPortConcessionsTests(unittest.TestCase):
    def test_state_owner_hook_appends_a_named_child_without_replacing_vanilla(self):
        from pathlib import Path
        source = parse(Path("yongchang_world/common/on_actions/ywc_v03_nqg_accounts.txt").read_text(encoding="utf-8-sig"))
        declarations = {name: body for name, _, body in source}
        hook = declarations["on_state_owner_change"]
        self.assertFalse(any(name in ("effect", "trigger") for name, _, _ in hook))
        children = [name for key, _, body in hook if key == "on_actions" for name, _, _ in body]
        self.assertEqual(children, ["ywc_v03_nqg_port_state_owner_changed"])
        self.assertEqual(sum(name == "effect" for name, _, _ in declarations[children[0]]), 1)

    def test_actual_acceptance_applies_only_the_captured_state_modifier(self):
        countries = base_countries()
        extra = copy.deepcopy(countries["NQG"]["states"][0]); extra.pop("_sid", None); extra["port"] = False
        countries["NQG"]["states"].append(extra)
        from test_v03_nqg_aid_response import NqgAidWorld
        world = NqgAidWorld(countries)
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        target = captured(world, countries)
        self.assertEqual(state_names(world, target), set(), "an unanswered proposal is not a concession")
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertEqual(state_names(world, target), {BASE})
        self.assertEqual(state_names(world, StateRef(extra["_sid"])), set())
        self.assertEqual(state_names(world, StateRef(countries["RUS"]["states"][0]["_sid"])), set())

    def test_refusal_does_not_create_a_state_modifier(self):
        world, countries = port_world()
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease")
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "refuse")
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, captured(world, countries)), set())

    def test_amendment_replaces_effect_and_old_endpoint_is_harmless(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        old_end = next(j for j in world.jobs if j.event_id == "ywc_nqg.1029")
        offer = run_option(world, "ywc_nqg.1026", "amend")
        self.assertTrue(world.display_job(offer)); world.choose_job(offer, "accept")
        self.assertEqual(state_names(world, target), {AMENDED})
        with world._chain(old_end.recipient, old_end.saved):
            world.execute(field(world.event_defs[old_end.event_id], "immediate"), "NQG")
        self.assertEqual(state_names(world, target), {AMENDED})

    def test_expired_endpoint_replay_does_not_cancel_a_new_partners_pending_offer(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        old_end = next(job for job in world.jobs if job.event_id == "ywc_nqg.1029")
        world.advance_months(120); world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), set())
        offer = run_option(world, "ywc_nqg.1020", "exclusive_lease_jap")
        self.assertTrue(world.display_job(offer))
        keys = ("ywc_nqg_port_treaty_serial", "ywc_nqg_port_treaty_state", "ywc_nqg_port_treaty_generation")
        before = {key: countries["NQG"].get(key) for key in keys}
        with world._chain(old_end.recipient, old_end.saved):
            world.execute(field(world.event_defs[old_end.event_id], "immediate"), "NQG")
        self.assertEqual({key: countries["NQG"].get(key) for key in keys}, before)
        self.assertEqual(state_names(world, target), set())
        self.assertTrue(world.job_options(offer)["accept"])
        world.choose_job(offer, "accept")
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_contract_partner"], world.country_ref("JAP"))
        self.assertEqual(state_names(world, target), {BASE})

    def test_owner_change_callback_removes_effect_without_waiting_for_monthly_pulse(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        self.assertEqual(state_names(world, target), {BASE})
        countries["NQG"]["states"][0]["owner"] = "RUS"
        world.run_state_owner_change(target)
        self.assertEqual(state_names(world, target), set())
        world.run_country_monthly("NQG")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_nqg_port_treaty_lease_active"], "NQG"))
        countries["NQG"]["states"][0].pop("owner")
        world.run_state_owner_change(target); world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), {BASE})

    def test_state_callback_retains_vanilla_and_uses_changed_state_as_root(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        other = StateRef(countries["RUS"]["states"][0]["_sid"])
        sentinel = "ywc_test_state_root"
        world.state_modifiers[(target, sentinel)] = {"fields": {}, "expires": None}
        world.state_modifiers[(other, sentinel)] = {"fields": {}, "expires": None}
        world.merge_on_actions(parse("on_state_owner_change = { effect = { if = { limit = { root = this } remove_modifier = ywc_test_state_root } } }"))
        world.run_state_owner_change(target)
        self.assertNotIn(sentinel, state_names(world, target))
        self.assertIn(sentinel, state_names(world, other))
        self.assertNotIn(BASE, state_names(world, target))

    def test_partner_market_loss_suspends_and_exact_recovery_restores(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        countries["RUS"]["market"] = "replacement_market"
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), set())
        countries["RUS"].pop("market")
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), {BASE})

    def test_lost_partner_recreation_does_not_inherit_the_concession(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        world.remove_country("RUS")
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), set())
        world.add_country("RUS", base_countries()["RUS"])
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), set())
        self.assertEqual(countries["NQG"]["ywc_nqg_port_treaty_lease_suspended_generation"], 1)

    def test_unknown_terms_remove_the_effect_instead_of_guessing(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        countries["NQG"]["ywc_nqg_port_treaty_contract_berth"] = 0.7
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), set())
        countries["NQG"]["ywc_nqg_port_treaty_contract_berth"] = 0.5
        countries["NQG"]["ywc_nqg_port_treaty_contract_duty"] = 2
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), set())

    def test_exact_midmonth_end_removes_before_modifier_would_expire(self):
        world, countries = port_world()
        world.advance_days(14); signed_lease(world)
        target = captured(world, countries)
        world.advance_days((date(1846, 1, 1) - world.date).days)
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), {BASE})
        world.advance_days(14); world.run_due_hidden()
        self.assertEqual(state_names(world, target), set())

    def test_signed_contract_survives_subject_and_event_arc_closure(self):
        world, countries = port_world(); signed_lease(world)
        target = captured(world, countries)
        countries["NQG"].update({"is_subject": True, "ywc_v03_nqg_v03_nqg_northern_port_settled": 1})
        world.run_on_action("on_become_subject", "NQG")
        world.run_country_monthly("NQG")
        self.assertEqual(state_names(world, target), {BASE})

    def test_actual_defined_effects_are_statewide_and_not_partner_specific(self):
        from pathlib import Path
        path = Path("yongchang_world/common/static_modifiers/ywc_v03_nqg_modifiers.txt")
        definitions = {key: body for key, _, body in parse(path.read_text(encoding="utf-8-sig"))}
        for name, capacity in ((BASE, 0.2), (AMENDED, 0.3)):
            body = definitions[name]
            self.assertEqual(float(field(body, "state_trade_capacity_mult")), capacity)
            self.assertEqual(float(field(body, "state_tariff_import_add")), -0.1)

    def test_bilingual_offer_discloses_statewide_effect_and_no_enforced_berths(self):
        import json
        from pathlib import Path
        data = json.loads(Path("data/content/v03/countries/nqg.json").read_text(encoding="utf-8"))
        events = {e["id"]: e for arc in data["arcs"] for e in arc["events"]}
        for key in ("exclusive_lease", "exclusive_lease_jap", "exclusive_lease_jhg"):
            note = next(o for o in events["ywc_nqg.1020"]["options"] if o["key"] == key)["consequence_note"]
            self.assertIn("all its trade centers", note["en"])
            self.assertIn("nominal berth share is not enforced", note["en"])
            self.assertIn("影响全州贸易中心", note["zh"])
            self.assertIn("并不强制分配名义泊位比例", note["zh"])


if __name__ == "__main__":
    unittest.main()

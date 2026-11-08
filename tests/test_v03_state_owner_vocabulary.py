"""Actual-source contracts for documented state owner = ROOT.

Legacy is_owned_by support in world fixtures is compatibility only. Byte/AST
inverse proofs belong to the private migration audit, never this module.
"""
import json
from pathlib import Path
import unittest

from tests.clausewitz_harness import parse
from tests.test_v03_tib_foundation_lifecycle import TibWorldFacts
from tests.test_v03_tib_inline_actual_source import _initial_world
from tests.test_v03_jhg_foundation import JhgTerminalWorld
from tests.test_v03_nmg_foundation_lifecycle import NmgWorld
from tests.test_v03_nqg_foundation import NqgWorldFactsRuntime
from tests.test_v03_oir_foundation import OIRWorld
from tests.test_v03_dmg_foundation_lifecycle import DmgWorld
from tests.test_v03_tib_school_ai import StrictSchoolWorld
from shu_kor_strict_review_runtime import Strict, facts, field

ROOT = Path(__file__).resolve().parents[1]
COUNTS = dict(dmg=9, jhg=4, kor=6, shu=20, oir=9, nmg=6, tib=8, nqg=1)


def source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def trigger_source(country):
    return source(f"yongchang_world/common/scripted_triggers/ywc_v03_{country}_triggers.txt")


def walk(nodes, state=False):
    for key, op, value in nodes:
        yield key, op, value, state
        if isinstance(value, list):
            yield from walk(value, state or key in ("any_scope_state", "every_scope_state"))


class StateOwnerVocabularyTests(unittest.TestCase):
    def assert_source_owners(self, text, count):
        self.assertNotIn("is_owned_by", text)
        self.assertEqual(text.count("owner = ROOT"), count)
        predicates = [n for n in walk(parse(text)) if n[0] == "owner" and n[2] == "ROOT"]
        self.assertEqual(len(predicates), count)
        for key, op, value, in_state in predicates:
            self.assertEqual((op, value, in_state), ("=", "ROOT", True))

    def test_actual_inventory_and_state_scoped_scalar_shapes(self):
        for country, count in COUNTS.items():
            with self.subTest(country=country):
                self.assert_source_owners(trigger_source(country), count)
        self.assert_source_owners(source("yongchang_world/common/scripted_effects/ywc_v03_tib_effects.txt"), 1)
        self.assert_source_owners(source("yongchang_world/events/ywc_v03_country_shu_events.txt"), 14)
        catalog = json.loads(source("data/content/v03/countries/shu.json"))
        def strings(value):
            if isinstance(value, str): yield value
            elif isinstance(value, list):
                for child in value: yield from strings(child)
            elif isinstance(value, dict):
                for child in value.values(): yield from strings(child)
        scripts = [text for text in strings(catalog) if "owner = ROOT" in text or "is_owned_by" in text]
        self.assertEqual(sum(text.count("owner = ROOT") for text in scripts), 14)
        for text in scripts:
            self.assert_source_owners(text.strip()[1:-1], text.count("owner = ROOT"))

    def test_documented_primitive_requires_real_invocation_root_identity(self):
        # A literal language primitive isolates interpreter compatibility in RED.
        w = TibWorldFacts("", "", {"SHU": {}, "KOR": {}})
        for tag in ("SHU", "KOR"):
            for owner in ("SHU", "KOR", None):
                w.state_scope = {"owner": owner, "owned": True}
                self.assertEqual(w.condition(("owner", "=", "ROOT"), tag), owner == tag)

    def test_actual_shu_and_kor_helpers_respect_two_roots_and_restore_scopes(self):
        for country, helpers in (("shu", ("ywc_shu_v03_has_pilot_state", "ywc_shu_v03_has_candidate_state", "ywc_shu_v03_administration_ready")),
                                 ("kor", ("ywc_kor_v03_has_staffed_supplied_barracks", "ywc_kor_v03_has_translation_employer"))):
            w = Strict(country)
            for tag in ("SHU", "KOR"):
                for owner in ("SHU", "KOR", None):
                    state = facts()
                    state["ywc_shu_v03_pilot_state"] = 1
                    state["states"][0].update(owner=owner)
                    w.countries[tag] = state
                    for helper in helpers:
                        with self.subTest(country=country, tag=tag, owner=owner, helper=helper):
                            self.assertEqual(w.conditions(w.trigger_defs[helper], tag), owner == tag)
                            self.assertIsNone(w.state_scope)
                            self.assertIsNone(w.building_scope)

    def test_actual_tib_agriculture_and_native_effect_filter_each_owned_state(self):
        w = _initial_world()
        native = next(n for n in field(w.effects["ywc_tib_choose_grain_3"], "if") if n[0] == "every_scope_state")
        self.assertEqual(field(native[2], "limit"), [("owner", "=", "ROOT")])
        self.assertEqual(field(native[2], "add_modifier"), [("name", "=", "ywc_v03_tib_grain_relief_earmarked"), ("days", "=", "365")])
        for tag in ("SHU", "KOR"):
            states = [{"owner": owner, "owned": True, "buildings": [{"type": "building_rice_farm", "occupancy": 1}], "pops": []}
                      for owner in (tag, tag, "KOR" if tag == "SHU" else "SHU", None)]
            w.countries[tag] = {"states": states}
            w.treasury[tag] = 0
            for state in states:
                w.countries[tag]["states"] = [state]
                self.assertEqual(w.conditions(w.trigger_defs["ywc_tib_has_agriculture"], tag), state["owner"] == tag)
            w.countries[tag]["states"] = states
            before = len(w.modifiers)
            checkpoint = w._scope_checkpoint()
            w.execute([native], tag)
            expected = dict((k, v) for k, _, v in field(native[2], "add_modifier"))
            self.assertEqual(w.modifiers[before:], [(tag, expected)] * 2)
            self.assertEqual(w._scope_checkpoint(), checkpoint)
            for state in states[2:]:
                w.countries[tag]["states"] = [state]
                before = len(w.modifiers)
                w.execute([native], tag)
                self.assertEqual(len(w.modifiers), before)

    def test_actual_jhg_nmg_oir_and_nqg_foreign_building_negatives(self):
        w = JhgTerminalWorld("", {"JHG": {}})
        nodes = w.triggers["ywc_jhg_court_administration_staffed"]
        for owned in (True, False):
            w.countries["JHG"]["engine_states"] = [{"owned_by_root": owned, "buildings": [{"type": "building_government_administration", "occupancy": 1, "goods_shortage": False}]}]
            self.assertEqual(w.conditions(nodes, "JHG"), owned)
        n = NmgWorld({"NMG": {"fixture_owned_state": 1, "fixture_buildings": {"building_wheat_farm": 1}}})
        for owner in ("NMG", "KOR", None):
            n.countries["NMG"]["fixture_state_owner"] = owner
            self.assertEqual(n.conditions(n.trigger_defs["ywc_nmg_land_agriculture_present"], "NMG"), owner == "NMG")
        o = OIRWorld()
        for owned in (True, False):
            o.countries["OIR"]["fixture_states"][0]["owned"] = owned
            for helper in ("ywc_oir_v03_has_owned_state", "ywc_oir_v03_has_staffed_administration"):
                self.assertEqual(o.conditions(o.triggers[helper], "OIR"), owned)
        q = NqgWorldFactsRuntime({"NQG": {}})
        for owner in ("NQG", "KOR", None):
            q.countries["NQG"]["states"] = [{"owner": owner}]
            self.assertEqual(q.conditions(q.triggers["ywc_nqg_v03_has_owned_state"], "NQG"), owner == "NQG")
            self.assertIsNone(q.states)

    def test_actual_shu_sichuan_option_and_merchant_branches_preserve_queue(self):
        w = Strict("shu")
        option = next(v for k, _, v in w.event_defs["ywc_shu.1000"] if k == "option" and field(v, "name").endswith(".pilot_state_sichuan"))
        merchant = next(v for k, _, v in w.event_defs["ywc_shu.1005"] if k == "option" and any(n[0] == "if" and "ywc_shu_accept_merchant_advance" in str(n) for n in v))
        branches = [n for n in merchant if n[0] == "if"]
        self.assertEqual(len(branches), 2)
        self.assertNotEqual(field(branches[0][2], "limit"), field(branches[1][2], "limit"))
        self.assertEqual(len([n for n in walk(merchant) if n[0] == "ywc_shu_accept_merchant_advance"]), 2)
        for owner in ("SHU", "KOR", None):
            state = facts()
            state["states"][0]["owner"] = owner
            w.countries["SHU"] = state
            w.treasury["SHU"] = 0
            self.assertEqual(w.conditions(field(option, "trigger"), "SHU"), owner == "SHU")
            self.assertEqual([w.conditions(field(n[2], "limit"), "SHU") for n in branches], [owner == "SHU", owner != "SHU"])
            w.execute([n for n in merchant if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")], "SHU")
            self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
            self.assertEqual(state.get("ywc_shu_merchant_advance"), 1)
            self.assertEqual(state.get("ywc_shu_merchant_advance_unpaid"), 1)
            self.assertGreater(state.get("ywc_shu_merchant_principal", 0), 0)
            self.assertEqual(w.treasury["SHU"], state["ywc_shu_merchant_principal"])
            self.assertEqual(state.get("ywc_shu_merchant_repayment_months"), 0)
            self.assertEqual(state.get("ywc_shu_merchant_consultation"), 1)
            self.assertEqual(state.get("ywc_shu_local_prepayment_offer", 0), int(owner != "SHU"))
            self.assertIsNone(w.state_scope)

    def test_documented_owner_rejects_unsupported_target_operator_block_and_scope(self):
        w = _initial_world()
        for script in ("owner = ROOT", "any_scope_state = { owner = OTHER }",
                       "any_scope_state = { owner = scope:requester }", "any_scope_state = { owner != ROOT }",
                       "any_scope_state = { owner ?= ROOT }", "any_scope_state = { owner = { who = ROOT } }",
                       "any_scope_state = { any_scope_building = { owner = ROOT } }"):
            with self.subTest(script=script), self.assertRaises(AssertionError):
                w.conditions(parse(script), "TIB")
        # Existing fail-closed and legacy compatibility controls stay explicit.
        for key in ("owner", "is_owned_by"):
            w.state_scope = {"owned": True}
            self.assertTrue(w.condition((key, "=", "ROOT"), "TIB"))
            for op, target in (("!=", "ROOT"), ("=", "OTHER"), ("=", [("who", "=", "ROOT")])):
                with self.assertRaises(AssertionError): w.condition((key, op, target), "TIB")
        w.state_scope = None

    def test_direct_fixture_seams_reject_malformed_documented_owner(self):
        dmg = DmgWorld("", {"DMG": {"fixture_owned_state": 1}})
        jhg = JhgTerminalWorld("", {"JHG": {}})
        nmg = NmgWorld({"NMG": {"fixture_owned_state": 1}})
        oir = OIRWorld()
        school = StrictSchoolWorld("", "", {"TIB": {}})
        for op, target in (("!=", "ROOT"), ("?=", "ROOT"), ("=", "OTHER"),
                           ("=", "scope:requester"), ("=", [("who", "=", "ROOT")])):
            owner = ("owner", op, target)
            checks = (
                lambda: dmg.condition(("any_scope_state", "=", [owner]), "DMG"),
                lambda: jhg._state_matches([owner], {"owned_by_root": True}),
                lambda: nmg.conditions([("always", "=", "no"), ("any_scope_state", "=", [owner])], "NMG"),
                lambda: oir._cond(owner, "OIR", {"owned": True}),
                lambda: school._validate_condition(owner),
            )
            for check in checks:
                with self.subTest(op=op, target=target, seam=checks.index(check)), self.assertRaises(AssertionError):
                    check()


if __name__ == "__main__":
    unittest.main()

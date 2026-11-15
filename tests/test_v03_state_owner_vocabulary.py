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
from test_v03_shu_merchant_obligations import reached_offer

ROOT = Path(__file__).resolve().parents[1]
# DMG retains its nine foundation predicates and adds six school queries, each
# nested in the selected owned state before entering pop/workplace scope.
# Eight more selected-state predicates belong to the market card; PHI's own
# border predicate uses c:PHI and cannot count as one of ROOT's eight.
# Crown appends eight used selected-state predicates; the original 23 remain intact.
# Revenue adds one candidate-state query and one typed saved-state owner check.
# Public deliberation appends sixteen state-owner reads; the old44 remain intact.
# School appends seven original-pilot owner reads; the old six remain intact.
# Court public adds the same two shapes with its own saved StateRef variable.
# 2026-11-15 test-debt re-inventory of the merged arc reality: JHG dockyard
# ownership (+2 d0a4033, +1 ten-country ship), KOR workshop coordination
# (+6 56ad436, +2 ship), SHU rural workshop (+10 2636ba0, +2 ship), TIB public
# revenue (+4 a907ce5, +5 ship), LAN beyond gold (+2 297920f, +4 ship), NMG bay
# ports (+4 ship), NQG procurement/premium routes (+6 ship) and DMG middle
# cards (+2 ship). Every added predicate was re-verified in state scope by
# assert_source_owners' walk() — the new captured-state variables it walks
# through gained explicit exceptions below; OIR is unchanged at nine.
COUNTS = dict(dmg=33, jhg=7, kor=18, shu=72, oir=9, nmg=17, tib=17, nqg=7, lan=15)


def source(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def trigger_source(country):
    return source(f"yongchang_world/common/scripted_triggers/ywc_v03_{country}_triggers.txt")


def walk(nodes, scope="country"):
    for key, op, value in nodes:
        yield key, op, value, scope
        if isinstance(value, list):
            next_scope = scope
            if key in ("any_scope_state", "every_scope_state", "random_scope_state"):
                # random_scope_state (effects only) also selects one real owned
                # state; the TIB middle-card pay helpers read owner = ROOT in
                # its limit, exactly like the any/every scope family.
                next_scope = "state"
            elif key in ("any_scope_building", "every_scope_building"):
                next_scope = "building"
            elif key in ("any_scope_pop", "every_scope_pop"):
                next_scope = "pop"
            elif key in ("var:ywc_kor_revenue_pilot_state", "var:ywc_kor_public_pilot_state"):
                # Only these exact native StateRef variables cross into state
                # scope; all other var:/scope: forms keep the country rule.
                next_scope = "state"
            elif key == "var:ywc_nmg_school_pilot":
                # The school claim stores a native StateRef once; literal
                # runtime tests prove its identity and current ownership.
                next_scope = "state"
            elif key == "var:ywc_kor_workshops_pilot":
                # KOR workshop coordination arc (56ad436) captures one candidate
                # state from every_scope_state into this typed variable; the
                # workshop readiness helpers read it in state scope and
                # tests/test_v03_kor_workshops_* run the real capture helper.
                next_scope = "state"
            elif key == "var:ywc_tib_revenue_pilot":
                # TIB public revenue arc (a907ce5) saves its pilot state once;
                # test_v03_tib_revenue_state_source.py asserts the StateRef type.
                next_scope = "state"
            elif key == "var:ywc_lan_gold_pilot_state":
                # LAN beyond-gold arc (297920f) captures the West Borneo pilot
                # StateRef once; test_v03_lan_beyond_gold.py asserts its identity
                # and that a decoy state can never substitute.
                next_scope = "state"
            elif key in ("ROOT.var:ywc_jhg_dock_pilot", "ROOT.var:ywc_shu_workshop_pilot"):
                # JHG dockyard (d0a4033) and SHU rural workshop (2636ba0) read a
                # once-captured state object through the ROOT.<StateRef> dotted
                # form; test_v03_jhg_dockyard_state.py and
                # test_v03_shu_rural_state_runtime.py prove the captured object.
                next_scope = "state"
            elif key in ("ROOT", "PREV", "this") or key.startswith(("c:", "scope:", "var:")):
                next_scope = "country"
            yield from walk(value, next_scope)


class StateOwnerVocabularyTests(unittest.TestCase):
    def assert_source_owners(self, text, count):
        self.assertNotIn("is_owned_by", text)
        self.assertEqual(text.count("owner = ROOT"), count)
        predicates = [n for n in walk(parse(text)) if n[0] == "owner" and n[2] == "ROOT"]
        self.assertEqual(len(predicates), count)
        for key, op, value, current_scope in predicates:
            self.assertEqual((op, value, current_scope), ("=", "ROOT", "state"))

    def test_inventory_rejects_owner_after_non_state_scope_transition(self):
        for nested in ("any_scope_building", "any_scope_pop", "c:SHU", "scope:ywc_kor_requester",
                       "var:unknown_country_var"):
            with self.subTest(nested=nested):
                script = f"any_scope_state = {{ {nested} = {{ owner = ROOT }} }}"
                owner = [row for row in walk(parse(script)) if row[0] == "owner"]
                self.assertNotEqual(owner[0][3], "state")

    def test_inventory_keeps_state_through_logical_blocks(self):
        script = "any_scope_state = { AND = { OR = { NOT = { owner = ROOT } } } }"
        owner = [row for row in walk(parse(script)) if row[0] == "owner"]
        self.assertEqual(owner[0][3], "state")

    def test_actual_inventory_and_state_scoped_scalar_shapes(self):
        for country, count in COUNTS.items():
            with self.subTest(country=country):
                self.assert_source_owners(trigger_source(country), count)
        # TIB public revenue arc (a907ce5) added one every_scope_state owner read
        # and the ten-country ship (00490cd) added five middle-card pay helpers
        # whose two fee legs each read owner = ROOT inside random_scope_state;
        # walk() now follows that state transition, so all twelve are state-scoped.
        self.assert_source_owners(source("yongchang_world/common/scripted_effects/ywc_v03_tib_effects.txt"), 12)
        # Foundation keeps 12 source-owner predicates. The middle arc's four
        # pilot choices each check ownership in both display and execution;
        # the count is unchanged by the merged arc work and re-verified here.
        self.assert_source_owners(source("yongchang_world/events/ywc_v03_country_shu_events.txt"), 20)
        catalog = json.loads(source("data/content/v03/countries/shu.json"))
        def strings(value):
            if isinstance(value, str): yield value
            elif isinstance(value, list):
                for child in value: yield from strings(child)
            elif isinstance(value, dict):
                for child in value.values(): yield from strings(child)
        # Foundation stays at 12; the middle era gains one owner read from the
        # v03_shu_rural_workshop arc (2636ba0, rendered into the catalog by the
        # ten-country ship), keeping the provincial contract's original eight.
        for era, count in (("foundation", 12), ("middle", 9)):
            era_scripts = [text for arc in catalog["arcs"] if arc["era"] == era
                           for text in strings(arc)]
            self.assertEqual(sum(text.count("owner = ROOT") for text in era_scripts), count)
        scripts = [text for text in strings(catalog) if "owner = ROOT" in text or "is_owned_by" in text]
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
            # The shared harness records an internal modifier mirror key next to
            # name (clausewitz_harness add_modifier, b8588f9 "Fix native Shu
            # add_modifier parameters"); remove_modifier looks records up by it,
            # so the established recorded shape includes the mirror too.
            expected["modifier"] = expected["name"]
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
        source_names = ("ywc_shu_merchant_port_source", "ywc_shu_merchant_farm_source")
        branches = [(key, field(body, "limit")) for key, _, body, _ in walk(merchant)
                    if key in ("if", "else_if") and isinstance(body, list)
                    and any(node[0] in source_names for node in (field(body, "limit") or []))]
        self.assertEqual(branches, [("if", [(source_names[0], "=", "yes")]),
                                    ("else_if", [(source_names[1], "=", "yes")])])
        self.assertEqual(len([n for n in walk(merchant) if n[0] == "ywc_shu_accept_merchant_advance"]), 2)
        for kind in ("port", "farm"):
            for owner in ("SHU", "KOR", None):
                with self.subTest(source=kind, owner=owner):
                    w, _, _ = reached_offer(kind)
                    state = w.countries["SHU"]
                    state["states"][0].update(owner=owner, owned=owner == "SHU")
                    before = w.treasury["SHU"]
                    previous_queue = state.get("ywc_shu_pending_event")
                    self.assertEqual(w.conditions(field(option, "trigger"), "SHU"), owner == "SHU")
                    self.assertEqual([w.conditions(limit, "SHU") for _, limit in branches],
                                     [owner == "SHU" and kind == "port", owner == "SHU" and kind == "farm"])
                    w.execute([n for n in merchant if n[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")], "SHU")
                    if owner == "SHU":
                        self.assertEqual(state.get("ywc_shu_pending_event"), 1006)
                        self.assertEqual(state.get("ywc_shu_merchant_advance_unpaid"), 1)
                        self.assertGreater(state.get("ywc_shu_merchant_principal", 0), 0)
                        self.assertEqual(w.treasury["SHU"] - before, state["ywc_shu_merchant_principal"])
                        self.assertEqual(state.get("ywc_shu_merchant_repayment_months"), 0)
                        self.assertEqual(state.get("ywc_shu_merchant_consultation"), 1)
                        self.assertEqual(state.get("ywc_shu_local_prepayment_offer", 0), int(kind == "farm"))
                    else:
                        # Losing the pilot itself invalidates the whole offer;
                        # neither a loan nor a replacement queue may be made.
                        self.assertEqual(state.get("ywc_shu_pending_event"), previous_queue)
                        self.assertNotIn("ywc_shu_merchant_advance", state)
                        self.assertNotIn("ywc_shu_merchant_advance_unpaid", state)
                        self.assertEqual(w.treasury["SHU"], before)
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

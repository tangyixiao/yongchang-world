"""Literal native AST facts only; never instantiate Strict or read DMG source."""
import copy
import inspect
import unittest

from clausewitz_harness import parse
from dmg_market_runtime import DmgMarketWorld, market_test_facts
from test_v03_tib_foundation_lifecycle import TibWorldFacts


def literal_world():
    data = market_test_facts()
    world = DmgMarketWorld.__new__(DmgMarketWorld)
    TibWorldFacts.__init__(world, "", "", data.pop("countries"))
    world.tag, world.t, world._root_tag = "DMG", "dmg", "DMG"
    world.scope_ig = None
    for key, value in data.items():
        setattr(world, key, value)
    world.market_scope = world.treaty_scope = world.article_scope = None
    world._object_scope = None
    return world


def query(world, text):
    return world.conditions(parse(text), "DMG")


def treaty(source="SPA", target="DMG", participants=None, article_type="trade_privilege"):
    return {"id": "current_treaty", "participants": participants or [source, target],
            "articles": [{"type": article_type, "source_country": source,
                          "target_country": target}]}


PRIVILEGE = "ROOT.market.owner = { has_treaty_trade_privilege_with = { TARGET = c:PHI.market.owner } }"
IMPORTS = "market = { market_imports_reliance = { target = c:PHI.market value > 0.01 } }"


class DmgMarketNativeFacts(unittest.TestCase):
    def test_constructor_default_contract_without_reading_country_source(self):
        signature = inspect.signature(DmgMarketWorld.__init__)
        self.assertEqual(signature.parameters["tag"].default.upper(), "DMG")
        self.assertIs(signature.parameters["load_inline"].default, True)

    def test_market_identity_is_current_and_not_partner_tag_or_owner_equality(self):
        world = literal_world()
        q = "market_capital.market ?= c:PHI.market_capital.market"
        self.assertFalse(query(world, q))
        world.countries["PHI"]["market_id"] = "m_dmg"
        self.assertTrue(query(world, q))
        world.countries["PHI"]["market_id"] = "m_phi"
        world.markets["m_phi"]["owner"] = "DMG"
        self.assertFalse(query(world, q), "same owner is not the same market object")

    def test_owner_paths_and_fixed_root_survive_foreign_country_and_market_scopes(self):
        world = literal_world()
        self.assertTrue(query(world, "c:PHI.market.owner ?= c:SPA"))
        self.assertFalse(query(world, "c:PHI.market.owner ?= c:PHI"))
        self.assertTrue(query(world, "c:PHI = { market.owner = { ROOT.market.owner ?= c:DMG } }"))
        self.assertTrue(query(world, "ROOT.market = { owner ?= ROOT }"))
        self.assertFalse(query(world, "c:PHI.market = { owner ?= ROOT }"))
        world.markets["m_phi"]["owner"] = "JHG"
        self.assertTrue(query(world, "c:PHI.market.owner ?= c:JHG"))

    def test_current_market_owner_changes_the_real_privilege_target_and_receiver(self):
        world = literal_world()
        world.treaties = [treaty()]
        self.assertTrue(query(world, PRIVILEGE))
        world.markets["m_phi"]["owner"] = "JHG"
        self.assertFalse(query(world, PRIVILEGE))
        world.treaties = [treaty("JHG", "DMG")]
        self.assertTrue(query(world, PRIVILEGE))
        world.markets["m_dmg"]["owner"] = "LAN"
        self.assertFalse(query(world, PRIVILEGE))
        world.treaties = [treaty("JHG", "LAN")]
        self.assertTrue(query(world, PRIVILEGE))

    def test_native_treaty_helper_direction_pair_draft_and_withdrawal(self):
        world = literal_world()
        world.treaties = [treaty("SPA", "DMG")]
        self.assertTrue(query(world, PRIVILEGE), "DMG owner receives from target SPA owner")
        world.treaties = [treaty("DMG", "SPA")]
        self.assertFalse(query(world, PRIVILEGE))
        world.treaties = [treaty("SPA", "JHG")]
        self.assertFalse(query(world, PRIVILEGE))
        world.treaties = [treaty("PHI", "DMG")]
        self.assertFalse(query(world, PRIVILEGE), "partner tag is not its current market owner")
        world.treaties = []
        world.draft_treaties = [treaty()]
        self.assertFalse(query(world, PRIVILEGE))
        world.treaties.append(treaty())
        self.assertTrue(query(world, PRIVILEGE))
        world.treaties.clear()
        self.assertFalse(query(world, PRIVILEGE), "withdrawal removes the current treaty")

    def test_literal_treaty_article_scopes_execute_and_restore(self):
        world = literal_world()
        world.treaties = [treaty()]
        q = "any_scope_treaty = { binds = c:SPA any_scope_article = { has_type = trade_privilege source_country = c:SPA target_country = ROOT } }"
        self.assertTrue(query(world, q))
        self.assertIsNone(world.treaty_scope)
        self.assertIsNone(world.article_scope)
        self.assertFalse(query(world, q.replace("trade_privilege", "military_access")))

    def test_ui_metadata_does_not_replace_native_hidden_treaty_predicates(self):
        world = literal_world()
        q = "custom_description = { text = native_ui_key subject = this object = c:SPA hidden_trigger = { any_scope_treaty = { binds = c:SPA any_scope_article = { has_type = trade_privilege source_country = c:SPA } } } }"
        self.assertFalse(query(world, q))
        world.treaties = [treaty()]
        self.assertTrue(query(world, q))

    def test_malformed_current_treaty_or_article_never_becomes_a_boolean_pact(self):
        mutations = (
            lambda t: t.update(participants=["DMG", "SPA", "JHG"]),
            lambda t: t.update(participants=["DMG", "DMG"]),
            lambda t: t.update(participants=["DMG", "MISSING"]),
            lambda t: t.update(is_active=True),
            lambda t: t.update(articles="trade_privilege"),
            lambda t: t["articles"][0].update(source_country="JHG"),
            lambda t: t["articles"][0].update(target_country="SPA"),
            lambda t: t["articles"][0].pop("type"),
            lambda t: t["articles"][0].update(is_active=True),
        )
        for change in mutations:
            with self.subTest(change=change):
                world = literal_world()
                bad = treaty()
                change(bad)
                world.treaties = [bad]
                with self.assertRaises(AssertionError):
                    query(world, PRIVILEGE)
        for expression in (
            "has_treaty_trade_privilege_with = yes",
            "has_treaty_trade_privilege_with = { target = c:SPA }",
            "has_treaty_trade_privilege_with = { TARGET = c:SPA TARGET = c:JHG }",
            "has_treaty_trade_privilege_with = { TARGET > c:SPA }",
            "has_treaty_trade_privilege_with = { TARGET = c:SPA.market }",
        ):
            with self.subTest(expression=expression), self.assertRaises(AssertionError):
                query(literal_world(), expression)

    def test_imports_is_current_exact_target_and_strictly_above_one_percent(self):
        world = literal_world()
        self.assertTrue(query(world, IMPORTS))
        for number, expected in ((0, False), (.01, False), (.01001, True), (.2, True)):
            world.markets["m_dmg"]["imports_reliance"]["m_phi"] = number
            self.assertIs(query(world, IMPORTS), expected)
        world.countries["PHI"]["market_id"] = "m_jhg"
        self.assertFalse(query(world, IMPORTS))

    def test_imports_rejects_bad_shape_operator_scope_and_nonfinite_facts(self):
        for body in (
            "value > 0.01", "target = c:PHI.market", "target = c:PHI value > 0.01",
            "target = c:PHI.market target = c:JHG.market value > 0.01",
            "target = c:PHI.market value > 0.01 value > 0",
            "target ?= c:PHI.market value > 0.01",
            "target = c:PHI.market value ?= 0.01",
            "target = c:PHI.market value > NaN",
            "target = c:PHI.market value > 0.01 existing_pact = yes",
        ):
            with self.subTest(body=body), self.assertRaises(AssertionError):
                query(literal_world(), "market = { market_imports_reliance = { " + body + " } }")
        with self.assertRaises(AssertionError):
            query(literal_world(), "market_imports_reliance = { target = c:PHI.market value > 0.01 }")
        for bad in (float("nan"), float("inf"), True, "0.2"):
            world = literal_world()
            world.markets["m_dmg"]["imports_reliance"]["m_phi"] = bad
            with self.subTest(bad=bad), self.assertRaises(AssertionError):
                query(world, IMPORTS)

    def test_diplomacy_uses_current_pairs_and_positive_relation_not_zero(self):
        world = literal_world()
        q = "NOT = { has_war_with = c:PHI } NOT = { has_diplomatic_pact = { who = c:PHI type = embargo } } c:PHI = { NOT = { has_diplomatic_pact = { who = ROOT type = embargo } } } c:PHI.relations:root > 0"
        self.assertTrue(query(world, q))
        world.relations[("DMG", "PHI")] = 0
        self.assertFalse(query(world, q))
        world.relations[("DMG", "PHI")] = 20
        world.pacts.add(("PHI", "DMG", "embargo"))
        self.assertFalse(query(world, q))
        world.pacts = {("DMG", "PHI", "embargo")}
        self.assertFalse(query(world, q))
        world.pacts.clear()
        world.wars.add(frozenset(("DMG", "PHI")))
        self.assertFalse(query(world, q))
        self.assertTrue(query(world, "has_war_with = c:PHI"))
        self.assertTrue(query(world, "c:PHI = { has_war_with = ROOT }") )
        world.pacts = [["DMG", "PHI", "embargo"]]
        self.assertTrue(query(world, "has_diplomatic_pact = { who = c:PHI type = embargo }"))

    def test_alive_missing_country_junior_and_current_isolation_laws(self):
        world = literal_world()
        self.assertTrue(query(world, "c:PHI ?= { is_country_alive = yes is_junior_in_customs_union = no country_has_isolationism_or_sakoku = no }"))
        world.countries["PHI"]["alive"] = False
        self.assertFalse(query(world, "c:PHI = { is_country_alive = yes }"))
        del world.countries["PHI"]
        self.assertFalse(query(world, "exists = c:PHI"))
        self.assertFalse(query(world, "c:PHI ?= { is_country_alive = yes }"))
        world = literal_world()
        world.countries["PHI"]["junior_in_customs_union"] = True
        self.assertFalse(query(world, "c:PHI = { is_junior_in_customs_union = no }"))
        for law in ("law_isolationism", "law_sakoku"):
            world.countries["PHI"]["laws"] = [law]
            self.assertTrue(query(world, "c:PHI = { country_has_isolationism_or_sakoku = yes }"))
            self.assertTrue(query(world, "country_has_isolationism_or_sakoku = no"))

    def test_fixed_root_and_split_state_owner_cannot_borrow_foreign_port(self):
        world = literal_world()
        own_port = "any_scope_state = { owner = ROOT state_region = s:STATE_LUZON any_scope_building = { is_building_type = building_port occupancy >= 0.5 } }"
        self.assertFalse(query(world, own_port))
        self.assertTrue(query(world, "c:PHI = { " + own_port.replace("owner = ROOT", "owner = c:PHI") + " }"))
        self.assertFalse(query(world, "c:PHI = { " + own_port + " }"))
        self.assertTrue(query(world, "any_scope_state = { owner = ROOT market_access >= 0.75 any_scope_pop = { is_pop_type = bureaucrats is_employed = yes workplace ?= { is_building_type = building_government_administration occupancy >= 0.8 } } }"))
        self.assertIsNone(world.state_scope)
        self.assertIsNone(world.pop_scope)
        self.assertIsNone(world.building_scope)

    def test_scope_is_restored_on_nested_numeric_failure(self):
        world = literal_world()
        world.markets["m_phi"]["imports_reliance"]["m_dmg"] = float("nan")
        before = (world.state_scope, world.pop_scope, world.building_scope,
                  world.market_scope, world.treaty_scope, world.article_scope, world._object_scope)
        with self.assertRaises(AssertionError):
            query(world, "c:PHI = { market = { market_imports_reliance = { target = ROOT.market value > 0 } } }")
        after = (world.state_scope, world.pop_scope, world.building_scope,
                 world.market_scope, world.treaty_scope, world.article_scope, world._object_scope)
        self.assertEqual(after, before)
        self.assertEqual(world._root_tag, "DMG")
        self.assertTrue(query(world, "ROOT.market.owner ?= c:DMG"))

    def test_malformed_native_query_or_scope_and_unknown_api_are_rejected(self):
        for text in (
            "market > c:PHI.market", "market ?= c:PHI", "market.owner.foo = c:PHI",
            "has_war_with > c:PHI", "has_diplomatic_pact = { who = c:PHI }",
            "has_diplomatic_pact = { who = c:PHI type = embargo type = embargo }",
            "has_diplomatic_pact = { who = c:PHI type = is_active }",
            "is_country_alive > yes", "market = { is_country_alive = yes }",
            "market = { any_scope_treaty = { binds = c:SPA } }",
            "any_scope_article = { has_type = trade_privilege }",
            "any_scope_treaty = { is_active = yes }", "is_active_treaty = yes",
            "c:PHI = { existing_pact = yes }", "has_trade_route = yes",
            "market_access >= 0.75", "owner = ROOT",
        ):
            with self.subTest(text=text), self.assertRaises(AssertionError):
                query(literal_world(), text)

    def test_invalid_engine_fact_types_and_nonfinite_relations_fail_closed(self):
        for field, bad in (("alive", "yes"), ("alive", 1),
                           ("junior_in_customs_union", 0), ("laws", "law_isolationism")):
            world = literal_world()
            world.countries["PHI"][field] = bad
            query_key = {"alive": "is_country_alive", "junior_in_customs_union": "is_junior_in_customs_union",
                         "laws": "country_has_isolationism_or_sakoku"}[field]
            with self.subTest(field=field, bad=bad), self.assertRaises(AssertionError):
                query(world, f"c:PHI = {{ {query_key} = yes }}")
        world = literal_world()
        world.relations[("DMG", "PHI")] = float("nan")
        with self.assertRaises(AssertionError):
            query(world, "c:PHI.relations:root > 0")
        world = literal_world()
        world.countries["DMG"]["states"][0]["market_access"] = float("nan")
        with self.assertRaises(AssertionError):
            query(world, "any_scope_state = { owner = ROOT market_access >= 0.75 }")
        world = literal_world()
        world.countries["DMG"]["is_at_war"] = True
        world.wars = [("DMG", "MISSING")]
        with self.assertRaises(AssertionError):
            query(world, "is_at_war = yes")


if __name__ == "__main__":
    unittest.main()

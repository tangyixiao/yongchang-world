"""Literal engine primitives; no business-ready predicate is stubbed."""
import copy
import unittest

from clausewitz_harness import parse
from lan_public_runtime import LanPublicWorld
from test_v03_tib_foundation_lifecycle import TibWorldFacts


def world(groups):
    result = LanPublicWorld.__new__(LanPublicWorld)
    TibWorldFacts.__init__(result, "", "", {"LAN": {"igs": groups}})
    result.scope_ig = None
    return result


def query(w):
    return w.conditions(parse("""
    any_interest_group = {
        OR = { is_interest_group_type = ig_industrialists
               is_interest_group_type = ig_petty_bourgeoisie }
        is_in_government = yes ig_clout >= 0.10 ig_approval >= 0
    }
    """), "LAN")


class LanPublicFactPrimitives(unittest.TestCase):
    def test_country_building_query_aggregates_only_owned_states(self):
        w = world([])
        query_nodes = parse("any_scope_building = { is_building_type = building_government_administration level >= 2 }")
        w.countries["LAN"]["states"] = [
            {"owner": "DEI", "buildings": [{"type": "building_government_administration", "level": 3}]},
            {"owner": "LAN", "buildings": [{"type": "building_government_administration", "level": 1}]},
        ]
        self.assertFalse(w.conditions(query_nodes, "LAN"))
        self.assertIsNone(w.state_scope)
        self.assertIsNone(w.building_scope)
        w.countries["LAN"]["states"][1]["buildings"][0]["level"] = 2
        self.assertTrue(w.conditions(query_nodes, "LAN"))
        self.assertIsNone(w.state_scope)
        self.assertIsNone(w.building_scope)

    def test_building_level_is_a_scoped_numeric_fact(self):
        w = world([])
        with self.assertRaises(AssertionError):
            w.condition(("level", ">=", "3"), "LAN")
        w.building_scope = {"type": "building_gold_mine", "level": 3}
        self.assertTrue(w.condition(("level", ">=", "3"), "LAN"))
        self.assertFalse(w.condition(("level", ">", "3"), "LAN"))
        for leaf in (("level", "?=", "3"), ("level", ">=", "nan")):
            with self.assertRaises(AssertionError):
                w.condition(leaf, "LAN")

    def test_actual_clout_government_approval_and_identity_belong_to_one_group(self):
        good = {"type": "ig_industrialists", "clout": .1, "in_government": True, "approval": 0}
        self.assertTrue(query(world([good])))
        for key, value in (("clout", .099), ("in_government", False), ("approval", -1),
                           ("type", "ig_rural_folk")):
            current = {**good, key: value}
            w = world([current])
            self.assertFalse(query(w), (key, value))
            self.assertIsNone(w.scope_ig)
        self.assertFalse(query(world([
            {**good, "in_government": False, "clout": .5},
            {**good, "clout": .09},
        ])), "different IGs cannot supply different halves of the predicate")

    def test_empty_and_malformed_queries_fail_without_scope_leaks(self):
        w = world([{"type": "ig_industrialists", "clout": .2,
                    "in_government": True, "approval": 1}])
        for node in (
            ("any_interest_group", "=", []),
            ("any_interest_group", "!=", [("ig_clout", ">=", ".1")]),
            ("any_interest_group", "=", [("ig_clout", ">=", "nan")]),
            ("any_interest_group", "=", [("ig_clout", "?=", ".1")]),
            ("any_interest_group", "=", [("is_in_government", "=", "perhaps")]),
            ("any_interest_group", "=", [("is_in_government", "!=", "yes")]),
            ("any_interest_group", "=", [("clout", ">=", ".1")]),
            ("any_interest_group", "=", [("ig_clout", ">=", ".1"), ("ig_clout", ">=", ".2")]),
            ("any_interest_group", "=", [("NOT", "=", [])]),
        ):
            with self.subTest(node=node), self.assertRaises(AssertionError):
                w.condition(node, "LAN")
            self.assertIsNone(w.scope_ig)

    def test_native_ig_leaf_requires_actual_ig_scope(self):
        w = world([])
        for leaf in (("ig_clout", ">=", ".1"), ("is_in_government", "=", "yes")):
            with self.assertRaises(AssertionError):
                w.condition(leaf, "LAN")
        self.assertFalse(query(w))

    def test_clout_and_government_changes_are_read_at_each_evaluation(self):
        groups = [{"type": "ig_petty_bourgeoisie", "clout": .2,
                   "in_government": True, "approval": 0}]
        w = world(groups)
        self.assertTrue(query(w))
        saved = copy.deepcopy(w.countries)
        groups[0]["in_government"] = False
        self.assertFalse(query(w))
        w.countries = saved
        self.assertTrue(query(w))
        w.countries["LAN"]["igs"][0]["clout"] = .099
        self.assertFalse(query(w))


if __name__ == "__main__":
    unittest.main()

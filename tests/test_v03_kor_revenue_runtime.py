"""Literal state facts; no fiscal policy or clock is stubbed."""
import unittest

from clausewitz_harness import parse
from kor_revenue_runtime import KorRevenueWorld


def world(states):
    return KorRevenueWorld("kor", countries={"KOR": {"states": states}, "CHI": {"states": []}})


class KorRevenueNativeFacts(unittest.TestCase):
    def check_query(self, result):
        try:
            return result.conditions(parse("any_scope_state = { owner = ROOT turmoil <= 0.25 }"), "KOR")
        except AssertionError as error:
            self.fail(f"native state turmoil predicate is unavailable: {error}")

    def test_turmoil_belongs_to_the_same_owned_state(self):
        states = [{"owner": "CHI", "turmoil": .1}, {"owner": "KOR", "turmoil": .26}]
        result = world(states)
        self.assertFalse(self.check_query(result))
        self.assertIsNone(result.state_scope)
        states[1]["turmoil"] = .25
        self.assertTrue(self.check_query(result))
        self.assertIsNone(result.state_scope)
        states[1]["owner"] = "CHI"
        self.assertFalse(self.check_query(result))

    def test_live_boundary_is_read_on_every_evaluation(self):
        state = {"owner": "KOR", "turmoil": .25}
        result = world([state])
        self.assertTrue(self.check_query(result))
        state["turmoil"] = .250001
        self.assertFalse(self.check_query(result))
        state["turmoil"] = 0
        self.assertTrue(self.check_query(result))

    def test_country_scope_and_malformed_values_reject(self):
        result = world([])
        with self.assertRaises(AssertionError):
            result.condition(("turmoil", "<=", ".25"), "KOR")
        for state in ({}, {"turmoil": True}, {"turmoil": "0.2"}, {"turmoil": -1},
                      {"turmoil": 1.01}, {"turmoil": float("nan")}, {"turmoil": float("inf")}):
            result.state_scope = state
            with self.subTest(state=state), self.assertRaises(AssertionError):
                result.condition(("turmoil", "<=", ".25"), "KOR")
        result.state_scope = {"turmoil": .2}
        for node in (("turmoil", "?=", ".25"), ("turmoil", "<=", "nan"),
                     ("turmoil", "<=", [])):
            with self.subTest(node=node), self.assertRaises(AssertionError):
                result.condition(node, "KOR")

    def test_saved_native_state_identity_does_not_follow_another_owned_state(self):
        from kor_partner_protocol_runtime import StateRef
        selected = {"owner": "KOR", "turmoil": .1}
        result = world([selected])
        try:
            result.execute(parse("""every_scope_state = {
                limit = { owner = c:KOR } save_scope_as = original_pilot
            }
            set_variable = { name = pilot value = scope:original_pilot }
            """), "KOR")
        except AssertionError as error:
            self.fail(f"native saved state identity is unavailable: {error}")
        self.assertIsInstance(result.countries["KOR"]["pilot"], StateRef)
        check = parse("var:pilot = { owner = ROOT turmoil <= .25 }")
        self.assertTrue(result.conditions(check, "KOR"))
        selected["owner"] = "CHI"
        self.assertFalse(result.conditions(check, "KOR"))
        other = {"owner": "KOR", "turmoil": 0}
        result.countries["KOR"]["states"].append(other)
        result._register_states("KOR")
        self.assertFalse(result.conditions(check, "KOR"), "another owned state cannot replace the pilot")
        selected["owner"] = "KOR"
        self.assertTrue(result.conditions(check, "KOR"))
        result.countries["KOR"]["states"].remove(selected)
        self.assertFalse(result.conditions(check, "KOR"), "a vanished object cannot be used")


if __name__ == "__main__":
    unittest.main()

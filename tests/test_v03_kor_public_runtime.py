"""Literal movement facts and query-local strict IG facts; no court business stub."""
import copy
import unittest

from clausewitz_harness import parse
from kor_public_runtime import KorPublicWorld


def movement(**changes):
    return {"is_being_suppressed": True, "political_movement_radicalism": .25, **changes}


def world(movements=None, *, other=None, igs=None):
    return KorPublicWorld(countries={
        "KOR": {"states": [{"owner": "KOR", "region": "s:STATE_SEOUL", "buildings": [], "pops": []}],
                "movements": [] if movements is None else movements, "igs": [] if igs is None else igs},
        "CHI": {"states": [], "movements": [] if other is None else other, "igs": []},
    })


def check(result, expression, tag="KOR"):
    return result.conditions(parse(expression), tag)


QUERY = """any_political_movement = {
    is_being_suppressed = yes political_movement_radicalism >= .25 }"""


class KorPublicNativeFacts(unittest.TestCase):
    def test_installed_movement_query_is_available_and_live_at_the_native_boundary(self):
        row = movement()
        result = world([row])
        try:
            self.assertTrue(check(result, QUERY))
        except AssertionError as error:
            self.fail(f"native political-movement predicate unavailable: {error}")
        row["political_movement_radicalism"] = .24999
        self.assertFalse(check(result, QUERY))
        row["political_movement_radicalism"] = 1
        self.assertTrue(check(result, QUERY))
        row["is_being_suppressed"] = False
        self.assertFalse(check(result, QUERY))

    def test_suppression_and_radicalism_must_belong_to_one_actual_movement(self):
        rows = [movement(is_being_suppressed=False, political_movement_radicalism=.9),
                movement(political_movement_radicalism=.1)]
        result = world(rows)
        self.assertFalse(check(result, QUERY))
        rows[1]["political_movement_radicalism"] = .25
        self.assertTrue(check(result, QUERY))
        self.assertFalse(check(result, """any_political_movement = {
            AND = { is_being_suppressed = no political_movement_radicalism < .25 } }"""))

    def test_country_switch_reads_only_that_countrys_actual_movements(self):
        result = world([movement(political_movement_radicalism=.1)], other=[movement()])
        result.countries["KOR"].update(is_being_suppressed=True, political_movement_radicalism=1)
        self.assertFalse(check(result, QUERY))
        self.assertTrue(check(result, "c:CHI = { " + QUERY + " }"))
        self.assertFalse(check(result, QUERY))
        self.assertIsNone(result._current)
        self.assertEqual(result._stack, [])

    def test_explicit_empty_is_absence_but_missing_or_malformed_collection_rejects(self):
        result = world()
        self.assertFalse(check(result, QUERY))
        del result.countries["KOR"]["movements"]
        with self.assertRaises(AssertionError):
            check(result, QUERY)
        for actual in (None, {}, "none", [None], ["movement"], [[]]):
            result.countries["KOR"]["movements"] = actual
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                check(result, QUERY)

    def test_only_queried_movement_fields_are_required_without_default_values(self):
        result = world([{"is_being_suppressed": False}])
        self.assertTrue(check(result, "any_political_movement = { is_being_suppressed = no }"))
        with self.assertRaises(AssertionError):
            check(result, "any_political_movement = { political_movement_radicalism = 0 }")
        result.countries["KOR"]["movements"] = [{"political_movement_radicalism": 0}]
        self.assertTrue(check(result, "any_political_movement = { political_movement_radicalism = 0 }"))
        with self.assertRaises(AssertionError):
            check(result, "any_political_movement = { is_being_suppressed = no }")

    def test_numeric_facts_are_finite_native_fractions_and_rhs_is_a_literal_number(self):
        result = world()
        for actual in (None, True, "0.5", [], {}, -.001, 1.001, float("nan"), float("inf")):
            result.countries["KOR"]["movements"] = [movement(political_movement_radicalism=actual)]
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                check(result, QUERY)
        result.countries["KOR"]["movements"] = [movement()]
        for op, rhs in (("?=", ".25"), ("bad", "0"), ([], "0"),
                        (">", []), (">", True), (">", "nan"), (">", "inf"), (">", "var:radicalism")):
            node = ("any_political_movement", "=", [("political_movement_radicalism", op, rhs)])
            with self.subTest(op=op, rhs=rhs), self.assertRaises(AssertionError):
                result.condition(node, "KOR")

    def test_suppression_is_explicit_boolean_and_equality_only(self):
        result = world()
        for actual in (None, 0, 1, "yes", "no", {}, float("nan")):
            result.countries["KOR"]["movements"] = [movement(is_being_suppressed=actual)]
            with self.subTest(actual=actual), self.assertRaises(AssertionError):
                check(result, QUERY)
        result.countries["KOR"]["movements"] = [movement()]
        for op, rhs in (("!=", "yes"), ("?=", "yes"), (">", "no"), ("=", True), ("=", [])):
            node = ("any_political_movement", "=", [("is_being_suppressed", op, rhs)])
            with self.subTest(op=op, rhs=rhs), self.assertRaises(AssertionError):
                result.condition(node, "KOR")

    def test_unknown_or_malformed_query_is_rejected_even_with_no_movements(self):
        result = world()
        for node in (("any_political_movement", "?=", [("is_being_suppressed", "=", "yes")]),
                     ("any_political_movement", "=", []), ("any_political_movement", "=", "yes"),
                     ("any_political_movement", "=", [("public_business_ready", "=", "yes")]),
                     ("any_political_movement", "=", [("AND", ">", [])]),
                     ("any_political_movement", "=", [("NOT", "=", [])]),
                     ("any_political_movement", "=", [("is_being_suppressed", "=")]),
                     ("any_political_movement", "=", [None])):
            with self.subTest(node=node), self.assertRaises(AssertionError):
                result.condition(node, "KOR")
        with self.assertRaises(AssertionError):
            result.condition(("unrecognized_public_trigger", "=", "yes"), "KOR")

    def test_movement_scope_rejects_country_state_and_other_fact_borrowing(self):
        result = world([movement()])
        for leaf in (("is_being_suppressed", "=", "yes"),
                     ("political_movement_radicalism", ">=", ".25")):
            with self.subTest(leaf=leaf), self.assertRaises(AssertionError):
                result.condition(leaf, "KOR")
        for expression in ("any_scope_state = { " + QUERY + " }",
                           "any_political_movement = { c:CHI = { always = yes } }",
                           "any_political_movement = { any_interest_group = { ig_approval < 0 } }"):
            with self.subTest(expression=expression), self.assertRaises(AssertionError):
                check(result, expression)
            self.assertIsNone(result.state_scope)
            self.assertIsNone(result.building_scope)
            self.assertEqual(result._stack, [])

    def test_true_false_and_exception_restore_every_existing_scope_and_do_not_mutate_facts(self):
        row = movement()
        result = world([row], other=[movement()])
        names = ("state_scope", "building_scope", "pop_scope", "scope_ig", "market_scope",
                 "_current", "_root", "_prev", "_saved", "_stack", "_explicit_state_ref", "movement_scope")
        before = {key: getattr(result, key, None) for key in names}
        facts = copy.deepcopy(result.countries)
        for expression, expected in ((QUERY, True),
                                     ("any_political_movement = { political_movement_radicalism > .9 }", False),
                                     ("c:CHI = { " + QUERY + " }", True)):
            self.assertEqual(check(result, expression), expected)
            for name, original in before.items():
                self.assertIs(getattr(result, name, None), original, name)
        row["political_movement_radicalism"] = float("nan")
        with self.assertRaises(AssertionError):
            check(result, QUERY)
        for name, original in before.items():
            self.assertIs(getattr(result, name, None), original, name)
        row["political_movement_radicalism"] = .25
        other_row = result.countries["CHI"]["movements"][0]
        other_row["political_movement_radicalism"] = float("nan")
        with self.assertRaises(AssertionError):
            check(result, "c:CHI = { " + QUERY + " }")
        for name, original in before.items():
            self.assertIs(getattr(result, name, None), original, name)
        other_row["political_movement_radicalism"] = .25
        self.assertEqual(result.countries, facts)

    def test_ig_validates_only_fields_actually_queried_and_keeps_same_group_conjunction(self):
        old_style = {"type": "ig_landowners", "approval": -1}
        result = world(igs=[old_style])
        self.assertTrue(check(result, "any_interest_group = { is_interest_group_type = ig_landowners ig_approval < 0 }"))
        for field, op, rhs in (("is_in_government", "=", "no"), ("ig_clout", ">=", "0")):
            with self.subTest(field=field), self.assertRaises(AssertionError):
                result.condition(("any_interest_group", "=", [(field, op, rhs)]), "KOR")
        del old_style["approval"]
        self.assertTrue(check(result, "any_interest_group = { is_interest_group_type = ig_landowners }"))
        with self.assertRaises(AssertionError):
            check(result, "any_interest_group = { ig_approval >= 0 }")
        result.countries["KOR"]["igs"] = [
            {"type": "ig_landowners", "in_government": False, "clout": .2, "approval": 1},
            {"type": "ig_landowners", "in_government": True, "clout": .09, "approval": 1}]
        expression = """any_interest_group = { is_interest_group_type = ig_landowners
            is_in_government = yes ig_clout >= .1 ig_approval >= 0 }"""
        self.assertFalse(check(result, expression))
        result.countries["KOR"]["igs"][1]["clout"] = .1
        self.assertTrue(check(result, expression))

    def test_queried_ig_facts_reject_invalid_types_and_restore_scope_on_failure(self):
        result = world()
        for field, actual_key, op, rhs, bad_values in (
                ("is_in_government", "in_government", "=", "no", (0, "no", None)),
                ("ig_clout", "clout", ">=", "0", (True, "0.2", -.1, 1.1, float("nan"))),
                ("ig_approval", "approval", ">=", "0", (True, "0", None, float("inf")))):
            for bad in bad_values:
                result.countries["KOR"]["igs"] = [{actual_key: bad}]
                with self.subTest(field=field, bad=bad), self.assertRaises(AssertionError):
                    result.condition(("any_interest_group", "=", [(field, op, rhs)]), "KOR")
                self.assertIsNone(result.scope_ig)


if __name__ == "__main__":
    unittest.main()

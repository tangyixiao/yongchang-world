"""Permanent native-source contracts for MGL offer and current obligations.

This file deliberately imports the frozen actual-history fixture.  It never
imports PLANWS data, seeds an MGL route/payment/terms variable, or treats a
defer choice as a paid offer.
"""
from copy import deepcopy
import unittest

from tests.test_v03_mgl_actual_source import (
    TAG, PREFIX, MGL_ARCS, actual_mgl_admission_world, pulse_actual_journals,
    choose_actual_option, _block,
)
from tests.test_v03_mgl_actual_source import _ordinary_facts


ARC_EVENTS = {"roads": "ywc_mng.1000", "debt": "ywc_mng.1010",
              "grain": "ywc_mng.1020"}
ROUTE_SUFFIX = {1: "dual", 2: "single", 3: "local"}
ARC_SLUG = {prefix: slug for slug, prefix in PREFIX.items()}
HELPERS = tuple(f"ywc_mgl_{arc}_{name}" for arc in ARC_EVENTS for name in (
    "any_affordable_entry_offer", "selected_current_obligation",
    "current_obligation_ready"))


def _missing_helpers(world):
    return [name for name in HELPERS if name not in world.strict_trigger_defs]


def _event_option_trigger(world, event_id, suffix):
    event = world.event_defs[event_id]
    option = next(value for key, _, value in event if key == "option" and
                  _block(value, "name") == event_id + "." + suffix)
    return next((value for key, _, value in option if key == "trigger"), [])


def _paid_option_truths(world, arc):
    event_id = ARC_EVENTS[arc]
    return {route: world.conditions(_event_option_trigger(world, event_id, suffix), TAG)
            for route, suffix in ROUTE_SUFFIX.items()}


def _pay_native_route(world, arc, route):
    """Reach an actual entry card and execute its native paid route option."""
    target = ARC_EVENTS[arc]
    wanted = ROUTE_SUFFIX[route]
    for _ in range(60):
        event_id = pulse_actual_journals(world)
        if event_id is None:
            continue
        if event_id == target:
            choose_actual_option(world, event_id, wanted)
            return event_id
        if event_id in ARC_EVENTS.values():
            raise AssertionError(("target_first_native_entry_event_expected", arc, route,
                                  event_id))
        raise AssertionError(("unexpected_event_before_native_payment", arc, route, event_id))
    raise AssertionError(("native_paid_entry_card_not_reached", arc, route))


def _without_only_terms_clauses(body, prefix, route):
    """Return a strict route-body AST with just its two terms clauses removed."""
    terms = f"ywc_mgl_{prefix}_terms_committed"
    kept = []
    for clause in body:
        key, comparison, value = clause
        if ((key == "has_variable" and comparison == "=" and value == terms) or
                (key == f"var:{terms}" and comparison == "=" and value == str(route))):
            continue
        kept.append(clause)
    if len(kept) != len(body) - 2:
        raise AssertionError(("strict_route_terms_ast_not_exactly_two_clauses", prefix,
                             route, body, kept))
    return kept


def _selected_expected_from_strict_ast(world, arc):
    """Evaluate only the old selected full/one/local AST after terms removal."""
    prefix = arc
    state = world.countries[TAG]
    route = int(state.get(f"ywc_mgl_{prefix}_route", 0))
    if route not in (1, 2, 3):
        return False
    strict_body = world.strict_trigger_defs[f"ywc_mgl_{prefix}_{'full' if route == 1 else 'one' if route == 2 else 'local'}_ready"]
    stripped = _without_only_terms_clauses(strict_body, prefix, route)
    return world.conditions(stripped, TAG)


def _ordinary_route_facts(arc, route):
    facts = deepcopy(_ordinary_facts())
    facts["gold_reserves"] = 10000
    if arc == "roads":
        facts["states"][0]["market_access"] = {1: .80, 2: .50, 3: .35}[route]
        # Keep the legacy/root admission's minimal tea signal in every recipe;
        # access/law still make the chosen route unique (route 3 has access .35).
        facts["market"]["tea"]["exports"] = {1: 60, 2: 1, 3: 1}[route]
        facts["market"]["grain"]["imports"] = 1 if route == 3 else 0
        facts["relations"] = {"SHU": 0, "RUS": 0 if route == 1 else -10}
        facts["laws"].discard("law_tenant_farmers")
        facts["laws"].discard("law_homesteading")
        facts["laws"].discard("law_serfdom")
        if route == 1:
            facts["laws"].add("law_mercantilism")
        else:
            facts["laws"].discard("law_mercantilism")
    elif arc == "debt":
        facts["laws"].discard("law_mercantilism")
        facts["laws"].discard("law_tenant_farmers")
        facts["laws"].discard("law_homesteading")
        facts["laws"].discard("law_serfdom")
        facts["laws"].add({1: "law_tenant_farmers", 2: "law_homesteading",
                           3: "law_serfdom"}[route])
        facts["states"][0]["average_sol"] = 8 if route == 2 else 11
        if route == 2:
            facts["states"][0]["average_sol"] = 8
    else:
        facts["market"]["grain"]["pricier"] = {1: .30, 2: .18, 3: .11}[route]
        facts["market"]["grain"]["imports"] = 0
        facts["military_expenses_share"] = .10 if route == 1 else 0
    return facts


class MglQualificationContractMatrix(unittest.TestCase):
    def test_exact_helpers_are_present_in_native_source(self):
        world, _ = actual_mgl_admission_world()
        self.assertEqual(_missing_helpers(world), [],
                         "expected native helper-contract RED; no evaluator unknowns")

        # These helpers must be callable by the strict actual-source evaluator.
        # Every new definition is parsed from the live native trigger file.
        for helper in HELPERS:
            yes = world.condition((helper, "=", "yes"), TAG)
            no = world.condition((helper, "=", "no"), TAG)
            self.assertNotEqual(yes, no, helper)

    def test_unpaid_offer_matches_real_paid_option_or_at_cash_and_fiscal_edges(self):
        # Fees are initialized from ordinary income by the authored initializer:
        # quote=100, double=200, single=100, local=50 at this income.
        expected_route_sets = {
            "roads": {50: {3}, 100: {2, 3}, 200: {1, 2, 3}},
            "debt": {50: {3}, 100: {3}, 200: {1, 3}},
            "grain": {50: {3}, 100: {2, 3}, 200: {1, 2, 3}},
        }
        for arc in ARC_EVENTS:
            for reserves in (50, 100, 200):
                with self.subTest(arc=arc, reserves=reserves):
                    world, _ = actual_mgl_admission_world(ordinary_facts=_ordinary_facts())
                    state = world.countries[TAG]
                    state["gold_reserves"] = reserves
                    observed_options = _paid_option_truths(world, arc)
                    self.assertEqual({r for r, enabled in observed_options.items() if enabled},
                                     expected_route_sets[arc][reserves])
                    helper = f"ywc_mgl_{arc}_any_affordable_entry_offer"
                    self.assertTrue(helper in world.strict_trigger_defs,
                                    f"expected missing-helper RED after checking actual paid options: {helper}")
                    actual_offer = world.condition(
                        (helper, "=", "yes"), TAG)
                    self.assertEqual(actual_offer, any(observed_options.values()),
                                     (arc, reserves, observed_options))
                    current_helper = f"ywc_mgl_{arc}_current_obligation_ready"
                    self.assertTrue(current_helper in world.strict_trigger_defs,
                                    f"expected missing current-helper RED after unpaid option matrix: {current_helper}")
                    current_obligation = world.condition((current_helper, "=", "yes"), TAG)
                    self.assertEqual(current_obligation, any(observed_options.values()),
                                     (arc, reserves, "unpaid current readiness equals affordable offer OR"))
                    selected_helper = f"ywc_mgl_{arc}_selected_current_obligation"
                    self.assertTrue(selected_helper in world.strict_trigger_defs,
                                    f"expected missing selected-helper RED for an unpaid arc: {selected_helper}")
                    self.assertFalse(world.condition((selected_helper, "=", "yes"), TAG),
                                     (arc, reserves, "unpaid arc has no selected route"))
                    self.assertEqual(state.get(f"ywc_mgl_{arc}_route_paid", 0), 0)
                    self.assertEqual(state.get(f"ywc_mgl_{arc}_route", 0), 0)

            for fiscal_mutation in ("default", "bankruptcy"):
                with self.subTest(arc=arc, fiscal_mutation=fiscal_mutation):
                    world, _ = actual_mgl_admission_world()
                    state = world.countries[TAG]
                    if fiscal_mutation == "default":
                        state["in_default"] = True
                    else:
                        state["modifiers"].add("declared_bankruptcy")
                    options = _paid_option_truths(world, arc)
                    self.assertEqual(options, {1: False, 2: False, 3: False}, options)
                    helper = f"ywc_mgl_{arc}_any_affordable_entry_offer"
                    self.assertTrue(helper in world.strict_trigger_defs,
                                    f"expected missing-helper RED after checking fiscal option gates: {helper}")
                    self.assertFalse(world.condition(
                        (helper, "=", "yes"), TAG))
                    current_helper = f"ywc_mgl_{arc}_current_obligation_ready"
                    self.assertTrue(current_helper in world.strict_trigger_defs,
                                    f"expected missing current-helper RED after fiscal option matrix: {current_helper}")
                    self.assertFalse(world.condition((current_helper, "=", "yes"), TAG))
                    selected_helper = f"ywc_mgl_{arc}_selected_current_obligation"
                    self.assertTrue(selected_helper in world.strict_trigger_defs,
                                    f"expected missing selected-helper RED under fiscal exclusion: {selected_helper}")
                    self.assertFalse(world.condition((selected_helper, "=", "yes"), TAG))

            with self.subTest(arc=arc, reserves=49, no_affordable_route=True):
                world, _ = actual_mgl_admission_world()
                state = world.countries[TAG]
                state["gold_reserves"] = 49
                options = _paid_option_truths(world, arc)
                self.assertEqual(options, {1: False, 2: False, 3: False}, options)
                offer_helper = f"ywc_mgl_{arc}_any_affordable_entry_offer"
                current_helper = f"ywc_mgl_{arc}_current_obligation_ready"
                self.assertTrue(offer_helper in world.strict_trigger_defs,
                                f"expected missing offer-helper RED at unaffordable boundary: {offer_helper}")
                self.assertTrue(current_helper in world.strict_trigger_defs,
                                f"expected missing current-helper RED at unaffordable boundary: {current_helper}")
                self.assertFalse(world.condition((offer_helper, "=", "yes"), TAG))
                self.assertFalse(world.condition((current_helper, "=", "yes"), TAG))
                selected_helper = f"ywc_mgl_{arc}_selected_current_obligation"
                self.assertTrue(selected_helper in world.strict_trigger_defs,
                                f"expected missing selected-helper RED when there is no offer: {selected_helper}")
                self.assertFalse(world.condition((selected_helper, "=", "yes"), TAG))

            # Defer has no trigger and is intentionally excluded from the OR.
            world, _ = actual_mgl_admission_world()
            defer_trigger = _event_option_trigger(world, ARC_EVENTS[arc], "defer")
            self.assertEqual(defer_trigger, [], (arc, "defer must not be an offer term"))

    def test_actual_paid_routes_match_only_terms_stripped_strict_route_ast(self):
        for arc in ARC_EVENTS:
            for route in (1, 2, 3):
                with self.subTest(arc=arc, route=route):
                    target_slug = ARC_SLUG[arc]
                    admission_order = [target_slug] + [a["slug"] for a in MGL_ARCS
                                                       if a["slug"] != target_slug]
                    world, _ = actual_mgl_admission_world(admission_order=admission_order,
                        ordinary_facts=_ordinary_route_facts(arc, route))
                    treasury_before = world.treasury[TAG]
                    entry_event = _pay_native_route(world, arc, route)
                    state = world.countries[TAG]
                    prefix = arc
                    fee_suffix = {1: "double_fee", 2: "fee", 3: "half_fee"}[route]
                    expected_fee = state[f"ywc_mgl_{prefix}_{fee_suffix}"]
                    self.assertEqual(entry_event, ARC_EVENTS[arc])
                    self.assertEqual(treasury_before - world.treasury[TAG], expected_fee,
                                     (arc, route, "source option must make the actual fee debit"))
                    self.assertEqual(state.get(f"ywc_mgl_{prefix}_route_paid"), 1)
                    self.assertEqual(state.get(f"ywc_mgl_{prefix}_route"), route)
                    self.assertNotIn(f"ywc_mgl_{prefix}_terms_committed", state)
                    qualification_suffix = {1: "full", 2: "one", 3: "local"}[route]
                    self.assertFalse(world.condition(
                        (f"ywc_mgl_{prefix}_{qualification_suffix}_ready", "=", "yes"), TAG))

                    # Make the genuine route-specific transition after its real fee:
                    # debt 2 SoL 8->10; grain route 1 entry price .30->execution .10,
                    # with imports and administration staffed only in execution.
                    if arc == "debt" and route == 2:
                        state["states"][0]["average_sol"] = 10
                    if arc == "grain":
                        state["market"]["grain"]["pricier"] = {1: .10, 2: .18, 3: .24}[route]
                        state["market"]["grain"]["imports"] = 1
                    if arc == "debt" and route == 3:
                        state["buildings"] = [b for b in state["buildings"]
                                               if "bg_livestock_ranches" not in b.get("groups", set())]
                        state["states"][0]["buildings"] = [b for b in state["states"][0]["buildings"]
                                                            if "bg_livestock_ranches" not in b.get("groups", set())]
                        state["states"][0]["pops"] = [p for p in state["states"][0]["pops"]
                                                       if p.get("workplace") != "building_livestock_ranch"]
                    # These are entry/payment gates; they are absent from the paid
                    # current-obligation AST and must remain absent here as well.
                    state["in_default"] = True
                    state["is_at_war"] = True
                    state["modifiers"].add("declared_bankruptcy")

                    strict_ast_expected = _selected_expected_from_strict_ast(world, arc)
                    self.assertTrue(strict_ast_expected,
                                    (arc, route, "native paid route fact recipe must qualify"))
                    selected_helper = f"ywc_mgl_{prefix}_selected_current_obligation"
                    current_helper = f"ywc_mgl_{prefix}_current_obligation_ready"
                    self.assertTrue(selected_helper in world.strict_trigger_defs,
                                    f"expected missing selected-helper RED after actual paid positive: {selected_helper}")
                    self.assertTrue(current_helper in world.strict_trigger_defs,
                                    f"expected missing current-helper RED after actual paid positive: {current_helper}")
                    selected = world.condition(
                        (selected_helper, "=", "yes"), TAG)
                    current = world.condition(
                        (current_helper, "=", "yes"), TAG)
                    self.assertEqual(selected, strict_ast_expected, (arc, route, "strict AST relation"))
                    self.assertEqual(current, strict_ast_expected, (arc, route, "paid current obligation"))

                    # A route-specific failure must turn the obligation false without
                    # relying on terms, payment/default, war, or an entry-only proxy.
                    if arc == "roads":
                        if route == 1:
                            state["relations"]["RUS"] = -1
                        elif route == 2:
                            state["states"][0]["market_access"] = .49
                        else:
                            state["market"]["grain"]["imports"] = 0
                    elif arc == "debt":
                        if route == 1:
                            state["laws"].discard("law_tenant_farmers")
                        elif route == 2:
                            state["market"]["wool"]["exports"] = 0
                        else:
                            # Local current obligation must not regain entry ranch/job facts.
                            state["laws"].discard("law_serfdom")
                    else:
                        if route == 1:
                            state["market"]["grain"]["pricier"] = .15
                        elif route == 2:
                            state["market"]["grain"]["pricier"] = .20
                        else:
                            state["market"]["grain"]["pricier"] = .25
                    false_expected = _selected_expected_from_strict_ast(world, arc)
                    self.assertFalse(false_expected, (arc, route, "perturbed route fact must fail"))
                    self.assertEqual(world.condition(
                        (selected_helper, "=", "yes"), TAG),
                        false_expected, (arc, route, "selected obligation should follow route facts"))
                    self.assertEqual(world.condition(
                        (current_helper, "=", "yes"), TAG),
                        false_expected, (arc, route, "current obligation should follow route facts"))


if __name__ == "__main__":
    unittest.main()

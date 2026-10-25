"""A rejected grain inquiry can continue domestically without inventing foreign aid.

Execute the authored catalog, generated option nodes and real JE lifecycle with
country/state facts; no readiness predicate or eligibility result is overridden.
"""
import copy
from pathlib import Path
import unittest

from tests.clausewitz_harness import parse
from tests.test_v03_nqg_foundation import (
    NqgWorldFactsRuntime, _arc, _catalog, _script_condition,
)


ROOT = Path(__file__).resolve().parents[1]
PREFIX = "ywc_nqg_winter_"
REFUSAL = PREFIX + "e1005_refuse_loan_terms"
CONSEQUENCE = {
    "en": "If you requested external grain aid, switch to the domestic stipend-cap route; existing domestic routes stay selected. Domestic staffing and finance requirements still apply. No outside grain is counted as received.",
    "zh": "若先前申请外部粮援，本项改走国内限额供养路线；原已选择的国内路线保持不变。仍须满足国内人员与财政条件，不会把外部粮食记作已收到。",
}


def _world():
    return NqgWorldFactsRuntime({
        "NQG": {
            "ywc_v03_initialized": 1, "ywc_v03_release_version": 3,
            "ywc_v03_active_arc_count": 0, "ywc_v03_visible_task_count": 0,
            "yearly_gross_income": 52000, "gold_reserves": 20000,
            "bureaucracy": 100, "net_fixed_income": 1, "scaled_debt": 0,
            "government_legitimacy": 35, "laws": ["law_mercantilism"],
            "states": [{"owner": "NQG", "market_access": 1.0, "buildings": [
                {"type": "building_government_administration", "occupancy": 0.9,
                 "goods_shortage": False},
                {"type": "building_barrack", "occupancy": 0.9, "goods_shortage": False},
                {"group": "bg_agriculture", "occupancy": 0.7, "goods_shortage": False},
            ]}],
        },
        "ALLY": {"diplomatic_pacts": ["alliance"], "relations_to_root": 20,
                 "gold_reserves": 10000, "scaled_debt": 0},
    })


def _option(event_id, key):
    arc = _arc(_catalog(), "v03_nqg_winter_court")
    event = next(event for event in arc["events"] if event["id"] == event_id)
    return next(option for option in event["options"] if option["key"] == key)


def _generated_refusal():
    events = parse((ROOT / "yongchang_world/events/ywc_v03_country_nqg_events.txt")
                   .read_text(encoding="utf-8-sig"))
    event = next(body for key, _, body in events if key == "ywc_nqg.1005")
    return next(body for key, _, body in event if key == "option" and
                ("name", "=", "ywc_nqg.1005.refuse_loan_terms") in body)


def _executable_option(nodes):
    # Strip only top-level metadata and text-only tooltip wrappers. Any hidden
    # effect, including one inside a tooltip, stays executable (or fails loudly
    # as an unsupported instruction); never silently drop a non-text effect.
    return [node for node in nodes if node[0] not in ("name", "trigger", "ai_chance")
            and not (node[0] == "custom_tooltip" and isinstance(node[2], list)
                     and all(child[0] == "text" for child in node[2]))]


def _refuse(world, surface):
    if surface == "catalog":
        option = _option("ywc_nqg.1005", "refuse_loan_terms")
        trigger = parse("condition = " + option["trigger"])[0][2]
        effects = parse("effect = " + option["effect"])[0][2]
    else:
        option = _generated_refusal()
        trigger = next(body for key, _, body in option if key == "trigger")
        effects = _executable_option(option)
    if not world.conditions(trigger, "NQG"):
        raise AssertionError("the selected refusal must always be available")
    world.execute(effects, "NQG")


class NqgWinterDomesticFallbackTest(unittest.TestCase):
    def _await(self, world, arc, event_id):
        for _ in range(9):
            world.advance_months(1)
            delivered = world.pulse(world.current_driver(arc))
            if event_id in delivered:
                return
            # Route 3 cannot qualify for domestic execution, so its real wait
            # may earn the authored 12-month notice before the refusal arrives.
            if "ywc_nqg.1009" in delivered:
                self.assertIn(PREFIX + "notice12_open", world.countries["NQG"])
                world.choose("ywc_nqg.1009", "acknowledge_12_month_notice")
            else:
                self.assertEqual(delivered, [])
        self.fail("authored event was not delivered: " + event_id)

    def _reach_refusal(self):
        world = _world()
        arc = _arc(_catalog(), "v03_nqg_winter_court")
        world.enter(arc["journals"][0])
        self.assertEqual(world.pulse(world.current_driver(arc)), ["ywc_nqg.1000"])
        self.assertTrue(_script_condition(world, "{ ywc_nqg_winter_loan_ready = yes }", "NQG"))
        world.choose("ywc_nqg.1000", "grain_loan")
        state = world.countries["NQG"]
        self.assertEqual(state[PREFIX + "route"], 3)
        self.assertEqual(state[PREFIX + "fee"], 1000)
        self.assertEqual(state[PREFIX + "half_fee"], 500)
        self.assertEqual(world.treasury, {"NQG": -1000, "ALLY": 0})
        # A later income change and repeated cost/payment helpers must retain
        # the actual captured fee and original single sunk payment.
        state["yearly_gross_income"] = 104000
        world.run(PREFIX + "capture_cost_base", "NQG")
        world.run(PREFIX + "pay_filing_fee_once", "NQG")
        for event, choice in ((1001, "cap_household"), (1002, "audit_districts"),
                              (1003, "cap_soldiers"), (1004, "cap_market")):
            self._await(world, arc, f"ywc_nqg.{event}")
            world.choose(f"ywc_nqg.{event}", choice)
        self.assertIn(arc["journals"][0]["id"], world.completed_journals["NQG"])
        self.assertEqual(world.current_driver(arc)["id"], arc["journals"][1]["id"])
        # The ally is gone by the terms decision. No eligibility override is
        # used; the real partner predicate must now fail.
        self.assertEqual(world.countries["ALLY"], {
            "diplomatic_pacts": ["alliance"], "relations_to_root": 20,
            "gold_reserves": 10000, "scaled_debt": 0,
        })
        self.assertEqual(world.treasury["ALLY"], 0)
        del world.countries["ALLY"]
        # Retire the removed country's interpreter bookkeeping alongside its
        # world facts; the production interpreter itself remains unchanged.
        for countries in (world.treasury, world.months_until_expiry, world.days_until_expiry,
                          world.active_journals, world.terminal_journals,
                          world.completed_journals, world.failed_journals):
            countries.pop("ALLY")
        self.assertFalse(_script_condition(world, "{ ywc_nqg_winter_loan_ready = yes }", "NQG"))
        self._await(world, arc, "ywc_nqg.1005")
        return world, arc

    def _fallback_and_observe(self):
        world, arc = self._reach_refusal()
        state = world.countries["NQG"]
        world.choose("ywc_nqg.1005", "refuse_loan_terms")
        self.assertEqual(state[PREFIX + "route"], 1, "refusal left the external inquiry selected")
        self.assertEqual(state[PREFIX + "stance_cap_stipend"], 1)
        self.assertNotIn(PREFIX + "stance_grain_loan", state)
        for key, value in (("st1000_grain_loan", 1), ("fee_paid", 1), ("captured_income", 1),
                           ("fee", 1000), ("half_fee", 500), ("implementation_started", 1),
                           ("route_lock", 1), ("pending", 1006), ("stage", 1006)):
            self.assertEqual(state[PREFIX + key], value, key)
        self.assertNotIn(PREFIX + "st1000_cap_stipend", state)
        self.assertEqual(world.treasury, {"NQG": -1000})
        self.assertEqual(state["gold_reserves"], 19000)
        self.assertNotIn(PREFIX + "six_months_complete", state)
        full = _option("ywc_nqg.1009", "settle_full")["trigger"]
        self.assertFalse(_script_condition(world, full, "NQG"))

        world.advance_months(1)
        self.assertEqual(world.pulse(world.current_driver(arc)), [])
        self.assertEqual(world.days_until_expiry["NQG"][PREFIX + "observation_timer"], 180)
        self.assertIn(PREFIX + "observation_started", state)
        choices = {"ywc_nqg.1006": "publish_count", "ywc_nqg.1007": "make_standing_rule"}
        chosen = []
        for month in range(1, 7):
            world.advance_months(1)
            delivered = world.pulse(world.current_driver(arc))
            for event_id in delivered:
                self.assertIn(event_id, choices)
                world.choose(event_id, choices[event_id])
                chosen.append(event_id)
            if month < 6:
                self.assertNotIn(PREFIX + "six_months_complete", state)
                self.assertFalse(_script_condition(world, full, "NQG"))
        self.assertEqual(chosen, ["ywc_nqg.1006", "ywc_nqg.1007"])
        self.assertIn(PREFIX + "six_months_complete", state)
        self.assertTrue(_script_condition(world, "{ ywc_nqg_winter_full_ready = yes }", "NQG"))
        self.assertIn(arc["journals"][1]["id"], world.completed_journals["NQG"])
        self.assertEqual(world.current_driver(arc)["id"], arc["journals"][2]["id"])
        return world, arc

    def test_grain_inquiry_refusal_completes_domestically_after_real_observation(self):
        world, arc = self._fallback_and_observe()
        self._await(world, arc, "ywc_nqg.1008")
        world.choose("ywc_nqg.1008", "hold_buffer")
        self._await(world, arc, "ywc_nqg.1009")
        self.assertTrue(_script_condition(world, _option("ywc_nqg.1009", "settle_full")["trigger"], "NQG"))
        world.choose("ywc_nqg.1009", "settle_full")
        state = world.countries["NQG"]
        self.assertEqual(state["ywc_v03_nqg_v03_nqg_winter_court_outcome"], 3)
        self.assertEqual(state["ywc_v03_nqg_v03_nqg_winter_court_settled"], 1)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
        self.assertTrue(_script_condition(world, arc["journals"][-1]["goal"], "NQG"))
        self.assertFalse(_script_condition(world, arc["journals"][-1]["exit_conditions"], "NQG"))
        self.assertEqual(world.completed_journals["NQG"], {journal["id"] for journal in arc["journals"]})
        self.assertEqual(world.active_journals["NQG"], set())
        self.assertEqual(world.failed_journals["NQG"], set())
        self.assertEqual(world.treasury, {"NQG": -1000})
        self.assertEqual((state["gold_reserves"], state["scaled_debt"]), (19000, 0))
        self.assertEqual(state[PREFIX + "st1000_grain_loan"], 1)
        self.assertEqual(state[PREFIX + "fee_paid"], 1)
        self.assertNotIn(PREFIX + "st1005_take_loan_terms", state)
        self.assertNotIn(PREFIX + "pending", state)
        before = copy.deepcopy((world.countries, world.treasury, world.journals))
        world.run(PREFIX + "close_as_established", "NQG")
        world.run(PREFIX + "release_slot", "NQG")
        self.assertEqual((world.countries, world.treasury, world.journals), before)
        with self.assertRaisesRegex(AssertionError, "actually active journal"):
            world.pulse(arc["journals"][-1])

    def test_fallback_still_requires_current_domestic_staffing_legitimacy_and_finance(self):
        world, _ = self._fallback_and_observe()
        baseline = copy.deepcopy(world.countries["NQG"])
        for loss in ("office", "legitimacy", "default", "bureaucracy", "income"):
            with self.subTest(loss=loss):
                state = copy.deepcopy(baseline)
                world.countries["NQG"] = state
                if loss == "office":
                    state["states"][0]["buildings"][0]["occupancy"] = 0.79
                else:
                    key, value = {"legitimacy": ("government_legitimacy", 29),
                                  "default": ("in_default", True),
                                  "bureaucracy": ("bureaucracy", -1),
                                  "income": ("net_fixed_income", -1)}[loss]
                    state[key] = value
                for predicate in ("route_execution_ready", "full_ready"):
                    self.assertFalse(_script_condition(world, "{ " + PREFIX + predicate + " = yes }", "NQG"))
                self.assertFalse(_script_condition(world, _option("ywc_nqg.1009", "settle_full")["trigger"], "NQG"))
                world.run(PREFIX + "close_as_established", "NQG")
                self.assertNotIn("ywc_v03_nqg_v03_nqg_winter_court_outcome", state)
                self.assertEqual(state[PREFIX + "fee_paid"], 1)
                self.assertEqual((state["gold_reserves"], world.treasury["NQG"]), (19000, -1000))

    def test_selected_refusal_preserves_paid_state_across_catalog_and_generated_boundaries(self):
        for surface in ("catalog", "generated"):
            for route in (1, 2, 3, None, 99):
                with self.subTest(surface=surface, route=route):
                    world = _world()
                    arc = _arc(_catalog(), "v03_nqg_winter_court")
                    world.enter(arc["journals"][0])
                    opening = {1: "cap_stipend", 2: "local_share"}.get(route, "grain_loan")
                    world.choose("ywc_nqg.1000", opening)
                    state = world.countries["NQG"]
                    if route is None:
                        state.pop(PREFIX + "route")
                    else:
                        state[PREFIX + "route"] = route
                    # Boundary fixtures retain both live and historical protected
                    # state, including a future deferred obligation the selected
                    # option must not clear when it advances to stage 1006.
                    state.update({PREFIX + key: value for key, value in {
                        "stage": 1005, "pending": 1005, "implementation_started": 1,
                        "route_lock": 1, "notice12_pending": 1, "notice12_open": 1,
                        "notice36_pending": 1, "notice36_intent": 1,
                        "deferred_event": 1007, "observation_started": 1,
                        "observation_timer": 1, "limited_target": 1,
                    }.items()})
                    before = copy.deepcopy(world.countries)
                    expected = copy.deepcopy(before)
                    expected["NQG"].update({PREFIX + "st1005_refuse_loan_terms": 1,
                                            PREFIX + "pending": 1006, PREFIX + "stage": 1006})
                    if route == 3:
                        expected["NQG"][PREFIX + "route"] = 1
                        expected["NQG"].pop(PREFIX + "stance_grain_loan")
                        expected["NQG"][PREFIX + "stance_cap_stipend"] = 1
                    protected = copy.deepcopy((world.treasury, world.modifiers, world.journals,
                                               world.months_until_expiry, world.days_until_expiry))
                    _refuse(world, surface)
                    self.assertEqual(world.countries, expected)
                    self.assertEqual((world.treasury, world.modifiers, world.journals,
                                      world.months_until_expiry, world.days_until_expiry), protected)
                    after = copy.deepcopy(world.countries)
                    world.run(REFUSAL, "NQG")
                    self.assertEqual(world.countries, after)
                    self.assertEqual(world.treasury, protected[0])
                    # The once-only choice guard must also preserve a route
                    # changed after refusal, rather than reapplying fallback.
                    if route == 3:
                        state[PREFIX + "route"] = 3
                        after = copy.deepcopy(world.countries)
                        world.run(REFUSAL, "NQG")
                        self.assertEqual(world.countries, after)
                        self.assertEqual(world.treasury, protected[0])

    def test_missing_or_unknown_unpaid_route_is_not_enrolled_or_charged(self):
        for surface in ("catalog", "generated"):
            for route in (None, 99):
                with self.subTest(surface=surface, route=route):
                    world = _world()
                    state = world.countries["NQG"]
                    if route is not None:
                        state[PREFIX + "route"] = route
                    expected = copy.deepcopy(world.countries)
                    expected["NQG"].update({PREFIX + "st1005_refuse_loan_terms": 1,
                                            PREFIX + "pending": 1006, PREFIX + "stage": 1006})
                    _refuse(world, surface)
                    self.assertEqual(world.countries, expected)
                    self.assertEqual(world.treasury, {"NQG": 0, "ALLY": 0})
                    self.assertNotIn(PREFIX + "fee_paid", state)
                    self.assertNotIn(PREFIX + "stance_cap_stipend", state)
                    self.assertFalse(_script_condition(world, "{ ywc_nqg_winter_full_ready = yes }", "NQG"))

    def test_catalog_and_generated_tooltips_explain_actual_domestic_continuation(self):
        self.assertEqual(_option("ywc_nqg.1005", "refuse_loan_terms")["consequence_note"], CONSEQUENCE)
        key = "ywc_nqg.1005.refuse_loan_terms.consequence_tooltip"
        for language, suffix in (("en", "english"), ("zh", "simp_chinese")):
            with self.subTest(language=language):
                path = ROOT / "yongchang_world/localization" / suffix / f"ywc_v03_country_nqg_l_{suffix}.yml"
                line = next(line for line in path.read_text(encoding="utf-8-sig").splitlines()
                            if line.lstrip().startswith(key + ":"))
                self.assertEqual(line.strip(), key + ':0 "' + CONSEQUENCE[language] + '"')


if __name__ == "__main__":
    unittest.main()

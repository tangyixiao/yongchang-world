"""Strict TIB lifecycle proofs using authored scripts and concrete world facts."""
from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import PulseWorld, parse

MOD = ROOT / "yongchang_world"
CATALOG = json.loads((ROOT / "data/content/v03/countries/tib.json").read_text(encoding="utf-8"))
PREFIX = {"v03_tib_service_register": "register", "v03_tib_grain_credit": "grain",
          "v03_tib_shared_schools": "schools"}


def definitions(text):
    return {key: body for key, _, body in parse(text)}


def field(nodes, key):
    return next(value for name, _, value in nodes if name == key)


class TibWorldFacts(PulseWorld):
    """Fail-closed interpreter for authored TIB world predicates."""

    def __init__(self, effects, triggers, countries):
        super().__init__(effects, countries)
        self.trigger_defs = definitions(triggers)
        self.state_scope = None
        self.pop_scope = None
        self.building_scope = None
        self.good_scope = None
        self.history = {tag: {} for tag in countries}
        self.active = {tag: [] for tag in countries}
        self.journal_defs = {}
        self.event_defs = {}
        self.elapsed_months = 0

    def compare(self, left, operator, right):
        operations = {"=": lambda: left == right, ">=": lambda: left >= right,
                      "<=": lambda: left <= right, ">": lambda: left > right,
                      "<": lambda: left < right, "!=": lambda: left != right}
        if operator not in operations:
            raise AssertionError(f"unsupported TIB comparison: {operator}")
        return operations[operator]()

    def condition(self, node, tag):
        key, comparison, value = node
        state = self.countries[tag]
        if key in self.trigger_defs and value == "yes":
            return self.conditions(self.trigger_defs[key], tag)
        if key == "has_law_or_variant":
            return value.removeprefix("law_type:") in state.get("laws", set())
        if key == "has_law":
            return value.removeprefix("law_type:") in state.get("laws", set())
        if key == "gold_reserves":
            if comparison not in ("=", ">=", "<=", ">", "<", "!="):
                raise AssertionError(f"unsupported TIB cash comparison: {comparison}")
            actual_cash = float(state.get("gold_reserves", 0)) + float(self.treasury.get(tag, 0))
            target = (float(state.get(value.removeprefix("var:"), 0)) if value.startswith("var:")
                      else float(value))
            return self.compare(actual_cash, comparison, target)
        if key == "institution_investment_level":
            if comparison != "=" or not isinstance(value, list):
                raise AssertionError(f"unsupported TIB institution shape: {node}")
            fields = {}
            for child in value:
                if not isinstance(child, tuple) or len(child) != 3:
                    raise AssertionError(f"unsupported TIB institution child: {child}")
                child_key, child_op, child_value = child
                if child_key in fields:
                    raise AssertionError(f"duplicate TIB institution child: {child_key}")
                if child_key == "institution":
                    if child_op != "=" or child_value != "institution_schools":
                        raise AssertionError(f"unsupported TIB institution: {child}")
                    fields[child_key] = child_value
                elif child_key == "value":
                    if child_op not in ("=", ">=", "<=", ">", "<", "!="):
                        raise AssertionError(f"unsupported TIB institution comparison: {child_op}")
                    try:
                        fields[child_key] = (child_op, float(child_value))
                    except (TypeError, ValueError):
                        raise AssertionError(f"unsupported TIB institution value: {child_value}")
                else:
                    raise AssertionError(f"unsupported TIB institution child: {child_key}")
            if set(fields) != {"institution", "value"}:
                raise AssertionError(f"incomplete TIB institution shape: {value}")
            amount = float(state.get("institutions", {}).get(fields["institution"], 0))
            op, target = fields["value"]
            return self.compare(amount, op, target)
        if key == "any_scope_state":
            previous = self.state_scope
            for candidate in state.get("states", []):
                self.state_scope = candidate
                if self.conditions(value, tag):
                    self.state_scope = previous
                    return True
            self.state_scope = previous
            return False
        if key == "is_owned_by":
            if value != "ROOT":
                raise AssertionError(f"unsupported ownership scope: {node}")
            return self.state_scope is not None and bool(self.state_scope.get("owned"))
        if key in ("market_access", "average_sol"):
            if self.state_scope is None:
                raise AssertionError(f"{key} read outside actual state scope")
            return self.compare(float(self.state_scope.get(key, 0)), comparison, float(value))
        if key == "any_scope_pop":
            previous = self.pop_scope
            if self.state_scope is None:
                raise AssertionError("pop scope entered without state scope")
            for candidate in self.state_scope.get("pops", []):
                self.pop_scope = candidate
                if self.conditions(value, tag):
                    self.pop_scope = previous
                    return True
            self.pop_scope = previous
            return False
        if key == "is_pop_type":
            if self.pop_scope is None:
                raise AssertionError("pop type read outside actual pop scope")
            return self.pop_scope.get("type") == value
        if key == "is_employed":
            return self.pop_scope is not None and bool(self.pop_scope.get("employed")) == (value == "yes")
        if key == "workplace":
            if comparison != "?=" or self.pop_scope is None:
                raise AssertionError(f"unsupported workplace scope: {node}")
            previous = self.building_scope
            self.building_scope = self.pop_scope.get("workplace")
            result = self.conditions(value, tag)
            self.building_scope = previous
            return result
        if key == "any_scope_building":
            if self.state_scope is None:
                raise AssertionError("building scope entered without state scope")
            previous = self.building_scope
            for candidate in self.state_scope.get("buildings", []):
                self.building_scope = candidate
                if self.conditions(value, tag):
                    self.building_scope = previous
                    return True
            self.building_scope = previous
            return False
        if key == "is_building_type":
            if self.building_scope is None:
                raise AssertionError("building type read outside actual building scope")
            building_type = self.building_scope if isinstance(self.building_scope, str) else self.building_scope.get("type")
            return building_type == value
        if key == "occupancy":
            if not isinstance(self.building_scope, dict):
                raise AssertionError("occupancy read outside actual building scope")
            return self.compare(float(self.building_scope.get("occupancy", 0)), comparison, float(value))
        if key == "radical_fraction":
            if comparison != "=" or self.state_scope is None or not isinstance(value, list):
                raise AssertionError(f"radical fraction requires a supported state scope and shape: {node}")
            fields = {}
            for child in value:
                if not isinstance(child, tuple) or len(child) != 3:
                    raise AssertionError(f"unsupported TIB radical child: {child}")
                child_key, child_op, child_value = child
                if child_key in fields:
                    raise AssertionError(f"duplicate TIB radical child: {child_key}")
                if child_key == "value":
                    if child_op not in ("=", ">=", "<=", ">", "<", "!="):
                        raise AssertionError(f"unsupported TIB radical comparison: {child_op}")
                    try:
                        fields[child_key] = (child_op, float(child_value))
                    except (TypeError, ValueError):
                        raise AssertionError(f"unsupported TIB radical value: {child_value}")
                elif child_key == "pop_type":
                    if child_op != "=" or not isinstance(child_value, str) or not child_value:
                        raise AssertionError(f"unsupported TIB radical pop type: {child}")
                    fields[child_key] = child_value
                else:
                    raise AssertionError(f"unsupported TIB radical child: {child_key}")
            if "value" not in fields:
                raise AssertionError(f"incomplete TIB radical shape: {value}")
            pop_type = fields.get("pop_type")
            operator, limit = fields["value"]
            fractions = [float(pop.get("radical_fraction", 0)) for pop in self.state_scope.get("pops", [])
                         if pop_type is None or pop.get("type") == pop_type]
            return any(self.compare(fraction, operator, limit) for fraction in fractions)
        if key == "market_capital.market":
            previous = self.good_scope
            for good, _, children in value:
                if not good.startswith("mg:"):
                    raise AssertionError(f"unsupported market good scope: {good}")
                self.good_scope = good.removeprefix("mg:")
                if self.conditions(children, tag):
                    self.good_scope = previous
                    return True
            self.good_scope = previous
            return False
        if key in ("market_goods_pricier", "market_goods_imports", "market_goods_exports"):
            if self.good_scope is None:
                raise AssertionError(f"{key} read outside actual market good scope")
            measure = key.removeprefix("market_goods_")
            actual = float(state.get("market", {}).get(self.good_scope, {}).get(measure, 0))
            return self.compare(actual, comparison, float(value))
        if key == "literacy_rate":
            return self.compare(float(state.get("literacy_rate", 0)), comparison, float(value))
        if key == "net_fixed_income":
            return self.compare(float(state.get("net_fixed_income", 0)), comparison, float(value))
        if key == "in_default":
            return bool(state.get("in_default", False)) == (value == "yes")
        return super().condition(node, tag)

    def execute(self, nodes, tag):
        if not any(key == "every_scope_state" for key, _, _ in nodes):
            return super().execute(nodes, tag)
        for key, _, body in nodes:
            if key == "every_scope_state":
                previous = self.state_scope
                for candidate in self.countries[tag].get("states", []):
                    self.state_scope = candidate
                    limit = next((value for name, _, value in body if name == "limit"), [])
                    if self.conditions(limit, tag):
                        self.execute([node for node in body if node[0] != "limit"], tag)
                self.state_scope = previous
            elif key == "add_modifier" and self.state_scope is not None:
                fields = {name: value for name, _, value in body}
                self.state_scope.setdefault("modifiers", set()).add(fields["name"])
            else:
                super().execute([(key, "=", body)], tag)

    def activate(self, journal_id, tag="TIB"):
        if journal_id in self.active[tag]:
            return
        body = self.journal_defs[journal_id]
        if not self.conditions(field(body, "possible"), tag):
            return
        self.active[tag].append(journal_id)
        self.history[tag][journal_id] = "active"
        self.execute(field(body, "immediate"), tag)

    def refresh(self, arc, tag="TIB"):
        for journal_id in list(self.active[tag]):
            body = self.journal_defs[journal_id]
            goal = self.conditions(field(body, "complete"), tag)
            failed = self.conditions(field(body, "fail"), tag)
            if goal and failed:
                raise AssertionError(f"JE goal/fail overlap: {journal_id}")
            if goal or failed:
                self.history[tag][journal_id] = "complete" if goal else "failed"
                self.active[tag].remove(journal_id)
                if failed:
                    self.execute(field(body, "on_fail"), tag)
        for journal in arc["journals"]:
            self.activate(journal["id"], tag)

    def pulse(self, arc, tag="TIB"):
        self.refresh(arc, tag)
        active = list(self.active[tag])
        if not active:
            return None
        self.advance_months(1)
        self.elapsed_months += 1
        before = len(self.events)
        for journal_id in active:
            body = self.journal_defs[journal_id]
            self.assert_live(journal_id, body, tag)
            pulse = field(body, "on_monthly_pulse")
            self.execute(field(pulse, "effect"), tag)
        emitted = self.events[before:]
        del self.events[before:]
        self.refresh(arc, tag)
        if not emitted:
            return None
        if len(emitted) != 1:
            raise AssertionError(f"multiple events from one TIB pulse: {emitted}")
        event_tag, event_id = emitted[0]
        if event_tag != tag:
            raise AssertionError(f"wrong event recipient: {event_tag}")
        event = self.event_defs[event_id]
        self.assert_true(field(event, "trigger"), tag, (event_id, "generated event trigger"))
        self.execute(field(event, "immediate"), tag)
        if "ywc_v03_major_event_cooldown" not in self.countries[tag]:
            raise AssertionError("production major-event cooldown was not applied")
        return event_id

    def assert_live(self, journal_id, body, tag):
        if self.conditions(field(body, "complete"), tag) or self.conditions(field(body, "fail"), tag):
            raise AssertionError(f"terminal JE pulsed: {journal_id}")

    def assert_true(self, nodes, tag, context):
        if not self.conditions(nodes, tag):
            raise AssertionError(f"false authored condition: {context}")


class TibStrictLifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = ((MOD / "common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
                       + "\n" + (MOD / "common/scripted_effects/ywc_v03_tib_effects.txt").read_text(encoding="utf-8-sig"))
        cls.triggers = ((MOD / "common/scripted_triggers/ywc_v03_triggers.txt").read_text(encoding="utf-8-sig")
                        + "\n" + (MOD / "common/scripted_triggers/ywc_v03_tib_triggers.txt").read_text(encoding="utf-8-sig"))
        # Native-source unit fixture; generated adapter coverage lives in the inline tests.
        from tools import build_v03_content
        cls.journals = definitions(build_v03_content._render_journal_file(CATALOG, None))
        cls.events = definitions(build_v03_content._render_event_file(CATALOG, ROOT, None))
        cls.arcs = {arc["slug"]: arc for arc in CATALOG["arcs"]}

    def world(self, pre, route, cash, legacy=None):
        common = {"gold_reserves": cash, "yearly_gross_income": 5200, "net_fixed_income": 20,
                  "in_default": False, "laws": {"law_serfdom", "law_religious_schools"},
                  "states": [{"owned": True, "market_access": 0.5, "average_sol": 8,
                              "buildings": [{"type": "building_rice_farm", "occupancy": 0.8}],
                              "pops": [{"type": "bureaucrats", "employed": True,
                                        "workplace": "building_government_administration", "radical_fraction": 0.30},
                                       {"type": "laborers", "employed": True, "workplace": "building_rice_farm",
                                        "radical_fraction": 0.30},
                                       {"type": "academics", "employed": True, "workplace": "building_university",
                                        "radical_fraction": 0.02}]}],
                  "market": {"grain": {"pricier": 0.30, "imports": 5}},
                  "institutions": {"institution_schools": 1}, "literacy_rate": 0.30,
                  "modifiers": set()}
        if pre == "register":
            if route == 1:
                common["laws"].add("law_serfdom")
                common["net_fixed_income"] = 20
            elif route == 2:
                common["states"][0]["average_sol"] = 8
            else:
                common["laws"].add("law_tenant_farmers")
        elif pre == "grain":
            if route == 1:
                common["states"][0]["average_sol"] = 8
                common["market"]["grain"]["pricier"] = 0.30
            elif route == 2:
                common["market"]["grain"]["pricier"] = 0.20
            else:
                common["market"]["grain"]["pricier"] = 0.12
        else:
            if route == 1:
                common["literacy_rate"] = 0.30
            elif route == 2:
                common["literacy_rate"] = 0.30
                common["institutions"]["institution_schools"] = 1
            else:
                common["literacy_rate"] = 0.30
                common["states"][0]["pops"][1]["radical_fraction"] = 0.40
        countries = {"TIB": common}
        world = TibWorldFacts(self.effects, self.triggers, countries)
        world.journal_defs = self.journals
        world.event_defs = self.events
        world.run("ywc_v03_initialize_country", "TIB")
        self.assertFalse(any(k.startswith("ywc_tib_") or k.endswith(("_started", "_paid", "_pending_event", "_mature", "_outcome")) for k in common))
        if legacy is not None:
            common["ywc_campaign_tib_c1_outcome"] = legacy
        return world

    def entry(self, arc, world):
        first = self.journals[arc["journals"][0]["id"]]
        world.assert_true(field(first, "is_shown_when_inactive"), "TIB", (arc["slug"], "shown"))
        world.assert_true(field(first, "possible"), "TIB", (arc["slug"], "possible"))
        world.activate(arc["journals"][0]["id"])
        return arc["events"][0]["id"]

    def deliver(self, world, arc, expected, max_months=45):
        for _ in range(max_months):
            event_id = world.pulse(arc)
            if event_id is not None:
                self.assertEqual(event_id, expected)
                return self.events[event_id]
        self.fail((arc["slug"], expected, "not delivered by live JE pulse"))

    def choose(self, world, arc, event, key):
        option = next(body for name, _, body in event if name == "option" and field(body, "name").endswith("." + key))
        if any(name == "trigger" for name, _, _ in option):
            world.assert_true(field(option, "trigger"), "TIB", (field(event, "title"), key))
        world.execute([node for node in option if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")], "TIB")
        world.refresh(arc)

    def route(self, arc, route, cash):
        pre = PREFIX[arc["slug"]]
        world = self.world(pre, route, cash)
        self.entry(arc, world)
        first = self.deliver(world, arc, arc["events"][0]["id"])
        state = world.countries["TIB"]
        old_treasury = world.treasury["TIB"]
        self.choose(world, arc, first, f"route_{route}")
        self.assertEqual(state[f"ywc_tib_{pre}_route"], route)
        self.assertEqual(state[f"ywc_tib_{pre}_paid"], 1)
        self.assertEqual(world.treasury["TIB"] - old_treasury, -cash)
        self.assertEqual(state["gold_reserves"] + world.treasury["TIB"], 0)
        return world, state, pre

    def implement(self, world, arc, route):
        pre = PREFIX[arc["slug"]]
        paths = {"register": (1001, 1002, 1003, 1004, 1007, 1008, 1009),
                 "grain": (1011, 1012, 1013, 1016, 1017),
                 "schools": (1021, 1022, 1025)}
        for number in paths[pre]:
            event = self.deliver(world, arc, f"ywc_tib.{number}")
            self.choose(world, arc, event, "review_next")
        state = world.countries["TIB"]
        self.assertEqual(state[f"ywc_tib_{pre}_implementation_complete"], 1, (pre, route))
        self.assertEqual(state[f"ywc_tib_{pre}_route"], route)
        self.assertEqual(world.history["TIB"].get(arc["journals"][0]["id"]), "complete"
                         if len(arc["journals"]) > 1 else "active")
        return world, state

    def settle(self, world, arc, expected, months=10):
        pre = PREFIX[arc["slug"]]
        state = world.countries["TIB"]
        # The first real monthly pulse starts the authored native month timer.
        event = world.pulse(arc)
        self.assertIsNone(event)
        world.advance_months(5)
        self.assertNotIn(f"ywc_v03_tib_{arc['slug']}_settled", state,
                         "a six-month timer must not settle before its expiry")
        for _ in range(months):
            if f"ywc_v03_tib_{arc['slug']}_settled" in state:
                break
            world.pulse(arc)
        self.assertEqual(state.get(f"ywc_v03_tib_{arc['slug']}_outcome"), expected, arc["slug"])
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)
        for journal in arc["journals"]:
            self.assertEqual(world.history["TIB"].get(journal["id"]), "complete")
        return state

    def test_real_world_facts_complete_two_distinct_paid_strategies_per_arc(self):
        scenarios = (("v03_tib_service_register", 1, 200, 1),
                     ("v03_tib_service_register", 2, 150, 2),
                     ("v03_tib_grain_credit", 1, 200, 1),
                     ("v03_tib_grain_credit", 2, 150, 2),
                     ("v03_tib_shared_schools", 1, 200, 1),
                     ("v03_tib_shared_schools", 2, 150, 2))
        for slug, route, cash, outcome in scenarios:
            with self.subTest(arc=slug, route=route):
                arc = self.arcs[slug]
                world, state, _ = self.route(arc, route, cash)
                self.implement(world, arc, route)
                self.settle(world, arc, outcome)

    def test_paid_register_route_stays_actionable_after_actual_unrest_improves(self):
        register = self.arcs["v03_tib_service_register"]
        world, state, _ = self.route(register, 1, 200)
        state["states"][0]["pops"][1]["radical_fraction"] = 0.05
        self.implement(world, register, 1)

    def test_paid_grain_route_stays_actionable_after_actual_price_improves(self):
        grain = self.arcs["v03_tib_grain_credit"]
        world, state, _ = self.route(grain, 1, 200)
        state["market"]["grain"]["pricier"] = 0.20
        self.implement(world, grain, 1)

    def test_paid_school_route_stays_actionable_after_actual_literacy_improves(self):
        schools = self.arcs["v03_tib_shared_schools"]
        world, state, _ = self.route(schools, 1, 200)
        state["literacy_rate"] = 0.70
        self.implement(world, schools, 1)

    def test_real_grain_route_three_keeps_its_documented_three_month_limited_window(self):
        arc = self.arcs["v03_tib_grain_credit"]
        world, state, _ = self.route(arc, 3, 300)
        self.implement(world, arc, 3)
        self.assertIsNone(world.pulse(arc))
        world.advance_months(2)
        self.assertNotIn("ywc_v03_tib_v03_tib_grain_credit_settled", state)
        world.advance_months(1)
        world.pulse(arc)
        self.assertEqual(state["ywc_v03_tib_v03_tib_grain_credit_outcome"], 3)
        self.assertEqual(world.history["TIB"][arc["journals"][-1]["id"]], "complete")

    def test_three_real_shown_possible_arcs_create_independent_active_queues(self):
        world = self.world("register", 1, 10000)
        arc_list = list(CATALOG["arcs"])
        for arc in arc_list:
            first = self.journals[arc["journals"][0]["id"]]
            world.assert_true(field(first, "is_shown_when_inactive"), "TIB", (arc["slug"], "shown"))
            world.assert_true(field(first, "possible"), "TIB", (arc["slug"], "possible"))
            world.activate(arc["journals"][0]["id"])
        state = world.countries["TIB"]
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
        self.assertEqual(set(world.active["TIB"]), {arc["journals"][0]["id"] for arc in arc_list})
        self.assertEqual({state[f"ywc_tib_{pre}_pending_event"] for pre in ("register", "grain", "schools")},
                         {1000, 1010, 1020})
        self.assertNotIn("ywc_v03_major_event_cooldown", state)

    def test_real_entry_withdrawal_preserves_legacy_values_and_releases_slots(self):
        for arc in CATALOG["arcs"]:
            pre = PREFIX[arc["slug"]]
            for legacy in (None, 1, 2, 3, 4):
                with self.subTest(arc=arc["slug"], legacy=legacy):
                    world = self.world(pre, 1, 10000, legacy=legacy)
                    state = world.countries["TIB"]
                    if legacy is None:
                        state["ywc_je_flavor_tib_estate_1_resolved"] = 1
                    self.entry(arc, world)
                    event = self.deliver(world, arc, arc["events"][0]["id"])
                    self.choose(world, arc, event, "withdraw")
                    self.assertEqual(state["ywc_v03_active_arc_count"], 0)
                    self.assertEqual(state["ywc_v03_visible_task_count"], 0)
                    self.assertEqual(state[f"ywc_v03_tib_{arc['slug']}_outcome"], 4)
                    world.run(f"ywc_tib_{pre}_withdraw", "TIB")
                    self.assertEqual(state["ywc_v03_active_arc_count"], 0)
                    self.assertEqual(state["ywc_v03_visible_task_count"], 0)
                    if legacy is not None:
                        self.assertEqual(state["ywc_campaign_tib_c1_outcome"], legacy)
                    else:
                        self.assertEqual(state["ywc_campaign_tib_c1_outcome"], 4)
                    self.assertEqual(world.history["TIB"][arc["journals"][0]["id"]], "failed")

    def test_fee_failure_at_stale_popup_retries_without_charge_and_paid_replay_is_idempotent(self):
        for arc in CATALOG["arcs"]:
            pre = PREFIX[arc["slug"]]
            with self.subTest(arc=arc["slug"]):
                world = self.world(pre, 1, 5000)
                self.entry(arc, world)
                event = self.deliver(world, arc, arc["events"][0]["id"])
                state = world.countries["TIB"]
                option = next(body for name, _, body in event
                              if name == "option" and field(body, "name").endswith(".route_1"))
                state["gold_reserves"] = 0
                self.assertFalse(world.conditions(field(option, "trigger"), "TIB"))
                effects = [node for node in option if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                world.execute(effects, "TIB")
                self.assertNotIn(f"ywc_tib_{pre}_paid", state)
                self.assertEqual(world.treasury["TIB"], 0)
                self.assertEqual(state[f"ywc_tib_{pre}_pending_event"], 1000 + (10 if pre == "grain" else 20 if pre == "schools" else 0))
                state["gold_reserves"] = 200
                retry = self.deliver(world, arc, arc["events"][0]["id"])
                self.choose(world, arc, retry, "route_1")
                paid_treasury = world.treasury["TIB"]
                self.assertEqual(state["gold_reserves"] + paid_treasury, 0)
                world.execute(effects, "TIB")
                self.assertEqual(world.treasury["TIB"], paid_treasury)
                self.assertEqual(state[f"ywc_tib_{pre}_paid"], 1)

    def test_real_loss_defer_notices_recovery_new_epoch_narrow_and_limited_close(self):
        notice_ids = {"register": (1005, 1006, 1009),
                      "grain": (1014, 1015, 1017),
                      "schools": (1023, 1024, 1025)}
        for arc in CATALOG["arcs"]:
            pre = PREFIX[arc["slug"]]
            notice12_number, notice36_number, final_number = notice_ids[pre]
            with self.subTest(arc=arc["slug"]):
                world, state, _ = self.route(arc, 1, 200)
                self.implement(world, arc, 1)
                sunk_treasury = world.treasury["TIB"]
                if pre == "register":
                    state["states"][0]["pops"][0]["employed"] = False
                elif pre == "grain":
                    state["states"][0]["market_access"] = 0
                else:
                    state["institutions"]["institution_schools"] = 0
                    state["states"][0]["pops"][2]["employed"] = False
                self.assertIsNone(world.pulse(arc))
                self.assertIn(f"ywc_tib_{pre}_blocked_started", state)
                self.assertIn(f"ywc_tib_{pre}_blocked_12_due", state)
                self.assertIn(f"ywc_tib_{pre}_blocked_36_due", state)
                world.advance_days(365)
                event = world.pulse(arc)
                self.assertEqual(event, f"ywc_tib.{notice12_number}")
                self.choose(world, arc, self.events[event], "defer")
                self.assertEqual(state[f"ywc_tib_{pre}_notice_last_delivered"], 1)
                world.advance_days(730)
                event = world.pulse(arc)
                self.assertEqual(event, f"ywc_tib.{notice36_number}")
                self.choose(world, arc, self.events[event], "renegotiate")
                self.assertEqual(state[f"ywc_tib_{pre}_paid"], 1)
                self.assertEqual(world.treasury["TIB"], sunk_treasury)
                self.assertEqual(state[f"ywc_tib_{pre}_pending_event"], final_number)

                if pre == "register":
                    state["states"][0]["pops"][0]["employed"] = True
                elif pre == "grain":
                    state["states"][0]["market_access"] = 0.5
                else:
                    state["institutions"]["institution_schools"] = 1
                    state["states"][0]["pops"][2]["employed"] = True
                event = self.deliver(world, arc, f"ywc_tib.{final_number}")
                self.choose(world, arc, event, "review_next")
                self.assertNotIn(f"ywc_tib_{pre}_blocked_started", state)
                self.assertNotIn(f"ywc_tib_{pre}_notice_12_sent", state)

                if pre == "register":
                    state["states"][0]["pops"][0]["employed"] = False
                elif pre == "grain":
                    state["states"][0]["market_access"] = 0
                else:
                    state["institutions"]["institution_schools"] = 0
                    state["states"][0]["pops"][2]["employed"] = False
                self.assertIsNone(world.pulse(arc))
                world.advance_days(365)
                event = world.pulse(arc)
                self.assertEqual(event, f"ywc_tib.{notice12_number}")
                self.choose(world, arc, self.events[event], "narrow_scope")
                self.assertEqual(state[f"ywc_tib_{pre}_route"], 1)
                self.assertEqual(state[f"ywc_tib_{pre}_paid"], 1)
                self.assertEqual(world.treasury["TIB"], sunk_treasury)
                event = self.deliver(world, arc, f"ywc_tib.{final_number}")
                self.choose(world, arc, event, "review_next")
                self.assertEqual(state[f"ywc_tib_{pre}_implementation_complete"], 1)
                self.assertNotIn(f"ywc_tib_{pre}_blocked_started", state)
                self.settle(world, arc, 3)


    def test_nested_world_facts_fail_closed_and_do_not_cross_join_scopes(self):
        world = self.world("schools", 1, 10000)
        state = world.countries["TIB"]
        trigger = self.triggers
        self.assertIn("any_scope_pop", trigger)
        state["states"][0]["pops"][0]["employed"] = False
        state["states"].append({"owned": False, "market_access": 0.9, "average_sol": 7,
                                 "buildings": [{"type": "building_rice_farm", "occupancy": 1}],
                                 "pops": [{"type": "bureaucrats", "employed": True,
                                           "workplace": "building_government_administration",
                                           "radical_fraction": 0.01}]})
        self.assertFalse(world.conditions(world.trigger_defs["ywc_tib_has_staffed_admin"], "TIB"))
        state["states"][0]["pops"][0]["employed"] = True
        self.assertTrue(world.conditions(world.trigger_defs["ywc_tib_has_staffed_admin"], "TIB"))
        state["laws"].discard("law_serfdom")
        state["laws"].discard("law_tenant_farmers")
        self.assertFalse(world.conditions(world.trigger_defs["ywc_tib_land_law_known"], "TIB"))
        state["laws"].add("law_serfdom")
        state["states"][0]["market_access"] = 0
        self.assertFalse(world.conditions(world.trigger_defs["ywc_tib_has_market_access"], "TIB"))
        state["states"][0]["market_access"] = 0.5
        state["states"][0]["buildings"][0]["occupancy"] = 0
        self.assertFalse(world.conditions(world.trigger_defs["ywc_tib_has_agriculture"], "TIB"))
        with self.assertRaisesRegex(AssertionError, "unsupported test trigger"):
            world.condition(("any_scope_state", "=", [("is_owned_by", "=", "ROOT"),
                                                        ("tib_unknown_predicate", "=", "yes")]), "TIB")

    def test_paid_cash_primitive_matches_actual_debit_and_unpaid_route_gate(self):
        arc = self.arcs["v03_tib_service_register"]
        world, state, pre = self.route(arc, 1, 200)
        self.assertEqual(state["gold_reserves"], 200)
        self.assertEqual(world.treasury["TIB"], -200)
        self.assertFalse(world.condition(("gold_reserves", ">=", "200"), "TIB"))
        self.assertFalse(world.condition(("gold_reserves", ">=", f"var:ywc_tib_{pre}_route_cost_1"), "TIB"))
        self.assertTrue(world.condition(("gold_reserves", ">=", "0"), "TIB"))

        unpaid = self.world("register", 1, 0)
        self.entry(arc, unpaid)
        event = self.deliver(unpaid, arc, arc["events"][0]["id"])
        option = next(body for name, _, body in event
                      if name == "option" and field(body, "name").endswith(".route_1"))
        self.assertFalse(unpaid.conditions(field(option, "trigger"), "TIB"))
        unpaid.execute([node for node in option if node[0] not in
                        ("name", "trigger", "ai_chance", "custom_tooltip")], "TIB")
        self.assertNotIn("ywc_tib_register_paid", unpaid.countries["TIB"])
        self.assertEqual(unpaid.treasury["TIB"], 0)

    def test_nested_school_and_radical_filters_validate_every_child(self):
        world = self.world("schools", 1, 10000)
        state = world.countries["TIB"]
        state["states"][0]["pops"][1]["radical_fraction"] = 0.30
        world.state_scope = state["states"][0]
        institution_true = ("institution_investment_level", "=",
                            [("institution", "=", "institution_schools"), ("value", ">=", "1")])
        institution_false = ("institution_investment_level", "=",
                             [("institution", "=", "institution_schools"), ("value", ">", "1")])
        radical_true = ("radical_fraction", "=", [("value", ">", "0.25"), ("pop_type", "=", "laborers")])
        radical_false = ("radical_fraction", "=", [("value", ">", "0.50"), ("pop_type", "=", "laborers")])
        self.assertTrue(world.condition(institution_true, "TIB"))
        self.assertFalse(world.condition(institution_false, "TIB"))
        self.assertTrue(world.condition(radical_true, "TIB"))
        self.assertFalse(world.condition(radical_false, "TIB"))

        for base in (institution_true, institution_false, radical_true, radical_false):
            unknown = base[0], base[1], [*base[2], ("tib_unknown_world_predicate", "=", "yes")]
            with self.subTest(predicate=base[0], false_known=base in (institution_false, radical_false)):
                with self.assertRaisesRegex(AssertionError, "unsupported TIB (institution|radical) child"):
                    world.condition(unknown, "TIB")
        bad_institution_op = ("institution_investment_level", "=",
                              [("institution", "=", "institution_schools"), ("value", "?=", "1")])
        malformed_institution = ("institution_investment_level", "=",
                                 [("institution", "=", "institution_schools"), ("value", ">=", "1"),
                                  ("value", ">=", "0")])
        bad_radical_op = ("radical_fraction", "=", [("value", "?=", "0.25")])
        malformed_radical = ("radical_fraction", "=", [("value", ">", "0.25"), ("mystery", "=", "x")])
        for node in (bad_institution_op, malformed_institution, bad_radical_op, malformed_radical):
            with self.subTest(node=node):
                with self.assertRaises(AssertionError):
                    world.condition(node, "TIB")

    def test_original_route_entry_filters_remain_live_world_requirements(self):
        cases = (("register", 1, "radical", "ywc_tib_register_route_1_ready"),
                 ("grain", 1, "price", "ywc_tib_grain_route_1_ready"),
                 ("schools", 1, "literacy", "ywc_tib_schools_route_1_ready"))
        for pre, route, fact, trigger in cases:
            with self.subTest(arc=pre):
                world = self.world(pre, route, 5000)
                state = world.countries["TIB"]
                if fact == "radical":
                    state["states"][0]["pops"][1]["radical_fraction"] = 0.05
                elif fact == "price":
                    state["market"]["grain"]["pricier"] = 0.20
                else:
                    state["literacy_rate"] = 0.70
                self.assertFalse(world.conditions(world.trigger_defs[trigger], "TIB"))


if __name__ == "__main__":
    unittest.main()

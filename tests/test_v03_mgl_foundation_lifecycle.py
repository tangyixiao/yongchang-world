"""Independent strict MGL lifecycle tests driven by authored scripts and world facts."""
from pathlib import Path
import json
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from clausewitz_harness import PulseWorld, parse

MOD = ROOT / "yongchang_world"
COUNTRY = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))
CATALOG_ARCS = COUNTRY["arcs"]
PRE = {"v03_mgl_two_trade_roads": "roads", "v03_mgl_pastoral_debt": "debt",
       "v03_mgl_princes_monasteries": "grain"}


def _definitions(text):
    return {key: body for key, _, body in parse(text)}


def _native_business_projection(catalog):
    """Render current authored business source without inline transport.

    Integrated delivery is exercised by the separate inline fixture, which
    installs real renderer registries and wrappers before root activation.
    """
    from tools import build_v03_content
    def definitions(text, expected, label):
        result = {}
        for key, _, body in parse(text):
            if key == "namespace":
                continue
            if key in result:
                raise AssertionError(("native_projection_collision", label, key))
            result[key] = body
        if len(result) != expected:
            raise AssertionError(("native_projection_count", label, len(result), expected))
        return result
    journals = definitions(build_v03_content._render_journal_file(catalog, None), 6, "journals")
    events = definitions(build_v03_content._render_event_file(catalog, ROOT, None), 24, "events")
    return journals, events


def _block(fields, name):
    return next(value for key, _, value in fields if key == name)


def _num(event_id):
    return int(event_id.rsplit(".", 1)[1])


class MglWorldFacts(PulseWorld):
    """Strictly evaluate MGL predicates from explicit legal world facts."""

    def __init__(self, effects, triggers, countries):
        super().__init__(effects, countries)
        self.trigger_defs = _definitions(triggers)
        self.scope_state = None
        self.scope_pop = None
        self.scope_good = None
        self.calendar_months = 0
        self.evidence_marks = {}
        self.history = {tag: {} for tag in countries}
        self.active_journals = {tag: [] for tag in countries}
        self.generated_journals = {}

    def activate_journal(self, journal_id, tag="MGL"):
        body = self.generated_journals[journal_id]
        if journal_id in self.active_journals[tag]:
            raise AssertionError(f"journal already active: {journal_id}")
        if not self.conditions(_block(body, "possible"), tag):
            raise AssertionError(f"journal not possible from authored conditions: {journal_id}")
        self.active_journals[tag].append(journal_id)
        self.history[tag][journal_id] = "active"
        self.execute(_block(body, "immediate"), tag)

    def advance_months(self, months=1):
        super().advance_months(months)
        self.calendar_months += months

    def _compare(self, left, comparison, right):
        return {"=": lambda: left == right, ">=": lambda: left >= right,
                "<=": lambda: left <= right, ">": lambda: left > right,
                "<": lambda: left < right, "!=": lambda: left != right}[comparison]()

    def condition(self, node, tag):
        key, comparison, value = node
        state = self.countries[tag]
        if key in self.trigger_defs and value == "yes":
            return self.conditions(self.trigger_defs[key], tag)
        if key == "has_law":
            law = value.removeprefix("law_type:")
            return law in state.get("laws", set())
        if key in ("market_access", "average_sol"):
            if self.scope_state is None:
                raise AssertionError(f"{key} read outside an actual state scope")
            return self._compare(float(self.scope_state.get(key, 0)), comparison, float(value))
        if key == "any_scope_state":
            previous = self.scope_state
            for state_fact in state.get("states", []):
                self.scope_state = state_fact
                if self.conditions(value, tag):
                    self.scope_state = previous
                    return True
            self.scope_state = previous
            return False
        if key == "any_scope_pop":
            previous = self.scope_pop
            populations = ([self.scope_state] if self.scope_state is not None else state.get("states", []))
            for state_fact in populations:
                for pop_fact in state_fact.get("pops", []):
                    self.scope_pop = pop_fact
                    if self.conditions(value, tag):
                        self.scope_pop = previous
                        return True
            self.scope_pop = previous
            return False
        if key == "is_employed":
            return self.scope_pop is not None and bool(self.scope_pop.get("employed")) == (value == "yes")
        if key == "workplace":
            return self.scope_pop is not None and self.conditions(value, tag)
        if key == "is_building_type":
            return self.scope_pop is not None and self.scope_pop.get("workplace") == value
        if key == "country_has_building_group_levels":
            fields = {k: v for k, _, v in value}
            group, threshold = fields["type"], float(fields["value"])
            levels = sum(float(b.get("level", 0)) for b in state.get("buildings", []) if group in b.get("groups", set()))
            return self._compare(levels, next(c for k, c, _ in value if k == "value"), threshold)
        if key == "market_capital.market":
            previous = self.scope_good
            for good, _, body in value:
                self.scope_good = good.removeprefix("mg:")
                if self.conditions(body, tag):
                    self.scope_good = previous
                    return True
            self.scope_good = previous
            return False
        if key in ("market_goods_exports", "market_goods_imports", "market_goods_pricier"):
            if self.scope_good is None:
                raise AssertionError(f"{key} read outside an actual market-good scope")
            amount = float(state.get("market", {}).get(self.scope_good, {}).get(key.removeprefix("market_goods_"), 0))
            return self._compare(amount, comparison, float(value))
        if key == "ywc_mgl_roads_trade_signal":
            return float(state.get("market", {}).get("tea", {}).get("exports", 0)) > 0
        if key == "ywc_mgl_grain_entry_price":
            return float(state.get("market", {}).get("grain", {}).get("pricier", 0)) > 0.10
        if key.startswith("c:") and ".relations:this" in key:
            partner = key.split(":", 1)[1].split(".", 1)[0]
            if partner not in self.countries:
                return False
            left = float(state.get("relations", {}).get(partner, 0))
            right = float(value)
            return self._compare(left, comparison, right)
        if key == "ig:ig_devout":
            if comparison != "?=" or not isinstance(value, list) or not value:
                raise AssertionError(f"unsupported IG scope shape: {node}")
            approval = float(state.get("interest_groups", {}).get("ig_devout", -100))
            result = []
            for child in value:
                if not isinstance(child, tuple) or len(child) != 3:
                    raise AssertionError(f"unsupported IG child shape: {child}")
                child_key, child_comparison, child_value = child
                if child_key != "ig_approval":
                    raise AssertionError(f"unsupported test trigger: {child}")
                if child_comparison not in ("=", ">=", "<=", ">", "<", "!="):
                    raise AssertionError(f"unsupported IG comparison: {child_comparison}")
                try:
                    target_approval = float(child_value)
                except (TypeError, ValueError) as exc:
                    raise AssertionError(f"unsupported IG approval value: {child_value}") from exc
                result.append(self._compare(approval, child_comparison, target_approval))
            return all(result)
        if key == "military_expenses_share":
            return self._compare(float(state.get(key, 0)), comparison, float(value))
        if key == "has_modifier" and value == "declared_bankruptcy":
            return value in state.get("modifiers", set())
        if key == "gold_reserves":
            cash = float(state.get("gold_reserves", 0)) + self.treasury.get(tag, 0)
            return self._compare(cash, comparison, float(value.removeprefix("var:"))) if not value.startswith("var:") else self._compare(cash, comparison, float(state.get(value[4:], 0)))
        if key in ("average_sol", "market_access"):
            raise AssertionError(f"{key} requires actual state-scope facts")
        return super().condition(node, tag)


class MglStrictLifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.effects = ((MOD / "common/scripted_effects/ywc_v03_effects.txt").read_text(encoding="utf-8-sig")
                       + "\n" + (MOD / "common/scripted_effects/ywc_v03_mgl_effects.txt").read_text(encoding="utf-8-sig"))
        cls.triggers = ((MOD / "common/scripted_triggers/ywc_v03_triggers.txt").read_text(encoding="utf-8-sig")
                        + "\n" + (MOD / "common/scripted_triggers/ywc_v03_mgl_triggers.txt").read_text(encoding="utf-8-sig"))
        cls.generated_journals, cls.generated_events = _native_business_projection(COUNTRY)
        cls.arc_by_slug = {arc["slug"]: arc for arc in CATALOG_ARCS}

    def _facts(self, pre, route, cash, legacy=1):
        base = {"gold_reserves": cash, "yearly_gross_income": 5200, "in_default": False,
                "laws": set(), "states": [], "market": {}, "relations": {"SHU": -100, "RUS": -100},
                "buildings": [], "interest_groups": {"ig_devout": 0}, "military_expenses_share": 0.05,
                "modifiers": set()}
        if pre == "roads":
            base["market"] = {"tea": {"exports": 100 if route == 1 else 1, "imports": 0, "pricier": 0},
                              "grain": {"exports": 0, "imports": 1, "pricier": 0}}
            base["states"] = [{"market_access": 0.8 if route == 1 else 0.5, "average_sol": 11,
                               "pops": []}]
            if route == 1:
                base["laws"].add("law_mercantilism")
                base["relations"] = {"SHU": 0, "RUS": 0}
        elif pre == "debt":
            law = "law_tenant_farmers" if route == 1 else "law_serfdom"
            base["laws"].add(law)
            base["market"] = {"wool": {"exports": 2, "imports": 0, "pricier": 0}}
            base["buildings"] = [{"groups": {"bg_livestock_ranches"}, "level": 2}]
            base["states"] = [{"market_access": 0.6, "average_sol": 11 if route == 1 else 8,
                               "pops": [{"employed": True, "workplace": "building_livestock_ranch"}]}]
        else:
            base["market"] = {"grain": {"exports": 0, "imports": 1, "pricier": 0.30 if route == 1 else 0.18}}
            base["buildings"] = [{"groups": {"bg_government"}, "level": 1}]
            base["states"] = [{"market_access": 0.75, "average_sol": 10,
                               "pops": [{"employed": True, "workplace": "building_government_administration"}]}]
            if route == 1:
                base["military_expenses_share"] = 0.15
        state = {"MGL": base, "SHU": {"relations": {"MGL": 0}}, "RUS": {"relations": {"MGL": 0}}}
        world = MglWorldFacts(self.effects, self.triggers, state)
        world.generated_journals = self.generated_journals
        world.run("ywc_v03_initialize_country", "MGL")
        self.assertFalse(any(key.startswith("ywc_mgl_") or key.endswith(("_started", "_paid", "_pending_event", "_mature", "_outcome")) for key in base))
        base["ywc_campaign_mng_c1_outcome"] = legacy
        return world

    def _entry(self, arc, world):
        je = self.generated_journals[arc["journals"][0]["id"]]
        shown = world.conditions(_block(je, "is_shown_when_inactive"), "MGL")
        possible = world.conditions(_block(je, "possible"), "MGL")
        self.assertTrue(shown and possible, (arc["slug"], "production entry not officially shown+possible"))
        world.activate_journal(arc["journals"][0]["id"])
        return arc["events"][0]["id"]

    def _refresh_lifecycle(self, world, arc):
        for active in list(world.active_journals["MGL"]):
            fields = self.generated_journals[active]
            goal = world.conditions(_block(fields, "complete"), "MGL")
            failed = world.conditions(_block(fields, "fail"), "MGL")
            self.assertFalse(goal and failed, (arc["slug"], active, "goal/fail overlap"))
            if goal or failed:
                world.history["MGL"][active] = "complete" if goal else "failed"
                world.active_journals["MGL"].remove(active)
                if not goal:
                    world.execute(_block(fields, "on_fail"), "MGL")
                if goal and active == arc["journals"][0]["id"]:
                    self.assertIn(arc["journals"][1]["id"], [dict((k, v) for k, _, v in body).get("type") for tag, body in world.journals if tag == "MGL"])
                    world.activate_journal(arc["journals"][1]["id"])

    def _pulse(self, world, arc):
        self._refresh_lifecycle(world, arc)
        active = list(world.active_journals["MGL"])
        self.assertTrue(active, (arc["slug"], "no active authored JE to pulse"))
        world.advance_months(1)
        before = len(world.events)
        for journal_id in active:
            fields = self.generated_journals[journal_id]
            self.assertFalse(world.conditions(_block(fields, "complete"), "MGL"), (journal_id, "completed JE pulsed"))
            self.assertFalse(world.conditions(_block(fields, "fail"), "MGL"), (journal_id, "failed JE pulsed"))
            pulse = _block(fields, "on_monthly_pulse")
            world.execute(_block(pulse, "effect"), "MGL")
        emitted = world.events[before:]
        world.events = world.events[:before]
        self._refresh_lifecycle(world, arc)
        if not emitted:
            return None
        self.assertEqual(len(emitted), 1, (arc["slug"], emitted))
        tag, event_id = emitted[0]
        self.assertEqual(tag, "MGL")
        event = self.generated_events[event_id]
        self.assertTrue(world.conditions(_block(event, "trigger"), "MGL"), (event_id, "production trigger false"))
        world.execute(_block(event, "immediate"), "MGL")
        self.assertIn("ywc_v03_major_event_cooldown", world.countries["MGL"], "official 90-day cooldown was not applied")
        return event_id

    def _deliver(self, world, arc, expected_id, max_months=45):
        for _ in range(max_months):
            event_id = self._pulse(world, arc)
            if event_id is None:
                continue
            self.assertEqual(event_id, expected_id, (arc["slug"], "unexpected generated event"))
            return self.generated_events[event_id]
        self.fail((arc["slug"], expected_id, "not delivered by live JE pulse"))

    def _choose(self, world, arc, event, key):
        options = [body for name, _, body in event if name == "option"]
        option = next(body for body in options if _block(body, "name").endswith("." + key))
        if any(name == "trigger" for name, _, _ in option):
            self.assertTrue(world.conditions(_block(option, "trigger"), "MGL"), (_block(event, "title"), key, "option trigger false"))
        effect_nodes = [node for node in option if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
        world.execute(effect_nodes, "MGL")
        self._refresh_lifecycle(world, arc)

    def _choose_legal_terms(self, world, arc, event):
        for _, _, option in [row for row in event if row[0] == "option"]:
            if any(name == "trigger" for name, _, _ in option) and world.conditions(_block(option, "trigger"), "MGL"):
                key = _block(option, "name").split(".")[-1]
                if "terms" in key:
                    self._choose(world, arc, event, key)
                    return
        self.fail((arc["slug"], "no current route-specific terms option"))

    def _route(self, arc, route, cash):
        pre = PRE[arc["slug"]]
        world = self._facts(pre, route, cash)
        first_id = self._entry(arc, world)
        first = self._deliver(world, arc, first_id)
        route_key = {1: "dual", 2: "single", 3: "local"}[route]
        option = next(body for name, _, body in first if name == "option" and _block(body, "name").endswith("." + route_key))
        self.assertTrue(world.conditions(_block(option, "trigger"), "MGL"), (arc["slug"], route_key, "actual route contract false"))
        fee_before = world.treasury["MGL"]
        self._choose(world, arc, first, route_key)
        state = world.countries["MGL"]
        self.assertEqual(state[f"ywc_mgl_{pre}_route"], route)
        self.assertEqual(state[f"ywc_mgl_{pre}_route_paid"], 1)
        self.assertEqual(world.treasury["MGL"] - fee_before, -cash, (arc["slug"], "actual fee debit"))
        self.assertEqual(state["gold_reserves"] + world.treasury["MGL"], 0, (arc["slug"], "cash did not synchronize to zero"))
        self.assertEqual(world.active_journals["MGL"], [arc["journals"][1]["id"]])
        self.assertEqual(world.history["MGL"][arc["journals"][0]["id"]], "complete")
        for index, key in ((1, "review"), (2, None), (3, "clarify"), (4, None), (5, "review")):
            event_id = arc["events"][index]["id"]
            event = self._deliver(world, arc, event_id)
            if index in (2, 4):
                options = [body for name, _, body in event if name == "option"]
                legal = []
                for body in options:
                    if any(name == "trigger" for name, _, _ in body) and world.conditions(_block(body, "trigger"), "MGL"):
                        legal.append(body)
                route_terms = next(body for body in legal if f"node_{2 if index == 2 else 4}_route_read" in str(body) or f"terms_committed value = {route}" in str(body))
                key = _block(route_terms, "name").split(".")[-1]
            self._choose(world, arc, event, key)
            if index == 4:
                world.evidence_marks[arc["slug"]] = world.calendar_months
            if arc["slug"] == "v03_mgl_princes_monasteries" and route == 1 and index == 4:
                state["market"]["grain"]["pricier"] = 0.10
        return world, state, pre

    def _resume_local_after_narrow(self, world, arc, pre):
        state = world.countries["MGL"]
        if pre == "roads":
            state["states"][0]["market_access"] = 0.5
            state["market"]["grain"]["imports"] = 1
        elif pre == "debt":
            state["laws"].discard("law_tenant_farmers")
            state["laws"].add("law_serfdom")
        for index, key in ((1, "review"), (2, None), (3, "clarify"), (4, None), (5, "review")):
            event = self._deliver(world, arc, arc["events"][index]["id"])
            if index in (2, 4):
                self._choose_legal_terms(world, arc, event)
                if index == 4:
                    world.evidence_marks[arc["slug"]] = world.calendar_months
            else:
                self._choose(world, arc, event, key)

    def test_real_paid_loss_notices_narrow_and_only_limited_recovery(self):
        cases = (("v03_mgl_two_trade_roads", "roads", "relations"),
                 ("v03_mgl_pastoral_debt", "debt", "employment"),
                 ("v03_mgl_princes_monasteries", "grain", "military"))
        for slug, pre, loss in cases:
            with self.subTest(arc=slug):
                arc = self.arc_by_slug[slug]
                world, state, _ = self._route(arc, 1, 200)
                treasury_after_payment = world.treasury["MGL"]
                if loss == "relations":
                    state["relations"]["SHU"] = -100
                elif loss == "employment":
                    state["states"][0]["pops"][0]["employed"] = False
                else:
                    state["military_expenses_share"] = 0
                notice12, notice36 = arc["events"][6]["id"], arc["events"][7]["id"]
                acked = False
                narrowed = False
                for _ in range(48):
                    event_id = self._pulse(world, arc)
                    if event_id == notice12:
                        self.assertFalse(acked, (slug, "12-month notice duplicated"))
                        self._choose(world, arc, self.generated_events[event_id], "defer")
                        self.assertEqual(state.get(f"ywc_mgl_{pre}_blocked_12_sent"), 1)
                        acked = True
                    elif event_id == notice36:
                        self.assertTrue(acked, (slug, "36-month notice preceded acknowledgement"))
                        self._choose(world, arc, self.generated_events[event_id], "narrow")
                        narrowed = True
                        break
                    elif event_id is not None:
                        self.fail((slug, "unexpected queued event during blocked watch", event_id))
                self.assertTrue(narrowed, (slug, "36-month narrowing option not delivered"))
                self.assertEqual(state[f"ywc_mgl_{pre}_route_paid"], 1)
                self.assertEqual(state[f"ywc_mgl_{pre}_route"], 3)
                self.assertEqual(world.treasury["MGL"], treasury_after_payment, "notice narrowing charged again")
                self.assertNotIn(f"ywc_mgl_{pre}_blocked_12_due", state)
                self.assertNotIn(f"ywc_mgl_{pre}_blocked_36_due", state)
                self._resume_local_after_narrow(world, arc, pre)
                self.assertEqual(state[f"ywc_mgl_{pre}_terms_committed"], 3)
                self.assertNotIn(f"ywc_mgl_{pre}_full_mature", state)
                self._settle_mature(world, arc, 3)
                self.assertEqual(state[f"ywc_v03_mgl_{slug}_outcome"], 3)
                self.assertEqual(world.treasury["MGL"], treasury_after_payment)

    def test_real_entry_withdrawal_preserves_legacy_values_and_releases_capacity(self):
        arc = self.arc_by_slug["v03_mgl_two_trade_roads"]
        for legacy in (1, 2, 3, 4):
            with self.subTest(legacy=legacy):
                world = self._facts("roads", 1, 10000, legacy=legacy)
                self._entry(arc, world)
                event = self._deliver(world, arc, arc["events"][0]["id"])
                self._choose(world, arc, event, "withdraw")
                state = world.countries["MGL"]
                self.assertEqual(state["ywc_campaign_mng_c1_outcome"], legacy)
                self.assertEqual(state["ywc_v03_mgl_v03_mgl_two_trade_roads_outcome"], 4)
                self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (0, 0))
                self.assertEqual(world.history["MGL"][arc["journals"][0]["id"]], "failed")
                self.assertNotIn(arc["journals"][1]["id"], world.history["MGL"])

    def test_real_three_arc_admission_and_independent_pending_queues(self):
        world = self._facts("roads", 1, 10000)
        state = world.countries["MGL"]
        state["laws"].update({"law_tenant_farmers", "law_serfdom"})
        state["market"].update({"wool": {"exports": 2, "imports": 0, "pricier": 0},
                                "grain": {"exports": 0, "imports": 1, "pricier": 0.30}})
        state["buildings"].append({"groups": {"bg_livestock_ranches", "bg_government"}, "level": 1})
        state["states"][0]["pops"].extend([
            {"employed": True, "workplace": "building_livestock_ranch"},
            {"employed": True, "workplace": "building_government_administration"}])
        for arc in CATALOG_ARCS:
            self._entry(arc, world)
        self.assertEqual((state["ywc_v03_active_arc_count"], state["ywc_v03_visible_task_count"]), (3, 3))
        pending = {"roads": 1000, "debt": 1010, "grain": 1020}
        for pre, number in pending.items():
            self.assertEqual(state[f"ywc_mgl_{pre}_pending_event"], number)
        self.assertFalse(any(key.startswith("test_") for key in state))
        self.assertEqual(len(world.active_journals["MGL"]), 3)
        self.assertNotIn("ywc_v03_major_event_cooldown", state,
                         "admission itself must not invent a delivered-event cooldown")

    def test_actual_missing_world_facts_block_contracts_and_unknown_triggers_fail_closed(self):
        roads = self.arc_by_slug["v03_mgl_two_trade_roads"]
        roads_world = self._facts("roads", 1, 10000)
        roads_state = roads_world.countries["MGL"]
        roads_state["market"]["tea"]["exports"] = 0
        entry = self.generated_journals[roads["journals"][0]["id"]]
        self.assertFalse(roads_world.conditions(_block(entry, "is_shown_when_inactive"), "MGL"))
        roads_state["market"]["tea"]["exports"] = 100
        roads_state["laws"].remove("law_mercantilism")
        first_event = self.generated_events[roads["events"][0]["id"]]
        dual = next(body for name, _, body in first_event
                    if name == "option" and _block(body, "name").endswith(".dual"))
        self.assertFalse(roads_world.conditions(_block(dual, "trigger"), "MGL"))

        debt = self.arc_by_slug["v03_mgl_pastoral_debt"]
        debt_world = self._facts("debt", 1, 10000)
        debt_world.countries["MGL"]["states"][0]["pops"][0]["employed"] = False
        debt_event = self.generated_events[debt["events"][0]["id"]]
        debt_dual = next(body for name, _, body in debt_event
                         if name == "option" and _block(body, "name").endswith(".dual"))
        self.assertFalse(debt_world.conditions(_block(debt_dual, "trigger"), "MGL"))

        grain = self.arc_by_slug["v03_mgl_princes_monasteries"]
        grain_world = self._facts("grain", 1, 10000)
        grain_world.countries["MGL"]["market"]["grain"]["pricier"] = 0.20
        grain_event = self.generated_events[grain["events"][0]["id"]]
        grain_dual = next(body for name, _, body in grain_event
                          if name == "option" and _block(body, "name").endswith(".dual"))
        self.assertFalse(grain_world.conditions(_block(grain_dual, "trigger"), "MGL"))

        with self.assertRaisesRegex(AssertionError, "unsupported test trigger"):
            roads_world.condition(("mgl_unknown_world_predicate", "=", "yes"), "MGL")

    def test_devout_scope_evaluates_every_child_and_rejects_unknown_or_invalid_comparison(self):
        world = self._facts("grain", 1, 10000)
        state = world.countries["MGL"]
        state["interest_groups"]["ig_devout"] = 0
        mixed = ("ig:ig_devout", "?=", [("ig_approval", ">=", "0"),
                                          ("mgl_unknown_world_predicate", "=", "yes")])
        with self.assertRaisesRegex(AssertionError, "unsupported test trigger"):
            world.condition(mixed, "MGL")
        self.assertTrue(world.condition(("ig:ig_devout", "?=", [("ig_approval", ">=", "0")]), "MGL"))
        self.assertFalse(world.condition(("ig:ig_devout", "?=", [("ig_approval", ">", "0")]), "MGL"))
        with self.assertRaisesRegex(AssertionError, "unsupported IG comparison"):
            world.condition(("ig:ig_devout", "?=", [("ig_approval", "?=", "0")]), "MGL")

    def _settle_mature(self, world, arc, expected_outcome, max_months=12):
        start_month = world.evidence_marks[arc["slug"]]
        state = world.countries["MGL"]
        slug = arc["slug"]
        for _ in range(max_months):
            if f"ywc_v03_mgl_{slug}_settled" in state:
                break
            self._pulse(world, arc)
        self.assertGreaterEqual(world.calendar_months - start_month, 6)
        self.assertEqual(state.get(f"ywc_v03_mgl_{slug}_outcome"), expected_outcome, slug)
        for journal in arc["journals"]:
            self.assertEqual(world.history["MGL"].get(journal["id"]), "complete", (slug, journal["id"]))
        self.assertEqual(state["ywc_v03_active_arc_count"], 0)
        self.assertEqual(state["ywc_v03_visible_task_count"], 0)
        self.assertNotIn(f"ywc_v03_mgl_{slug}_withdrawn", state)

    def test_actual_world_facts_enable_two_distinct_paid_success_strategies_per_arc(self):
        scenarios = (("v03_mgl_two_trade_roads", 1, 200, 1), ("v03_mgl_two_trade_roads", 3, 50, 3),
                     ("v03_mgl_pastoral_debt", 1, 200, 1), ("v03_mgl_pastoral_debt", 3, 50, 3),
                     ("v03_mgl_princes_monasteries", 1, 200, 1), ("v03_mgl_princes_monasteries", 2, 100, 2))
        for slug, route, cash, outcome in scenarios:
            with self.subTest(arc=slug, route=route):
                arc = self.arc_by_slug[slug]
                world, state, pre = self._route(arc, route, cash)
                self._settle_mature(world, arc, outcome)
                self.assertNotIn(f"ywc_v03_mgl_{slug}_withdrawn", state)


if __name__ == "__main__":
    unittest.main()

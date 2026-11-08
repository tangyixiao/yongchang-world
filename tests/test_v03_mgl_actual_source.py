"""Strict actual-source fixture for MGL progression contract tests.

Only ordinary opening-world facts are fixture supplied. History, the legacy
campaign, the initializer, root admission, queues, payments and outcomes run
from the formal authored source through the Clausewitz subset interpreter.
"""
from __future__ import annotations

from itertools import permutations
from copy import deepcopy
import json
from pathlib import Path
import unittest

from tests.clausewitz_harness import parse
from tests import test_v03_mgl_foundation_lifecycle as base

ROOT = Path(__file__).resolve().parents[1]
TAG = "MGL"
LEGACY_JE = "ywc_je_flavor_mng_balance_1"
LEGACY_EVENTS = ("ywc_mng.7", "ywc_mng.100", "ywc_mng.101", "ywc_mng.102", "ywc_mng.103", "ywc_mng.104")
PREFIX = {"v03_mgl_two_trade_roads": "roads", "v03_mgl_pastoral_debt": "debt",
          "v03_mgl_princes_monasteries": "grain"}
PRE = {slug: prefix for slug, prefix in PREFIX.items()}
MGL_ARCS = json.loads((ROOT / "data/content/v03/countries/mgl.json").read_text(encoding="utf-8"))["arcs"]


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def _defs(paths):
    result = {}
    for path in paths:
        for key, _, body in parse(_read(path)):
            if key in result:
                raise AssertionError(("native_definition_collision", key, path))
            result[key] = body
    return result


def _block(nodes, name):
    rows = [value for key, _, value in nodes if key == name]
    if len(rows) != 1:
        raise AssertionError(("expected_unique_block", name, len(rows)))
    return rows[0]


def _num(event_id):
    return int(event_id.rsplit(".", 1)[1])


class _StrictMglWorld(base.MglWorldFacts):
    def __init__(self, effects, triggers, countries):
        self._trigger_stack = set()
        self.named_effect_calls = []
        super().__init__(effects, triggers, countries)
        self.strict_trigger_defs = self.trigger_defs
        self.story_month = 0
        self.completed_journals = []
        self.calendar_day = 0
        self._journal_request_cursor = 0

    def conditions(self, nodes, tag):
        # Clausewitz lists are implicit AND. Evaluate every child so a false
        # branch cannot conceal an unsupported atom or recursive helper.
        results = [self.condition(node, tag) for node in nodes]
        return all(results)

    def has_journal_entry(self, journal_id, tag=TAG):
        return journal_id in self.active_journals.get(tag, ())

    def run(self, name, tag=TAG):
        self.named_effect_calls.append(name)
        return super().run(name, tag)

    def advance_months(self, months=1):
        super().advance_months(months)
        self.story_month += months

    def advance_days(self, days=1):
        super().advance_days(days)
        self.calendar_day += days

    def condition(self, node, tag):
        key, comparison, value = node
        if key in {"AND", "OR", "NOT", "NOR"}:
            if comparison != "=" or not isinstance(value, list):
                raise AssertionError(("invalid_boolean_condition", node))
            # Visit every branch: unsupported conditions cannot hide behind short-circuit truth.
            results = [self.condition(child, tag) for child in value]
            return {"AND": all, "OR": any, "NOT": lambda xs: not all(xs),
                    "NOR": lambda xs: not any(xs)}[key](results)
        if key in self.strict_trigger_defs:
            if comparison != "=" or value not in ("yes", "no") or key in self._trigger_stack:
                raise AssertionError(("invalid_or_recursive_scripted_trigger", node))
            self._trigger_stack.add(key)
            try:
                matched = self.conditions(self.strict_trigger_defs[key], tag)
            finally:
                self._trigger_stack.remove(key)
            return matched == (value == "yes")
        if key == "is_subject":
            if comparison != "=" or value not in ("yes", "no"):
                raise AssertionError(("invalid_is_subject_condition", node))
            return bool(self.countries[tag].get("is_subject", False)) == (value == "yes")
        if key == "has_journal_entry":
            if comparison != "=" or value not in self.journal_defs:
                raise AssertionError(("invalid_has_journal_entry", node))
            return value in self.active_journals.get(tag, ())
        # Delegate ordinary Clausewitz atoms to the formal MGL fact evaluator.
        # Its unknown atom branch is made fail closed here.
        known = {"has_variable", "has_journal_entry", "has_law", "market_access", "average_sol",
                 "any_scope_state", "any_scope_pop", "is_employed", "workplace", "is_building_type",
                 "country_has_building_group_levels", "market_capital.market", "market_goods_exports",
                 "market_goods_imports", "market_goods_pricier", "ywc_mgl_roads_trade_signal",
                 "ywc_mgl_grain_entry_price", "ig:ig_devout", "military_expenses_share",
                 "has_modifier", "gold_reserves", "yearly_gross_income", "net_fixed_income",
                 "in_default", "is_at_war", "exists", "var", "always", "c"}
        if key.startswith(("var:", "c:")) or key in known:
            return super().condition(node, tag)
        raise AssertionError(("unsupported_actual_mgl_condition", node))


def _ordinary_facts():
    return {"gold_reserves": 10000, "yearly_gross_income": 5200, "net_fixed_income": 100,
            "in_default": False, "is_at_war": False, "is_subject": False,
            "laws": {"law_mercantilism", "law_tenant_farmers", "law_serfdom"},
            "buildings": [{"type": "building_livestock_ranch", "level": 2,
                           "groups": {"bg_livestock_ranches"}},
                          {"type": "building_government_administration", "level": 1,
                           "groups": {"bg_government"}}],
            "states": [{"market_access": 0.8, "average_sol": 11,
                        "buildings": [{"type": "building_livestock_ranch", "level": 2,
                                       "groups": {"bg_livestock_ranches"}},
                                      {"type": "building_government_administration", "level": 1,
                                       "groups": {"bg_government"}}],
                        "pops": [{"employed": True, "workplace": "building_livestock_ranch"},
                                 {"employed": True, "workplace": "building_government_administration"}]}],
            "market": {"tea": {"exports": 100, "imports": 0, "pricier": 0},
                       "grain": {"exports": 0, "imports": 1, "pricier": 0.30},
                       "wool": {"exports": 2, "imports": 0, "pricier": 0}},
            "relations": {"SHU": 0, "RUS": 0}, "interest_groups": {"ig_devout": 0},
            "military_expenses_share": 0.15, "modifiers": set()}


def actual_mgl_admission_world(admission_order=None, ordinary_facts=None):
    """Create a fresh world via actual history, legacy events, terminal and roots."""
    state = deepcopy(_ordinary_facts() if ordinary_facts is None else ordinary_facts)
    allowed_facts = set(_ordinary_facts())
    forbidden = sorted(set(state) - allowed_facts)
    if forbidden:
        raise ValueError(("ordinary_facts_contains_source_owned_state", forbidden))
    effects_paths = ("yongchang_world/common/scripted_effects/ywc_v03_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_v03_mgl_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_shared_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt",
                     "yongchang_world/common/scripted_effects/ywc_flavor_effects.txt")
    trigger_paths = ("yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt",
                     "yongchang_world/common/scripted_triggers/ywc_v03_mgl_triggers.txt")
    # Validate all formal helper registries before constructing this world's instances.
    _defs(effects_paths)
    _defs(trigger_paths)
    world = _StrictMglWorld("\n".join(_read(p) for p in effects_paths),
                            "\n".join(_read(p) for p in trigger_paths),
                            {TAG: state, "SHU": {"relations": {TAG: 0}}, "RUS": {"relations": {TAG: 0}}})
    world.journal_defs = _defs(("yongchang_world/common/journal_entries/ywc_mng.txt",
                                "yongchang_world/common/journal_entries/ywc_v03_country_mgl_journal.txt"))
    world.event_defs = {}
    for path in ("yongchang_world/events/ywc_steppe_highland_events.txt",
                 "yongchang_world/events/ywc_large_campaign_events.txt",
                 "yongchang_world/events/ywc_v03_country_mgl_events.txt"):
        for key, _, body in parse(_read(path)):
            if key == "namespace":
                continue
            if key in world.event_defs:
                raise AssertionError(("native_event_collision", key, path))
            world.event_defs[key] = body
    world.generated_journals = world.journal_defs
    world.generated_events = world.event_defs
    world.arc_by_slug = {arc["slug"]: arc for arc in MGL_ARCS}

    history = _defs(("yongchang_world/common/history/countries/ywc_content_starts.txt",))["COUNTRIES"]
    country = next((n for n in history if n[0] == "c:MGL"), None)
    if country is None or country[1] != "?=":
        raise AssertionError("authored MGL country history missing")
    world.execute([country], TAG)
    added = [dict((k, v) for k, _, v in body).get("type") for tag, body in world.journals if tag == TAG]
    if LEGACY_JE not in added:
        raise AssertionError(("history_missing_legacy_je", added))
    world.active_journals[TAG].append(LEGACY_JE)
    world.history[TAG][LEGACY_JE] = "active"
    world._journal_request_cursor = len(world.journals)

    legacy_trace = []
    for expected in LEGACY_EVENTS:
        emitted_id = None
        for _ in range(60):
            world.advance_months(1)
            pulse = _block(_block(world.journal_defs[LEGACY_JE], "on_monthly_pulse"), "effect")
            before = len(world.events)
            world.execute(pulse, TAG)
            emitted = world.events[before:]
            del world.events[before:]
            if emitted:
                if emitted != [(TAG, expected)]:
                    raise AssertionError(("legacy_event_order", expected, emitted))
                emitted_id = emitted[0][1]
                break
        if emitted_id != expected:
            raise AssertionError(("legacy_event_not_reached", expected))
        event = world.event_defs[expected]
        trigger = next((v for k, _, v in event if k == "trigger"), [])
        if trigger and not world.conditions(trigger, TAG):
            raise AssertionError(("legacy_full_trigger_false", expected))
        world.execute(next((v for k, _, v in event if k == "immediate"), []), TAG)
        option = next(v for k, _, v in event if k == "option" and _block(v, "name") == expected + ".b")
        gate = next((v for k, _, v in option if k == "trigger"), [])
        if gate and not world.conditions(gate, TAG):
            raise AssertionError(("legacy_option_illegal", expected + ".b"))
        effects = [n for n in option if n[0] not in ("name", "trigger", "ai_chance", "default_option", "custom_tooltip")]
        before_state = dict(state)
        world.execute(effects, TAG)
        legacy_trace.append({"event": expected, "option": expected + ".b",
                             "delta": {k: v for k, v in state.items() if before_state.get(k) != v}})

    legacy = world.journal_defs[LEGACY_JE]
    complete, failed = world.conditions(_block(legacy, "complete"), TAG), world.conditions(_block(legacy, "fail"), TAG)
    if complete == failed or not complete:
        raise AssertionError(("legacy_terminal_predicates", complete, failed))
    world.history[TAG][LEGACY_JE] = "complete"
    if LEGACY_JE not in world.completed_journals:
        world.completed_journals.append(LEGACY_JE)
    world.active_journals[TAG].remove(LEGACY_JE)
    active_after_terminal = list(world.active_journals[TAG])
    on_complete = next((v for k, _, v in legacy if k == "on_complete"), [])
    if on_complete:
        world.execute(on_complete, TAG)

    world.run("ywc_v03_initialize_country", TAG)
    post_history_month = world.story_month
    post_history_day = world.calendar_day
    state_business = sorted(k for k in state if k.startswith(("ywc_mgl_", "ywc_v03_mgl_")))
    if state_business:
        raise AssertionError(("business_state_seeded_before_roots", state_business))
    orders = [arc["slug"] for arc in MGL_ARCS]
    if admission_order is not None:
        orders = list(admission_order)
        if len(orders) != len(MGL_ARCS) or set(orders) != {a["slug"] for a in MGL_ARCS}:
            raise ValueError("admission_order must contain each MGL root slug exactly once")
    by_slug = {a["slug"]: a for a in MGL_ARCS}
    admissions = []
    for slug in orders:
        arc = by_slug[slug]
        jid = arc["journals"][0]["id"]
        je = world.journal_defs[jid]
        shown = world.conditions(_block(je, "is_shown_when_inactive"), TAG)
        possible = world.conditions(_block(je, "possible"), TAG)
        if not (shown and possible):
            raise AssertionError(("root_not_admissible", slug, shown, possible))
        before = dict(state)
        world.activate_journal(jid, TAG)
        admissions.append({"arc": slug, "journal": jid, "shown": shown, "possible": possible,
                           "immediate": True,
                           "delta": {k: v for k, v in state.items() if before.get(k) != v}})
    counts = {"active": state.get("ywc_v03_active_arc_count"),
              "visible": state.get("ywc_v03_visible_task_count")}
    if counts != {"active": 3, "visible": 3}:
        raise AssertionError(("root_admission_counts", counts))
    return world, {"history_legacy_je": LEGACY_JE, "legacy_trace": legacy_trace,
                   "root_admission_month": post_history_month,
                   "root_admission_day": post_history_day,
                   "legacy_terminal": {"complete": complete, "fail": failed,
                                       "completed": list(world.completed_journals),
                                       "active": active_after_terminal,
                                       "on_complete_ran": bool(on_complete)},
                   "root_admissions": admissions, "counts": counts}


def _refresh_actual_journal_lifecycle(world):
    """Apply engine-like JE terminal transitions after evaluating authored gates."""
    state = world.countries[TAG]
    # Source addJE requests are appended by the formal effect interpreter.
    # Reconcile them on every call, independent of the root JE's own terminal.
    requests = world.journals[world._journal_request_cursor:]
    world._journal_request_cursor = len(world.journals)
    for request_tag, request_body in requests:
        if request_tag != TAG:
            continue
        requested_id = dict((key, value) for key, _, value in request_body).get("type")
        if requested_id not in world.journal_defs or requested_id in world.active_journals[TAG]:
            raise AssertionError(("invalid_source_add_journal_request", requested_id, request_body))
        requested_fields = world.journal_defs[requested_id]
        possible_nodes = next((value for key, _, value in requested_fields if key == "possible"), None)
        shown_nodes = next((value for key, _, value in requested_fields
                            if key == "is_shown_when_inactive"), None)
        immediate_nodes = next((value for key, _, value in requested_fields if key == "immediate"), None)
        if possible_nodes is None or shown_nodes is None or immediate_nodes is None:
            # Legacy flavor JEs can be sourced through their own native event
            # path without inactive-admission gates. They are validated as
            # exact known definitions, but this MGL adapter does not synthesize
            # their activation. MGL review JEs require both gates below.
            if requested_id.startswith("ywc_je_v03_mgl_"):
                raise AssertionError(("source_add_journal_missing_admission_gates", requested_id))
            continue
        possible = world.conditions(possible_nodes, TAG)
        shown = world.conditions(shown_nodes, TAG)
        if not (possible and shown):
            raise AssertionError(("source_add_journal_not_admissible", requested_id, possible, shown))
        world.activate_journal(requested_id, TAG)
    for journal_id in list(world.active_journals[TAG]):
        fields = world.journal_defs[journal_id]
        complete = world.conditions(_block(fields, "complete"), TAG)
        failed = world.conditions(_block(fields, "fail"), TAG)
        if complete and failed:
            raise AssertionError(("journal_goal_fail_overlap", journal_id))
        if not (complete or failed):
            continue
        outcome = "complete" if complete else "failed"
        world.history[TAG][journal_id] = outcome
        world.active_journals[TAG].remove(journal_id)
        if journal_id in world.completed_journals:
            raise AssertionError(("duplicate_journal_terminal_record", journal_id))
        world.completed_journals.append(journal_id)
        if not complete:
            on_fail = next((v for k, _, v in fields if k == "on_fail"), [])
            if on_fail:
                world.execute(on_fail, TAG)
        else:
            on_complete = next((v for k, _, v in fields if k == "on_complete"), [])
            if on_complete:
                world.execute(on_complete, TAG)


def pulse_actual_journals(world):
    """Advance one month and execute only currently active, nonterminal JE pulses."""
    _refresh_actual_journal_lifecycle(world)
    active = list(world.active_journals[TAG])
    if not active:
        raise AssertionError("no active authored MGL journal to pulse")
    world.advance_months(1)
    first_event_id = None
    for journal_id in active:
        fields = world.journal_defs[journal_id]
        if world.conditions(_block(fields, "complete"), TAG) or world.conditions(_block(fields, "fail"), TAG):
            raise AssertionError(("terminal_journal_pulsed", journal_id))
        pulse = _block(fields, "on_monthly_pulse")
        before = len(world.events)
        world.execute(_block(pulse, "effect"), TAG)
        emitted = list(world.events[before:])
        del world.events[before:]
        if len(emitted) > 1:
            raise AssertionError(("one_journal_emitted_multiple_major_events", journal_id, emitted))
        if not emitted:
            continue
        if first_event_id is not None:
            raise AssertionError(("shared_90_day_gate_emitted_multiple_events", first_event_id, emitted))
        tag, event_id = emitted[0]
        if tag != TAG:
            raise AssertionError(("unexpected_event_country", tag, event_id))
        event = world.event_defs[event_id]
        trigger = _block(event, "trigger")
        if not world.conditions(trigger, TAG):
            raise AssertionError(("native_event_full_trigger_false", event_id))
        immediate = next((v for k, _, v in event if k == "immediate"), [])
        world.execute(immediate, TAG)
        _refresh_actual_journal_lifecycle(world)
        if first_event_id is None:
            first_event_id = event_id
    _refresh_actual_journal_lifecycle(world)
    return first_event_id


def choose_actual_option(world, event_id, suffix):
    event = world.event_defs[event_id]
    option = next((v for k, _, v in event if k == "option" and
                   _block(v, "name") == event_id + "." + suffix), None)
    if option is None:
        raise AssertionError(("missing_native_option", event_id, suffix))
    trigger = next((v for k, _, v in option if k == "trigger"), [])
    if trigger and not world.conditions(trigger, TAG):
        raise AssertionError(("native_option_not_legal", event_id, suffix))
    effects = [n for n in option if n[0] not in
               ("name", "trigger", "ai_chance", "default_option", "custom_tooltip")]
    world.execute(effects, TAG)
    _refresh_actual_journal_lifecycle(world)


class MglActualSourceFactoryTests(unittest.TestCase):
    def test_factory_builds_strict_actual_history_terminal_and_three_root_admissions(self):
        world, evidence = actual_mgl_admission_world()
        self.assertIs(world.strict_trigger_defs, world.trigger_defs)
        self.assertEqual([x["event"] for x in evidence["legacy_trace"]], list(LEGACY_EVENTS))
        self.assertEqual(evidence["legacy_terminal"], {"complete": True, "fail": False,
                         "completed": [LEGACY_JE], "active": [], "on_complete_ran": False})
        self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})
        self.assertTrue(all(x["shown"] and x["possible"] and x["immediate"] for x in evidence["root_admissions"]))

    def test_factory_supports_each_of_six_real_admission_orders(self):
        slugs = [arc["slug"] for arc in MGL_ARCS]
        for order in permutations(slugs):
            with self.subTest(order=order):
                world, evidence = actual_mgl_admission_world(order)
                self.assertEqual([x["arc"] for x in evidence["root_admissions"]], list(order))
                self.assertEqual(evidence["counts"], {"active": 3, "visible": 3})

    def test_factory_rejects_short_circuited_unknowns_and_bad_recursive_helpers(self):
        world, _ = actual_mgl_admission_world()
        with self.assertRaisesRegex(AssertionError, "unsupported_actual_mgl_condition"):
            world.condition(("AND", "=", [("always", "=", "no"), ("never_mgl_atom", "=", "yes")]), TAG)
        with self.assertRaisesRegex(AssertionError, "unsupported_actual_mgl_condition"):
            world.condition(("OR", "=", [("always", "=", "yes"), ("never_mgl_atom", "=", "yes")]), TAG)
        with self.assertRaisesRegex(AssertionError, "unsupported_actual_mgl_condition"):
            world.conditions([("always", "=", "no"), ("never_mgl_atom", "=", "yes")], TAG)
        helper = next(iter(world.strict_trigger_defs))
        with self.assertRaisesRegex(AssertionError, "invalid_or_recursive_scripted_trigger"):
            world.condition((helper, "=", "maybe"), TAG)
        world.strict_trigger_defs["fixture_cycle"] = [("fixture_cycle", "=", "yes")]
        try:
            with self.assertRaisesRegex(AssertionError, "invalid_or_recursive_scripted_trigger"):
                world.condition(("fixture_cycle", "=", "yes"), TAG)
        finally:
            world.strict_trigger_defs.pop("fixture_cycle")
        world.strict_trigger_defs["fixture_false_then_unknown"] = [
            ("always", "=", "no"), ("never_mgl_helper_atom", "=", "yes")]
        try:
            with self.assertRaisesRegex(AssertionError, "unsupported_actual_mgl_condition"):
                world.condition(("fixture_false_then_unknown", "=", "yes"), TAG)
        finally:
            world.strict_trigger_defs.pop("fixture_false_then_unknown")

    def test_source_payment_add_journal_request_is_required_for_review_admission(self):
        from tests.test_v03_mgl_actual_source import _refresh_actual_journal_lifecycle

        world, _ = actual_mgl_admission_world()
        state = world.countries[TAG]
        effect = world.effects["ywc_mgl_roads_pay_route_1"]

        def without_add_journal(nodes):
            cleaned = []
            for key, comparison, value in nodes:
                if key == "add_journal_entry":
                    continue
                if isinstance(value, list):
                    value = without_add_journal(value)
                cleaned.append((key, comparison, value))
            return cleaned

        # The actual payment effect's sole addJE request is removed in memory.
        world.effects["ywc_mgl_roads_pay_route_1"] = without_add_journal(effect)
        # Entry was genuinely reachable at root start; run the mutated authored
        # payment and force only its terminal fixture predicate for reconciliation.
        state["ywc_mgl_roads_entry_1_ready"] = 1
        world.run("ywc_mgl_roads_pay_route_1", TAG)
        self.assertFalse(any(tag == TAG and dict((k, v) for k, _, v in body).get("type") ==
                             "ywc_je_v03_mgl_roads_review" for tag, body in world.journals))
        state["ywc_v03_mgl_v03_mgl_two_trade_roads_settled"] = 1
        _refresh_actual_journal_lifecycle(world)
        self.assertNotIn("ywc_je_v03_mgl_roads_review", world.active_journals[TAG])
        self.assertFalse(world.has_journal_entry("ywc_je_v03_mgl_roads_review", TAG))
        self.assertFalse(any(tag == TAG and dict((k, v) for k, _, v in body).get("type") ==
                             "ywc_je_v03_mgl_roads_review" for tag, body in world.journals))

    def test_factory_rejects_seeded_membership_and_keeps_definition_registries_private(self):
        with self.assertRaisesRegex(ValueError, "ordinary_facts_contains_source_owned_state"):
            actual_mgl_admission_world(ordinary_facts={**_ordinary_facts(), "ywc_mgl_roads_route": 1})
        with self.assertRaisesRegex(ValueError, "ordinary_facts_contains_source_owned_state"):
            actual_mgl_admission_world(ordinary_facts={**_ordinary_facts(), "active_journals": ["fake"]})
        with self.assertRaisesRegex(ValueError, "ordinary_facts_contains_source_owned_state"):
            actual_mgl_admission_world(ordinary_facts={**_ordinary_facts(), "ywc_v03_initialized": 1})
        first, _ = actual_mgl_admission_world()
        second, _ = actual_mgl_admission_world()
        self.assertIs(first.strict_trigger_defs, first.trigger_defs)
        self.assertIsNot(first.strict_trigger_defs, second.strict_trigger_defs)
        self.assertIsNot(first.effects, second.effects)
        self.assertFalse(first.has_journal_entry(LEGACY_JE, TAG), "completed history request is not active membership")
        marker = "factory_instance_only"
        first.strict_trigger_defs[marker] = []
        try:
            self.assertNotIn(marker, second.strict_trigger_defs)
        finally:
            first.strict_trigger_defs.pop(marker)


if __name__ == "__main__":
    unittest.main()

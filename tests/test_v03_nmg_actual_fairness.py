"""Strict NMG actual-source history, initializer, and root admission fixture.

The world interpreter is the authored-source test harness, not the game engine.
Only ordinary engine-owned economic, legal, political, and building facts are fixtures.
"""
from pathlib import Path
import unittest

from tests import test_v03_nmg_foundation_lifecycle as base
from tests.clausewitz_harness import parse

ROOT = Path(__file__).resolve().parents[1]
TAG = "NMG"
OLD_JE = "ywc_je_flavor_nmg_bargain_1"
LEGACY_EVENTS = ("ywc_nmg.6", "ywc_nmg.100", "ywc_nmg.101", "ywc_nmg.102", "ywc_nmg.103", "ywc_nmg.104")


def _read(path):
    return (ROOT / path).read_text(encoding="utf-8-sig")


def _defs(paths):
    result = {}
    for path in paths:
        for key, _, body in parse(_read(path)):
            if key in result:
                raise AssertionError(("native_definition_collision", path, key))
            result[key] = body
    return result


class _ActualNmgWorld(base.NmgWorld):
    """Keep this fixture's strict source trigger registry instance-local."""
    def __init__(self, countries):
        self.named_effect_calls = []
        super().__init__(countries)

    def run(self, name, tag="NMG"):
        self.named_effect_calls.append(name)
        return super().run(name, tag)

    def validate_condition(self, node, seen=frozenset()):
        key, comparison, value = node
        if key in {"AND", "OR", "NOT", "NOR"}:
            if comparison != "=" or not isinstance(value, list):
                raise AssertionError(("invalid_boolean_condition", node))
            for child in value:
                self.validate_condition(child, seen)
            return
        if key in self.strict_trigger_defs:
            if comparison != "=" or value not in ("yes", "no") or key in seen:
                raise AssertionError(("invalid_or_recursive_scripted_trigger", node))
            for child in self.strict_trigger_defs[key]:
                self.validate_condition(child, seen | {key})
            return
        if key == "has_journal_entry":
            if (comparison != "=" or not isinstance(value, str) or not value.startswith("ywc_je_")
                    or not value.removeprefix("ywc_je_").replace("_", "").isalnum()):
                raise AssertionError(("invalid_journal_entry_query", node))
            return
        supported = {
            "has_variable", "has_modifier", "exists", "always", "net_fixed_income",
            "bureaucracy", "gold_reserves", "yearly_gross_income", "scaled_debt",
            "in_default", "is_at_war", "trigger_if", "calc_true_if", "ywc_nmg_v03_has_owned_state",
            "is_owned_by", "any_scope_state", "any_scope_building", "is_building_type",
            "occupancy", "building_has_goods_shortage", "has_law_or_variant", "radical_fraction",
            "literacy_rate", "institution_investment_level", "is_subject", "is_subject_of",
            "overlord", "relations:root", "relations_threshold:poor", "any_interest_group",
            "is_interest_group_type", "ig_approval",
        }
        if key.startswith("var:") or key.startswith("c:") or key in supported:
            return
        raise AssertionError(("unsupported_actual_nmg_condition", node))

    def condition(self, node, tag):
        self.validate_condition(node)
        key, comparison, value = node
        if key == "has_journal_entry":
            if (comparison != "=" or not isinstance(value, str) or not value.startswith("ywc_je_")
                    or not value.removeprefix("ywc_je_").replace("_", "").isalnum()):
                raise AssertionError(("invalid_journal_entry_query", node))
            return value in self.active_journals and tag == TAG
        if key in self.strict_trigger_defs:
            if comparison != "=" or value not in ("yes", "no") or key in self._trigger_stack:
                raise AssertionError(("invalid_or_recursive_scripted_trigger", node))
            self._trigger_stack.add(key)
            try:
                matched = self.conditions(self.strict_trigger_defs[key], tag)
            finally:
                self._trigger_stack.remove(key)
            return matched == (value == "yes")
        return super().condition(node, tag)


def actual_nmg_admission_world(admission_order=None):
    """Run real history + six old event options + initializer + all three root JEs.

    Returns (world, evidence). Starts with ordinary facts only; queues, outcomes,
    counters, lifecycle markers, and arc-private variables are not pre-seeded.
    """
    generic = base.fixture()
    allowed_nmg_facts = {
        "bureaucracy", "net_fixed_income", "yearly_gross_income", "gold_reserves",
        "fixture_owned_state", "fixture_state_owner", "fixture_shortages", "fixture_buildings",
        "fixture_laws", "literacy_rate", "fixture_schools_invested", "fixture_subject",
        "fixture_mex_overlord", "fixture_relations", "is_at_war",
    }
    facts = {TAG: {key: value for key, value in generic[TAG].items() if key in allowed_nmg_facts},
             "MEX": {"fixture_relations": 50}}
    state = facts[TAG]
    # These are the only fixture facts used to satisfy authored eligibility.
    world = _ActualNmgWorld(facts)
    effect_paths = (
        "yongchang_world/common/scripted_effects/ywc_v03_nmg_effects.txt",
        "yongchang_world/common/scripted_effects/ywc_v03_effects.txt",
        "yongchang_world/common/scripted_effects/ywc_campaign_effects.txt",
        "yongchang_world/common/scripted_effects/ywc_flavor_effects.txt",
        "yongchang_world/common/scripted_effects/ywc_shared_effects.txt",
    )
    adapter_effect = "yongchang_world/common/scripted_effects/ywc_v03_delivery_nmg_effects.txt"
    if (ROOT / adapter_effect).is_file():
        effect_paths += (adapter_effect,)
    world.effects.update(_defs(effect_paths))
    trigger_paths = (
        "yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt",
        "yongchang_world/common/scripted_triggers/ywc_v03_nmg_triggers.txt",
    )
    triggers = {}
    adapter_trigger = "yongchang_world/common/scripted_triggers/ywc_v03_delivery_nmg_triggers.txt"
    if (ROOT / adapter_trigger).is_file():
        trigger_paths += (adapter_trigger,)
    for path in trigger_paths:
        for key, _, body in parse(_read(path)):
            if key in triggers:
                raise AssertionError(("trigger_definition_collision", key, path))
            triggers[key] = body
    world.strict_trigger_defs = triggers
    world.trigger_defs = triggers
    world._trigger_stack = set()
    journals = _defs(("yongchang_world/common/journal_entries/ywc_nmg.txt",
                      "yongchang_world/common/journal_entries/ywc_v03_country_nmg_journal.txt"))
    world.journal_defs = journals
    event_paths = ("yongchang_world/events/ywc_kor_lan_nmg_events.txt",
                   "yongchang_world/events/ywc_large_campaign_events.txt",
                   "yongchang_world/events/ywc_v03_country_nmg_events.txt")
    world.event_defs = {}
    optional_event_hooks = "yongchang_world/events/ywc_v03_delivery_nmg_events.txt"
    if (ROOT / optional_event_hooks).is_file():
        event_paths += (optional_event_hooks,)
    for path in event_paths:
        for key, _, body in parse(_read(path)):
            if key == "namespace":
                continue
            if key in world.event_defs:
                raise AssertionError(("event_definition_collision", key, path))
            world.event_defs[key] = body

    # Execute the authored NMG country history block; only this source may add the old JE.
    countries = _defs(["yongchang_world/common/history/countries/ywc_content_starts.txt"])["COUNTRIES"]
    scope = next((node for node in countries if node[0] == "c:NMG"), None)
    if scope is None or scope[1] != "?=":
        raise AssertionError("authored NMG country history scope missing")
    world.execute([scope], TAG)
    added = [body for tag, body in world.journals if tag == TAG]
    if not any(isinstance(item, list) and base.field(item, "type") == OLD_JE for item in added):
        raise AssertionError(("actual_history_did_not_add_legacy_je", added))
    world.active_journal = OLD_JE
    world.active_journals.add(OLD_JE)

    legacy = journals[OLD_JE]
    pulse = base.field(base.field(legacy, "on_monthly_pulse"), "effect")
    trace = []
    for expected in LEGACY_EVENTS:
        event_id = None
        for _ in range(36):
            world.advance_months(1)
            before = len(world.events)
            world.execute(pulse, TAG)
            emitted = world.events[before:]
            del world.events[before:]
            if emitted:
                if len(emitted) != 1 or emitted[0][0] != TAG:
                    raise AssertionError(("legacy_emission_shape", emitted))
                event_id = emitted[0][1]
                break
        if event_id != expected:
            raise AssertionError(("legacy_event_order", expected, event_id))
        event = world.event_defs[event_id]
        gate = next((body for key, _, body in event if key == "trigger"), [])
        if gate and not world.conditions(gate, TAG):
            raise AssertionError(("legacy_event_trigger_false", event_id))
        immediate = next((body for key, _, body in event if key == "immediate"), [])
        world.execute(immediate, TAG)
        # Authored historical route: the existing .b option is legal for all six events.
        option_name = event_id + ".b"
        option = next(body for key, _, body in event if key == "option"
                      and base.field(body, "name") == option_name)
        option_gate = next((body for key, _, body in option if key == "trigger"), [])
        if option_gate and not world.conditions(option_gate, TAG):
            raise AssertionError(("legacy_option_not_legal", option_name))
        before = dict(state)
        world.execute([node for node in option if node[0] not in
                       ("name", "trigger", "ai_chance", "default_option", "custom_tooltip")], TAG)
        trace.append({"event": event_id, "option": option_name,
                      "changes": {k: v for k, v in state.items() if before.get(k) != v}})
    legacy_complete = world.conditions(base.field(legacy, "complete"), TAG)
    legacy_fail = world.conditions(base.field(legacy, "fail"), TAG)
    if legacy_complete == legacy_fail:
        raise AssertionError(("legacy_terminal_predicates_not_exclusive", legacy_complete, legacy_fail))
    if not legacy_complete:
        raise AssertionError("legacy authored story did not complete")
    world.completed_journals.append(OLD_JE)
    world.active_journals.discard(OLD_JE)
    world.active_journal = None
    legacy_active_after_complete = sorted(world.active_journals)
    on_complete = next((body for key, _, body in legacy if key == "on_complete"), [])
    if on_complete:
        world.execute(on_complete, TAG)
    if world.active_journal is not None or OLD_JE in world.active_journals:
        raise AssertionError("completed legacy JE remained active")
    if state.get("ywc_campaign_nmg_c1_outcome") != 2 or state.get("ywc_je_flavor_nmg_bargain_1_resolved") != 1:
        raise AssertionError(("legacy_source_result_missing", dict(state)))

    world.run("ywc_v03_initialize_country", TAG)
    if state.get("ywc_v03_active_arc_count") != 0 or state.get("ywc_v03_visible_task_count") != 0:
        raise AssertionError(("initializer_not_empty", dict(state)))
    admissions = []
    arcs_by_slug = {arc["slug"]: arc for arc in base.CATALOG["arcs"]}
    if admission_order is None:
        ordered_arcs = list(base.CATALOG["arcs"])
    else:
        order = list(admission_order)
        if len(order) != len(arcs_by_slug) or set(order) != set(arcs_by_slug):
            raise ValueError("admission_order must contain every NMG foundation arc slug exactly once")
        ordered_arcs = [arcs_by_slug[slug] for slug in order]
    for arc in ordered_arcs:
        first = arc["journals"][0]
        # The catalog locates the entry, but only the generated live JE contains
        # production-appended source hooks as well as its authored gates.
        nodes = world.journal_defs[first["id"]]
        shown = next(body for key, _, body in nodes if key == "is_shown_when_inactive")
        possible = next(body for key, _, body in nodes if key == "possible")
        if not (world.conditions(shown, TAG) and world.conditions(possible, TAG)):
            raise AssertionError(("root_not_jointly_admissible", arc["slug"]))
        before = dict(state)
        immediate = next(body for key, _, body in nodes if key == "immediate")
        world.execute(immediate, TAG)
        world.active_journal = first["id"]
        world.active_journals.add(first["id"])
        world.journals.append((TAG, [("type", "=", first["id"])]))
        admissions.append({"arc": arc["slug"], "je": first["id"],
                           "shown": True, "possible": True,
                           "delta": {k: v for k, v in state.items() if before.get(k) != v}})
    if state.get("ywc_v03_active_arc_count") != 3 or state.get("ywc_v03_visible_task_count") != 3:
        raise AssertionError(("three_root_admission_count", state))
    return world, {"history_added_legacy_je": OLD_JE,
                   "legacy_lifecycle": {"complete": legacy_complete, "fail": legacy_fail,
                                        "completed_bookkeeping": world.completed_journals.copy(),
                                        "active_after_complete": legacy_active_after_complete},
                   "legacy_trace": trace,
                   "root_admissions": admissions,
                   "final_counts": {"active": state["ywc_v03_active_arc_count"],
                                    "visible": state["ywc_v03_visible_task_count"]}}


class NmgActualAdmissionAndTransportRed(unittest.TestCase):
    def test_actual_fixture_rejects_short_circuited_unknown_and_invalid_helper_calls(self):
        world, _ = actual_nmg_admission_world()
        self.assertTrue(world.condition(("always", "=", "yes"), TAG))
        unknown = ("not_a_real_nmg_condition", "=", "yes")
        false_and = ("AND", "=", [("always", "=", "no"), unknown])
        true_or = ("OR", "=", [("always", "=", "yes"), unknown])
        with self.assertRaisesRegex(AssertionError, "unsupported_actual_nmg_condition"):
            world.condition(false_and, TAG)
        with self.assertRaisesRegex(AssertionError, "unsupported_actual_nmg_condition"):
            world.condition(true_or, TAG)
        helper = next(iter(world.strict_trigger_defs))
        with self.assertRaisesRegex(AssertionError, "invalid_or_recursive_scripted_trigger"):
            world.condition((helper, "=", "maybe"), TAG)
        world.strict_trigger_defs["fixture_cycle"] = [("fixture_cycle", "=", "yes")]
        try:
            with self.assertRaisesRegex(AssertionError, "invalid_or_recursive_scripted_trigger"):
                world.condition(("fixture_cycle", "=", "yes"), TAG)
        finally:
            world.strict_trigger_defs.pop("fixture_cycle")

    def test_factory_executes_real_history_legacy_chain_initializer_and_all_root_admissions(self):
        _world, evidence = actual_nmg_admission_world()
        self.assertEqual([row["event"] for row in evidence["legacy_trace"]], list(LEGACY_EVENTS))
        self.assertEqual(len(evidence["root_admissions"]), 3)
        self.assertTrue(all(row["shown"] and row["possible"] for row in evidence["root_admissions"]))
        self.assertEqual(evidence["final_counts"], {"active": 3, "visible": 3})
        self.assertEqual(evidence["legacy_lifecycle"]["complete"], True)
        self.assertEqual(evidence["legacy_lifecycle"]["fail"], False)
        self.assertEqual(evidence["legacy_lifecycle"]["active_after_complete"], [])

    def test_factory_accepts_all_six_authored_root_admission_orders(self):
        import itertools
        slugs = [arc["slug"] for arc in base.CATALOG["arcs"]]
        for order in itertools.permutations(slugs):
            with self.subTest(order=order):
                _world, evidence = actual_nmg_admission_world(order)
                self.assertEqual([row["arc"] for row in evidence["root_admissions"]], list(order))
                self.assertEqual(evidence["final_counts"], {"active": 3, "visible": 3})

    def test_all_six_native_first_pulse_orders_require_real_transport_reservation(self):
        import itertools
        import math
        from tests.test_v03_nmg_inline_adapter import catalog
        from tools.v03_inline_delivery_adapter import _queue_snapshot_name, render_inline_country_adapters
        native_catalog = catalog()
        for order in itertools.permutations(base.CATALOG["arcs"]):
            with self.subTest(order=tuple(arc["slug"] for arc in order)):
                order_slugs = [arc["slug"] for arc in order]
                world, _ = actual_nmg_admission_world(order_slugs)
                world.advance_months(1)
                country = world.countries[TAG]
                prefix = "ywc_v03_nmg_inline"
                candidates = [(arc_row, branch, candidate)
                              for arc_row in native_catalog["arcs"]
                              for branch in arc_row.get("inline_delivery_adapter", {}).get("branches", [])
                              for candidate in branch["candidates"]]
                captured_round = None
                # This contract proves the first actual popup only. Native NMG
                # events set a shared 90-day cooldown, so later JEs may correctly
                # emit no popup in this same calendar month; story audits own the
                # complete monthly pulse/fairness path.
                for arc in order[:1]:
                    je_id = arc["journals"][0]["id"]
                    entry = world.journal_defs[je_id]
                    pulse = base.field(base.field(entry, "on_monthly_pulse"), "effect")
                    before = len(world.events)
                    world.active_journal = je_id
                    world.execute(pulse, TAG)
                    emitted = world.events[before:]
                    self.assertEqual(len(emitted), 1,
                                     f"active native JE {je_id} must produce one actual first popup")
                    event_id = emitted[0][1]
                    event = world.event_defs[event_id]
                    trigger = next((body for key, _, body in event if key == "trigger"), [])
                    self.assertTrue(world.conditions(trigger, TAG), event_id)

                    # Deliberate feature RED is at the first actual native popup:
                    # a source-valid adapter must be renderable and have reserved
                    # this exact authored queue before the native immediate runs.
                    try:
                        rendered = render_inline_country_adapters(native_catalog)
                    except (ValueError, KeyError, AssertionError) as exc:
                        self.fail(f"actual native popup {event_id} has no valid source-bound adapter: {exc}")
                    self.assertIn(prefix + "_reservation", country,
                                  f"native first popup {event_id} lacks a selected-candidate reservation")
                    reservation = country[prefix + "_reservation"]
                    self.assertIsInstance(reservation, (int, float))
                    self.assertNotIsInstance(reservation, bool)
                    self.assertTrue(math.isfinite(reservation))
                    self.assertEqual(reservation, int(reservation))
                    reservation_id = int(reservation)
                    self.assertGreater(reservation_id, 0)
                    self.assertLessEqual(reservation_id, len(candidates))
                    arc_row, branch, candidate = candidates[reservation_id - 1]
                    self.assertEqual(branch["event"], event_id)
                    self.assertEqual(branch["journal"], je_id)
                    epoch = country[prefix + "_reservation_epoch"]
                    self.assertGreater(epoch, 0)
                    self.assertIsInstance(epoch, (int, float))
                    self.assertNotIsInstance(epoch, bool)
                    self.assertTrue(math.isfinite(epoch))
                    self.assertEqual(epoch, int(epoch))
                    self.assertEqual(country[f"{prefix}_candidate_epoch_{reservation_id}"], epoch)
                    present = _queue_snapshot_name(reservation_id, candidate["queue"], "present", prefix)
                    value = _queue_snapshot_name(reservation_id, candidate["queue"], "value", prefix)
                    self.assertIn(present, country)
                    self.assertEqual(country[present], 1)
                    self.assertIn(value, country)
                    self.assertEqual(country[value], candidate["value"])
                    round_name = prefix + "_round"
                    self.assertIn(round_name, country)
                    if captured_round is None:
                        captured_round = country[round_name]
                        self.assertIsInstance(captured_round, (int, float))
                        self.assertNotIsInstance(captured_round, bool)
                        self.assertTrue(math.isfinite(captured_round))
                        self.assertEqual(captured_round, int(captured_round))
                        self.assertGreater(captured_round, 0)
                    self.assertEqual(country[round_name], captured_round)
                    guard = f"{prefix}_dispatch_{reservation_id}"
                    self.assertIn(guard, rendered["event_hooks"][event_id])
                    guard_body = world.trigger_defs.get(guard)
                    self.assertIsNotNone(guard_body)
                    self.assertTrue(world.conditions(guard_body, TAG))

                    immediate = next((body for key, _, body in event if key == "immediate"), [])
                    before_calls = len(world.named_effect_calls)
                    from copy import deepcopy
                    original_run = world.run
                    ack_observations = []
                    ack = f"{prefix}_ack_{reservation_id}"
                    def trace_ack_run(name, tag="NMG"):
                        if name != ack:
                            return original_run(name, tag)
                        before_state = deepcopy(world.countries[TAG])
                        result = original_run(name, tag)
                        after_state = deepcopy(world.countries[TAG])
                        ack_observations.append((before_state, result, after_state))
                        return result
                    world.run = trace_ack_run
                    world.execute(immediate, TAG)
                    world.run = original_run
                    callback = f"{prefix}_callback_{reservation_id}"
                    self.assertIn(callback, rendered["ack_hooks"][event_id])
                    calls = world.named_effect_calls[before_calls:]
                    self.assertIn(callback, calls, "event must call the ACK callback helper")
                    self.assertEqual(len(ack_observations), 1,
                                     "world.run must enter the exact source ACK body exactly once")
                    ack_before, ack_return, ack_after = ack_observations[0]
                    self.assertIn(candidate["queue"], ack_before,
                                  "native queue must remain present at the whole-body ACK boundary")
                    self.assertEqual(ack_before[candidate["queue"]], candidate["value"])
                    self.assertEqual(ack_before[prefix + "_reservation"], reservation_id)
                    self.assertIn(prefix + "_timer", ack_before)
                    self.assertEqual(ack_before[present], 1)
                    self.assertEqual(ack_before[value], candidate["value"])
                    self.assertEqual(ack_before[round_name], captured_round)
                    self.assertIn(ack, calls, "named call trace corroborates the actual ACK entry")
                    self.assertNotIn(candidate["queue"], country,
                                     "selected queue must be consumed only after complete ACK")
                    self.assertNotIn(prefix + "_reservation", country)
                    self.assertNotIn(prefix + "_timer", country)
                    for suffix in ("present", "value"):
                        self.assertNotIn(_queue_snapshot_name(reservation_id, candidate["queue"], suffix, prefix), country)
                    self.assertNotIn(f"{prefix}_candidate_epoch_{reservation_id}", country)
                    arc_index = next(i for i, row in enumerate(native_catalog["arcs"])
                                     if row["slug"] == arc_row["slug"])
                    served = f"{prefix}_served_{arc_index + 1}"
                    self.assertEqual(country.get(served), captured_round,
                                     "successful ACK must record this arc as served for the captured round")
                    self.assertNotIn(candidate["queue"], ack_after)
                    self.assertNotIn(prefix + "_reservation", ack_after)
                    self.assertNotIn(prefix + "_timer", ack_after)
                    self.assertNotIn(present, ack_after)
                    self.assertNotIn(value, ack_after)
                    self.assertNotIn(f"{prefix}_candidate_epoch_{reservation_id}", ack_after)
                    self.assertEqual(ack_after.get(served), captured_round)
                    self.assertEqual(ack_return, None,
                                     "the actual authored ACK effect returns normally after its whole body")
                    options = [body for key, _, body in event if key == "option"]
                    legal = []
                    for option in options:
                        gate = next((body for key, _, body in option if key == "trigger"), [])
                        if not gate or world.conditions(gate, TAG):
                            legal.append(option)
                    self.assertTrue(legal, event_id)
                    selected = legal[0]
                    effects = [node for node in selected
                               if node[0] not in ("name", "trigger", "ai_chance", "custom_tooltip")]
                    world.execute(effects, TAG)
                    world.events.clear()
                    break



if __name__ == "__main__":
    unittest.main()

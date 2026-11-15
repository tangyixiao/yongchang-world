"""JHG inline provenance contracts over actual authored source commands.

All postgate journeys start at the real history/legacy/initializer/root
factory. The 58-row unit inventory describes callsites; isolated queue inputs
are permitted only in named source-callsite fixtures and never count as a
natural full-story journey or engine evidence.
"""
from __future__ import annotations

import copy
import unittest
from contextlib import nullcontext
from functools import lru_cache

from tests import test_v03_jhg_inline_actual_source as actual
from tests import test_v03_jhg_inline_adapter as binding
from tests.test_v03_jhg_inline_native_story import run_native_route, _assert_route2_contract

TAG = actual.TAG
PREFIX = "ywc_v03_jhg_inline"
COOLDOWN = "ywc_v03_major_event_cooldown"
_JHG_QUEUE_NAMES = (
    "ywc_jhg_court_pending_event", "ywc_jhg_court_notice_pending_event",
    "ywc_jhg_convoy_pending_event", "ywc_jhg_convoy_notice_pending_event",
    "ywc_jhg_tribute_pending_event", "ywc_jhg_tribute_notice_pending_event",
)


def _all_bindings():
    """Return source-bound candidates in authored catalog order, IDs 1..58."""
    cat = binding._v2_catalog_from_formal_jhg_source()
    rows = []
    for arc in cat["arcs"]:
        adapter = arc["inline_delivery_adapter"]
        for branch in adapter["branches"]:
            if len(branch["candidates"]) != 1:
                raise AssertionError(("JHG candidate cardinality", branch))
            rows.append({"id": len(rows) + 1, "arc": arc, "branch": branch,
                         "candidate": branch["candidates"][0]})
    return rows


def _selected(event_id, candidate_id):
    if isinstance(candidate_id, bool) or not isinstance(candidate_id, (int, float)):
        return None
    if candidate_id <= 0 or int(candidate_id) != candidate_id:
        return None
    rows = _all_bindings()
    if candidate_id > len(rows):
        return None
    row = rows[int(candidate_id) - 1]
    return row if row["branch"]["event"] == event_id else None


def _event(world, event_id):
    try:
        return world.event_defs[event_id]
    except KeyError as exc:
        raise AssertionError(("missing generated JHG event", event_id)) from exc


def _snapshot(world):
    """Capture complete native variable and timer presence/value state."""
    state = world.countries[TAG]
    native = {name: copy.deepcopy(value) for name, value in state.items()
              if not name.startswith(PREFIX + "_")}
    return {
        "variables": native,
        "days_until_expiry": {k: copy.deepcopy(v) for k, v in world.days_until_expiry[TAG].items()
                               if not k.startswith(PREFIX + "_")},
        "months_until_expiry": {k: copy.deepcopy(v) for k, v in world.months_until_expiry[TAG].items()
                                  if not k.startswith(PREFIX + "_")},
        "treasury": copy.deepcopy(world.treasury.get(TAG, 0)),
    }


def _present_value(mapping, name):
    return (name in mapping, copy.deepcopy(mapping.get(name)))


@lru_cache(maxsize=1)
def _native_jhg_source_world():
    """Cache raw native JHG AST registries for independent source-fragment oracles."""
    return actual._initial_world()


def _native_fragment_outcome(testcase, phase_world, row, notice_case=None):
    """Run only the matching raw native sender branch and immediate from the same inputs."""
    world = actual.copy_actual_world_without_observers(phase_world)
    state = world.countries[TAG]
    for queue in _JHG_QUEUE_NAMES:
        state.pop(queue, None)
    queue = row["candidate"]["queue"]
    state[queue] = row["candidate"]["value"]
    if notice_case is not None:
        pre36, delivery36, marker = notice_case
        stem = _native_notice_stem(queue)
        pre_name = stem + "_36_notice"
        d12 = stem + "_notice_delivery_12"
        d36 = stem + "_notice_delivery_36"
        m12 = stem + "_12_notice_delivered"
        m36 = stem + "_36_notice_delivered"
        if pre36 is None: state.pop(pre_name, None)
        else: state[pre_name] = pre36
        state.pop(d12, None)
        if delivery36 is None: state.pop(d36, None)
        else: state[d36] = delivery36
        state.pop(m12, None); state.pop(m36, None)
        target = m36 if pre36 is not None or delivery36 is not None else m12
        if marker is None: state.pop(target, None)
        else: state[target] = marker
    world.advance_days(91)

    raw = _native_jhg_source_world()
    journal = row["branch"]["journal"]
    event = row["branch"]["event"]
    world.journal_defs[journal] = copy.deepcopy(raw.journal_defs[journal])
    world.event_defs[event] = copy.deepcopy(raw.event_defs[event])
    pulse = actual._field(actual._field(world.journal_defs[journal],
                                       "on_monthly_pulse", []), "effect", [])
    native_branch = _matching_native_branch(world, row)
    before = len(world.dispatch_contexts)
    world.execute([_standalone_branch(native_branch)], TAG)
    appended = world.dispatch_contexts[before:]
    testcase.assertEqual(len(appended), 1, (row["id"], "raw native source fragment append"))
    testcase.assertEqual(appended[0]["event_id"], event)
    actual.run_inline_event_immediate(world, event)
    return _snapshot(world)


def _standalone_branch(node):
    """Run one exact else_if source node as an explicitly isolated branch unit."""
    key, op, body = node
    if key not in ("if", "else_if"):
        raise AssertionError(("expected authored branch node", node))
    return ("if", op, body)


def _matching_native_branch(world, row):
    """Find the unique original JHG branch bound to this journal/queue/event."""
    pulse = actual._field(actual._field(world.journal_defs[row["branch"]["journal"]],
                                      "on_monthly_pulse", []), "effect", [])
    queue = "var:" + row["candidate"]["queue"]
    value = str(row["candidate"]["value"])
    found = []
    for node in pulse:
        if node[0] not in ("if", "else_if") or not isinstance(node[2], list):
            continue
        event_ids = [v for k, _, v in _walk(node[2]) if k == "id"]
        queue_tests = [(k, o, v) for k, o, v in _walk(node[2])
                       if k == queue and o == "=" and str(v) == value]
        if row["branch"]["event"] in event_ids and queue_tests:
            found.append(node)
    if len(found) != 1:
        raise AssertionError(("raw native source branch must uniquely match exact row",
                              row["id"], found))
    return found[0]


def _one_real_dispatch(testcase, body_first=False):
    """Run one actual root monthly sender and return its captured dispatch.

    This stops between the authored trigger append and a separately driven
    body, except when body_first=True, where the append observer runs the
    actual registered body in the copied context before source continuation.
    """
    world, evidence = actual.actual_jhg_inline_world()
    testcase.assertEqual((len(evidence["legacy_events"]), len(evidence["roots"])), (6, 3))
    rows = []
    append_states = []
    append_native_states = []
    body_pause_states = []
    effect_runs = []
    seen = set()

    def body_at_append(current, dispatch):
        rows.append(copy.deepcopy(dispatch))
        append_states.append(copy.deepcopy(current.countries[TAG]))
        append_native_states.append(_snapshot(current))
        if body_first:
            actual.run_queued_inline_event_immediate(current, dispatch)
            body_pause_states.append(copy.deepcopy(current.countries[TAG]))

    active = sorted(world.active_journals)
    with actual.observe_actual_effect_runs(world, lambda _w, name, _tag: effect_runs.append(name)):
      with actual.observe_actual_dispatch_append(world, body_at_append):
        for _ in range(8):
            world.advance_months(1)
            for journal_id in active:
                pulse = actual._field(actual._field(world.journal_defs[journal_id], "on_monthly_pulse", []), "effect", [])
                before = len(world.dispatch_contexts)
                world.execute(pulse, TAG)
                found = world.dispatch_contexts[before:]
                if found:
                    testcase.assertEqual(len(found), 1, "one authored sender append per selected pulse")
                    seen.add(journal_id)
                    break
            if rows:
                break
    testcase.assertTrue(rows, "real generated root source must emit within eight monthly pulses")
    dispatch = rows[0]
    testcase.assertEqual(dispatch["tag"], TAG)
    reservation = dispatch["scope_context"].get(PREFIX + "_dispatch_candidate")
    row = _selected(dispatch["event_id"], reservation)
    testcase.assertIsNotNone(row, (dispatch, reservation))
    epoch = dispatch["scope_context"].get(PREFIX + "_dispatch_epoch")
    testcase.assertIsInstance(epoch, (int, float)); testcase.assertNotIsInstance(epoch, bool)
    testcase.assertGreater(epoch, 0)
    scope = dispatch["scope_context"]
    queue = row["candidate"]["queue"]
    testcase.assertEqual(append_states[0].get(PREFIX + "_reservation"), reservation)
    testcase.assertEqual(append_states[0].get(PREFIX + "_reservation_epoch"), epoch)
    testcase.assertEqual(append_states[0].get(queue), row["candidate"]["value"])
    testcase.assertNotIn(COOLDOWN, append_native_states[0]["days_until_expiry"],
                         "a positive source admission is captured before body cooldown mutation")
    if body_first:
        state = world.countries[TAG]
        testcase.assertEqual(state.get(f"{PREFIX}_body_completed_{int(reservation)}"), 1)
        testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_{int(reservation)}"), 1)
        testcase.assertNotIn(PREFIX + "_reservation", state)
        testcase.assertNotIn(queue, state)
        testcase.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        pause = body_pause_states[0]
        testcase.assertEqual(pause.get(f"{PREFIX}_body_completed_{int(reservation)}"), 1)
        testcase.assertNotIn(f"{PREFIX}_sender_completed_{int(reservation)}", pause)
        testcase.assertEqual(pause.get(PREFIX + "_reservation"), reservation)
        testcase.assertIn(queue, pause)
        testcase.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90,
                             "the native body cooldown is present even while sender proof is pending")
    else:
        state = world.countries[TAG]
        testcase.assertEqual(state.get(PREFIX + "_reservation"), reservation)
        testcase.assertEqual(state.get(queue), row["candidate"]["value"])
        testcase.assertNotIn(f"{PREFIX}_body_completed_{int(reservation)}", state)
    world._b2_effect_runs = tuple(effect_runs)
    world._b2_append_native_state = copy.deepcopy(append_native_states[0])
    world._b2_body_pause_state = (copy.deepcopy(body_pause_states[0]) if body_pause_states else None)
    return world, evidence, dispatch, row, int(reservation), epoch


def _walk(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list):
            yield from _walk(value)


def _native_notice_stem(queue):
    """Strip source queue suffixes longest-first for exact native field setup."""
    for suffix in ("_notice_pending_event", "_pending_event"):
        if queue.endswith(suffix):
            return queue[:-len(suffix)]
    raise AssertionError(("unknown authored queue suffix", queue))


def _phase_worlds(testcase):
    """Copy each genuinely admitted live JHG phase at its real prepare wake."""
    actual.assert_inline_supported(testcase)
    world, evidence = actual.actual_jhg_inline_world()
    phases = {}
    witnesses = world.inline_rendered["live_witnesses"]
    def at_prepare(current, name, tag):
        if name != PREFIX + "_prepare" or tag != TAG:
            return
        state = current.countries[tag]
        for journal, witness in witnesses.items():
            if journal in phases or not current.journal_is_active(tag, journal):
                continue
            if current.is_finished(tag, journal) or witness not in state or state[witness] != 1:
                continue
            definition = current.journal_defs[journal]
            if current.conditions(actual._field(definition, "complete", []), tag):
                continue
            if current.conditions(actual._field(definition, "fail", []), tag):
                continue
            phases[journal] = actual.copy_actual_world_without_observers(current)
    with actual.observe_actual_effect_runs(world, at_prepare):
        result = run_native_route(2, world=world, evidence=evidence)
    _assert_route2_contract(testcase, result)
    testcase.assertEqual(set(phases), {row["branch"]["journal"] for row in _all_bindings()},
                         "every contract fixture must descend from an actually admitted native phase")
    return phases


@lru_cache(maxsize=1)
def _native_notice_phase_worlds():
    """Capture genuine raw-source notice phases before authored options run."""
    from tests import test_v03_jhg_inline_native_story as story
    world = actual._initial_world()
    legacy = actual._run_legacy_and_initialize(world)
    roots = actual._admit_roots(world)
    pulse_journals = {
        id(actual._field(actual._field(definition, "on_monthly_pulse", []), "effect", [])): journal
        for journal, definition in world.journal_defs.items()
    }
    target = {(row["branch"]["journal"], row["branch"]["event"])
              for row in _all_bindings() if row["candidate"]["kind"] == "notice"}
    active_journal = [None]
    phase_worlds = {}
    cls = type(world)
    own_execute = cls.__dict__.get("execute")
    original_execute = getattr(cls, "execute")
    original_immediate = story.run_queued_inline_event_immediate

    def observed_execute(current, nodes, tag=TAG):
        if current is world and id(nodes) in pulse_journals:
            active_journal[0] = pulse_journals[id(nodes)]
        return original_execute(current, nodes, tag)

    def observed_immediate(current, dispatch):
        result = original_immediate(current, dispatch)
        identity = (active_journal[0], dispatch["event_id"])
        if identity in target:
            phase_worlds[identity[0]] = actual.copy_actual_world_without_observers(current)
        return result

    setattr(cls, "execute", observed_execute)
    story.run_queued_inline_event_immediate = observed_immediate
    try:
        story.run_native_route(2, world=world, evidence={"legacy_events": legacy, "roots": roots})
    finally:
        story.run_queued_inline_event_immediate = original_immediate
        if own_execute is None:
            delattr(cls, "execute")
        else:
            setattr(cls, "execute", own_execute)
    expected_arcs = {row["arc"]["slug"] for row in _all_bindings()
                     if row["candidate"]["kind"] == "notice"}
    captured_arcs = {row["arc"]["slug"] for row in _all_bindings()
                     if row["candidate"]["kind"] == "notice"
                     and row["branch"]["journal"] in phase_worlds}
    if captured_arcs != expected_arcs:
        raise AssertionError(("natural native route did not visit every notice arc",
                              expected_arcs, captured_arcs))
    return phase_worlds


def _generated_sender(world, row):
    """Find the actual generated sender node for this exact event and queue."""
    script = world.journal_defs[row["branch"]["journal"]]
    pulse = actual._field(actual._field(script, "on_monthly_pulse", []), "effect", [])
    queue = "var:" + row["candidate"]["queue"]
    value = str(row["candidate"]["value"])
    found = []
    for node in pulse:
        key, op, body = node
        if key not in ("if", "else_if") or not isinstance(body, list):
            continue
        event_ids = [v for k, _, v in _walk(body) if k == "id"]
        queue_tests = [(k, o, v) for k, o, v in _walk(body)
                       if k == queue and o == "=" and str(v) == value]
        if row["branch"]["event"] in event_ids and queue_tests:
            found.append(node)
    if len(found) != 1:
        raise AssertionError(("generated sender must uniquely bind exact JHG source row", row["id"], found))
    return found[0]


def _invoke_callsite(testcase, phase_world, row, body_first=False, notice_case=None):
    """Execute one actual generated caller in a labelled isolated callsite fixture."""
    world = actual.copy_actual_world_without_observers(phase_world)
    state = world.countries[TAG]
    candidate = row["candidate"]
    branch = row["branch"]
    # This is an explicit isolated source-callsite queue fixture descended
    # from an actually admitted route phase. No positive token, proof, receipt,
    # reservation, callback, or completion field is planted here.
    testcase.assertNotIn(PREFIX + "_reservation", state)
    phase = next(p for p in row["arc"]["inline_delivery_adapter"]["live_phases"]
                 if p["journal"] == branch["journal"])
    testcase.assertEqual(state.get(phase["live_witness"]), 1)
    testcase.assertTrue(world.journal_is_active(TAG, branch["journal"]))
    world.advance_days(91)
    testcase.assertNotIn(COOLDOWN, world.days_until_expiry[TAG],
                         "the shared 90-day cooldown must expire through the native clock")
    queue = candidate["queue"]
    stem = _native_notice_stem(queue)
    siblings = (stem + "_pending_event", stem + "_notice_pending_event")
    for sibling in _JHG_QUEUE_NAMES:
        state.pop(sibling, None)
    notice_inputs = None
    notice_oracle = None
    if notice_case is not None:
        pre36, delivery36, marker = notice_case
        pre_name = stem + "_36_notice"
        delivery12_name = stem + "_notice_delivery_12"
        delivery36_name = stem + "_notice_delivery_36"
        if pre36 is None: state.pop(pre_name, None)
        else: state[pre_name] = pre36
        state.pop(delivery12_name, None)
        if delivery36 is None: state.pop(delivery36_name, None)
        else: state[delivery36_name] = delivery36
        target_marker = (stem + "_36_notice_delivered"
                         if pre36 is not None or delivery36 is not None
                         else stem + "_12_notice_delivered")
        marker12_name = stem + "_12_notice_delivered"
        marker36_name = stem + "_36_notice_delivered"
        state.pop(marker12_name, None); state.pop(marker36_name, None)
        if marker is None: state.pop(target_marker, None)
        else: state[target_marker] = marker
        notice_inputs = (pre_name, pre36, delivery12_name, None,
                         delivery36_name, delivery36, target_marker, marker)
        written_delivery = delivery36_name if pre36 is not None else delivery12_name
        untouched_delivery = delivery12_name if pre36 is not None else delivery36_name
        untouched_value = None if pre36 is not None else delivery36
        notice_oracle = (pre_name, pre36, written_delivery, untouched_delivery,
                         untouched_value, target_marker)
    state[queue] = candidate["value"]
    if notice_inputs is not None:
        pre_name, pre36, delivery12_name, delivery12, delivery_name, delivery36, marker_name, marker = notice_inputs
        for key, value in ((pre_name, pre36), (delivery12_name, delivery12),
                           (delivery_name, delivery36), (marker_name, marker)):
            if value is None: testcase.assertNotIn(key, state)
            else: testcase.assertEqual(state.get(key), value, (row["id"], key))
    testcase.assertEqual(state.get(queue), candidate["value"])
    testcase.assertNotIn(siblings[1] if queue == siblings[0] else siblings[0], state)

    sender = _generated_sender(world, row)
    sender_body = sender[2]
    limit = actual._field(sender_body, "limit", [])
    dispatches = []
    append_snapshots = []
    ack_rows = []

    def before_ack(current, name, tag):
        ack_rows.append({"boundary": "before_ack", "name": name,
                         "snapshot": _snapshot(current),
                         "private": copy.deepcopy(current.countries[tag])})

    def after_ack(current, name, tag):
        ack_rows.append({"boundary": "after_ack", "name": name,
                         "snapshot": _snapshot(current),
                         "private": copy.deepcopy(current.countries[tag])})

    def on_append(current, dispatch):
        dispatches.append(copy.deepcopy(dispatch))
        append_snapshots.append(copy.deepcopy(current.countries[TAG]))
        if body_first:
            actual.run_queued_inline_event_immediate(current, dispatch)

    prepared_runs = []
    with actual.observe_actual_effect_runs(world,
            lambda _w, name, _tag: prepared_runs.append(name)):
      with actual.observe_actual_dispatch_append(world, on_append):
        with actual.observe_actual_owned_ack(world, before_ack, after=after_ack):
            # Run the real scheduler prelude after declared native queue setup.
            # The target arc is now legitimately eligible even when its source
            # phase checkpoint had already served it in the prior round.
            world.run(PREFIX + "_prepare", TAG)
            testcase.assertIn(PREFIX + "_prepare", prepared_runs)
            turn = world.triggers[f"{PREFIX}_turn_{row['id']}"]
            testcase.assertTrue(world.conditions(turn, TAG),
                                (row["id"], "actual fair-scheduler turn is eligible after prepare"))
            testcase.assertTrue(world.conditions(limit, TAG),
                                (row["id"], "exact generated source branch limit is true after prepare"))
            # This explicitly named isolated-callsite unit executes the exact
            # bound branch. Running monthly_review first would mutate some
            # declared later-phase notice inputs before their native callsite.
            world.execute([_standalone_branch(sender)], TAG)
            testcase.assertEqual(len(dispatches), 1,
                                 (row["id"], "actual source trigger_event append count"))
            dispatch = dispatches[0]
            testcase.assertEqual(dispatch["event_id"], branch["event"])
            ident = row["id"]
            epoch = dispatch["scope_context"].get(PREFIX + "_dispatch_epoch")
            testcase.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"), ident)
            testcase.assertIsInstance(epoch, (int, float)); testcase.assertNotIsInstance(epoch, bool)
            testcase.assertGreater(epoch, 0)
            append_state = append_snapshots[0]
            testcase.assertEqual(append_state.get(PREFIX + "_reservation"), ident)
            testcase.assertEqual(append_state.get(PREFIX + "_reservation_epoch"), epoch)
            testcase.assertEqual(append_state.get(queue), candidate["value"])
            testcase.assertNotIn(f"{PREFIX}_body_completed_{ident}", append_state)
            if not body_first:
                testcase.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
                testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
                testcase.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)
                testcase.assertNotIn(PREFIX + "_callback_" + str(ident), state)
                testcase.assertEqual(ack_rows, [])
                actual.run_queued_inline_event_immediate(world, dispatch)
            else:
                testcase.assertEqual(len(ack_rows), 2,
                                     "body-first body wake must wait; sender continuation then reaches ACK")
                testcase.assertEqual(ack_rows[0]["name"], f"{PREFIX}_ack_{ident}")
                testcase.assertEqual(ack_rows[0]["private"].get(f"{PREFIX}_body_completed_{ident}"), 1)
                testcase.assertEqual(ack_rows[0]["private"].get(f"{PREFIX}_sender_completed_{ident}"), 1)
                testcase.assertEqual(ack_rows[0]["snapshot"]["days_until_expiry"].get(COOLDOWN), 90)
                testcase.assertIn(queue, ack_rows[0]["snapshot"]["variables"])
                testcase.assertEqual(ack_rows[0]["private"].get(PREFIX + "_reservation"), ident)
            testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
            testcase.assertEqual(state.get(f"{PREFIX}_body_completed_{ident}"), 1)
            testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
            testcase.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
            testcase.assertEqual(state.get(f"{PREFIX}_callback_{ident}"), 1)
            testcase.assertNotIn(PREFIX + "_reservation", state)
            testcase.assertNotIn(queue, state)
    if notice_oracle is not None:
        pre_name, pre36, written_delivery, untouched_delivery, untouched_value, marker_name = notice_oracle
        before = ack_rows[0]["snapshot"]["variables"]
        after = ack_rows[1]["snapshot"]["variables"]
        for native in (before, after):
            testcase.assertEqual(native.get(stem + "_notice_delivery_active"), 1)
            testcase.assertEqual(_present_value(native, written_delivery), (True, 1))
            testcase.assertEqual(_present_value(native, untouched_delivery),
                                 (untouched_value is not None, untouched_value))
            testcase.assertEqual(_present_value(native, marker_name), (True, 1))
            testcase.assertEqual(_present_value(native, pre_name), (pre36 is not None, pre36))
        testcase.assertIn(queue, before)
        testcase.assertNotIn(queue, after)
    native_expected = _native_fragment_outcome(testcase, phase_world, row,
                                               notice_case=notice_case)
    testcase.assertEqual(ack_rows[1]["snapshot"], native_expected,
                         (row["id"], "complete generated native post-ACK state equals same-input raw source P/R/immediate"))
    testcase.assertEqual([entry["boundary"] for entry in ack_rows], ["before_ack", "after_ack"])
    return world, dispatch, epoch, ack_rows


class JhgInlineProvenance(unittest.TestCase):
    def test_native_world_copy_drops_observers_and_rebinds_run_to_copy(self):
        """Temporary hooks cannot leak through a copied source-interpreter world."""
        world = actual.source_scope_model_control_world()
        observer = lambda *_: None
        after = lambda *_: None
        effect_observer = lambda *_: None
        world._dispatch_append_observer = observer
        world._owned_ack_observer = observer
        world._owned_ack_after_observer = after
        world._effect_run_observer = effect_observer
        parser = __import__("tests.clausewitz_harness", fromlist=["parse"]).parse
        clones = []
        source_dispatch = []
        def checkpoint(current, dispatch):
            source_dispatch.append(copy.deepcopy(dispatch))
            clones.append(actual.copy_actual_world_without_observers(current))
        world._dispatch_append_observer = checkpoint
        with world.invocation({"source": 17.0}):
            world.execute(parser("trigger_event = { id = ywc_jhg.1000 }"), TAG)
            self.assertEqual(world.scope_context, {"source": 17.0})
        self.assertEqual(world.scope_context, {}, "source invocation restores its pre-call context")
        self.assertEqual(len(clones), 1)
        clone = clones[0]
        pending_events = copy.deepcopy(list(world.events))
        frozen_contexts = copy.deepcopy(world.dispatch_contexts)
        self.assertIsNot(clone.countries, world.countries)
        self.assertIsNot(clone.countries[TAG], world.countries[TAG])
        self.assertIsNone(clone._dispatch_append_observer)
        self.assertIsNone(clone._owned_ack_observer)
        self.assertIsNone(clone._owned_ack_after_observer)
        self.assertIsNone(clone._effect_run_observer)
        self.assertIs(clone.run.__self__, clone,
                      "the class-level source runner binds to the clone, never an original-world closure")
        self.assertEqual(list(clone.events), pending_events)
        self.assertIs(clone.events.world, clone)
        self.assertEqual(clone.dispatch_contexts, frozen_contexts,
                         "copying pending events cannot replay overridden append or mint dispatches")
        self.assertEqual(len(clone.dispatch_contexts), len(world.dispatch_contexts))
        self.assertEqual(clone._execute_depth, 0)
        self.assertEqual(clone._explicit_context, 0)
        self.assertEqual(clone.scope_context, {})
        self.assertEqual(clone.scope_context_stack, [])
        self.assertEqual(source_dispatch[0]["scope_context"], {"source": 17.0})
        self.assertEqual(clone.dispatch_contexts[-1]["scope_context"], {"source": 17.0},
                         "queued delivery retains only its genuinely frozen invocation")
        fresh_dispatches = []
        with actual.observe_actual_dispatch_append(
                clone, lambda _w, dispatch: fresh_dispatches.append(copy.deepcopy(dispatch))):
            with clone.invocation({"fresh": 7.0}):
                clone.execute(parser("trigger_event = { id = ywc_jhg.1001 }"), TAG)
        self.assertEqual(fresh_dispatches[0]["scope_context"], {"fresh": 7.0})
        self.assertEqual(clone.scope_context, {})
        self.assertEqual(world.scope_context, {})
        with actual.observe_actual_owned_ack(clone, lambda *_: None):
            self.assertIs(clone.run.__self__, clone)
        self.assertIs(world._dispatch_append_observer, checkpoint)
        self.assertIs(world._owned_ack_observer, observer)
        self.assertIs(world._owned_ack_after_observer, after)
        self.assertIs(world._effect_run_observer, effect_observer)

    def test_native_queue_suffix_and_notice_oracle_are_source_independent(self):
        """The suffix utility and native 12/36 notice oracle work before adapter support."""
        stems = {
            "ywc_jhg_court": "v03_jhg_court_assembly",
            "ywc_jhg_convoy": "v03_jhg_convoy_capacity",
            "ywc_jhg_tribute": "v03_jhg_tribute_autonomy",
        }
        for row in _all_bindings():
            if row["candidate"]["kind"] != "notice":
                continue
            queue = row["candidate"]["queue"]
            stem = _native_notice_stem(queue)
            self.assertEqual(stem, next(key for key in stems if queue.startswith(key)))
            self.assertEqual(queue, stem + "_notice_pending_event")
        for stem in stems:
            self.assertEqual(_native_notice_stem(stem + "_pending_event"), stem)
        result = run_native_route(2)
        delivered12 = [row for row in result["ledger"]
                       if (row.get("notice_state") or {}).get("12_notice_delivered") == 1]
        delivered36 = [row for row in result["ledger"]
                       if (row.get("notice_state") or {}).get("36_notice_delivered") == 1]
        self.assertTrue(delivered12)
        self.assertTrue(delivered36)

    def test_native_exact_notice_branch_oracle_covers_all_six_site_contexts(self):
        """The raw exact branch preserves all P/R presence semantics without monthly review."""
        values = (None, 0, 1, 7)
        rows = [row for row in _all_bindings() if row["candidate"]["kind"] == "notice"]
        phases = _native_notice_phase_worlds()
        for row in rows:
            queue = row["candidate"]["queue"]
            stem = _native_notice_stem(queue)
            pre36_name = stem + "_36_notice"
            delivery12 = stem + "_notice_delivery_12"
            delivery36 = stem + "_notice_delivery_36"
            marker12 = stem + "_12_notice_delivered"
            marker36 = stem + "_36_notice_delivered"
            for pre36 in values:
                for stale36 in values:
                    for old_marker in values:
                        with self.subTest(site=row["id"], pre36=pre36,
                                          stale36=stale36, marker=old_marker):
                            outcome = _native_fragment_outcome(
                                self, phases.get(row["branch"]["journal"])
                                or next(phases[journal] for journal in phases
                                        if any(item["arc"]["slug"] == row["arc"]["slug"]
                                               and item["branch"]["journal"] == journal
                                               for item in rows)), row,
                                notice_case=(pre36, stale36, old_marker))
                            native = outcome["variables"]
                            writes36 = pre36 is not None
                            marker_is36 = pre36 is not None or stale36 is not None
                            self.assertNotIn(queue, native)
                            self.assertEqual(_present_value(native, pre36_name),
                                             (pre36 is not None, pre36))
                            self.assertEqual(native.get(stem + "_notice_delivery_active"), 1)
                            self.assertEqual(_present_value(native,
                                delivery36 if writes36 else delivery12), (True, 1))
                            untouched_name = delivery12 if writes36 else delivery36
                            untouched_value = None if writes36 else stale36
                            self.assertEqual(_present_value(native, untouched_name),
                                             (untouched_value is not None, untouched_value))
                            self.assertEqual(_present_value(native,
                                marker36 if marker_is36 else marker12), (True, 1))
                            self.assertEqual(_present_value(native,
                                marker12 if marker_is36 else marker36), (False, None))

    def test_dispatch_observer_payload_is_independent_and_invocation_restores_on_exception(self):
        """Observer mutation/failure cannot corrupt the source-captured context."""
        world = actual.source_scope_model_control_world()
        parser = __import__("tests.clausewitz_harness", fromlist=["parse"]).parse
        source_context = {"owner": 41.0}
        caught = []
        def mutate_and_raise(_world, dispatch):
            dispatch["scope_context"]["owner"] = 999.0
            dispatch["scope_context"]["observer_only"] = True
            caught.append(dispatch)
            raise RuntimeError("observer fault after real append")
        with actual.observe_actual_dispatch_append(world, mutate_and_raise):
            with world.invocation(source_context):
                with self.assertRaisesRegex(RuntimeError, "observer fault"):
                    world.execute(parser("trigger_event = { id = ywc_jhg.1000 }"), TAG)
                self.assertEqual(world.scope_context, source_context)
        self.assertEqual(world.dispatch_contexts[-1]["scope_context"], source_context)
        self.assertEqual(caught[0]["scope_context"]["owner"], 999.0)
        self.assertNotIn("observer_only", world.dispatch_contexts[-1]["scope_context"])
        self.assertIsNone(world._dispatch_append_observer)

    def test_authored_binding_inventory_is_complete_and_same_event_candidates_stay_distinct(self):
        rows = _all_bindings()
        self.assertEqual(len(rows), 58)
        self.assertEqual(sum(row["candidate"]["kind"] == "normal" for row in rows), 52)
        self.assertEqual(sum(row["candidate"]["kind"] == "notice" for row in rows), 6)
        self.assertEqual([row["id"] for row in rows], list(range(1, 59)))
        for event_id in {row["branch"]["event"] for row in rows}:
            same = [row for row in rows if row["branch"]["event"] == event_id]
            # Event ids intentionally recur across JEs. The catalog identity
            # is the source row (journal + branch index + candidate), not the
            # event id alone; shared native queues remain legal source facts.
            self.assertEqual(len({(row["branch"]["journal"], row["branch"]["branch_index"],
                                   row["id"], row["candidate"]["queue"])
                                  for row in same}), len(same),
                             (event_id, "repeated event identity must retain exact source-row ownership"))
        notice_rows = [row for row in rows if row["candidate"]["kind"] == "notice"]
        self.assertEqual({row["branch"]["journal"] for row in notice_rows},
                         {phase["journal"] for arc in binding._v2_catalog_from_formal_jhg_source()["arcs"]
                          for phase in arc["inline_delivery_adapter"]["live_phases"]})

    def test_real_source_first_and_conceptual_body_first_join_use_actual_commands(self):
        """Both labelled schedules use real append, source tail, body, receipt, and ACK."""
        actual.assert_inline_supported(self)
        for body_first in (False, True):
            with self.subTest(schedule="body-first" if body_first else "source-first"):
                world, evidence, dispatch, row, reservation, epoch = _one_real_dispatch(self, body_first)
                state = world.countries[TAG]
                ident = reservation
                body_receipt = f"{PREFIX}_body_completed_{ident}"
                sender_receipt = f"{PREFIX}_sender_completed_{ident}"
                self.assertIn(f"{PREFIX}_sender_return_{ident}", world._b2_effect_runs,
                              "the real source continuation executes its owned sender wake")
                if body_first:
                    self.assertEqual(state.get(body_receipt), 1)
                    self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
                    self.assertEqual(state.get(sender_receipt), 1,
                                     "real source continuation joins after the body-first observer returns")
                    pause = world._b2_body_pause_state
                    self.assertNotIn(sender_receipt, pause,
                                     "body wake is independently held before source continuation")
                    self.assertEqual(pause.get(body_receipt), 1)
                    self.assertEqual(pause.get(PREFIX + "_reservation"), ident)
                else:
                    self.assertEqual(state.get(sender_receipt), 1)
                    self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
                    self.assertNotIn(body_receipt, state,
                                     "queued source-first state has no body proof before dispatch execution")
                    before = _snapshot(world)
                    body_effects = []
                    with actual.observe_actual_effect_runs(
                        world, lambda _w, name, _tag: body_effects.append(name)):
                        actual.run_queued_inline_event_immediate(world, dispatch)
                    self.assertIn(f"{PREFIX}_body_return_{ident}", body_effects,
                                  "the real queued body executes its separately owned wake")
                    self.assertEqual(state.get(body_receipt), 1)
                    self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
                    self.assertNotEqual(_snapshot(world), before,
                                        "actual native immediate and ACK must change the native snapshot")
                self.assertEqual(state.get(f"{PREFIX}_callback_{ident}"), 1)
                self.assertEqual(state.get(f"{PREFIX}_callback_candidate_{ident}"), ident)
                self.assertEqual(state.get(f"{PREFIX}_callback_epoch_{ident}"), epoch)
                self.assertEqual(state.get(f"{PREFIX}_callback_queue_{ident}"), row["candidate"]["value"])
                self.assertNotIn(PREFIX + "_reservation", state,
                                 "successful join consumes the private reservation exactly once")
                self.assertNotIn(row["candidate"]["queue"], state,
                                 "successful ACK removes the selected native queue exactly once")

    def test_natural_story_uses_actual_notices_and_real_cooldown_expiry(self):
        """Full authored native story is an independent positive source control."""
        # This is the real native source journey, run without invoking the
        # unavailable public JHG adapter gate. It seeds no queue, notice,
        # receipt, outcome, or cooldown state.
        result = run_native_route(2)
        _assert_route2_contract(self, result)
        acknowledgements = [row for row in result["ledger"]
                            if row["option"] == "acknowledge_12_notice"]
        long_notices = [row for row in result["ledger"]
                        if (row.get("notice_state") or {}).get("36_notice_delivered") == 1]
        self.assertTrue(any((row.get("notice_state") or {}).get("12_notice_delivered") == 1
                            for row in acknowledgements), "natural source reaches an authored 12-month notice")
        self.assertTrue(any((row.get("notice_state") or {}).get("36_notice_delivered") == 1
                            and (row.get("notice_state") or {}).get("notice_delivery_36") == 1
                            for row in long_notices), "natural source reaches an authored 36-month notice")
        self.assertTrue(any(row.get("days_remaining") == 90 for row in result["cooldown_trace"]))
        self.assertTrue(any(row.get("expired_naturally") for row in result["cooldown_trace"]))

    def test_all_58_callsite_contract_matrix_keeps_both_schedules_and_site_identity(self):
        """Run all 58 real generated callers in both explicitly labelled schedules."""
        phases = _phase_worlds(self)
        rows = _all_bindings()
        self.assertEqual(len(rows), 58)
        for row in rows:
            ident = row["id"]
            branch = row["branch"]
            for body_first in (False, True):
                with self.subTest(candidate=ident, event=branch["event"],
                                  schedule="body-first" if body_first else "source-first"):
                    result = _invoke_callsite(self, phases[branch["journal"]], row, body_first)
                    self.assertEqual(result[1]["event_id"], branch["event"])
        actual.assert_inline_supported(self)

    def test_six_notice_sites_cross_presence_value_marker_matrix_in_both_orders(self):
        """Each actual notice callsite preserves R2 presence-based source decisions."""
        phases = _phase_worlds(self)
        notices = [row for row in _all_bindings() if row["candidate"]["kind"] == "notice"]
        self.assertEqual(len(notices), 6)
        values = (None, 0, 1, 7)
        for row in notices:
            for pre36 in values:
                for delivery36 in values:
                    target = "36" if pre36 is not None or delivery36 is not None else "12"
                    for marker in values:
                        for body_first in (False, True):
                            with self.subTest(site=row["id"], pre36=pre36,
                                              delivery36=delivery36, marker=marker,
                                              schedule="body-first" if body_first else "source-first"):
                                world, dispatch, epoch, ack_rows = _invoke_callsite(
                                    self, phases[row["branch"]["journal"]], row, body_first,
                                    notice_case=(pre36, delivery36, marker))
                                stem = row["candidate"]["queue"].removesuffix("_notice_pending_event")
                                state = world.countries[TAG]
                                self.assertEqual(state.get(stem + "_notice_delivery_active"), 1)
                                written_subtype = "36" if pre36 is not None else "12"
                                self.assertEqual(state.get(stem + "_notice_delivery_" + written_subtype), 1)
                                untouched_subtype = "12" if pre36 is not None else "36"
                                untouched_value = None if pre36 is not None else delivery36
                                self.assertEqual(_present_value(state, stem + "_notice_delivery_" + untouched_subtype),
                                                 (untouched_value is not None, untouched_value))
                                self.assertEqual(state.get(stem + "_" + target + "_notice_delivered"), 1)
                                self.assertEqual(dispatch["scope_context"].get(
                                    PREFIX + "_dispatch_epoch"), epoch)
                                self.assertEqual(ack_rows[0]["snapshot"]["variables"].get(COOLDOWN), 1)
                                self.assertEqual(ack_rows[1]["snapshot"]["variables"].get(COOLDOWN), 1)
        actual.assert_inline_supported(self)


if __name__ == "__main__":
    unittest.main()

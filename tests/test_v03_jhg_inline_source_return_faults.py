"""Faults at the true source-return boundary must not become trusted R(P)."""

import copy
import unittest

from tests import test_v03_jhg_inline_actual_source as actual
from tests.test_v03_jhg_inline_provenance import (
    COOLDOWN,
    PREFIX,
    TAG,
    _JHG_QUEUE_NAMES,
    _all_bindings,
    _generated_sender,
    _invoke_callsite,
    _native_notice_stem,
    _phase_worlds,
    _standalone_branch,
)
from tests.test_v03_jhg_inline_queue_snapshots import _complete_state_snapshot


def _faulted_source_return(testcase, row, phase_world, *, body_first, notice_case=None):
    world = actual.copy_actual_world_without_observers(phase_world)
    world.advance_days(91)
    state = world.countries[TAG]
    for queue_name in _JHG_QUEUE_NAMES:
        state.pop(queue_name, None)
    queue = row["candidate"]["queue"]
    state[queue] = row["candidate"]["value"]
    sibling = "ywc_jhg_court_pending_event"
    state[sibling] = 1000

    if notice_case is not None:
        pre36, delivery36, marker = notice_case
        stem = _native_notice_stem(queue)
        for name in (stem + "_36_notice", stem + "_notice_delivery_12",
                     stem + "_notice_delivery_36", stem + "_12_notice_delivered",
                     stem + "_36_notice_delivered"):
            state.pop(name, None)
        if pre36 is not None:
            state[stem + "_36_notice"] = pre36
        if delivery36 is not None:
            state[stem + "_notice_delivery_36"] = delivery36
        target = stem + ("_36_notice_delivered" if pre36 is not None or delivery36 is not None
                         else "_12_notice_delivered")
        if marker is not None:
            state[target] = marker

    sender = _generated_sender(world, row)
    callsite = sender[2]
    dispatches = []
    returned = []

    def on_append(current, dispatch):
        dispatches.append(copy.deepcopy(dispatch))
        if body_first:
            actual.run_queued_inline_event_immediate(current, dispatch)

    def before_effect(current, name, tag):
        expected = f"{PREFIX}_sender_return_{row['id']}"
        if name == expected and not returned:
            current.countries[tag][sibling] = 777
            returned.append(_complete_state_snapshot(current))

    with actual.observe_actual_effect_runs(world, before_effect):
        with actual.observe_actual_dispatch_append(world, on_append):
            world.run(PREFIX + "_prepare", TAG)
            limit = actual._field(callsite, "limit", [])
            testcase.assertTrue(world.conditions(limit, TAG), (row["id"], "authored source branch is live"))
            world.execute([_standalone_branch(sender)], TAG)

    testcase.assertEqual(len(dispatches), 1)
    testcase.assertEqual(len(returned), 1, (row["id"], "fault injected at exact sender-return entry"))
    dispatch = dispatches[0]
    testcase.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"), row["id"])
    fault_time = _complete_state_snapshot(world)
    testcase.assertEqual(fault_time, returned[0], "sender-return guard must preserve its fault-time state")
    testcase.assertEqual(state.get(sibling), 777)
    testcase.assertEqual(state.get(queue), row["candidate"]["value"])
    testcase.assertEqual(state.get(PREFIX + "_reservation"), row["id"])
    testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_{row['id']}"), None)

    if not body_first:
        with testcase.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)
        testcase.assertEqual(_complete_state_snapshot(world), fault_time)
        testcase.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
        testcase.assertNotIn(f"{PREFIX}_body_completed_{row['id']}", state)
    else:
        testcase.assertEqual(state.get(f"{PREFIX}_body_completed_{row['id']}"), 1)
        testcase.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        testcase.assertEqual(_complete_state_snapshot(world), fault_time)
    return world


def _faulted_postmarker_reset_to_p(testcase, row, phase_world, *, body_first,
                                  delivery36, boundary_fault=None):
    world = actual.copy_actual_world_without_observers(phase_world)
    world.advance_days(91)
    state = world.countries[TAG]
    for queue_name in _JHG_QUEUE_NAMES:
        state.pop(queue_name, None)
    queue = row["candidate"]["queue"]
    state[queue] = row["candidate"]["value"]
    stem = _native_notice_stem(queue)
    for name in (stem + "_36_notice", stem + "_notice_delivery_12",
                 stem + "_notice_delivery_36", stem + "_12_notice_delivered",
                 stem + "_36_notice_delivered"):
        state.pop(name, None)
    if delivery36 is not None:
        state[stem + "_notice_delivery_36"] = delivery36
    marker = stem + ("_12_notice_delivered" if delivery36 is None
                     else "_36_notice_delivered")
    state[marker] = 7

    sender = _generated_sender(world, row)
    dispatches = []
    sender_entry = []

    def on_append(current, dispatch):
        dispatches.append(copy.deepcopy(dispatch))
        if body_first:
            actual.run_queued_inline_event_immediate(current, dispatch)

    def before_effect(current, name, tag):
        if name == f"{PREFIX}_sender_return_{row['id']}" and not sender_entry:
            testcase.assertEqual(current.countries[tag].get(marker), 1)
            testcase.assertEqual(
                current.countries[tag].get(f"{PREFIX}_source_boundary_{row['id']}"),
                row["id"],
                "native source postfragment must set the owner-bound reached-boundary fact",
            )
            testcase.assertEqual(
                current.countries[tag].get(f"{PREFIX}_source_boundary_epoch_{row['id']}"),
                current.countries[tag].get(f"{PREFIX}_reservation_epoch"),
            )
            current.countries[tag][marker] = 7
            if boundary_fault == "missing_epoch":
                current.countries[tag].pop(f"{PREFIX}_source_boundary_epoch_{row['id']}", None)
            elif boundary_fault == "zero_candidate":
                current.countries[tag][f"{PREFIX}_source_boundary_{row['id']}"] = 0
            elif boundary_fault == "wrong_epoch":
                current.countries[tag][f"{PREFIX}_source_boundary_epoch_{row['id']}"] += 1
            sender_entry.append(_complete_state_snapshot(current))

    with actual.observe_actual_effect_runs(world, before_effect):
        with actual.observe_actual_dispatch_append(world, on_append):
            world.run(PREFIX + "_prepare", TAG)
            callsite = sender[2]
            testcase.assertTrue(world.conditions(actual._field(callsite, "limit", []), TAG))
            world.execute([_standalone_branch(sender)], TAG)

    testcase.assertEqual(len(dispatches), 1)
    testcase.assertEqual(len(sender_entry), 1)
    dispatch = dispatches[0]
    testcase.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"), row["id"])
    fault_time = sender_entry[0]
    testcase.assertEqual(_complete_state_snapshot(world), fault_time,
                         "rejected sender return must preserve its complete fault-time state")
    testcase.assertEqual(state.get(marker), 7)
    expected_boundary = 0 if boundary_fault == "zero_candidate" else row["id"]
    testcase.assertEqual(state.get(f"{PREFIX}_source_boundary_{row['id']}"), expected_boundary)
    if boundary_fault == "missing_epoch":
        testcase.assertNotIn(f"{PREFIX}_source_boundary_epoch_{row['id']}", state)
    else:
        expected_epoch = state.get(f"{PREFIX}_reservation_epoch")
        if boundary_fault == "wrong_epoch":
            expected_epoch += 1
        testcase.assertEqual(state.get(f"{PREFIX}_source_boundary_epoch_{row['id']}"),
                             expected_epoch)
    testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_{row['id']}"), None)

    if body_first:
        testcase.assertEqual(state.get(f"{PREFIX}_body_completed_{row['id']}"), 1)
        testcase.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        testcase.assertEqual(state.get(f"{PREFIX}_callback_{row['id']}"), 1)
    else:
        with testcase.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)
        testcase.assertEqual(_complete_state_snapshot(world), fault_time,
                             "once source reached its rejected return boundary, body cannot use P fallback")
        testcase.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
        testcase.assertNotIn(f"{PREFIX}_body_completed_{row['id']}", state)


def _queue_faulted_source_return_then_native_recovery(testcase, row, phase_world):
    world = actual.copy_actual_world_without_observers(phase_world)
    world.advance_days(91)
    state = world.countries[TAG]
    for queue_name in _JHG_QUEUE_NAMES:
        state.pop(queue_name, None)
    queue = row["candidate"]["queue"]
    authored_queue = row["candidate"]["value"]
    state[queue] = authored_queue
    sender = _generated_sender(world, row)
    dispatches = []
    return_fault_states = []
    boundary_at_return = []

    def on_append(current, dispatch):
        dispatches.append(copy.deepcopy(dispatch))
        current.countries[TAG][queue] = 0

    def before_effect(current, name, tag):
        if name == f"{PREFIX}_sender_return_{row['id']}":
            testcase.assertEqual(current.countries[tag].get(queue), 0)
            boundary_at_return.append((
                current.countries[tag].get(f"{PREFIX}_source_boundary_{row['id']}"),
                current.countries[tag].get(f"{PREFIX}_source_boundary_epoch_{row['id']}"),
                current.countries[tag].get(f"{PREFIX}_reservation_epoch"),
            ))
            return_fault_states.append(_complete_state_snapshot(current))

    world.run(PREFIX + "_prepare", TAG)
    callsite = sender[2]
    testcase.assertTrue(world.conditions(actual._field(callsite, "limit", []), TAG))
    with actual.observe_actual_effect_runs(world, before_effect):
        with actual.observe_actual_dispatch_append(world, on_append):
            world.execute([_standalone_branch(sender)], TAG)

    testcase.assertEqual(len(dispatches), 1)
    testcase.assertEqual(len(return_fault_states), 1)
    dispatch = dispatches[0]
    testcase.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"),
                         row["id"])
    testcase.assertGreater(dispatch["scope_context"].get(PREFIX + "_dispatch_epoch"), 0)
    state = world.countries[TAG]
    fault_time = return_fault_states[0]
    testcase.assertEqual(state.get(queue), 0)
    testcase.assertEqual(state.get(f"{PREFIX}_sender_completed_{row['id']}"), None)
    testcase.assertEqual(_complete_state_snapshot(world), fault_time,
                         "rejected source receipt must preserve complete queue-fault state")

    private_before_recovery = {key: value for key, value in state.items()
                               if key.startswith(PREFIX)}
    state[queue] = authored_queue
    testcase.assertEqual(
        {key: value for key, value in state.items() if key.startswith(PREFIX)},
        private_before_recovery,
        "native-only queue recovery cannot manufacture or alter private ownership facts",
    )
    recovered_before_body = _complete_state_snapshot(world)

    with testcase.assertRaises(ValueError):
        actual.run_queued_inline_event_immediate(world, dispatch)
    testcase.assertEqual(_complete_state_snapshot(world), recovered_before_body,
                         "blocked original event must preserve recovered native/private state")
    testcase.assertEqual(boundary_at_return, [(
        row["id"], state.get(f"{PREFIX}_reservation_epoch"),
        state.get(f"{PREFIX}_reservation_epoch"),
    )], "real source must record its boundary while selected native queue is invalid")


class JhgInlineSourceReturnFaults(unittest.TestCase):
    def test_pre_sender_return_sibling_corruption_fails_closed_in_both_schedules(self):
        actual.assert_inline_supported(self)
        rows = _all_bindings()
        normal = rows[19]  # the concrete court_pending sibling observation
        notice = next(row for row in rows if row["candidate"]["kind"] == "notice")
        phases = _phase_worlds(self)
        contexts = [(normal, phases[normal["branch"]["journal"]], None)]
        notice_contexts = (
            (None, None, None),
            (None, 0, 0),
            (None, 1, 1),
            (None, 7, 7),
            (1, None, None),
            (1, 0, 0),
            (1, 1, 1),
            (1, 7, 7),
        )
        contexts.extend((notice, phases[notice["branch"]["journal"]], case)
                        for case in notice_contexts)
        for row, phase_world, notice_case in contexts:
            for body_first in (False, True):
                with self.subTest(candidate=row["id"], notice_case=notice_case,
                                  schedule="body-first" if body_first else "source-first"):
                    _faulted_source_return(self, row, phase_world,
                                           body_first=body_first, notice_case=notice_case)

    def test_unfaulted_normal_and_presence_selected_notice_controls_still_join(self):
        actual.assert_inline_supported(self)
        rows = _all_bindings()
        normal = rows[19]
        notice = next(row for row in rows if row["candidate"]["kind"] == "notice")
        phases = _phase_worlds(self)
        for row, notice_case in ((normal, None), (notice, (None, 7, 7)),
                                 (notice, (1, 0, 0))):
            phase = phases[row["branch"]["journal"]]
            for body_first in (False, True):
                with self.subTest(candidate=row["id"], notice_case=notice_case,
                                  schedule="body-first" if body_first else "source-first"):
                    _invoke_callsite(self, phase, row, body_first=body_first,
                                     notice_case=notice_case)

    def test_rejected_postmarker_reset_to_p_never_falls_back_but_real_body_first_survives(self):
        actual.assert_inline_supported(self)
        notice = next(row for row in _all_bindings()
                      if row["candidate"]["kind"] == "notice")
        phase = _phase_worlds(self)[notice["branch"]["journal"]]
        for delivery36 in (None, 0, 7):
            for body_first in (False, True):
                with self.subTest(delivery36=delivery36,
                                  schedule="body-first" if body_first else "source-first"):
                    _faulted_postmarker_reset_to_p(self, notice, phase,
                                                   body_first=body_first,
                                                   delivery36=delivery36)
            for boundary_fault in ("missing_epoch", "zero_candidate", "wrong_epoch"):
                with self.subTest(delivery36=delivery36, schedule="source-first",
                                  boundary_fault=boundary_fault):
                    _faulted_postmarker_reset_to_p(self, notice, phase,
                                                   body_first=False,
                                                   delivery36=delivery36,
                                                   boundary_fault=boundary_fault)

    def test_real_source_boundary_survives_queue_fault_and_blocks_native_only_recovery(self):
        actual.assert_inline_supported(self)
        row = _all_bindings()[19]
        testcase_phase = _phase_worlds(self)[row["branch"]["journal"]]
        _queue_faulted_source_return_then_native_recovery(self, row, testcase_phase)


if __name__ == "__main__":
    unittest.main()

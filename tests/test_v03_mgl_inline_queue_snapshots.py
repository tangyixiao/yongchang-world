"""MGL inline selected/sibling queue snapshot and private cleanup contract.

Every test obtains its initial queue and reservation from a genuine authored
MGL monthly-pulse sender. Injected faults happen only after that positive
source candidate exists; a rejected path may clear private state but cannot
restore or clobber native MGL state.
"""
from __future__ import annotations

import copy
import unittest

from tests.test_v03_mgl_inline_provenance import (
    PREFIX, TAG, _actual_unconsumed_popup, _natural_blocked_notice,
    _outside_adapter, _field, _event,
)


def _candidate(testcase, kind):
    if kind == "normal":
        return _actual_unconsumed_popup(testcase)
    months = 18 if kind == "12" else 42
    return _natural_blocked_notice(testcase, kind, months)


def _sibling_queue(queue):
    if queue.endswith("_pending_event"):
        stem = queue.removesuffix("_pending_event")
        return (stem + "_blocked_12_notice_event", stem + "_blocked_36_notice_event")
    if queue.endswith("_blocked_12_notice_event"):
        stem = queue.removesuffix("_blocked_12_notice_event")
        return (stem + "_pending_event", stem + "_blocked_36_notice_event")
    if queue.endswith("_blocked_36_notice_event"):
        stem = queue.removesuffix("_blocked_36_notice_event")
        return (stem + "_pending_event", stem + "_blocked_12_notice_event")
    raise AssertionError(("unknown-native-mgl-queue-kind", queue))


class MglInlineQueueSnapshotRegression(unittest.TestCase):
    def test_selected_absent_zero_and_seven_reject_before_native_body(self):
        """Exact selected presence/value snapshot is required before native effects."""
        # A genuine unmodified full body is the positive control.
        world, evidence, event_id, row, reservation, epoch, queue = _actual_unconsumed_popup(self)
        self.assertEqual(len(evidence["root_admissions"]), 3)
        event = _event(world, event_id)
        state = world.countries[TAG]
        ack = []
        original_run = world.run
        def watch(name, tag=TAG):
            if name == f"{PREFIX}_ack_{reservation}" and tag == TAG:
                ack.append(copy.deepcopy(state))
            return original_run(name, tag)
        world.run = watch
        world.execute(_field(event, "immediate", []), TAG)
        self.assertEqual(len(ack), 1)
        self.assertEqual(ack[0].get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(ack[0].get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)

        for kind in ("normal", "12", "36"):
          for fault, value in (("absent", None), ("zero", 0), ("seven", 7)):
            with self.subTest(kind=kind, fault=fault):
                world, _evidence, event_id, row, reservation, _epoch, queue = _candidate(self, kind)
                state = world.countries[TAG]
                if fault == "absent":
                    state.pop(queue, None)
                else:
                    state[queue] = value
                native_before = _outside_adapter(state)
                body = _field(_event(world, event_id), "immediate", [])
                world.execute(body, TAG)
                self.assertEqual(_outside_adapter(state), native_before,
                                 "selected queue mismatch must block every native body write")
                self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                self.assertNotIn(f"{PREFIX}_callback_{reservation}", state)
                world.run(PREFIX + "_prepare", TAG)
                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(PREFIX + "_timer", state)
                self.assertEqual((queue in state, state.get(queue)),
                                 (fault != "absent", value),
                                 "cleanup cannot restore stale selected queue state")

    def test_sibling_absent_zero_and_seven_are_never_restored_or_clobbered(self):
        """Fresh sibling values survive ACK and cleanup exactly, including absence."""
        for kind in ("normal", "12", "36"):
          for fault, value in (("absent", None), ("zero", 0), ("seven", 7)):
            with self.subTest(kind=kind, fault=fault):
                world, _evidence, event_id, row, reservation, _epoch, queue = _candidate(self, kind)
                siblings = _sibling_queue(queue)
                state = world.countries[TAG]
                siblings_before = {}
                for sibling in siblings:
                    if fault == "absent":
                        state.pop(sibling, None)
                    else:
                        state[sibling] = value
                    siblings_before[sibling] = (sibling in state, copy.deepcopy(state.get(sibling)))
                world.execute(_field(_event(world, event_id), "immediate", []), TAG)
                for sibling, before in siblings_before.items():
                    self.assertEqual((sibling in state, state.get(sibling)), before,
                                     "full body / ACK must preserve both fresh sibling values")

    def test_unknown_ids_and_live_invalid_epoch_cleanup_are_private_only(self):
        """Unknown reservation 0/-1/999 and malformed live metadata cannot restore native queues."""
        for unknown in (0, -1, 999):
            for queue_shape in ("absent", "zero", "seven"):
                with self.subTest(reservation=unknown, queue=queue_shape):
                    world, _evidence, _event_id, _row, _reservation, _epoch, queue = _actual_unconsumed_popup(self)
                    state = world.countries[TAG]
                    if queue_shape == "absent":
                        state.pop(queue, None)
                    else:
                        state[queue] = 0 if queue_shape == "zero" else 7
                    native_before = _outside_adapter(state)
                    state[PREFIX + "_reservation"] = unknown
                    # Invalid epochs are deliberately varied even for unknown IDs.
                    state[PREFIX + "_reservation_epoch"] = {0: 0, -1: -1, 999: 1}[unknown]
                    world.run(PREFIX + "_prepare", TAG)
                    self.assertNotIn(PREFIX + "_reservation", state)
                    self.assertNotIn(PREFIX + "_timer", state)
                    self.assertEqual(_outside_adapter(state), native_before,
                                     "unknown cleanup may remove private fields only")
                    self.assertEqual((queue in state, state.get(queue)),
                                     (queue_shape != "absent",
                                      None if queue_shape == "absent" else
                                      0 if queue_shape == "zero" else 7))

    def test_known_live_invalid_metadata_is_released_without_native_rollback(self):
        """Real candidates fail closed on malformed epoch, timer, or phase witness."""
        from tests.test_v03_mgl_inline_provenance import _all_rows
        cases = ("epoch-absent", "epoch-zero", "epoch-negative", "epoch-mismatch",
                 "timer-absent", "phase-absent", "phase-zero")
        for bad in cases:
            with self.subTest(metadata=bad):
                world, _evidence, _event_id, row, reservation, epoch, queue = _actual_unconsumed_popup(self)
                state = world.countries[TAG]
                timer = PREFIX + "_timer"
                phase = next(p for p in row["arc"]["inline_delivery_adapter"]["live_phases"]
                             if p["journal"] == row["branch"]["journal"])["live_witness"]
                if bad == "epoch-absent": state.pop(PREFIX + "_reservation_epoch", None)
                elif bad == "epoch-zero": state[PREFIX + "_reservation_epoch"] = 0
                elif bad == "epoch-negative": state[PREFIX + "_reservation_epoch"] = -1
                elif bad == "epoch-mismatch": state[PREFIX + "_reservation_epoch"] = epoch + 1
                elif bad == "timer-absent": state.pop(timer, None); world.days_until_expiry[TAG].pop(timer, None)
                elif bad == "phase-absent": state.pop(phase, None)
                elif bad == "phase-zero": state[phase] = 0
                outside_before = _outside_adapter(state)
                self.assertFalse(world.condition((f"{PREFIX}_dispatch_{reservation}", "=", "yes"), TAG))
                world.run(PREFIX + "_prepare", TAG)
                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(timer, state)
                self.assertEqual(_outside_adapter(state), outside_before)
                self.assertEqual(state.get(queue), row["candidate"]["value"])

    def test_afterbody_ack_fault_cleanup_preserves_fresh_native_snapshot(self):
        """ACK faults occur after a real complete body and preserve fault-time native state."""
        for kind in ("normal", "12", "36"):
          for shape, value in (("absent", None), ("zero", 0), ("seven", 7)):
            with self.subTest(kind=kind, queue_shape=shape):
                world, _evidence, event_id, row, reservation, epoch, queue = _candidate(self, kind)
                state = world.countries[TAG]
                siblings = _sibling_queue(queue)
                phase = next(p for p in row["arc"]["inline_delivery_adapter"]["live_phases"]
                             if p["journal"] == row["branch"]["journal"])["live_witness"]
                original_run = world.run
                ack_boundaries = []
                fault_snapshot = []
                def fault_at_ack(name, tag=TAG):
                    if name == f"{PREFIX}_ack_{reservation}" and tag == TAG:
                        # The actual event wrapper must have completed the native
                        # body and minted the exact candidate proof before faulting.
                        self.assertEqual(state.get(f"{PREFIX}_body_completed_{reservation}"), 1)
                        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                        self.assertEqual(state.get(f"{PREFIX}_callback_{reservation}"), 1)
                        if event_id in {"ywc_mng.1005", "ywc_mng.1015", "ywc_mng.1025"}:
                            observation = {"ywc_mng.1005": "ywc_mgl_roads_observation_open",
                                          "ywc_mng.1015": "ywc_mgl_debt_observation_open",
                                          "ywc_mng.1025": "ywc_mgl_grain_observation_open"}[event_id]
                            self.assertEqual(state.get(observation), 1)
                        ack_boundaries.append(copy.deepcopy(state))
                        # Fault is injected only now, after full native immediate.
                        if shape == "absent": state.pop(queue, None)
                        else: state[queue] = value
                        for sibling in siblings:
                            if shape == "absent": state.pop(sibling, None)
                            else: state[sibling] = value
                        if shape == "zero": state[PREFIX + "_reservation_epoch"] = 0
                        elif shape == "seven":
                            state.pop(PREFIX + "_timer", None)
                            world.days_until_expiry[TAG].pop(PREFIX + "_timer", None)
                            state[phase] = 0
                        fault_snapshot.append(_outside_adapter(state))
                    return original_run(name, tag)
                world.run = fault_at_ack
                world.execute(_field(_event(world, event_id), "immediate", []), TAG)
                self.assertEqual(len(ack_boundaries), 1, "natural candidate completed body and reached ACK")
                self.assertEqual(_outside_adapter(state), fault_snapshot[0],
                                 "ACK rejection cannot roll back native values changed at its boundary")
                world.run(PREFIX + "_prepare", TAG)
                self.assertEqual(_outside_adapter(state), fault_snapshot[0],
                                 "private prepare cleanup cannot restore or clobber native state")
                self.assertEqual((queue in state, state.get(queue)), (shape != "absent", value))
                for sibling in siblings:
                    self.assertEqual((sibling in state, state.get(sibling)), (shape != "absent", value))

    def test_natural_expiry_clears_private_reservation_without_source_rollback(self):
        world, _evidence, _event_id, _row, _reservation, _epoch, _queue = _actual_unconsumed_popup(self)
        state = world.countries[TAG]
        timer = PREFIX + "_timer"
        self.assertIn(timer, state)
        world.advance_days(10000)
        native_after_own_clock = _outside_adapter(state)
        world.run(PREFIX + "_prepare", TAG)
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertNotIn(timer, state)
        self.assertEqual(_outside_adapter(state), native_after_own_clock)


if __name__ == "__main__":
    unittest.main()

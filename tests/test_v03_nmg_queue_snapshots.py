"""Permanent actual-source NMG queue presence/value snapshot regressions.

Every positive reservation comes from admitted authored NMG history and a
source-driven live-JE pulse. The only private-state changes below are explicit
negative fault injections at the documented queue/ACK/cleanup boundaries.
"""
import copy
import math
import unittest
from pathlib import Path

from tests.test_v03_nmg_transport_provenance import (
    ARC_ORDER,
    PREFIX,
    _event,
    _field,
    _natural_notice_world,
    _reservation,
    _start_real_popup,
    _candidate_kind,
)
from tools.v03_inline_delivery_adapter import _queue_snapshot_name


TAG = "NMG"
NORMAL_SLUG = ARC_ORDER[0]
NORMAL_EVENT = "ywc_nmg.1000"
SIBLING_QUEUE = "ywc_nmg_land_notice_pending"
BUSINESS_COOLDOWN = "ywc_v03_major_event_cooldown"
SERVED = f"{PREFIX}_served_1"
ROUND = f"{PREFIX}_round"

# This input list is deliberately formal: none points into PLANWS or scratch.
SOURCE_INPUTS = (
    "data/content/v03/countries/nmg.json",
    "tests/test_v03_nmg_actual_fairness.py",
    "tests/test_v03_nmg_transport_provenance.py",
    "tests/test_v03_nmg_foundation_lifecycle.py",
    "tools/v03_inline_delivery_adapter.py",
    "yongchang_world/common/history/countries/chi - china.txt",
    "yongchang_world/common/journal_entries/ywc_v03_country_nmg_journal.txt",
    "yongchang_world/events/ywc_v03_country_nmg_events.txt",
    "yongchang_world/common/scripted_effects/ywc_v03_delivery_nmg_effects.txt",
)


def _private_prefix(name):
    return name.startswith(PREFIX + "_")


def _native_state(state):
    """Capture actual source-owned NMG state, retaining presence as evidence."""
    return {
        key: copy.deepcopy(value)
        for key, value in state.items()
        if (key.startswith("ywc_nmg_") and not _private_prefix(key))
        or key == BUSINESS_COOLDOWN
    }


def _fixture_state(state):
    return {
        key: copy.deepcopy(value)
        for key, value in state.items()
        if not key.startswith("ywc_nmg_") and not _private_prefix(key)
        and key != BUSINESS_COOLDOWN
    }


def _real_normal():
    world, evidence, event_id, row, order = _start_real_popup(NORMAL_SLUG, kind="normal")
    if event_id != NORMAL_EVENT:
        raise AssertionError(("unexpected_normal_event", event_id))
    reservation, epoch, queue = _reservation(world, row, event_id)
    return world, evidence, event_id, row, order, reservation, epoch, queue


def _nmg_notice_body_fields(immediate, notice_kind):
    """Derive native notice ABI names from the event immediate being exercised."""
    writes = {"return": [], "last": [], "context": [], "delivered": []}
    due_removals = []

    def walk(nodes):
        for node in nodes:
            yield node
            if isinstance(node[2], list):
                yield from walk(node[2])

    due_suffix = f"_{notice_kind}_due"
    delivered_suffix = f"_{notice_kind}_delivered"
    for name, _comparison, value in walk(immediate):
        if name == "set_variable":
            variable = _field(value, "name", "")
            if variable.endswith("_notice_return_event"):
                writes["return"].append(variable)
            elif variable.endswith("_last_event"):
                writes["last"].append(variable)
            elif variable.endswith("_notice_response_context"):
                writes["context"].append(variable)
            elif variable.endswith(delivered_suffix):
                writes["delivered"].append(variable)
        elif name == "remove_variable" and isinstance(value, str) and value.endswith(due_suffix):
            due_removals.append(value)

    fields = {}
    for key, values in writes.items():
        if len(values) != 1:
            raise AssertionError(("native-notice-source-field-cardinality", key, values))
        fields[key] = values[0]
    if len(due_removals) != 1:
        raise AssertionError(("native-notice-due-removal-cardinality", due_removals))
    fields["due"] = due_removals[0]
    return fields


def _assert_finite_integral(test, value, label):
    test.assertIsInstance(value, (int, float), label)
    test.assertNotIsInstance(value, bool, label)
    test.assertTrue(math.isfinite(value), label)
    test.assertEqual(value, int(value), label)


def _notice12_ack_world(slug):
    world, evidence, event_id, row, order, counts = _natural_notice_world(slug, "notice12")
    if _candidate_kind(row["candidate"]) != "notice12":
        raise AssertionError(("expected-real-notice12-source-candidate", slug, event_id, row))
    reservation, epoch, queue = _reservation(world, row, event_id)
    event = _event(world, event_id)
    fields = _nmg_notice_body_fields(_field(event, "immediate", []), "notice12")
    return world, evidence, event_id, row, order, counts, reservation, epoch, queue, event, fields


class NmgQueueSnapshotRegression(unittest.TestCase):
    def test_selected_queue_presence_or_value_drift_blocks_prebody_and_cleanup_does_not_restore_it(self):
        """A stale selected snapshot cannot authorize any native immediate."""
        self.assertTrue(all((Path(__file__).resolve().parents[1] / path).is_file()
                            for path in SOURCE_INPUTS))

        # Same actual source path is a non-vacuous positive control: normal
        # immediate reaches whole-body completion and a real ACK/serve.
        world, evidence, event_id, row, _order, reservation, epoch, queue = _real_normal()
        self.assertEqual(len(evidence["root_admissions"]), 3)
        state = world.countries[TAG]
        event = _event(world, event_id)
        ack_name = f"{PREFIX}_ack_{reservation}"
        positive_ack_boundary = []
        original_run = world.run

        def observe_positive_ack(name, tag=TAG):
            if name == ack_name and tag == TAG:
                positive_ack_boundary.append(copy.deepcopy(state))
            return original_run(name, tag)

        world.run = observe_positive_ack
        world.execute(_field(event, "immediate", []), TAG)
        self.assertEqual(len(positive_ack_boundary), 1)
        self.assertEqual(positive_ack_boundary[0].get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(positive_ack_boundary[0].get(
            f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
        self.assertEqual(state.get(SERVED), state.get(ROUND))
        self.assertNotIn(queue, state)
        self.assertEqual(state.get(BUSINESS_COOLDOWN), 1)

        for fault, value in (("absent", None), ("zero", 0), ("seven", 7)):
            with self.subTest(fault=fault):
                world, _evidence, event_id, row, _order, reservation, _epoch, queue = _real_normal()
                state = world.countries[TAG]
                event = _event(world, event_id)
                if fault == "absent":
                    state.pop(queue, None)
                else:
                    state[queue] = value
                native_before = _native_state(state)
                ordinary_before = _fixture_state(state)
                served_before = copy.deepcopy(state.get(SERVED))
                world.execute(_field(event, "immediate", []), TAG)

                # Pre-body rejection may clear only candidate-private state.
                self.assertEqual(_native_state(state), native_before,
                                 "queue snapshot mismatch ran a native body mutation")
                self.assertEqual(_fixture_state(state), ordinary_before)
                self.assertEqual(state.get(SERVED), served_before,
                                 "a rejected/no-body path must not newly serve the round")
                self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                self.assertNotIn(f"{PREFIX}_callback_{reservation}", state)
                # The source pulse's prepare owns stale-reservation cleanup;
                # the guarded event itself must never compensate the queue.
                world.run(PREFIX + "_prepare", TAG)
                self.assertNotIn(PREFIX + "_reservation", state,
                                 "failed preflight should clear the private reservation")
                self.assertNotIn(PREFIX + "_timer", state)
                self.assertEqual((queue in state, state.get(queue)),
                                 (fault != "absent", value),
                                 "cleanup must not restore an old selected queue snapshot")

    def test_selected_queue_fault_at_actual_ack_boundary_is_a_side_effect_free_rejection(self):
        """Exercise ACK only after the true whole native event body ran."""
        for fault, value in (("absent", None), ("zero", 0), ("seven", 7)):
            with self.subTest(fault=fault):
                world, _evidence, event_id, _row, _order, reservation, epoch, queue = _real_normal()
                state = world.countries[TAG]
                event = _event(world, event_id)
                ack_name = f"{PREFIX}_ack_{reservation}"
                original_run = world.run
                at_ack = []

                def mutate_at_real_ack(name, tag=TAG):
                    if name == ack_name and tag == TAG:
                        at_ack.append(copy.deepcopy(state))
                        self.assertEqual(state.get(f"{PREFIX}_body_completed_{reservation}"), 1)
                        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                        self.assertEqual(state.get(BUSINESS_COOLDOWN), 1)
                        self.assertIn(f"ywc_nmg_land_last_event", state,
                                      "the actual native last_event write must precede ACK")
                        if fault == "absent":
                            state.pop(queue, None)
                        else:
                            state[queue] = value
                        at_ack[-1] = copy.deepcopy(state)
                    return original_run(name, tag)

                world.run = mutate_at_real_ack
                world.execute(_field(event, "immediate", []), TAG)
                self.assertEqual(len(at_ack), 1, "the whole real immediate must reach its ACK hook once")
                self.assertEqual(state, at_ack[0],
                                 "rejected real ACK must have no side effects or queue rollback")
                self.assertEqual(state.get(queue) if queue in state else None, value)
                self.assertEqual(queue in state, fault != "absent")
                self.assertEqual(state.get(BUSINESS_COOLDOWN), 1)
                self.assertEqual(state.get("ywc_nmg_land_last_event"), 1000,
                                 "authored event 1000 must write its native last_event value")

    def test_unknown_reservation_cleanup_preserves_native_presence_and_values_without_valid_epoch(self):
        """Unknown IDs 0/-1/999 release only protocol-private state."""
        native_fields = (
            "ywc_nmg_land_pending",
            SIBLING_QUEUE,
            "ywc_nmg_land_last_event",
            "ywc_nmg_land_notice_return_event",
            "ywc_nmg_land_notice_response_context",
            "ywc_nmg_land_notice12_due",
            "ywc_nmg_land_notice12_delivered",
            "ywc_nmg_land_notice36_due",
            "ywc_nmg_land_notice36_delivered",
        )
        for unknown, fault in ((0, "absent"), (0, "zero"), (0, "seven"),
                               (-1, "absent"), (-1, "zero"), (-1, "seven"),
                               (999, "absent"), (999, "zero"), (999, "seven")):
            with self.subTest(unknown=unknown, fault=fault):
                world, _evidence, _event_id, _row, _order, _reservation, _epoch, _queue = _real_normal()
                state = world.countries[TAG]
                if fault == "absent":
                    for name in native_fields:
                        state.pop(name, None)
                    state.pop(PREFIX + "_reservation_epoch", None)
                elif fault == "zero":
                    for name in native_fields:
                        state[name] = 0
                    state[PREFIX + "_reservation_epoch"] = 0
                else:
                    for name in native_fields:
                        state[name] = 7
                    state[PREFIX + "_reservation_epoch"] = -1
                state[PREFIX + "_reservation"] = unknown
                native_before = _native_state(state)
                ordinary_before = _fixture_state(state)

                world.run(PREFIX + "_prepare", TAG)

                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(PREFIX + "_timer", state)
                self.assertEqual(_native_state(state), native_before,
                                 "unknown-slot cleanup overwrote fresh source state")
                self.assertEqual(_fixture_state(state), ordinary_before)

    def test_sibling_queue_absence_zero_and_value_seven_survive_real_selected_normal_delivery(self):
        """ACK may reject or complete, but never restore a stale sibling queue."""
        for fault, value in (("absent", None), ("zero", 0), ("seven", 7)):
            with self.subTest(fault=fault):
                world, _evidence, event_id, _row, _order, reservation, epoch, queue = _real_normal()
                sibling_snapshot_present = _queue_snapshot_name(
                    reservation, SIBLING_QUEUE, "present", PREFIX)
                sibling_snapshot_value = _queue_snapshot_name(
                    reservation, SIBLING_QUEUE, "value", PREFIX)
                self.assertTrue(sibling_snapshot_present.startswith(PREFIX + f"_c{reservation}_"))
                self.assertTrue(sibling_snapshot_value.startswith(PREFIX + f"_c{reservation}_"))
                state = world.countries[TAG]
                if fault == "absent":
                    state.pop(SIBLING_QUEUE, None)
                else:
                    state[SIBLING_QUEUE] = value
                sibling_before = (SIBLING_QUEUE in state, copy.deepcopy(state.get(SIBLING_QUEUE)))
                served_before = copy.deepcopy(state.get(SERVED))
                event = _event(world, event_id)
                ack_calls = []
                original_run = world.run

                def observe_actual_ack(name, tag=TAG):
                    if name == f"{PREFIX}_ack_{reservation}" and tag == TAG:
                        ack_calls.append(copy.deepcopy(state))
                    return original_run(name, tag)

                world.run = observe_actual_ack
                world.execute(_field(event, "immediate", []), TAG)
                self.assertEqual((SIBLING_QUEUE in state, state.get(SIBLING_QUEUE)), sibling_before,
                                 "actual ACK restored/rewrote the fresh sibling queue")
                if ack_calls:
                    self.assertEqual(len(ack_calls), 1,
                                     "completed native body must pass through the real ACK invocation")
                    self.assertEqual(ack_calls[0].get("ywc_nmg_land_last_event"), 1000)
                    self.assertEqual(ack_calls[0].get(BUSINESS_COOLDOWN), 1)
                    self.assertEqual(ack_calls[0].get(queue), 1000,
                                     "the actual selected queue must still be intact at real ACK entry")
                else:
                    self.assertEqual(state.get(SERVED), served_before,
                                        "no-body path must not serve the candidate round")

    def test_real_notice12_ack_fails_closed_when_native_return_or_notice_postconditions_drift(self):
        """Actual notice body evidence is required after ACK-entry native faults."""
        # Non-vacuous notice12 source positive: authored paid setup, natural
        # due clock, full immediate, and original real ACK all complete.
        world, evidence, event_id, row, _order, _counts, reservation, epoch, queue, event, fields = (
            _notice12_ack_world(ARC_ORDER[0]))
        self.assertEqual(len(evidence["root_admissions"]), 3)
        state = world.countries[TAG]
        self.assertIn(fields["last"], state,
                      "paid source history must establish a real pre-notice last_event")
        old_last_event = copy.deepcopy(state[fields["last"]])
        _assert_finite_integral(self, old_last_event, "source-authored old last_event")
        self.assertEqual(state.get(fields["due"]), 1)
        self.assertEqual(state.get(queue), row["candidate"]["value"])
        ack_name = f"{PREFIX}_ack_{reservation}"
        original_run = world.run
        positive_boundary = []

        def observe_notice12_positive(name, tag=TAG):
            if name == ack_name and tag == TAG:
                positive_boundary.append(copy.deepcopy(state))
            return original_run(name, tag)

        world.run = observe_notice12_positive
        world.execute(_field(event, "immediate", []), TAG)
        self.assertEqual(len(positive_boundary), 1,
                         "a valid real notice12 immediate must reach ACK exactly once")
        at_ack = positive_boundary[0]
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_{reservation}"), 1)
        self.assertEqual(at_ack.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
        self.assertEqual(at_ack.get(fields["last"]), int(event_id.rsplit(".", 1)[1]))
        self.assertEqual(at_ack.get(fields["return"]), old_last_event,
                         "native return must reflect the actual old source last_event")
        self.assertNotIn(fields["due"], at_ack)
        self.assertEqual(at_ack.get(fields["delivered"]), 1)
        self.assertEqual(at_ack.get(fields["context"]), 1)
        self.assertEqual(at_ack.get(BUSINESS_COOLDOWN), 1)
        self.assertIn(queue, at_ack)
        self.assertNotIn(queue, state, "valid notice12 ACK must consume the selected queue")
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertEqual(state.get(SERVED), state.get(ROUND))

        # Exercise the complete eight-case native postcondition family on one
        # arc. Each body reaches its genuine ACK hook before exactly one
        # controlled field fault is injected; other arcs add a return mismatch.
        cases = [(ARC_ORDER[0], fault) for fault in (
            "return_missing", "return_wrong",
            "delivered_missing", "delivered_zero",
            "context_missing", "context_zero",
            "due_zero", "due_one",
        )]
        cases.extend((slug, "return_wrong") for slug in ARC_ORDER[1:])

        for slug, fault in cases:
            with self.subTest(arc=slug, fault=fault):
                (world, _evidence, event_id, row, _order, _counts,
                 reservation, epoch, queue, event, fields) = _notice12_ack_world(slug)
                state = world.countries[TAG]
                self.assertIn(fields["last"], state)
                source_old_last = copy.deepcopy(state[fields["last"]])
                _assert_finite_integral(self, source_old_last, "actual pre-body source last_event")
                self.assertEqual(state.get(fields["due"]), 1)
                self.assertEqual(state.get(queue), row["candidate"]["value"])
                served_name = f"{PREFIX}_served_{ARC_ORDER.index(slug) + 1}"
                served_before = copy.deepcopy(state.get(served_name))
                ack_name = f"{PREFIX}_ack_{reservation}"
                proof_names = (
                    f"{PREFIX}_callback_{reservation}",
                    f"{PREFIX}_callback_candidate_{reservation}",
                    f"{PREFIX}_callback_epoch_{reservation}",
                    f"{PREFIX}_callback_queue_{reservation}",
                )
                timer_name = PREFIX + "_timer"
                epoch_name = PREFIX + "_reservation_epoch"
                candidate_epoch_name = f"{PREFIX}_candidate_epoch_{reservation}"
                native_entry = []
                mutated_entry = []
                original_run = world.run

                def inject_native_postcondition_fault(name, tag=TAG):
                    if name == ack_name and tag == TAG:
                        entry = copy.deepcopy(state)
                        native_entry.append(entry)
                        self.assertEqual(entry.get(f"{PREFIX}_body_completed_{reservation}"), 1)
                        self.assertEqual(entry.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                        self.assertEqual(entry.get(fields["last"]), int(event_id.rsplit(".", 1)[1]))
                        self.assertEqual(entry.get(fields["return"]), source_old_last)
                        self.assertNotIn(fields["due"], entry)
                        self.assertEqual(entry.get(fields["delivered"]), 1)
                        self.assertEqual(entry.get(fields["context"]), 1)
                        self.assertEqual(entry.get(BUSINESS_COOLDOWN), 1)
                        self.assertEqual(entry.get(queue), row["candidate"]["value"])
                        self.assertTrue(all(name in entry for name in proof_names), proof_names)
                        self.assertEqual(entry[proof_names[0]], 1)
                        self.assertEqual(entry[proof_names[1]], reservation)
                        self.assertEqual(entry[proof_names[2]], epoch)
                        self.assertEqual(entry[proof_names[3]], row["candidate"]["value"])
                        self.assertIn(timer_name, entry)
                        self.assertIn(epoch_name, entry)
                        self.assertIn(candidate_epoch_name, entry)
                        self.assertEqual(entry[epoch_name], epoch)
                        self.assertEqual(entry[candidate_epoch_name], epoch)

                        if fault == "return_missing":
                            state.pop(fields["return"], None)
                        elif fault == "return_wrong":
                            state[fields["return"]] = source_old_last + 1
                            self.assertNotEqual(state[fields["return"]], source_old_last)
                        elif fault == "delivered_missing":
                            state.pop(fields["delivered"], None)
                        elif fault == "delivered_zero":
                            state[fields["delivered"]] = 0
                        elif fault == "context_missing":
                            state.pop(fields["context"], None)
                        elif fault == "context_zero":
                            state[fields["context"]] = 0
                        elif fault in {"due_zero", "due_one"}:
                            state[fields["due"]] = 0 if fault == "due_zero" else 1
                        else:
                            self.fail(("unknown-controlled-notice-postcondition-fault", fault))
                        mutated_entry.append(copy.deepcopy(state))
                    return original_run(name, tag)

                world.run = inject_native_postcondition_fault
                world.execute(_field(event, "immediate", []), TAG)

                self.assertEqual(len(native_entry), 1,
                                 "authored notice immediate must reach the genuine ACK after its whole body")
                self.assertEqual(len(mutated_entry), 1)
                self.assertEqual(state, mutated_entry[0],
                                 "ACK with stale native postconditions must have zero country-state side effects")
                self.assertEqual({name: state.get(name) for name in proof_names},
                                 {name: mutated_entry[0].get(name) for name in proof_names})
                self.assertEqual(state.get(timer_name), mutated_entry[0].get(timer_name))
                self.assertEqual(state.get(epoch_name), mutated_entry[0].get(epoch_name))
                self.assertEqual(state.get(candidate_epoch_name),
                                 mutated_entry[0].get(candidate_epoch_name))
                self.assertEqual(state.get(queue), row["candidate"]["value"],
                                 "failed native postcondition ACK must retain selected slot")
                self.assertEqual(state.get(served_name), served_before,
                                 "failed native postcondition ACK must not serve its JE round")

    def test_known_live_invalid_reservations_release_only_private_slot(self):
        """A real live reservation with damaged preflight is cleared without touching its native queue."""
        faults = (
            ("global_epoch_absent", "global_epoch", "absent"),
            ("global_epoch_zero", "global_epoch", 0),
            ("global_epoch_negative", "global_epoch", -1),
            ("global_epoch_mismatch", "global_epoch", "mismatch"),
            ("candidate_epoch_absent", "candidate_epoch", "absent"),
            ("candidate_epoch_zero", "candidate_epoch", 0),
            ("candidate_epoch_negative", "candidate_epoch", -1),
            ("candidate_epoch_mismatch", "candidate_epoch", "mismatch"),
            ("snapshot_value_absent", "snapshot_value", "absent"),
            ("snapshot_value_zero", "snapshot_value", 0),
            ("snapshot_value_seven", "snapshot_value", 7),
            ("snapshot_present_absent", "snapshot_present", "absent"),
            ("snapshot_present_zero", "snapshot_present", 0),
            ("snapshot_present_seven", "snapshot_present", 7),
        )

        # Live-valid control: a reservation made by all three real root
        # admissions and the authored pulse remains owned until expiry/ACK.
        world, evidence, event_id, row, _order, reservation, epoch, queue = _real_normal()
        self.assertEqual(len(evidence["root_admissions"]), 3)
        state = world.countries[TAG]
        timer_name = PREFIX + "_timer"
        self.assertIn(timer_name, state)
        _assert_finite_integral(self, state[timer_name], "source-created live reservation timer")
        self.assertGreater(state[timer_name], 0)
        self.assertGreater(world.days_until_expiry[TAG][timer_name], 0)
        event = _event(world, event_id)
        self.assertTrue(world.conditions(_field(event, "trigger", []), TAG),
                        "unmutated actual reservation must dispatch before prepare")
        world.run(PREFIX + "_prepare", TAG)
        self.assertEqual(state.get(PREFIX + "_reservation"), reservation)
        self.assertIn(timer_name, state)
        self.assertEqual(state.get(queue), row["candidate"]["value"])

        for label, fault, value in faults:
            with self.subTest(fault=label):
                world, evidence, event_id, row, _order, reservation, epoch, queue = _real_normal()
                self.assertEqual(len(evidence["root_admissions"]), 3)
                state = world.countries[TAG]
                timer_name = PREFIX + "_timer"
                epoch_name = PREFIX + "_reservation_epoch"
                candidate_epoch_name = f"{PREFIX}_candidate_epoch_{reservation}"
                snapshot_present = _queue_snapshot_name(reservation, queue, "present", PREFIX)
                snapshot_value = _queue_snapshot_name(reservation, queue, "value", PREFIX)
                self.assertIn(timer_name, state, "fault injection starts with a live timer")
                _assert_finite_integral(self, state[timer_name], "live reservation timer")
                self.assertGreater(state[timer_name], 0)
                self.assertGreater(world.days_until_expiry[TAG][timer_name], 0)
                self.assertEqual(state.get(queue), row["candidate"]["value"],
                                 "selected queue must be the actual source event value")
                self.assertIn(snapshot_present, state)
                self.assertEqual(state[snapshot_present], 1)
                self.assertEqual(state.get(snapshot_value), row["candidate"]["value"])

                if fault == "global_epoch":
                    if value == "absent":
                        state.pop(epoch_name, None)
                    elif value == "mismatch":
                        state[epoch_name] = epoch + 1
                    else:
                        state[epoch_name] = value
                elif fault == "candidate_epoch":
                    if value == "absent":
                        state.pop(candidate_epoch_name, None)
                    elif value == "mismatch":
                        state[candidate_epoch_name] = epoch + 1
                    else:
                        state[candidate_epoch_name] = value
                elif fault == "snapshot_value":
                    if value == "absent":
                        state.pop(snapshot_value, None)
                    else:
                        state[snapshot_value] = value
                elif fault == "snapshot_present":
                    if value == "absent":
                        state.pop(snapshot_present, None)
                    else:
                        state[snapshot_present] = value
                else:
                    self.fail(("unknown-live-reservation-fault", label))

                event = _event(world, event_id)
                dispatch_after_fault = world.conditions(_field(event, "trigger", []), TAG)
                with self.subTest(boundary="dispatch_gate"):
                    self.assertFalse(dispatch_after_fault,
                                     "each injected fault must make the actual source dispatch gate false")
                native_before = _native_state(state)
                world.run(PREFIX + "_prepare", TAG)
                self.assertEqual(_native_state(state), native_before,
                                 "live cleanup may not rewrite the exact selected source queue or any native state")
                with self.subTest(boundary="reservation_cleanup"):
                    self.assertNotIn(PREFIX + "_reservation", state,
                                     "known invalid live slot must be released during prepare")
                with self.subTest(boundary="timer_cleanup"):
                    self.assertNotIn(timer_name, state,
                                     "known invalid live timer must be cleared with its private slot")

        # Natural expiry is a distinct stale-slot path: even with an invalid
        # epoch, expiry removes the timer first and the next prepare then frees
        # the reservation. This is not evidence that a live invalid slot waits
        # for expiry; the cases above assert cleanup while its timer is present.
        world, _evidence, event_id, row, _order, reservation, epoch, queue = _real_normal()
        state = world.countries[TAG]
        state.pop(PREFIX + "_reservation_epoch", None)
        native_before = _native_state(state)
        self.assertIn(PREFIX + "_timer", state)
        world.advance_days(1)
        self.assertNotIn(PREFIX + "_timer", state)
        world.run(PREFIX + "_prepare", TAG)
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertNotIn(PREFIX + "_timer", state)
        self.assertEqual(_native_state(state), native_before)

    def test_comment_only_native_receipts_complete_real_generated_wrapper_and_ack(self):
        """AST-equivalent legal comments preserve the complete generated NMG body/proof/ACK path."""
        import json

        from tests.clausewitz_harness import parse
        from tools.build_v03_content import _adapter_event_immediate
        from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog

        catalog_path = Path(__file__).resolve().parents[1] / "data/content/v03/countries/nmg.json"
        base = json.loads(catalog_path.read_text(encoding="utf-8"))
        validate_inline_catalog(base)
        baseline_render = render_inline_country_adapters(base)
        arc_events = (
            (ARC_ORDER[0], "ywc_nmg.1000", 3, "land"),
            (ARC_ORDER[1], "ywc_nmg.1010", 15, "office"),
            (ARC_ORDER[2], "ywc_nmg.1020", 23, "revenue"),
        )

        def comment_variants(source, comment):
            major = "ywc_v03_mark_major_delivered = yes"
            if source.count(major) != 1:
                raise AssertionError(("native-major-marker-cardinality", source.count(major)))
            return {
                "prefix": source.replace("{", "{\n" + comment + "\n", 1),
                "before_receipt": source.replace(major, major + "\n" + comment + "\n", 1),
                # The newline terminates the same-line comment before the real receipt.
                "same_line": source.replace(major, major + " " + comment + "\n", 1),
            }

        def source_definitions(source, label):
            rows = parse(source)
            names = [name for name, _op, _body in rows]
            if len(names) != len(set(names)):
                raise AssertionError(("duplicate-generated-definition", label, names))
            return {name: body for name, _op, body in rows}

        layouts = ("baseline", "prefix", "before_receipt", "same_line")
        for slug, event_id, expected_candidate, owner in arc_events:
            for layout in layouts:
                with self.subTest(arc=slug, layout=layout):
                    # Each scenario begins from actual NMG history, legacy
                    # options, initializer, three root admissions and pulse.
                    world, evidence, actual_event, row, _order = _start_real_popup(slug, kind="normal")
                    self.assertEqual(len(evidence["root_admissions"]), 3)
                    self.assertEqual(actual_event, event_id)
                    reservation, epoch, queue = _reservation(world, row, actual_event)
                    self.assertEqual(reservation, expected_candidate)
                    self.assertEqual(row["candidate"]["value"], int(event_id.rsplit(".", 1)[1]))

                    mutant = copy.deepcopy(base)
                    event = next(event for arc in mutant["arcs"] for event in arc["events"]
                                 if event["id"] == event_id)
                    original_native = next(event["immediate"] for arc in base["arcs"]
                                           for event in arc["events"] if event["id"] == event_id)
                    self.assertEqual(event["immediate"], original_native)
                    native_receipt = f"ywc_nmg_{owner}_last_event"
                    comment = f"# name = {native_receipt} value = 777"
                    if layout != "baseline":
                        event["immediate"] = comment_variants(original_native, comment)[layout]
                    self.assertEqual(parse("immediate = " + original_native),
                                     parse("immediate = " + event["immediate"]),
                                     "the comment variant must retain the exact native AST")

                    validate_inline_catalog(mutant)
                    rendered = render_inline_country_adapters(mutant)
                    with self.subTest(rendered_contract="all_fields_equal_baseline"):
                        self.assertTrue(rendered == baseline_render,
                                        "all effects, triggers, proofs and hook metadata must be comment-invariant")

                    effect_defs = source_definitions(rendered["effects"], "effects")
                    trigger_defs = source_definitions(rendered["triggers"], "triggers")
                    self.assertIs(world.strict_trigger_defs, world.trigger_defs,
                                  "actual-world trigger and strict registry must be one instance-owned map")
                    self.assertTrue(set(effect_defs).issubset(world.effects),
                                    "generated effect pair must replace only already-loaded actual definitions")
                    self.assertTrue(set(trigger_defs).issubset(world.trigger_defs),
                                    "generated trigger pair must replace only already-loaded actual definitions")
                    world.effects.update(effect_defs)
                    world.trigger_defs.update(trigger_defs)
                    self.assertIs(world.strict_trigger_defs, world.trigger_defs,
                                  "updating generated triggers must retain the root factory alias")

                    complete_source = _adapter_event_immediate(event, rendered)
                    complete_nodes = parse("immediate = " + complete_source)
                    self.assertEqual(len(complete_nodes), 1)
                    self.assertEqual(complete_nodes[0][0], "immediate")
                    complete_wrapper = complete_nodes[0][2]
                    self.assertTrue(complete_source.startswith("{"))
                    self.assertIn(f"{PREFIX}_callback_{reservation} = yes", complete_source,
                                  "builder must generate the complete proof/callback wrapper")

                    state = world.countries[TAG]
                    timer_name = PREFIX + "_timer"
                    ack_name = f"{PREFIX}_ack_{reservation}"
                    ack_boundaries = []
                    original_run = world.run

                    def observe_natural_ack(name, tag=TAG):
                        if name == ack_name and tag == TAG:
                            ack_boundaries.append(copy.deepcopy(state))
                        return original_run(name, tag)

                    world.run = observe_natural_ack
                    dispatch = world.condition((f"{PREFIX}_dispatch_{reservation}", "=", "yes"), TAG)
                    self.assertTrue(dispatch, "real source reservation must pass before complete immediate")
                    world.execute(complete_wrapper, TAG)

                    receipt = int(event_id.rsplit(".", 1)[1])
                    self.assertEqual(state.get(native_receipt), receipt)
                    self.assertEqual(state.get(BUSINESS_COOLDOWN), 1)
                    with self.subTest(boundary="natural_ack_count"):
                        self.assertEqual(len(ack_boundaries), 1,
                                         "generated wrapper must produce proof and reach ACK naturally exactly once")
                    if ack_boundaries:
                        boundary = ack_boundaries[0]
                        self.assertEqual(boundary.get(f"{PREFIX}_body_completed_{reservation}"), 1)
                        self.assertEqual(boundary.get(f"{PREFIX}_body_completed_epoch_{reservation}"), epoch)
                        self.assertEqual(boundary.get(native_receipt), receipt)
                        self.assertEqual(boundary.get(BUSINESS_COOLDOWN), 1)
                        self.assertEqual(boundary.get(queue), receipt)
                        self.assertEqual(boundary.get(PREFIX + "_reservation"), reservation)
                        self.assertIn(timer_name, boundary)
                        proof_names = (
                            f"{PREFIX}_callback_{reservation}",
                            f"{PREFIX}_callback_candidate_{reservation}",
                            f"{PREFIX}_callback_epoch_{reservation}",
                            f"{PREFIX}_callback_queue_{reservation}",
                        )
                        self.assertTrue(all(name in boundary for name in proof_names), proof_names)
                        self.assertEqual(boundary[proof_names[0]], 1)
                        self.assertEqual(boundary[proof_names[1]], reservation)
                        self.assertEqual(boundary[proof_names[2]], epoch)
                        self.assertEqual(boundary[proof_names[3]], receipt)

                    with self.subTest(boundary="selected_queue_consumed"):
                        self.assertNotIn(queue, state,
                                         "a real generated ACK must consume the selected queue")
                    with self.subTest(boundary="reservation_cleared"):
                        self.assertNotIn(PREFIX + "_reservation", state)
                    with self.subTest(boundary="timer_cleared"):
                        self.assertNotIn(timer_name, state)
                    with self.subTest(boundary="body_completion_cleared"):
                        self.assertNotIn(f"{PREFIX}_body_completed_{reservation}", state)
                    with self.subTest(boundary="callback_proof_cleared"):
                        self.assertNotIn(f"{PREFIX}_callback_{reservation}", state)
                    with self.subTest(boundary="round_served"):
                        self.assertEqual(state.get(f"{PREFIX}_served_{ARC_ORDER.index(slug) + 1}"),
                                         state.get(PREFIX + "_round"))

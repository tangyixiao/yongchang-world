"""JHG queue/native snapshot, stale-dispatch and fault-boundary contracts."""
from __future__ import annotations

import copy
import unittest

from tests import test_v03_jhg_inline_actual_source as actual
from tests.test_v03_jhg_inline_provenance import (
    PREFIX, TAG, COOLDOWN, _all_bindings, _one_real_dispatch,
    _phase_worlds, _generated_sender, _native_notice_stem, _JHG_QUEUE_NAMES,
)


def _native_fields(world):
    """Capture native value/presence and both timer expiry maps in full."""
    state = world.countries[TAG]
    return {
        "variables": {name: copy.deepcopy(value) for name, value in state.items()
                      if not name.startswith(PREFIX + "_")},
        "days": {k: copy.deepcopy(v) for k, v in world.days_until_expiry[TAG].items()
                 if not k.startswith(PREFIX + "_")},
        "months": {k: copy.deepcopy(v) for k, v in world.months_until_expiry[TAG].items()
                   if not k.startswith(PREFIX + "_")},
        "treasury": copy.deepcopy(world.treasury.get(TAG, 0)),
    }


def _served_keys():
    arcs = []
    for candidate in _all_bindings():
        slug = candidate["arc"]["slug"]
        if slug not in arcs: arcs.append(slug)
    keys = [PREFIX + "_round"]
    keys.extend(f"{PREFIX}_served_{index}" for index in range(1, len(arcs) + 1))
    return tuple(keys)


def _served_snapshot(world):
    state = world.countries[TAG]
    return {key: (key in state, copy.deepcopy(state.get(key))) for key in _served_keys()}


def _private_snapshot(world):
    return copy.deepcopy(world.countries[TAG])


def _complete_state_snapshot(world):
    """Keep native, private, treasury, served and timer maps at one boundary."""
    return {
        "native": _native_fields(world),
        "private": _private_snapshot(world),
        "days": copy.deepcopy(world.days_until_expiry[TAG]),
        "months": copy.deepcopy(world.months_until_expiry[TAG]),
        "served": _served_snapshot(world),
        "treasury": copy.deepcopy(world.treasury.get(TAG, 0)),
    }


def _sender_dispatch(testcase, world, row, body_first=False):
    """Run one exact generated branch after real prepare in a declared unit fixture."""
    sender = _generated_sender(world, row)
    dispatches = []
    effect_runs = []
    def observe(current, dispatch):
        dispatches.append(copy.deepcopy(dispatch))
        if body_first: actual.run_queued_inline_event_immediate(current, dispatch)
    with actual.observe_actual_effect_runs(world, lambda _w, name, _tag: effect_runs.append(name)):
        with actual.observe_actual_dispatch_append(world, observe):
            world.run(PREFIX + "_prepare", TAG)
            testcase.assertIn(PREFIX + "_prepare", effect_runs)
            testcase.assertTrue(world.conditions(world.triggers[f"{PREFIX}_turn_{row['id']}"], TAG),
                                (row["id"], "source scheduler turn is legal after actual prepare"))
            limit = actual._field(sender[2], "limit", [])
            testcase.assertTrue(world.conditions(limit, TAG),
                                (row["id"], "exact generated branch limit is true after prepare"))
            world._b2_native_pre_source = _native_fields(world)
            world.execute([("if", sender[1], sender[2])], TAG)
    testcase.assertEqual(len(dispatches), 1, (row["id"], "one actual generated sender append"))
    testcase.assertEqual(dispatches[0]["event_id"], row["branch"]["event"],
                         (row["id"], "the declared source-callsite selected this event"))
    testcase.assertEqual(dispatches[0]["scope_context"].get(PREFIX + "_dispatch_candidate"),
                         row["id"], (row["id"], "exact source row identity survives the fair scheduler"))
    world._b2_effect_runs = tuple(effect_runs)
    return dispatches[0]


def _source_callsite_fixture(testcase, row, notice_case=None, phases=None):
    phases = _phase_worlds(testcase) if phases is None else phases
    world = actual.copy_actual_world_without_observers(phases[row["branch"]["journal"]])
    world.advance_days(91)
    testcase.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
    queue = row["candidate"]["queue"]
    state = world.countries[TAG]
    for sibling in _JHG_QUEUE_NAMES:
        state.pop(sibling, None)
    state[queue] = row["candidate"]["value"]
    if notice_case is not None:
        pre36, delivery36, marker = notice_case
        stem = _native_notice_stem(queue)
        pre_name = stem + "_36_notice"
        delivery12 = stem + "_notice_delivery_12"
        delivery36_name = stem + "_notice_delivery_36"
        marker12 = stem + "_12_notice_delivered"
        marker36 = stem + "_36_notice_delivered"
        if pre36 is None: state.pop(pre_name, None)
        else: state[pre_name] = pre36
        state.pop(delivery12, None)
        if delivery36 is None: state.pop(delivery36_name, None)
        else: state[delivery36_name] = delivery36
        state.pop(marker12, None); state.pop(marker36, None)
        target = marker36 if pre36 is not None or delivery36 is not None else marker12
        if marker is None: state.pop(target, None)
        else: state[target] = marker
    return world, _sender_dispatch(testcase, world, row)


class JhgInlineQueueSnapshots(unittest.TestCase):
    def test_sourcefirst_full_native_snapshot_and_exact_ack_boundary(self):
        """Capture all native values and expiry maps before body and around real ACK."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self, body_first=False)
        state = world.countries[TAG]
        queue = row["candidate"]["queue"]
        before_body = _native_fields(world)
        self.assertIn(queue, before_body["variables"])
        self.assertEqual(before_body["variables"][queue], row["candidate"]["value"])
        self.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)
        before_ack = []; after_ack = []
        with actual.observe_actual_owned_ack(
            world,
            lambda current, name, tag: before_ack.append((name, _native_fields(current), copy.deepcopy(current.countries[tag]))),
            after=lambda current, name, tag: after_ack.append((name, _native_fields(current), copy.deepcopy(current.countries[tag]))),
        ):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(len(before_ack), 1); self.assertEqual(len(after_ack), 1)
        self.assertEqual(before_ack[0][0], f"{PREFIX}_ack_{ident}")
        self.assertEqual(before_ack[0][2].get(f"{PREFIX}_body_completed_{ident}"), 1)
        self.assertEqual(before_ack[0][2].get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
        self.assertEqual(before_ack[0][2].get(f"{PREFIX}_sender_completed_{ident}"), 1)
        self.assertEqual(before_ack[0][1]["variables"].get(COOLDOWN), 1)
        self.assertEqual(before_ack[0][1]["days"].get(COOLDOWN), 90,
                         "body-owned 90-day expiry is present at the real pre-ACK boundary")
        self.assertNotIn(COOLDOWN, before_ack[0][1]["months"])
        self.assertIn(queue, before_ack[0][1]["variables"], "selected queue persists until successful ACK")
        self.assertNotIn(queue, after_ack[0][1]["variables"], "ACK removes selected queue once")
        self.assertEqual(after_ack[0][2].get(f"{PREFIX}_callback_candidate_{ident}"), ident)
        self.assertEqual(after_ack[0][2].get(f"{PREFIX}_callback_epoch_{ident}"), epoch)

    def test_missing_one_or_both_proofs_and_mixed_epochs_never_service_native_work(self):
        """Only separate same-epoch source and body returns can lead to ACK."""
        actual.assert_inline_supported(self)
        row = next(row for row in _all_bindings() if row["candidate"]["kind"] == "normal")
        ident = row["id"]

        # Missing-both starts with a real sender-generated dispatch, then the
        # named fault removes only source receipts before public wakes execute.
        world, dispatch = _source_callsite_fixture(self, row)
        state = world.countries[TAG]
        sender_stamp = f"{PREFIX}_sender_completed_{ident}"
        sender_epoch = f"{PREFIX}_sender_completed_epoch_{ident}"
        body_stamp = f"{PREFIX}_body_completed_{ident}"
        body_epoch = f"{PREFIX}_body_completed_epoch_{ident}"
        state.pop(sender_stamp, None); state.pop(sender_epoch, None)
        native_before = _native_fields(world); served_before = _served_snapshot(world)
        for suffix in (f"callback_{ident}", f"join_{ident}", f"ack_{ident}"):
            world.run(f"{PREFIX}_{suffix}", TAG)
        self.assertNotIn(sender_stamp, state); self.assertNotIn(body_stamp, state)
        self.assertEqual(_native_fields(world), native_before)
        self.assertEqual(_served_snapshot(world), served_before)
        self.assertEqual(state.get(PREFIX + "_reservation"), ident)
        self.assertIn(row["candidate"]["queue"], state)

        # Sender-only: actual source continuation has already fired its own
        # wake. Direct callback/ACK attempts cannot manufacture body proof.
        world, dispatch = _source_callsite_fixture(self, row)
        state = world.countries[TAG]
        self.assertEqual(state.get(sender_stamp), 1)
        self.assertIn(f"{PREFIX}_sender_return_{ident}", world._b2_effect_runs)
        native_before = _native_fields(world); served_before = _served_snapshot(world)
        world.run(f"{PREFIX}_callback_{ident}", TAG)
        world.run(f"{PREFIX}_join_{ident}", TAG)
        world.run(f"{PREFIX}_ack_{ident}", TAG)
        self.assertNotIn(body_stamp, state); self.assertNotIn(body_epoch, state)
        self.assertEqual(_native_fields(world), native_before)
        self.assertEqual(_served_snapshot(world), served_before)
        self.assertEqual(state.get(sender_stamp), 1)
        self.assertIn(row["candidate"]["queue"], state)

        # Body-only: source proof is fault-removed after the genuine append;
        # the real native event creates only its own body-side proof/wake.
        world, dispatch = _source_callsite_fixture(self, row)
        state = world.countries[TAG]
        state.pop(sender_stamp, None); state.pop(sender_epoch, None)
        body_runs = []
        with actual.observe_actual_effect_runs(
            world, lambda _w, name, _tag: body_runs.append(name)):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertIn(f"{PREFIX}_body_return_{ident}", body_runs)
        self.assertEqual(state.get(body_stamp), 1)
        self.assertEqual(state.get(body_epoch), dispatch["scope_context"][PREFIX + "_dispatch_epoch"])
        self.assertNotIn(sender_stamp, state); self.assertNotIn(sender_epoch, state)
        native_after_body = _native_fields(world); served_before = _served_snapshot(world)
        world.run(f"{PREFIX}_callback_{ident}", TAG)
        world.run(f"{PREFIX}_join_{ident}", TAG)
        world.run(f"{PREFIX}_ack_{ident}", TAG)
        self.assertEqual(_native_fields(world), native_after_body)
        self.assertEqual(_served_snapshot(world), served_before)
        self.assertIn(row["candidate"]["queue"], state)
        self.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)

        # Both receipts are source-generated here, then a named fault changes
        # one epoch only after the true body has reached its ACK boundary.
        world, dispatch = _source_callsite_fixture(self, row)
        state = world.countries[TAG]
        epoch = dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
        fault = []
        def mismatch_after_body(current, name, tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            native = _native_fields(current)
            private = copy.deepcopy(current.countries[tag])
            served = _served_snapshot(current)
            private[sender_epoch] = epoch + 1
            current.countries[tag][sender_epoch] = epoch + 1
            fault.append((native, private, served))
        with actual.observe_actual_owned_ack(world, mismatch_after_body):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(len(fault), 1)
        self.assertEqual(_native_fields(world), fault[0][0])
        self.assertEqual(world.countries[TAG], fault[0][1])
        self.assertEqual(_served_snapshot(world), fault[0][2])
        self.assertIn(row["candidate"]["queue"], state)
        self.assertEqual(state.get(PREFIX + "_reservation"), ident)

    def test_successful_join_then_repeated_ack_wakes_and_body_replay_are_idempotent(self):
        """Repeated owned helpers cannot service a consumed epoch or replay body."""
        actual.assert_inline_supported(self)
        row = next(row for row in _all_bindings() if row["candidate"]["kind"] == "normal")
        phases = _phase_worlds(self)
        from tests.test_v03_jhg_inline_provenance import _invoke_callsite
        world, dispatch, epoch, ack_rows = _invoke_callsite(
            self, phases[row["branch"]["journal"]], row, body_first=False)
        state = world.countries[TAG]
        ident = row["id"]
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
        self.assertNotIn(row["candidate"]["queue"], state)
        before_native = _native_fields(world); before_served = _served_snapshot(world)
        for suffix in (f"ack_{ident}", f"join_{ident}",
                       f"sender_return_{ident}", f"body_return_{ident}", f"callback_{ident}"):
            world.run(f"{PREFIX}_{suffix}", TAG)
        self.assertEqual(_native_fields(world), before_native)
        self.assertEqual(_served_snapshot(world), before_served)
        private_before_replay = copy.deepcopy(state)
        with self.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(_native_fields(world), before_native)
        self.assertEqual(state, private_before_replay)

    def test_matching_sender_receipt_requires_notice_post_state_not_baseline_p(self):
        """Corrupting R(P) back to baseline P after a matching sender proof fails ACK."""
        actual.assert_inline_supported(self)
        row = next(item for item in _all_bindings() if item["candidate"]["kind"] == "notice")
        phases = _phase_worlds(self)
        world = actual.copy_actual_world_without_observers(phases[row["branch"]["journal"]])
        world.advance_days(91)
        state = world.countries[TAG]
        stem = _native_notice_stem(row["candidate"]["queue"])
        marker = stem + "_36_notice_delivered"
        state[stem + "_36_notice"] = 1
        state[row["candidate"]["queue"]] = row["candidate"]["value"]
        baseline_p = _native_fields(world)
        self.assertNotIn(marker, state)

        # The unchanged source callsite creates reservation, frozen dispatch,
        # sender receipt, and native R(P). The same-epoch sender receipt ties
        # this test to the post-source state, rather than an arbitrary marker.
        dispatch = _sender_dispatch(self, world, row)
        ident = row["id"]
        epoch = dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
        self.assertEqual(state.get(marker), 1)
        self.assertNotEqual(_native_fields(world), baseline_p)

        fault = []
        def corrupt_post_state(current, name, tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            current_state = current.countries[tag]
            self.assertEqual(current_state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
            self.assertEqual(current_state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
            self.assertEqual(current_state.get(PREFIX + "_reservation_epoch"), epoch)
            # Restore only the baseline marker presence/value P at the actual
            # ACK boundary, after the body and both genuine proofs exist.
            current_state.pop(marker, None)
            fault.append(_complete_state_snapshot(current))

        with actual.observe_actual_owned_ack(world, corrupt_post_state):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(len(fault), 1)
        self.assertEqual(_native_fields(world), fault[0]["native"],
                         "guard failure must preserve corrupted fault-time R(P), not roll it back")
        self.assertEqual(world.countries[TAG], fault[0]["private"])
        self.assertEqual(_served_snapshot(world), fault[0]["served"])
        self.assertEqual(world.days_until_expiry[TAG], fault[0]["days"])
        self.assertEqual(world.months_until_expiry[TAG], fault[0]["months"])
        self.assertEqual(world.treasury.get(TAG, 0), fault[0]["treasury"])
        self.assertIn(row["candidate"]["queue"], world.countries[TAG])
        self.assertEqual(world.countries[TAG].get(PREFIX + "_reservation"), ident)
        self.assertNotIn(marker, world.countries[TAG])

    def test_matching_sender_receipt_requires_notice_post_state_before_body_entry(self):
        """R(P) corruption at event entry rejects before native immediate/body proof."""
        actual.assert_inline_supported(self)
        row = next(item for item in _all_bindings() if item["candidate"]["kind"] == "notice")
        world, dispatch = _source_callsite_fixture(self, row, notice_case=(1, None, None))
        state = world.countries[TAG]
        ident = row["id"]
        epoch = dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
        stem = _native_notice_stem(row["candidate"]["queue"])
        marker = stem + "_36_notice_delivered"
        baseline_p = world._b2_native_pre_source
        self.assertNotIn(marker, baseline_p["variables"])
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)
        self.assertEqual(state.get(marker), 1, "the actual source continuation produced R(P)")

        # Restore exactly baseline P at the real source-to-body boundary while
        # retaining the same-epoch source receipt and actual frozen dispatch.
        state.pop(marker, None)
        fault = _complete_state_snapshot(world)
        with self.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(_complete_state_snapshot(world), fault,
                         "prebody rejection preserves exact fault-time native/private/timer/treasury state")
        self.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)
        self.assertNotIn(f"{PREFIX}_body_completed_epoch_{ident}", state)
        self.assertNotIn(COOLDOWN, state,
                         "the native body did not mark the shared cooldown")
        self.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
        self.assertIn(row["candidate"]["queue"], state)
        self.assertEqual(state.get(PREFIX + "_reservation"), ident)
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)

    def test_invalid_frozen_invocation_tokens_reject_before_native_body(self):
        """A stale/missing token is checked at actual event entry, before any body proof."""
        actual.assert_inline_supported(self)
        cases = (
            ("missing-candidate", None, "candidate"),
            ("zero-candidate", 0, "candidate"),
            ("negative-candidate", -1, "candidate"),
            ("other-candidate-same-event", "same-event", "candidate"),
            ("other-candidate-different-event", "other-event", "candidate"),
            ("missing-epoch", None, "epoch"),
            ("zero-epoch", 0, "epoch"),
            ("negative-epoch", -1, "epoch"),
            ("mismatched-epoch", "mismatch", "epoch"),
        )
        for label, value, field in cases:
            with self.subTest(token=label):
                world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
                bad = copy.deepcopy(dispatch)
                key = PREFIX + ("_dispatch_candidate" if field == "candidate" else "_dispatch_epoch")
                if value is None: bad["scope_context"].pop(key, None)
                elif value == "mismatch": bad["scope_context"][key] = epoch + 1
                elif value == "same-event":
                    bad["scope_context"][key] = next(
                        item["id"] for item in _all_bindings()
                        if item["id"] != ident and item["branch"]["event"] == row["branch"]["event"])
                elif value == "other-event":
                    bad["scope_context"][key] = next(
                        item["id"] for item in _all_bindings()
                        if item["branch"]["event"] != row["branch"]["event"])
                else: bad["scope_context"][key] = value
                native_before = _native_fields(world)
                private_before = copy.deepcopy(world.countries[TAG])
                with self.assertRaises(ValueError):
                    actual.run_queued_inline_event_immediate(world, bad)
                self.assertEqual(_native_fields(world), native_before)
                self.assertEqual(world.countries[TAG], private_before)
                self.assertNotIn(f"{PREFIX}_body_completed_{ident}", world.countries[TAG])
                self.assertEqual(world.countries[TAG].get(PREFIX + "_reservation_epoch"), epoch)
                self.assertEqual(world.countries[TAG].get(row["candidate"]["queue"]), row["candidate"]["value"])

    def test_invalid_live_phase_epoch_unknown_owner_zero_queue_and_cooldown_are_fail_closed(self):
        """Source callsites require real JE/witness/owner state and cooldown absence."""
        actual.assert_inline_supported(self)
        phases = _phase_worlds(self)
        rows = _all_bindings()
        row = next(item for item in rows if item["candidate"]["kind"] == "normal")
        phase = phases[row["branch"]["journal"]]
        witness = next(p["live_witness"] for p in row["arc"]["inline_delivery_adapter"]["live_phases"]
                       if p["journal"] == row["branch"]["journal"])
        sender = _generated_sender(phase, row)
        invocation = sender if sender[0] == "if" else ("if", sender[1], sender[2])

        # Invalid source phase representations and missing real journal
        # membership reject before reservation, append, proof or served state.
        for label, mutation in (("absent", lambda s, w: s.pop(witness, None)),
                                ("zero", lambda s, w: s.__setitem__(witness, 0)),
                                ("seven", lambda s, w: s.__setitem__(witness, 7)),
                                ("unknown-je", None)):
            with self.subTest(live_phase=label):
                world = actual.copy_actual_world_without_observers(phase)
                world.advance_days(91)
                state = world.countries[TAG]
                state[row["candidate"]["queue"]] = row["candidate"]["value"]
                if mutation is None:
                    world.journals = [entry for entry in world.journals
                                      if not (entry[0] == TAG and "type" in dict(
                                          (key, value) for key, _, value in entry[1])
                                          and dict((key, value) for key, _, value in entry[1])["type"]
                                          == row["branch"]["journal"])]
                else:
                    mutation(state, witness)
                native_before = _native_fields(world)
                private_before = copy.deepcopy(state)
                served_before = _served_snapshot(world)
                self.assertFalse(world.conditions(actual._field(sender[2], "limit", []), TAG))
                world.execute([invocation], TAG)
                self.assertEqual(_native_fields(world), native_before)
                self.assertEqual(state, private_before)
                self.assertEqual(_served_snapshot(world), served_before)
                self.assertNotIn(PREFIX + "_reservation", state)
                self.assertNotIn(PREFIX + "_sender_completed_" + str(row["id"]), state)

        # Queue value zero is not an authored candidate and does not reserve.
        world = actual.copy_actual_world_without_observers(phase)
        world.advance_days(91)
        state = world.countries[TAG]
        queue = row["candidate"]["queue"]
        state[queue] = 0
        native_before = _native_fields(world); private_before = copy.deepcopy(state)
        served_before = _served_snapshot(world)
        self.assertFalse(world.conditions(actual._field(sender[2], "limit", []), TAG))
        world.execute([invocation], TAG)
        self.assertEqual(_native_fields(world), native_before)
        self.assertEqual(state, private_before)
        self.assertEqual(_served_snapshot(world), served_before)

        # A live cooldown value of 0, 1 or 7 is a negative native input, never
        # a positive source admission; preserve value and exact timer presence.
        for value in (0, 1, 7):
            with self.subTest(cooldown=value):
                world = actual.copy_actual_world_without_observers(phase)
                world.advance_days(91)
                state = world.countries[TAG]
                state[queue] = row["candidate"]["value"]
                state[COOLDOWN] = value
                world.days_until_expiry[TAG][COOLDOWN] = 90
                native_before = _native_fields(world); private_before = copy.deepcopy(state)
                served_before = _served_snapshot(world)
                self.assertFalse(world.conditions(actual._field(sender[2], "limit", []), TAG))
                world.execute([invocation], TAG)
                self.assertEqual(_native_fields(world), native_before)
                self.assertEqual(state, private_before)
                self.assertEqual(_served_snapshot(world), served_before)

    def test_unknown_owner_cleanup_allows_real_other_arc_sender_progress(self):
        """Unknown owner cleanup expires privately and does not deadlock another arc."""
        actual.assert_inline_supported(self)
        phases = _phase_worlds(self)
        normal = [item for item in _all_bindings() if item["candidate"]["kind"] == "normal"]
        owner = normal[-1]
        world = actual.copy_actual_world_without_observers(phases[owner["branch"]["journal"]])
        world.advance_days(91)
        state = world.countries[TAG]
        state[owner["candidate"]["queue"]] = owner["candidate"]["value"]
        old_dispatch = _sender_dispatch(self, world, owner)
        old_epoch = old_dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
        state[PREFIX + "_reservation"] = 999
        served_before = _served_snapshot(world)
        world.advance_days(91)
        world.run(PREFIX + "_prepare", TAG)
        self.assertNotIn(PREFIX + "_reservation", state,
                         "eventual unknown-owner cleanup cannot strand the shared reservation slot")
        self.assertEqual(_served_snapshot(world), served_before)
        self.assertIn(owner["candidate"]["queue"], state)
        self.assertGreater(old_epoch, 0)

        other = next(item for item in normal if item["arc"]["slug"] != owner["arc"]["slug"])
        self.assertTrue(world.journal_is_active(TAG, other["branch"]["journal"]))
        state[other["candidate"]["queue"]] = other["candidate"]["value"]
        fresh = _sender_dispatch(self, world, other)
        self.assertEqual(fresh["event_id"], other["branch"]["event"])
        self.assertEqual(fresh["scope_context"].get(PREFIX + "_dispatch_candidate"), other["id"])
        self.assertGreater(fresh["scope_context"].get(PREFIX + "_dispatch_epoch"), old_epoch)
        epoch = fresh["scope_context"][PREFIX + "_dispatch_epoch"]
        native_at_body = _native_fields(world)
        served_before = _served_snapshot(world)
        actual.run_queued_inline_event_immediate(world, fresh)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{other['id']}"), epoch)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{other['id']}"), epoch)
        self.assertEqual(state.get(f"{PREFIX}_callback_epoch_{other['id']}"), epoch)
        self.assertNotIn(other["candidate"]["queue"], state)
        self.assertIn(owner["candidate"]["queue"], state,
                      "successful other-arc ACK preserves stale owner's native queue")
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        self.assertNotEqual(_served_snapshot(world), served_before)
        self.assertNotEqual(_native_fields(world), native_at_body)

    def test_latent_fixture_api_imports_and_notice_signature_are_auditable_before_gate(self):
        """Feature RED cannot hide unresolved helper imports or keyword drift."""
        import inspect
        from tests.test_v03_jhg_inline_queue_snapshots import _sender_dispatch, _source_callsite_fixture
        self.assertIn("notice_case", inspect.signature(_source_callsite_fixture).parameters)
        self.assertIn("body_first", inspect.signature(_sender_dispatch).parameters)

    def test_invalid_current_reservation_epoch_and_owner_reject_real_frozen_event(self):
        """Only the current source-issued owner and positive epoch enter body."""
        actual.assert_inline_supported(self)
        row = next(item for item in _all_bindings() if item["candidate"]["kind"] == "normal")
        ident = row["id"]
        reservation = PREFIX + "_reservation"
        epoch_key = PREFIX + "_reservation_epoch"
        cases = ("reservation-absent", "reservation-zero", "reservation-unknown",
                 "epoch-absent", "epoch-zero", "epoch-negative", "epoch-mismatch")
        for case in cases:
            with self.subTest(current_state=case):
                world, dispatch = _source_callsite_fixture(self, row)
                state = world.countries[TAG]
                epoch = dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
                if case == "reservation-absent": state.pop(reservation, None)
                elif case == "reservation-zero": state[reservation] = 0
                elif case == "reservation-unknown": state[reservation] = 999
                elif case == "epoch-absent": state.pop(epoch_key, None)
                elif case == "epoch-zero": state[epoch_key] = 0
                elif case == "epoch-negative": state[epoch_key] = -1
                elif case == "epoch-mismatch": state[epoch_key] = epoch + 1
                native_before = _native_fields(world)
                private_before = copy.deepcopy(state)
                served_before = _served_snapshot(world)
                with self.assertRaises(ValueError):
                    actual.run_queued_inline_event_immediate(world, dispatch)
                self.assertEqual(_native_fields(world), native_before)
                self.assertEqual(state, private_before)
                self.assertEqual(_served_snapshot(world), served_before)

    def test_prebody_selected_sibling_context_and_cooldown_faults_fail_without_rollback(self):
        """Normal/12/36 snapshots reject changed native inputs before body or service."""
        actual.assert_inline_supported(self)
        rows = _all_bindings()
        normal = next(row for row in rows if row["candidate"]["kind"] == "normal")
        notices = [row for row in rows if row["candidate"]["kind"] == "notice"]
        notice12, notice36 = notices[0], notices[-1]
        phases = _phase_worlds(self)

        def assert_rejected(row, notice_case, mutate):
            world, dispatch = _source_callsite_fixture(self, row, notice_case=notice_case,
                                                       phases=phases)
            state = world.countries[TAG]
            ident = row["id"]
            epoch = dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
            self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
            mutate(world, state, row)
            fault = _complete_state_snapshot(world)
            with self.assertRaises(ValueError):
                actual.run_queued_inline_event_immediate(world, dispatch)
            self.assertEqual(_complete_state_snapshot(world), fault)
            self.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)
            self.assertNotIn(f"{PREFIX}_body_completed_epoch_{ident}", state)
            self.assertNotIn(f"{PREFIX}_callback_{ident}", state)
            self.assertEqual(state.get(PREFIX + "_reservation"), ident)
            self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)
            self.assertEqual(row["candidate"]["queue"] in state,
                             fault["private"].get(row["candidate"]["queue"]) is not None,
                             "selected queue presence/value is preserved exactly as faulted")

        cases = (
            (normal, None),
            (notice12, (None, None, None)),
            (notice36, (1, None, None)),
        )
        for row, notice_case in cases:
            queue = row["candidate"]["queue"]
            stem = _native_notice_stem(queue)
            sibling = (stem + ("_pending_event" if queue.endswith("_notice_pending_event")
                               else "_notice_pending_event"))
            sibling_row = next(item for item in _all_bindings()
                               if item["branch"]["journal"] == row["branch"]["journal"]
                               and item["candidate"]["queue"] == sibling)
            for label, value in (("selected-absent", None), ("selected-zero", 0),
                                 ("selected-seven", 7), ("sibling-zero", (sibling, 0)),
                                 ("sibling-seven", (sibling, 7)),
                                 ("sibling-source-value", (sibling, sibling_row["candidate"]["value"]))):
                with self.subTest(fault=label, candidate=row["id"]):
                    def mutate(_world, state, current_row, _value=value):
                        if isinstance(_value, tuple): state[_value[0]] = _value[1]
                        elif _value is None: state.pop(current_row["candidate"]["queue"], None)
                        else: state[current_row["candidate"]["queue"]] = _value
                    assert_rejected(row, notice_case, mutate)

        for row, notice_case, stem, subtype in (
            (notice12, (None, None, None), _native_notice_stem(notice12["candidate"]["queue"]), "12"),
            (notice36, (1, None, None), _native_notice_stem(notice36["candidate"]["queue"]), "36"),
        ):
            context_fields = (
                (stem + "_notice_delivery_active", None),
                (stem + "_notice_delivery_active", 0),
                (stem + "_notice_delivery_" + subtype, None),
                (stem + "_notice_delivery_" + subtype, 0),
                (stem + "_notice_delivery_" + subtype, 7),
                (stem + "_" + subtype + "_notice_delivered", None),
                (stem + "_" + subtype + "_notice_delivered", 0),
                (stem + "_" + subtype + "_notice_delivered", 7),
                (stem + "_36_notice", None if subtype == "36" else 0),
                (stem + "_36_notice", 7) if subtype == "36" else (stem + "_36_notice", 7),
            )
            for field, value in context_fields:
                with self.subTest(candidate=row["id"], field=field, value=value):
                    def mutate(_world, state, _row, f=field, v=value):
                        if v is None: state.pop(f, None)
                        else: state[f] = v
                    assert_rejected(row, notice_case, mutate)

        for row, notice_case in cases:
            for value in (0, 1, 7):
                with self.subTest(cooldown=value, candidate=row["id"]):
                    def mutate(world, state, _row, v=value):
                        state[COOLDOWN] = v
                        world.days_until_expiry[TAG][COOLDOWN] = 17
                    assert_rejected(row, notice_case, mutate)

    def test_epoch_mutation_after_real_body_cannot_ack_or_rollback_native_state(self):
        """A changed live epoch cannot consume native ownership after body completion."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        fault_time = []
        def mutate_epoch_after_body(current, name, tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            state = current.countries[tag]
            self.assertEqual(state.get(f"{PREFIX}_body_completed_{ident}"), 1)
            self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
            self.assertEqual(state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
            fault_time.append(_complete_state_snapshot(current))
            state[PREFIX + "_reservation_epoch"] = epoch + 1
        with actual.observe_actual_owned_ack(world, mutate_epoch_after_body):
            actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(len(fault_time), 1)
        self.assertEqual(_native_fields(world), fault_time[0]["native"],
                         "ACK rejection cannot roll native source/body state back to prebody P")
        expected_private = fault_time[0]["private"]
        expected_private[PREFIX + "_reservation_epoch"] = epoch + 1
        self.assertEqual(world.countries[TAG], expected_private)
        self.assertEqual(world.countries[TAG].get(PREFIX + "_reservation_epoch"), epoch + 1)
        self.assertIn(row["candidate"]["queue"], world.countries[TAG])
        self.assertEqual(_served_snapshot(world), fault_time[0]["served"],
                         "a stale epoch cannot mark this arc served")
        self.assertEqual(world.days_until_expiry[TAG], fault_time[0]["days"])
        self.assertEqual(world.months_until_expiry[TAG], fault_time[0]["months"])
        self.assertEqual(world.treasury.get(TAG, 0), fault_time[0]["treasury"])

    def test_fault_after_full_body_before_ack_preserves_fault_time_native_state(self):
        """Real body completes before the owned ACK seam injects a native-state fault."""
        actual.assert_inline_supported(self)
        for replacement in (None, 0, 7):
            with self.subTest(selected=replacement):
                world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
                state = world.countries[TAG]
                queue = row["candidate"]["queue"]
                stem = (queue.removesuffix("_notice_pending_event")
                        .removesuffix("_pending_event"))
                siblings = [name for name in (stem + "_pending_event", stem + "_notice_pending_event")
                            if name != queue]
                fault_snapshots = []
                def fault_after_body(current, name, tag):
                    self.assertEqual(name, f"{PREFIX}_ack_{ident}")
                    current_state = current.countries[tag]
                    self.assertEqual(current_state.get(f"{PREFIX}_body_completed_{ident}"), 1)
                    self.assertEqual(current_state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
                    self.assertEqual(current_state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
                    self.assertEqual(current_state.get(COOLDOWN), 1)
                    if replacement is None: current_state.pop(queue, None)
                    else: current_state[queue] = replacement
                    for sibling in siblings:
                        if replacement is None: current_state.pop(sibling, None)
                        else: current_state[sibling] = replacement
                    fault_snapshots.append(_complete_state_snapshot(current))
                with actual.observe_actual_owned_ack(world, fault_after_body):
                    actual.run_queued_inline_event_immediate(world, dispatch)
                self.assertEqual(len(fault_snapshots), 1)
                self.assertEqual(_native_fields(world), fault_snapshots[0]["native"],
                                 "rejected ACK cannot roll back native post/body state")
                self.assertEqual(_served_snapshot(world), fault_snapshots[0]["served"],
                                 "failed ACK cannot mark an arc served")
                self.assertEqual(world.days_until_expiry[TAG], fault_snapshots[0]["days"])
                self.assertEqual(world.months_until_expiry[TAG], fault_snapshots[0]["months"])
                self.assertEqual(world.treasury.get(TAG, 0), fault_snapshots[0]["treasury"])
                world.run(PREFIX + "_prepare", TAG)
                self.assertEqual(_native_fields(world), fault_snapshots[0]["native"],
                                 "private cleanup cannot restore or clobber native fault-time values")
                self.assertEqual(_served_snapshot(world), fault_snapshots[0]["served"])

    def test_after_ack_exception_keeps_ack_boundary_state_without_native_rollback(self):
        """A named after-ACK fault occurs only after the real ACK has run."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        snapshots = []
        def after(current, name, tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            self.assertEqual(current.countries[tag].get(f"{PREFIX}_body_completed_{ident}"), 1)
            self.assertNotIn(row["candidate"]["queue"], current.countries[tag])
            snapshots.append(_native_fields(current))
            raise RuntimeError("fault after actual ACK")
        with actual.observe_actual_owned_ack(world, lambda *_: None, after=after):
            with self.assertRaisesRegex(RuntimeError, "after actual ACK"):
                actual.run_queued_inline_event_immediate(world, dispatch)
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(_native_fields(world), snapshots[0])
        world.run(PREFIX + "_prepare", TAG)
        self.assertEqual(_native_fields(world), snapshots[0])
        self.assertNotIn(PREFIX + "_reservation", world.countries[TAG])

    def test_old_queued_same_candidate_after_natural_expiry_cannot_delete_new_owner(self):
        """No-body expiry and two fresh notice deliveries preserve the 36 marker."""
        actual.assert_inline_supported(self)
        row = next(row for row in _all_bindings() if row["candidate"]["kind"] == "notice")
        world, old_dispatch = _source_callsite_fixture(self, row, notice_case=(1, None, None))
        state = world.countries[TAG]
        queue = row["candidate"]["queue"]
        stem = _native_notice_stem(queue)
        ident = row["id"]
        marker = stem + "_36_notice_delivered"
        self.assertEqual(state.get(marker), 1,
                         "the real notice source tail has set the 36-month postmarker")
        old_epoch = old_dispatch["scope_context"][PREFIX + "_dispatch_epoch"]

        # Let the source dispatch expire without running its event body.
        world.advance_days(91)
        world.run(PREFIX + "_prepare", TAG)
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertIn(queue, state, "natural no-body expiry preserves the authored queue")
        self.assertEqual(state.get(marker), 1)

        # A fresh actual source dispatch owns a larger epoch; the old frozen
        # invocation rejects before body and cannot clear the new owner.
        new_dispatch = _sender_dispatch(self, world, row)
        new_epoch = state.get(PREFIX + "_reservation_epoch")
        self.assertGreater(new_epoch, old_epoch)
        self.assertEqual(new_dispatch["scope_context"].get(PREFIX + "_dispatch_epoch"), new_epoch)
        before = _native_fields(world)
        with self.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, old_dispatch)
        self.assertEqual(_native_fields(world), before)
        self.assertEqual(state.get(PREFIX + "_reservation"), ident)
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), new_epoch)
        self.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)

        # Complete fresh body and real sender/body receipt joins through ACK.
        served_before = _served_snapshot(world)
        actual.run_queued_inline_event_immediate(world, new_dispatch)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), new_epoch)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), new_epoch)
        self.assertEqual(state.get(PREFIX + "_callback_epoch_" + str(ident)), new_epoch)
        self.assertNotIn(queue, state)
        self.assertEqual(state.get(marker), 1, "successful 36 notice ACK preserves its native postmarker")
        self.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        self.assertNotEqual(_served_snapshot(world), served_before)

        # Retry again only after natural expiry. Queue setup here is an explicit
        # source-callsite fixture; dispatch, epochs, proofs, body and ACK remain
        # entirely sourced from the authored commands.
        world.advance_days(91)
        world.run(PREFIX + "_prepare", TAG)
        self.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
        self.assertNotIn(PREFIX + "_reservation", state)
        self.assertEqual(state.get(marker), 1)
        state[queue] = row["candidate"]["value"]
        second_dispatch = _sender_dispatch(self, world, row)
        second_epoch = second_dispatch["scope_context"][PREFIX + "_dispatch_epoch"]
        self.assertGreater(second_epoch, new_epoch)
        self.assertEqual(state.get(marker), 1)
        actual.run_queued_inline_event_immediate(world, second_dispatch)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), second_epoch)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), second_epoch)
        self.assertEqual(state.get(PREFIX + "_callback_epoch_" + str(ident)), second_epoch)
        self.assertNotIn(queue, state)
        self.assertEqual(state.get(marker), 1)
if __name__ == "__main__":
    unittest.main()

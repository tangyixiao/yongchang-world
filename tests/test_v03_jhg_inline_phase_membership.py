"""Actual journal membership must remain part of every owned JHG phase."""

import unittest

from tests import test_v03_jhg_inline_actual_source as actual
from tests import test_v03_jhg_inline_adapter as binding
from tests.test_v03_jhg_inline_provenance import (
    COOLDOWN,
    PREFIX,
    TAG,
    _one_real_dispatch,
)
from tests.test_v03_jhg_inline_queue_snapshots import _complete_state_snapshot


class JhgInlinePhaseMembership(unittest.TestCase):
    def test_missing_journal_before_body_fails_without_mutation(self):
        """A real dispatch loses JE membership before body entry and stays inert."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        journal = row["branch"]["journal"]
        queue = row["candidate"]["queue"]
        state = world.countries[TAG]
        witness = binding.assert_inline_supported(self)["live_witnesses"][journal]

        self.assertTrue(world.journal_is_active(TAG, journal))
        self.assertEqual(state.get(witness), 1)
        self.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"), ident)
        self.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_epoch"), epoch)
        world.journals = [entry for entry in world.journals
                          if not (entry[0] == TAG and
                                  dict((name, value) for name, _, value in entry[1]).get("type") == journal)]
        self.assertFalse(world.journal_is_active(TAG, journal))
        self.assertEqual(state.get(witness), 1, "witness remains after JE membership is removed")
        before = _complete_state_snapshot(world)

        with self.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)

        self.assertEqual(_complete_state_snapshot(world), before)
        self.assertEqual(state.get(witness), 1)
        self.assertEqual(state.get(queue), row["candidate"]["value"])
        self.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)
        self.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
        self.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"), ident)
        self.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_epoch"), epoch)

    def test_missing_journal_at_ack_preserves_full_body_boundary(self):
        """Membership lost at the real pre-ACK seam prevents only the ACK."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        journal = row["branch"]["journal"]
        queue = row["candidate"]["queue"]
        state = world.countries[TAG]
        witness = binding.assert_inline_supported(self)["live_witnesses"][journal]
        before_ack = []

        def remove_membership(current, name, tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            self.assertTrue(current.journal_is_active(tag, journal))
            current.journals = [entry for entry in current.journals
                                if not (entry[0] == tag and
                                        dict((field, value) for field, _, value in entry[1]).get("type") == journal)]
            self.assertFalse(current.journal_is_active(tag, journal))
            self.assertEqual(current.countries[tag].get(witness), 1)
            before_ack.append(_complete_state_snapshot(current))

        with actual.observe_actual_owned_ack(world, remove_membership):
            actual.run_queued_inline_event_immediate(world, dispatch)

        self.assertEqual(len(before_ack), 1)
        self.assertEqual(_complete_state_snapshot(world), before_ack[0])
        self.assertFalse(world.journal_is_active(TAG, journal))
        self.assertEqual(state.get(witness), 1)
        self.assertEqual(state.get(queue), row["candidate"]["value"])
        self.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_{ident}"), 1)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_{ident}"), 1)
        self.assertEqual(state.get(f"{PREFIX}_sender_completed_epoch_{ident}"), epoch)
        self.assertEqual(state.get(f"{PREFIX}_reservation"), ident)

    def test_natural_reservation_expiry_before_body_rejects_queued_context(self):
        """Native clock expiry invalidates a frozen queued event before cleanup runs."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        queue = row["candidate"]["queue"]
        state = world.countries[TAG]
        timer = f"{PREFIX}_timer"
        self.assertEqual(state.get(PREFIX + "_reservation"), ident)
        self.assertEqual(state.get(PREFIX + "_reservation_epoch"), epoch)
        self.assertEqual(world.days_until_expiry[TAG].get(timer), 90)

        world.advance_days(91)
        self.assertNotIn(timer, world.days_until_expiry[TAG])
        self.assertEqual(state.get(PREFIX + "_reservation"), ident,
                         "natural expiry has elapsed before a later prepare cleanup")
        before = _complete_state_snapshot(world)
        with self.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)

        self.assertEqual(_complete_state_snapshot(world), before)
        self.assertEqual(state.get(queue), row["candidate"]["value"])
        self.assertNotIn(f"{PREFIX}_body_completed_{ident}", state)
        self.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_candidate"), ident)
        self.assertEqual(dispatch["scope_context"].get(PREFIX + "_dispatch_epoch"), epoch)

    def test_natural_expiry_at_pre_ack_preserves_native_and_private_boundary(self):
        """Expiry at the real ACK seam blocks ACK without native rollback."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        queue = row["candidate"]["queue"]
        timer = f"{PREFIX}_timer"
        before_ack = []

        def expire_at_ack(current, name, _tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            self.assertEqual(current.days_until_expiry[TAG].get(timer), 90)
            self.assertEqual(current.days_until_expiry[TAG].get(COOLDOWN), 90)
            current.advance_days(91)
            self.assertNotIn(timer, current.days_until_expiry[TAG])
            self.assertNotIn(COOLDOWN, current.days_until_expiry[TAG])
            self.assertEqual(current.countries[TAG].get(f"{PREFIX}_reservation"), ident)
            self.assertEqual(current.countries[TAG].get(queue), row["candidate"]["value"])
            before_ack.append(_complete_state_snapshot(current))

        with actual.observe_actual_owned_ack(world, expire_at_ack):
            actual.run_queued_inline_event_immediate(world, dispatch)

        self.assertEqual(len(before_ack), 1)
        self.assertEqual(_complete_state_snapshot(world), before_ack[0])
        self.assertEqual(world.countries[TAG].get(queue), row["candidate"]["value"])
        self.assertEqual(world.countries[TAG].get(f"{PREFIX}_reservation"), ident)
        self.assertEqual(world.countries[TAG].get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)

    def test_body_receipt_blocks_replay_before_ack_without_cooldown(self):
        """Body completion, not incidental cooldown, owns exact-once entry."""
        actual.assert_inline_supported(self)
        world, _evidence, dispatch, row, ident, epoch = _one_real_dispatch(self)
        queue = row["candidate"]["queue"]
        state = world.countries[TAG]

        class StopBeforeAck(Exception):
            pass

        def stop_at_ack(_current, name, _tag):
            self.assertEqual(name, f"{PREFIX}_ack_{ident}")
            raise StopBeforeAck

        with actual.observe_actual_owned_ack(world, stop_at_ack):
            with self.assertRaises(StopBeforeAck):
                actual.run_queued_inline_event_immediate(world, dispatch)

        self.assertEqual(state.get(f"{PREFIX}_body_completed_{ident}"), 1)
        self.assertEqual(state.get(f"{PREFIX}_body_completed_epoch_{ident}"), epoch)
        self.assertEqual(state.get(f"{PREFIX}_reservation"), ident)
        self.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN), 90)
        self.assertEqual(state.get(COOLDOWN), 1)
        self.assertEqual(state.get(queue), row["candidate"]["value"])

        state.pop(COOLDOWN, None)
        world.days_until_expiry[TAG].pop(COOLDOWN, None)
        fault_time = _complete_state_snapshot(world)
        with self.assertRaises(ValueError):
            actual.run_queued_inline_event_immediate(world, dispatch)

        self.assertEqual(_complete_state_snapshot(world), fault_time)
        self.assertNotIn(COOLDOWN, state)
        self.assertNotIn(COOLDOWN, world.days_until_expiry[TAG])
        self.assertEqual(state.get(queue), row["candidate"]["value"])


if __name__ == "__main__":
    unittest.main()

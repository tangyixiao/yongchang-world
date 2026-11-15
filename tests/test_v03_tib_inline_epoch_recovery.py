"""Allocator recovery faults over actual source-only TIB transactions.

These cases fault only the current counter, age the real lease, and run the
complete authored sender chain without monthly_review. They establish that
lost counter history cannot recreate custody; they are not body-receipt or
naturally scheduled campaign claims. No positive proof or nonce is planted.
"""
from __future__ import annotations

import unittest

from tests.test_v03_tib_inline_provenance import (
    TAG, PREFIX, representative_rows, source_only, lease_duration, full_snapshot,
    dispatch_source, reject_or_inert_body, run_frozen, helper, supported, pv,
)


class TibInlineEpochRecovery(unittest.TestCase):
    def _assert_counter_recovery_rejects_new_custody(self, fault):
        supported(self)
        row = next(row for row in representative_rows()
                   if row['branch']['journal'] == 'ywc_je_v03_tib_register_1')
        initial = source_only(self, row)
        world, old_dispatch = initial['world'], initial['dispatch']
        state = world.countries[TAG]
        counter = PREFIX + '_epoch'
        selected = row['candidate']['queue']
        self.assertGreater(initial['epoch'], 0)
        self.assertEqual(state[counter], initial['epoch'])
        self.assertEqual(old_dispatch['scope_context'][PREFIX+'_dispatch_epoch'], initial['epoch'])
        self.assertEqual(state[helper('source_completed', row['id'])], 1)
        self.assertEqual(state[helper('source_completed_epoch', row['id'])], initial['epoch'])
        self.assertEqual(pv(state, selected), (True, row['candidate']['value']))
        timer, duration = lease_duration(world)

        # This is the sole identity fault. Actual elapsed time and prepare then
        # release old custody while native pending work must survive.
        if fault == 'zero':
            state[counter] = 0
        else:
            self.assertEqual(fault, 'missing')
            state.pop(counter)
        malformed = pv(state, counter)
        world.advance_days(duration)
        self.assertNotIn(timer, world.days_until_expiry[TAG])
        world.run(PREFIX+'_prepare', TAG)
        self.assertNotIn(PREFIX+'_reservation', state)
        self.assertEqual(pv(state, counter), malformed)
        self.assertEqual(pv(state, selected), (True, row['candidate']['value']))

        faulttime = full_snapshot(world)
        result = dispatch_source(self, world, row, chain=True)
        self.assertEqual(result['dispatches'], [],
                         'malformed initialized counter must reject the whole sender before reservation or native pre')
        self.assertEqual(full_snapshot(world), faulttime)
        self.assertEqual(pv(state, counter), malformed)

        reject_or_inert_body(self, world, old_dispatch)
        for kind in ('source_return', 'body_return', 'callback', 'join', 'ack'):
            run_frozen(world, old_dispatch, helper(kind, row['id']))
        self.assertEqual(full_snapshot(world), faulttime)
        self.assertEqual(pv(state, selected), (True, row['candidate']['value']))

    def test_zero_current_epoch_recovery_is_fail_closed(self):
        self._assert_counter_recovery_rejects_new_custody('zero')

    def test_missing_current_epoch_recovery_is_fail_closed(self):
        self._assert_counter_recovery_rejects_new_custody('missing')


if __name__ == '__main__':
    unittest.main()

"""Strict sender/receipt controls for LAN beyond-gold integration."""
import copy
import json
from pathlib import Path
import unittest

from tools.v03_inline_delivery_adapter import (
    _lan_active_arcs, _lan_native_receipt, _lan_queue_candidates, _lan_source_binding,
    _validate_lan_inline_catalog,
)

ROOT = Path(__file__).resolve().parents[1]


class LanGoldAdapterControls(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads((ROOT / 'data/content/v03/countries/lan.json').read_text(encoding='utf-8'))
        self.gold = next(arc for arc in self.catalog['arcs'] if arc['slug'] == 'v03_lan_beyond_gold')

    def test_registered_arc_preserves_the_four_existing_arcs(self):
        active = _lan_active_arcs(self.catalog)
        self.assertEqual([arc['slug'] for arc in active], [arc['slug'] for arc in self.catalog['arcs']])
        wrong = copy.deepcopy(self.catalog)
        wrong['arcs'][-1]['slug'] = 'v03_lan_unregistered'
        with self.assertRaises(ValueError):
            _lan_active_arcs(wrong)

    def test_only_exact_owned_queue_is_a_sender_candidate(self):
        candidate = 'if = { limit = { var:ywc_lan_gold_pending_event = 1126 } trigger_event = { id = ywc_lan.1126 } }'
        self.assertEqual(_lan_queue_candidates(candidate), [
            {'queue': 'ywc_lan_gold_pending_event', 'kind': 'normal', 'mode': 'exact', 'value': 1126}])
        for bad in (candidate.replace(' = 1126', ' >= 1126'),
                    candidate.replace('ywc_lan_gold_pending_event', 'ywc_lan_foreign_pending_event'),
                    candidate.replace('var:ywc_lan_gold_pending_event = 1126', 'always = yes')):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _lan_queue_candidates(bad)

    def test_each_native_receipt_requires_exact_event_identity(self):
        for index, event in enumerate(self.gold['events'], 1):
            with self.subTest(event=event['id']):
                self.assertEqual(_lan_native_receipt(event),
                                 ('ywc_v03_lan_v03_lan_beyond_gold_last_event', index))
                corrupted = copy.deepcopy(event)
                corrupted['immediate'] = corrupted['immediate'].replace(f'value = {index}', 'value = 99')
                with self.assertRaises(ValueError):
                    _lan_native_receipt(corrupted)

    def test_actual_senders_and_frozen_catalog_binding(self):
        sites = [[row['event'] for row in _lan_source_binding(j['id'], j['script'])['branches']]
                 for j in self.gold['journals']]
        self.assertEqual(sites, [
            ['ywc_lan.1126', 'ywc_lan.1120', 'ywc_lan.1121', 'ywc_lan.1122', 'ywc_lan.1123', 'ywc_lan.1124'],
            ['ywc_lan.1126', 'ywc_lan.1125', 'ywc_lan.1126', 'ywc_lan.1127'],
        ])
        _validate_lan_inline_catalog(self.catalog)
        for change in ('immediate', 'sender', 'extra_operation'):
            modified = copy.deepcopy(self.catalog)
            arc = modified['arcs'][-1]
            if change == 'immediate':
                arc['events'][0]['immediate'] = arc['events'][0]['immediate'].replace('value = 1', 'value = 2')
            elif change == 'sender':
                arc['journals'][0]['script'] = arc['journals'][0]['script'].replace(
                    'var:ywc_lan_gold_pending_event = 1120', 'var:ywc_lan_gold_pending_event = 1121', 1)
            else:
                arc['journals'][1]['script'] = arc['journals'][1]['script'].replace(
                    'remove_variable = ywc_lan_gold_observation_waiting trigger_event',
                    'remove_variable = ywc_lan_gold_seed_paid trigger_event', 1)
            with self.subTest(change=change), self.assertRaises(ValueError):
                _validate_lan_inline_catalog(modified)

    def test_review_waiting_is_acknowledged_or_restored_after_failed_delivery(self):
        from shu_kor_strict_review_runtime import field
        from test_v03_lan_beyond_gold import new_world, gold_arc, reach_review, month, choose

        world = new_world()
        arc = reach_review(world)
        state = world.countries[world.tag]
        month(world, arc, 6)
        review = world.deliver(arc, 'ywc_lan.1125')
        choose(world, arc, review, 'wait_observation')
        self.assertEqual(state['ywc_lan_gold_observation_waiting'], 1)
        for _ in range(12):
            world.advance_months(1)
            world.pulse(arc)
            if world.events:
                break
        self.assertTrue(world.events)
        self.assertEqual(world.events[0][1], 'ywc_lan.1125')
        ident = int(state['ywc_v03_lan_inline_reservation'])
        self.assertNotIn('ywc_lan_gold_observation_waiting', state)
        snapshot = f'ywc_v03_lan_inline_c{ident}_ywc_lan_gold_observation_waiting_present'
        self.assertEqual(state[snapshot], 1)

        valid = copy.deepcopy(world)
        expired = copy.deepcopy(world)
        expired_state = expired.countries[expired.tag]
        expired_state.pop('ywc_v03_lan_inline_timer', None)
        expired.run('ywc_v03_lan_inline_prepare', expired.tag)
        self.assertEqual(expired_state['ywc_lan_gold_observation_waiting'], 1)
        self.assertNotIn('ywc_v03_lan_inline_reservation', expired_state)
        changed = copy.deepcopy(world)
        changed_state = changed.countries[changed.tag]
        changed_state['ywc_lan_gold_observation_waiting'] = 2
        changed_state.pop('ywc_v03_lan_inline_timer', None)
        changed.run('ywc_v03_lan_inline_prepare', changed.tag)
        self.assertEqual(changed_state['ywc_lan_gold_observation_waiting'], 2)
        event = world.event_defs['ywc_lan.1125']
        fault = copy.deepcopy(field(event, 'immediate'))
        changed = []
        def corrupt(nodes):
            for key, _, value in nodes:
                if key == 'set_variable' and isinstance(value, list) and field(value, 'name') == 'ywc_v03_lan_v03_lan_beyond_gold_last_event':
                    for i, child in enumerate(value):
                        if child[0] == 'value':
                            value[i] = ('value', '=', '0')
                            changed.append(True)
                if isinstance(value, list):
                    corrupt(value)
        corrupt(fault)
        self.assertEqual(len(changed), 1)
        world.execute(fault, world.tag)
        self.assertEqual(state['ywc_v03_lan_inline_reservation'], ident)
        state.pop('ywc_v03_lan_inline_timer', None)
        world.run('ywc_v03_lan_inline_prepare', world.tag)
        # A displayed body must not be rolled back even if its receipt is bad.
        self.assertNotIn('ywc_lan_gold_observation_waiting', state)
        self.assertNotIn('ywc_v03_lan_inline_reservation', state)

        valid.execute(field(event, 'immediate'), valid.tag)
        actual = valid.countries[valid.tag]
        self.assertNotIn('ywc_v03_lan_inline_reservation', actual)
        self.assertNotIn('ywc_lan_gold_observation_waiting', actual)


if __name__ == '__main__':
    unittest.main()

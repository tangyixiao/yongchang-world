"""Source-structural obligations for the new TIB public-revenue card.

These are necessary checks, not a substitute for executing actual stories,
fees, old-history influence or native scheduling after source handoff.
"""
import json
from pathlib import Path
import unittest

from tests.clausewitz_harness import parse
from tools.v03_inline_delivery_adapter import parse_block

ROOT = Path(__file__).resolve().parents[1]
SLUG = 'v03_tib_public_revenue'


def walk(nodes):
    for key, op, value in nodes:
        yield key, op, value
        if isinstance(value, list):
            yield from walk(value)


def body_of_option(option):
    source = option['effect'].strip()
    if not (source.startswith('{') and source.endswith('}')):
        raise AssertionError(('effect is not a script block', option.get('key')))
    parse_block(source)
    return parse(source[1:-1])


class TibRevenueStructureContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        catalog = json.loads((ROOT / 'data/content/v03/countries/tib.json').read_text(encoding='utf-8-sig'))
        matches = [a for a in catalog['arcs'] if a.get('slug') == SLUG]
        if len(matches) != 1:
            raise AssertionError(f'{SLUG}: expected exactly one actual source arc, got {len(matches)}')
        cls.arc = matches[0]
        mod = ROOT / 'yongchang_world'
        effect_source = (mod / 'common/scripted_effects/ywc_v03_tib_effects.txt').read_text(encoding='utf-8-sig')
        trigger_source = (mod / 'common/scripted_triggers/ywc_v03_tib_triggers.txt').read_text(encoding='utf-8-sig')
        cls.effects = {k: v for k, _, v in parse(effect_source)}
        cls.triggers = {k: v for k, _, v in parse(trigger_source)}

    def test_ten_reserved_events_and_three_distinct_native_journals(self):
        events = self.arc['events']
        self.assertEqual(len(events), 10)
        self.assertEqual({e['id'] for e in events}, {f'ywc_tib.{n}' for n in range(1120, 1130)})
        journals = self.arc['journals']
        self.assertEqual(len(journals), 3)
        self.assertEqual(len({j['id'] for j in journals}), 3)
        for journal in journals:
            for field in ('script', 'goal', 'exit_conditions'):
                with self.subTest(journal=journal['id'], field=field):
                    self.assertIsInstance(journal.get(field), str)
                    self.assertTrue(journal[field].strip())
                    parse_block(journal[field])

    def test_each_event_has_choices_and_real_parseable_source_effects(self):
        for event in self.arc['events']:
            with self.subTest(event=event['id']):
                self.assertTrue(event.get('options'))
                keys = [option['key'] for option in event['options']]
                self.assertEqual(len(keys), len(set(keys)))
                for option in event['options']:
                    self.assertTrue(body_of_option(option), (event['id'], option['key']))
                    if option.get('trigger'):
                        parse_block(option['trigger'])

    def test_new_effects_do_not_force_law_sovereignty_or_create_buildings(self):
        # Only authored revenue helpers and their reachable revenue helpers are
        # inspected: shared helpers and unrelated country scripts are untouched.
        forbidden = {'activate_law', 'set_law', 'change_law', 'enact_law',
                     'create_building', 'create_country', 'transfer_state',
                     'change_state_owner', 'set_owner', 'annex'}
        prefixes = ('ywc_tib_revenue_', 'ywc_v03_tib_revenue_')
        stack = [body_of_option(o) for e in self.arc['events'] for o in e['options']]
        expanded = set()
        while stack:
            for key, op, value in walk(stack.pop()):
                self.assertNotIn(key, forbidden)
                if key.startswith(prefixes) and key in self.effects and key not in expanded:
                    expanded.add(key)
                    stack.append(self.effects[key])

    def test_real_revenue_modifiers_are_defined_and_route_variety_exists(self):
        # Exact magnitude/scope and timing still need real route execution.
        prefixes = ('ywc_tib_revenue_', 'ywc_v03_tib_revenue_')
        refs = set()
        for name, nodes in self.effects.items():
            if not name.startswith(prefixes):
                continue
            for key, _, body in walk(nodes):
                if key == 'add_modifier' and isinstance(body, list):
                    refs.update(v for k, _, v in body if k == 'name' and isinstance(v, str))
        self.assertGreaterEqual(len(refs), 3, 'three routes need distinct actual effects')
        path = ROOT / 'yongchang_world/common/static_modifiers/ywc_v03_tib_modifiers.txt'
        defined = {key for key, _, _ in parse(path.read_text(encoding='utf-8-sig'))}
        self.assertFalse(refs - defined, ('undefined revenue modifiers', sorted(refs - defined)))


if __name__ == '__main__':
    unittest.main()

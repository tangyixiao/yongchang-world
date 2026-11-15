"""New TIB revenue native sender bindings retain a strict source contract."""
import copy
import unittest
from tests.test_v03_tib_revenue_legacy_contract import catalog
from tools.v03_tib_inline_delivery_adapter import annotate_tib_catalog, validate_tib_inline_catalog, render_tib_inline_country_adapters, _binding, _node_refs
from tools.v03_inline_delivery_adapter import parse_block
from tests import test_v03_tib_inline_adapter as old

class TibRevenueInlineBinding(unittest.TestCase):
    def test_all_source_senders_and_event_hooks_are_bound(self):
        candidate = annotate_tib_catalog(catalog())
        validate_tib_inline_catalog(candidate)
        revenue = next(a for a in candidate['arcs'] if a['slug'] == 'v03_tib_public_revenue')
        self.assertEqual(len(revenue['inline_delivery_adapter']['live_phases']), 3)
        self.assertEqual(len(revenue['inline_delivery_adapter']['branches']), 18)
        rendered = render_tib_inline_country_adapters(candidate)
        for number in range(1120, 1130):
            self.assertIn(f'ywc_tib.{number}', rendered['event_hooks'])
        self.assertEqual(len(rendered['live_witnesses']), 9)

    def test_all_revenue_callbacks_require_owned_receipts_and_snapshots(self):
        candidate = annotate_tib_catalog(catalog())
        rendered = render_tib_inline_country_adapters(candidate)
        effects = old._builder_defs(rendered['effects'])
        rows, names = [], set()
        for arc in candidate['arcs']:
            for journal in arc['journals']:
                for row in _binding(journal['id'], journal['script']):
                    rows.append((len(rows) + 1, arc, journal, row))
                    raw = journal['script'][row['start']:row['end']]
                    names.update(_node_refs((parse_block('{ ' + raw + ' }')[0],)))
        self.assertEqual(len(names), 16)
        revenue_rows = [row for row in rows if row[1]['slug'] == 'v03_tib_public_revenue']
        self.assertEqual(len(revenue_rows), 18)
        prefix = 'ywc_v03_tib_inline_'
        for ident, arc, journal, branch in revenue_rows:
            with self.subTest(journal=journal['id'], ident=ident):
                q = branch['candidates'][0]['queue']
                value = branch['candidates'][0]['value']
                witness = rendered['live_witnesses'][journal['id']]
                callback = f'{prefix}callback_{ident}'
                join = f'{prefix}join_{ident}'
                ack = f'{prefix}ack_{ident}'
                old._assert_callback_contract(self, effects[callback], callback, ident, q, value, witness, [])
                old._assert_receipt_join(self, effects[join], join, ident, q, value, witness, [])
                old._assert_ack_guard(self, effects[ack], ack, ident, q, value, witness, [])
                mapping = {name: (f'{prefix}snapshot_{ident}_{name.removeprefix("ywc_tib_")}_present',
                                  f'{prefix}snapshot_{ident}_{name.removeprefix("ywc_tib_")}_value') for name in names}
                old._assert_complete_native_snapshots(self, effects[join], mapping, join)
                old._assert_complete_native_snapshots(self, effects[ack], mapping, ack)

    def test_tampered_revenue_journal_rejected(self):
        candidate = annotate_tib_catalog(catalog())
        revenue = next(a for a in candidate['arcs'] if a['slug'] == 'v03_tib_public_revenue')
        revenue['journals'][0]['goal'] = '{ always = yes }'
        with self.assertRaises(ValueError):
            validate_tib_inline_catalog(candidate)

if __name__ == '__main__': unittest.main()

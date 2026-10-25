"""Legal native event comments must survive actual TIB event-file wrapping."""
from __future__ import annotations

import copy
import unittest

from tools import build_v03_content
from tools.v03_inline_delivery_adapter import (
    children, direct_values, parse_block, validate_inline_catalog,
    render_inline_country_adapters,
)
from tests.test_v03_tib_inline_adapter import (
    ROOT, _v2_catalog_from_formal_tib_source, assert_inline_supported, _rows,
)


class TibInlineEventComments(unittest.TestCase):
    def _complete_file(self, candidate, adapter):
        text = build_v03_content._render_event_file(candidate, ROOT, adapter)
        try:
            nodes = parse_block('{\n' + text + '\n}')
        except ValueError as exc:
            self.fail(f'actual complete generated event file is malformed: {exc}')
        definitions = {node.key: node for node in nodes}
        self.assertEqual(len(definitions), len(nodes), 'no duplicate output definitions')
        event_ids = {event['id'] for arc in candidate['arcs'] for event in arc['events']}
        self.assertEqual(len(event_ids), 24)
        self.assertEqual(set(definitions), event_ids | {'namespace'})
        return nodes, definitions

    def _assert_full_event_protocol(self, event, definition, adapter):
        fields = children(definition)
        immediate = direct_values(fields, 'immediate')
        self.assertEqual(len(immediate), 1)
        body = children(immediate[0])
        self.assertEqual(len(body), 1)
        self.assertEqual(body[0].key, 'if')
        guarded = children(body[0])
        self.assertEqual(guarded[0].key, 'limit')
        hooks = adapter['event_hooks'][event['id']]
        expected_gate = parse_block('{ OR = { ' + ' '.join(name+' = yes' for name in hooks) + ' } }')
        self.assertEqual(_rows(guarded[0]), _rows(expected_gate))
        native = parse_block(event['immediate'])
        self.assertEqual(_rows(guarded[1:1+len(native)]), _rows(native), 'complete full native B prefix')
        suffix = parse_block('{ ' + ' '.join(adapter['inline_proofs'][event['id']]) + ' ' +
            ' '.join(name+' = yes' for name in adapter['ack_hooks'][event['id']]) + ' }')
        self.assertTrue(suffix, 'real body receipt and callback suffix')
        self.assertEqual(_rows(guarded[1+len(native):]), _rows(suffix), 'body_return before every callback')

    def _assert_trailing_comments(self, field):
        baseline_adapter = assert_inline_supported(self)
        candidate = _v2_catalog_from_formal_tib_source()
        validate_inline_catalog(candidate)
        self.assertEqual(render_inline_country_adapters(candidate), baseline_adapter)
        pristine_nodes, pristine_defs = self._complete_file(candidate, baseline_adapter)
        events = [event for arc in candidate['arcs'] for event in arc['events']]
        self.assertEqual(len(events), 24)
        for event in events:
            self._assert_full_event_protocol(event, pristine_defs[event['id']], baseline_adapter)
        checked = 0
        for event in events:
            with self.subTest(event=event['id'], field=field):
                mutant = copy.deepcopy(candidate)
                changed = next(item for arc in mutant['arcs'] for item in arc['events']
                               if item['id'] == event['id'])
                source = changed[field]
                closing = source.rfind('}')
                self.assertGreaterEqual(closing, 0)
                changed[field] = source[:closing] + ' # legal trailing comment\n' + source[closing:]
                self.assertEqual(_rows(parse_block(changed[field])), _rows(parse_block(source)))
                validate_inline_catalog(mutant)
                actual_adapter = render_inline_country_adapters(mutant)
                self.assertEqual(actual_adapter, baseline_adapter, 'native comments cannot change helper protocol')
                actual_nodes, actual_defs = self._complete_file(mutant, actual_adapter)
                self.assertEqual(_rows(actual_nodes), _rows(pristine_nodes),
                                 'whole output AST including namespace, triggers, native bodies, receipts, callbacks and options')
                self._assert_full_event_protocol(event, actual_defs[event['id']], actual_adapter)
                checked += 1
        self.assertEqual(checked, 24)

    def test_all_24_trigger_trailing_comments_preserve_complete_generated_event_file(self):
        self._assert_trailing_comments('trigger')

    def test_all_24_immediate_trailing_comments_preserve_full_native_body_receipts_and_callbacks(self):
        self._assert_trailing_comments('immediate')


if __name__ == '__main__':
    unittest.main()

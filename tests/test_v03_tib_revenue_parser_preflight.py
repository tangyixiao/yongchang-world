"""Strict parser preflight: synthetic blocks, no TIB business-source access."""
import unittest
from tools.v03_inline_delivery_adapter import parse_block
from tests.test_v03_tib_revenue_structure import body_of_option, walk


class TibRevenueParserPreflight(unittest.TestCase):
    def test_well_formed_blocks_and_empty_effect(self):
        self.assertTrue(parse_block('{ on_monthly_pulse = { effect = { always = yes } } }'))
        self.assertEqual(body_of_option({'key': 'test', 'effect': '{}'}), [])

    def test_each_missing_or_extra_brace_rejected(self):
        for source in ('{ on_monthly_pulse = { effect = { always = yes } }',
                       '{ if = { limit = { always = yes } }',
                       '{ always = yes } }'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                parse_block(source)

    def test_quoted_braces_and_comment_braces_are_not_structural(self):
        self.assertTrue(parse_block('{ value = "literal } {" # ignored {\n always = yes }'))

    def test_walker_reaches_nested_forbidden_primitive(self):
        effect = body_of_option({'key': 'x', 'effect': '{ if = { limit = { always = yes } create_building = { type = building_x } } }'})
        self.assertIn('create_building', {name for name, _, _ in walk(effect)})


if __name__ == '__main__': unittest.main()

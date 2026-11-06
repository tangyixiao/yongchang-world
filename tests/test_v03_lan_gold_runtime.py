"""Literal controls for the LAN actual-source interpreter's building scope."""
import unittest
from pathlib import Path

from lan_gold_runtime import LanGoldWorld
from shu_kor_strict_review_runtime import facts


class LanGoldBuildingLevel(unittest.TestCase):
    def setUp(self):
        self.world = LanGoldWorld(countries={'LAN': facts()})

    def test_level_compares_the_current_building_only(self):
        self.world.building_scope = {'level': 2}
        self.assertTrue(self.world.condition(('level', '>=', '2'), 'LAN'))
        self.assertFalse(self.world.condition(('level', '>=', '3'), 'LAN'))
        self.assertTrue(self.world.condition(('level', '<', '3'), 'LAN'))

    def test_level_requires_a_valid_building_fact_and_operator(self):
        for building, op, value in ((None, '>=', '1'), ({}, '>=', '1'),
                                     ({'level': True}, '>=', '1'),
                                     ({'level': 2}, '?=', '1'),
                                     ({'level': 2}, '>=', 'no')):
            with self.subTest(building=building, op=op, value=value):
                self.world.building_scope = building
                with self.assertRaises((AssertionError, ValueError)):
                    self.world.condition(('level', op, value), 'LAN')

    def test_each_split_route_modifier_has_bilingual_names_and_descriptions(self):
        root = Path(__file__).resolve().parents[1]
        for language, filename in (
            ('english', 'ywc_v03_lan_modifiers_l_english.yml'),
            ('simp_chinese', 'ywc_v03_lan_modifiers_l_simp_chinese.yml'),
        ):
            text = (root / 'yongchang_world' / 'localization' / language / filename).read_text(encoding='utf-8-sig')
            for route in ('processing', 'farming', 'monopoly', 'compromise'):
                for scope in ('country', 'state'):
                    key = f'ywc_lan_gold_{route}_{scope}'
                    with self.subTest(language=language, key=key):
                        self.assertIn(f' {key}:0 ', text)
                        self.assertIn(f' {key}_desc:0 ', text)


if __name__ == '__main__':
    unittest.main()

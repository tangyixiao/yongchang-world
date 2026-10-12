"""Contracts for the user's 1836 fragmentation and Ladakh support request."""
import json
from pathlib import Path
import re
import unittest

from tools.build_state_history import balanced_end, extract_groups, state_blocks
from tools.ownership_topology import _state_adjacency, component_sizes

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / 'yongchang_world'
KHAM = {'KAM', 'DER', 'CHD', 'HOR', 'LTG'}
CENTRAL = {'TSK', 'KIR', 'SMR', 'KRS', 'KGL', 'MEV', 'AKS'}


class FrontierFragmentationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads((ROOT / 'data/baseline/vic3-1.13.11.json').read_text('utf-8'))
        cls.blocks = state_blocks((MOD / 'common/history/states/00_states.txt').read_text('utf-8-sig'), cls.baseline)
        cls.owners = {}
        for state, block in cls.blocks.items():
            for group in extract_groups(block):
                cls.owners.setdefault(group['owner'], set()).update(group['owned_provinces'])

    def test_kham_is_five_starting_countries_and_central_asia_has_seven_more(self):
        for tag in KHAM | CENTRAL:
            self.assertTrue(self.owners.get(tag), f'{tag} has no starting territory')
        southwest = json.loads((ROOT / 'data/scenario/southwest_states.json').read_text('utf-8'))
        self.assertTrue(KHAM <= set(southwest['starting_tags']))
        self.assertNotIn('DER', southwest['releasable_tags'])

    def test_new_borders_are_connected_and_lhasa_is_retained(self):
        import numpy as np
        from PIL import Image
        pool = set().union(*(self.owners.get(tag, set()) for tag in KHAM | CENTRAL | {'TIB', 'KUC', 'KHI', 'BUK', 'KOK'}))
        image = np.asarray(Image.open('E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png').convert('RGB'), dtype=np.uint32)
        encoded = image[:, :, 0]*65536 + image[:, :, 1]*256 + image[:, :, 2]
        adjacency = _state_adjacency(pool, encoded, np)
        for tag in KHAM | CENTRAL | {'TIB', 'KUC', 'KHI', 'BUK'}:
            self.assertEqual(component_sizes(self.owners.get(tag, set()), adjacency), [len(self.owners.get(tag, set()))], tag)
        self.assertIn('x06698A', self.owners['TIB'])

    def test_tib_name_changes_in_both_languages_without_changing_tag(self):
        registry = json.loads((ROOT / 'data/scenario/tag_registry.json').read_text('utf-8'))
        tib = next(r for r in registry['countries'] if r['tag'] == 'TIB')
        self.assertEqual((tib['name_zh'], tib['mode'], tib['source_tag']), ('甘丹颇章', 'reuse', 'TIB'))
        for language, name in [('simp_chinese', '甘丹颇章'), ('english', 'Ganden Phodrang')]:
            text = '\n'.join(p.read_text('utf-8-sig') for p in (MOD / 'localization' / language).rglob('*.yml'))
            self.assertRegex(text, rf'(?m)^ TIB:0 "{name}"$')

    def test_ladakh_war_has_tibet_on_defending_side_and_keeps_original_demands(self):
        path = MOD / 'common/history/diplomatic_plays/00_ladakh_war.txt'
        self.assertTrue(path.exists())
        text = path.read_text('utf-8-sig')
        self.assertIn('target_state = s:STATE_KASHMIR.region_state:LAD', text)
        self.assertIn('add_target_backers = { c:TIB }', text)
        self.assertIn('war = yes', text)
        self.assertIn('holder = c:LAD', text)
        self.assertIn('target_country = c:KAS', text)
        self.assertEqual(text.count('create_diplomatic_play ='), 1)

    def test_new_countries_have_owned_capitals_and_armies(self):
        definitions = (MOD / 'common/country_definitions/ywc_regional_countries.txt').read_text('utf-8-sig')
        history = (MOD / 'common/history/countries/ywc_regional_countries.txt').read_text('utf-8-sig')
        formations = (MOD / 'common/history/military_formations/ywc_regional_military_formations.txt').read_text('utf-8-sig')
        for tag in CENTRAL | KHAM - {'KAM', 'DER'}:
            capital = re.search(r'(?m)^'+tag+r'\s*=\s*\{[^\n]*capital\s*=\s*(STATE_[A-Z_]+)', definitions).group(1)
            self.assertIn(tag, {g['owner'] for g in extract_groups(self.blocks[capital])})
            self.assertIn('c:'+tag+' ?=', history)
            self.assertIn('c:'+tag+' ?=', formations)

    def test_split_population_is_conserved(self):
        manifest = ROOT / 'data/scenario/frontier_fragmentation.json'
        self.assertTrue(manifest.exists())
        data = json.loads(manifest.read_text('utf-8'))
        corrections = json.loads((ROOT/'data/scenario/geographic_corrections.json').read_text('utf-8'))
        latest = json.loads((ROOT/'data/scenario/border_refinement.json').read_text('utf-8'))
        northern = json.loads((ROOT/'data/scenario/northern_expansion_manifest.json').read_text('utf-8'))
        current_ownership = json.loads((ROOT/'data/scenario/ownership_overrides.json').read_text('utf-8'))
        replaced = {r['state'] for r in latest['population_totals']}
        northern_states = {r['state'] for r in northern['population_totals']}
        replaced |= northern_states
        corrections['population_totals'] = (
            [r for r in corrections['population_totals'] if r['state'] not in replaced]
            + [r for r in latest['population_totals'] if r['state'] not in northern_states]
        )
        changed = {r['state'] for r in corrections['population_totals']}
        rows = ([r for r in data['population_totals'] if r['state'] not in changed | northern_states]
                + corrections['population_totals'] + northern['population_totals'])
        current_groups = {r['state']: r['groups'] for r in current_ownership['states']}
        for row in rows:
            owners = row.get('owners') or [group['owner'] for group in current_groups[row['state']]]
            total = 0
            for path in (MOD / 'common/history/pops').glob('*.txt'):
                text = path.read_text('utf-8-sig')
                for match in re.finditer(r'\bs:'+row['state']+r'\s*=\s*\{', text):
                    opening = text.index('{', match.start(), match.end())
                    block = text[opening:balanced_end(text, opening)+1]
                    for region in re.finditer(r'region_state:([A-Z]{3})\s*=\s*\{', block):
                        if region.group(1) not in owners:
                            continue
                        start = block.index('{', region.start(), region.end())
                        pop = block[start:balanced_end(block, start)+1]
                        total += sum(map(int, re.findall(r'\bsize\s*=\s*(\d+)', pop)))
            self.assertEqual(total, row['before'], row['state'])


if __name__ == '__main__':
    unittest.main()

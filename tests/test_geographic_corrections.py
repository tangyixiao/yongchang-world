"""Regression contracts for names, the Li house, and researched borders."""
import json
from pathlib import Path
import re
import unittest

from tools.build_state_history import balanced_end, extract_groups, state_blocks
from tools.ownership_topology import _state_adjacency, component_sizes

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT/'yongchang_world'


class NameAndHouseTest(unittest.TestCase):
    def test_tib_overrides_vanilla_keys_in_replace_directories(self):
        for language, label in [('simp_chinese','甘丹颇章'),('english','Ganden Phodrang')]:
            directory = MOD/'localization'/language
            replacement = directory/'replace/ywc_country_overrides_l_{}.yml'.format(language)
            self.assertTrue(replacement.exists())
            self.assertIn(f' TIB:0 "{label}"', replacement.read_text('utf-8-sig'))
            for path in directory.glob('*.yml'):
                self.assertNotRegex(path.read_text('utf-8-sig'), r'(?m)^ TIB(?:_ADJ)?:')

    def test_shun_ruler_and_heir_are_defined_members_of_the_li_house(self):
        templates = MOD/'common/character_templates/ywc_shun_house.txt'
        history = MOD/'common/history/characters/ywc_shun_house.txt'
        self.assertTrue(templates.exists())
        text = templates.read_text('utf-8-sig')
        for key, role in [('ywc_shu_li_dejun','ruler'),('ywc_shu_li_zhaohan','heir')]:
            match = re.search(r'(?m)^'+key+r'\s*=\s*\{', text)
            self.assertIsNotNone(match)
            start=text.index('{',match.start(),match.end())
            block=text[start:balanced_end(text,start)+1]
            self.assertIn('last_name = Li',block)
            self.assertIn(role+' = yes',block)
            self.assertIn('template = '+key,history.read_text('utf-8-sig'))

    def test_successors_keep_the_li_surname_through_native_character_hooks(self):
        path=MOD/'common/on_actions/ywc_shun_house.txt'
        self.assertTrue(path.exists())
        text=path.read_text('utf-8-sig')
        for hook in ['on_new_ruler','on_heir_born']:
            self.assertRegex(text,hook+r'\s*=\s*\{\s*on_actions\s*=\s*\{\s*ywc_shu_keep_li_surname')
        self.assertIn('owner = { c:SHU ?= this }',text)
        self.assertIn('set_last_name = Li',text)


class GeographicBorderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/'data/scenario/geographic_corrections.json').read_text('utf-8'))
        base=json.loads((ROOT/'data/baseline/vic3-1.13.11.json').read_text('utf-8'))
        cls.groups={s:{g['owner']:set(g['owned_provinces']) for g in extract_groups(b)} for s,b in state_blocks((MOD/'common/history/states/00_states.txt').read_text('utf-8-sig'),base).items()}
        cls.owners={}
        for gs in cls.groups.values():
            for tag,ps in gs.items(): cls.owners.setdefault(tag,set()).update(ps)

    def test_named_city_cores_and_russian_towns_remain_in_the_right_country(self):
        cores={('STATE_FERGANA','city'):'TSK',('STATE_FERGANA','farm'):'KOK',
            ('STATE_UZBEKIA','city'):'SMR',('STATE_UZBEKIA','farm'):'BUK',('STATE_UZBEKIA','wood'):'KRS',
            ('STATE_TAJIKISTAN','city'):'HSR',('STATE_KIRGHIZIA','city'):'KIR',
            ('STATE_TIANSHAN','city'):'KSH',('STATE_TIANSHAN','mine'):'AKS',('STATE_TIANSHAN','farm'):'KHT',
            ('STATE_SOUTHERN_MANCHURIA','city'):'SHU',('STATE_NORTHERN_MANCHURIA','city'):'SOL',
            ('STATE_YUNNAN','city'):'SHU',('STATE_GANSU','city'):'HXI'}
        for s in ['STATE_ASTRAKHAN','STATE_SAMARA','STATE_TOBOLSK','STATE_TOMSK']: cores[s,'city']='RUS'
        for (state,role),tag in cores.items():
            province=self.data['city_hubs'][state]['landmarks'][role]
            self.assertIn(province,self.groups[state][tag],f'{state}/{role}: {tag}')
        uralsk= self.data['city_hubs']['STATE_URALSK']['landmarks']['city']
        self.assertIn(uralsk,self.groups['STATE_URALSK']['BYL'],'Uralsk remains within the Bayuly polity')

    def test_new_starting_countries_have_owned_capitals_and_armies(self):
        definitions=(MOD/'common/country_definitions/ywc_regional_countries.txt').read_text('utf-8-sig')
        history=(MOD/'common/history/countries/ywc_geographic_countries.txt').read_text('utf-8-sig')
        armies=(MOD/'common/history/military_formations/ywc_geographic_armies.txt').read_text('utf-8-sig')
        for tag in self.data['new_tags']:
            capital=re.search(r'(?m)^'+tag+r'\s*=\s*\{[^\n]*capital\s*=\s*(STATE_[A-Z_]+)',definitions).group(1)
            self.assertIn(tag,self.groups[capital])
            self.assertIn('c:'+tag+' ?=',history)
            self.assertIn('c:'+tag+' ?=',armies)

    def test_central_oases_and_shun_marches_keep_their_subject_relationships(self):
        text=(MOD/'common/history/diplomacy/ywc_geographic_diplomacy.txt').read_text('utf-8-sig')
        for parent,children in {'SHU':['ODS','CHR','HXI','AMD','DLI','LXJ'],'KOK':['TSK'],'BUK':['SMR','KRS','HSR'],'KHI':['KGL'],'RUS':['BKY']}.items():
            match=re.search(r'c:'+parent+r'\s*\?=\s*\{',text); start=text.index('{',match.start(),match.end())
            body=text[start:balanced_end(text,start)+1]
            for tag in children: self.assertIn('country = c:'+tag,body)
        for tag in ['SHB','QRT','DRZ','TKK','YMD']:
            self.assertNotIn('country = c:'+tag,text)

    def test_mainland_borders_are_connected(self):
        import numpy as np
        from PIL import Image
        tags=set(self.data['new_tags'])|{'SHU','KHQ','HUL','SOL','AMR','AMD','DLI'}
        pool=set().union(*(self.owners[t] for t in tags))
        pixels=np.asarray(Image.open('E:/SteamLibrary/steamapps/common/Victoria 3/game/map_data/provinces.png').convert('RGB'),dtype=np.uint32)
        encoded=pixels[:,:,0]*65536+pixels[:,:,1]*256+pixels[:,:,2]
        adj=_state_adjacency(pool,encoded,np)
        for tag in tags-{'SHU','AMR'}:
            self.assertEqual(component_sizes(self.owners[tag],adj),[len(self.owners[tag])],tag)
        # Two native Amur coastal islands have no raster land adjacency.
        self.assertEqual(component_sizes(self.owners['AMR'],adj),[len(self.owners['AMR'])-2,1,1])
        components=component_sizes(self.owners['SHU'],adj)
        self.assertGreater(components[0]/len(self.owners['SHU']),.98,'Shun mainland must remain contiguous')


if __name__=='__main__':
    unittest.main()

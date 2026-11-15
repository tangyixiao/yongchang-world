"""TIB revenue exact-site source contract using typed live StateRef objects."""
import copy
import json
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from kor_partner_protocol_runtime import PartnerWorld,StateRef
from tests.clausewitz_harness import parse
from tools import build_v03_content

ROOT=Path(__file__).resolve().parents[1]

def province(owner='TIB'):
    office={'type':'building_government_administration','occupancy':.8,'shortage':False}
    farm={'type':'building_rice_farm','occupancy':.8,'shortage':False}
    return {'owner':owner,'owned':owner=='TIB','region':'s:STATE_TIBET',
            'market_access':.5,'average_sol':8,'buildings':[office,farm],
            'pops':[{'type':'bureaucrats','employed':True,'workplace':office,'radical_fraction':0},
                    {'type':'laborers','employed':True,'workplace':farm,'radical_fraction':.3}]}

def new_world(world_class=PartnerWorld, generated=False):
    countries={'TIB':{'states':[province(),province()],'igs':[],
                      'laws':{'law_land_based_taxation','law_serfdom','law_religious_schools'},
                      'gold_reserves':5000,'yearly_gross_income':5200,'net_fixed_income':100,
                      'in_default':False,'bureaucracy':100,'is_at_war':False,
                      'market':{'grain':{'pricier':.3}},'institutions':{'institution_schools':1},
                      'literacy_rate':.3},'CHI':{'states':[],'igs':[]}}
    w=world_class(countries,tag='tib')
    cat=json.loads((ROOT/'data/content/v03/countries/tib.json').read_text(encoding='utf-8-sig'))
    arc=next(a for a in cat['arcs'] if a['slug']=='v03_tib_public_revenue')
    only={**cat,'arcs':[arc]}
    if not generated:
        w.journal_defs.update({k:v for k,_,v in parse(build_v03_content._render_journal_file(only,None))})
        w.event_defs.update({k:v for k,_,v in parse(build_v03_content._render_event_file(only,ROOT,None)) if isinstance(v,list)})
    return w,arc

class TibRevenueSourceExactState(unittest.TestCase):
    def test_country_helpers_use_the_established_local_state_scope_form(self):
        # Match the existing KOR country-scoped StateRef convention, rather
        # than accepting an uncorroborated ROOT.var object-scope expression.
        source = (ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_tib_triggers.txt').read_text(encoding='utf-8-sig')
        definitions = {key: body for key, _, body in parse(source)}
        for name in ('ywc_tib_revenue_pilot_ready', 'ywc_tib_revenue_route_1_ready',
                     'ywc_tib_revenue_route_3_ready'):
            with self.subTest(helper=name):
                scopes = [(key, op, body) for key, op, body in definitions[name]
                          if key.lower().endswith('var:ywc_tib_revenue_pilot') and isinstance(body, list)]
                self.assertEqual([key for key, _, _ in scopes], ['var:ywc_tib_revenue_pilot'])

    def test_country_scoped_route_checks_follow_the_original_owned_state(self):
        w, arc = new_world()
        w.run_script('ywc_v03_initialize_country = yes', 'TIB')
        w.activate(arc['journals'][0]['id'], 'TIB')
        original, other = w.countries['TIB']['states']
        def ready(name):
            return w.check_script('AND = { AND = { ' + name + ' = yes } }', 'TIB')
        self.assertTrue(ready('ywc_tib_revenue_pilot_ready'))
        self.assertTrue(ready('ywc_tib_revenue_route_1_ready'))
        self.assertTrue(ready('ywc_tib_revenue_route_3_ready'))
        original['market_access'] = 0
        self.assertFalse(ready('ywc_tib_revenue_route_3_ready'))
        self.assertGreater(other['market_access'], 0.1)
        original['market_access'] = 0.5
        w.countries['TIB']['states'].remove(original)
        original['owner'] = 'CHI'
        w.countries['CHI']['states'].append(original)
        for name in ('ywc_tib_revenue_pilot_ready', 'ywc_tib_revenue_route_1_ready',
                     'ywc_tib_revenue_route_3_ready'):
            with self.subTest(foreign=name):
                self.assertFalse(ready(name))

    def test_opening_claim_captures_exact_owned_site_and_never_rebinds(self):
        w,arc=new_world();w.run_script('ywc_v03_initialize_country = yes','TIB')
        w.activate(arc['journals'][0]['id'],'TIB')
        self.assertIn(arc['journals'][0]['id'],w.active['TIB'])
        s=w.countries['TIB']
        self.assertTrue('ywc_tib_revenue_pilot' in s,'real claim did not capture a typed pilot')
        ref=s['ywc_tib_revenue_pilot'];self.assertIsInstance(ref,StateRef)
        self.assertTrue(w.check_script('ywc_tib_revenue_pilot_ready = yes','TIB'))
        original=s['states'][0];other=s['states'][1]
        original['pops']=[]
        self.assertFalse(w.check_script('ywc_tib_revenue_pilot_ready = yes','TIB'))
        self.assertTrue(other['pops'])
        s['states'].remove(original);original['owner']='CHI';w.countries['CHI']['states'].append(original)
        self.assertFalse(w.check_script('ywc_tib_revenue_pilot_ready = yes','TIB'))
        w.countries['CHI']['states'].remove(original)
        self.assertFalse(w.check_script('ywc_tib_revenue_pilot_ready = yes','TIB'))
        self.assertEqual(s['ywc_tib_revenue_pilot'],ref)

if __name__=='__main__':unittest.main()

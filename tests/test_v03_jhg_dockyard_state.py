"""Real dockyard source with exact state-object and workplace negatives."""
import copy
import sys
from pathlib import Path
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
from kor_partner_protocol_runtime import PartnerWorld,StateRef


def shipyard():
    return {'type':'building_shipyard','occupancy':.8,'shortage':False}

def province(owner='JHG',with_workers=True):
    yard=shipyard(); office={'type':'building_government_administration','occupancy':.8,'shortage':False}
    return {'owner':owner,'owned':owner=='JHG','region':'s:STATE_FORMOSA',
            'buildings':[yard,office],
            'pops':([{'type':'machinists','employed':True,'workplace':yard},
                     {'type':'bureaucrats','employed':True,'workplace':office}] if with_workers else [])}

def new_world():
    countries={'JHG':{'states':[province(),province()],'igs':[],'gold_reserves':10000,
                     'yearly_gross_income':5200,'net_fixed_income':100,'in_default':False,
                     'bureaucracy':100,'navy_size':20,'laws':set()},
               'CHI':{'states':[],'igs':[]}}
    return PartnerWorld(countries,tag='jhg')

class JhgDockyardExactState(unittest.TestCase):
    def test_capture_requires_real_claim_and_duplicate_claim_is_inert(self):
        w=new_world()
        w.run_script('ywc_v03_initialize_country = yes','JHG')
        self.assertTrue('ywc_jhg_dock_claim' in w.effects,'missing native claim')
        w.run_script('ywc_jhg_dock_capture_pilot = yes','JHG')
        self.assertNotIn('ywc_jhg_dock_pilot',w.countries['JHG'])
        w.run_script('ywc_jhg_dock_claim = yes','JHG')
        s=w.countries['JHG']
        self.assertEqual(s['ywc_jhg_v03_jhg_dockyard_capital_started'],1)
        self.assertEqual((s['ywc_v03_active_arc_count'],s['ywc_v03_visible_task_count']),(1,1))
        ref=s['ywc_jhg_dock_pilot']
        w.run_script('ywc_jhg_dock_claim = yes','JHG')
        self.assertEqual((s['ywc_v03_active_arc_count'],s['ywc_v03_visible_task_count']),(1,1))
        self.assertEqual(s['ywc_jhg_dock_pilot'],ref)

    def test_real_source_captures_first_site_once_and_never_borrows_another_state(self):
        w=new_world()
        self.assertTrue('ywc_jhg_dock_capture_pilot' in w.effects,'missing native site capture helper')
        self.assertTrue('ywc_jhg_dock_pilot_ready' in w.trigger_defs,'missing real workplace reader')
        w.run_script('ywc_v03_initialize_country = yes ywc_jhg_dock_claim = yes','JHG')
        s=w.countries['JHG']; ref=s['ywc_jhg_dock_pilot']
        self.assertIsInstance(ref,StateRef)
        self.assertTrue(w.check_script('ywc_jhg_dock_pilot_ready = yes','JHG'))
        original=s['states'][0]; replacement=s['states'][1]
        original['pops']=[]
        self.assertFalse(w.check_script('ywc_jhg_dock_pilot_ready = yes','JHG'))
        w.run_script('ywc_jhg_dock_capture_pilot = yes','JHG')
        self.assertEqual(s['ywc_jhg_dock_pilot'],ref)
        self.assertTrue(replacement['pops'])
        s['states'].remove(original);original['owner']='CHI';w.countries['CHI']['states'].append(original)
        self.assertFalse(w.check_script('ywc_jhg_dock_pilot_ready = yes','JHG'))
        w.countries['CHI']['states'].remove(original)
        self.assertFalse(w.check_script('ywc_jhg_dock_pilot_ready = yes','JHG'))
        self.assertEqual(s['ywc_jhg_dock_pilot'],ref)

    def test_site_requires_both_real_jobs_and_no_input_shortage(self):
        for kind, change in (('yard','shortage'),('yard','occupancy'),
                             ('office','shortage'),('office','occupancy'),
                             ('yard','employee'),('office','employee')):
            with self.subTest(kind=kind, change=change):
                w=new_world()
                w.run_script('ywc_v03_initialize_country = yes ywc_jhg_dock_claim = yes','JHG')
                state=w.countries['JHG']['states'][0]
                self.assertTrue(w.check_script('ywc_jhg_dock_pilot_ready = yes','JHG'))
                building=state['buildings'][0 if kind=='yard' else 1]
                if change=='shortage':building['shortage']=True
                elif change=='occupancy':building['occupancy']=.49
                else:state['pops'][0 if kind=='yard' else 1]['employed']=False
                self.assertFalse(w.check_script('ywc_jhg_dock_pilot_ready = yes','JHG'))

    def test_undelivered_opening_cannot_charge_select_or_advance(self):
        w=new_world()
        w.run_script('ywc_v03_initialize_country = yes ywc_jhg_dock_claim = yes','JHG')
        self.assertTrue(all(f'ywc_jhg_dock_choose_{i}' in w.effects for i in (1,2,3)),
                        'three actual native selection helpers required')
        before=copy.deepcopy((w.countries,w.treasury,w.modifiers,w.active,w.history))
        for i in (1,2,3):
            w.run_script(f'ywc_jhg_dock_choose_{i} = yes','JHG')
            self.assertEqual((w.countries,w.treasury,w.modifiers,w.active,w.history),before)

    def test_stale_cost_capture_cannot_recreate_quote_after_workplace_loss(self):
        w=new_world()
        w.run_script('ywc_v03_initialize_country = yes ywc_jhg_dock_claim = yes','JHG')
        state=w.countries['JHG']
        self.assertEqual(state['ywc_jhg_dock_cost_captured'],1)
        for key in ('cost_captured','base','cost_1','cost_2','cost_3'):
            state.pop('ywc_jhg_dock_'+key,None)
        state['states'][0]['pops']=[]
        before=copy.deepcopy((w.countries,w.treasury,w.modifiers))
        w.run_script('ywc_jhg_dock_capture_cost = yes','JHG')
        self.assertEqual((w.countries,w.treasury,w.modifiers),before)

if __name__=='__main__':unittest.main()

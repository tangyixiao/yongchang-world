"""Actual native JHG dockyard story guards, rendered from source in memory."""
import copy
import json
from pathlib import Path
import unittest

from tools import build_v03_content
from tests.clausewitz_harness import parse
from tests.test_v03_jhg_dockyard_state import new_world
from tests import test_v03_jhg_dockyard_history as history
from kor_partner_protocol_runtime import PartnerWorld

ROOT=Path(__file__).resolve().parents[1]
SLUG='v03_jhg_dockyard_capital'

def field(nodes,name,default=None):
    return next((value for key,_,value in nodes if key==name),default)

def option(event,key):
    return next(v for k,_,v in event if k=='option' and field(v,'name','').endswith('.'+key))

def body(option_nodes):
    return [x for x in option_nodes if x[0] not in ('name','trigger','ai_chance','default_option','custom_tooltip')]

def snapshot(w):
    return copy.deepcopy((w.countries,w.treasury,w.modifiers,w.active,w.history,
                          w.days_until_expiry,w.months_until_expiry))

class JhgDockyardNativeStory(unittest.TestCase):
    def open_source(self, w=None):
        catalog=json.loads((ROOT/'data/content/v03/countries/jhg.json').read_text(encoding='utf-8-sig'))
        arcs=[a for a in catalog['arcs'] if a['slug']==SLUG]
        self.assertTrue(len(arcs)==1,'missing real dockyard source arc')
        arc=arcs[0]; only={**catalog,'arcs':[arc]}
        w=new_world() if w is None else w
        w.journal_defs.update({k:v for k,_,v in parse(build_v03_content._render_journal_file(only,None))})
        w.event_defs.update({k:v for k,_,v in parse(build_v03_content._render_event_file(only,ROOT,None)) if isinstance(v,list)})
        values=ROOT/'yongchang_world/common/script_values/ywc_v03_nmg_values.txt'
        w.named_values.update({k:v for k,_,v in parse(values.read_text(encoding='utf-8-sig'))})
        modifiers=ROOT/'yongchang_world/common/static_modifiers/ywc_v03_jhg_dock_modifiers.txt'
        if modifiers.exists():
            w.modifier_defs.update({k:v for k,_,v in parse(modifiers.read_text(encoding='utf-8-sig'))})
        w.run_script('ywc_v03_initialize_country = yes','JHG')
        w.activate(arc['journals'][0]['id'],'JHG')
        self.assertIn(arc['journals'][0]['id'],w.active['JHG'])
        # These source-only legacy tests use one currently open popup at a
        # time. Keep its native chain alive through immediate and selection;
        # independent actual EventJobs are checked separately in dispatch.
        country = w.country_ref('JHG')
        w._current = w._root = country
        w._prev = None
        w._stack = [country]
        w._saved = {}
        event=w.deliver(arc,'ywc_jhg.1100')
        return w,arc,event

    def reached(self, target):
        w,arc,event=self.open_source()
        if target==1100:return w,arc,event
        w.execute(body(option(event,'route_1')),'JHG')
        for number in range(1101,target+1):
            event=w.deliver(arc,f'ywc_jhg.{number}')
            if number==target:return w,arc,event
            if number==1105:
                w.execute(body(option(event,'observe')),'JHG')
                for _ in range(6):w.advance_months(1);w.pulse(arc)
            else:w.execute(body(option(event,'advance')),'JHG')
        raise AssertionError(('unreachable target',target))

    def test_delivered_opening_charges_each_real_cost_once(self):
        for route,cost in ((1,200),(2,150),(3,100)):
            with self.subTest(route=route):
                w,_,event=self.open_source()
                choice=option(event,f'route_{route}')
                self.assertTrue(w.conditions(field(choice,'trigger',[]),'JHG'))
                before=w.treasury['JHG']
                w.execute(body(choice),'JHG')
                self.assertEqual(before-w.treasury['JHG'],cost)
                state=w.countries['JHG']
                self.assertEqual(state['ywc_jhg_dock_paid'],1)
                self.assertEqual(state['ywc_jhg_dock_paid_amount'],cost)
                self.assertEqual(state['ywc_jhg_dock_route'],route)
                after=snapshot(w)
                w.execute(body(choice),'JHG')
                self.assertEqual(snapshot(w),after)

    def test_delivered_opening_rechecks_lost_facts_at_click(self):
        for loss in ('funds','shortage','employees','owner','war'):
            with self.subTest(loss=loss):
                w,_,event=self.open_source();state=w.countries['JHG'];site=state['states'][0]
                if loss=='funds':state['gold_reserves']=0
                elif loss=='shortage':site['buildings'][0]['shortage']=True
                elif loss=='employees':site['pops']=[]
                elif loss=='owner':site['owner']='CHI'
                else:state['is_at_war']=True
                choice=option(event,'route_1'); before=snapshot(w)
                w.execute(body(choice),'JHG')
                self.assertEqual(snapshot(w),before)

    def test_withdrawn_opening_buttons_cannot_reopen_or_charge(self):
        w,_,event=self.open_source()
        w.execute(body(option(event,'withdraw')),'JHG')
        before=snapshot(w)
        for key in ('route_1','route_2','route_3','wait','withdraw'):
            with self.subTest(stale=key):
                w.execute(body(option(event,key)),'JHG')
                self.assertEqual(snapshot(w),before)

    def test_wait_invalidates_cached_opening_until_a_real_redelivery(self):
        w,arc,event=self.open_source()
        w.execute(body(option(event,'wait')),'JHG')
        before=snapshot(w)
        w.execute(body(option(event,'route_1')),'JHG')
        self.assertEqual(snapshot(w),before)
        again=w.deliver(arc,'ywc_jhg.1100')
        self.assertTrue(w.conditions(field(option(again,'route_1'),'trigger',[]),'JHG'))
        previous=w.treasury['JHG']
        w.execute(body(option(again,'route_1')),'JHG')
        self.assertEqual(previous-w.treasury['JHG'],200)

    def test_wait_at_each_delivered_stage_rejects_all_old_buttons(self):
        for number in range(1100,1108):
            with self.subTest(stage=number):
                w,arc,event=self.reached(number)
                w.execute(body(option(event,'wait')),'JHG')
                before=snapshot(w)
                for kind,_,nodes in event:
                    if kind!='option':continue
                    w.execute(body(nodes),'JHG')
                    self.assertEqual(snapshot(w),before,field(nodes,'name'))
                w.deliver(arc,f'ywc_jhg.{number}')

    def test_all_routes_deliver_real_final_event_after_six_distinct_months(self):
        self.assertTrue((ROOT/'yongchang_world/common/static_modifiers/ywc_v03_jhg_dock_modifiers.txt').is_file(),
                        'the three state effects need actual modifier definitions')
        for route,modifier in ((1,'ywc_jhg_dock_state_royal'),
                               (2,'ywc_jhg_dock_state_joint'),
                               (3,'ywc_jhg_dock_state_merchant')):
            with self.subTest(route=route):
                w,arc,event=self.open_source()
                w.execute(body(option(event,f'route_{route}')),'JHG')
                for n in (1101,1102,1103,1104):
                    event=w.deliver(arc,f'ywc_jhg.{n}')
                    if n==1104:
                        self.assertFalse(w.conditions(field(option(event,'use_convoy_history'),'trigger',[]),'JHG'))
                    w.execute(body(option(event,'advance')),'JHG')
                event=w.deliver(arc,'ywc_jhg.1105')
                w.execute(body(option(event,'observe')),'JHG')
                for _ in range(3):w.pulse(arc)
                self.assertEqual(w.countries['JHG']['ywc_jhg_dock_review_streak'],0)
                for n in range(1,7):
                    w.advance_months(1)
                    w.pulse(arc)
                    self.assertEqual(w.countries['JHG']['ywc_jhg_dock_review_streak'],n)
                event=w.deliver(arc,'ywc_jhg.1106')
                w.execute(body(option(event,'advance')),'JHG')
                self.assertNotIn('ywc_jhg_v03_jhg_dockyard_capital_settled',w.countries['JHG'])
                final=w.deliver(arc,'ywc_jhg.1107')
                self.assertNotIn('ywc_jhg_v03_jhg_dockyard_capital_settled',w.countries['JHG'])
                w.execute(body(option(final,'close')),'JHG')
                s=w.countries['JHG']
                self.assertEqual(s['ywc_jhg_v03_jhg_dockyard_capital_outcome'],route)
                self.assertEqual(s['ywc_jhg_v03_jhg_dockyard_capital_settled'],1)
                self.assertIn((s['ywc_jhg_dock_pilot'],modifier),w.state_modifiers)
                after=snapshot(w)
                w.execute(body(option(final,'close')),'JHG')
                self.assertEqual(snapshot(w),after)

    def test_lost_maturity_proof_cannot_advance_real_review_popup(self):
        w,arc,event=self.open_source()
        w.execute(body(option(event,'route_1')),'JHG')
        for n in (1101,1102,1103,1104):
            event=w.deliver(arc,f'ywc_jhg.{n}')
            w.execute(body(option(event,'advance')),'JHG')
        event=w.deliver(arc,'ywc_jhg.1105')
        w.execute(body(option(event,'observe')),'JHG')
        for _ in range(6):w.advance_months(1);w.pulse(arc)
        event=w.deliver(arc,'ywc_jhg.1106')
        for name,bad in (('review_mature',0),('review_mature',None),('review_streak',5),('review_streak',None)):
            with self.subTest(proof=name,bad=bad):
                trial=copy.deepcopy(w);state=trial.countries['JHG'];key='ywc_jhg_dock_'+name
                if bad is None:del state[key]
                else:state[key]=bad
                before=snapshot(trial)
                trial.execute(body(option(event,'advance')),'JHG')
                self.assertEqual(snapshot(trial),before)

    def test_actual_prior_court_and_convoy_change_distinct_native_nodes(self):
        # Run the original three native stories, then carry their actual saved
        # country facts and treasury into the typed source world. Add an explicit
        # current shipyard world fact; no prior success marker is synthesized.
        history.JhgDockyardEarnedPriorContracts.setUpClass()
        old=history.JhgDockyardEarnedPriorContracts.world
        countries=copy.deepcopy(old.countries)
        site=countries['JHG']['states'][0]
        site['owner']='JHG'
        yard={'type':'building_shipyard','occupancy':.8,'shortage':False}
        site['buildings'].append(yard)
        site['pops'].append({'type':'machinists','employed':True,'workplace':yard})
        # Preserve the old state's actual office; its employment is an explicit
        # current fact, independent of the earned historical records.
        office=next(b for b in site['buildings'] if b['type']=='building_government_administration')
        bureaucrat=next(p for p in site['pops'] if p['type']=='bureaucrats')
        bureaucrat['workplace']=office; bureaucrat['employed']=True
        w=PartnerWorld(countries,tag='jhg')
        w.treasury=copy.deepcopy(old.treasury)
        w,arc,event=self.open_source(w)
        s=w.countries['JHG']
        self.assertEqual(s['ywc_jhg_dock_cost_2'],1125)
        paid_before=w.treasury['JHG']
        w.execute(body(option(event,'route_2')),'JHG')
        self.assertEqual(paid_before-w.treasury['JHG'],1125)
        for number in (1101,1102,1103):
            event=w.deliver(arc,f'ywc_jhg.{number}')
            w.execute(body(option(event,'advance')),'JHG')
        event=w.deliver(arc,'ywc_jhg.1104')
        old_option=option(event,'use_convoy_history')
        self.assertTrue(w.conditions(field(old_option,'trigger',[]),'JHG'))
        w.execute(body(old_option),'JHG')
        self.assertEqual(s['ywc_jhg_dock_convoy_applied'],1)
        s['ywc_jhg_convoy_filing_fee_paid']=0
        event=w.deliver(arc,'ywc_jhg.1105')
        self.assertFalse(w.conditions(field(option(event,'observe'),'trigger',[]),'JHG'))

    def test_same_month_loss_interrupts_and_requires_six_fresh_months(self):
        w,arc,event=self.open_source()
        w.execute(body(option(event,'route_1')),'JHG')
        for number in (1101,1102,1103,1104):
            event=w.deliver(arc,f'ywc_jhg.{number}')
            w.execute(body(option(event,'advance')),'JHG')
        event=w.deliver(arc,'ywc_jhg.1105')
        w.execute(body(option(event,'observe')),'JHG')
        for _ in range(2):w.advance_months(1);w.pulse(arc)
        self.assertEqual(w.countries['JHG']['ywc_jhg_dock_review_streak'],2)
        yard=w.countries['JHG']['states'][0]['buildings'][0]
        yard['shortage']=True
        w.pulse(arc)
        s=w.countries['JHG']
        self.assertEqual(s['ywc_jhg_dock_review_interrupted'],1)
        self.assertEqual(s['ywc_jhg_dock_review_streak'],0)
        self.assertNotIn('ywc_jhg_dock_review_mature',s)
        yard['shortage']=False
        event=w.deliver(arc,'ywc_jhg.1105')
        w.execute(body(option(event,'observe')),'JHG')
        for _ in range(5):w.advance_months(1);w.pulse(arc)
        self.assertNotIn('ywc_jhg_dock_review_mature',s)
        w.advance_months(1);w.pulse(arc)
        self.assertEqual(s['ywc_jhg_dock_review_mature'],1)

    def test_old_1101_buttons_cannot_rewind_or_end_later_stage(self):
        w,arc,event=self.open_source()
        w.execute(body(option(event,'route_1')),'JHG')
        old=w.deliver(arc,'ywc_jhg.1101')
        w.execute(body(option(old,'advance')),'JHG')
        w.deliver(arc,'ywc_jhg.1102')
        before=snapshot(w)
        for key in ('advance','wait','withdraw'):
            with self.subTest(stale=key):
                w.execute(body(option(old,key)),'JHG')
                self.assertEqual(snapshot(w),before)

    def test_missing_review_clock_does_not_award_a_month(self):
        w,arc,event=self.open_source()
        w.execute(body(option(event,'route_1')),'JHG')
        for number in (1101,1102,1103,1104):
            event=w.deliver(arc,f'ywc_jhg.{number}')
            w.execute(body(option(event,'advance')),'JHG')
        event=w.deliver(arc,'ywc_jhg.1105')
        w.execute(body(option(event,'observe')),'JHG')
        s=w.countries['JHG']
        del s['ywc_jhg_dock_review_month']
        w.advance_months(1)
        w.pulse(arc)
        self.assertEqual(s['ywc_jhg_dock_review_streak'],0)
        self.assertNotIn('ywc_jhg_dock_review_mature',s)

if __name__=='__main__':unittest.main()

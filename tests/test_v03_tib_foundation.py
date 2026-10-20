import json
import re
import unittest
from pathlib import Path
sys_path = str(Path(__file__).resolve().parents[1] / "tests")
import sys
sys.path.insert(0, sys_path)
from clausewitz_harness import PulseWorld

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/'yongchang_world'
CAT=ROOT/'data/content/v03/countries/tib.json'
REG=ROOT/'data/content/v03/id_registry.json'
EFFECT=MOD/'common/scripted_effects/ywc_v03_tib_effects.txt'
TRIGGER=MOD/'common/scripted_triggers/ywc_v03_tib_triggers.txt'
SLUGS=['v03_tib_service_register','v03_tib_grain_credit','v03_tib_shared_schools']
RANGES=[(1000,1009,10,3),(1010,1019,8,2),(1020,1029,6,1)]
PREFIX=['register','grain','schools']
def body(text,name):
    m=re.search(rf'(?m)^{re.escape(name)}\s*=\s*\{{',text)
    if not m: raise AssertionError(f'missing {name}')
    depth=0; quote=False
    for i in range(m.start(),len(text)):
        c=text[i]
        if c=='"' and (i==0 or text[i-1]!='\\'): quote=not quote
        if quote: continue
        if c=='{': depth+=1
        elif c=='}':
            depth-=1
            if depth==0: return text[m.start():i+1]
    raise AssertionError(f'unclosed {name}')


def catalog_block(text,key):
    marker=key+' = {'; start=text.index(marker)+len(key+' = '); depth=0; quoted=False
    for i in range(start,len(text)):
     ch=text[i]
     if ch=='"' and (i==0 or text[i-1]!='\\'): quoted=not quoted
     if quoted: continue
     if ch=='{': depth+=1
     elif ch=='}':
      depth-=1
      if depth==0:return text[start:i+1]
    raise AssertionError('unclosed catalog property '+key)

class TibPulseWorld(PulseWorld):
 def __init__(self,effects,countries,triggers=None):
    super().__init__(effects,countries)
    if triggers is None: triggers=TRIGGER.read_text(encoding='utf-8-sig')
    from clausewitz_harness import parse
    self.trigger_defs={key:body for key,_,body in parse(triggers)}
 def condition(self,node,tag):
    key,op,value=node; state=self.countries[tag]
    if key=='c:TIB': return tag=='TIB'
    if key=='ywc_v03_can_deliver_major': return bool(state.get('test_deliver',True))
    if key in self.trigger_defs: return self.conditions(self.trigger_defs[key],tag)
    if key in ('market_capital.market','mg:grain','workplace ?'):
     return self.conditions(value,tag)
    if key=='market_goods_pricier':
     left=float(state.get('grain_price_gap',0.30 if state.get('test_ready',False) else 0)); right=float(value)
     return {'=':lambda:left==right,'>':lambda:left>right,'<':lambda:left<right,'>=':lambda:left>=right,'<=':lambda:left<=right,'!=':lambda:left!=right}[op]()
    if key=='has_law_or_variant': return value in state.get('laws',[]) or bool(state.get('test_ready',False))
    if key in ('any_scope_state','any_scope_pop','any_scope_building','radical_fraction'):
     return bool(state.get('owned_state',state.get('test_ready',False)))
    if key=='institution_investment_level': return bool(state.get('schools_institution',state.get('test_ready',False)))
    if key in ('literacy_rate','market_access'):
     left=float(state.get('literacy_rate',0.2 if state.get('test_ready',False) else 0.5) if key=='literacy_rate' else state.get('market_access',1 if state.get('test_ready',False) else 0)); right=float(value)
     return {'=':lambda:left==right,'>':lambda:left>right,'<':lambda:left<right,'>=':lambda:left>=right,'<=':lambda:left<=right,'!=':lambda:left!=right}[op]()
    if key in ('is_owned_by','is_pop_type','is_employed','is_building_type'):
     return bool(state.get('test_ready',False))
    return super().condition(node,tag)

class TibFoundationTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
    cls.cat=json.loads(CAT.read_text(encoding='utf-8')); cls.reg=json.loads(REG.read_text(encoding='utf-8'))
    cls.effects=EFFECT.read_text(encoding='utf-8-sig'); cls.triggers=TRIGGER.read_text(encoding='utf-8-sig')

 def _reach_final_observation(self, pre):
    from clausewitz_harness import parse
    paths={'register':([1000,1001,1002,1003,1004,1007,1008,1009],['route_1','review_next','review_next','review_next','review_next','review_next','review_next','review_next']),
           'grain':([1010,1011,1012,1013,1016,1017],['route_1','review_next','review_next','review_next','review_next','review_next']),
           'schools':([1020,1021,1022,1025],['route_1','review_next','review_next','review_next'])}
    nodes,choices=paths[pre]; arc=self.cat['arcs'][PREFIX.index(pre)]
    world=TibPulseWorld(self.effects,{'TIB':{'gold_reserves':1000,'net_fixed_income':10,'in_default':False,'test_ready':True,
     'yearly_gross_income':5200,'ywc_v03_initialized':1,'ywc_campaign_tib_c1_outcome':0,
     'ywc_v03_active_arc_count':0,'ywc_v03_visible_task_count':0}})
    entry=arc['journals'][0]['script']; entry_immediate=parse('test_action = '+catalog_block(entry,'immediate'))[0][2]
    world.execute(entry_immediate,'TIB')
    def pulse_active_journal():
     stage=world.countries['TIB'].get(f'ywc_tib_{pre}_stage',0)
     index=(2 if pre=='register' and stage>1 else 1 if pre in ('register','grain') and stage>0 else 0)
     active=arc['journals'][index]
     if self._journal_status(world,active)!=(False,False): raise AssertionError(f'{active["id"]} is not live by its goal/exit predicates')
     pulse=parse('test_action = '+catalog_block(active['script'],'on_monthly_pulse'))[0][2]
     effect=next(v for k,_,v in pulse if k=='effect')
     world.execute(effect,'TIB')
    pulse_active_journal(); world.events.clear()
    for idx,(node,key) in enumerate(zip(nodes,choices)):
     event=next(e for e in arc['events'] if e['id']==f'ywc_tib.{node}')
     option=next(o for o in event['options'] if o['key']==key)
     world.execute(parse('test_action = '+option['effect'])[0][2],'TIB')
     if node in (1003,1013):
      immediate=parse('test_action = '+catalog_block(arc['journals'][1]['script'],'immediate'))[0][2]
      world.execute(immediate,'TIB')
     if node==1004:
      immediate=parse('test_action = '+catalog_block(arc['journals'][2]['script'],'immediate'))[0][2]
      world.execute(immediate,'TIB')
     pulse_active_journal()
     world.events.clear()
    final_je=arc['journals'][-1]
    final_pulse=parse('test_action = '+catalog_block(final_je['script'],'on_monthly_pulse'))[0][2]
    final_effect=next(v for k,_,v in final_pulse if k=='effect')
    return world,arc,final_je,final_effect

 def _journal_status(self, world, journal):
    from clausewitz_harness import parse
    goal=parse('probe = '+journal['goal'])[0][2]
    exit_condition=parse('probe = '+journal['exit_conditions'])[0][2]
    return world.conditions(goal,'TIB'),world.conditions(exit_condition,'TIB')

 def _journal_active(self, world, journal):
    goal,exit_condition=self._journal_status(world,journal)
    return bool(world.countries['TIB'].get('ywc_v03_tib_v03_tib_service_register_started',0)
      or world.countries['TIB'].get('ywc_v03_tib_v03_tib_grain_credit_started',0)
      or world.countries['TIB'].get('ywc_v03_tib_v03_tib_shared_schools_started',0)) and not goal and not exit_condition
 def test_arcs_are_registered_with_reserved_ranges_and_counts(self):
    rows={(x['catalog_key'],x['slug']):x for x in self.reg['arc_ranges']}
    for i,(slug,(lo,hi,n,j)) in enumerate(zip(SLUGS,RANGES)):
     a=self.cat['arcs'][i]; self.assertEqual(a['slug'],slug); self.assertEqual((rows[('country_tib',slug)]['start'],rows[('country_tib',slug)]['end']),(lo,hi))
     self.assertEqual(len(a['events']),n); self.assertEqual(len(a['journals']),j)
     self.assertEqual([x['id'] for x in a['events']],[f'ywc_tib.{x}' for x in range(lo,lo+n)])
 def test_locked_card_shape_and_bilingual_notes(self):
    self.assertEqual((self.cat['key'],self.cat['layer'],self.cat['runtime_tags']),('country_tib','country',['TIB']))
    for a in self.cat['arcs']:
     self.assertEqual(a['era'],'foundation'); self.assertEqual(a['depends_on'],[]); self.assertGreaterEqual(len(a['outcomes']),4); self.assertGreaterEqual(len(a['legacy_links']),2)
     for e in a['events']:
      self.assertTrue(e['title']['zh'] and e['title']['en']); self.assertTrue(e['desc']['zh'] and e['desc']['en']); self.assertGreaterEqual(len(e['options']),2)
      for o in e['options']: self.assertEqual(set(o['cost_note']),{'zh','en'}); self.assertEqual(set(o['consequence_note']),{'zh','en'})
     for j in a['journals']: self.assertNotRegex(j['script'],r'(?<![a-z0-9_])(?:complete|fail)\s*=')
 def test_required_scripted_calls_resolve(self):
    defs=set(re.findall(r'(?m)^([a-z_0-9]+)\s*=\s*\{',self.effects+'\n'+self.triggers))
    for folder in ('common/scripted_effects','common/scripted_triggers'):
     for f in (MOD/folder).glob('*.txt'):
      defs.update(re.findall(r'(?m)^([a-z_0-9]+)\s*=\s*\{',f.read_text(encoding='utf-8-sig')))
    text=json.dumps(self.cat['arcs'],ensure_ascii=False)
    calls=set(re.findall(r'(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)',text))
    self.assertEqual(sorted(calls-defs),[])
 def test_each_event_has_dispatch_and_cooldown_mark(self):
    for a in self.cat['arcs']:
     alltxt='\n'.join(j['script'] for j in a['journals'])
     for e in a['events']:
      self.assertIn(e['id'],alltxt); self.assertIn('ywc_v03_mark_major_delivered = yes',e['immediate']); self.assertIn('ywc_v03_can_deliver_major = yes',e['trigger'])
 def test_entry_journals_use_fixed_slots_and_legacy_continuation(self):
    for a in self.cat['arcs']:
     j=a['journals'][0]['script']
     self.assertGreaterEqual(j.count('var:ywc_v03_active_arc_count < 3'),2); self.assertGreaterEqual(j.count('var:ywc_v03_visible_task_count < 6'),2)
     self.assertIn('change_variable = { name = ywc_v03_active_arc_count add = 1 }',j); self.assertIn('change_variable = { name = ywc_v03_visible_task_count add = 1 }',j)
     self.assertIn('var:ywc_campaign_tib_c1_outcome >= 0',j)
 def test_route_selection_charges_real_income_snapshot_once(self):
    for p in PREFIX:
     capture=body(self.effects,f'ywc_tib_capture_{p}_fee')
     for token in ('yearly_gross_income','divide = 52','clamp_variable','min = 100','max = 1000000000'): self.assertIn(token,capture)
     for r in (1,2,3):
      choose=body(self.effects,f'ywc_tib_choose_{p}_{r}')
      for token in ('add_treasury','multiply = -1',f'ywc_tib_{p}_paid','NOT = { in_default = yes }','NOT = { has_modifier = declared_bankruptcy }'): self.assertIn(token,choose)
 def test_failed_and_replayed_route_choice_keeps_or_advances_current_event(self):
    world=TibPulseWorld(self.effects,{'TIB':{'gold_reserves':120,'net_fixed_income':10,'in_default':False,'ywc_tib_register_fee':100,'ywc_tib_register_route_cost_1':200,'ywc_tib_register_route_cost_2':150,'ywc_tib_register_route_cost_3':75,'ywc_tib_register_pending_event':1000}})
    from clausewitz_harness import parse
    trigger_defs={key:body for key,_,body in parse(self.triggers)}
    self.assertFalse(world.conditions(trigger_defs['ywc_tib_payable_register_1'],'TIB'))
    self.assertTrue(world.conditions(trigger_defs['ywc_tib_payable_register_3'],'TIB'))
    world.execute(parse('test_action = '+self.cat['arcs'][0]['events'][0]['options'][0]['effect'])[0][2],'TIB')
    self.assertEqual(world.countries['TIB']['ywc_tib_register_pending_event'],1000)
    self.assertNotIn('ywc_tib_register_paid',world.countries['TIB'])
    self.assertEqual(world.treasury['TIB'],0)
    world.countries['TIB']['gold_reserves']=250
    world.execute(parse('test_action = '+self.cat['arcs'][0]['events'][0]['options'][0]['effect'])[0][2],'TIB')
    self.assertEqual(world.treasury['TIB'],-200)
    self.assertEqual(world.countries['TIB']['ywc_tib_register_route'],1)
    world.execute(parse('test_action = '+self.cat['arcs'][0]['events'][0]['options'][0]['effect'])[0][2],'TIB')
    self.assertEqual(world.treasury['TIB'],-200)

 def test_parallel_arc_options_keep_independent_queues_and_charges(self):
    world=TibPulseWorld(self.effects,{'TIB':{'gold_reserves':1000,'net_fixed_income':10,'in_default':False,
     'ywc_tib_register_fee':100,'ywc_tib_register_route_cost_1':200,
     'ywc_tib_grain_fee':100,'ywc_tib_grain_route_cost_2':150,
     'ywc_tib_register_pending_event':1000,'ywc_tib_grain_pending_event':1010}})
    from clausewitz_harness import parse
    world.execute(parse('test_action = '+self.cat['arcs'][0]['events'][0]['options'][0]['effect'])[0][2],'TIB')
    world.execute(parse('test_action = '+self.cat['arcs'][1]['events'][0]['options'][1]['effect'])[0][2],'TIB')
    state=world.countries['TIB']
    self.assertEqual(state['ywc_tib_register_route'],1);self.assertEqual(state['ywc_tib_grain_route'],2)
    self.assertEqual(state['ywc_tib_register_pending_event'],1001);self.assertEqual(state['ywc_tib_grain_pending_event'],1011)
    self.assertEqual(world.treasury['TIB'],-350)

 def test_normal_shipped_event_paths_reach_final_implementation(self):
    from clausewitz_harness import parse
    paths=[('register',[1000,1001,1002,1003,1004,1007,1008,1009],['route_1','review_next','review_next','review_next','review_next','review_next','review_next','review_next']),
           ('grain',[1010,1011,1012,1013,1016,1017],['route_1','review_next','review_next','review_next','review_next','review_next']),
           ('schools',[1020,1021,1022,1025],['route_1','review_next','review_next','review_next'])]
    for pre,nodes,choices in paths:
     world=TibPulseWorld(self.effects,{'TIB':{'gold_reserves':1000,'net_fixed_income':10,'in_default':False,'test_ready':True,
      'yearly_gross_income':5200,'ywc_v03_active_arc_count':0,'ywc_v03_visible_task_count':0}})
     arc=self.cat['arcs'][PREFIX.index(pre)]; entry_script=arc['journals'][0]['script']
     entry_immediate=parse('test_action = '+catalog_block(entry_script,'immediate'))[0][2]
     world.execute(entry_immediate,'TIB')
     state=world.countries['TIB']
     self.assertEqual(state['ywc_v03_active_arc_count'],1,pre)
     j=arc['journals'][1 if pre!='schools' else 0]['script']
     pulse=parse('test_action = '+catalog_block(entry_script,'on_monthly_pulse'))[0][2]
     pulse_effect=next(v for k,_,v in pulse if k=='effect')
     world.execute(pulse_effect,'TIB');self.assertIn(('TIB',f'ywc_tib.{nodes[0]}'),world.events);world.events.pop()
     for idx,(node,key) in enumerate(zip(nodes,choices)):
      event=next(e for e in arc['events'] if e['id']==f'ywc_tib.{node}')
      option=next(o for o in event['options'] if o['key']==key)
      world.execute(parse('test_action = '+option['effect'])[0][2],'TIB')
      if node==1003 or node==1013:
       immediate=parse('test_action = '+catalog_block(arc['journals'][1]['script'],'immediate'))[0][2]
       world.execute(immediate,'TIB')
      if node==1004:
       immediate=parse('test_action = '+catalog_block(arc['journals'][2]['script'],'immediate'))[0][2]
       world.execute(immediate,'TIB')
      world.execute(pulse_effect,'TIB')
      if idx+1<len(nodes):
       self.assertIn(('TIB',f'ywc_tib.{nodes[idx+1]}'),world.events)
       world.events.pop()
      else:
       self.assertEqual(world.events,[],pre)
       self.assertNotIn(f'ywc_tib_{pre}_pending_event',state,pre)
     self.assertEqual(state['ywc_tib_'+pre+'_implementation_complete'],1,pre)
     self.assertEqual(state['ywc_tib_'+pre+'_route'],1,pre)
     self.assertEqual(state['ywc_tib_'+pre+'_paid'],1,pre)
     self.assertEqual(world.treasury['TIB'],-200,pre)

 def test_final_observation_loss_keeps_live_je_and_unblocks_12_36_month_exits(self):
    from clausewitz_harness import parse
    for pre in PREFIX:
     world,arc,final_je,pulse_effect=self._reach_final_observation(pre)
     state=world.countries['TIB']
     self.assertEqual(state[f'ywc_tib_{pre}_implementation_complete'],1,pre)
     self.assertEqual(self._journal_status(world,final_je),(False,False),pre)
     self.assertTrue(self._journal_active(world,final_je),pre)
     state['test_ready']=False
     state.pop('grain_price_gap',None)
     world.execute(pulse_effect,'TIB')
     self.assertNotIn(f'ywc_tib_{pre}_timer',state,pre)
     self.assertNotIn(f'ywc_tib_{pre}_six_months_complete',state,pre)
     self.assertIn(f'ywc_tib_{pre}_blocked_started',state,pre)
     self.assertEqual(self._journal_status(world,final_je),(False,False),pre)
     self.assertTrue(self._journal_active(world,final_je),pre)
     world.advance_days(365)
     self.assertEqual(self._journal_status(world,final_je),(False,False),pre)
     self.assertTrue(self._journal_active(world,final_je),pre)
     world.execute(pulse_effect,'TIB')
     notice12={'register':1005,'grain':1014,'schools':1023}[pre]
     self.assertIn(('TIB',f'ywc_tib.{notice12}'),world.events,pre)
     world.events.clear()
     event12=next(e for e in arc['events'] if e['id']==f'ywc_tib.{notice12}')
     defer=next(o for o in event12['options'] if o['key']=='defer')
     world.execute(parse('test_action = '+defer['effect'])[0][2],'TIB')
     self.assertEqual(self._journal_status(world,final_je),(False,False),pre)
     self.assertTrue(self._journal_active(world,final_je),pre)
     world.advance_days(730)
     self.assertEqual(self._journal_status(world,final_je),(False,False),pre)
     world.execute(pulse_effect,'TIB')
     notice36={'register':1006,'grain':1015,'schools':1024}[pre]
     self.assertIn(('TIB',f'ywc_tib.{notice36}'),world.events,pre)
     self.assertEqual(state[f'ywc_tib_{pre}_notice_last_delivered'],2,pre)
     world.events.clear()
     event36=next(e for e in arc['events'] if e['id']==f'ywc_tib.{notice36}')
     withdraw=next(o for o in event36['options'] if o['key']=='withdraw')
     world.execute(parse('test_action = '+withdraw['effect'])[0][2],'TIB')
     self.assertEqual(self._journal_status(world,final_je),(False,True),pre)
     self.assertFalse(self._journal_active(world,final_je),pre)
     self.assertEqual(state['ywc_v03_active_arc_count'],0,pre)

 def test_final_observation_narrow_and_restoration_keep_paid_arc_live(self):
    from clausewitz_harness import parse
    for pre in PREFIX:
     world,arc,final_je,pulse_effect=self._reach_final_observation(pre)
     state=world.countries['TIB']; baseline=world.treasury['TIB']
     state['test_ready']=False; state.pop('grain_price_gap',None)
     world.execute(pulse_effect,'TIB'); world.advance_days(365); world.execute(pulse_effect,'TIB')
     notice12={'register':1005,'grain':1014,'schools':1023}[pre]
     self.assertIn(('TIB',f'ywc_tib.{notice12}'),world.events,pre)
     world.events.clear()
     event12=next(e for e in arc['events'] if e['id']==f'ywc_tib.{notice12}')
     narrow=next(o for o in event12['options'] if o['key']=='narrow_scope')
     world.execute(parse('test_action = '+narrow['effect'])[0][2],'TIB')
     self.assertEqual(state[f'ywc_tib_{pre}_paid'],1,pre)
     self.assertEqual(state[f'ywc_tib_{pre}_route'],1,pre)
     self.assertEqual(world.treasury['TIB'],baseline,pre)
     self.assertNotIn(f'ywc_tib_{pre}_implementation_complete',state,pre)
     self.assertEqual(self._journal_status(world,final_je),(False,False),pre)
     self.assertTrue(self._journal_active(world,final_je),pre)
     state['test_ready']=True
     world.execute(pulse_effect,'TIB')
     for suffix in ('blocked_started','blocked_12_due','blocked_36_due','notice_12_event','notice_36_event','notice_12_sent','notice_36_sent'):
      self.assertNotIn(f'ywc_tib_{pre}_{suffix}',state,(pre,suffix))
     self.assertFalse(any(event[1]==f'ywc_tib.{notice12}' for event in world.events),pre)
 def test_notice_dispatch_preserves_normal_queues_at_full_capacity(self):
    from clausewitz_harness import parse
    arc=self.cat['arcs'][0];j=arc['journals'][1]['script']
    world=TibPulseWorld(self.effects,{'TIB':{'ywc_v03_active_arc_count':3,'ywc_v03_visible_task_count':6,
     'ywc_v03_tib_v03_tib_service_register_started':1,'test_deliver':True,
     'ywc_tib_register_pending_event':1004,'ywc_tib_register_notice_12_event':1005,
     'ywc_tib_grain_pending_event':1010}})
    world.execute(parse('test_action = '+catalog_block(j,'immediate'))[0][2],'TIB')
    self.assertEqual(world.countries['TIB']['ywc_v03_active_arc_count'],3)
    pulse=parse('test_action = '+catalog_block(j,'on_monthly_pulse'))[0][2]
    effect=next(v for k,_,v in pulse if k=='effect');world.execute(effect,'TIB')
    state=world.countries['TIB']
    self.assertIn(('TIB','ywc_tib.1005'),world.events)
    self.assertEqual(state['ywc_tib_register_pending_event'],1004)
    self.assertEqual(state['ywc_tib_grain_pending_event'],1010)
    self.assertEqual(state['ywc_v03_active_arc_count'],3)

 def test_replayed_route_choice_cannot_double_charge(self):
    for p in PREFIX:
     for r in (1,2,3):
      helper=body(self.effects,f'ywc_tib_choose_{p}_{r}')
      self.assertIn(f'NOT = {{ has_variable = ywc_tib_{p}_paid }}',helper)
      self.assertEqual(helper.count('add_treasury'),1)
 def test_observation_resets_and_restarts_from_zero(self):
    for p in PREFIX:
     reset=body(self.effects,f'ywc_tib_{p}_reset_observation'); review=body(self.effects,f'ywc_tib_{p}_monthly_review')
     self.assertIn(f'remove_variable = ywc_tib_{p}_timer',reset); self.assertIn('months = 6',review)
     self.assertIn(f'ywc_tib_{p}_reset_observation = yes',review); self.assertIn(f'NOT = {{ has_variable = ywc_tib_{p}_six_months_complete }}',review)
 def test_routes_have_real_market_price_radicalism_and_employment_gates(self):
    self.assertIn('market_goods_pricier > 0.25',self.triggers)
    self.assertIn('market_goods_pricier > 0.15',self.triggers)
    self.assertIn('market_goods_pricier > 0.10',self.triggers)
    self.assertIn('radical_fraction = { value > 0.25 pop_type = laborers }',self.triggers)
    self.assertIn('is_employed = yes workplace ?= { is_building_type = building_government_administration }',self.triggers)
    self.assertIn('is_employed = yes workplace ?= { is_building_type = building_university }',self.triggers)
    self.assertIn('average_sol < 10',self.triggers)

 def test_withdrawal_is_idempotent_and_releases_clamped_slots(self):
    for i,p in enumerate(PREFIX):
     helper=body(self.effects,f'ywc_tib_{p}_withdraw')
     self.assertIn('NOT = { has_variable = ywc_v03_tib_'+SLUGS[i]+'_settled }',helper)
     self.assertIn('clamp_variable = { name = ywc_v03_active_arc_count min = 0 max = 3 }',helper)
     self.assertIn('clamp_variable = { name = ywc_v03_visible_task_count min = 0 max = 6 }',helper)

 def test_journal_phases_resume_without_overwriting_the_queued_node(self):
    for i,a in enumerate(self.cat['arcs']):
     pre=PREFIX[i]
     self.assertIn(f'ywc_tib_{pre}_pending_event',a['journals'][0]['script'])
     if len(a['journals'])>1:
      self.assertIn(f'has_variable = ywc_v03_tib_{SLUGS[i]}_started',a['journals'][1]['script'])
      self.assertIn(f'ywc_tib_{pre}_phase_two_open',a['journals'][1]['script'])
     self.assertIn(f'ywc_tib_{pre}_six_months_complete',a['journals'][-1]['goal'])

 def test_no_neighbor_claim_or_direct_land_law_removal(self):
    alltext=json.dumps(self.cat['arcs'],ensure_ascii=False)+'\n'+self.effects
    self.assertNotRegex(alltext,r'\b(?:add_claim|annex|transfer_state)\s*=')
    self.assertNotRegex(alltext,r'activate_law\s*=\s*law_type:law_no_land_ownership|remove_law\s*=')
    for a in self.cat['arcs']:
     self.assertTrue(any('康青' in e['desc']['zh'] or 'neighbor' in e['desc']['en'].lower() for e in a['events']))


 def test_notice_defer_preserves_normal_queue_and_narrow_keeps_paid_route(self):
    from clausewitz_harness import parse
    world=TibPulseWorld(self.effects,{'TIB':{'test_ready':False,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
     'ywc_v03_tib_v03_tib_grain_credit_started':1,'ywc_tib_grain_paid':1,'ywc_tib_grain_route':1,'ywc_tib_grain_stage':1,'ywc_tib_grain_pending_event':1012}})
    state=world.countries['TIB'];world.run('ywc_tib_grain_monthly_review','TIB')
    self.assertIn('ywc_tib_grain_blocked_12_due',state)
    world.advance_days(365);world.run('ywc_tib_grain_monthly_review','TIB')
    self.assertEqual(state['ywc_tib_grain_notice_12_event'],1014)
    arc=self.cat['arcs'][1];pulse=parse('test_action = '+catalog_block(arc['journals'][0]['script'],'on_monthly_pulse'))[0][2]
    pe=next(v for k,_,v in pulse if k=='effect');world.execute(pe,'TIB')
    self.assertIn(('TIB','ywc_tib.1014'),world.events);self.assertEqual(state['ywc_tib_grain_pending_event'],1012)
    defer=next(o for o in arc['events'][4]['options'] if o['key']=='defer')
    world.execute(parse('test_action = '+defer['effect'])[0][2],'TIB')
    self.assertEqual(state['ywc_tib_grain_notice_12_event'],1014);self.assertEqual(state['ywc_tib_grain_pending_event'],1012)
    world.execute(pe,'TIB');self.assertIn(('TIB','ywc_tib.1014'),world.events)
    narrow=next(o for o in arc['events'][4]['options'] if o['key']=='narrow_scope')
    before=world.treasury['TIB'];world.execute(parse('test_action = '+narrow['effect'])[0][2],'TIB')
    self.assertEqual(state['ywc_tib_grain_route'],1);self.assertEqual(state['ywc_tib_grain_paid'],1)
    self.assertEqual(world.treasury['TIB'],before);self.assertNotIn('ywc_tib_grain_implementation_complete',state)
    self.assertEqual(state['ywc_tib_grain_pending_event'],1017)

 def test_setback_is_a_real_journal_failure_and_clears_both_queues(self):
    from clausewitz_harness import parse
    for i,pre in enumerate(PREFIX):
     world=TibPulseWorld(self.effects,{'TIB':{'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
      'ywc_v03_tib_'+SLUGS[i]+'_started':1,'ywc_tib_'+pre+'_pending_event':1020+i*10,'ywc_tib_'+pre+'_notice_12_event':1023+i*10}})
     world.run(f'ywc_tib_{pre}_settle_setback','TIB')
     arc=self.cat['arcs'][i];state=world.countries['TIB']
     fail=parse('probe = '+arc['journals'][-1]['exit_conditions'])[0][2]
     self.assertTrue(world.conditions(fail,'TIB'))
     self.assertEqual(state['ywc_v03_active_arc_count'],0);self.assertEqual(state['ywc_v03_visible_task_count'],0)
     self.assertNotIn(f'ywc_tib_{pre}_pending_event',state);self.assertNotIn(f'ywc_tib_{pre}_notice_12_event',state)


 def test_36_month_notice_has_fair_dispatch_after_12_month_defer(self):
    from clausewitz_harness import parse
    world=TibPulseWorld(self.effects,{'TIB':{'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
     'ywc_tib_grain_notice_12_event':1014,'ywc_tib_grain_notice_36_event':1015,'ywc_tib_grain_pending_event':1012}})
    state=world.countries['TIB'];arc=self.cat['arcs'][1]
    pulse=parse('test_action = '+catalog_block(arc['journals'][0]['script'],'on_monthly_pulse'))[0][2]
    pe=next(v for k,_,v in pulse if k=='effect')
    defer=next(o for o in arc['events'][4]['options'] if o['key']=='defer')
    world.execute(pe,'TIB')
    self.assertIn(('TIB','ywc_tib.1014'),world.events)
    self.assertEqual(state['ywc_tib_grain_notice_last_delivered'],1)
    world.events.clear();world.execute(parse('test_action = '+defer['effect'])[0][2],'TIB')
    world.execute(pe,'TIB')
    self.assertIn(('TIB','ywc_tib.1015'),world.events)
    self.assertEqual(state['ywc_tib_grain_notice_last_delivered'],2)
    self.assertEqual(state['ywc_tib_grain_notice_12_event'],1014)
    self.assertNotIn('ywc_tib_grain_notice_36_event',state)
    self.assertEqual(state['ywc_tib_grain_pending_event'],1012)
    world.events.clear();world.execute(pe,'TIB')
    self.assertIn(('TIB','ywc_tib.1014'),world.events)
    self.assertEqual(state['ywc_tib_grain_pending_event'],1012)

 def test_narrowed_routes_use_real_lower_conditions_and_cap_to_limited_outcome(self):
    from clausewitz_harness import parse
    cases=[
     ('register',1,{'net_fixed_income':50,'in_default':False,'laws':['law_type:law_serfdom'],'owned_state':False},'ywc_tib_register_route_1_ready'),
     ('grain',1,{'net_fixed_income':50,'in_default':False,'grain_price_gap':0.12,'owned_state':False},'ywc_tib_grain_route_1_ready'),
     ('schools',1,{'net_fixed_income':50,'in_default':False,'laws':['law_type:law_public_schools'],'literacy_rate':0.7,'owned_state':False},'ywc_tib_schools_route_1_ready')]
    for pre,route,world_facts,raw_route in cases:
     state=dict(world_facts);state.update({f'ywc_tib_{pre}_route':route,f'ywc_tib_{pre}_scope_narrowed':1})
     world=TibPulseWorld(self.effects,{'TIB':state})
     ready=f'ywc_tib_{pre}_route_execution_ready'
     self.assertFalse(world.condition((raw_route,'=','yes'),'TIB'),pre)
     self.assertTrue(world.condition((f'ywc_tib_{pre}_narrow_ready','=','yes'),'TIB'),pre)
     self.assertTrue(world.condition((ready,'=','yes'),'TIB'),pre)
     self.assertEqual(sum(k=='OR' for k,_,_ in parse(body(self.triggers,ready))[0][2]),1,pre)
    # After narrowing, the real final progress helper completes without changing route or charging again.
    state={'net_fixed_income':50,'in_default':False,'grain_price_gap':0.12,'owned_state':False,
     'ywc_tib_grain_route':1,'ywc_tib_grain_scope_narrowed':1,'ywc_tib_grain_paid':1,
     'ywc_v03_tib_v03_tib_grain_credit_started':1,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1}
    world=TibPulseWorld(self.effects,{'TIB':state})
    world.treasury['TIB']=-200
    world.run('ywc_tib_grain_progress_6','TIB')
    self.assertEqual(state['ywc_tib_grain_implementation_complete'],1)
    self.assertEqual(state['ywc_tib_grain_route'],1)
    self.assertEqual(world.treasury['TIB'],-200)
    self.assertNotIn('ywc_tib_grain_pending_event',state)
    world.run('ywc_tib_grain_monthly_review','TIB');world.advance_months(6);world.run('ywc_tib_grain_monthly_review','TIB')
    self.assertEqual(state['ywc_v03_tib_v03_tib_grain_credit_outcome'],3)

 def test_eligibility_recovery_clears_stale_queued_notices(self):
    for pre in PREFIX:
     facts={'register':{'net_fixed_income':20,'laws':['law_type:law_serfdom']},'grain':{'net_fixed_income':20,'grain_price_gap':0.12},'schools':{'net_fixed_income':20,'laws':['law_type:law_public_schools']}}[pre]
     state={**facts,f'ywc_v03_tib_{SLUGS[PREFIX.index(pre)]}_started':1,
      f'ywc_tib_{pre}_paid':1,f'ywc_tib_{pre}_route':1,f'ywc_tib_{pre}_stage':1,f'ywc_tib_{pre}_scope_narrowed':1,
      f'ywc_tib_{pre}_blocked_started':1,f'ywc_tib_{pre}_blocked_12_due':1,
      f'ywc_tib_{pre}_notice_12_event':{'register':1005,'grain':1014,'schools':1023}[pre],
      f'ywc_tib_{pre}_notice_36_event':{'register':1006,'grain':1015,'schools':1024}[pre],
      f'ywc_tib_{pre}_notice_12_sent':1,f'ywc_tib_{pre}_notice_36_sent':1}
     world=TibPulseWorld(self.effects,{'TIB':state});world.run(f'ywc_tib_{pre}_monthly_review','TIB')
     for suffix in ('blocked_started','blocked_12_due','blocked_36_due','notice_12_event','notice_36_event','notice_12_sent','notice_36_sent'):
      self.assertNotIn(f'ywc_tib_{pre}_{suffix}',state,(pre,suffix))

 def test_paid_grain_subsidy_matures_only_as_limited_outcome(self):
    world=TibPulseWorld(self.effects,{'TIB':{'test_ready':True,'grain_price_gap':0.12,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
     'ywc_v03_tib_v03_tib_grain_credit_started':1,'ywc_tib_grain_paid':1,'ywc_tib_grain_route':3,'ywc_tib_grain_implementation_complete':1}})
    world.run('ywc_tib_grain_monthly_review','TIB');world.advance_months(3);world.run('ywc_tib_grain_monthly_review','TIB')
    state=world.countries['TIB']
    self.assertEqual(state['ywc_v03_tib_v03_tib_grain_credit_outcome'],3)
    self.assertNotEqual(state['ywc_v03_tib_v03_tib_grain_credit_outcome'],1)
    self.assertEqual(state['ywc_v03_active_arc_count'],0)

 def test_legacy_campaign_result_is_preserved_by_every_tib_closer(self):
    for pre,slug in zip(PREFIX,SLUGS):
     expected={'withdraw':4,'setback':4,'success':3}
     for close_kind,outcome in expected.items():
      for previous in (1,2,3,4):
       state={'ywc_campaign_tib_c1_outcome':previous,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
        f'ywc_v03_tib_{slug}_started':1,'test_ready':True,'net_fixed_income':10,
        f'ywc_tib_{pre}_route':3,f'ywc_tib_{pre}_paid':1,f'ywc_tib_{pre}_implementation_complete':1,
        f'ywc_tib_{pre}_six_months_complete':1}
       world=TibPulseWorld(self.effects,{'TIB':state})
       if close_kind=='withdraw': world.run(f'ywc_tib_{pre}_withdraw','TIB')
       elif close_kind=='setback': world.run(f'ywc_tib_{pre}_settle_setback','TIB')
       else: world.run(f'ywc_tib_{pre}_monthly_review','TIB')
       self.assertEqual(state['ywc_campaign_tib_c1_outcome'],previous,(pre,close_kind,previous))
       self.assertEqual(state[f'ywc_v03_tib_{slug}_outcome'],outcome,(pre,close_kind,previous))
       self.assertEqual(state['ywc_v03_active_arc_count'],0,(pre,close_kind,previous))
       if close_kind=='withdraw': world.run(f'ywc_tib_{pre}_withdraw','TIB')
       elif close_kind=='setback': world.run(f'ywc_tib_{pre}_settle_setback','TIB')
       else: world.run(f'ywc_tib_{pre}_monthly_review','TIB')
       self.assertEqual(state['ywc_campaign_tib_c1_outcome'],previous,(pre,close_kind,'replay'))
       self.assertEqual(state['ywc_v03_active_arc_count'],0,(pre,close_kind,'replay'))

 def test_missing_legacy_result_bridges_once_and_new_arcs_stay_independent(self):
    expected={'withdraw':4,'setback':4,'success':3}
    for i,(pre,slug) in enumerate(zip(PREFIX,SLUGS)):
     for close_kind,outcome in expected.items():
      state={'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
       f'ywc_v03_tib_{slug}_started':1,'test_ready':True,'net_fixed_income':10,
       f'ywc_tib_{pre}_route':3,f'ywc_tib_{pre}_paid':1,f'ywc_tib_{pre}_implementation_complete':1,
       f'ywc_tib_{pre}_six_months_complete':1}
      world=TibPulseWorld(self.effects,{'TIB':state})
      close=(lambda:world.run(f'ywc_tib_{pre}_withdraw','TIB')) if close_kind=='withdraw' else (lambda:world.run(f'ywc_tib_{pre}_settle_setback','TIB')) if close_kind=='setback' else (lambda:world.run(f'ywc_tib_{pre}_monthly_review','TIB'))
      close()
      self.assertEqual(state['ywc_campaign_tib_c1_outcome'],outcome,(pre,close_kind))
      self.assertEqual(state[f'ywc_v03_tib_{slug}_outcome'],outcome,(pre,close_kind))
      close()
      self.assertEqual(state['ywc_campaign_tib_c1_outcome'],outcome,(pre,close_kind,'idempotent'))
      other=(i+1)%len(PREFIX); other_pre=PREFIX[other]; other_slug=SLUGS[other]
      state['ywc_v03_active_arc_count']=1;state['ywc_v03_visible_task_count']=1
      state[f'ywc_v03_tib_{other_slug}_started']=1
      world.run(f'ywc_tib_{other_pre}_withdraw','TIB')
      self.assertEqual(state['ywc_campaign_tib_c1_outcome'],outcome,(pre,close_kind,'cross_arc'))
      self.assertEqual(state[f'ywc_v03_tib_{other_slug}_outcome'],4,(pre,other_pre))

if __name__=='__main__': unittest.main()

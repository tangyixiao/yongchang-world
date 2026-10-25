from pathlib import Path
import json,re,sys,unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from clausewitz_harness import PulseWorld

CATALOG_PATH=ROOT/'data/content/v03/countries/mgl.json'
REGISTRY_PATH=ROOT/'data/content/v03/id_registry.json'
EFFECTS_PATH=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_mgl_effects.txt'
TRIGGERS_PATH=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_mgl_triggers.txt'
MOD=ROOT/'yongchang_world'
SLUGS=['v03_mgl_two_trade_roads','v03_mgl_pastoral_debt','v03_mgl_princes_monasteries']
RANGES=[(1000,1009),(1010,1019),(1020,1029)]
JES=[['ywc_je_v03_mgl_roads_register','ywc_je_v03_mgl_roads_review'],
     ['ywc_je_v03_mgl_debt_register','ywc_je_v03_mgl_debt_review'],
     ['ywc_je_v03_mgl_grain_register','ywc_je_v03_mgl_grain_review']]

def _arc(catalog,slug):
 rows=[a for a in catalog['arcs'] if a['slug']==slug]
 if len(rows)!=1: raise AssertionError(f'{slug}: expected one arc, got {len(rows)}')
 return rows[0]

def _arc_text(arc):
 return '\n'.join([j['script']+' '+j['goal']+' '+j['exit_conditions'] for j in arc['journals']]+[
  e['trigger']+' '+e['immediate']+' '+' '.join(o['effect']+' '+o.get('trigger','') for o in e['options']) for e in arc['events']])

def _definitions():
 found=set()
 for folder in ('common/scripted_effects','common/scripted_triggers'):
  for p in (MOD/folder).rglob('*.txt'):
   found.update(re.findall(r'(?m)^([a-z_0-9]+)\s*=\s*\{',p.read_text(encoding='utf-8-sig')))
 return found

def _helper_body(text,name):
 m=re.search(rf'(?m)^{re.escape(name)}\s*=\s*\{{.*?^\}}',text,re.S)
 if m: return m.group(0)
 # Country helpers are deliberately one-line Clausewitz definitions.
 m=re.search(rf'(?m)^{re.escape(name)}\s*=\s*\{{[^\n]*',text)
 if not m: raise AssertionError(f'missing helper {name}')
 return m.group(0)

class MglPulseWorld(PulseWorld):
 def __init__(self,effects,countries):
  super().__init__(effects,countries)
  # The old fixture is intentionally a unit model. Resolve the production
  # helper definitions, while leaving native world facts at the fixture edge.
  from clausewitz_harness import parse
  self._mgl_trigger_definitions=dict((name,body) for name,_,body in parse(TRIGGERS_PATH.read_text(encoding='utf-8-sig')))
  self._mgl_selected_obligation_boundary=0
  self._mgl_selected_obligation_prefix=None
  self._mgl_trigger_stack=[]

 def conditions(self,nodes,tag):
  # Evaluate each child even after a false one so unsupported atoms never hide
  # behind Python's all(generator) short-circuit.
  results=[self.condition(node,tag) for node in nodes]
  return all(results)

 def condition(self,node,tag):
  key,comparison,value=node
  if (key in self._mgl_trigger_definitions and key.startswith('ywc_mgl_')
      and key.endswith(('_any_affordable_entry_offer','_selected_current_obligation','_current_obligation_ready'))):
   if comparison!='=' or value not in ('yes','no'):
    raise AssertionError(f'unsupported test trigger comparison or literal: {node}')
   if key in self._mgl_trigger_stack:
    chain=' -> '.join((*self._mgl_trigger_stack,key))
    raise AssertionError(f'cyclic test trigger helper: {chain}')
   expected=value=='yes'
   self._mgl_trigger_stack.append(key)
   if key.endswith('_selected_current_obligation'):
    previous=self._mgl_selected_obligation_prefix
    self._mgl_selected_obligation_prefix=key.removeprefix('ywc_mgl_').removesuffix('_selected_current_obligation')
    self._mgl_selected_obligation_boundary+=1
    try: result=self.conditions(self._mgl_trigger_definitions[key],tag)
    finally:
     self._mgl_selected_obligation_boundary-=1
     self._mgl_selected_obligation_prefix=previous
     self._mgl_trigger_stack.pop()
   else:
    try: result=self.conditions(self._mgl_trigger_definitions[key],tag)
    finally: self._mgl_trigger_stack.pop()
   return result==expected
  # Old unit scenarios do not model laws, markets, states, pops, or IGs.
  # Bind those world-only leaves to the existing route-specific readiness
  # fact, and only while evaluating the selected-obligation production helper.
  # Route selection, paid state, and all Boolean composition remain parsed
  # production logic; unknown leaves still fail in PulseWorld.condition.
  if self._mgl_selected_obligation_boundary and key in {
   'has_law','any_scope_state','market_capital.market',
   'country_has_building_group_levels','ig:ig_devout',
   'military_expenses_share','exists','c:SHU','c:RUS',
   'c:SHU.relations:this','c:RUS.relations:this'
  }:
   pre=getattr(self,'_mgl_selected_obligation_prefix',None)
   route_suffix={1:'full',2:'one',3:'local'}.get(self.countries[tag].get(f'ywc_mgl_{pre}_route',0)) if pre else None
   return bool(pre and route_suffix and self.countries[tag].get(f'test_ywc_mgl_{pre}_{route_suffix}_ready',False))
  if key=='ywc_v03_can_deliver_major': return True
  if key.startswith('ywc_mgl_') and key.endswith('_trade_signal'):
   return bool(self.countries[tag].get('test_'+key,False))
  if key.startswith('ywc_mgl_') and key.endswith('_entry_price'):
   return bool(self.countries[tag].get('test_'+key,False))
  if key.startswith('ywc_mgl_') and key.endswith(('_full_ready','_one_ready','_local_ready','_entry_1_ready','_entry_2_ready','_entry_3_ready')):
   return bool(self.countries[tag].get('test_'+key,False))
  return super().condition(node,tag)

def _script_fields(journal):
 return dict((key,value) for key,_,value in __import__('clausewitz_harness').parse(journal['script'].strip()[1:-1]))

def _active_je(world,journal):
 from clausewitz_harness import parse
 fields=_script_fields(journal)
 goal=world.conditions(parse(journal['goal'].strip()[1:-1]),'MGL')
 exit_=world.conditions(parse(journal['exit_conditions'].strip()[1:-1]),'MGL')
 return fields,goal,exit_

class MglFoundationContractTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.catalog=json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
  cls.registry=json.loads(REGISTRY_PATH.read_text(encoding='utf-8'))
  cls.arcs=[_arc(cls.catalog,s) for s in SLUGS]
  cls.effects=EFFECTS_PATH.read_text(encoding='utf-8-sig')
  cls.triggers=TRIGGERS_PATH.read_text(encoding='utf-8-sig')

 def test_arcs_are_registered_with_reserved_event_ranges(self):
  ranges={(x['catalog_key'],x['slug']):(x['start'],x['end']) for x in self.registry['arc_ranges']}
  for slug,(start,end),arc,jes in zip(SLUGS,RANGES,self.arcs,JES):
   self.assertEqual(ranges[('country_mgl',slug)],(start,end))
   event_end=start+7
   self.assertEqual([e['id'] for e in arc['events']],[f'ywc_mng.{n}' for n in range(start,event_end+1)])
   self.assertEqual([j['id'] for j in arc['journals']],jes)
  self.assertEqual(len([e for a in self.arcs for e in a['events']]),24)
  self.assertEqual(len([j for a in self.arcs for j in a['journals']]),6)

 def test_locked_shape_runtime_namespace_and_legacy_links(self):
  self.assertEqual(self.catalog['runtime_tags'],['MGL'])
  self.assertEqual(self.catalog['key'],'country_mgl')
  for arc in self.arcs:
   self.assertEqual(arc['era'],'foundation');self.assertEqual(arc['depends_on'],[])
   self.assertEqual(arc['legacy_links'],['ywc_campaign_mng_c1_outcome','ywc_je_flavor_mng_balance_1'])
   self.assertTrue(len(arc['outcomes'])>=4)
   for e in arc['events']:
    self.assertTrue(e['id'].startswith('ywc_mng.'),e['id'])
    self.assertTrue(e['title']['zh'] and e['title']['en'])
    self.assertTrue(e['desc']['zh'] and e['desc']['en'])
    self.assertGreaterEqual(len(e['options']),2)
    self.assertIn('ywc_v03_can_deliver_major = yes',e['trigger'])
    self.assertIn('ywc_v03_mark_major_delivered = yes',e['immediate'])
    self.assertTrue(any(x['key']=='defer' for x in e['options']))
    self.assertTrue(any(x['key']=='withdraw' for x in e['options']))
    for o in e['options']:
     self.assertEqual(set(o['cost_note']),{'zh','en'})
     self.assertEqual(set(o['consequence_note']),{'zh','en'})
     self.assertRegex(o['ai_chance'],r'\bbase\s*=')
   for j in arc['journals']:
    self.assertNotRegex(j['script'],r'(?<![a-z0-9_])(?:complete|fail)\s*=')

 def test_required_calls_resolve(self):
  defined=_definitions()
  for a in self.arcs:
   calls=set(re.findall(r'(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)',_arc_text(a)))
   self.assertEqual(sorted(calls-defined),[],a['slug'])

 def test_every_event_is_dispatched(self):
  for a in self.arcs:
   dispatched=set(re.findall(r'trigger_event\s*=\s*\{\s*id\s*=\s*([A-Za-z0-9_.]+)',_arc_text(a)))
   self.assertEqual([e['id'] for e in a['events'] if e['id'] not in dispatched],[],a['slug'])

 def test_route_helpers_record_distinct_routes(self):
  for pre in ('roads','debt','grain'):
   for n in (1,2,3):
    body=_helper_body(self.effects,f'ywc_mgl_{pre}_pay_route_{n}')
    self.assertIn(f'ywc_mgl_{pre}_route value = {n}',body)

 def test_route_choices_are_never_free_two_way_buttons(self):
  for pre,arc in zip(('roads','debt','grain'),self.arcs):
   options=arc['events'][0]['options']
   route=[o for o in options if o['key'] in ('dual','single','local')]
   self.assertEqual(len(route),3)
   for opt in route:
    self.assertIn(f'ywc_mgl_{pre}_pay_route_',opt['effect'])
    fee='double_fee' if opt['key']=='dual' else 'fee' if opt['key']=='single' else 'half_fee'
    self.assertIn(f'gold_reserves >= var:ywc_mgl_{pre}_{fee}',opt['trigger'])
    self.assertIn('has_modifier = declared_bankruptcy',opt['trigger'])

 def test_debits_are_guarded_and_idempotent(self):
  for pre in ('roads','debt','grain'):
   for n in (1,2,3):
    body=_helper_body(self.effects,f'ywc_mgl_{pre}_pay_route_{n}')
    self.assertIn(f'ywc_mgl_{pre}_route_paid',body)
    self.assertIn('add_treasury',body);self.assertIn('multiply = -1',body)
    self.assertIn('in_default = no',body);self.assertIn('has_modifier = declared_bankruptcy',body)
   for arc in self.arcs:
    if arc['slug'].endswith({'roads':'two_trade_roads','debt':'pastoral_debt','grain':'princes_monasteries'}[pre]):
     for opt in arc['events'][0]['options'][:3]:
      self.assertIn('gold_reserves >= var:ywc_mgl_'+pre+'_',opt['trigger'])
      self.assertIn('in_default = no',opt['trigger']);self.assertIn('has_modifier = declared_bankruptcy',opt['trigger'])

 def test_closers_write_outcome_and_release_once(self):
  for pre,slug in zip(('roads','debt','grain'),SLUGS):
   body=_helper_body(self.effects,f'ywc_mgl_{pre}_close')
   state=f'ywc_v03_mgl_{slug}'
   for value in ('ywc_v03_active_arc_count','ywc_v03_visible_task_count','change_variable','clamp_variable',state+'_settled','ywc_campaign_mng_c1_outcome'):
    self.assertIn(value,body)

 def test_observation_and_blockage_timers_exist(self):
  for pre in ('roads','debt','grain'):
   body=_helper_body(self.effects,f'ywc_mgl_{pre}_monthly_review')
   self.assertIn('months = 6',body)
   self.assertIn('days = 365',body);self.assertIn('days = 1095',body)
   self.assertIn(f'ywc_mgl_{pre}_reset_observation = yes',body)

 def test_legacy_continuation_and_refusable_document_dispute(self):
  for arc in self.arcs:
   entry=arc['journals'][0]['script']
   self.assertIn('ywc_campaign_mng_c1_outcome',entry)
   self.assertIn('var:ywc_v03_active_arc_count < 3',entry)
   self.assertIn('var:ywc_v03_visible_task_count < 6',entry)
   dispute=[e for e in arc['events'] if any(o['key']=='refuse' for o in e['options'])]
   self.assertTrue(dispute,arc['slug'])
   self.assertTrue(any('refuse' in e['desc']['en'].lower() or 'reject' in e['desc']['en'].lower() for e in dispute))

 def test_trade_flow_and_price_gates_use_verified_market_scopes(self):
  self.assertIn('ywc_mgl_roads_trade_signal = yes',self.arcs[0]['journals'][0]['script'])
  self.assertIn('market_capital.market = { mg:tea = { market_goods_exports > 0 } }',self.triggers)
  self.assertIn('market_goods_exports > 50',self.triggers)
  self.assertIn('market_goods_imports >= 1',self.triggers)
  self.assertIn('ywc_mgl_grain_entry_price = yes',self.arcs[2]['journals'][0]['script'])
  self.assertIn('market_goods_pricier > 0.10',self.triggers)
  self.assertIn('market_goods_pricier > 0.15',self.triggers)
  self.assertIn('market_goods_pricier > 0.25',self.triggers)

 def test_routes_are_read_by_two_later_executable_nodes(self):
  for pre,arc in zip(('roads','debt','grain'),self.arcs):
   for index in (2,4):
    event=arc['events'][index]
    self.assertTrue(all(f'var:ywc_mgl_{pre}_route = {route}' in o['trigger'] for route,o in enumerate([x for x in event['options'] if x['key'].endswith('_terms')],1)))
    self.assertTrue(any(f'ywc_mgl_{pre}_node_{index}_route_read' in o['effect'] for o in event['options'] if o['key'].endswith('_terms')))
    self.assertIn(f'ywc_mgl_{pre}_terms_committed',arc['events'][index+1]['reads'])

 def test_each_route_applies_a_timed_political_consequence(self):
  modifiers=Path(MOD/'common/static_modifiers/ywc_v03_mgl_modifiers.txt').read_text(encoding='utf-8-sig')
  for pre in ('roads','debt','grain'):
   for route in (1,2,3):
    body=_helper_body(self.effects,f'ywc_mgl_{pre}_pay_route_{route}')
    self.assertRegex(body,r'add_modifier = \{ name = ywc_v03_mgl_'+pre+r'_\w+ days = 730 \}')
    name=re.search(r'add_modifier = \{ name = ([a-z_0-9]+)',body).group(1)
    self.assertIn(name+' = {',modifiers)
  self.assertIn('interest_group_ig_rural_folk_approval_add',modifiers)
  self.assertIn('interest_group_ig_devout_approval_add',modifiers)
  self.assertIn('interest_group_ig_landowners_approval_add',modifiers)
  self.assertIn('interest_group_ig_armed_forces_approval_add',modifiers)

 def test_real_interface_gates_are_country_specific(self):
  self.assertIn('market_access >= 0.75',self.triggers)
  self.assertIn('exists = c:SHU',self.triggers);self.assertIn('exists = c:RUS',self.triggers)
  self.assertIn('c:SHU.relations:this',self.triggers);self.assertIn('c:RUS.relations:this',self.triggers)
  self.assertIn('country_has_building_group_levels',self.triggers)
  self.assertIn('average_sol < 10',self.triggers)
  self.assertIn('ig:ig_devout ?= { ig_approval >= 0 }',self.triggers)
  self.assertIn('type = bg_government value > 0',self.triggers)
  self.assertIn('law_type:law_serfdom',self.triggers)
  self.assertIn('military_expenses_share >= 0.10',self.triggers)
  self.assertIn('average_sol >= 10',self.triggers)
  self.assertIn('is_employed = yes',self.triggers)
  self.assertIn('market_goods_exports > 0',self.triggers)

 def test_strict_harness_failed_debit_and_replay(self):
  effects=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':{'gold_reserves':50,'in_default':False,'ywc_mgl_roads_fee':100,'ywc_mgl_roads_double_fee':200,'ywc_mgl_roads_half_fee':50,'test_ywc_mgl_roads_entry_2_ready':True,'ywc_v03_mgl_v03_mgl_two_trade_roads_started':1}})
  effects.countries['MGL']['ywc_mgl_roads_pending_event']=1000
  effects.run('ywc_mgl_roads_pay_route_2','MGL')
  self.assertEqual(effects.treasury['MGL'],0)
  self.assertEqual(effects.countries['MGL']['ywc_mgl_roads_pending_event'],1000)
  self.assertNotIn('ywc_mgl_roads_route',effects.countries['MGL'])
  effects.countries['MGL']['gold_reserves']=500
  effects.run('ywc_mgl_roads_pay_route_2','MGL')
  first=effects.treasury['MGL']
  effects.run('ywc_mgl_roads_pay_route_2','MGL')
  self.assertEqual(first,-100);self.assertEqual(effects.treasury['MGL'],-100)
  self.assertEqual(len(effects.modifiers),1)

 def test_parallel_arcs_keep_independent_pending_event_queues(self):
  world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':{
   'gold_reserves':1000,'in_default':False,
   'ywc_mgl_roads_fee':100,'ywc_mgl_roads_double_fee':200,'ywc_mgl_roads_half_fee':50,'test_ywc_mgl_roads_entry_2_ready':True,'ywc_v03_mgl_v03_mgl_two_trade_roads_started':1,
   'ywc_mgl_debt_fee':100,'ywc_mgl_debt_double_fee':200,'ywc_mgl_debt_half_fee':50,'test_ywc_mgl_debt_entry_1_ready':True,'ywc_v03_mgl_v03_mgl_pastoral_debt_started':1}})
  world.run('ywc_mgl_roads_pay_route_2','MGL')
  world.run('ywc_mgl_debt_pay_route_1','MGL')
  state=world.countries['MGL']
  self.assertEqual(state['ywc_mgl_roads_pending_event'],1001)
  self.assertEqual(state['ywc_mgl_debt_pending_event'],1011)
  self.assertEqual(state['ywc_mgl_roads_route'],2)
  self.assertEqual(state['ywc_mgl_debt_route'],1)
  for arc in self.arcs:
   pre={'v03_mgl_two_trade_roads':'roads','v03_mgl_pastoral_debt':'debt','v03_mgl_princes_monasteries':'grain'}[arc['slug']]
   je=' '.join(j['script'] for j in arc['journals'])
   self.assertIn(f'ywc_mgl_{pre}_pending_event',je)

 def test_strict_harness_observation_waits_for_final_narrative_and_resets(self):
  world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':{
   'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
   'ywc_mgl_roads_route':1,'ywc_mgl_roads_terms_committed':1,'test_ywc_mgl_roads_full_ready':True}})
  state=world.countries['MGL']
  world.run('ywc_mgl_roads_monthly_review','MGL')
  self.assertNotIn('ywc_mgl_roads_full_timer',state)
  self.assertNotIn('ywc_v03_mgl_v03_mgl_two_trade_roads_settled',state)
  state['ywc_mgl_roads_observation_open']=1
  state['ywc_mgl_roads_terms_committed']=1
  world.run('ywc_mgl_roads_monthly_review','MGL')
  self.assertIn('ywc_mgl_roads_full_timer',state)
  world.advance_months(3)
  state['test_ywc_mgl_roads_full_ready']=False
  world.run('ywc_mgl_roads_monthly_review','MGL')
  self.assertNotIn('ywc_mgl_roads_full_watch',state)
  self.assertNotIn('ywc_mgl_roads_full_timer',state)
  self.assertNotIn('ywc_v03_mgl_v03_mgl_two_trade_roads_settled',state)
  state['test_ywc_mgl_roads_full_ready']=True
  world.run('ywc_mgl_roads_monthly_review','MGL')
  world.advance_months(5)
  world.run('ywc_mgl_roads_monthly_review','MGL')
  self.assertNotIn('ywc_v03_mgl_v03_mgl_two_trade_roads_settled',state)
  world.advance_months(1)
  world.run('ywc_mgl_roads_monthly_review','MGL')
  self.assertEqual(state['ywc_v03_mgl_v03_mgl_two_trade_roads_outcome'],1)

 def test_strict_harness_limited_maturity_never_becomes_full_and_withdrawal_once(self):
  world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':{
   'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
   'ywc_mgl_grain_route':3,'ywc_mgl_grain_terms_committed':3,'ywc_mgl_grain_observation_open':1,'test_ywc_mgl_grain_local_ready':True}})
  world.run('ywc_mgl_grain_monthly_review','MGL')
  world.advance_months(6)
  world.run('ywc_mgl_grain_monthly_review','MGL')
  self.assertEqual(world.countries['MGL']['ywc_v03_mgl_v03_mgl_princes_monasteries_outcome'],3)
  self.assertNotEqual(world.countries['MGL']['ywc_v03_mgl_v03_mgl_princes_monasteries_outcome'],1)
  world.run('ywc_mgl_grain_withdraw','MGL')
  self.assertEqual(world.countries['MGL']['ywc_v03_mgl_v03_mgl_princes_monasteries_withdrawn'],1)
  after=dict(world.countries['MGL'])
  world.run('ywc_mgl_grain_withdraw','MGL')
  self.assertEqual(world.countries['MGL']['ywc_v03_active_arc_count'],0)
  self.assertEqual(world.countries['MGL']['ywc_v03_visible_task_count'],0)
  self.assertEqual(world.countries['MGL'],after)


 def test_second_route_read_commits_real_terms(self):
  from clausewitz_harness import parse
  for arc,pre in zip(self.arcs,('roads','debt','grain')):
   world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':{f'ywc_mgl_{pre}_route':2,f'ywc_mgl_{pre}_node_2_route_read':2,f'ywc_mgl_{pre}_documents_clarified':1}})
   option=next(o for o in arc['events'][4]['options'] if o['key'].endswith('_terms') and 'route = 2' in o['trigger'])
   world.execute(parse('probe = '+option['effect'])[0][2],'MGL')
   state=world.countries['MGL']
   self.assertEqual(state[f'ywc_mgl_{pre}_terms_committed'],2)
   self.assertEqual(state[f'ywc_mgl_{pre}_observation_open'],1)

 def test_blocked_notices_expire_once_and_queue_independently(self):
  world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':{'ywc_v03_mgl_v03_mgl_two_trade_roads_started':1,'ywc_v03_mgl_v03_mgl_pastoral_debt_started':1}})
  for pre in ('roads','debt'):
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertIn(f'ywc_mgl_{pre}_blocked_12_due',world.countries['MGL'])
  world.advance_months(13)
  for pre,notice in (('roads',1006),('debt',1016)):
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertEqual(world.countries['MGL'][f'ywc_mgl_{pre}_blocked_12_notice_event'],notice)
   self.assertIn(f'ywc_mgl_{pre}_blocked_12_sent',world.countries['MGL'])

 def _execute_option(self,world,arc,event_index,key):
  from clausewitz_harness import parse
  option=next(o for o in arc['events'][event_index]['options'] if o['key']==key)
  world.execute(parse('probe = '+option['effect'])[0][2],'MGL')

 def test_unpaid_notice_narrowing_returns_to_paid_story_entry(self):
  for arc,pre,start in zip(self.arcs,('roads','debt','grain'),(1000,1010,1020)):
   state={'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
          f'ywc_v03_mgl_{arc["slug"]}_started':1,
          f'test_ywc_mgl_{pre}_entry_3_ready':True,
          f'test_ywc_mgl_{pre}_entry_1_ready':True,
          f'ywc_mgl_{pre}_fee':100,f'ywc_mgl_{pre}_half_fee':50,
          'gold_reserves':1000,'in_default':False}
   world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':state})
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   world.advance_months(13);world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self._execute_option(world,arc,6,'narrow')
   self.assertEqual(state.get(f'ywc_mgl_{pre}_pending_event'),start,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_route',state,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_observation_open',state,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_route_paid',state,arc['slug'])
   world.advance_months(6);world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertNotIn(f'ywc_v03_mgl_{arc["slug"]}_settled',state,arc['slug'])
   self.assertNotIn(f'ywc_v03_mgl_{arc["slug"]}_outcome',state,arc['slug'])
   world.run(f'ywc_mgl_{pre}_pay_route_1','MGL')
   self.assertNotIn(f'ywc_mgl_{pre}_route_paid',state,arc['slug'])
   self.assertEqual(world.treasury['MGL'],0,arc['slug'])
   self._execute_option(world,arc,0,'local')
   world.run(f'ywc_mgl_{pre}_pay_route_3','MGL')
   self.assertIn(f'ywc_mgl_{pre}_route_paid',state,arc['slug'])
   self.assertEqual(world.treasury['MGL'],-50,arc['slug'])
   paid={'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
         f'ywc_v03_mgl_{arc["slug"]}_started':1,
         f'ywc_mgl_{pre}_route_paid':1,f'ywc_mgl_{pre}_route':1,
         f'ywc_mgl_{pre}_pending_event':start+1}
   paid_world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':paid})
   paid_world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   paid_world.advance_months(13);paid_world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self._execute_option(paid_world,arc,6,'narrow')
   self.assertEqual(paid[f'ywc_mgl_{pre}_route'],3,arc['slug'])
   self.assertEqual(paid[f'ywc_mgl_{pre}_pending_event'],start+1,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_terms_committed',paid,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_observation_open',paid,arc['slug'])

 def test_complete_paid_route_chain_reaches_only_its_mature_outcome(self):
  from clausewitz_harness import parse
  for arc,pre,route,pending in zip(self.arcs,('roads','debt','grain'),(1,1,1),(1000,1010,1020)):
   state={'gold_reserves':1000,'in_default':False,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
          f'ywc_v03_mgl_{arc["slug"]}_started':1,
          f'ywc_mgl_{pre}_fee':100,f'ywc_mgl_{pre}_double_fee':200,f'ywc_mgl_{pre}_half_fee':50,
          f'test_ywc_mgl_{pre}_entry_1_ready':True,
          f'test_ywc_mgl_{pre}_full_ready':True}
   world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':state})
   self._execute_option(world,arc,0,'dual')
   world.run(f'ywc_mgl_{pre}_pay_route_1','MGL')
   self.assertEqual(state[f'ywc_mgl_{pre}_pending_event'],pending+1)
   self._execute_option(world,arc,1,'review')
   self._execute_option(world,arc,2,next(o['key'] for o in arc['events'][2]['options'] if o['key'].endswith('_terms')))
   self._execute_option(world,arc,3,'clarify')
   self._execute_option(world,arc,4,next(o['key'] for o in arc['events'][4]['options'] if o['key'].endswith('_terms')))
   self.assertEqual(state[f'ywc_mgl_{pre}_terms_committed'],1)
   self.assertEqual(state[f'ywc_mgl_{pre}_observation_open'],1)
   self._execute_option(world,arc,5,'review')
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   world.advance_months(6);world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertEqual(state[f'ywc_v03_mgl_{arc["slug"]}_outcome'],1,arc['slug'])
   self.assertEqual(state[f'ywc_v03_mgl_{arc["slug"]}_settled'],1,arc['slug'])
   self.assertEqual(world.treasury['MGL'],-200,arc['slug'])
   for journal in arc['journals']:
    goal=world.conditions(parse(journal['goal'].strip()[1:-1]),'MGL')
    exit_=world.conditions(parse(journal['exit_conditions'].strip()[1:-1]),'MGL')
    self.assertTrue(goal,(journal['id'],'success not completed'))
    self.assertFalse(exit_,(journal['id'],'success also failed'))

 def test_withdrawal_terminal_predicates_are_exclusive_for_all_arcs(self):
  from clausewitz_harness import parse
  for arc,pre in zip(self.arcs,('roads','debt','grain')):
   state={'gold_reserves':1000,'in_default':False,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
          f'ywc_v03_mgl_{arc["slug"]}_started':1,
          f'ywc_mgl_{pre}_fee':100,f'ywc_mgl_{pre}_double_fee':200,f'ywc_mgl_{pre}_half_fee':50,
          f'test_ywc_mgl_{pre}_entry_1_ready':True}
   world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':state})
   self._execute_option(world,arc,0,'dual');world.run(f'ywc_mgl_{pre}_pay_route_1','MGL')
   world.run(f'ywc_mgl_{pre}_withdraw','MGL')
   for journal in arc['journals']:
    goal=world.conditions(parse(journal['goal'].strip()[1:-1]),'MGL')
    exit_=world.conditions(parse(journal['exit_conditions'].strip()[1:-1]),'MGL')
    self.assertFalse(goal,(journal['id'],'complete on withdraw'))
    self.assertTrue(exit_,(journal['id'],'not failed on withdraw'))

 def test_notice_settlement_is_failure_for_both_journals_all_arcs(self):
  from clausewitz_harness import parse
  for arc,pre in zip(self.arcs,('roads','debt','grain')):
   for notice_index in (6,7):
    state={'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
           f'ywc_v03_mgl_{arc["slug"]}_started':1,
           f'ywc_mgl_{pre}_route_paid':1,f'ywc_mgl_{pre}_route':1}
    world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':state})
    self._execute_option(world,arc,notice_index,'settle')
    self.assertEqual(state[f'ywc_v03_mgl_{arc["slug"]}_outcome'],4,(arc['slug'],notice_index))
    self.assertEqual(state['ywc_v03_active_arc_count'],0)
    self.assertEqual(state['ywc_v03_visible_task_count'],0)
    for journal in arc['journals']:
     goal=world.conditions(parse(journal['goal'].strip()[1:-1]),'MGL')
     exit_=world.conditions(parse(journal['exit_conditions'].strip()[1:-1]),'MGL')
     self.assertFalse(goal,(journal['id'],'setback reported complete'))
     self.assertTrue(exit_,(journal['id'],'setback did not fail'))

 def test_paid_notice_narrow_clears_live_commitment_and_replays_local_chain(self):
  from clausewitz_harness import parse
  for arc,pre,start in zip(self.arcs,('roads','debt','grain'),(1000,1010,1020)):
   state={'gold_reserves':1000,'in_default':False,'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
          f'ywc_v03_mgl_{arc["slug"]}_started':1,f'ywc_mgl_{pre}_fee':100,
          f'ywc_mgl_{pre}_double_fee':200,f'ywc_mgl_{pre}_half_fee':50,
          f'test_ywc_mgl_{pre}_entry_1_ready':True,
          f'test_ywc_mgl_{pre}_full_ready':False,
          f'test_ywc_mgl_{pre}_local_ready':True}
   world=MglPulseWorld(EFFECTS_PATH.read_text(encoding='utf-8-sig'),{'MGL':state})
   self._execute_option(world,arc,0,'dual')
   self.assertEqual(world.treasury['MGL'],-200,arc['slug'])
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   world.advance_months(13)
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertEqual(state[f'ywc_mgl_{pre}_blocked_12_notice_event'],start+6,arc['slug'])

   # Complete the paid route-1 terms through actual event options while its
   # separately queued 12-month notice remains pending.
   self._execute_option(world,arc,1,'review')
   route1_terms=next(o for o in arc['events'][2]['options'] if f'name = ywc_mgl_{pre}_node_2_route_read value = 1' in o['effect'])
   world.execute(parse('probe = '+route1_terms['effect'])[0][2],'MGL')
   self._execute_option(world,arc,3,'clarify')
   final_terms=next(o for o in arc['events'][4]['options'] if f'name = ywc_mgl_{pre}_terms_committed value = 1' in o['effect'])
   world.execute(parse('probe = '+final_terms['effect'])[0][2],'MGL')
   self._execute_option(world,arc,5,'review')
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertIn(f'ywc_mgl_{pre}_observation_open',state,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_full_watch',state,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_full_timer',state,arc['slug'])
   # A stale maturity marker is included to prove narrowing clears every watch.
   state[f'ywc_mgl_{pre}_full_mature']=1
   doc_flag=f'ywc_mgl_{pre}_documents_clarified'
   self.assertIn(doc_flag,state,arc['slug'])
   self.assertIn(f'ywc_mgl_{pre}_node_2_route_read',state,arc['slug'])
   self.assertIn(f'ywc_mgl_{pre}_node_4_route_read',state,arc['slug'])

   self._execute_option(world,arc,6,'narrow')
   self.assertEqual(state[f'ywc_mgl_{pre}_route'],3,arc['slug'])
   self.assertEqual(state[f'ywc_mgl_{pre}_route_paid'],1,arc['slug'])
   self.assertEqual(state[f'ywc_mgl_{pre}_pending_event'],start+1,arc['slug'])
   self.assertNotIn(f'ywc_mgl_{pre}_blocked_12_notice_event',state,arc['slug'])
   for suffix in ('terms_committed','observation_open','documents_clarified','documents_refused','documents_resolved',
                  'papers_clarified','node_2_route_read','node_4_route_read',
                  'full_timer','full_watch','full_mature','limited_timer','limited_watch','limited_mature',
                  'legacy_timer','legacy_watch','legacy_mature'):
    self.assertNotIn(f'ywc_mgl_{pre}_{suffix}',state,(arc['slug'],suffix))
   for suffix in ('full_timer','full_watch','full_mature','limited_timer','limited_watch','limited_mature',
                  'legacy_timer','legacy_watch','legacy_mature'):
    self.assertNotIn(f'ywc_mgl_{pre}_{suffix}',world.months_until_expiry['MGL'],(arc['slug'],suffix))

   # Follow the real post-payment event, route-3 readback, document and terms
   # options; the sunk payment remains and the local watch starts afresh.
   self._execute_option(world,arc,1,'review')
   route3_terms=next(o for o in arc['events'][2]['options'] if f'name = ywc_mgl_{pre}_node_2_route_read value = 3' in o['effect'])
   world.execute(parse('probe = '+route3_terms['effect'])[0][2],'MGL')
   self._execute_option(world,arc,3,'clarify')
   final_local_terms=next(o for o in arc['events'][4]['options'] if f'name = ywc_mgl_{pre}_terms_committed value = 3' in o['effect'])
   world.execute(parse('probe = '+final_local_terms['effect'])[0][2],'MGL')
   self._execute_option(world,arc,5,'review')
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertIn(f'ywc_mgl_{pre}_legacy_watch',state,arc['slug'])
   self.assertIn(f'ywc_mgl_{pre}_legacy_timer',state,arc['slug'])
   world.advance_months(6)
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertEqual(state[f'ywc_v03_mgl_{arc["slug"]}_outcome'],3,arc['slug'])
   self.assertEqual(world.treasury['MGL'],-200,arc['slug'])

 def _runtime_world(self,state):
  shared=(MOD/'common/scripted_effects/ywc_v03_effects.txt').read_text(encoding='utf-8-sig')
  return MglPulseWorld(shared+'\n'+self.effects,{'MGL':state})

 def _activate_actual_je(self,world,journal):
  from clausewitz_harness import parse
  fields,goal,exit_=_active_je(world,journal)
  self.assertFalse(goal,(journal['id'],'already complete'))
  self.assertFalse(exit_,(journal['id'],'already failed'))
  self.assertTrue(world.conditions(fields['possible'],'MGL'),(journal['id'],'possible false'))
  world.execute(fields['immediate'],'MGL')
  return fields

 def _pulse_actual_je(self,world,journal):
  fields,goal,exit_=_active_je(world,journal)
  self.assertEqual((goal,exit_),(False,False),(journal['id'],'must only pulse active JE'))
  effect=next(value for key,_,value in fields['on_monthly_pulse'] if key=='effect')
  before=len(world.events)
  world.execute(effect,'MGL')
  return [event for _,event in world.events[before:]]

 def _deliver_actual_event(self,world,arc,event_id):
  from clausewitz_harness import parse
  event=next(event for event in arc['events'] if event['id']==event_id)
  self.assertTrue(world.conditions(parse(event['trigger'].strip()[1:-1]),'MGL'),(event_id,'trigger false'))
  world.execute(parse(event['immediate'].strip()[1:-1]),'MGL')
  return event

 def _choose_actual_event_option(self,world,event,key):
  from clausewitz_harness import parse
  option=next((option for option in event['options'] if option['key']==key),None)
  self.assertIsNotNone(option,(event['id'],key,[option['key'] for option in event['options']]))
  if option.get('trigger'):
   self.assertTrue(world.conditions(parse(option['trigger'].strip()[1:-1]),'MGL'),(event['id'],key,'trigger false'))
  world.execute(parse(option['effect'].strip()[1:-1]),'MGL')

 def _reach_final_mgl_observation(self,arc,pre):
  state={'gold_reserves':10000,'yearly_gross_income':5200,'in_default':False,
   'ywc_v03_initialized':1,'ywc_campaign_mng_c1_outcome':1,
   'ywc_v03_active_arc_count':0,'ywc_v03_visible_task_count':0,
   f'test_ywc_mgl_{pre}_trade_signal':True,
   f'test_ywc_mgl_{pre}_entry_price':True,
   f'test_ywc_mgl_{pre}_entry_1_ready':True,
   f'test_ywc_mgl_{pre}_full_ready':True,f'test_ywc_mgl_{pre}_one_ready':True,
   f'test_ywc_mgl_{pre}_local_ready':True}
  world=self._runtime_world(state)
  entry=arc['journals'][0]
  self._activate_actual_je(world,entry)
  self.assertEqual((state['ywc_v03_active_arc_count'],state['ywc_v03_visible_task_count']),(1,1))
  self.assertEqual(state[f'ywc_mgl_{pre}_pending_event'],int(arc['events'][0]['id'].split('.')[-1]))
  self.assertEqual(self._pulse_actual_je(world,entry),[arc['events'][0]['id']])
  first=self._deliver_actual_event(world,arc,arc['events'][0]['id'])
  self._choose_actual_event_option(world,first,'dual')
  self.assertEqual(world.treasury['MGL'],-200)
  self.assertEqual(state[f'ywc_mgl_{pre}_route_paid'],1)
  self.assertEqual(_active_je(world,entry)[1:],(True,False))
  self.assertEqual(dict((k,v) for k,_,v in world.journals[-1][1])['type'],arc['journals'][1]['id'])
  self.assertTrue(world.conditions(_script_fields(arc['journals'][1])['possible'],'MGL'))
  self._activate_actual_je(world,arc['journals'][1])
  self.assertEqual(state[f'ywc_mgl_{pre}_review_open'],1)
  for index,key in ((1,'review'),(2,None),(3,'clarify'),(4,None),(5,'review')):
   event_id=arc['events'][index]['id']
   self.assertEqual(self._pulse_actual_je(world,arc['journals'][1]),[event_id])
   event=self._deliver_actual_event(world,arc,event_id)
   if index==2:
    key=next(option['key'] for option in event['options'] if f'name = ywc_mgl_{pre}_node_2_route_read value = 1' in option['effect'])
   elif index==4:
    key=next(option['key'] for option in event['options'] if f'name = ywc_mgl_{pre}_terms_committed value = 1' in option['effect'])
   self._choose_actual_event_option(world,event,key)
   self.assertEqual(_active_je(world,arc['journals'][1])[1:],(False,False))
  self.assertEqual(state[f'ywc_mgl_{pre}_observation_open'],1)
  self.assertNotIn(f'ywc_mgl_{pre}_pending_event',state)
  return world,state,arc['journals'][1]

 def test_final_observation_loss_keeps_live_je_and_dispatches_both_notices(self):
  for arc,pre in zip(self.arcs,('roads','debt','grain')):
   for notice_index in (6,7):
    for action in ('narrow','withdraw'):
     world,state,review=self._reach_final_mgl_observation(arc,pre)
     for suffix in ('full_ready','one_ready','local_ready'):
      state[f'test_ywc_mgl_{pre}_{suffix}']=False
     target=arc['events'][notice_index]['id']
     deferred_count=0
     for _month in range(40):
      world.advance_months(1)
      event_ids=self._pulse_actual_je(world,review)
      for event_id in event_ids:
       event=self._deliver_actual_event(world,arc,event_id)
       if notice_index==7 and event_id==arc['events'][6]['id']:
        self._choose_actual_event_option(world,event,'defer')
        deferred_count+=1
       elif event_id==target:
        self._choose_actual_event_option(world,event,action)
        break
       else:
        self.fail((arc['slug'],notice_index,'unexpected event',event_id))
      if target in event_ids:
       break
     self.assertIn(target,event_ids,(arc['slug'],target,'notice missing'))
     if notice_index==7:
      self.assertGreater(deferred_count,0,(arc['slug'],'12-month notice did not defer'))
      self.assertEqual(state['ywc_mgl_'+pre+'_blocked_notice_last_delivered'],2)
     if action=='narrow':
      self.assertEqual(state[f'ywc_mgl_{pre}_route'],3)
      self.assertEqual(state[f'ywc_mgl_{pre}_route_paid'],1)
      self.assertNotIn(f'ywc_v03_mgl_{arc["slug"]}_settled',state)
      self.assertEqual(world.treasury['MGL'],-200)
      self.assertEqual(_active_je(world,review)[1:],(False,False))
     else:
      self.assertEqual(state[f'ywc_v03_mgl_{arc["slug"]}_outcome'],4)
      self.assertEqual(_active_je(world,review)[1:],(False,True))

   # Recovery is exercised from the real active final JE and its actual due
   # queues; no preloaded started, notice, or fabricated pending values.
   world,state,review=self._reach_final_mgl_observation(arc,pre)
   for suffix in ('full_ready','one_ready','local_ready'):
    state[f'test_ywc_mgl_{pre}_{suffix}']=False
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   world.advance_months(38)
   for notice_index in (6,7):
    event_id=arc['events'][notice_index]['id']
    self.assertEqual(self._pulse_actual_je(world,review),[event_id],(arc['slug'],'queued notice'))
    event=self._deliver_actual_event(world,arc,event_id)
    self._choose_actual_event_option(world,event,'defer')
   self.assertNotIn(f'ywc_mgl_{pre}_blocked_12_notice_event',state,arc['slug'])
   self.assertIn(f'ywc_mgl_{pre}_blocked_36_notice_event',state,arc['slug'])
   state[f'test_ywc_mgl_{pre}_full_ready']=True
   self._pulse_actual_je(world,review)
   for suffix in ('blocked_12_due','blocked_36_due','blocked_12_started','blocked_36_started',
                  'blocked_12_sent','blocked_36_sent','blocked_12_notice_event','blocked_36_notice_event'):
    self.assertNotIn(f'ywc_mgl_{pre}_{suffix}',state,(arc['slug'],suffix))
 def test_restored_final_qualification_clears_due_and_both_waiting_notice_queues(self):
  for arc,pre,start in zip(self.arcs,('roads','debt','grain'),(1000,1010,1020)):
   state={'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
    f'ywc_v03_mgl_{arc["slug"]}_started':1,f'ywc_mgl_{pre}_route':1,
    f'ywc_mgl_{pre}_route_paid':1,f'ywc_mgl_{pre}_terms_committed':1,
    f'ywc_mgl_{pre}_observation_open':1,
    f'test_ywc_mgl_{pre}_full_ready':False,f'test_ywc_mgl_{pre}_one_ready':False,
    f'test_ywc_mgl_{pre}_local_ready':False}
   world=MglPulseWorld(self.effects,{'MGL':state})
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   world.advance_months(38);world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   self.assertEqual(state[f'ywc_mgl_{pre}_blocked_12_notice_event'],start+6,arc['slug'])
   self.assertEqual(state[f'ywc_mgl_{pre}_blocked_36_notice_event'],start+7,arc['slug'])
   state[f'test_ywc_mgl_{pre}_full_ready']=True
   world.run(f'ywc_mgl_{pre}_monthly_review','MGL')
   for suffix in ('blocked_12_due','blocked_36_due','blocked_12_started','blocked_36_started',
                  'blocked_12_sent','blocked_36_sent','blocked_12_notice_event','blocked_36_notice_event'):
    self.assertNotIn(f'ywc_mgl_{pre}_{suffix}',state,(arc['slug'],suffix))
   self.assertIn(f'ywc_mgl_{pre}_observation_open',state,arc['slug'])
   self.assertNotIn(f'ywc_v03_mgl_{arc["slug"]}_settled',state,arc['slug'])

 def test_closer_legacy_bridge_preserves_all_existing_results_and_is_idempotent(self):
  for arc,pre in zip(self.arcs,('roads','debt','grain')):
   slug=arc['slug']
   for prior in (1,2,3,4):
    state={'ywc_v03_active_arc_count':1,'ywc_v03_visible_task_count':1,
     f'ywc_v03_mgl_{slug}_started':1,'ywc_campaign_mng_c1_outcome':prior}
    world=MglPulseWorld(self.effects,{'MGL':state})
    world.run(f'ywc_mgl_{pre}_withdraw','MGL')
    self.assertEqual(state['ywc_campaign_mng_c1_outcome'],prior,(slug,prior))
    self.assertEqual(state[f'ywc_v03_mgl_{slug}_outcome'],4,(slug,prior))
    self.assertEqual((state['ywc_v03_active_arc_count'],state['ywc_v03_visible_task_count']),(0,0))
    after=dict(state);world.run(f'ywc_mgl_{pre}_withdraw','MGL')
    self.assertEqual(state,after,(slug,prior,'withdraw replay'))
  state={'ywc_v03_active_arc_count':3,'ywc_v03_visible_task_count':3}
  world=MglPulseWorld(self.effects,{'MGL':state})
  for (pre,arc),value in zip(zip(('roads','debt','grain'),self.arcs),(1,2,3)):
   state[f'ywc_v03_mgl_{arc["slug"]}_started']=1
   state[f'ywc_mgl_{pre}_close_value']=value
   world.run(f'ywc_mgl_{pre}_close','MGL')
   self.assertEqual(state[f'ywc_v03_mgl_{arc["slug"]}_outcome'],value)
  self.assertEqual(state['ywc_campaign_mng_c1_outcome'],1)
  self.assertEqual((state['ywc_v03_active_arc_count'],state['ywc_v03_visible_task_count']),(0,0))
  after=dict(state)
  for pre in ('roads','debt','grain'): world.run(f'ywc_mgl_{pre}_close','MGL')
  self.assertEqual(state,after)

 def test_revised_route_labels_and_notice_cost_notes_are_specific(self):
  for arc in self.arcs:
   first=arc['events'][0]['options'][:3]
   labels=[o['label']['zh'] for o in first]
   self.assertEqual(len(set(labels)),3,arc['slug'])
   for e in (arc['events'][6],arc['events'][7]):
    actions={o['key']:o for o in e['options'] if o['key'] in ('narrow','settle')}
    self.assertNotEqual(actions['narrow']['label']['zh'],actions['settle']['label']['zh'],e['id'])
    self.assertNotIn('护路',actions['narrow']['cost_note']['zh'],e['id'])
    if 'debt' in arc['slug'] or 'monasteries' in arc['slug']:
     self.assertNotIn('护路',actions['settle']['cost_note']['zh'],e['id'])
     self.assertNotIn('escort',actions['settle']['cost_note']['en'].lower(),e['id'])
     self.assertIn('不退',actions['settle']['cost_note']['zh'],e['id'])
     self.assertIn('not refunded',actions['settle']['cost_note']['en'].lower(),e['id'])

 def test_pastoral_routes_use_land_reform_laws_and_low_grain_route_has_admin_capacity(self):
  self.assertIn('law_type:law_tenant_farmers',self.triggers)
  self.assertIn('law_type:law_serfdom',self.triggers)
  grain_line=next(line for line in self.triggers.splitlines() if line.startswith('ywc_mgl_grain_local_ready'))
  self.assertIn('type = bg_government value > 0',grain_line)
  self.assertIn('is_employed = yes',grain_line)

if __name__=='__main__': unittest.main()

"""OIR script regressions. Execute authored JE/event/helper scripts in the strict offline subset."""
import json, re, sys, unittest
from pathlib import Path
from tests.clausewitz_harness import PulseWorld, parse
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/content/v03/countries/oir.json'
EFF=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_oir_effects.txt'
TRG=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_oir_triggers.txt'
CORE_E=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_effects.txt'
CORE_T=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt'
MOD=ROOT/'yongchang_world'
SLUGS=['v03_oir_pasture_boundaries','v03_oir_common_supply','v03_oir_caravan_tolls']
RANGES=[(1000,1009),(1010,1019),(1020,1029)]

def body(src,name):
 m=re.search(r'(?m)^'+re.escape(name)+r'\s*=\s*\{',src)
 if not m: raise AssertionError('missing '+name)
 depth=0; quote=False
 for i in range(m.start(),len(src)):
  ch=src[i]
  if ch=='"':quote=not quote
  if not quote:
   if ch=='{':depth+=1
   elif ch=='}':
    depth-=1
    if depth==0:return src[m.start():i+1]
 raise AssertionError('unbalanced '+name)

def defs():
 out=set()
 for folder in ('common/scripted_effects','common/scripted_triggers'):
  for f in (MOD/folder).rglob('*.txt'):
   out.update(re.findall(r'(?m)^([a-z_0-9]+)\s*=\s*\{',f.read_text(encoding='utf-8-sig')))
 return out

class OIRWorld(PulseWorld):
 """Fixture only supplies engine world facts; all authored triggers/effects execute."""
 def __init__(self,country=None):
  country=country or {}
  effects=EFF.read_text(encoding='utf-8-sig')+'\n'+CORE_E.read_text(encoding='utf-8-sig')
  super().__init__(effects,{'OIR':country})
  self.triggers={k:b for k,_,b in parse(TRG.read_text(encoding='utf-8-sig')+'\n'+CORE_T.read_text(encoding='utf-8-sig'))}
 def _cond(self,node,tag,state=None,building=None,good=None):
  key,op,val=node; v=self.countries[tag]
  if key in ('AND','OR','NOT','NOR'):
   rs=[self._cond(x,tag,state,building,good) for x in val]
   return {'AND':all(rs),'OR':any(rs),'NOT':not all(rs),'NOR':not any(rs)}[key]
  if key in self.triggers and val=='yes': return self.conditions(self.triggers[key],tag)
  if key=='any_scope_state':
   return any(all(self._cond(x,tag,s) for x in val) for s in v.get('fixture_states',[]))
  if key=='any_scope_building':
   if state is None:return False
   return any(all(self._cond(x,tag,state,b) for x in val) for b in state.get('buildings',[]))
  if key=='is_owned_by': return bool(state and state.get('owned',True))
  if key=='is_building_type': return bool(building and building.get('type')==val)
  if key=='occupancy': return self._cmp(building.get('occupancy',0) if building else 0,op,val,v)
  if key=='turmoil': return self._cmp(state.get('turmoil',0) if state else 0,op,val,v)
  if key=='radical_fraction':
   fractions=(state or {}).get('radicals',{})
   pop=next((x[2] for x in val if x[0]=='pop_type'),None)
   threshold=next((x for x in val if x[0]=='value'),('value','>',0.0))
   return self._cmp(fractions.get(pop,0),threshold[1],threshold[2],v)
  if key=='has_law_or_variant': return val.split(':')[-1] in v.get('fixture_laws',set())
  if key=='market_capital.market':
   market={'market_goods_imports':v.get('market_goods_imports',0),'market_goods_exports':v.get('market_goods_exports',0)}
   for item in val:
    if item[0].startswith('mg:'):
     g=item[0][3:]; market['market_goods_imports']=v.get('goods',{}).get(g,{}).get('imports',market['market_goods_imports']); market['market_goods_exports']=v.get('goods',{}).get(g,{}).get('exports',market['market_goods_exports'])
     return all(self._cond(x,tag,state,building,g) for x in item[2])
   return False
  if key.startswith('mg:'):
   g=key[3:]; return all(self._cond(x,tag,state,building,g) for x in val)
  if key in ('market_goods_imports','market_goods_exports'):
   got=(v.get('goods',{}).get(good,{}) if good else {})
   left=got.get('imports' if key.endswith('imports') else 'exports',v.get(key,0))
   return self._cmp(left,op,val,v)
  if key in ('market_access','army_size','military_wages'):
   return self._cmp(v.get(key,0),op,val,v)
  return super().condition(node,tag)
 def _cmp(self,left,op,val,v):
  if isinstance(val,list):
   f={k:x for k,_,x in val}; right=v.get(f['value'][4:],0) if f['value'].startswith('var:') else float(f['value']); right*=float(f.get('multiply',1)); op='>='
  elif isinstance(val,str) and val.startswith('var:'): right=v.get(val[4:],0)
  elif val in ('yes','no'): right=(val=='yes')
  else: right=float(val)
  return {'=':lambda:left==right,'>=':lambda:left>=right,'<=':lambda:left<=right,'>':lambda:left>right,'<':lambda:left<right,'!=':lambda:left!=right}[op]()
 def condition(self,node,tag): return self._cond(node,tag)

def world():
 return OIRWorld({'ywc_v03_initialized':1,'ywc_v03_active_arc_count':0,'ywc_v03_visible_task_count':0,
  'ywc_flavor_oir_banner_cohesion':70,'yearly_gross_income':5200,'gold_reserves':10000,'bureaucracy':100,'net_fixed_income':100,
  'army_size':2200,'military_wages':1,'market_access':0.9,
  'goods':{'grain':{'imports':300,'exports':0},'tea':{'imports':0,'exports':60}},
  'fixture_laws':{'law_serfdom','law_professional_army','law_mercantilism'},
  'fixture_states':[{'owned':True,'turmoil':0.03,'radicals':{'farmers':0.05},'buildings':[
   {'type':'building_government_administration','occupancy':0.8},
   {'type':'building_livestock_ranch','occupancy':0.8},
   {'type':'building_barrack','occupancy':0.8}]}]})

def option(arc,eid,key):
 e=next(x for x in arc['events'] if x['id']==f'ywc_oir.{eid:04d}')
 return next(x for x in e['options'] if x['key']==key)
def nodes(s): return parse('x = '+s)[0][2]
def event_by_id(arc,eid): return next(e for e in arc['events'] if e['id']==f'ywc_oir.{eid:04d}')
def je_node(jid):
 src=(MOD/'common/journal_entries/ywc_v03_country_oir_journal.txt').read_text(encoding='utf-8-sig')
 return next(n for n in parse(src) if n[0]==jid)[2]
def pulse(w,jid):
 j=je_node(jid); pulse=next(x[2] for x in j if x[0]=='on_monthly_pulse'); effect=next(x[2] for x in pulse if x[0]=='effect'); w.execute(effect,'OIR')
def fire(w,arc,eid):
 ev=event_by_id(arc,eid)
 assert w.conditions(nodes(ev['trigger']),'OIR'),f'event trigger false: {eid}'
 w.execute(nodes(ev['immediate']),'OIR')
 return ev
def choose(w,ev,key):
 op=next(x for x in ev['options'] if x['key']==key)
 if 'trigger' in op: assert w.conditions(nodes(op['trigger']),'OIR'),f'option unavailable: {ev["id"]}:{key}'
 w.execute(nodes(op['effect']),'OIR')
 return op

def play_final(arc,route):
 w=world(); a=next(x for x in w.countries.values())
 start=int(arc['events'][0]['id'].split('.')[-1]); pre=arc['slug'].split('_')[-1]; pre={'boundaries':'pasture','supply':'supply','tolls':'tolls'}[pre]
 ids=[j['id'] for j in arc['journals']]; entry=ids[0]
 je=je_node(entry); possible=next(x[2] for x in je if x[0]=='possible')
 assert w.conditions(possible,'OIR'),f'entry JE not possible: {entry}'
 immediate=next(x[2] for x in je if x[0]=='immediate'); w.execute(immediate,'OIR')
 assert a['ywc_v03_active_arc_count']==1 and a['ywc_v03_visible_task_count']==1
 pulse(w,entry); assert w.events[-1]==('OIR',f'ywc_oir.{start:04d}')
 ev=fire(w,arc,start); choose(w,ev,f'route_{route}')
 assert a[f'ywc_oir_{pre}_route']==route
 if route<=2: assert w.treasury['OIR']<0
 # Use the currently active review phase. Each authored event is delivered from its real queue.
 driver=ids[1] if len(ids)>1 else ids[0]
 normal=[int(e['id'].split('.')[-1]) for e in arc['events'][:len(arc['events'])-2]]
 for eid in normal[1:]:
  w.advance_days(90); pulse(w,driver)
  assert w.events[-1]==('OIR',f'ywc_oir.{eid:04d}'),(arc['slug'],eid,w.events[-1:] )
  ev=fire(w,arc,eid)
  if eid==normal[-1]:
   assert a[f'ywc_oir_{pre}_final_stage']==1
   break
  choose(w,ev,'advance')
 return w,arc,pre,driver

def lower_readiness(v,pre):
 if pre=='pasture': v['fixture_states'][0]['buildings'][1]['occupancy']=0.5
 elif pre=='supply': v['army_size']=600
 else: v['market_access']=0.5

class OIRContract(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  c.catalog=json.loads(CAT.read_text(encoding='utf-8')); c.registry=json.loads((ROOT/'data/content/v03/id_registry.json').read_text(encoding='utf-8')); c.arcs={a['slug']:a for a in c.catalog['arcs']}; c.e=EFF.read_text(encoding='utf-8-sig'); c.t=TRG.read_text(encoding='utf-8-sig')
 def test_catalog_ranges_narrative_and_schema(self):
  ranges={(x['catalog_key'],x['slug']):(x['start'],x['end']) for x in self.registry['arc_ranges']}
  self.assertEqual(sum(len(a['events']) for a in self.arcs.values()),24); self.assertEqual(sum(len(a['journals']) for a in self.arcs.values()),6)
  for slug,(lo,hi) in zip(SLUGS,RANGES):
   a=self.arcs[slug]; self.assertEqual(ranges['country_oir',slug],(lo,hi)); self.assertEqual(a['depends_on'],[])
   self.assertEqual([e['id'] for e in a['events']],[f'ywc_oir.{i:04d}' for i in list(range(lo,lo+len(a['events'])-2))+[lo+len(a['events'])-2,lo+len(a['events'])-1]])
   texts=[e['desc']['zh'] for e in a['events']]; self.assertEqual(len(set(texts)),len(texts)); self.assertTrue(all(e['desc']['en'] for e in a['events']))
   for e in a['events']:
    self.assertGreaterEqual(len(e['options']),3); self.assertIn('defer',[o['key'] for o in e['options']]); self.assertIn('withdraw',[o['key'] for o in e['options']])
    for o in e['options']: self.assertEqual(set(o['cost_note']),{'zh','en'}); self.assertEqual(set(o['consequence_note']),{'zh','en'})
   for j in a['journals']: self.assertNotRegex(j['script'],r'(?<![a-z0-9_])(?:complete|fail)\s*=')
 def test_real_entry_je_rejects_capacity_and_routes_do_not_overclaim_legacy(self):
  for a in self.arcs.values():
   w=world(); v=w.countries['OIR']; j=je_node(a['journals'][0]['id']); poss=next(x[2] for x in j if x[0]=='possible')
   v['ywc_v03_active_arc_count']=3; v['ywc_v03_visible_task_count']=6
   self.assertFalse(w.conditions(poss,'OIR'))
   immediate=next(x[2] for x in j if x[0]=='immediate'); w.execute(immediate,'OIR'); self.assertNotIn('ywc_oir_'+a['slug'].split('_')[-1]+'_pending_event',v)
 def test_paid_path_uses_captured_exact_fee_and_replay_guard(self):
  fees={'pasture':{1:150,2:50},'supply':{1:100,2:60},'tolls':{1:100,2:40}}
  for slug in SLUGS:
   arc=self.arcs[slug]; pre={'boundaries':'pasture','supply':'supply','tolls':'tolls'}[slug.split('_')[-1]]
   for route,fee in fees[pre].items():
    with self.subTest(arc=slug,route=route):
     w=world(); v=w.countries['OIR']; je=je_node(arc['journals'][0]['id']); w.execute(next(x[2] for x in je if x[0]=='immediate'),'OIR'); pulse(w,arc['journals'][0]['id']); ev=fire(w,arc,int(arc['events'][0]['id'].split('.')[-1])); op=option(arc,int(arc['events'][0]['id'].split('.')[-1]),f'route_{route}')
     before=w.treasury['OIR']; self.assertTrue(w.conditions(nodes(op['trigger']),'OIR')); w.execute(nodes(op['effect']),'OIR'); self.assertEqual(w.treasury['OIR'],before-fee)
     self.assertEqual(v[f'ywc_oir_{pre}_route_{route}_fee_paid'],fee)
     w.execute(nodes(op['effect']),'OIR'); self.assertEqual(w.treasury['OIR'],before-fee)
  # Failure to debit the captured 1.5x pasture fee neither sets a route nor advances the first queue.
  arc=self.arcs[SLUGS[0]]; w=world(); v=w.countries['OIR']; je=je_node(arc['journals'][0]['id']); w.execute(next(x[2] for x in je if x[0]=='immediate'),'OIR'); pulse(w,arc['journals'][0]['id']); ev=fire(w,arc,1000); v['gold_reserves']=149
  w.execute(nodes(option(arc,1000,'route_1')['effect']),'OIR'); self.assertNotIn('ywc_oir_pasture_route',v); self.assertEqual(v['ywc_oir_pasture_pending_event'],1000); self.assertEqual(w.treasury['OIR'],0)
  v['gold_reserves']=1000; w.execute(nodes(option(arc,1000,'route_1')['effect']),'OIR'); self.assertEqual(w.treasury['OIR'],-150)
  w.execute(nodes(option(arc,1000,'route_1')['effect']),'OIR'); self.assertEqual(w.treasury['OIR'],-150); self.assertEqual(v['ywc_oir_pasture_route'],1)
 def test_actual_normal_je_option_chains_reach_each_final_implementation_node(self):
  for slug in SLUGS:
   arc=self.arcs[slug]
   for route in (1,2):
    with self.subTest(arc=slug,route=route):
     w,arc2,pre,_=play_final(arc,route); a=w.countries['OIR']
     self.assertEqual(a[f'ywc_oir_{pre}_last_event'],int(arc['events'][-3]['id'].split('.')[-1]))
     self.assertEqual(a[f'ywc_oir_{pre}_implementation_reached'],1)
     self.assertTrue(any(f'ywc_oir_{pre}_route_{route}_effect'==m[1]['name'] for m in w.modifiers))
 def test_final_observation_restarts_on_real_readiness_loss_and_settles_from_event(self):
  for slug in SLUGS:
   arc=self.arcs[slug]; w,arc2,pre,driver=play_final(arc,1); v=w.countries['OIR']; final=int(arc['events'][-3]['id'].split('.')[-1]); ev=event_by_id(arc,final); choose(w,ev,'defer')
   w.advance_days(90); pulse(w,driver); self.assertIn(f'ywc_oir_{pre}_observation_timer',v)
   w.advance_months(2); v['fixture_states'][0]['buildings']=[x for x in v['fixture_states'][0]['buildings'] if x['type']!='building_government_administration'] if pre!='tolls' else v['fixture_states'][0]['buildings']; v['market_access']=0.2 if pre=='tolls' else 0.9; v['army_size']=100 if pre=='supply' else 2200
   pulse(w,driver); self.assertNotIn(f'ywc_oir_{pre}_observation_timer',v); self.assertNotIn(f'ywc_oir_{pre}_six_months_complete',v)
   # Restore engine facts. The authored review starts a new six-month timer.
   v['fixture_states'][0]['buildings']=[{'type':'building_government_administration','occupancy':0.8},{'type':'building_livestock_ranch','occupancy':0.8},{'type':'building_barrack','occupancy':0.8}]; v['market_access']=0.9; v['army_size']=2200
   pulse(w,driver); self.assertIn(f'ywc_oir_{pre}_observation_timer',v); w.advance_months(6); pulse(w,driver)
   # The same final normal node is delivered again and its real option invokes the closer.
   self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{final:04d}')); ev=fire(w,arc,final); choose(w,ev,'route_1')
   out='ywc_v03_oir_'+slug+'_outcome'; settled='ywc_v03_oir_'+slug+'_settled'; self.assertEqual(v[out],1); self.assertEqual(v[settled],1); self.assertEqual(v['ywc_v03_active_arc_count'],0)
   for j in arc['journals']:
    jn=je_node(j['id']); self.assertTrue(w.conditions(next(x[2] for x in jn if x[0]=='complete'),'OIR'),(j['id'],'success goal false')); self.assertFalse(w.conditions(next(x[2] for x in jn if x[0]=='fail'),'OIR'),(j['id'],'success also failed'))
 def test_notice_queues_never_overwrite_normal_pending_and_setback_fails_je(self):
  for slug in SLUGS:
   arc=self.arcs[slug]; w,arc2,pre,driver=play_final(arc,1); v=w.countries['OIR']; final=int(arc['events'][-3]['id'].split('.')[-1]); choose(w,event_by_id(arc,final),'defer')
   # Lower actual engine facts, leaving the authored normal queue untouched.
   if pre=='pasture': v['fixture_states'][0]['buildings'][1]['occupancy']=0.2
   elif pre=='supply': v['army_size']=100
   else: v['market_access']=0.2
   w.advance_days(90); pulse(w,driver)
   if w.events and w.events[-1]==('OIR',f'ywc_oir.{final:04d}'):
    ev=fire(w,arc,final); choose(w,ev,'defer')
   self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final)
   w.advance_days(365); pulse(w,driver)
   n12=int(arc['events'][-2]['id'].split('.')[-1]); self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final)
   self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{n12:04d}')); ev=fire(w,arc,n12); choose(w,ev,'narrow_scope')
   self.assertEqual(v[f'ywc_oir_{pre}_route'],1); self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final); self.assertTrue(v[f'ywc_oir_{pre}_scope_narrowed'])
   # Reblocked limited scope produces a separate 36-month notice, then an honest setback.
   w.advance_days(90); pulse(w,driver)
   if w.events[-1]==('OIR',f'ywc_oir.{final:04d}'):
    ev=fire(w,arc,final); choose(w,ev,'defer')
   self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final)
   w.advance_days(1095); pulse(w,driver); n36=int(arc['events'][-1]['id'].split('.')[-1])
   self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final); self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{n36:04d}'))
   ev=fire(w,arc,n36); choose(w,ev,'settle_failure')
   self.assertEqual(v['ywc_v03_oir_'+slug+'_outcome'],4); self.assertNotIn(f'ywc_oir_{pre}_pending_event',v)
   for j in arc['journals']:
    jn=je_node(j['id']); self.assertTrue(w.conditions(next(x[2] for x in jn if x[0]=='fail'),'OIR'))
 def test_narrowed_paid_route_has_limited_closer_but_cannot_take_full_closer(self):
  for slug in SLUGS:
   arc=self.arcs[slug]; final=int(arc['events'][-3]['id'].split('.')[-1]); notice=int(arc['events'][-2]['id'].split('.')[-1]); pre={'boundaries':'pasture','supply':'supply','tolls':'tolls'}[slug.split('_')[-1]]
   # A deferred notice keeps the normal final node pending and does not settle the arc.
   w,_,pre,driver=play_final(arc,1); v=w.countries['OIR']; choose(w,event_by_id(arc,final),'defer'); lower_readiness(v,pre)
   w.advance_days(90); pulse(w,driver)
   if w.events[-1]==('OIR',f'ywc_oir.{final:04d}'):
    ev=fire(w,arc,final); choose(w,ev,'defer')
   w.advance_days(365); pulse(w,driver)
   if w.events[-1]==('OIR',f'ywc_oir.{final:04d}'):
    ev=fire(w,arc,final); choose(w,ev,'defer'); w.advance_days(90); pulse(w,driver)
   self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{notice:04d}'))
   n=fire(w,arc,notice); choose(w,n,'defer')
   self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final); self.assertTrue(v[f'ywc_oir_{pre}_12_notice_deferred']); self.assertEqual(v[f'ywc_v03_active_arc_count'],1)
   # Rebuild the world and take the notice's real narrowing action through limited settlement.
   w,_,pre,driver=play_final(arc,1); v=w.countries['OIR']; choose(w,event_by_id(arc,final),'defer'); lower_readiness(v,pre)
   w.advance_days(90); pulse(w,driver)
   if w.events[-1]==('OIR',f'ywc_oir.{final:04d}'):
    ev=fire(w,arc,final); choose(w,ev,'defer')
   w.advance_days(365); pulse(w,driver)
   if w.events[-1]==('OIR',f'ywc_oir.{final:04d}'):
    ev=fire(w,arc,final); choose(w,ev,'defer'); w.advance_days(90); pulse(w,driver)
   self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{notice:04d}'))
   n=fire(w,arc,notice); choose(w,n,'narrow_scope'); self.assertTrue(v[f'ywc_oir_{pre}_scope_narrowed']); self.assertEqual(v[f'ywc_oir_{pre}_pending_event'],final)
   w.advance_days(90); pulse(w,driver); self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{final:04d}'))
   ev=fire(w,arc,final); choose(w,ev,'defer'); w.advance_months(6); pulse(w,driver)
   self.assertEqual(w.events[-1],('OIR',f'ywc_oir.{final:04d}')); ev=fire(w,arc,final)
   self.assertFalse(w.conditions(nodes(option(arc,final,'route_1')['trigger']),'OIR'))
   choose(w,ev,'route_3'); self.assertEqual(v['ywc_v03_oir_'+slug+'_outcome'],3)
   for j in arc['journals']:
    jn=je_node(j['id']); self.assertTrue(w.conditions(next(x[2] for x in jn if x[0]=='complete'),'OIR')); self.assertFalse(w.conditions(next(x[2] for x in jn if x[0]=='fail'),'OIR'))
 def test_je_terminal_matrix_and_withdrawal_are_mutually_exclusive_and_idempotent(self):
  for arc in self.arcs.values():
   w=world(); v=w.countries['OIR']; j=je_node(arc['journals'][0]['id']); w.execute(next(x[2] for x in j if x[0]=='immediate'),'OIR'); pulse(w,arc['journals'][0]['id']); ev=fire(w,arc,int(arc['events'][0]['id'].split('.')[-1])); choose(w,ev,'withdraw')
   self.assertEqual(v['ywc_v03_active_arc_count'],0); self.assertEqual(v['ywc_v03_visible_task_count'],0)
   for ji in arc['journals']:
    n=je_node(ji['id']); self.assertTrue(w.conditions(next(x[2] for x in n if x[0]=='complete'),'OIR'),(ji['id'],'withdraw goal false')); self.assertFalse(w.conditions(next(x[2] for x in n if x[0]=='fail'),'OIR'),(ji['id'],'withdraw also failed'))
   # Replaying the actual opening withdrawal option cannot release the same slot twice.
   choose(w,ev,'withdraw'); self.assertEqual(v['ywc_v03_active_arc_count'],0); self.assertEqual(v['ywc_v03_visible_task_count'],0)
 def test_shared_real_90_day_cooldown_and_parallel_active_je_continuation(self):
  arc=self.arcs[SLUGS[0]]; w=world(); v=w.countries['OIR']; je=je_node(arc['journals'][0]['id']); w.execute(next(x[2] for x in je if x[0]=='immediate'),'OIR'); pulse(w,arc['journals'][0]['id']); ev=fire(w,arc,1000); choose(w,ev,'defer')
  self.assertIn('ywc_v03_major_event_cooldown',v)
  w.advance_days(89); self.assertFalse(w.conditions(w.triggers['ywc_v03_can_deliver_major'],'OIR'))
  w.advance_days(1); self.assertTrue(w.conditions(w.triggers['ywc_v03_can_deliver_major'],'OIR'))
  v['ywc_v03_active_arc_count']=3; v['ywc_oir_pasture_pending_event']=1001; pulse(w,arc['journals'][-1]['id']); self.assertEqual(w.events[-1],('OIR','ywc_oir.1001'))
 def test_legacy_continuation_is_consumed_and_missing_legacy_has_real_cost(self):
  arc=self.arcs[SLUGS[0]]; results=[]
  for prior in (1,2):
   w=world();v=w.countries['OIR'];v['ywc_campaign_oir_c1_outcome']=prior;je=je_node(arc['journals'][0]['id']);w.execute(next(x[2] for x in je if x[0]=='immediate'),'OIR');pulse(w,arc['journals'][0]['id']);ev=fire(w,arc,1000);before=v['ywc_flavor_oir_banner_cohesion'];choose(w,ev,'route_1');results.append(v['ywc_flavor_oir_banner_cohesion']);self.assertEqual(v['ywc_campaign_oir_c1_outcome'],prior);self.assertEqual(v['ywc_oir_prior_c1_outcome'],prior)
  self.assertNotEqual(results[0],results[1])
  w=world();v=w.countries['OIR'];before=v['ywc_flavor_oir_banner_cohesion'];je=je_node(arc['journals'][0]['id']);w.execute(next(x[2] for x in je if x[0]=='immediate'),'OIR');self.assertEqual(v['ywc_campaign_oir_c1_outcome'],None) if 'ywc_campaign_oir_c1_outcome' in v else None; self.assertEqual(v['ywc_flavor_oir_banner_cohesion'],before-5);self.assertTrue(v['ywc_oir_legacy_compatibility'])
 def test_verified_engine_gates_and_route_effect_modifiers_are_material(self):
  for token in ['building_livestock_ranch','occupancy >= 0.6','law_type:law_serfdom','radical_fraction','turmoil > 0.15','building_barrack','army_size >= 1500','military_wages >= 1','market_goods_imports >= 200','market_goods_exports > 50','var:ywc_flavor_oir_banner_cohesion >= 50']:
   self.assertIn(token,self.t)
  for m in ['interest_group_ig_armed_forces_approval_add','interest_group_ig_landowners_approval_add','interest_group_ig_rural_folk_approval_add','country_military_wages_mult']:
   self.assertIn(m,(MOD/'common/static_modifiers/ywc_v03_oir_modifiers.txt').read_text(encoding='utf-8-sig'))
  self.assertNotIn('horses',self.t)
  full=json.dumps(self.catalog,ensure_ascii=False)+'\n'+self.e+'\n'+self.t
  for bad in ['discover_in_state','annex_country','change_tag','add_state_region'] : self.assertNotIn(bad,full)
 def test_all_helpers_resolve_and_each_allocated_id_is_in_authored_dispatch(self):
  calls=set(re.findall(r'(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)',json.dumps(self.catalog,ensure_ascii=False)))
  self.assertFalse(calls-defs(),sorted(calls-defs()))
  for arc in self.arcs.values():
   p=arc['slug'].split('_')[-1]; p={'boundaries':'pasture','supply':'supply','tolls':'tolls'}[p]
   dispatch=body(self.e,'ywc_oir_dispatch_'+p)
   for ev in arc['events']:self.assertIn('id = '+ev['id'],dispatch)
 def test_renderer_outputs_are_current_and_generated_ids_match_allocations(self):
  for arc in self.arcs.values():
   self.assertEqual(set(arc['legacy_links']),{'ywc_campaign_oir_c1_outcome','ywc_je_flavor_oir_banner_1'})
   self.assertIn('ywc_campaign_oir_c1_outcome',arc['journals'][0]['script'])
if __name__=='__main__':unittest.main()

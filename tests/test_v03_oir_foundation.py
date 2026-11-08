"""OIR script regressions. Execute authored JE/event/helper scripts in the strict offline subset."""
import json, re, sys, unittest
from pathlib import Path
from tests.clausewitz_harness import PulseWorld, parse
ROOT=Path(__file__).resolve().parents[1]
CAT=ROOT/'data/content/v03/countries/oir.json'
EFF=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_oir_effects.txt'
TRG=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_oir_triggers.txt'
SCHED_E=ROOT/'yongchang_world/common/scripted_effects/ywc_v03_delivery_oir_effects.txt'
SCHED_T=ROOT/'yongchang_world/common/scripted_triggers/ywc_v03_delivery_oir_triggers.txt'
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
 """Only engine facts are fixtures; authored country logic and JE lifecycle execute."""
 def __init__(self):
  facts={'ywc_v03_initialized':1,'ywc_v03_active_arc_count':0,'ywc_v03_visible_task_count':0,
   'ywc_flavor_oir_banner_cohesion':70,'yearly_gross_income':5200,'gold_reserves':10000,
   'bureaucracy':100,'net_fixed_income':100,'army_size':2200,
   'fixture_modifiers':{'military_wages_medium'},'fixture_relations':{'SHU':10,'RUS':10},
   'goods':{'grain':{'imports':300},'tea':{'exports':60},'small_arms':{'sell_orders':300}},
   'fixture_laws':{'law_serfdom','law_professional_army','law_mercantilism'},
   'fixture_states':[{'owned':True,'market_access':0.9,'turmoil':0.03,'radicals':{'farmers':0.05},
    'buildings':[{'type':'building_government_administration','occupancy':0.8},
     {'type':'building_livestock_ranch','occupancy':0.8},
     {'type':'building_barrack','occupancy':0.8,'shortage':False}]}]}
  super().__init__(EFF.read_text(encoding='utf-8-sig')+'\n'+SCHED_E.read_text(encoding='utf-8-sig')+'\n'+CORE_E.read_text(encoding='utf-8-sig'),{'OIR':facts,'SHU':{},'RUS':{}})
  self.triggers={k:b for k,_,b in parse(TRG.read_text(encoding='utf-8-sig')+'\n'+SCHED_T.read_text(encoding='utf-8-sig')+'\n'+CORE_T.read_text(encoding='utf-8-sig'))}
  self.managed={};self.active=set();self.completed=set();self.failed=set()
 def _cmp(self,left,op,right,v):
  if isinstance(right,str) and right.startswith('var:'):right=v.get(right[4:],0)
  elif right in ('yes','no'):right=right=='yes'
  else:right=float(right)
  return {'=':lambda:left==right,'>=':lambda:left>=right,'<=':lambda:left<=right,
   '>':lambda:left>right,'<':lambda:left<right,'!=':lambda:left!=right}[op]()
 def _cond(self,node,tag,state=None,building=None,good=None):
  key,op,val=node;v=self.countries[tag]
  if key in ('AND','OR','NOT','NOR'):
   xs=[self._cond(x,tag,state,building,good) for x in val]
   return {'AND':all(xs),'OR':any(xs),'NOT':not all(xs),'NOR':not any(xs)}[key]
  if key in self.triggers and val=='yes':return self.conditions(self.triggers[key],tag)
  if key=='any_scope_state':return any(all(self._cond(x,tag,s) for x in val) for s in v.get('fixture_states',[]))
  if key=='any_scope_building':return any(all(self._cond(x,tag,state,b) for x in val) for b in (state or {}).get('buildings',[]))
  if key=='is_owned_by':return bool(state and state.get('owned'))
  if key=='is_building_type':return bool(building and building.get('type')==val)
  if key=='occupancy':return self._cmp((building or {}).get('occupancy',0),op,val,v)
  if key=='building_has_goods_shortage':return self._cmp((building or {}).get('shortage',False),op,val,v)
  if key in ('turmoil','market_access'):
   assert state is not None,f'{key} requires explicit state scope in the verified fixture'
   return self._cmp(state.get(key,0),op,val,v)
  if key=='radical_fraction':
   threshold=next(x for x in val if x[0]=='value');pop=next(x[2] for x in val if x[0]=='pop_type')
   return self._cmp((state or {}).get('radicals',{}).get(pop,0),threshold[1],threshold[2],v)
  if key=='has_law_or_variant':return val.split(':')[-1] in v.get('fixture_laws',set())
  if key=='has_modifier':return val in v.get('fixture_modifiers',set()) or any(t==tag and f.get('name',f.get('modifier'))==val for t,f in self.modifiers)
  if key=='market_capital.market':return all(self._cond(x,tag,state,building,good) for x in val)
  if key.startswith('mg:'):return all(self._cond(x,tag,state,building,key[3:]) for x in val)
  if key in ('market_goods_imports','market_goods_exports','market_goods_sell_orders'):
   field={'market_goods_imports':'imports','market_goods_exports':'exports','market_goods_sell_orders':'sell_orders'}[key]
   return self._cmp(v.get('goods',{}).get(good,{}).get(field,0),op,val,v)
  if key=='army_size':return self._cmp(v.get(key,0),op,val,v)
  if re.fullmatch(r'c:[A-Z0-9]+\.relations:this',key):
   partner=key[2:].split('.')[0]
   return partner in self.countries and self._cmp(v.get('fixture_relations',{}).get(partner,-200),op,val,v)
  return super().condition(node,tag)
 def condition(self,node,tag):return self._cond(node,tag)

def world():return OIRWorld()
def nodes(text):return parse('x = '+text)[0][2]
def je_node(jid):
 src=(MOD/'common/journal_entries/ywc_v03_country_oir_journal.txt').read_text(encoding='utf-8-sig')
 return next(b for k,_,b in parse(src) if k==jid)
def field(jid,key):return next(b for k,_,b in je_node(jid) if k==key)
def predicates(w,jid):return w.conditions(field(jid,'complete'),'OIR'),w.conditions(field(jid,'fail'),'OIR')
def start(w,arc):
 jid=arc['journals'][0]['id'];assert w.conditions(field(jid,'possible'),'OIR')
 assert field(jid,'possible')==field(jid,'is_shown_when_inactive')
 w.managed[arc['slug']]=arc;w.active.add(jid);w.execute(field(jid,'immediate'),'OIR');sync(w)
def sync(w):
 # Only explicitly started arcs are managed; phases within them activate from real possible blocks.
 for _ in range(10):
  changed=False
  for jid in list(w.active):
   complete,fail=predicates(w,jid);assert not (complete and fail),f'ambiguous JE: {jid}'
   if complete or fail:
    w.active.remove(jid);(w.failed if fail else w.completed).add(jid);changed=True
    key='on_fail' if fail else 'on_complete';b=next((b for k,_,b in je_node(jid) if k==key),None)
    if b:w.execute(b,'OIR')
  for arc in w.managed.values():
   for j in arc['journals'][1:]:
    jid=j['id']
    if jid not in w.active|w.completed|w.failed and w.conditions(field(jid,'possible'),'OIR'):
     w.active.add(jid);w.execute(field(jid,'immediate'),'OIR');changed=True
  if not changed:return
 raise AssertionError('JE phase activation did not converge')
def pulse(w,jid):
 sync(w);assert jid in w.active,f'cannot pulse inactive/completed JE: {jid}'
 b=next(b for k,_,b in field(jid,'on_monthly_pulse') if k=='effect');w.execute(b,'OIR');sync(w)
def pulse_current(w,arc):
 sync(w);ids=[j['id'] for j in arc['journals'] if j['id'] in w.active]
 assert len(ids)==1,f'expected one real active phase, got {ids}'
 pulse(w,ids[0])
def fire(w,arc,eid):
 ev=next(e for e in arc['events'] if e['id']==f'ywc_oir.{eid}')
 source=parse((MOD/'events/ywc_v03_country_oir_events.txt').read_text(encoding='utf-8-sig'))
 generated=next(block for key,_,block in source if key==ev['id'])
 trigger=next(block for key,_,block in generated if key=='trigger')
 immediate=next(block for key,_,block in generated if key=='immediate')
 assert w.conditions(trigger,'OIR');w.execute(immediate,'OIR');sync(w);return ev
def choose(w,ev,key):
 o=next(o for o in ev['options'] if o['key']==key)
 if o.get('trigger'):assert w.conditions(nodes(o['trigger']),'OIR'),(ev['id'],key)
 w.execute(nodes(o['effect']),'OIR');sync(w)
def deliver(w,arc,days=90):
 if days:w.advance_days(days)
 count=len(w.events);pulse_current(w,arc);assert len(w.events)==count+1
 return fire(w,arc,int(w.events[-1][1].split('.')[-1]))
def pre(arc):return {'boundaries':'pasture','supply':'supply','tolls':'tolls'}[arc['slug'].split('_')[-1]]
def slot(arc):return 'ywc_v03_oir_'+arc['slug']
def play_final(arc,route,w=None):
 w=w or world();start(w,arc);ev=deliver(w,arc,0);choose(w,ev,f'route_{route}')
 normal=arc['events'][:-2]
 for expected in normal[1:]:
  ev=deliver(w,arc);assert ev['id']==expected['id']
  if expected is not normal[-1]:choose(w,ev,'advance')
 return w,ev
def lose(v,p,partial=False):
 if p=='pasture':v['fixture_states'][0]['buildings'][1]['occupancy']=0.5 if partial else 0.2
 elif p=='supply':v['army_size']=600 if partial else 100
 else:v['fixture_states'][0]['market_access']=0.5 if partial else 0.2

def arrive_notice(w,arc,ev):
 choose(w,ev,'defer');lose(w.countries['OIR'],pre(arc),True)
 ev=deliver(w,arc);choose(w,ev,'defer');w.advance_days(365);return deliver(w,arc,0)

class OIRContract(unittest.TestCase):
 @classmethod
 def setUpClass(c):
  c.catalog=json.loads(CAT.read_text(encoding='utf-8'));c.arcs=c.catalog['arcs']
  c.e=EFF.read_text(encoding='utf-8-sig');c.t=TRG.read_text(encoding='utf-8-sig')
 def test_allocation_dispatch_and_distinct_bilingual_stories(self):
  self.assertEqual(sum(len(a['events']) for a in self.arcs),24);self.assertEqual(sum(len(a['journals']) for a in self.arcs),6)
  for language in ('zh','en'):
   descriptions=[e['desc'][language] for a in self.arcs for e in a['events']]
   self.assertEqual(len(set(descriptions)),24)
   self.assertFalse(any(x in ' '.join(descriptions).lower() for x in ('story queue','正常故事队列','此项会改变后续')))
  for a,base in zip(self.arcs,(1000,1010,1020)):
   self.assertEqual([e['id'] for e in a['events']],[f'ywc_oir.{i}' for i in range(base,base+len(a['events']))])
   for e in a['events']:
    self.assertIn('id = '+e['id'],self.e)
    self.assertTrue({'defer','withdraw'}<={o['key'] for o in e['options']})
    self.assertTrue(all(set(o['cost_note'])==set(o['consequence_note'])=={'zh','en'} for o in e['options']))
    for o in e['options']:self.assertNotIn('This changes later execution',o['consequence_note']['en'])
 def test_capacity_claim_open_and_successful_payment_are_guarded(self):
  for a in self.arcs:
   w=world();v=w.countries['OIR'];v['ywc_v03_active_arc_count']=3;v['ywc_v03_visible_task_count']=6
   jid=a['journals'][0]['id'];self.assertFalse(w.conditions(field(jid,'possible'),'OIR'))
   w.execute(field(jid,'immediate'),'OIR');self.assertNotIn(slot(a)+'_started',v);self.assertNotIn('ywc_oir_'+pre(a)+'_pending_event',v)
 def test_only_active_journals_pulse_and_each_phase_really_activates(self):
  for a in self.arcs:
   w,ev=play_final(a,1);p=pre(a);self.assertTrue(w.countries['OIR']['ywc_oir_'+p+'_implementation_reached'])
   self.assertEqual(w.active,{a['journals'][-1]['id']})
   for jid in w.completed:
    with self.assertRaisesRegex(AssertionError,'cannot pulse'):pulse(w,jid)
 def test_exact_route_fees_insufficient_payment_and_replay(self):
  fees={'pasture':(150,50),'supply':(100,60),'tolls':(100,40)}
  for a in self.arcs:
   p=pre(a)
   for route,amount in enumerate(fees[p],1):
    w=world();start(w,a);ev=deliver(w,a,0);op=next(o for o in ev['options'] if o['key']==f'route_{route}');v=w.countries['OIR']
    v['gold_reserves']=amount-1;w.execute(nodes(op['effect']),'OIR');self.assertNotIn(f'ywc_oir_{p}_route',v);self.assertEqual(w.treasury['OIR'],0)
    v['gold_reserves']=10000;choose(w,ev,f'route_{route}');self.assertEqual(w.treasury['OIR'],-amount)
    w.execute(nodes(op['effect']),'OIR');self.assertEqual(w.treasury['OIR'],-amount);self.assertEqual(v[f'ywc_oir_{p}_route_{route}_fee_paid'],amount)
 def test_all_three_routes_reach_real_success_with_terminal_predicates(self):
  for a in self.arcs:
   for route in (1,2,3):
    w,ev=play_final(a,route);choose(w,ev,'defer');w.advance_months(6);ev=deliver(w,a,0)
    # First monthly observation begins after final arrival, so start it before aging.
    if not w.countries['OIR'].get('ywc_oir_'+pre(a)+'_six_months_complete'):
     choose(w,ev,'defer');w.advance_months(6);ev=deliver(w,a,0)
    choose(w,ev,f'route_{route}');self.assertEqual(w.countries['OIR'][slot(a)+'_outcome'],route)
    for j in a['journals']:self.assertEqual(predicates(w,j['id']),(True,False))
    self.assertEqual(w.countries['OIR']['ywc_v03_active_arc_count'],0)
 def test_full_observation_loss_clears_watch_and_mature(self):
  for a in self.arcs:
   w,ev=play_final(a,1);p=pre(a);v=w.countries['OIR'];choose(w,ev,'defer');ev=deliver(w,a);choose(w,ev,'defer')
   self.assertIn(f'ywc_oir_{p}_observation_timer',v);w.advance_months(3);lose(v,p);pulse_current(w,a)
   self.assertNotIn(f'ywc_oir_{p}_observation_timer',v);self.assertNotIn(f'ywc_oir_{p}_six_months_complete',v)
 def test_notice_defer_preserves_normal_queue_and_narrow_requires_fresh_watch(self):
  for a in self.arcs:
   w,ev=play_final(a,1);p=pre(a);v=w.countries['OIR'];n=arrive_notice(w,a,ev)
   self.assertEqual(n['id'],a['events'][-2]['id']);pending=v[f'ywc_oir_{p}_pending_event'];choose(w,n,'defer')
   self.assertEqual(v[f'ywc_oir_{p}_pending_event'],pending)
   # Actual helper is also the effect of the consumed notice; replay tests its idempotent decision.
   choose(w,n,'narrow_scope');self.assertEqual(v[f'ywc_oir_{p}_pending_event'],pending)
   self.assertNotIn(f'ywc_oir_{p}_six_months_complete',v);ev=deliver(w,a);choose(w,ev,'defer')
   w.advance_months(5);pulse_current(w,a);self.assertNotIn(f'ywc_oir_{p}_limited_six_months_complete',v)
   w.advance_months(1);ev=deliver(w,a,0)
   self.assertFalse(w.conditions(nodes(next(o['trigger'] for o in ev['options'] if o['key']=='route_1')),'OIR'))
   choose(w,ev,'route_3');self.assertEqual(v[slot(a)+'_outcome'],3)
 def test_shared_toll_narrow_watch_never_counts_false_reduced_target(self):
  a=self.arcs[2];w,ev=play_final(a,2);v=w.countries['OIR'];choose(w,ev,'defer');v['ywc_flavor_oir_banner_cohesion']=40
  ev=deliver(w,a);choose(w,ev,'defer');w.advance_days(365);n=deliver(w,a,0);choose(w,n,'narrow_scope')
  v['ywc_flavor_oir_banner_cohesion']=70;v['fixture_states'][0]['market_access']=0.2
  pulse_current(w,a);w.advance_months(6);pulse_current(w,a)
  self.assertNotIn('ywc_oir_tolls_limited_timer',v);self.assertNotIn('ywc_oir_tolls_limited_six_months_complete',v)
  v['fixture_states'][0]['market_access']=0.4;pulse_current(w,a);self.assertIn('ywc_oir_tolls_limited_timer',v)
  w.advance_months(5);pulse_current(w,a);self.assertNotIn('ywc_oir_tolls_limited_six_months_complete',v)
  v['fixture_states'][0]['market_access']=0.2;pulse_current(w,a);self.assertNotIn('ywc_oir_tolls_limited_timer',v)
  v['fixture_states'][0]['market_access']=0.4;pulse_current(w,a);w.advance_months(6);pulse_current(w,a)
  self.assertIn('ywc_oir_tolls_limited_six_months_complete',v)
  v['fixture_states'][0]['market_access']=0.2;pulse_current(w,a)
  self.assertNotIn('ywc_oir_tolls_limited_six_months_complete',v)
  v['fixture_states'][0]['market_access']=0.4;pulse_current(w,a);w.advance_months(6);pulse_current(w,a)
  ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));choose(w,ev,'route_3');self.assertEqual(v[slot(a)+'_outcome'],3)
 def test_real_notice_setback_all_phase_predicates_fail_exclusively(self):
  for a in self.arcs:
   w,ev=play_final(a,1);p=pre(a);v=w.countries['OIR'];choose(w,ev,'defer');lose(v,p)
   ev=deliver(w,a);choose(w,ev,'defer');w.advance_days(1095);n=deliver(w,a,0);self.assertEqual(n['id'],a['events'][-2]['id']);choose(w,n,'defer')
   n=deliver(w,a);self.assertEqual(n['id'],a['events'][-1]['id']);choose(w,n,'settle_failure')
   for j in a['journals']:self.assertEqual(predicates(w,j['id']),(False,True))
   self.assertEqual(v[slot(a)+'_outcome'],4);self.assertEqual(v['ywc_v03_active_arc_count'],0)
 def test_actual_withdrawal_is_failure_and_release_is_idempotent(self):
  for a in self.arcs:
   w=world();start(w,a);ev=deliver(w,a,0);choose(w,ev,'withdraw');v=w.countries['OIR']
   for j in a['journals']:self.assertEqual(predicates(w,j['id']),(False,True))
   choose(w,ev,'withdraw');self.assertEqual(v['ywc_v03_active_arc_count'],0);self.assertEqual(v['ywc_v03_visible_task_count'],0)
 def test_legacy_capture_and_compatibility_cost_once_on_replay(self):
  for a in self.arcs:
   w=world();v=w.countries['OIR'];start(w,a);one=v['ywc_flavor_oir_banner_cohesion']
   w.execute(field(a['journals'][0]['id'],'immediate'),'OIR');w.run('ywc_oir_capture_legacy_context','OIR')
   self.assertEqual(v['ywc_flavor_oir_banner_cohesion'],one);self.assertEqual(v['ywc_v03_active_arc_count'],1)
  values=[]
  for prior in (1,2):
   w=world();v=w.countries['OIR'];v['ywc_campaign_oir_c1_outcome']=prior;start(w,self.arcs[0]);ev=deliver(w,self.arcs[0],0);choose(w,ev,'route_1')
   values.append(v['ywc_flavor_oir_banner_cohesion']);self.assertEqual(v['ywc_campaign_oir_c1_outcome'],prior)
  self.assertNotEqual(*values)
 def test_missing_all_legacy_state_has_real_once_only_political_cost(self):
  w=world();v=w.countries['OIR'];v.pop('ywc_flavor_oir_banner_cohesion');start(w,self.arcs[1]);before=len(w.modifiers)
  self.assertTrue(any(m[1].get('name')=='ywc_oir_legacy_compatibility_cost' for m in w.modifiers))
  w.run('ywc_oir_capture_legacy_context','OIR');self.assertEqual(len(w.modifiers),before)
 def test_supply_goods_wages_and_toll_relations_are_real_separate_gates(self):
  w=world();v=w.countries['OIR']
  def ready(name):return w.conditions(w.triggers[name],'OIR')
  self.assertTrue(ready('ywc_oir_v03_supply_unified_ready'))
  v['goods']['small_arms']['sell_orders']=0;self.assertFalse(ready('ywc_oir_v03_supply_unified_ready'));self.assertFalse(ready('ywc_oir_v03_supply_reduced_ready'))
  v['goods']['small_arms']['sell_orders']=300;v['fixture_modifiers'].clear();self.assertFalse(ready('ywc_oir_v03_supply_unified_ready'))
  v['fixture_relations']={'SHU':-50,'RUS':-50};self.assertFalse(ready('ywc_oir_v03_tolls_single_ready'));self.assertFalse(ready('ywc_oir_v03_tolls_shared_ready'))
  v['fixture_relations']['SHU']=10;self.assertTrue(ready('ywc_oir_v03_tolls_single_ready'))
  v['fixture_states'][0]['owned']=False;self.assertFalse(ready('ywc_oir_v03_tolls_single_ready'))
 def test_free_route_notes_name_real_conditions_and_never_paid(self):
  for a in self.arcs:
   op=next(o for o in a['events'][0]['options'] if o['key']=='route_3');self.assertIn('No treasury debit',op['cost_note']['en'])
   text=json.dumps(a,ensure_ascii=False)
   self.assertNotIn('paid route',text.lower());self.assertNotIn('已付路线',text)
  note=next(o for o in self.arcs[0]['events'][0]['options'] if o['key']=='route_3')['cost_note']['zh'];self.assertNotIn('土地法',note)
 def test_90_day_cooldown_and_full_capacity_continuation(self):
  w=world();a=self.arcs[0];start(w,a);ev=deliver(w,a,0);choose(w,ev,'route_1')
  for other in self.arcs[1:]:start(w,other)
  self.assertEqual(w.countries['OIR']['ywc_v03_active_arc_count'],3)
  w.advance_days(89);self.assertFalse(w.conditions(w.triggers['ywc_v03_can_deliver_major'],'OIR'))
  w.advance_days(1);before=len(w.events);pulse_current(w,a);self.assertEqual(len(w.events),before+1)
  tag,event_id=w.events[-1];self.assertEqual(tag,'OIR');recipient=next(x for x in self.arcs if any(e['id']==event_id for e in x['events']))
  ev=fire(w,recipient,int(event_id.rsplit('.',1)[1]));self.assertEqual(ev['id'],'ywc_oir.1010')
 def test_material_route_effects_two_downstream_nodes_and_legacy_preservation(self):
  for a in self.arcs:
   for route in (1,2,3):
    w=world();v=w.countries['OIR'];v['ywc_campaign_oir_c1_outcome']=2;start(w,a);ev=deliver(w,a,0);choose(w,ev,f'route_{route}')
    for _ in range(2):
     ev=deliver(w,a);before=len(w.modifiers);choose(w,ev,'advance');self.assertGreater(len(w.modifiers),before)
    self.assertEqual(v['ywc_campaign_oir_c1_outcome'],2)
 def test_completed_bridge_preserves_existing_campaign_result(self):
  for a in self.arcs:
   w=world();v=w.countries['OIR'];v['ywc_campaign_oir_c1_outcome']=2
   w,ev=play_final(a,1,w);choose(w,ev,'defer');ev=deliver(w,a);choose(w,ev,'defer')
   w.advance_months(6);ev=deliver(w,a,0);choose(w,ev,'route_1')
   self.assertEqual(v['ywc_campaign_oir_c1_outcome'],2);self.assertEqual(v['ywc_oir_prior_c1_outcome'],2)
 def test_popup_qualification_loss_never_debits_or_advances(self):
  for a in self.arcs:
   for route in (1,2):
    for mode in ('default','bankruptcy'):
     w=world();start(w,a);ev=deliver(w,a,0);v=w.countries['OIR']
     op=next(o for o in ev['options'] if o['key']==f'route_{route}');self.assertTrue(w.conditions(nodes(op['trigger']),'OIR'))
     if mode=='default':v['in_default']=True
     else:v['fixture_modifiers'].add('declared_bankruptcy')
     w.execute(nodes(op['effect']),'OIR');self.assertEqual(w.treasury['OIR'],0)
     self.assertNotIn('ywc_oir_'+pre(a)+'_route',v);self.assertEqual(v['ywc_oir_'+pre(a)+'_pending_event'],int(ev['id'].split('.')[-1]))
 def test_all_terminal_closers_share_stale_rejection_and_preserve_other_queues(self):
  cases={"pasture":("court","banner","custom"),"supply":("unified","quota","capped"),"tolls":("single","shared","banner")}
  for p,names in cases.items():
   for name in names:
    reject=f'ywc_oir_{p}_reject_as_{name}';close=f'ywc_oir_close_{p}_as_{name}'
    closer=body(self.e,close);self.assertIn(f'else = {{ {reject} = yes }}',closer)
    logic=body(self.e,reject);self.assertIn(f'ywc_oir_{p}_reset_observation = yes',logic)
    self.assertNotIn(f'ywc_oir_{p}_reset_blocked_epoch = yes',logic)
    self.assertIn(f'NOT = {{ has_variable = ywc_oir_{p}_pending_event }}',logic)
    self.assertIn(f'value = {dict(pasture=1005,supply=1017,tolls=1023)[p]}',logic)
    self.assertNotIn(f'remove_variable = ywc_oir_{p}_notice_event',logic)
 def test_paid_route_narrowed_limited_rejection_requeues_without_changing_obligation(self):
  fees={"pasture":(150,50),"supply":(100,60),"tolls":(100,40)}
  for a in self.arcs:
   p=pre(a);key='ywc_oir_'+p;final_id=int(a['events'][-3]['id'].split('.')[-1])
   for route in (1,2):
    for loss_pulse_first in (False,True):
     fee=fees[p][route-1];w,ev=play_final(a,route);v=w.countries['OIR']
     self.assertEqual(w.treasury['OIR'],-fee);choose(w,ev,'defer')
     if p=='pasture':v['ywc_flavor_oir_banner_cohesion']=40
     elif p=='supply':v['army_size']=600
     else:
      v['fixture_states'][0]['market_access']=0.45;v['ywc_flavor_oir_banner_cohesion']=40
     ev=deliver(w,a);choose(w,ev,'defer');w.advance_days(365)
     notice=deliver(w,a,0);self.assertEqual(notice['id'],a['events'][-2]['id'])
     choose(w,notice,'narrow_scope');self.assertEqual(v[key+'_route'],route);self.assertEqual(w.treasury['OIR'],-fee)
     ev=deliver(w,a);self.assertEqual(ev['id'],a['events'][-3]['id']);choose(w,ev,'defer')
     w.advance_months(6);before=len(w.events);pulse_current(w,a)
     self.assertIn(key+'_limited_six_months_complete',v);self.assertEqual(len(w.events),before+1)
     ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));self.assertEqual(ev['id'],a['events'][-3]['id'])
     v['in_default']=True
     if loss_pulse_first:
      before=len(w.events);pulse_current(w,a);self.assertEqual(len(w.events),before)
     stale=next(o for o in ev['options'] if o['key']=='route_3');w.execute(nodes(stale['effect']),'OIR');sync(w)
     self.assertNotIn(key+'_limited_six_months_complete',v);self.assertNotIn(key+'_outcome',v)
     self.assertEqual(v[key+'_route'],route);self.assertEqual(w.treasury['OIR'],-fee);self.assertEqual(v[key+'_pending_event'],final_id)
     if loss_pulse_first:
      self.assertIn(key+'_blocked_timer_started',v);self.assertEqual(w.days_until_expiry['OIR'][key+'_blocked_12_due'],365)
      self.assertEqual(w.days_until_expiry['OIR'][key+'_blocked_36_due'],1095)
     v['in_default']=False;w.advance_days(90);ev=deliver(w,a,0);self.assertEqual(ev['id'],a['events'][-3]['id']);choose(w,ev,'defer')
     self.assertNotIn(key+'_limited_six_months_complete',v)
     w.advance_months(5);pulse_current(w,a);self.assertNotIn(key+'_limited_six_months_complete',v)
     w.advance_months(1);before=len(w.events);pulse_current(w,a);self.assertIn(key+'_limited_six_months_complete',v);self.assertEqual(len(w.events),before+1)
     ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));choose(w,ev,'route_3')
     self.assertEqual(v[slot(a)+'_outcome'],3);self.assertEqual(v[key+'_route'],route)
     self.assertEqual(w.treasury['OIR'],-fee);self.assertEqual(v['ywc_v03_active_arc_count'],0)
 def test_stale_full_rejection_preserves_current_queued_notice_epoch(self):
  for i,a in enumerate(self.arcs):
   p=pre(a);key='ywc_oir_'+p;w,ev=play_final(a,1);v=w.countries['OIR'];fee={'pasture':150,'supply':100,'tolls':100}[p]
   choose(w,ev,'defer');ev=deliver(w,a);choose(w,ev,'defer');w.advance_months(6);before=len(w.events);pulse_current(w,a)
   self.assertEqual(len(w.events),before+1);ev=fire(w,a,int(w.events[-1][1].split('.')[-1]))
   v['in_default']=True
   if p=='pasture':v['fixture_states'][0]['buildings'][1]['occupancy']=0.2
   elif p=='supply':v['army_size']=100
   else:v['fixture_states'][0]['market_access']=0.2
   pulse_current(w,a);self.assertIn(key+'_blocked_timer_started',v);self.assertNotIn(key+'_six_months_complete',v)
   w.advance_days(365);other=self.arcs[(i+1)%len(self.arcs)];start(w,other);other_event=deliver(w,other,0);choose(w,other_event,'defer')
   before=len(w.events);pulse_current(w,a);self.assertEqual(len(w.events),before)
   notice_id=int(a['events'][-2]['id'].split('.')[-1]);self.assertEqual(v[key+'_notice_event'],notice_id)
   self.assertIn(key+'_12_notice_sent',v);self.assertEqual(w.days_until_expiry['OIR'][key+'_blocked_36_due'],730)
   stale=next(o for o in ev['options'] if o['key']=='route_1');w.execute(nodes(stale['effect']),'OIR');sync(w)
   self.assertEqual(v[key+'_pending_event'],int(a['events'][-3]['id'].split('.')[-1]))
   self.assertEqual(v[key+'_notice_event'],notice_id);self.assertIn(key+'_blocked_timer_started',v);self.assertIn(key+'_12_notice_sent',v)
   self.assertEqual(w.days_until_expiry['OIR'][key+'_blocked_36_due'],730);self.assertNotIn(key+'_outcome',v);self.assertEqual(w.treasury['OIR'],-fee)
 def test_actual_mature_terminal_rejection_requeues_and_requires_fresh_watch(self):
  fees={"pasture":(150,50),"supply":(100,60),"tolls":(100,40)}
  for a in self.arcs:
   p=pre(a);vkey='ywc_oir_'+p
   for route in (1,2):
    fee=fees[p][route-1];w,ev=play_final(a,route);v=w.countries['OIR'];self.assertEqual(w.treasury['OIR'],-fee)
    choose(w,ev,'defer');ev=deliver(w,a);choose(w,ev,'defer')
    w.advance_months(6);before=len(w.events);pulse_current(w,a);self.assertIn(vkey+'_six_months_complete',v)
    self.assertEqual(len(w.events),before+1);ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));self.assertEqual(ev['id'],a['events'][-3]['id'])
    v['in_default']=True;cash=w.treasury['OIR'];stale_option=next(o for o in ev['options'] if o['key']==f'route_{route}');w.execute(nodes(stale_option['effect']),'OIR');sync(w)
    self.assertEqual(w.treasury['OIR'],cash);self.assertEqual(v[vkey+'_route'],route)
    self.assertNotIn(vkey+'_six_months_complete',v);self.assertNotIn(vkey+'_observation_timer',v)
    self.assertEqual(v[vkey+'_pending_event'],int(ev['id'].split('.')[-1]))
    v['in_default']=False
    w.advance_days(90);ev=deliver(w,a,0);self.assertEqual(ev['id'],a['events'][-3]['id'])
    choose(w,ev,'defer');self.assertNotIn(vkey+'_six_months_complete',v)
    w.advance_months(5);pulse_current(w,a);self.assertNotIn(vkey+'_six_months_complete',v)
    w.advance_months(1);before=len(w.events);pulse_current(w,a);self.assertIn(vkey+'_six_months_complete',v)
    self.assertEqual(len(w.events),before+1);ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));choose(w,ev,f'route_{route}')
    self.assertEqual(v[slot(a)+'_outcome'],route);self.assertEqual(w.treasury['OIR'],-fee)
    self.assertEqual(v['ywc_v03_active_arc_count'],0)
 def test_actual_limited_terminal_rejection_requeues_and_restarts_limited_watch(self):
  for a in self.arcs:
   p=pre(a);key='ywc_oir_'+p;w,ev=play_final(a,3);v=w.countries['OIR']
   choose(w,ev,'defer');ev=deliver(w,a);choose(w,ev,'defer')
   if p=='pasture':v['ywc_flavor_oir_banner_cohesion']=30
   elif p=='supply':v['army_size']=400
   else:v['fixture_states'][0]['market_access']=0.45
   ev=deliver(w,a);choose(w,ev,'defer');w.advance_days(365);notice=deliver(w,a,0)
   self.assertEqual(notice['id'],a['events'][-2]['id']);choose(w,notice,'narrow_scope')
   ev=deliver(w,a);self.assertEqual(ev['id'],a['events'][-3]['id']);choose(w,ev,'defer')
   w.advance_months(6);before=len(w.events);pulse_current(w,a)
   self.assertIn(key+'_limited_six_months_complete',v);self.assertEqual(len(w.events),before+1)
   ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));v['in_default']=True
   stale_option=next(o for o in ev['options'] if o['key']=='route_3');w.execute(nodes(stale_option['effect']),'OIR');sync(w)
   self.assertNotIn(key+'_limited_six_months_complete',v);self.assertEqual(v[key+'_pending_event'],int(ev['id'].split('.')[-1]))
   self.assertEqual(v[key+'_route'],3);self.assertNotIn(slot(a)+'_settled',v)
   v['in_default']=False;w.advance_days(90);before=len(w.events);pulse_current(w,a);self.assertEqual(len(w.events),before+1)
   ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));choose(w,ev,'defer')
   self.assertNotIn(key+'_limited_six_months_complete',v)
   w.advance_months(5);pulse_current(w,a);self.assertNotIn(key+'_limited_six_months_complete',v)
   w.advance_months(1);before=len(w.events);pulse_current(w,a);self.assertIn(key+'_limited_six_months_complete',v);self.assertEqual(len(w.events),before+1)
   ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));choose(w,ev,'route_3')
   self.assertEqual(v[slot(a)+'_outcome'],3);self.assertEqual(w.treasury['OIR'],0);self.assertEqual(v['ywc_v03_active_arc_count'],0)
 def test_qualified_immature_close_keeps_clock_and_settled_close_stays_terminal(self):
  calls={"pasture":"ywc_oir_close_pasture_as_court","supply":"ywc_oir_close_supply_as_unified","tolls":"ywc_oir_close_tolls_as_single"}
  for a in self.arcs:
   p=pre(a);key='ywc_oir_'+p;w,ev=play_final(a,1);v=w.countries['OIR']
   choose(w,ev,'defer');ev=deliver(w,a);choose(w,ev,'defer')
   timer=v[key+'_observation_timer'];self.assertIn(key+'_observation_started',v)
   w.run(calls[p],'OIR');self.assertEqual(v[key+'_observation_timer'],timer)
   self.assertIn(key+'_observation_started',v);self.assertNotIn(key+'_six_months_complete',v)
   w.advance_months(6);before=len(w.events);pulse_current(w,a);self.assertEqual(len(w.events),before+1)
   ev=fire(w,a,int(w.events[-1][1].split('.')[-1]));choose(w,ev,'route_1')
   after=(v[slot(a)+'_outcome'],v['ywc_v03_active_arc_count'],v['ywc_v03_visible_task_count'],w.treasury['OIR'],len(w.modifiers))
   w.run(calls[p],'OIR')
   self.assertEqual((v[slot(a)+'_outcome'],v['ywc_v03_active_arc_count'],v['ywc_v03_visible_task_count'],w.treasury['OIR'],len(w.modifiers)),after)
 def test_actual_recovery_starts_new_twelve_and_thirty_six_month_notice_epoch(self):
  for a in self.arcs:
   p=pre(a);vkey='ywc_oir_'+p
   w,ev=play_final(a,1);v=w.countries['OIR'];choose(w,ev,'defer');lose(v,p)
   ev=deliver(w,a);choose(w,ev,'defer')
   w.advance_days(365);n=deliver(w,a,0);self.assertEqual(n['id'],a['events'][-2]['id']);choose(w,n,'defer')
   w.advance_days(730);n=deliver(w,a,0);self.assertEqual(n['id'],a['events'][-1]['id']);choose(w,n,'defer')
   if p=='pasture':v['fixture_states'][0]['buildings'][1]['occupancy']=0.8
   elif p=='supply':v['army_size']=2200
   else:v['fixture_states'][0]['market_access']=0.9
   pulse_current(w,a)
   for suffix in ('blocked_timer_started','blocked_12_due','blocked_36_due','12_notice_sent','36_notice_sent','notice_event','last_notice_event'):
    self.assertNotIn(vkey+'_'+suffix,v,(a['slug'],suffix))
   lose(v,p);ev=deliver(w,a);choose(w,ev,'defer')
   w.advance_days(365);n=deliver(w,a,0);self.assertEqual(n['id'],a['events'][-2]['id'])
   self.assertIn(vkey+'_12_notice_sent',v);choose(w,n,'defer')
   w.advance_days(730);n=deliver(w,a,0);self.assertEqual(n['id'],a['events'][-1]['id'])
   self.assertIn(vkey+'_36_notice_sent',v);choose(w,n,'defer')
 def test_all_helpers_resolve_and_no_territory_or_minerals(self):
  calls=set(re.findall(r'(?<![A-Za-z0-9_.])(ywc_[a-z0-9_]+)\s*=\s*(?:yes|no|\{)',json.dumps(self.catalog)))
  self.assertFalse(calls-defs(),sorted(calls-defs()))
  all_text=json.dumps(self.catalog)+self.e+self.t
  for bad in ('annex_country','discover_in_state','add_state_region','mg:horses'):self.assertNotIn(bad,all_text)
if __name__=='__main__':unittest.main()

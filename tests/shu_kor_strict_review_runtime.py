
import json,sys,copy,operator,hashlib,traceback
from pathlib import Path
sys.path.insert(0,'tests')
from clausewitz_harness import PulseWorld,parse
from test_v03_tib_foundation_lifecycle import TibWorldFacts
# Extracted strict production-AST/world-fact adapter; it never reads ignored review artifacts.
def field(ns,k,d=None):return next((v for n,_,v in ns if n==k),d if d is not None else [])
def body(s):return parse(s.strip()[1:-1]) if s else []
class Strict(TibWorldFacts):
 def __init__(self,t):
  self.tag=t.upper(); self.t=t
  def rd(p):return Path(p).read_text('utf-8-sig')
  self.cat=json.loads(rd(f'data/content/v03/countries/{t}.json'))
  super().__init__(rd('yongchang_world/common/scripted_effects/ywc_v03_effects.txt')+'\n'+rd(f'yongchang_world/common/scripted_effects/ywc_v03_{t}_effects.txt'),rd('yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt')+'\n'+rd(f'yongchang_world/common/scripted_triggers/ywc_v03_{t}_triggers.txt'),{self.tag:{}})
  self.journal_defs=dict((k,v)for k,_,v in parse(rd(f'yongchang_world/common/journal_entries/ywc_v03_country_{t}_journal.txt')))
  self.event_defs=dict((k,v)for k,_,v in parse(rd(f'yongchang_world/events/ywc_v03_country_{t}_events.txt')) if isinstance(v,list))
  self.active={self.tag:[]};self.history={self.tag:{}};self.requests=[];self.elapsed_months=0;self.trace=[];self.scope_ig=None;self.request_cursor=0
 _comparison_ops={'=','!=','>','>=','<','<='}
 @staticmethod
 def _number(value,node):
  try:
   number=float(value)
  except (TypeError,ValueError):raise AssertionError(('malformed_numeric_value',node,value))
  if not __import__('math').isfinite(number):raise AssertionError(('nonfinite_numeric_value',node,value))
  return number
 def _validate_ig_query(self,op,value,node):
  if op!='=' or not isinstance(value,list) or not value:raise AssertionError(('malformed_any_interest_group',node))
  seen=set()
  for child in value:
   if not isinstance(child,(tuple,list)) or len(child)!=3:raise AssertionError(('malformed_ig_child',node,child))
   key,cop,cv=child
   if key not in ('is_interest_group_type','ig_approval') or key in seen:raise AssertionError(('unknown_or_duplicate_ig_child',node,child))
   seen.add(key)
   if key=='is_interest_group_type':
    if cop!='=' or not isinstance(cv,str) or not cv.startswith('ig_'):raise AssertionError(('malformed_ig_type_child',node,child))
   else:
    if cop not in self._comparison_ops or not isinstance(cv,str):raise AssertionError(('malformed_ig_approval_child',node,child))
    self._number(cv,node)
  if not seen:raise AssertionError(('empty_any_interest_group',node))
 def condition(self,node,tag):
  k,op,v=node;s=self.countries[tag]
  if k in self.trigger_defs and v in ('yes','no'):return self.conditions(self.trigger_defs[k],tag)==(v=='yes')
  if k=='has_journal_entry':return v in self.active[tag]
  if k=='has_modifier':return any(t==tag and f.get('modifier',f.get('name'))==v for t,f in self.modifiers)
  if k=='state_region':return self.state_scope is not None and self.state_scope['region']==v
  if k=='has_building':return self.state_scope is not None and any(b['type']==v for b in self.state_scope['buildings'])
  if k=='is_building_group':return self.building_scope is not None and v in self.building_scope.get('groups',[])
  if k=='building_has_goods_shortage':return self.building_scope is not None and self.building_scope['shortage']==(v=='yes')
  if k=='pop_has_primary_culture':return self.pop_scope is not None and self.pop_scope['primary']==(v=='yes')
  if k=='pop_acceptance':return self.pop_scope is not None and self.compare(self.pop_scope['acceptance'],op,int(v.rsplit('_',1)[1]))
  if k=='wealth':
   r=s.get(v[5:],0) if v.startswith('ROOT.') else float(v)
   return self.pop_scope is not None and self.compare(self.pop_scope['wealth'],op,r)
  if k=='literacy_rate' and self.pop_scope is not None:return self.compare(self.pop_scope['literacy'],op,float(v))
  if k=='any_interest_group':
   self._validate_ig_query(op,v,node)
   old=self.scope_ig
   try:
    result=False
    for ig in s.get('igs',[]):
     self.scope_ig=ig
     matched=True
     for child in v:
      ck,cop,cv=child
      if ck=='is_interest_group_type': matched=matched and ig.get('type')==cv
      else: matched=matched and self.compare(float(ig['approval']),cop,float(cv))
     result=result or matched
    return result
   finally:self.scope_ig=old
  if k=='is_interest_group_type':
   if self.scope_ig is None:raise AssertionError(('ig_type_outside_scope',node))
   if op!='=' or not isinstance(v,str) or not v.startswith('ig_'):raise AssertionError(('malformed_ig_type',node))
   return (self.scope_ig.get('type') if isinstance(self.scope_ig,dict) else self.scope_ig)==v
  if k=='ig_approval':
   if self.scope_ig is None:raise AssertionError(('ig_approval_outside_scope',node))
   if op not in self._comparison_ops or not isinstance(v,str):raise AssertionError(('malformed_ig_approval',node))
   return self.compare(float(self.scope_ig['approval']),op,self._number(v,node))
  if k in ['country_has_voting_franchise','is_subject']:return bool(s.get(k,False))==(v=='yes')
  if k.startswith(('ROOT.modifier:','modifier:')):
   return self.compare(s.get(k.removeprefix('ROOT.'),0),op,(v=='yes') if v in ('yes','no') else float(v))
  if k in ['army_size','legitimacy','authority']:return self.compare(s.get(k,0),op,float(v))
  if k=='gold_reserves':
   if op not in self._comparison_ops:raise AssertionError(('malformed_gold_operator',node))
   if isinstance(v,list):
    seen=set();values=[]
    for child in v:
     if not isinstance(child,(tuple,list)) or len(child)!=3:raise AssertionError(('malformed_gold_child',node,child))
     ck,cop,cv=child
     if ck not in ('value','multiply') or ck in seen:raise AssertionError(('unknown_or_duplicate_gold_child',node,child))
     seen.add(ck)
     if cop!='=':raise AssertionError(('malformed_gold_child_operator',node,child))
     if not isinstance(cv,str):raise AssertionError(('malformed_gold_child_value',node,child))
     values.append((ck,cv))
    values=dict(values)
    if 'value' not in values:raise AssertionError(('missing_gold_value',node))
    raw=values['value'];r=s.get(raw[4:],0) if raw.startswith('var:') else self._number(raw,node)
    if 'multiply' in values:r*=self._number(values['multiply'],node)
   elif isinstance(v,str):r=s.get(v[4:],0) if v.startswith('var:') else self._number(v,node)
   else:raise AssertionError(('malformed_gold_value',node))
   return self.compare(s.get('gold_reserves',0)+self.treasury[tag],op,r)
  return super().condition(node,tag)
 def execute(self,ns,tag):
  result=super().execute(ns,tag)
  while self.request_cursor<len(self.journals):
   t,b=self.journals[self.request_cursor];self.request_cursor+=1
   jid=field(b,'type')
   if jid in self.journal_defs:self.requests.append(jid)
   else:self.trace.append({'outside_scope_legacy_request':jid})
  return result
 def activate_entry(self,arc,jid,explicit=False):
  if jid in self.history[self.tag]:return
  j=self.journal_defs[jid]
  for k in (['possible'] if explicit else ['is_shown_when_inactive','possible']):
   ns=field(j,k,None)
   if ns and not self.conditions(ns,self.tag):raise AssertionError(('admission',jid,k))
  self.active[self.tag].append(jid);self.history[self.tag][jid]='active'
  self.trace.append({'admit':jid,'month':self.elapsed_months,'explicit':explicit})
  self.execute(field(j,'immediate'),self.tag)
 def refresh(self,arc):
  for jid in list(self.active[self.tag]):
   j=self.journal_defs[jid];g=self.conditions(field(j,'complete'),self.tag);f=self.conditions(field(j,'fail'),self.tag)
   if g and f:raise AssertionError(('goal/fail overlap',jid))
   if g or f:
    self.active[self.tag].remove(jid);self.history[self.tag][jid]='complete' if g else 'failed'
    self.trace.append({'finish':jid,'success':g,'month':self.elapsed_months})
    self.execute(field(j,'on_complete' if g else 'on_fail'),self.tag)
  while self.requests:self.activate_entry(arc,self.requests.pop(0),True)
  for jrow in arc['journals']:
   jid=jrow['id'];j=self.journal_defs[jid]
   if jid not in self.history[self.tag] and field(j,'possible') and self.conditions(field(j,'possible'),self.tag) and (not field(j,'is_shown_when_inactive') or self.conditions(field(j,'is_shown_when_inactive'),self.tag)):self.activate_entry(arc,jid)
 def pulse(self,arc):
  self.refresh(arc)
  for jid in list(self.active[self.tag]):
   j=self.journal_defs[jid]
   assert not self.conditions(field(j,'complete'),self.tag) and not self.conditions(field(j,'fail'),self.tag),('terminalpulse',jid)
   self.execute(field(field(j,'on_monthly_pulse'),'effect'),self.tag)
  self.refresh(arc)
 def deliver(self,arc,want):
  for _ in range(75):
   self.pulse(arc)
   if self.events:
    ev=self.events.pop(0)[1]
    e=self.event_defs[ev]
    if not self.conditions(field(e,'trigger'),self.tag):
     self.trace.append({'rejected_event_trigger':ev,'month':self.elapsed_months})
     continue
    self.execute(field(e,'immediate'),self.tag)
    if ev!=want:
     raise AssertionError(('unexpected_event',ev,want,self.elapsed_months))
    return e
   self.advance_months(1);self.elapsed_months+=1
  raise AssertionError(('no_event',want,self.active,self.countries[self.tag]))
 def strict_ai_weight(self,nodes):
  allowed_top={'base','modifier'};allowed_modifier={'trigger','add','multiply','factor'}
  if any(k not in allowed_top or op!='=' for k,op,_ in nodes):raise AssertionError(('unsupported_ai_node',nodes))
  base=[v for k,_,v in nodes if k=='base']
  if len(base)!=1:raise AssertionError(('ai_base_shape',nodes))
  weight=float(base[0])
  for key,op,mod in nodes:
   if key!='modifier':continue
   if op!='=' or not isinstance(mod,list):raise AssertionError(('ai_modifier_shape',mod))
   if any(k not in allowed_modifier or child_op!='=' for k,child_op,_ in mod):raise AssertionError(('unsupported_ai_modifier_child',mod))
   triggers=[v for k,_,v in mod if k=='trigger']
   if len(triggers)!=1:raise AssertionError(('ai_trigger_shape',mod))
   actions=[(k,v) for k,_,v in mod if k in ('add','multiply','factor')]
   if len(actions)!=1:raise AssertionError(('ai_action_shape',mod))
   action,value=actions[0]
   if not isinstance(value,str):raise AssertionError(('ai_action_value',value))
   if self.conditions(triggers[0],self.tag):
    n=float(value)
    if action=='add':weight+=n
    elif action in ('multiply','factor'):weight*=n
  if weight<0:raise AssertionError(('negative_ai_weight',weight))
  return weight
 def options(self,e):
  rows=[]
  for k,_,o in e:
   if k!='option':continue
   ai=field(o,'ai_chance')
   rows.append({'option':field(o,'name').split('.')[-1],'legal':self.conditions(field(o,'trigger'),self.tag),'weight':self.strict_ai_weight(ai)})
  return rows
 def context(self,e):
  out={}
  for name in ['normal','paid_cash0','default','friendly','hostile','war_alone']:
   w=copy.deepcopy(self);s=w.countries[self.tag]
   if name=='paid_cash0':s['gold_reserves']=-w.treasury[self.tag]
   elif name=='default':s['in_default']=True
   elif name in ('friendly','hostile'):s['relations']={'NMG':100 if name=='friendly' else -100};s['existing_pact']=name=='friendly'
   elif name=='war_alone':s['is_at_war']=True
   out[name]=w.options(e)
  return out
 def choose(self,arc,e,key,contexts=True):
  eid=field(e,'title').removesuffix('.t');o=next(o for k,_,o in e if k=='option' and field(o,'name').endswith('.'+key))
  assert self.conditions(field(o,'trigger'),self.tag),('illegal_choice',eid,key,self.options(e))
  before=copy.deepcopy(self.countries[self.tag]);tre=self.treasury[self.tag];mods=len(self.modifiers)
  terminal_probe={}
  if key.startswith(('establish','settle','confirm_','common_qualification','territorial_compact')) and int(eid.split('.')[-1]) in (1009,1015,1017,1023,1025):
   for scenario in ('paid_cash0','default','war_alone','resource_loss'):
    q=copy.deepcopy(self);state=q.countries[q.tag]
    if scenario=='paid_cash0':state['gold_reserves']=-q.treasury[q.tag]
    elif scenario=='default':state['in_default']=True
    elif scenario=='war_alone':state['is_at_war']=True
    else:
     for st in state['states']:
      for b in st['buildings']:b['occupancy']=0
      for p in st['pops']:
       if p.get('workplace'):p['workplace']['occupancy']=0
    if scenario in ('war_alone','resource_loss'):q.pulse(arc)
    legal=q.conditions(field(o,'trigger'),q.tag)
    oldcash=q.treasury[q.tag]
    # whole source option effect, legal now or stale after a genuine current-state change.
    q.execute([n for n in o if n[0]not in ('name','trigger','ai_chance','custom_tooltip')],q.tag)
    terminal_probe[scenario]={'legal':legal,'cash_delta':q.treasury[q.tag]-oldcash,'settled':state.get('ywc_v03_'+q.t+'_'+arc['slug']+'_settled'),'outcome':state.get('ywc_v03_'+q.t+'_'+arc['slug']+'_outcome'),'pending':{k:v for k,v in state.items() if 'pending_event' in k},'modifiers':q.modifiers[mods:]}

  row={'event':eid,'choice':key,'month':self.elapsed_months,'active':copy.deepcopy(self.active[self.tag]),'contexts':self.context(e) if contexts else {}}
  self.execute([n for n in o if n[0]not in ('name','trigger','ai_chance','custom_tooltip')],self.tag)
  row.update(terminal_scenarios=terminal_probe,treasury_delta=self.treasury[self.tag]-tre,changed={k:v for k,v in self.countries[self.tag].items() if before.get(k)!=v},modifiers=self.modifiers[mods:])
  self.trace.append(row);self.refresh(arc)
def facts(landowner_approval=-2):
 b=[{'type':ty,'occupancy':1,'shortage':False,'groups':['bg_agriculture'] if ty=='building_maize_farm' else []} for ty in ['building_government_administration','building_barrack','building_university','building_port','building_maize_farm']]
 return {'ywc_v03_initialized':1,'ywc_v03_release_version':3,'yearly_gross_income':52000,'gold_reserves':100000,'net_fixed_income':100,'bureaucracy':100,'scaled_debt':0,'army_size':10,'legitimacy':80,'authority':150,'is_at_war':False,'in_default':False,'is_subject':False,'country_has_voting_franchise':False,'laws':['law_per_capita_based_taxation','law_protectionism','law_professional_army','law_tenant_farmers','law_multicultural','law_public_schools'],'institutions':{'institution_schools':2},'igs':[{'type':'ig_landowners','approval':landowner_approval},{'type':'ig_devout','approval':0},{'type':'ig_intelligentsia','approval':0},{'type':'ig_armed_forces','approval':0}],'states':[{'owned':True,'region':'s:STATE_SICHUAN','buildings':b,'pops':[{'primary':False,'acceptance':5,'type':'bureaucrats','employed':True,'wealth':25,'literacy':.8,'workplace':b[0]}]}]}

M1_PLAN=[(1000,'pilot_state_sichuan'),(1001,'central_register'),(1002,'time_limited_exemption'),(1003,'budget_queue'),(1004,'central_appeal'),(1005,'refuse_private_advance'),(1006,'publish_central_difference'),(1007,'central_public_duties'),(1008,'review_in_peace'),(1009,'establish_central')]
def runplan(w,arc,plan=M1_PLAN):
 for n,key in plan:
  e=w.deliver(arc,f'ywc_shu.{n}')
  w.choose(arc,e,key)

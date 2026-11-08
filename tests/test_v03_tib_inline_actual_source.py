"""Self-contained TIB authored-source world factory for inline adapter contracts.

Construction is copied into this test seam so runtime tests never load private planning files.
It uses real country history, legacy events, initializer, roots and source helper registries.
"""
from __future__ import annotations
from pathlib import Path
from contextlib import contextmanager
import copy
import math
import unittest
from tests.clausewitz_harness import PulseWorld, parse
from tests.test_v03_tib_foundation_lifecycle import TibWorldFacts
from tests.test_v03_tib_inline_adapter import (_v2_catalog_from_formal_tib_source,
    assert_inline_supported, catalog)
from tools import build_v03_content
from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog

ROOT=Path(__file__).resolve().parents[1]; TAG='TIB'
STARTS='yongchang_world/common/history/countries/ywc_content_starts.txt'
EVENT_PATHS=('yongchang_world/events/ywc_steppe_highland_events.txt','yongchang_world/events/ywc_large_campaign_events.txt','yongchang_world/events/ywc_v03_country_tib_events.txt')
JOURNAL_PATHS=('yongchang_world/common/journal_entries/ywc_tib.txt','yongchang_world/common/journal_entries/ywc_v03_country_tib_journal.txt','yongchang_world/common/journal_entries/ywc_shared_journal.txt','yongchang_world/common/journal_entries/ywc_large_campaign_crises.txt')
EFFECT_PATHS=('yongchang_world/common/scripted_effects/ywc_v03_tib_effects.txt','yongchang_world/common/scripted_effects/ywc_v03_effects.txt','yongchang_world/common/scripted_effects/ywc_shared_effects.txt','yongchang_world/common/scripted_effects/ywc_campaign_effects.txt','yongchang_world/common/scripted_effects/ywc_flavor_effects.txt')
TRIGGER_PATHS=('yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt','yongchang_world/common/scripted_triggers/ywc_v03_tib_triggers.txt')
def _read(rel): return (ROOT/rel).read_text(encoding='utf-8-sig')
def _defs(paths):
    out={}
    for rel in paths:
        for key,_,body in parse(_read(rel)):
            if key in out and key!='namespace': raise AssertionError(('duplicate source definition',rel,key))
            out[key]=body
    return out
def _field(nodes,name,default=None): return next((body for key,_,body in nodes if key==name),default)

class _ScopedDispatchList(list):
    """Observe actual base trigger_event appends and freeze the scoped values."""
    def __init__(self,world): super().__init__(); self.world=world
    def append(self,row):
        super().append(row)
        dispatch={'tag':row[0],'event_id':row[1],
          'scope_context':dict(self.world.scope_context),'dispatch_id':len(self.world.dispatch_contexts)+1}
        self.world.dispatch_contexts.append(dispatch)
        observer=self.world._dispatch_append_observer
        if observer is not None: observer(self.world,copy.deepcopy(dispatch))

class _ActualTibWorld(TibWorldFacts):
    def __init__(self,effects,triggers,countries,known_journals):
        self.known_journals=known_journals
        super().__init__(effects,triggers,countries)
        self.scope_context={}; self.scope_context_stack=[]; self.dispatch_contexts=[]; self._explicit_context=0
        self._execute_depth=0
        self._dispatch_append_observer=None
        self._owned_ack_observer=None
        self._owned_ack_after_observer=None
        self._effect_run_observer=None
        self.events=_ScopedDispatchList(self)
    @contextmanager
    def invocation(self, frozen=None):
        prior=self.scope_context
        self.scope_context=dict(frozen or {})
        self._explicit_context+=1
        try: yield
        finally: self.scope_context=prior; self._explicit_context-=1
    def run(self,name,tag=TAG):
        if self._effect_run_observer is not None:
            self._effect_run_observer(self,name,tag)
        owned=isinstance(name,str) and name.startswith('ywc_v03_tib_inline_ack_')
        if owned and self._owned_ack_observer is not None:
            self._owned_ack_observer(self,name,tag)
        result=super().run(name,tag)
        if owned and self._owned_ack_after_observer is not None:
            self._owned_ack_after_observer(self,name,tag)
        return result
    def _predicate_scope(self):
        """The strict base enters these real scopes before calling predicates."""
        for name,scope in (('building_scope','building'),('pop_scope','pop'),
                           ('good_scope','good'),('state_scope','state')):
            if getattr(self,name,None) is not None: return scope
        return 'country'
    def _scope_checkpoint(self):
        return tuple(getattr(self,name,None) for name in ('state_scope','pop_scope','building_scope','good_scope'))
    def _restore_scopes(self,checkpoint):
        self.state_scope,self.pop_scope,self.building_scope,self.good_scope=checkpoint
    def conditions(self,nodes,tag):
        # Validate the entire reachable grammar before any all()/OR/scope
        # evaluation can hide an unsupported node behind a false/empty path.
        depth=getattr(self,'_prevalidated_depth',0); checkpoint=self._scope_checkpoint()
        if depth==0:
            for node in nodes: self._validate_shape(node,self._predicate_scope())
        self._prevalidated_depth=depth+1
        try: return super().conditions(nodes,tag)
        finally:
            self._prevalidated_depth=depth
            self._restore_scopes(checkpoint)
    @staticmethod
    def _shape_number(value,context,reference=False):
        if not isinstance(value,str) or not value: raise AssertionError(('invalid numeric scalar',context,value))
        if reference and value.startswith('var:'):
            if not value[4:] or any(c.isspace() for c in value[4:]): raise AssertionError(('invalid variable reference',context,value))
            return
        try: number=float(value)
        except (ValueError,TypeError) as exc: raise AssertionError(('invalid numeric scalar',context,value)) from exc
        if not math.isfinite(number): raise AssertionError(('non-finite numeric scalar',context,value))
    def _validate_shape(self,node,scope='country',seen=frozenset()):
        if not isinstance(node,tuple) or len(node)!=3: raise AssertionError(('invalid condition node',node))
        key,op,value=node; ops={'=','!=','>','>=','<','<='}
        if not isinstance(key,str) or not isinstance(op,str): raise AssertionError(('invalid condition key/operator',node))
        def block():
            if op!='=' or not isinstance(value,list): raise AssertionError(('invalid scoped block',node))
            if any(not isinstance(child,tuple) or len(child)!=3 or not isinstance(child[0],str) or not isinstance(child[1],str) for child in value):
                raise AssertionError(('malformed scoped child',node))
        def scalar():
            if op!='=' or not isinstance(value,str) or not value: raise AssertionError(('invalid scalar predicate',node))
        def validate_children(items,child_scope=scope):
            for child in items: self._validate_shape(child,child_scope,seen)
        if key in self.trigger_defs:
            if op!='=' or value!='yes': raise AssertionError(('invalid scripted trigger call',node))
            if key in seen: raise AssertionError(('cyclic scripted trigger reference',key))
            for child in self.trigger_defs[key]: self._validate_shape(child,scope,seen|{key})
            return
        if key in ('AND','OR','NOT','NOR'):
            block(); validate_children(value); return
        if key in ('any_scope_state','any_scope_pop','any_scope_building','workplace'):
            if key=='workplace':
                if op!='?=' or not isinstance(value,list) or scope!='pop': raise AssertionError(('invalid workplace scope',node,scope))
                child_scope='building'
            else:
                block()
                needed={'any_scope_state':'country','any_scope_pop':'state','any_scope_building':'state'}[key]
                if scope!=needed: raise AssertionError(('invalid source scope nesting',node,scope))
                child_scope={'any_scope_state':'state','any_scope_pop':'pop','any_scope_building':'building'}[key]
            validate_children(value,child_scope); return
        scoped={'is_owned_by':'state','market_access':'state','average_sol':'state','radical_fraction':'state',
                'is_pop_type':'pop','is_employed':'pop','is_building_type':'building','occupancy':'building',
                'market_goods_pricier':'good','market_goods_imports':'good','market_goods_exports':'good'}
        if key in scoped and scope!=scoped[key]: raise AssertionError(('predicate outside supported scope',node,scope))
        if key=='has_journal_entry':
            scalar()
            if value not in self.known_journals: raise AssertionError(('unknown actual JE predicate',node))
            return
        if key in ('has_variable','has_modifier','has_law','has_law_or_variant','is_owned_by','is_pop_type','is_building_type'):
            scalar()
            if key=='is_owned_by' and value!='ROOT': raise AssertionError(('unsupported ownership target',node))
            if key in ('has_law','has_law_or_variant') and not value.removeprefix('law_type:').startswith('law_'): raise AssertionError(('invalid law identifier',node))
            if key=='is_building_type' and not value.startswith('building_'): raise AssertionError(('invalid building identifier',node))
            return
        if key in ('always','is_employed','in_default','is_at_war','is_subject'):
            scalar()
            if value not in ('yes','no'): raise AssertionError(('invalid boolean predicate',node))
            return
        if key=='exists':
            scalar()
            if not (value.startswith('scope:') and value[6:] or value.startswith('c:') and len(value[2:])==3 and value[2:].isalnum()): raise AssertionError(('unsupported exists scope',node))
            return
        if key.startswith('c:'):
            if op!='?=' or value!='this' or len(key[2:])!=3 or not key[2:].isalnum(): raise AssertionError(('unsupported country optional predicate',node))
            return
        if key.startswith('scope:'):
            if op not in ops or not key[6:] or not isinstance(value,str): raise AssertionError(('invalid scoped numeric predicate',node))
            if value.startswith('scope:'):
                if not value[6:]: raise AssertionError(('empty scope reference',node))
            elif value in ('yes','no'):
                if op not in ('=','!='): raise AssertionError(('invalid boolean scope comparator',node))
            else: self._shape_number(value,node,reference=True)
            return
        if key.startswith('var:'):
            if op not in ops or not key[4:]: raise AssertionError(('invalid variable predicate',node))
            self._shape_number(value,node,reference=True); return
        if key=='market_capital.market':
            block()
            for child in value:
                if not isinstance(child,tuple) or len(child)!=3: raise AssertionError(('invalid market scope child',child))
                good,cop,body=child
                if good!='mg:grain' or cop!='=' or not isinstance(body,list): raise AssertionError(('unsupported market good scope',child))
                validate_children(body,'good')
            return
        if key in ('institution_investment_level','radical_fraction'):
            block(); fields={}
            allowed={'institution','value'} if key=='institution_investment_level' else {'pop_type','value'}
            for child in value:
                if not isinstance(child,tuple) or len(child)!=3: raise AssertionError(('invalid nested predicate child',child))
                ck,cop,cv=child
                if ck not in allowed or ck in fields or not isinstance(cv,str): raise AssertionError(('unknown/duplicate nested predicate field',node,child))
                fields[ck]=(cop,cv)
                if ck=='value':
                    if cop not in ops: raise AssertionError(('invalid nested numeric operator',child))
                    self._shape_number(cv,node)
                elif cop!='=' or not cv or ck=='institution' and cv!='institution_schools': raise AssertionError(('invalid nested scope identifier',child))
            required={'value','institution'} if key=='institution_investment_level' else {'value'}
            if not required<=fields.keys(): raise AssertionError(('incomplete nested predicate',node))
            return
        numeric={'net_fixed_income','bureaucracy','gold_reserves','yearly_gross_income','scaled_debt','literacy_rate',
                 'market_access','average_sol','occupancy','market_goods_pricier','market_goods_imports','market_goods_exports'}
        if key in numeric:
            if op not in ops: raise AssertionError(('invalid numeric predicate operator',node))
            if isinstance(value,list):
                if key!='gold_reserves': raise AssertionError(('unsupported numeric block',node))
                fields={}
                for child in value:
                    if not isinstance(child,tuple) or len(child)!=3: raise AssertionError(('invalid gold child',child))
                    ck,cop,cv=child
                    if ck not in ('value','multiply') or ck in fields or cop!='=': raise AssertionError(('unknown/duplicate gold field',child))
                    fields[ck]=cv; self._shape_number(cv,node,reference=ck=='value')
                if 'value' not in fields: raise AssertionError(('missing gold value',node))
            else: self._shape_number(value,node,reference=key=='gold_reserves')
            return
        if key=='trigger_if':
            block(); limits=[v for k,o,v in value if k=='limit' and o=='=']
            if len(limits)!=1 or not isinstance(limits[0],list): raise AssertionError(('invalid conditional trigger limit',node))
            for ck,cop,cv in value:
                if ck in ('limit','trigger_else'):
                    if cop!='=' or not isinstance(cv,list): raise AssertionError(('invalid conditional trigger block',node))
                    validate_children(cv)
                else: self._validate_shape((ck,cop,cv),scope,seen)
            return
        if key=='calc_true_if':
            block(); amounts=[child for child in value if child[0]=='amount']
            if len(amounts)!=1 or amounts[0][1] not in ('=','>='): raise AssertionError(('invalid count trigger amount',node))
            self._shape_number(amounts[0][2],node)
            validate_children([child for child in value if child[0]!='amount']); return
        raise AssertionError(('unsupported condition grammar',node))
    def condition(self,node,tag):
        depth=getattr(self,'_prevalidated_depth',0); checkpoint=self._scope_checkpoint()
        if depth==0: self._validate_shape(node,self._predicate_scope())
        self._prevalidated_depth=depth+1
        try: return self._condition(node,tag)
        finally:
            self._prevalidated_depth=depth
            self._restore_scopes(checkpoint)
    def _condition(self,node,tag):
        # Only the documented scope-value subset is modeled here. All other
        # predicates retain the strict native-source harness behavior.
        key,comparison,value=node
        if key=='exists' and isinstance(value,str) and value.startswith('scope:'):
            if comparison!='=': raise AssertionError(('unsupported scope exists operator',node))
            return value[6:] in self.scope_context
        if isinstance(key,str) and key.startswith('scope:'):
            name=key[6:]
            if comparison not in ('=','>','<','>=','<=','!='): raise AssertionError(('unknown scope comparison',comparison))
            raw=value
            if not isinstance(raw,str): raise AssertionError(('unsupported scope RHS shape',node))
            if raw in ('yes','no'):
                right=raw=='yes'
                if comparison not in ('=','!='): raise AssertionError(('unsupported boolean scope comparison',node))
            elif isinstance(raw,str) and raw.startswith('var:'):
                rhs=raw[4:]
                if rhs not in self.countries[tag]: raise AssertionError(('missing country variable in scope comparison',rhs))
                right=self.countries[tag][rhs]
            elif isinstance(raw,str) and raw.startswith('scope:'):
                rhs=raw[6:]
                if rhs not in self.scope_context: raise AssertionError(('missing scope RHS in scope comparison',rhs))
                right=self.scope_context[rhs]
            else:
                try: right=float(raw)
                except (TypeError,ValueError) as exc: raise AssertionError(('unsupported scope RHS',node)) from exc
            if isinstance(right,bool):
                if comparison not in ('=','!='): raise AssertionError(('unsupported boolean scope comparison',node))
            else:
                try: right=float(right)
                except (TypeError,ValueError) as exc: raise AssertionError(('non-numeric scope comparison',node)) from exc
                if not math.isfinite(right): raise AssertionError(('non-finite scope comparison RHS',node))
            if name not in self.scope_context: return False
            left=self.scope_context[name]
            if isinstance(left,bool) != isinstance(right,bool): raise AssertionError(('scope comparison type mismatch',node))
            if not isinstance(left,bool):
                try: left=float(left)
                except (TypeError,ValueError) as exc: raise AssertionError(('non-numeric scope comparison LHS',node)) from exc
                if not math.isfinite(left): raise AssertionError(('non-finite scope comparison LHS',node))
            return {'=':lambda a,b:a==b,'>':lambda a,b:a>b,'<':lambda a,b:a<b,'>=':lambda a,b:a>=b,'<=':lambda a,b:a<=b,'!=':lambda a,b:a!=b}[comparison](left,right)
        if key=='has_journal_entry':
            if comparison!='=' or not isinstance(value,str) or value not in self.known_journals:
                raise AssertionError(('unknown or invalid actual JE predicate',node))
            return value in self.active[tag]
        if key=='is_subject':
            if comparison!='=' or value not in ('yes','no'): raise AssertionError(('invalid subject predicate',node))
            return self.countries[tag].get('is_subject',False)==(value=='yes')
        if key.startswith('c:'):
            if comparison!='?=' or value!='this': raise AssertionError(('unsupported country optional predicate',node))
            return super().condition(node,tag)
        if comparison=='?=' and key!='workplace': raise AssertionError(('unsupported optional predicate',node))
        if key=='gold_reserves':
            allowed=('=','>','<','>=','<=','!=')
            if comparison not in allowed: raise AssertionError(('unsupported gold_reserves comparator',node))
            if isinstance(value,list):
                fields={}
                try: rows=[tuple(entry) for entry in value]
                except TypeError as exc: raise AssertionError(('malformed gold_reserves block',node)) from exc
                for entry in rows:
                    if len(entry)!=3: raise AssertionError(('malformed gold_reserves block field',node,entry))
                    field,field_op,field_value=entry
                    if field not in ('value','multiply') or field_op!='=' or field in fields or not isinstance(field_value,str):
                        raise AssertionError(('unsupported gold_reserves block field',node))
                    fields[field]=field_value
                if 'value' not in fields: raise AssertionError(('missing gold_reserves value',node))
            elif isinstance(value,str): fields={'value':value}
            else: raise AssertionError(('unsupported gold_reserves shape',node))
            raw=fields['value']
            if raw.startswith('var:'):
                variable=raw[4:]
                if variable not in self.countries[tag]: raise AssertionError(('missing gold_reserves RHS variable',variable))
                variable_value=self.countries[tag][variable]
                if isinstance(variable_value,bool): raise AssertionError(('boolean gold_reserves RHS variable',variable))
                try: right=float(variable_value)
                except (TypeError,ValueError) as exc: raise AssertionError(('non-numeric gold_reserves RHS variable',variable)) from exc
            else:
                try: right=float(raw)
                except (TypeError,ValueError) as exc: raise AssertionError(('non-numeric gold_reserves value',node)) from exc
            try: right*=float(fields.get('multiply',1))
            except (TypeError,ValueError) as exc: raise AssertionError(('non-numeric gold_reserves multiply',node)) from exc
            if not math.isfinite(right): raise AssertionError(('non-finite gold_reserves threshold',node))
            left=float(self.countries[tag].get('gold_reserves',0))+float(self.treasury.get(tag,0))
            return self.compare(left,comparison,right)
        return super().condition(node,tag)
    def available_gold(self,tag):
        return float(self.countries[tag].get('gold_reserves',0))+float(self.treasury.get(tag,0))
    def execute(self,nodes,tag):
        checkpoint=self._scope_checkpoint()
        for key,op,value in nodes:
            if key=='every_scope_state':
                # The supported native command may iterate zero states. Validate
                # its whole limit before the base establishes/iterates scopes.
                if op!='=' or not isinstance(value,list): raise AssertionError(('invalid state command',key,value))
                limits=[]
                for child in value:
                    if not isinstance(child,tuple) or len(child)!=3: raise AssertionError(('invalid state command child',child))
                    ck,cop,cv=child
                    if ck=='limit':
                        if cop!='=' or not isinstance(cv,list): raise AssertionError(('invalid state command limit',child))
                        limits.append(cv)
                if len(limits)>1: raise AssertionError(('duplicate state command limit',value))
                for limit in limits:
                    for predicate in limit: self._validate_shape(predicate,'state')
            if key in ('set_variable','change_variable','clamp_variable'):
                allowed={'name','add','multiply','divide'} if key=='change_variable' else {'name','value','months','days'} if key=='set_variable' else {'name','min','max'}
                seen=set()
                if op!='=' or not isinstance(value,list): raise AssertionError(('invalid variable command',key))
                for ck,cop,cv in value:
                    if ck not in allowed or ck in seen or cop!='=' or not isinstance(cv,str): raise AssertionError(('unknown or duplicate command field',key,ck))
                    seen.add(ck)
            if key in ('trigger_event','add_journal_entry'):
                allowed={'id'} if key=='trigger_event' else {'type'}
                if op!='=' or not isinstance(value,list) or len(value)!=1 or any(k not in allowed or o!='=' or not isinstance(v,str) for k,o,v in value): raise AssertionError(('invalid authored command fields',key,value))
            if key=='add_journal_entry':
                requested=_field(value,'type') if isinstance(value,list) else value
                if requested not in self.known_journals: raise AssertionError(('unknown authored JE',requested))
        outer=self._execute_depth==0; self._execute_depth+=1
        if outer and not self._explicit_context: self.scope_context={}
        try:
            # Keep every original conditional chain intact. save_scope_value_as
            # is the sole added command and naturally terminates a chain.
            pending=[]
            for node in nodes:
                key,op,value=node
                if key=='save_scope_value_as':
                    if pending: super().execute(pending,tag); pending=[]
                    if op!='=' or not isinstance(value,list): raise AssertionError(('unsupported save_scope_value_as node shape',node))
                    fields={}
                    for field,field_op,field_value in value:
                        if field not in ('name','value') or field_op!='=' or not isinstance(field_value,str) or field in fields:
                            raise AssertionError(('unsupported save_scope_value_as field',field,field_op,field_value))
                        fields[field]=field_value
                    if set(fields)!={'name','value'}: raise AssertionError(('unsupported save_scope_value_as fields',fields))
                    name=fields['name']; raw=fields['value']
                    if isinstance(raw,str) and raw.startswith('var:'):
                        actual=self.countries[tag].get(raw[4:],0)
                        if isinstance(actual,bool) or not isinstance(actual,(int,float)) or not math.isfinite(actual): raise AssertionError(('non-numeric frozen value',raw))
                    else:
                        try: actual=float(raw)
                        except (TypeError,ValueError):
                            if raw not in ('yes','no'): raise AssertionError(('unsupported scoped numeric value',raw))
                            actual=raw=='yes'
                    if isinstance(actual,bool) or not math.isfinite(actual): raise AssertionError(('non-numeric scoped value',raw))
                    self.scope_context[name]=actual
                else: pending.append(node)
            if pending: return super().execute(pending,tag)
        finally:
            self._execute_depth-=1
            self._restore_scopes(checkpoint)

def _initial_world(strategy=1):
    """Controlled partial-world ordinary facts; no engine or 1836 claim."""
    if type(strategy) is not int or strategy not in (1,2): raise ValueError('strategy must be 1 or 2')
    effects='\n'.join(_read(p) for p in EFFECT_PATHS)
    triggers='\n'.join(_read(p) for p in TRIGGER_PATHS)
    farm={'type':'building_rice_farm','occupancy':.8}
    admin={'type':'building_government_administration','occupancy':.8}
    university={'type':'building_university','occupancy':.8}
    buildings=[farm,admin]+([university] if strategy==1 else [])
    pops=[{'type':'laborers','employed':True,'workplace':farm,'radical_fraction':.30 if strategy==1 else .10},
          {'type':'bureaucrats','employed':True,'workplace':admin,'radical_fraction':.02}]
    if strategy==1: pops.append({'type':'academics','employed':True,'workplace':university,'radical_fraction':.02})
    state={'yearly_gross_income':5200,'gold_reserves':10000,'net_fixed_income':20,
      'in_default':False,'is_subject':False,'laws':{'law_serfdom','law_religious_schools'},
      'states':[{'owned':True,'market_access':.5,'average_sol':8,'buildings':buildings,'pops':pops}],
      'market':{'grain':{'pricier':.30 if strategy==1 else .20,'imports':5}},
      'institutions':{'institution_schools':1},'literacy_rate':.30}
    journals=_defs(JOURNAL_PATHS)
    world=_ActualTibWorld(effects,triggers,{TAG:state},set(journals))
    world.effects=_defs(EFFECT_PATHS); world.trigger_defs=_defs(TRIGGER_PATHS)
    world.triggers=world.trigger_defs
    world.journal_defs=journals; world.event_defs=_defs(EVENT_PATHS)
    native_catalog=catalog()
    native_journals=_script_defs(build_v03_content._render_journal_file(native_catalog,None),'native journals')
    native_events=_script_defs(build_v03_content._render_event_file(native_catalog,ROOT,None),'native events')
    for arc in native_catalog['arcs']:
        for je in arc['journals']: world.journal_defs[je['id']]=native_journals[je['id']]
        for event in arc['events']: world.event_defs[event['id']]=native_events[event['id']]
    return world

def _run_legacy_and_initialize(world):
    starts=parse(_read(STARTS)); countries=_field(starts,'COUNTRIES',[])
    scope=next((n for n in countries if n[0]=='c:TIB'),None)
    if scope is None or scope[1]!='?=': raise AssertionError('real TIB country history missing')
    world.execute([scope],TAG)
    old_id='ywc_je_flavor_tib_estate_1'
    if not any(t==TAG and _field(b,'type')==old_id for t,b in world.journals): raise AssertionError(('history did not add legacy JE',old_id))
    # Driver activates exactly the JE actually added by history; no business outcome is seeded.
    world.active[TAG].append(old_id); world.history[TAG][old_id]='active'
    old=world.journal_defs[old_id]; expected=['ywc_tib.7','ywc_tib.100','ywc_tib.101','ywc_tib.102','ywc_tib.103','ywc_tib.104']
    pulse=_field(_field(old,'on_monthly_pulse'), 'effect'); trace=[]
    for event_id in expected:
        for _ in range(40):
            before=len(world.events); world.execute(pulse,TAG); emitted=list(world.events[before:]); del world.events[before:]
            if emitted: break
            world.advance_months(1)
        if emitted!=[(TAG,event_id)]: raise AssertionError(('legacy event sequence',event_id,emitted))
        event=world.event_defs[event_id]; trigger=_field(event,'trigger',[])
        if trigger and not world.conditions(trigger,TAG): raise AssertionError(('legacy trigger false',event_id))
        world.execute(_field(event,'immediate',[]),TAG)
        option=next((b for k,_,b in event if k=='option' and _field(b,'name')==event_id+'.b'),None)
        if option is None: raise AssertionError(('legacy option absent',event_id))
        gate=_field(option,'trigger',[])
        if gate and not world.conditions(gate,TAG): raise AssertionError(('legacy option illegal',event_id))
        world.execute([n for n in option if n[0] not in ('name','trigger','ai_chance','default_option','custom_tooltip')],TAG)
        trace.append(event_id); world.advance_months(1)
    complete=world.conditions(_field(old,'complete',[]),TAG); failed=world.conditions(_field(old,'fail',[]),TAG)
    if not complete or failed: raise AssertionError(('legacy JE terminal',complete,failed))
    if _field(old,'on_complete',[]): world.execute(_field(old,'on_complete'),TAG)
    world.active[TAG].remove(old_id); world.history[TAG][old_id]='complete'
    world.root_gates_before_initialize=[(world.conditions(_field(world.journal_defs[a['journals'][0]['id']],'is_shown_when_inactive',[]),TAG),world.conditions(_field(world.journal_defs[a['journals'][0]['id']],'possible',[]),TAG)) for a in catalog()['arcs']]
    if any(shown or possible for shown,possible in world.root_gates_before_initialize): raise AssertionError('roots visible before initializer')
    world.run('ywc_v03_initialize_country',TAG)
    return trace

def _admit_roots(world):
    rows=[]; world.root_counts=[]
    for arc in catalog()['arcs']:
        je=arc['journals'][0]; body=world.journal_defs[je['id']]
        shown=_field(body,'is_shown_when_inactive',[]); possible=_field(body,'possible',[])
        if not world.conditions(shown,TAG) or not world.conditions(possible,TAG): raise AssertionError(('root gates false',je['id']))
        world.execute(_field(body,'immediate',[]),TAG); world.journals.append((TAG,[('type','=',je['id'])]))
        rows.append(je['id']); world.active[TAG].append(je['id']); world.history[TAG][je['id']]='active'
        counts=(world.countries[TAG]['ywc_v03_active_arc_count'],world.countries[TAG]['ywc_v03_visible_task_count'])
        if counts!=(len(rows),len(rows)): raise AssertionError(('actual root counts',counts,len(rows)))
        world.root_counts.append(counts)
    return rows

def _script_defs(text,label):
    out={}
    for key,_,body in parse(text):
        if key in out: raise AssertionError(('duplicate generated definition',label,key))
        out[key]=body
    return out

def _install_rendered_registries(world,candidate,rendered):
    """Install renderer-owned FX/TRG and real builder JEs/events before roots run."""
    fx=_script_defs(rendered['effects'],'effects'); trg=_script_defs(rendered['triggers'],'triggers')
    for label, additions, target in (('effect',fx,world.effects),('trigger',trg,world.trigger_defs)):
        duplicates=set(additions)&set(target)
        if duplicates: raise AssertionError(('generated helper collision',label,sorted(duplicates)))
        target.update(additions)
    journals=_script_defs(build_v03_content._render_journal_file(candidate,rendered),'journals')
    events=_script_defs(build_v03_content._render_event_file(candidate,ROOT,rendered),'events')
    for arc in candidate['arcs']:
        for je in arc['journals']:
            if je['id'] not in journals: raise AssertionError(('generated JE missing',je['id']))
            world.journal_defs[je['id']]=journals[je['id']]
        for event in arc['events']:
            if event['id'] not in world.event_defs or event['id'] not in events:
                raise AssertionError(('generated event missing',event['id']))
            world.event_defs[event['id']]=events[event['id']]
    world.inline_registries={'effects':fx,'triggers':trg,'journals':journals,'events':events}
    world.inline_catalog=candidate; world.inline_rendered=rendered

def actual_tib_inline_identity_control_world(strategy=1):
    world=_initial_world(strategy); legacy=_run_legacy_and_initialize(world); roots=_admit_roots(world)
    return world,{'legacy_events':legacy,'roots':roots}

def actual_tib_inline_world(strategy=1):
    """Install actual generated registries before source history and root admission."""
    candidate=_v2_catalog_from_formal_tib_source()
    try:
        validate_inline_catalog(candidate)
        rendered=render_inline_country_adapters(candidate)
    except ValueError as exc:
        if 'inline adapter is currently enabled only for registered inline countries' in str(exc):
            raise AssertionError(f'TIB inline adapter feature is not registered: {exc}') from exc
        raise
    if len(rendered.get('event_hooks',{}))!=24: raise AssertionError('generated adapter must guard all 24 events')
    world=_initial_world(strategy); _install_rendered_registries(world,candidate,rendered)
    legacy=_run_legacy_and_initialize(world); roots=_admit_roots(world)
    return world,{'legacy_events':legacy,'roots':roots}

def pulse_inline_journals(world):
    """Pulse each live native JE once; reconcile terminals and admit via authored gates."""
    if TAG not in world.active: raise AssertionError('missing active membership')
    emitted=[]
    for jid in list(world.active[TAG]):
        je=world.journal_defs[jid]
        complete=world.conditions(_field(je,'complete',[]),TAG); failed=world.conditions(_field(je,'fail',[]),TAG)
        if complete and failed: raise AssertionError(('JE both complete and failed',jid))
        if complete or failed:
            hook='on_fail' if failed else 'on_complete'
            if _field(je,hook,[]): world.execute(_field(je,hook),TAG)
            world.history[TAG][jid]='failed' if failed else 'complete'; world.active[TAG].remove(jid)
    for arc in catalog()['arcs']:
        for candidate in arc['journals']:
            jid=candidate['id']
            if jid in world.active[TAG] or world.history[TAG].get(jid) in ('complete','failed'): continue
            je=world.journal_defs[jid]
            if world.conditions(_field(je,'is_shown_when_inactive',[]),TAG) and world.conditions(_field(je,'possible',[]),TAG):
                if jid not in world.active[TAG]: world.journals.append((TAG,[('type','=',jid)]))
                world.execute(_field(je,'immediate',[]),TAG); world.active[TAG].append(jid); world.history[TAG][jid]='active'
                break
    for jid in sorted(world.active[TAG]):
        je=world.journal_defs[jid]
        if world.conditions(_field(je,'complete',[]),TAG) or world.conditions(_field(je,'fail',[]),TAG): continue
        before=len(world.events); world.execute(_field(_field(je,'on_monthly_pulse'),'effect'),TAG)
        emitted.extend(world.events[before:]); del world.events[before:]
    return emitted

def run_inline_event_immediate(world,event_id):
    """Run the registered event's full trigger/immediate body exactly once."""
    event=world.event_defs[event_id]
    with world.invocation({}):
        trigger=_field(event,'trigger',[])
        if trigger and not world.conditions(trigger,TAG): raise ValueError(('event trigger false',event_id))
        return world.execute(_field(event,'immediate',[]),TAG)

def _run_inline_event_in_current_context(world,event_id,tag=TAG):
    event=world.event_defs[event_id]
    trigger=_field(event,'trigger',[])
    if trigger and not world.conditions(trigger,tag): raise ValueError(('event trigger false',event_id,tag))
    return world.execute(_field(event,'immediate',[]),tag)

def run_queued_inline_event_immediate(world,dispatch):
    """Run actual event body in the frozen model context from real event append."""
    if dispatch.get('tag')!=TAG: raise AssertionError(('wrong dispatch tag',dispatch.get('tag')))
    if dispatch.get('event_id') not in world.event_defs: raise KeyError(dispatch.get('event_id'))
    with world.invocation(dispatch.get('scope_context',{})):
        return _run_inline_event_in_current_context(world,dispatch['event_id'],dispatch['tag'])

@contextmanager
def observe_actual_dispatch_append(world,observer):
    """Observe after a real trigger_event append with its copied scoped values.

    The observer is a test-only scheduling seam. It does not add commands,
    tokens, receipts, or queue state to the source interpreter.
    """
    previous=world._dispatch_append_observer
    if previous is not None: raise AssertionError('nested dispatch append observers are unsupported')
    world._dispatch_append_observer=observer
    try: yield
    finally: world._dispatch_append_observer=previous

@contextmanager
def observe_actual_owned_ack(world,observer,after=None):
    """Observe/intervene around the actually invoked owned ACK.

    The actual body and generated receipt/callback commands have already run
    when this seam fires. The observer may inspect or fault native state, then
    the unchanged source helper still executes if the observer returns.
    """
    if world._owned_ack_observer is not None: raise AssertionError('nested ACK observers are unsupported')
    world._owned_ack_observer=observer
    world._owned_ack_after_observer=after
    try: yield
    finally:
        world._owned_ack_observer=None
        world._owned_ack_after_observer=None

@contextmanager
def observe_actual_effect_runs(world,observer):
    """Record real named-effect invocations without replacing their bodies."""
    previous=world._effect_run_observer
    if previous is not None: raise AssertionError('nested effect-run observers are unsupported')
    world._effect_run_observer=observer
    try: yield
    finally: world._effect_run_observer=previous

def copy_actual_world_without_observers(world):
    """Copy source state without transient callbacks; run remains self-bound."""
    before=(world._dispatch_append_observer,world._owned_ack_observer,
            world._owned_ack_after_observer,world._effect_run_observer)
    world._dispatch_append_observer=None
    world._owned_ack_observer=None
    world._owned_ack_after_observer=None
    world._effect_run_observer=None
    try:
        # A generic deepcopy reconstructs list subclasses by replaying append;
        # _ScopedDispatchList.append itself records a fresh dispatch. Build a
        # shell first, then populate event rows through list.extend (the base
        # implementation) so copied pending events remain inert history.
        clone=copy.copy(world)
        events=_ScopedDispatchList.__new__(_ScopedDispatchList)
        list.__init__(events)
        memo={id(world):clone,id(world.events):events}
        clone.__dict__.update(world.__dict__)
        for name,value in world.__dict__.items():
            if name=='events':
                list.extend(events,copy.deepcopy(list(world.events),memo))
            else:
                clone.__dict__[name]=copy.deepcopy(value,memo)
        events.world=clone
        clone.events=events
        clone._dispatch_append_observer=None
        clone._owned_ack_observer=None
        clone._owned_ack_after_observer=None
        clone._effect_run_observer=None
        # A checkpoint may be taken from inside execute()/invocation() at a
        # genuine trigger_event append. The clone is a fresh standalone world,
        # not a continuation of those suspended Python frames. Frozen context
        # already lives on dispatch_contexts/events and remains untouched.
        clone._execute_depth=0
        clone._prevalidated_depth=0
        clone._explicit_context=0
        clone.scope_context={}
        clone.scope_context_stack=[]
        clone.state_scope=None; clone.pop_scope=None; clone.building_scope=None; clone.good_scope=None
    finally:
        (world._dispatch_append_observer,world._owned_ack_observer,
         world._owned_ack_after_observer,world._effect_run_observer)=before
    return clone

def source_scope_model_control_world():
    """Fresh real-source factory for documented command/guard primitive tests."""
    return _initial_world()

def choose_inline_option(world,event_id,suffix):
    event=world.event_defs[event_id]; option=next((b for k,_,b in event if k=='option' and _field(b,'name','').endswith('.'+suffix)),None)
    if option is None: raise KeyError((event_id,suffix))
    gate=_field(option,'trigger',[])
    if gate and not world.conditions(gate,TAG): raise ValueError(('option illegal',event_id,suffix))
    return world.execute([n for n in option if n[0] not in ('name','trigger','ai_chance','default_option','custom_tooltip')],TAG)

class TibInlineActualSourceControls(unittest.TestCase):
    def test_real_native_source_history_legacy_initializer_and_roots_are_positive(self):
        world,evidence=actual_tib_inline_identity_control_world()
        self.assertEqual(len(evidence['legacy_events']),6); self.assertEqual(len(evidence['roots']),3)
        self.assertEqual(len(world.triggers),len({k for p in TRIGGER_PATHS for k,_,_ in parse(_read(p))}))
    def test_native_factory_registry_isolation_and_live_root_pulse_surface(self):
        first,_=actual_tib_inline_identity_control_world(); second,_=actual_tib_inline_identity_control_world()
        self.assertIsNot(first.effects,second.effects); self.assertIsNot(first.triggers,second.triggers)
        self.assertIsNot(first.journal_defs,second.journal_defs); self.assertIsNot(first.event_defs,second.event_defs)
        first.effects['__private_registry_probe__']=[('effect',)]
        self.assertNotIn('__private_registry_probe__',second.effects)
        first.effects.pop('__private_registry_probe__',None)
        first.active[TAG]=list(je for arc in catalog()['arcs'] for je in [arc['journals'][0]['id']])
        self.assertEqual({tag for tag,_ in first.journals if tag==TAG},{TAG})
        # The public pulse seam returns actual emitted native events; it never
        # fabricates receipts and leaves delivery/body execution to callers.
        pulse_inline_journals(first)
    def test_both_ordinary_profiles_are_legal_and_source_route_distinct(self):
        for strategy in (1,2):
            w=_initial_world(strategy); state=w.countries[TAG]
            self.assertEqual(state['laws'],{'law_serfdom','law_religious_schools'})
            self.assertFalse(any(k.startswith(('ywc_','test_')) for k in state))
            for st in state['states']:
                for pop in st['pops']:
                    self.assertTrue(any(pop['workplace'] is b and b['occupancy']>0 for b in st['buildings']))
            for prefix in ('register','grain','schools'):
                self.assertTrue(w.conditions([(f'ywc_tib_{prefix}_route_{strategy}_ready','=','yes')],TAG))
                if strategy==2: self.assertFalse(w.conditions([(f'ywc_tib_{prefix}_route_1_ready','=','yes')],TAG))
            world,evidence=actual_tib_inline_identity_control_world(strategy)
            self.assertEqual(world.root_counts,[(1,1),(2,2),(3,3)])
            self.assertEqual(world.root_gates_before_initialize,[(False,False)]*3)
            self.assertEqual([world.countries[TAG][f'ywc_tib_{p}_pending_event'] for p in ('register','grain','schools')],[1000,1010,1020])
    def test_actual_membership_rejects_history_only_and_unknown_ids(self):
        w,_=actual_tib_inline_identity_control_world()
        jid=catalog()['arcs'][0]['journals'][0]['id']
        self.assertTrue(w.condition(('has_journal_entry','=',jid),TAG))
        w.active[TAG].remove(jid)
        self.assertTrue(any(_field(b,'type')==jid for _,b in w.journals))
        self.assertFalse(w.condition(('has_journal_entry','=',jid),TAG))
        for node in [('has_journal_entry','=','unknown'),('has_journal_entry','?=',jid)]:
            with self.assertRaises(AssertionError): w.condition(node,TAG)
        with self.assertRaises(AssertionError): w.execute(parse('add_journal_entry = { type = unknown }'),TAG)
    def test_scope_presence_numeric_context_and_unknown_fields_fail_closed(self):
        w=_initial_world()
        self.assertFalse(w.condition(('exists','=','scope:probe'),TAG))
        for value in (0,7):
            w.countries[TAG]['probe']=value
            w.execute(parse('save_scope_value_as = { name = probe value = var:probe }'),TAG)
            self.assertTrue(w.condition(('exists','=','scope:probe'),TAG))
            self.assertTrue(w.condition(('scope:probe','=',str(value)),TAG))
        for script in ('save_scope_value_as = { name = x value = 1 extra = 7 }',
                       'save_scope_value_as = { name = x value = nan }',
                       'set_variable = { name = x value = 1 extra = 2 }','trigger_event = { id = ywc_tib.1000 extra = 1 }','add_journal_entry = { type = unknown extra = 1 }'):
            with self.assertRaises(AssertionError): w.execute(parse(script),TAG)
        for script in ('institution_investment_level = { institution = institution_schools value >= 1 extra = 2 }',
                       'radical_fraction = { value > .2 extra = 1 }','unknown = yes','scope:x ?= 1','is_employed = maybe','has_law ?= law_serfdom'):
            with self.assertRaises(AssertionError): w.conditions(parse(script),TAG)
    def test_real_append_observer_and_copy_are_isolated_without_proof_manufacture(self):
        w,_=actual_tib_inline_identity_control_world(); seen=[]; checkpoints=[]
        def observe(current,dispatch):
            self.assertGreater(current._execute_depth,0,'checkpoint is inside actual suspended append')
            seen.append(dispatch); checkpoints.append(copy_actual_world_without_observers(current))
        with observe_actual_dispatch_append(w,observe):
            w.execute(parse('save_scope_value_as = { name = candidate value = 17 } save_scope_value_as = { name = epoch value = 3 } trigger_event = { id = ywc_tib.1000 }'),TAG)
        clone=checkpoints[0]
        self.assertEqual(seen[-1]['scope_context'],{'candidate':17.,'epoch':3.})
        self.assertIs(clone.events.world,clone); self.assertIsNone(clone._dispatch_append_observer)
        self.assertEqual((clone._execute_depth,clone._explicit_context,clone.scope_context),(0,0,{}))
        clone.countries[TAG]['states'][0]['average_sol']=99
        clone.active[TAG].clear(); clone.history[TAG].clear(); clone.days_until_expiry[TAG]['copy_only']=2
        self.assertEqual(w.countries[TAG]['states'][0]['average_sol'],8)
        self.assertTrue(w.active[TAG]); self.assertTrue(w.history[TAG]); self.assertNotIn('copy_only',w.days_until_expiry[TAG])
        before=len(w.events); clone.execute(parse('trigger_event = { id = ywc_tib.1000 }'),TAG)
        self.assertEqual(len(w.events),before); self.assertEqual(clone.dispatch_contexts[-1]['scope_context'],{})
        self.assertFalse(any('_completed_' in k or '_callback_' in k for k in clone.countries[TAG]))
    def test_actual_treasury_debit_and_shared_cooldown_execute_source(self):
        w=_initial_world(); cash=w.available_gold(TAG)
        w.execute(parse('add_treasury = -100'),TAG)
        self.assertEqual(w.available_gold(TAG),cash-100)
        w.run('ywc_v03_mark_major_delivered',TAG)
        self.assertEqual(w.days_until_expiry[TAG]['ywc_v03_major_event_cooldown'],90)
        self.assertFalse(w.conditions(parse('ywc_v03_can_deliver_major = yes'),TAG))
        w.advance_days(90)
        self.assertTrue(w.conditions(parse('ywc_v03_can_deliver_major = yes'),TAG))
    def test_inline_factory_reports_genuine_feature_red(self):
        actual_tib_inline_world()
    def test_api_surface_is_fixed_for_later_contracts(self):
        for fn in (actual_tib_inline_world,actual_tib_inline_identity_control_world,pulse_inline_journals,run_inline_event_immediate,run_queued_inline_event_immediate,choose_inline_option,observe_actual_dispatch_append,observe_actual_owned_ack,observe_actual_effect_runs,copy_actual_world_without_observers,source_scope_model_control_world): self.assertTrue(callable(fn))

    def test_full_shape_prevalidation_rejects_false_prefix_empty_scope_and_bad_referenced_trigger(self):
        w=_initial_world()
        invalid=(
            'unknown = yes',
            'has_journal_entry = unknown',
            'institution_investment_level = { institution = invalid value >= 1 }',
            'institution_investment_level = { institution != institution_schools value >= 1 }',
            'institution_investment_level = { institution = institution_schools value ?= 1 }',
            'institution_investment_level = { institution = institution_schools value >= nan }',
            'gold_reserves >= { value = 100 multiply != 2 }',
            'any_scope_state = { unknown = yes }',
            'any_scope_state = { has_journal_entry = unknown }',
            'any_scope_state = { radical_fraction = { value > .2 pop_type != laborers } }',
            'any_scope_state = { radical_fraction = { value > .2 extra = 1 } }',
            'any_scope_state = { any_scope_pop = { workplace ?= { unknown = yes } } }',
            'any_scope_state = { any_scope_building = { occupancy ?= .5 } }',
            'any_scope_state ?= { is_owned_by = ROOT }',
            'any_scope_pop = { is_employed = yes }',
            'market_capital.market = { mg:invalid = { market_goods_pricier > .2 } }',
            'market_capital.market = { mg:grain ?= { market_goods_pricier > .2 } }',
            'market_capital.market = { mg:grain = { unknown = yes } }',
            'scope:pending > nan',
        )
        for script in invalid:
            for prefix in ('','always = no ','OR = { always = yes } '):
                with self.subTest(invalid=script,prefix=prefix):
                    with self.assertRaises(AssertionError): w.conditions(parse(prefix+script),TAG)
        # No iterator body will run, yet unsupported nested grammar must fail.
        w.countries[TAG]['states']=[]
        for child in ('unknown = yes','has_journal_entry = unknown','any_scope_pop = { workplace ?= { unknown = yes } }'):
            with self.assertRaises(AssertionError): w.conditions(parse('any_scope_state = { '+child+' }'),TAG)
        w.countries[TAG]['states']=[{'owned':True,'pops':[],'buildings':[]}]
        for script in ('any_scope_state = { any_scope_pop = { unknown = yes } }',
                       'any_scope_state = { any_scope_building = { unknown = yes } }'):
            with self.assertRaises(AssertionError): w.conditions(parse(script),TAG)
        # Mutate only this fresh world's actual source trigger AST as a negative
        # grammar control. No class registry, file, registration or receipt changes.
        original=copy.deepcopy(w.trigger_defs['ywc_tib_finance_safe'])
        try:
            w.trigger_defs['ywc_tib_finance_safe'].append(('unknown','=','yes'))
            with self.assertRaises(AssertionError): w.conditions(parse('always = no ywc_tib_finance_safe = yes'),TAG)
            with self.assertRaises(AssertionError): w.conditions(parse('any_scope_state = { any_scope_pop = { ywc_tib_finance_safe = yes } }'),TAG)
        finally: w.trigger_defs['ywc_tib_finance_safe']=original
        self.assertTrue(w.conditions(parse('always = yes'),TAG))
        self.assertFalse(w.conditions(parse('always = no ywc_tib_finance_safe = yes'),TAG))

    def test_actual_native_state_command_preserves_validation_entry_scope_and_restores_context(self):
        w=_initial_world()
        # Exact real source node, outside the route's payment/story gate. This
        # is a native scoped-command primitive control, not route acceptance.
        native=next(node for node in _field(w.effects['ywc_tib_choose_grain_3'],'if') if node[0]=='every_scope_state')
        self.assertEqual(_field(native[2],'limit'),[('is_owned_by','=','ROOT')])
        expected=dict((k,v) for k,_,v in _field(native[2],'add_modifier'))
        w.countries[TAG]['states'].append({'owned':False,'pops':[],'buildings':[]})
        before=len(w.modifiers); initial=w._scope_checkpoint()
        w.execute([native],TAG)
        self.assertEqual(w.modifiers[before:],[(TAG,expected)],'actual native body executed once for the owned modeled state')
        self.assertEqual(w._scope_checkpoint(),initial)
        state=w.countries[TAG]['states'][0]; w.state_scope=state
        limit=_field(native[2],'limit')
        self.assertTrue(w.conditions(limit,TAG)); self.assertTrue(w.condition(limit[0],TAG))
        self.assertIs(w.state_scope,state)
        w.execute([native],TAG); self.assertIs(w.state_scope,state)
        # Direct public entries preserve the other actually modeled contexts,
        # too; each is restored before returning to its enclosing state.
        pop=state['pops'][0]; w.pop_scope=pop
        self.assertTrue(w.condition(('is_employed','=','yes'),TAG))
        self.assertTrue(w.conditions([('is_employed','=','yes')],TAG))
        w.building_scope=pop['workplace']
        building=('is_building_type','=',pop['workplace']['type'])
        self.assertTrue(w.condition(building,TAG)); self.assertTrue(w.conditions([building],TAG))
        w.building_scope=None; w.pop_scope=None; w.good_scope='grain'
        self.assertTrue(w.condition(('market_goods_pricier','>','.25'),TAG))
        self.assertTrue(w.conditions([('market_goods_pricier','>','.25')],TAG))
        w.good_scope=None; w.state_scope=None
        with self.assertRaises(AssertionError): w.condition(limit[0],TAG)
        with self.assertRaises(AssertionError): w.conditions(limit,TAG)
        self.assertEqual(w._scope_checkpoint(),initial)
    def test_state_entry_prevalidation_rejects_false_empty_and_exception_paths_without_scope_leaks(self):
        w=_initial_world(); state=w.countries[TAG]['states'][0]
        native=next(node for node in _field(w.effects['ywc_tib_choose_grain_3'],'if') if node[0]=='every_scope_state')
        bad=('unknown = yes','has_journal_entry = unknown',
             'institution_investment_level = { institution = invalid value >= 1 }',
             'any_scope_pop = { workplace ?= { unknown = yes } }')
        for script in bad:
            predicates=parse('always = no '+script)
            w.state_scope=state; expected=w._scope_checkpoint()
            with self.subTest(state_entry=script):
                with self.assertRaises(AssertionError): w.conditions(predicates,TAG)
                with self.assertRaises(AssertionError): w.condition(('AND','=',predicates),TAG)
                self.assertEqual(w._scope_checkpoint(),expected)
            w.state_scope=None
            malformed=(native[0],native[1],[(k,o,predicates if k=='limit' else v) for k,o,v in native[2]])
            for states in ([state],[]):
                with self.subTest(command_limit=script,empty=not states):
                    w.countries[TAG]['states']=states
                    with self.assertRaises(AssertionError): w.execute([malformed],TAG)
                    self.assertEqual(w._scope_checkpoint(),(None,None,None,None))
        w.countries[TAG]['states']=[state]
        # A real scoped command's failing unsupported body must also unwind the
        # base's transient state pointer. No extra scoped command is introduced.
        bad_body=(native[0],native[1],[native[2][0],('unsupported_command','=','yes')])
        with self.assertRaises(AssertionError): w.execute([bad_body],TAG)
        self.assertEqual(w._scope_checkpoint(),(None,None,None,None))
        # Runtime errors in an already grammar-valid nested predicate likewise
        # restore state/pop context and the prevalidation depth.
        w.state_scope=state; expected=w._scope_checkpoint()
        runtime=parse('any_scope_pop = { gold_reserves >= var:missing_cash_reference }')
        with self.assertRaises(AssertionError): w.conditions(runtime,TAG)
        self.assertEqual(w._scope_checkpoint(),expected); self.assertEqual(w._prevalidated_depth,0)
        w.state_scope=None; w.countries[TAG]['states']=[]
        before=len(w.modifiers); w.execute([native],TAG)
        self.assertEqual(len(w.modifiers),before); self.assertEqual(w._scope_checkpoint(),(None,None,None,None))

if __name__=='__main__': unittest.main()

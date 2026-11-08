"""Self-contained JHG authored-source world factory for inline adapter contracts.

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
from tests import test_v03_jhg_foundation as foundation
from tests.test_v03_jhg_inline_adapter import (_v2_catalog_from_formal_jhg_source,
    assert_inline_supported, catalog)
from tools import build_v03_content
from tools.v03_inline_delivery_adapter import render_inline_country_adapters, validate_inline_catalog

ROOT=Path(__file__).resolve().parents[1]; TAG='JHG'
STARTS='yongchang_world/common/history/countries/ywc_content_starts.txt'
EVENT_PATHS=('yongchang_world/events/ywc_shu_jhg_events.txt','yongchang_world/events/ywc_large_campaign_events.txt','yongchang_world/events/ywc_v03_country_jhg_events.txt')
JOURNAL_PATHS=('yongchang_world/common/journal_entries/ywc_jhg.txt','yongchang_world/common/journal_entries/ywc_v03_country_jhg_journal.txt','yongchang_world/common/journal_entries/ywc_shared_journal.txt','yongchang_world/common/journal_entries/ywc_large_campaign_crises.txt')
EFFECT_PATHS=('yongchang_world/common/scripted_effects/ywc_v03_jhg_effects.txt','yongchang_world/common/scripted_effects/ywc_v03_effects.txt','yongchang_world/common/scripted_effects/ywc_shared_effects.txt','yongchang_world/common/scripted_effects/ywc_campaign_effects.txt','yongchang_world/common/scripted_effects/ywc_flavor_effects.txt')
TRIGGER_PATHS=('yongchang_world/common/scripted_triggers/ywc_v03_triggers.txt','yongchang_world/common/scripted_triggers/ywc_v03_jhg_triggers.txt')
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

class _ActualJhgWorld(foundation.JhgTerminalWorld):
    def __init__(self,effects,countries,known_journals):
        self.known_journals=known_journals
        super().__init__(effects,countries)
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
        owned=isinstance(name,str) and name.startswith('ywc_v03_jhg_inline_ack_')
        if owned and self._owned_ack_observer is not None:
            self._owned_ack_observer(self,name,tag)
        result=super().run(name,tag)
        if owned and self._owned_ack_after_observer is not None:
            self._owned_ack_after_observer(self,name,tag)
        return result
    def condition(self,node,tag):
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
        if key.startswith('ig:'):
            if comparison!='?=' or not isinstance(value,list) or len(value)!=1 or value[0][0]!='is_powerful' or value[0][1]!='=' or value[0][2] not in ('yes','no'):
                raise AssertionError(('unsupported interest-group predicate',node))
            fact=key.split(':',1)[1].removeprefix('ig_')
            actual=bool(self.countries[tag].get('engine_interest_groups',{}).get(fact,self.countries[tag].get('engine_powerful_'+fact,False)))
            return actual==(value[0][2]=='yes')
        if key.startswith('c:'):
            if comparison!='?=' or value!='this': raise AssertionError(('unsupported country optional predicate',node))
            return super().condition(node,tag)
        if comparison=='?=':
            known=('ywc_jhg_court_withdrawn','ywc_jhg_convoy_withdrawn','ywc_jhg_tribute_withdrawn')
            if key not in known or value not in ('yes','no'): raise AssertionError(('unsupported optional predicate',node))
            return bool(self.countries[tag].get(key,False))==(value=='yes')
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
            return foundation.JhgTerminalWorld._compare(left,comparison,right)
        return super().condition(node,tag)
    def available_gold(self,tag):
        return float(self.countries[tag].get('gold_reserves',0))+float(self.treasury.get(tag,0))
    def execute(self,nodes,tag):
        for key,_,value in nodes:
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
                    if pending: PulseWorld.execute(self,pending,tag); pending=[]
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
                    else:
                        try: actual=float(raw)
                        except (TypeError,ValueError):
                            if raw not in ('yes','no'): raise AssertionError(('unsupported scoped numeric value',raw))
                            actual=raw=='yes'
                    self.scope_context[name]=actual
                else: pending.append(node)
            if pending: return PulseWorld.execute(self,pending,tag)
        finally:
            self._execute_depth-=1

def _initial_world():
    effects='\n'.join(_read(p) for p in EFFECT_PATHS)
    state={'yearly_gross_income':52000,'gold_reserves':20000,'net_fixed_income':1000,'bureaucracy':80,
      'government_legitimacy':65,'navy_size':10,'engine_is_subject':True,
      'engine_laws':['law_merchant_navy','law_landed_voting'],
      'engine_interest_groups':{'industrialists':True,'landowners':True},'engine_diplomatic_pacts':['alliance'],
      'engine_overlord':{'relations':70},'engine_partners':[{'diplomatic_pacts':['alliance'],'relations_to_root':70,'army_size':12,'gold_reserves':10000}],
      'engine_states':[{'owned_by_root':True,'buildings':[{'type':'building_government_administration','occupancy':.95,'goods_shortage':False},{'type':'building_port','occupancy':.95,'goods_shortage':False}]}]}
    journals=_defs(JOURNAL_PATHS); world=_ActualJhgWorld(effects,{TAG:state},set(journals))
    world.journal_defs=journals; world.event_defs=_defs(EVENT_PATHS); world.finished_journals=set()
    triggers='\n'.join(_read(p) for p in TRIGGER_PATHS)
    world.triggers={k:b for k,_,b in parse(triggers)}
    # Native identity registries come from raw catalog business AST through the
    # real bare builder, even when committed JHG files later contain wrappers.
    native_catalog=catalog()
    native_journals=_script_defs(build_v03_content._render_journal_file(native_catalog,None),'native journals')
    native_events=_script_defs(build_v03_content._render_event_file(native_catalog,ROOT,None),'native events')
    for arc in native_catalog['arcs']:
        for je in arc['journals']: world.journal_defs[je['id']]=native_journals[je['id']]
        for event in arc['events']: world.event_defs[event['id']]=native_events[event['id']]
    return world

def _run_legacy_and_initialize(world):
    starts=parse(_read(STARTS)); countries=_field(starts,'COUNTRIES',[])
    scope=next((n for n in countries if n[0]=='c:JHG'),None)
    if scope is None or scope[1]!='?=': raise AssertionError('real JHG country history missing')
    world.execute([scope],TAG)
    old_id='ywc_je_flavor_jhg_convoy_1'
    if not world.journal_is_active(TAG,old_id): raise AssertionError(('history did not add legacy JE',old_id))
    old=world.journal_defs[old_id]; expected=['ywc_jhg.6','ywc_jhg.100','ywc_jhg.101','ywc_jhg.102','ywc_jhg.103','ywc_jhg.104']
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
    world.finish_journal(TAG,{'id':old_id})
    world.run('ywc_v03_initialize_country',TAG)
    return trace

def _admit_roots(world):
    rows=[]; world.active_journals=set()
    for arc in catalog()['arcs']:
        je=arc['journals'][0]; body=world.journal_defs[je['id']]
        shown=_field(body,'is_shown_when_inactive',[]); possible=_field(body,'possible',[])
        if not world.conditions(shown,TAG) or not world.conditions(possible,TAG): raise AssertionError(('root gates false',je['id']))
        world.execute(_field(body,'immediate',[]),TAG); world.journals.append((TAG,[('type','=',je['id'])]))
        rows.append(je['id']); world.active_journals.add(je['id'])
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
    for label, additions, target in (('effect',fx,world.effects),('trigger',trg,world.triggers)):
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

def actual_jhg_inline_identity_control_world():
    world=_initial_world(); legacy=_run_legacy_and_initialize(world); roots=_admit_roots(world)
    return world,{'legacy_events':legacy,'roots':roots}

def actual_jhg_inline_world():
    """Install actual generated registries before source history and root admission."""
    candidate=_v2_catalog_from_formal_jhg_source()
    try:
        validate_inline_catalog(candidate)
        rendered=render_inline_country_adapters(candidate)
    except ValueError as exc:
        if 'inline adapter is currently enabled only for registered inline countries' in str(exc):
            raise AssertionError(f'JHG inline adapter feature is not registered: {exc}') from exc
        raise
    if len(rendered.get('event_hooks',{}))!=24: raise AssertionError('generated adapter must guard all 24 events')
    world=_initial_world(); _install_rendered_registries(world,candidate,rendered)
    legacy=_run_legacy_and_initialize(world); roots=_admit_roots(world)
    return world,{'legacy_events':legacy,'roots':roots}

def pulse_inline_journals(world):
    """Pulse each live native JE once; reconcile terminals and admit via authored gates."""
    if not hasattr(world,'active_journals'): world.active_journals=set()
    emitted=[]
    for jid in list(world.active_journals):
        je=world.journal_defs[jid]
        complete=world.conditions(_field(je,'complete',[]),TAG); failed=world.conditions(_field(je,'fail',[]),TAG)
        if complete and failed: raise AssertionError(('JE both complete and failed',jid))
        if complete or failed:
            hook='on_fail' if failed else 'on_complete'
            if _field(je,hook,[]): world.execute(_field(je,hook),TAG)
            world.finish_journal(TAG,{'id':jid}); world.active_journals.remove(jid)
    for arc in catalog()['arcs']:
        for candidate in arc['journals']:
            jid=candidate['id']
            if jid in world.active_journals or world.is_finished(TAG,jid): continue
            je=world.journal_defs[jid]
            if world.conditions(_field(je,'is_shown_when_inactive',[]),TAG) and world.conditions(_field(je,'possible',[]),TAG):
                if not world.journal_is_active(TAG,jid): world.journals.append((TAG,[('type','=',jid)]))
                world.execute(_field(je,'immediate',[]),TAG); world.active_journals.add(jid)
                break
    for jid in sorted(world.active_journals):
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
        clone._explicit_context=0
        clone.scope_context={}
        clone.scope_context_stack=[]
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

class JhgInlineActualSourceControls(unittest.TestCase):
    def test_real_native_source_history_legacy_initializer_and_roots_are_positive(self):
        world,evidence=actual_jhg_inline_identity_control_world()
        self.assertEqual(len(evidence['legacy_events']),6); self.assertEqual(len(evidence['roots']),3)
        self.assertEqual(len(world.triggers),len({k for p in TRIGGER_PATHS for k,_,_ in parse(_read(p))}))
    def test_native_factory_registry_isolation_and_live_root_pulse_surface(self):
        first,_=actual_jhg_inline_identity_control_world(); second,_=actual_jhg_inline_identity_control_world()
        self.assertIsNot(first.effects,second.effects); self.assertIsNot(first.triggers,second.triggers)
        self.assertIsNot(first.journal_defs,second.journal_defs); self.assertIsNot(first.event_defs,second.event_defs)
        first.effects['__private_registry_probe__']=[('effect',)]
        self.assertNotIn('__private_registry_probe__',second.effects)
        first.effects.pop('__private_registry_probe__',None)
        first.active_journals=set(je for arc in catalog()['arcs'] for je in [arc['journals'][0]['id']])
        self.assertEqual({tag for tag,_ in first.journals if tag==TAG},{TAG})
        # The public pulse seam returns actual emitted native events; it never
        # fabricates receipts and leaves delivery/body execution to callers.
        pulse_inline_journals(first)
    def test_inline_factory_reports_genuine_feature_red(self):
        actual_jhg_inline_world()
    def test_api_surface_is_fixed_for_later_contracts(self):
        for fn in (actual_jhg_inline_world,actual_jhg_inline_identity_control_world,pulse_inline_journals,run_inline_event_immediate,choose_inline_option): self.assertTrue(callable(fn))

if __name__=='__main__': unittest.main()

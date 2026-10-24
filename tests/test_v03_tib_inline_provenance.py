"""TIB source/body transactions over real source and genuinely admitted phases.

The isolated branch seam changes only an else_if entry into an if entry; its
limit, native pre, trigger and complete continuation remain actual source.
Queue/marker inputs are controlled fault-model inputs, never story progress.
Body-first means complete B inside the append observer, with source suspended;
no player option executes there. B's permanent story remains the monthly oracle.
"""
from __future__ import annotations

import copy
import unittest
from functools import lru_cache

from tests import test_v03_tib_inline_actual_source as actual
from tests import test_v03_tib_inline_adapter as source
from tests.test_v03_tib_inline_native_story import Story, public_projection

TAG = 'TIB'
PREFIX = 'ywc_v03_tib_inline'
COOLDOWN = 'ywc_v03_major_event_cooldown'
ORDERS = ('source_first', 'body_first')
ABSENT = None


@lru_cache(maxsize=1)
def all_bindings():
    """All ordered source sites, retaining formal chain and prior identity."""
    rows = []
    for arc in source._v2_catalog_from_formal_tib_source()['arcs']:
        for branch in arc['inline_delivery_adapter']['branches']:
            if len(branch['candidates']) != 1:
                raise AssertionError(('one exact TIB candidate required', branch))
            rows.append({'id': len(rows)+1, 'arc': arc, 'branch': branch,
                         'candidate': branch['candidates'][0]})
    return rows


@lru_cache(maxsize=1)
def phase_ids():
    return tuple(dict.fromkeys(r['branch']['journal'] for r in all_bindings()))


@lru_cache(maxsize=1)
def native_names():
    queues = {r['candidate']['queue'] for r in all_bindings()}
    markers = {q.removesuffix('_notice_12_event')+'_notice_last_delivered'
               for q in queues if q.endswith('_notice_12_event')}
    return tuple(sorted(queues | markers))


def pv(mapping, name):
    return name in mapping, copy.deepcopy(mapping.get(name))


def native_snapshot(world):
    return public_projection(world)


def full_snapshot(world):
    return {'native': native_snapshot(world),
        'private': {k: copy.deepcopy(v) for k,v in world.countries[TAG].items()
                    if k.startswith(PREFIX+'_')},
        'days': copy.deepcopy(world.days_until_expiry[TAG]),
        'months': copy.deepcopy(world.months_until_expiry[TAG])}


def field(nodes, key, default=None):
    return actual._field(nodes,key,default)


def walk(nodes):
    for node in nodes:
        yield node
        if isinstance(node[2],list):
            yield from walk(node[2])


def pulse(world, journal):
    return field(field(world.journal_defs[journal],'on_monthly_pulse',[]),'effect',[])


def source_node(world, row):
    """Resolve repeated preferred/fallback sites by authored occurrence order.

    A independently contracts typed whole source/chain preservation. Here the
    actual runtime list is resolved structurally, preserving both occurrences
    of the same queue/event instead of reducing to an event ID.
    """
    b = row['branch']; c = row['candidate']
    def matches(node):
        return (node[0] in ('if','else_if') and isinstance(node[2],list)
            and field(field(node[2],'trigger_event',[]),'id') == b['event']
            and any(k == 'var:'+c['queue'] and op == '=' and str(v)==str(c['value'])
                    for k,op,v in walk(field(node[2],'limit',[]))))
    found = [n for n in pulse(world,b['journal']) if matches(n)]
    peers = [r for r in all_bindings() if r['branch']['journal']==b['journal']
             and r['branch']['event']==b['event'] and r['candidate']==c]
    if len(found)!=len(peers):
        raise AssertionError(('exact source occurrence cardinality',row['id'],len(found),len(peers)))
    return found[[r['id'] for r in peers].index(row['id'])]


def branch_unit(node):
    if node[0] not in ('if','else_if'):
        raise AssertionError(('not an authored sender',node))
    return ('if',node[1],node[2])


def witness(row):
    return next(p['live_witness'] for p in row['arc']['inline_delivery_adapter']['live_phases']
                if p['journal']==row['branch']['journal'])


def _collect_phases(testcase, inline):
    """Observe actual monthly helpers/prepare during the accepted complete Story.

    A method override adds observation only; the original Story observer and
    common driver still execute. No progress/active membership is injected.
    """
    checkpoints = {}
    class CaptureStory(Story):
        def effect_run(self,world,name,tag):
            super().effect_run(world,name,tag)
            eligible = (name.startswith(PREFIX+'_') and name.endswith('_prepare')) if inline else name in {
                f'ywc_tib_{p}_monthly_review' for p in ('register','grain','schools')}
            if not eligible: return
            for row in all_bindings():
                jid = row['branch']['journal']
                if not inline and name != 'ywc_tib_'+jid.removeprefix('ywc_je_v03_tib_').rsplit('_',1)[0]+'_monthly_review':
                    continue
                if jid in checkpoints or jid not in world.active[TAG]: continue
                if inline and world.countries[TAG].get(witness(row)) != 1: continue
                if inline and PREFIX+'_reservation' in world.countries[TAG]: continue
                testcase.assertEqual(world.history[TAG][jid],'active')
                testcase.assertFalse(world.conditions(field(world.journal_defs[jid],'complete',[]),TAG))
                testcase.assertFalse(world.conditions(field(world.journal_defs[jid],'fail',[]),TAG))
                checkpoints[jid] = actual.copy_actual_world_without_observers(world)
    CaptureStory(testcase,1,inline).run()
    testcase.assertEqual(set(checkpoints),set(phase_ids()),'six genuinely admitted phase checkpoints')
    return checkpoints


@lru_cache(maxsize=2)
def _cached_phases(inline):
    return _collect_phases(unittest.TestCase(),inline)


def phase_worlds(testcase, inline=False):
    result = _cached_phases(inline)
    testcase.assertEqual(set(result),set(phase_ids()))
    return result


def assign_native_inputs(world,row,inputs=None):
    """Explicit isolated queue/marker fault inputs, not a naturally scheduled JE."""
    state=world.countries[TAG]
    for name in native_names(): state.pop(name,None)
    state[row['candidate']['queue']]=row['candidate']['value']
    if row['candidate']['kind']=='notice12':
        # Exact preferred/fallback predicate context is retained, not disabled.
        marker=row['candidate']['queue'].removesuffix('_notice_12_event')+'_notice_last_delivered'
        if row['branch']['branch_index']==2: state[marker]=1
    if inputs:
        for name,value in inputs.items():
            if name not in native_names(): raise AssertionError(('not a native fault input',name))
            if value is ABSENT: state.pop(name,None)
            else: state[name]=value


def fresh_case(testcase,row,inline=True,inputs=None):
    phase=phase_worlds(testcase,inline)[row['branch']['journal']]
    world=actual.copy_actual_world_without_observers(phase)
    # Actual elapsed time, never direct cooldown deletion or lease removal.
    world.advance_days(91)
    assign_native_inputs(world,row,inputs)
    testcase.assertIn(row['branch']['journal'],world.active[TAG])
    if inline:
        testcase.assertEqual(world.countries[TAG].get(witness(row)),1)
        testcase.assertNotIn(PREFIX+'_reservation',world.countries[TAG])
    return world


def bare_oracle_with_business(world):
    """Separate bare-builder world with matching business inputs before dispatch.

    Generated registries are never replaced after wrapping. This fresh native
    world receives only business state, actual membership/history and clocks.
    """
    raw=actual._initial_world()
    public=native_snapshot(world)
    raw.countries[TAG]=copy.deepcopy(public['country'])
    raw.treasury[TAG]=public['treasury']; raw.modifiers=copy.deepcopy(public['modifiers'])
    raw.days_until_expiry[TAG]=copy.deepcopy(public['days'])
    raw.months_until_expiry[TAG]=copy.deepcopy(public['months'])
    raw.active[TAG]=list(public['active']); raw.history[TAG]=dict(public['history'])
    raw.journals=copy.deepcopy(world.journals)
    return raw


def native_oracle(testcase,world,row,chain=False):
    raw=bare_oracle_with_business(world)
    nodes=[n for n in pulse(raw,row['branch']['journal']) if n[0] in ('if','else_if','else')] if chain else [branch_unit(source_node(raw,row))]
    captured=[]
    with actual.observe_actual_dispatch_append(raw,lambda w,d: captured.append(copy.deepcopy(d))):
        raw.execute(nodes,TAG)
    testcase.assertLessEqual(len(captured),1,'single authored sender chain')
    for dispatch in captured: actual.run_queued_inline_event_immediate(raw,dispatch)
    return raw,captured


def helper(kind,ident):
    return f'{PREFIX}_{kind}_{ident}'


def run_frozen(world,dispatch,name):
    with world.invocation(dispatch['scope_context']): world.run(name,TAG)


def epoch_of(testcase,dispatch,ident):
    context=dispatch['scope_context']
    testcase.assertEqual(context.get(PREFIX+'_dispatch_candidate'),ident)
    epoch=context.get(PREFIX+'_dispatch_epoch')
    testcase.assertIsInstance(epoch,(int,float)); testcase.assertNotIsInstance(epoch,bool)
    testcase.assertGreater(epoch,0)
    return epoch


def receipt_names(ident):
    return tuple(helper(k,ident) for k in ('source_completed','source_completed_epoch',
        'body_completed','body_completed_epoch'))


def callback_names(ident):
    return tuple(helper(k,ident) for k in ('callback','callback_candidate','callback_epoch','callback_queue'))


def dispatch_source(testcase,world,row,order='source_first',*,at_append=None,
                    before_effect=None,before_ack=None,after_ack=None,chain=False):
    """Actual source execution with observable seams; no synthetic receipts."""
    observed=[]; ack=[]; effects=[]; append_states=[]
    def appended(current,dispatch):
        observed.append(copy.deepcopy(dispatch)); append_states.append(full_snapshot(current))
        if at_append: at_append(current,dispatch)
        if order=='body_first':
            actual.run_queued_inline_event_immediate(current,dispatch)
            ident=int(dispatch['scope_context'][PREFIX+'_dispatch_candidate'])
            epoch=epoch_of(testcase,dispatch,ident); state=current.countries[TAG]
            testcase.assertEqual(state.get(helper('body_completed',ident)),1)
            testcase.assertEqual(state.get(helper('body_completed_epoch',ident)),epoch)
            testcase.assertNotIn(helper('source_completed',ident),state)
            testcase.assertNotIn(helper('source_completed_epoch',ident),state)
            testcase.assertEqual(ack,[],'body-first B cannot ACK before real source continuation')
    def effect(current,name,tag):
        effects.append(name)
        if before_effect: before_effect(current,name,tag)
    def preack(current,name,tag):
        if before_ack: before_ack(current,name,tag)
        ack.append(('before',full_snapshot(current)))
    def postack(current,name,tag):
        ack.append(('after',full_snapshot(current)))
        if after_ack: after_ack(current,name,tag)
    with actual.observe_actual_dispatch_append(world,appended), actual.observe_actual_effect_runs(world,effect), actual.observe_actual_owned_ack(world,preack,postack):
        world.run(PREFIX+'_prepare',TAG)
        nodes=[n for n in pulse(world,row['branch']['journal']) if n[0] in ('if','else_if','else')] if chain else [branch_unit(source_node(world,row))]
        if not chain: testcase.assertTrue(world.conditions(field(nodes[0][2],'limit',[]),TAG),(row['id'],'actual isolated branch admission'))
        world.execute(nodes,TAG)
    return {'world':world,'dispatches':observed,'append_states':append_states,'ack':ack,'effects':effects}


def complete_case(testcase,row,order,*,inputs=None,chain=False):
    world=fresh_case(testcase,row,True,inputs)
    expected,oracle_dispatch=native_oracle(testcase,world,row,chain)
    def before_body(current,dispatch):
        if order!='body_first': return
        ident=dispatch['scope_context'].get(PREFIX+'_dispatch_candidate')
        testcase.assertIsInstance(ident,(int,float))
        testcase.assertNotIn(helper('source_boundary',int(ident)),current.countries[TAG])
        testcase.assertNotIn(helper('source_boundary_epoch',int(ident)),current.countries[TAG])
        testcase.assertNotIn(helper('source_completed',int(ident)),current.countries[TAG])
        testcase.assertNotIn(helper('body_completed',int(ident)),current.countries[TAG])
    result=dispatch_source(testcase,world,row,order,chain=chain,at_append=before_body)
    testcase.assertEqual([d['event_id'] for d in result['dispatches']],
                         [d['event_id'] for d in oracle_dispatch])
    if not oracle_dispatch:
        testcase.assertEqual(native_snapshot(world),native_snapshot(expected)); return result
    testcase.assertEqual(len(result['dispatches']),1)
    dispatch=result['dispatches'][0]
    if chain:
        peers=[r for r in all_bindings() if r['branch']['journal']==row['branch']['journal']
               and r['id']==dispatch['scope_context'].get(PREFIX+'_dispatch_candidate')]
        testcase.assertEqual(len(peers),1); row=peers[0]
    ident=row['id']; queue=row['candidate']['queue']; state=world.countries[TAG]
    epoch=epoch_of(testcase,dispatch,ident)
    result.update(row=row,dispatch=dispatch,epoch=epoch,oracle=expected)
    append=result['append_states'][0]['native']['country']
    testcase.assertEqual(append[queue],row['candidate']['value'],'selected clear deferred through P')
    if order=='source_first':
        testcase.assertEqual(state.get(helper('source_completed',ident)),1)
        testcase.assertEqual(state.get(helper('source_completed_epoch',ident)),epoch)
        testcase.assertNotIn(helper('body_completed',ident),state)
        testcase.assertNotIn(COOLDOWN,world.days_until_expiry[TAG])
        testcase.assertEqual(native_snapshot(world),result['append_states'][0]['native'],
            'actual complete source return is identity R(P)=P before B')
        with actual.observe_actual_effect_runs(world,lambda w,n,t: result['effects'].append(n)), actual.observe_actual_owned_ack(world,
                lambda w,n,t: result['ack'].append(('before',full_snapshot(w))),
                lambda w,n,t: result['ack'].append(('after',full_snapshot(w)))):
            actual.run_queued_inline_event_immediate(world,dispatch)
    for name,value in zip(receipt_names(ident),(1,epoch,1,epoch)):
        testcase.assertEqual(state.get(name),value,(ident,name))
    for name,value in zip(callback_names(ident),(1,ident,epoch,row['candidate']['value'])):
        testcase.assertEqual(state.get(name),value,(ident,name))
    testcase.assertNotIn(queue,state); testcase.assertNotIn(PREFIX+'_reservation',state)
    testcase.assertEqual([s for s,_ in result['ack']],['before','after'])
    before=result['ack'][0][1]['native']; after=result['ack'][1][1]['native']
    # ACK's entire native mutation is precisely the selected queue clear.
    cleared=copy.deepcopy(before); cleared['country'].pop(queue)
    testcase.assertEqual(cleared,after)
    testcase.assertEqual(native_snapshot(world),native_snapshot(expected),
        (ident,order,'full native source+full B oracle including treasury/timers'))
    testcase.assertEqual(world.days_until_expiry[TAG].get(COOLDOWN),90)
    testcase.assertEqual(result['effects'].count('ywc_v03_mark_major_delivered'),1)
    return result


def supported(testcase):
    # Always first in future cases: no generated fixture is attempted before
    # this exact public unsupported-country assertion.
    return source.assert_inline_supported(testcase)


class TibNativeProvenanceControls(unittest.TestCase):
    def test_ordered_58_rows_six_phases_18_notice_sites_and_identity_post(self):
        rows=all_bindings()
        self.assertEqual(len(rows),58); self.assertEqual(len(phase_ids()),6)
        self.assertEqual([sum(r['candidate']['kind']==k for r in rows) for k in ('normal','notice12','notice36')],[40,12,6])
        self.assertEqual(len(native_names()),12)
        self.assertEqual(len({r['candidate']['queue'] for r in rows}),9)
        world=actual._initial_world()
        for r in rows:
            with self.subTest(site=r['id']):
                b=r['branch']; node=source_node(world,r); body=node[2]
                position=next(i for i,n in enumerate(body) if n[0]=='trigger_event')
                self.assertEqual(body[position+1:],[],'all TIB R(P)=P')
                self.assertEqual(b['branch_kind'],node[0])
                self.assertTrue(b['branch_sha256']); self.assertTrue(b['limit_sha256']); self.assertTrue(b['chain_sha256'])
                self.assertEqual(b['statement_ordinal'],b['branch_index']+1)
                if r['candidate']['kind'].startswith('notice'):
                    writes=[n for n in body[:position] if n[0]=='set_variable']
                    self.assertEqual(len(writes),1)
                    self.assertEqual(field(writes[0][2],'value'),'1' if r['candidate']['kind']=='notice12' else '2')
        self.assertEqual(len({r['branch']['event'] for r in rows if r['candidate']['kind'].startswith('notice')}),6)
        self.assertEqual(len({(r['branch']['journal'],r['branch']['statement_ordinal'],r['branch']['chain_index']) for r in rows}),58)

    def test_native_six_phase_checkpoints_descend_from_complete_accepted_story(self):
        phases=phase_worlds(self)
        for jid,w in phases.items():
            self.assertIn(jid,w.active[TAG]); self.assertEqual(w.history[TAG][jid],'active')
            self.assertEqual(w.countries[TAG]['laws'],{'law_serfdom','law_religious_schools'})
            self.assertEqual(w._execute_depth,0); self.assertEqual(w.scope_context,{})
            self.assertFalse(any(k.startswith(PREFIX+'_') for k in w.countries[TAG]))

    def test_native_all_58_isolated_source_and_full_body_oracles(self):
        for row in all_bindings():
            with self.subTest(site=row['id']):
                w=fresh_case(self,row,False); raw,dispatches=native_oracle(self,w,row)
                self.assertEqual([d['event_id'] for d in dispatches],[row['branch']['event']])
                self.assertNotIn(row['candidate']['queue'],raw.countries[TAG])
                self.assertEqual(raw.days_until_expiry[TAG][COOLDOWN],90)
                self.assertEqual(raw.treasury[TAG],w.treasury[TAG],'B is not a player route option')

    def test_native_suspended_copy_frozen_context_and_exception_isolation(self):
        w,_=actual.actual_tib_inline_identity_control_world(); seen=[]
        def observe(current,dispatch):
            self.assertGreater(current._execute_depth,0)
            clone=actual.copy_actual_world_without_observers(current)
            self.assertEqual(clone._execute_depth,0); self.assertEqual(clone.scope_context,{})
            self.assertIs(clone.events.world,clone)
            self.assertIsNone(clone._dispatch_append_observer)
            clone.countries[TAG]['native_copy_control']=7
            self.assertNotIn('native_copy_control',current.countries[TAG])
            seen.append(clone)
        with actual.observe_actual_dispatch_append(w,observe): actual.pulse_inline_journals(w)
        self.assertEqual(len(seen),3)
        with self.assertRaisesRegex(RuntimeError,'scope control'):
            with w.invocation({'control':9}):
                self.assertEqual(w.scope_context,{'control':9}); raise RuntimeError('scope control')
        self.assertEqual(w.scope_context,{})

    def test_native_actual_save_scope_value_freezes_payload_without_ambient_leak(self):
        w,_=actual.actual_tib_inline_identity_control_world()
        row=representative_rows()[0]; fee='ywc_tib_register_fee'
        observed=[]
        def at_append(current,dispatch):
            self.assertEqual(dispatch['scope_context']['native_model_control'],current.countries[TAG][fee])
            clone=actual.copy_actual_world_without_observers(current)
            self.assertEqual(clone.scope_context,{})
            self.assertEqual(clone.dispatch_contexts[-1]['scope_context'],dispatch['scope_context'])
            dispatch['scope_context']['native_model_control']=999
            self.assertEqual(current.dispatch_contexts[-1]['scope_context']['native_model_control'],100)
            observed.append(clone)
        with w.invocation({}),actual.observe_actual_dispatch_append(w,at_append):
            w.execute([('save_scope_value_as','=',[('name','=','native_model_control'),('value','=','var:'+fee)])],TAG)
            w.execute([branch_unit(source_node(w,row))],TAG)
        self.assertEqual(len(observed),1); self.assertEqual(w.scope_context,{})


class TibInlineProvenance(unittest.TestCase):
    def test_source_boundary_r_equals_p_never_reopens_after_actual_return(self):
        supported(self)
        for jid in phase_ids():
          row=next(r for r in all_bindings() if r['branch']['journal']==jid and r['candidate']['kind']=='normal')
          for fault in ('delete_receipt','wrong_receipt_epoch','boundary_only','boundary_epoch_only','wrong_boundary_epoch'):
            with self.subTest(phase=jid,fault=fault):
                w=fresh_case(self,row); result=dispatch_source(self,w,row)
                d=result['dispatches'][0]; ident=row['id']; state=w.countries[TAG]; epoch=epoch_of(self,d,ident)
                self.assertEqual(state.get(helper('source_boundary',ident)),ident)
                self.assertEqual(state.get(helper('source_boundary_epoch',ident)),epoch)
                self.assertEqual(state.get(helper('source_completed',ident)),1)
                if fault=='delete_receipt': state.pop(helper('source_completed',ident))
                elif fault=='wrong_receipt_epoch': state[helper('source_completed_epoch',ident)]=epoch+1
                elif fault=='boundary_only': state.pop(helper('source_boundary_epoch',ident)); state.pop(helper('source_completed',ident))
                elif fault=='boundary_epoch_only': state.pop(helper('source_boundary',ident)); state.pop(helper('source_completed',ident))
                else:
                    state[helper('source_boundary_epoch',ident)]=epoch+1
                    self.assertEqual(state.get(helper('source_completed',ident)),1)
                    self.assertEqual(state.get(helper('source_completed_epoch',ident)),epoch)
                    self.assertEqual(state.get(helper('source_boundary_epoch',ident)),epoch+1)
                before=full_snapshot(w)
                # Full registered event must reject at trigger or guard B.
                reject_or_inert_body(self,w,d)
                self.assertEqual(full_snapshot(w),before)
                run_frozen(w,d,helper('join',ident)); run_frozen(w,d,helper('ack',ident))
                self.assertEqual(full_snapshot(w),before)

    def test_source_rejected_at_real_boundary_restoration_cannot_repair_receipt(self):
        supported(self)
        for row in representative_rows():
          for order in ORDERS:
            with self.subTest(site=row['id'],order=order):
                w=fresh_case(self,row); state=w.countries[TAG]; chosen=next(n for n in native_names() if n!=row['candidate']['queue'])
                fault={}; ident=row['id']
                def before(current,name,tag):
                    if name==helper('source_return',ident):
                        fault['old']=pv(state,chosen); state[chosen]=999
                        fault['boundary']=native_snapshot(current)
                result=dispatch_source(self,w,row,order,before_effect=before)
                d=result['dispatches'][0]; self.assertIn('boundary',fault)
                self.assertNotIn(helper('source_completed',ident),state)
                self.assertEqual(state.get(helper('source_boundary',ident)),ident)
                restore_value(state,chosen,fault['old'])
                stable=native_snapshot(w)
                if order=='source_first': reject_or_inert_body(self,w,d)
                run_frozen(w,d,helper('join',ident)); run_frozen(w,d,helper('ack',ident))
                self.assertEqual(native_snapshot(w),stable)
                self.assertEqual(state[row['candidate']['queue']],row['candidate']['value'])
                self.assertNotIn(helper('source_completed',ident),state)

    def test_callback_and_each_completion_pair_independently_required_at_join(self):
        supported(self)
        for row in representative_rows():
          ident=row['id']
          for name in (*receipt_names(ident),*callback_names(ident)):
            for mode in ('missing','wrong'):
              with self.subTest(site=ident,field=name,mode=mode):
                held=held_before_ack(self,row)
                w=held['world']; d=held['dispatch']; state=w.countries[TAG]
                self.assertIn(name,state,'corrupt only actual executed proof')
                if mode=='missing': state.pop(name)
                else: state[name]=state[name]+7
                before=full_snapshot(w)
                run_frozen(w,d,helper('join',ident)); run_frozen(w,d,helper('ack',ident))
                self.assertEqual(full_snapshot(w),before)
                self.assertEqual(state[row['candidate']['queue']],row['candidate']['value'])
                if name in receipt_names(ident):
                    # An authorized callback can refresh its own tuple, but
                    # cannot repair either actual completion pair.
                    old_receipts={n:pv(state,n) for n in receipt_names(ident)}; native=native_snapshot(w)
                    run_frozen(w,d,helper('callback',ident))
                    self.assertEqual({n:pv(state,n) for n in receipt_names(ident)},old_receipts)
                    self.assertEqual(native_snapshot(w),native)
                    self.assertEqual(state[row['candidate']['queue']],row['candidate']['value'])

    def test_phase_witness_epoch_context_and_expired_lease_reject_prebody_and_preack(self):
        supported(self)
        faults=('inactive','history_only','wrong_phase','terminal','missing_witness',
            'missing_current','zero_current','wrong_current','missing_reservation_epoch',
            'zero_reservation_epoch','wrong_reservation_epoch','missing_candidate_epoch',
            'zero_candidate_epoch','wrong_candidate_epoch','wrong_candidate','missing_context',
            'wrong_context_candidate','wrong_context_epoch','expired_lease')
        for row in representative_rows():
          for boundary in ('prebody','preack'):
            for fault in faults:
              with self.subTest(site=row['id'],boundary=boundary,fault=fault):
                held=held_before_ack(self,row) if boundary=='preack' else source_only(self,row)
                w=held['world']; d=copy.deepcopy(held['dispatch']); corrupt_owner(w,d,row,fault)
                before=native_snapshot(w)
                if boundary=='prebody': reject_or_inert_body(self,w,d)
                else:
                    run_frozen(w,d,helper('join',row['id'])); run_frozen(w,d,helper('ack',row['id']))
                self.assertEqual(native_snapshot(w),before)
                self.assertEqual(w.countries[TAG][row['candidate']['queue']],row['candidate']['value'])

    def test_public_unscoped_wakes_do_not_inherit_frozen_proof_and_body_replay_is_inert(self):
        supported(self)
        for row in representative_rows():
            held=held_before_ack(self,row); w=held['world']; ident=row['id']; before=full_snapshot(w)
            for kind in ('callback','join','ack','source_return','body_return'):
                with w.invocation({}): w.run(helper(kind,ident),TAG)
            self.assertEqual(full_snapshot(w),before)
            state=w.countries[TAG]; dispatch=held['dispatch']; epoch=held['epoch']
            timer,remaining=lease_duration(w)
            native_fields={name:pv(state,name) for name in native_names()}
            # Controlled cooldown-only negative fault, authorized for this
            # replay test. Never age/reset the lease or create owner/proof.
            for checkpoint in ('before_cooldown_fault','before_replay'):
                with self.subTest(phase=row['branch']['journal'],checkpoint=checkpoint):
                    self.assertGreater(remaining,0)
                    self.assertEqual(lease_duration(w),(timer,remaining))
                    self.assertIn(timer,state)
                    self.assertEqual(state.get(PREFIX+'_reservation'),ident)
                    self.assertEqual(state.get(PREFIX+'_epoch'),epoch)
                    self.assertEqual(state.get(PREFIX+'_reservation_epoch'),epoch)
                    self.assertEqual(state.get(helper('candidate_epoch',ident)),epoch)
                    self.assertEqual(dispatch['scope_context'].get(PREFIX+'_dispatch_candidate'),ident)
                    self.assertEqual(dispatch['scope_context'].get(PREFIX+'_dispatch_epoch'),epoch)
                    self.assertGreater(epoch,0)
                    self.assertIn(row['branch']['journal'],w.active[TAG])
                    self.assertEqual(state.get(witness(row)),1)
                    self.assertFalse(w.conditions(field(w.journal_defs[row['branch']['journal']],'complete',[]),TAG))
                    self.assertFalse(w.conditions(field(w.journal_defs[row['branch']['journal']],'fail',[]),TAG))
                    for name,value in zip(receipt_names(ident),(1,epoch,1,epoch)):
                        self.assertEqual(state.get(name),value)
                    self.assertEqual({name:pv(state,name) for name in native_names()},native_fields)
                    if checkpoint=='before_cooldown_fault':
                        self.assertEqual(w.days_until_expiry[TAG].get(COOLDOWN),90)
                        self.assertIn(COOLDOWN,state)
                        expected=full_snapshot(w)
                        expected['native']['country'].pop(COOLDOWN)
                        expected['native']['days'].pop(COOLDOWN)
                        expected['days'].pop(COOLDOWN)
                        state.pop(COOLDOWN); w.days_until_expiry[TAG].pop(COOLDOWN)
                        self.assertEqual(full_snapshot(w),expected,'only shared cooldown value/timer removed')
                    else:
                        self.assertNotIn(COOLDOWN,state)
                        self.assertNotIn(COOLDOWN,w.days_until_expiry[TAG])
            faulttime=full_snapshot(w); replay_effects=[]
            with actual.observe_actual_effect_runs(w,lambda current,name,tag: replay_effects.append(name)):
                reject_or_inert_body(self,w,dispatch)
            self.assertEqual(full_snapshot(w),faulttime,'body receipt alone blocks replay with valid live custody')
            self.assertNotIn('ywc_v03_mark_major_delivered',replay_effects,'full native B/shared cooldown cannot repeat')
            self.assertFalse(any(name.startswith('ywc_tib_choose_') for name in replay_effects),'route fee helper cannot repeat')


def restore_value(state,name,old):
    if old[0]: state[name]=copy.deepcopy(old[1])
    else: state.pop(name,None)


def reject_or_inert_body(testcase,world,dispatch):
    """Only the exact registered false-trigger rejection is an allowed result."""
    try: actual.run_queued_inline_event_immediate(world,dispatch)
    except ValueError as exc:
        testcase.assertEqual(exc.args,(('event trigger false',dispatch['event_id'],TAG),))


class StopAtAck(RuntimeError): pass


def source_only(testcase,row):
    w=fresh_case(testcase,row); result=dispatch_source(testcase,w,row)
    testcase.assertEqual(len(result['dispatches']),1)
    result['dispatch']=result['dispatches'][0]; result['row']=row
    result['epoch']=epoch_of(testcase,result['dispatch'],row['id'])
    return result


def held_before_ack(testcase,row):
    result=source_only(testcase,row); w=result['world']; ident=row['id']
    def stop(current,name,tag):
        result['faulttime']=full_snapshot(current)
        raise StopAtAck('actual full B before ACK')
    with testcase.assertRaisesRegex(StopAtAck,'actual full B before ACK'):
        with actual.observe_actual_owned_ack(w,stop): actual.run_queued_inline_event_immediate(w,result['dispatch'])
    testcase.assertIn('faulttime',result)
    testcase.assertEqual(full_snapshot(w),result['faulttime'],'complete state preserved across pre-ACK exception unwind')
    for name,value in zip(receipt_names(ident),(1,result['epoch'],1,result['epoch'])):
        testcase.assertEqual(w.countries[TAG].get(name),value)
    for name,value in zip(callback_names(ident),(1,ident,result['epoch'],row['candidate']['value'])):
        testcase.assertEqual(w.countries[TAG].get(name),value)
    testcase.assertEqual(w.days_until_expiry[TAG].get(COOLDOWN),90)
    return result


def representative_rows():
    return [next(r for r in all_bindings() if r['branch']['journal']==jid and r['candidate']['kind']=='normal') for jid in phase_ids()]


def lease_duration(world):
    timers={k:v for k,v in world.days_until_expiry[TAG].items() if k.startswith(PREFIX+'_')}
    if len(timers)!=1: raise AssertionError(('exact actual private lease timer',timers))
    name,days=next(iter(timers.items()))
    if not isinstance(days,(int,float)) or days<=0: raise AssertionError(('positive native timer',timers))
    return name,days


def corrupt_owner(world,dispatch,row,fault):
    state=world.countries[TAG]; ident=row['id']; jid=row['branch']['journal']
    if fault in ('inactive','history_only','wrong_phase','terminal'):
        world.active[TAG].remove(jid)
        if fault=='inactive': world.history[TAG].pop(jid,None)
        if fault=='history_only':
            if not any(t==TAG and field(b,'type')==jid for t,b in world.journals):
                raise AssertionError(('history-only requires real authored add history',jid))
            if world.history[TAG].get(jid)!='active':
                raise AssertionError(('history-only checkpoint must retain real active history',jid))
        if fault=='terminal': world.history[TAG][jid]='complete'
        if fault=='wrong_phase':
            other=next(j for j in phase_ids() if j!=jid)
            if other not in world.active[TAG]: world.active[TAG].append(other)
    elif fault=='missing_witness': state.pop(witness(row))
    elif fault=='wrong_candidate': state[PREFIX+'_reservation']=ident+1000
    elif fault=='expired_lease': world.advance_days(lease_duration(world)[1])
    elif fault=='missing_context': dispatch['scope_context']={}
    elif fault=='wrong_context_candidate': dispatch['scope_context'][PREFIX+'_dispatch_candidate']=ident+1000
    elif fault=='wrong_context_epoch': dispatch['scope_context'][PREFIX+'_dispatch_epoch']+=1
    else:
        operation,suffix=fault.split('_',1)
        name={'current':PREFIX+'_epoch','reservation_epoch':PREFIX+'_reservation_epoch',
              'candidate_epoch':helper('candidate_epoch',ident)}[suffix]
        if operation=='missing': state.pop(name)
        elif operation=='zero': state[name]=0
        else: state[name]+=1


def _install_site_cases():
    for row in all_bindings():
        for order in ORDERS:
            def test(self,row=row,order=order):
                supported(self)
                complete_case(self,row,order)
            name=f"test_site_{row['id']:02d}_{order}_{row['branch']['journal'].removeprefix('ywc_je_v03_tib_')}_branch_{row['branch']['branch_index']:02d}"
            test.__name__=name
            test.__doc__=f"Exact source site {row['id']}, {order}, {row['candidate']['kind']}; full actual B and joined selected ACK."
            setattr(TibInlineProvenance,name,test)


_install_site_cases()

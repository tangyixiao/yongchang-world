"""TIB native scalar snapshots, authored priority and private custody faults.

All fault assignments below are declared controlled native queue/marker inputs.
The complete-chain seam omits monthly_review solely to retain those inputs;
every authored sender/prior branch is executed in order. No branch is disabled.
"""
from __future__ import annotations

import copy
import itertools
import unittest

from tests import test_v03_tib_inline_actual_source as actual
from tests.test_v03_tib_inline_provenance import (
    TAG, PREFIX, COOLDOWN, ORDERS, ABSENT, all_bindings, phase_ids, native_names,
    pv, field, walk, pulse, source_node, branch_unit, phase_worlds, fresh_case,
    native_snapshot, full_snapshot, bare_oracle_with_business, native_oracle,
    helper, run_frozen, supported, complete_case, dispatch_source, source_only,
    held_before_ack, representative_rows, receipt_names, callback_names,
    restore_value, reject_or_inert_body, lease_duration, epoch_of,
)

MARKERS=(ABSENT,0,1,2,7)
ELIGIBILITY=tuple(itertools.product((False,True),repeat=3))


def phase_rows(jid):
    return [r for r in all_bindings() if r['branch']['journal']==jid]


def selection_inputs(jid,bits,marker):
    """Order of eligibility bits is normal / 12 / 36; false uses absence."""
    rows=phase_rows(jid)
    normal=next(r for r in rows if r['candidate']['kind']=='normal')
    notice12=next(r for r in rows if r['candidate']['kind']=='notice12')
    notice36=next(r for r in rows if r['candidate']['kind']=='notice36')
    inputs={r['candidate']['queue']:(r['candidate']['value'] if on else ABSENT)
            for r,on in zip((normal,notice12,notice36),bits)}
    marker_name=notice12['candidate']['queue'].removesuffix('_notice_12_event')+'_notice_last_delivered'
    inputs[marker_name]=marker
    # Independent semantic oracle, checked against actual complete source chain.
    if bits[1] and marker!=1: selected=rows[0]
    elif bits[2]: selected=rows[1]
    elif bits[1]: selected=rows[2]
    elif bits[0]: selected=normal
    else: selected=None
    return normal,inputs,selected


def selection_cases():
    for jid,bits,marker,order in itertools.product(phase_ids(),ELIGIBILITY,MARKERS,ORDERS):
        yield {'phase':jid,'bits':bits,'marker':marker,'order':order}


def native_chain(testcase,world,row,order):
    captured=[]; append_states=[]
    def appended(current,dispatch):
        captured.append(copy.deepcopy(dispatch)); append_states.append(native_snapshot(current))
        if order=='body_first': actual.run_queued_inline_event_immediate(current,dispatch)
    with actual.observe_actual_dispatch_append(world,appended):
        world.execute([n for n in pulse(world,row['branch']['journal']) if n[0] in ('if','else_if','else')],TAG)
    if order=='source_first':
        for dispatch in captured: actual.run_queued_inline_event_immediate(world,dispatch)
    testcase.assertLessEqual(len(captured),1)
    return captured,append_states


def assert_selection(testcase,world,dispatches,selected,*,inline):
    testcase.assertEqual([d['event_id'] for d in dispatches],[] if selected is None else [selected['branch']['event']])
    if selected is None: return
    if inline:
        epoch_of(testcase,dispatches[0],selected['id'])
    queue=selected['candidate']['queue']
    testcase.assertNotIn(queue,world.countries[TAG])
    if selected['candidate']['kind'].startswith('notice'):
        marker=queue.rsplit('_notice_',1)[0]+'_notice_last_delivered'
        testcase.assertEqual(world.countries[TAG][marker],1 if selected['candidate']['kind']=='notice12' else 2)


def scalar_expected(name):
    if name.endswith('_notice_last_delivered'): return 1
    return next(r['candidate']['value'] for r in all_bindings() if r['candidate']['queue']==name)


def field_fault_cases():
    """Representative per-phase normal site, all12 fields and representations.

    Selected input must initially be its exact literal to reach a real append;
    all other fields start absent/0/exact/unexpected. Every start changes to a
    different representation. Negative matrix is not claimed at all58 sites.
    """
    for row in representative_rows():
        selected=row['candidate']['queue']
        for name in native_names():
            initial_values=(scalar_expected(name),) if name==selected else (ABSENT,0,scalar_expected(name),777777)
            for initial in initial_values:
                for changed in (ABSENT,0,scalar_expected(name),777777):
                    if initial==changed: continue
                    for boundary in ('before_source','before_body','after_body'):
                        yield row,name,initial,changed,boundary


def mutate(state,name,value):
    if value is ABSENT: state.pop(name,None)
    else: state[name]=value


def assert_guarded_field_fault(testcase,row,name,initial,changed,boundary):
    w=fresh_case(testcase,row,True,{name:initial}); state=w.countries[TAG]
    ident=row['id']; selected=row['candidate']['queue']; boundary_state={}
    def before_source(current,effect,tag):
        if effect==helper('source_return',ident):
            mutate(state,name,changed); boundary_state['fault']=native_snapshot(current)
    if boundary=='before_source':
        result=dispatch_source(testcase,w,row,before_effect=before_source)
        d=result['dispatches'][0]
        testcase.assertIn('fault',boundary_state)
        testcase.assertEqual(native_snapshot(w),boundary_state['fault'],'no rollback at rejected source return')
        testcase.assertNotIn(helper('source_completed',ident),state)
        # Actual pure-owner boundary history survives native mismatch.
        testcase.assertEqual(state.get(helper('source_boundary',ident)),ident)
        mutate(state,name,initial)
        faulttime=native_snapshot(w)
        reject_or_inert_body(testcase,w,d)
        run_frozen(w,d,helper('join',ident)); run_frozen(w,d,helper('ack',ident))
        testcase.assertEqual(native_snapshot(w),faulttime,'restoring values cannot reopen P after source boundary')
        testcase.assertNotIn(helper('source_completed',ident),state)
    else:
        # Isolate the exact selected input before any fault. This helper's
        # source is actually executed, rather than planting a positive proof.
        result=dispatch_source(testcase,w,row); d=result['dispatches'][0]
        testcase.assertEqual(state.get(helper('source_completed',ident)),1)
        if boundary=='before_body':
            mutate(state,name,changed); faulttime=native_snapshot(w)
            reject_or_inert_body(testcase,w,d)
        else:
            def preack(current,effect,tag):
                mutate(state,name,changed); boundary_state['fault']=native_snapshot(current)
            with actual.observe_actual_owned_ack(w,preack): actual.run_queued_inline_event_immediate(w,d)
            testcase.assertIn('fault',boundary_state); faulttime=boundary_state['fault']
            testcase.assertEqual(state.get(helper('body_completed',ident)),1)
            testcase.assertEqual(w.days_until_expiry[TAG].get(COOLDOWN),90)
        testcase.assertEqual(native_snapshot(w),faulttime)
        run_frozen(w,d,helper('join',ident)); run_frozen(w,d,helper('ack',ident))
        testcase.assertEqual(native_snapshot(w),faulttime)
    if name!=selected:
        testcase.assertEqual(state[selected],row['candidate']['value'])
    else:
        # The controlled fault is preserved; ACK may not consume a rewritten
        # selected queue, including zero and unexpected nonzero values.
        testcase.assertEqual(pv(state,selected),(changed is not ABSENT,changed)
            if boundary!='before_source' else (True,initial))


class TibNativeQueueControls(unittest.TestCase):
    def test_480_complete_authored_chain_selection_semantic_cases(self):
        seen=set(); notices=set(); count=0
        for case in selection_cases():
          with self.subTest(**case):
            row,inputs,selected=selection_inputs(case['phase'],case['bits'],case['marker'])
            w=fresh_case(self,row,False,inputs)
            dispatches,append_states=native_chain(self,w,row,case['order'])
            assert_selection(self,w,dispatches,selected,inline=False)
            if selected:
                seen.add(selected['id'])
                if selected['candidate']['kind'].startswith('notice'): notices.add(selected['id'])
                if selected['candidate']['kind'].startswith('notice'):
                    marker=selected['candidate']['queue'].rsplit('_notice_',1)[0]+'_notice_last_delivered'
                    # Expected P derives from EXECUTED native pre, not input marker.
                    self.assertEqual(append_states[0]['country'][marker],1 if selected['candidate']['kind']=='notice12' else 2)
            count+=1
        self.assertEqual(count,480); self.assertEqual(len(notices),18)
        self.assertEqual(len(seen),24,'18 notices plus one representative normal per phase')

    def test_native_zero_and_nonmatching_queue_representations_are_distinct(self):
        count=0
        for jid in phase_ids():
            for bits,marker in itertools.product(ELIGIBILITY,MARKERS):
                row,inputs,_=selection_inputs(jid,bits,marker)
                for name,value in inputs.items():
                    if name.endswith('_notice_last_delivered') or value is not ABSENT: continue
                    for replacement in (0,777777):
                        altered={**inputs,name:replacement}
                        w=fresh_case(self,row,False,altered)
                        before=pv(w.countries[TAG],name)
                        native_chain(self,w,row,'source_first')
                        self.assertEqual(before,(True,replacement))
                        self.assertEqual(pv(w.countries[TAG],name),before,'ineligible sibling scalar remains exact')
                        count+=1
        self.assertEqual(count,720)

    def test_native_presence_value_domain_copy_and_actual_timer_aging(self):
        fields=native_names(); self.assertEqual(len(fields),12)
        for jid in phase_ids():
            row=next(r for r in representative_rows() if r['branch']['journal']==jid)
            for name in fields:
                for value in (ABSENT,0,scalar_expected(name),777777):
                    w=fresh_case(self,row,False,{name:value})
                    clone=actual.copy_actual_world_without_observers(w)
                    self.assertEqual(pv(clone.countries[TAG],name),(value is not ABSENT,value))
                    mutate(clone.countries[TAG],name,888888)
                    self.assertEqual(pv(w.countries[TAG],name),(value is not ABSENT,value))
        w=actual.source_scope_model_control_world()
        w.execute([('set_variable','=',[('name','=','native_clock_control'),('value','=','7'),('days','=','3')])],TAG)
        w.advance_days(2); self.assertEqual(w.days_until_expiry[TAG]['native_clock_control'],1)
        w.advance_days(1); self.assertNotIn('native_clock_control',w.countries[TAG])
        self.assertNotIn('native_clock_control',w.days_until_expiry[TAG])

    def test_declared_case_inventories_are_exact_and_no_event_id_dedup(self):
        cases=list(selection_cases()); self.assertEqual(len(cases),480)
        faults=list(field_fault_cases()); self.assertEqual(len(faults),2430)
        self.assertEqual({r['branch']['journal'] for r,*_ in faults},set(phase_ids()))
        self.assertEqual({name for _,name,*_ in faults},set(native_names()))
        self.assertEqual({boundary for *_,boundary in faults},{'before_source','before_body','after_body'})
        self.assertEqual(len({(c['phase'],c['bits'],c['marker'],c['order']) for c in cases}),480)


class TibInlineQueueSnapshots(unittest.TestCase):
    def test_480_real_inline_complete_chain_selections_match_native_both_orders(self):
        supported(self)
        notices=set(); count=0
        for case in selection_cases():
          with self.subTest(**case):
            row,inputs,selected=selection_inputs(case['phase'],case['bits'],case['marker'])
            result=complete_case(self,row,case['order'],inputs=inputs,chain=True)
            assert_selection(self,result['world'],result['dispatches'],selected,inline=True)
            if selected and selected['candidate']['kind'].startswith('notice'): notices.add(selected['id'])
            if selected: self.assertEqual(result['row']['id'],selected['id'],'exact preferred/fallback source identity')
            count+=1
        self.assertEqual(count,480); self.assertEqual(len(notices),18)

    def test_false_eligibility_zero_and_nonmatching_scalars_match_native_chain(self):
        supported(self)
        count=0
        for jid in phase_ids():
          for bits,marker in itertools.product(ELIGIBILITY,MARKERS):
            row,inputs,selected=selection_inputs(jid,bits,marker)
            for name,value in inputs.items():
                if name.endswith('_notice_last_delivered') or value is not ABSENT: continue
                for replacement in (0,777777):
                  for order in ORDERS:
                    with self.subTest(phase=jid,bits=bits,marker=marker,field=name,value=replacement,order=order):
                        result=complete_case(self,row,order,inputs={**inputs,name:replacement},chain=True)
                        assert_selection(self,result['world'],result['dispatches'],selected,inline=True)
                        self.assertEqual(pv(result['world'].countries[TAG],name),(True,replacement))
                        count+=1
        self.assertEqual(count,1440)

    def test_all12_captured_fields_six_actual_phases_three_boundaries_reject_changes(self):
        supported(self)
        count=0
        for row,name,initial,changed,boundary in field_fault_cases():
            with self.subTest(phase=row['branch']['journal'],field=name,initial=initial,changed=changed,boundary=boundary):
                assert_guarded_field_fault(self,row,name,initial,changed,boundary)
                count+=1
        self.assertEqual(count,2430)

    def test_missing_actual_capture_presence_or_value_rejects_body_and_ack(self):
        supported(self)
        # Capture mapping comes from the real sender AST, never naming guesses.
        for row in representative_rows():
          for boundary in ('prebody','preack'):
            base=source_only(self,row) if boundary=='prebody' else held_before_ack(self,row)
            node=source_node(base['world'],row); pre=node[2][:next(i for i,n in enumerate(node[2]) if n[0]=='trigger_event')]
            mapping=source_capture_mapping(self,pre)
            for native,pair in mapping.items():
                for capture in pair:
                    w=actual.copy_actual_world_without_observers(base['world']); d=base['dispatch']; state=w.countries[TAG]
                    self.assertIn(capture,state); state.pop(capture)
                    before=full_snapshot(w)
                    if boundary=='prebody': reject_or_inert_body(self,w,d)
                    else:
                        run_frozen(w,d,helper('join',row['id'])); run_frozen(w,d,helper('ack',row['id']))
                    self.assertEqual(full_snapshot(w),before,(row['id'],native,capture,boundary))

    def test_fault_before_source_return_exception_preserves_complete_fault_time_state(self):
        supported(self)
        for row in representative_rows():
          for order in ORDERS:
            w=fresh_case(self,row); fault={}
            def before(current,name,tag):
                if name==helper('source_return',row['id']):
                    current.countries[TAG][row['candidate']['queue']]=777777
                    fault['state']=full_snapshot(current)
                    raise RuntimeError('source continuation fault')
            with self.assertRaisesRegex(RuntimeError,'source continuation fault'):
                dispatch_source(self,w,row,order,before_effect=before)
            self.assertEqual(full_snapshot(w),fault['state'])
            self.assertNotIn(helper('source_completed',row['id']),w.countries[TAG])
            self.assertEqual(w.countries[TAG].get(helper('source_boundary',row['id'])),row['id'])
            if order=='body_first': self.assertEqual(w.days_until_expiry[TAG].get(COOLDOWN),90)

    def test_fault_after_full_body_before_ack_preserves_state_and_no_delivery_recheck(self):
        supported(self)
        for row in representative_rows():
            held=held_before_ack(self,row); w=held['world']; d=held['dispatch']; ident=row['id']
            faulttime=held['faulttime']
            self.assertEqual(full_snapshot(w),faulttime,'expected state captured inside actual pre-ACK observer')
            self.assertEqual(w.days_until_expiry[TAG].get(COOLDOWN),90)
            # The exception was at the actual ACK seam, after full B/receipts.
            # Retrying the real join must succeed while B's cooldown exists.
            run_frozen(w,d,helper('join',ident))
            expected=copy.deepcopy(faulttime['native']); expected['country'].pop(row['candidate']['queue'])
            self.assertEqual(native_snapshot(w),expected)
            stable=full_snapshot(w)
            for kind in ('callback','join','ack'):
                run_frozen(w,d,helper(kind,ident))
            self.assertEqual(full_snapshot(w),stable)

    def test_after_successful_ack_exception_retains_committed_queue_transaction(self):
        supported(self)
        for row in representative_rows():
          for order in ORDERS:
            w=fresh_case(self,row); captured=[]; fault={}
            def appended(current,d):
                captured.append(copy.deepcopy(d))
                if order=='body_first': actual.run_queued_inline_event_immediate(current,d)
            def after(current,name,tag):
                fault['state']=full_snapshot(current)
                raise RuntimeError('after committed ACK')
            with self.assertRaisesRegex(RuntimeError,'after committed ACK'):
                with actual.observe_actual_dispatch_append(w,appended),actual.observe_actual_owned_ack(w,lambda *a:None,after):
                    w.run(PREFIX+'_prepare',TAG)
                    w.execute([branch_unit(source_node(w,row))],TAG)
                    if order=='source_first': actual.run_queued_inline_event_immediate(w,captured[0])
            self.assertEqual(full_snapshot(w),fault['state'])
            self.assertNotIn(row['candidate']['queue'],w.countries[TAG])
            self.assertNotIn(PREFIX+'_reservation',w.countries[TAG])
            stable=native_snapshot(w)
            reject_or_inert_body(self,w,captured[0])
            run_frozen(w,captured[0],helper('ack',row['id']))
            self.assertEqual(native_snapshot(w),stable)

    def test_real_lease_expiry_private_cleanup_same_value_new_epoch_rejects_old_context(self):
        supported(self)
        for row in representative_rows():
            old=source_only(self,row); w=old['world']; d=old['dispatch']; ident=row['id']; queue=row['candidate']['queue']
            timer,days=lease_duration(w); old_epoch=old['epoch']
            self.assertIn(timer,w.countries[TAG]); self.assertEqual(w.countries[TAG][queue],row['candidate']['value'])
            w.advance_days(days)
            self.assertNotIn(timer,w.days_until_expiry[TAG])
            # Native timers naturally age. Cleanup comparison begins AFTER
            # elapsed-time effects, not at the original reservation time.
            elapsed=native_snapshot(w)
            w.run(PREFIX+'_prepare',TAG)
            self.assertEqual(native_snapshot(w),elapsed)
            self.assertNotIn(PREFIX+'_reservation',w.countries[TAG])
            self.assertEqual(w.countries[TAG][queue],row['candidate']['value'])
            # Existing scalar work survives; real sender creates a new owner
            # and actual save_scope_value context, without nonce/receipt seeds.
            new=dispatch_source(self,w,row)
            self.assertEqual(len(new['dispatches']),1)
            new_d=new['dispatches'][0]; new_epoch=epoch_of(self,new_d,ident)
            self.assertGreater(new_epoch,old_epoch)
            self.assertNotEqual(new_d['scope_context'],d['scope_context'])
            stable=full_snapshot(w)
            reject_or_inert_body(self,w,d)
            for kind in ('source_return','body_return','callback','join','ack'):
                run_frozen(w,d,helper(kind,ident))
            self.assertEqual(full_snapshot(w),stable,'old frozen context cannot delete or service the new owner')
            actual.run_queued_inline_event_immediate(w,new_d)
            self.assertNotIn(queue,w.countries[TAG]); self.assertNotIn(PREFIX+'_reservation',w.countries[TAG])
            self.assertEqual(w.countries[TAG].get(helper('body_completed_epoch',ident)),new_epoch)
            stable=full_snapshot(w)
            for kind in ('callback','join','ack'): run_frozen(w,new_d,helper(kind,ident))
            self.assertEqual(full_snapshot(w),stable)


def source_capture_mapping(testcase,pre):
    """Use accepted typed A assertion to map actual private capture fields."""
    from tests.test_v03_tib_inline_adapter import _assert_sender_snapshot_capture
    from tools.v03_inline_delivery_adapter import parse_block
    # Lossless serialization of the runtime AST's supported scalar/block
    # grammar; values here are source identifiers/numbers, never free text.
    def script(nodes):
        return ' '.join(k+' '+op+' '+('{ '+script(v)+' }' if isinstance(v,list) else str(v)) for k,op,v in nodes)
    mapping=_assert_sender_snapshot_capture(testcase,parse_block('{ '+script(pre)+' }'),set(native_names()),'actual runtime sender')
    testcase.assertEqual(set(mapping),set(native_names()))
    return mapping

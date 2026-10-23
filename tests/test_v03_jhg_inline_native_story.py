"""Real authored JHG journeys; source interpreter only, never an engine claim."""
from __future__ import annotations
import unittest
from tests.test_v03_jhg_inline_actual_source import (
    TAG, _field, _admit_roots, _run_legacy_and_initialize, _initial_world,
    catalog, run_queued_inline_event_immediate, choose_inline_option,
    source_scope_model_control_world,
)

def _strip_option(option):
    return [n for n in option if n[0] not in ('name','trigger','ai_chance','default_option','custom_tooltip')]

def _options(world,event):
    out={}
    for key,_,body in event:
        if key!='option': continue
        name=_field(body,'name','').rsplit('.',1)[-1]
        gate=_field(body,'trigger',[])
        if not gate or world.conditions(gate,TAG): out[name]=body
    return out

def _contains_named_effect(nodes,prefix):
    for key,_,value in nodes:
        if isinstance(key,str) and key.startswith(prefix): return True
        if isinstance(value,list) and _contains_named_effect(value,prefix): return True
    return False

_NORMAL_ROUTE2={
    'v03_jhg_court_assembly':[
        ('ywc_jhg.1000','audit_contract'),('ywc_jhg.1001','audit_contract'),
        ('ywc_jhg.1002','prince_guarantee'),('ywc_jhg.1003','merchant_pool'),
        ('ywc_jhg.1004','audit_contract'),('ywc_jhg.1005','prince_guarantee'),
        ('ywc_jhg.1006','hold_course'),('ywc_jhg.1007','settle_full')],
    'v03_jhg_convoy_capacity':[
        ('ywc_jhg.1010','shared_escort'),('ywc_jhg.1011','main_lane'),
        ('ywc_jhg.1012','shared_escort'),('ywc_jhg.1013','main_lane'),
        ('ywc_jhg.1014','insurance'),('ywc_jhg.1015','explain_limits'),
        ('ywc_jhg.1016','main_lane'),('ywc_jhg.1017','hold_course'),
        ('ywc_jhg.1018','settle_full')],
    'v03_jhg_tribute_autonomy':[
        ('ywc_jhg.1020','fixed_share'),('ywc_jhg.1021','fixed_share'),
        ('ywc_jhg.1022','project_share'),('ywc_jhg.1023','ambiguity'),
        ('ywc_jhg.1024','hold_course'),('ywc_jhg.1025','settle_full')],
}

_NOTICE_STEMS={
    'v03_jhg_court_assembly':'ywc_jhg_court',
    'v03_jhg_convoy_capacity':'ywc_jhg_convoy',
    'v03_jhg_tribute_autonomy':'ywc_jhg_tribute',
}

def _notice_state(state,slug):
    stem=_NOTICE_STEMS[slug]
    suffixes=('notice_delivery_active','notice_delivery_12','notice_delivery_36',
        '12_notice_delivered','36_notice_delivered','six_months_complete',
        'limited_six_months_complete','notice_pending_event')
    return {suffix:state.get(stem+'_'+suffix) for suffix in suffixes}

def _assert_route2_contract(testcase,r):
    arcs=catalog()['arcs']; expected_journals={j['id'] for arc in arcs for j in arc['journals']}
    testcase.assertEqual(len(r['legacy']),6); testcase.assertEqual(len(r['roots']),3)
    testcase.assertEqual(set(r['roots']),{arc['journals'][0]['id'] for arc in arcs})
    testcase.assertFalse(r['active']); testcase.assertEqual(set(r['finished']),expected_journals)
    testcase.assertEqual(set(r['finished'].values()),{'complete'})
    testcase.assertEqual(r['payments'],{arc['slug']:1000 for arc in arcs})
    testcase.assertEqual(r['final_gold'],17000); testcase.assertEqual(r['raw_base_gold'],20000)
    testcase.assertEqual(r['terminal_caps'],(0,0))
    testcase.assertEqual(set(r['fee_rows']),{arc['slug'] for arc in arcs})
    for slug,rows in r['fee_rows'].items():
        testcase.assertEqual(len(rows),1,(slug,rows))
        testcase.assertEqual(rows[0]['treasury_delta'],-1000,(slug,rows))
    testcase.assertTrue(r['world'].conditions([('gold_reserves','>=','17000')],TAG))
    testcase.assertFalse(r['world'].conditions([('gold_reserves','>','17000')],TAG))
    starts=[row['month'] for row in r['cooldown_trace'] if row.get('days_remaining')==90]
    expired=[row['month'] for row in r['cooldown_trace'] if row.get('expired_naturally')]
    testcase.assertTrue(starts); testcase.assertEqual(len(starts),len(expired))
    testcase.assertEqual([month+3 for month in starts],expired)
    event_rows=[row for row in r['cooldown_trace'] if 'event' in row]
    testcase.assertTrue(event_rows)
    testcase.assertTrue(all(row['days_remaining']>0 for row in event_rows))
    testcase.assertEqual([row['event'] for row in event_rows],[row['event'] for row in r['ledger']])
    testcase.assertTrue(all(last-first>=6 for first,last in r['arc_event_month_spans'].values()))
    testcase.assertEqual(len(r['body_runs']),len(r['ledger']))
    dispatch_rows=[(d['dispatch_id'],d['tag'],d['event_id']) for d in r['dispatches']]
    testcase.assertEqual(len(dispatch_rows),len(set(row[0] for row in dispatch_rows)))
    testcase.assertEqual([row[0] for row in dispatch_rows],list(range(r['dispatch_context_start']+1,r['dispatch_context_start']+1+len(dispatch_rows))))
    testcase.assertEqual(r['body_runs'],dispatch_rows)
    testcase.assertEqual([(row['dispatch_id'],TAG,row['event']) for row in r['ledger']],dispatch_rows)
    testcase.assertTrue(all(row['tag']==TAG for row in r['dispatches']))
    testcase.assertTrue(all(row['event'] in {e['id'] for arc in arcs for e in arc['events']} for row in r['ledger']))
    months=[row['month'] for row in r['ledger']]
    testcase.assertTrue(all(b-a>=3 for a,b in zip(months,months[1:])))
    for slug,expected in _NORMAL_ROUTE2.items():
        rows=[row for row in r['ledger'] if row['arc']==slug]
        endpoint=expected[-1][0]
        extras=[row for row in rows if row['event']==endpoint and row['option']!='settle_full']
        normal=[(row['event'],row['option']) for row in rows if row not in extras]
        testcase.assertEqual(normal,expected,(slug,normal,expected))
        for row in extras:
            facts=row['notice_state']; options=set(row['legal_options'])
            testcase.assertIn(row['option'],('defer','acknowledge_12_notice'))
            testcase.assertIn(row['option'],options)
            if row['option']=='defer':
                testcase.assertFalse(facts.get('notice_delivery_active') and facts.get('notice_delivery_12'),(slug,row))
                testcase.assertFalse(facts.get('six_months_complete'),(slug,row))
                testcase.assertFalse(facts.get('limited_six_months_complete'),(slug,row))
            else:
                testcase.assertTrue(facts.get('notice_delivery_active'),(slug,row))
                testcase.assertTrue(facts.get('notice_delivery_12'),(slug,row))
                testcase.assertTrue(facts.get('12_notice_delivered'),(slug,row))
        settled=next(row for row in rows if row['event']==endpoint and row['option']=='settle_full')
        testcase.assertTrue(settled['notice_state'].get('six_months_complete'),(slug,settled))

def run_native_route(route=2, max_months=180, world=None, evidence=None):
    """Pulse one live JE then drain its actually queued event, before next JE.

    This is an explicit source-driver scheduling choice. It runs authored
    events/options and never seeds a queue, receipt, outcome, or cooldown.
    """
    if world is None:
        world=_initial_world(); legacy=_run_legacy_and_initialize(world); roots=_admit_roots(world)
    else:
        if evidence is None: raise AssertionError('provided generated world requires actual factory evidence')
        legacy=evidence['legacy_events']; roots=evidence['roots']
    arcs=catalog()['arcs']; slugs=[a['slug'] for a in arcs]
    expected_roots={a['journals'][0]['id'] for a in arcs}
    active=set(getattr(world,'active_journals',expected_roots))
    if active!=expected_roots: raise AssertionError(('world root admissions mismatch',active,expected_roots))
    known={j['id'] for a in arcs for j in a['journals']}
    done={}; payments={}; ledger=[]; admission=[]; phases=[]; cooldown_trace=[]; body_runs=[]; observed_dispatches=[]
    dispatch_context_start=len(world.dispatch_contexts)
    state=world.countries[TAG]
    prefix_by_arc={a['slug']:a.get('prefix','ywc_v03_jhg_'+a['slug']) for a in arcs}
    jid_arc={j['id']:a['slug'] for a in arcs for j in a['journals']}
    event_arc={e['id']:a['slug'] for a in arcs for e in a['events']}
    opening={a['slug']:int(a['events'][0]['id'].rsplit('.',1)[1]) for a in arcs}
    endpoint={'v03_jhg_court_assembly':1007,'v03_jhg_convoy_capacity':1018,'v03_jhg_tribute_autonomy':1025}
    route2_open={'v03_jhg_court_assembly':'audit_contract','v03_jhg_convoy_capacity':'shared_escort','v03_jhg_tribute_autonomy':'fixed_share'}
    for month in range(1,max_months+1):
        had_cooldown='ywc_v03_major_event_cooldown' in world.days_until_expiry[TAG]
        world.advance_months(1)
        if had_cooldown and 'ywc_v03_major_event_cooldown' not in world.days_until_expiry[TAG]: cooldown_trace.append({'month':month,'expired_naturally':True})
        for jid in list(active):
            je=world.journal_defs[jid]
            complete=world.conditions(_field(je,'complete',[]),TAG); failed=world.conditions(_field(je,'fail',[]),TAG)
            if complete and failed: raise AssertionError(('JE both complete and failed',jid))
            if complete or failed:
                hook='on_fail' if failed else 'on_complete'
                if _field(je,hook,[]): world.execute(_field(je,hook),TAG)
                world.finish_journal(TAG,{'id':jid}); active.remove(jid); done[jid]='failed' if failed else 'complete'
                phases.append((month,jid,done[jid]))
        for jid in sorted(known-active-set(done)):
            je=world.journal_defs[jid]
            shown=world.conditions(_field(je,'is_shown_when_inactive',[]),TAG)
            possible=world.conditions(_field(je,'possible',[]),TAG)
            if shown and possible:
                world.execute(_field(je,'immediate',[]),TAG); active.add(jid)
                world.journals.append((TAG,[('type','=',jid)])); admission.append(jid)
                break
        for jid in sorted(active):
            je=world.journal_defs[jid]
            if world.conditions(_field(je,'complete',[]),TAG) or world.conditions(_field(je,'fail',[]),TAG): continue
            before=len(world.events); dispatch_start=len(world.dispatch_contexts)
            world.execute(_field(_field(je,'on_monthly_pulse'),'effect'),TAG)
            emitted=list(world.events[before:]); del world.events[before:]
            dispatches=world.dispatch_contexts[dispatch_start:]
            if len(dispatches)!=len(emitted): raise AssertionError(('actual dispatch observation count mismatch',jid,emitted,dispatches))
            for (tag,event_id),dispatch in zip(emitted,dispatches):
                if tag!=TAG: raise AssertionError(('wrong source event tag',tag,event_id))
                if dispatch['tag']!=tag or dispatch['event_id']!=event_id: raise AssertionError(('actual dispatch identity mismatch',dispatch,(tag,event_id)))
                event=world.event_defs[event_id]
                observed_dispatches.append(dict(dispatch))
                run_queued_inline_event_immediate(world,dispatch)
                body_runs.append((dispatch['dispatch_id'],tag,event_id))
                if 'ywc_v03_major_event_cooldown' in world.days_until_expiry[TAG]: cooldown_trace.append({'month':month,'event':event_id,'days_remaining':world.days_until_expiry[TAG]['ywc_v03_major_event_cooldown']})
                choices=_options(world,event); slug=event_arc[event_id]
                number=int(event_id.rsplit('.',1)[1])
                if number==opening[slug]:
                    key=route2_open[slug]
                    if route==1 and slug=='v03_jhg_convoy_capacity': key='main_lane'
                elif number==endpoint[slug]:
                    stem={'v03_jhg_court_assembly':'ywc_jhg_court','v03_jhg_convoy_capacity':'ywc_jhg_convoy','v03_jhg_tribute_autonomy':'ywc_jhg_tribute'}[slug]
                    if state.get(stem+'_limited_six_months_complete'): key='settle_partial'
                    elif state.get(stem+'_six_months_complete'): key='settle_full'
                    elif state.get(stem+'_notice_delivery_active') and state.get(stem+'_notice_delivery_12'): key='acknowledge_12_notice'
                    elif state.get(stem+'_notice_delivery_active') and state.get(stem+'_notice_delivery_36'): key='limited_36_settlement'
                    else: key='defer'
                    if key not in choices: key='defer'
                else:
                    candidates=[x for x,b in choices.items() if x not in ('defer','withdraw')
                                and not _contains_named_effect(_strip_option(b),'ywc_jhg_'+slug.split('_')[2]+'_choose_')]
                    key=candidates[0] if candidates else 'defer'
                if key not in choices: raise AssertionError(('no legal authored option',event_id,key,list(choices)))
                dispatch['selected_option']=key
                dispatch['legal_options']=sorted(choices)
                dispatch['notice_state']=_notice_state(state,slug) if number==endpoint[slug] else None
                before_treasury=world.treasury[TAG]
                world.execute(_strip_option(choices[key]),TAG)
                delta=world.treasury[TAG]-before_treasury
                if delta:
                    payments[slug]=payments.get(slug,0)-delta
                ledger.append({'month':month,'journal':jid,'arc':slug,'event':event_id,'option':key,'treasury_delta':delta,
                    'dispatch_id':dispatch['dispatch_id'],'legal_options':sorted(choices),
                    'notice_state':dispatch['notice_state']})
        if not active and len(done)==len(known): break
    if 'ywc_v03_major_event_cooldown' in world.days_until_expiry[TAG]:
        for offset in range(1,4):
            world.advance_months(1)
            if 'ywc_v03_major_event_cooldown' not in world.days_until_expiry[TAG]:
                cooldown_trace.append({'month':month+offset,'expired_naturally':True})
                break
    spans={}
    for arc in arcs:
        ids={e['id'] for e in arc['events']}
        seen=[row['month'] for row in ledger if row['event'] in ids]
        spans[arc['slug']]=(min(seen),max(seen)) if seen else None
    fee_rows={slug:[row for row in ledger if row['arc']==slug and row['treasury_delta']<0] for slug in slugs}
    return {'world':world,'legacy':legacy,'roots':roots,'active':active,'finished':done,
        'admitted':admission,'payments':payments,'ledger':ledger,'phases':phases,
        'months':month,'final_gold':world.available_gold(TAG),'raw_base_gold':state.get('gold_reserves'),'cooldown_trace':cooldown_trace,
        'partner_watch_possible':world.conditions(_field(world.journal_defs['ywc_je_v03_jhg_convoy_partner_watch'],'possible',[]),TAG),
        'arc_event_month_spans':spans,'fee_rows':fee_rows,'body_runs':body_runs,'dispatches':observed_dispatches,
        'dispatch_context_start':dispatch_context_start,
        'terminal_caps':(state.get('ywc_v03_active_arc_count'),state.get('ywc_v03_visible_task_count'))}

class JhgNativeStory(unittest.TestCase):
    def test_authored_fee_option_is_idempotent_and_cash_gate_uses_accumulated_treasury(self):
        from tests.test_v03_jhg_inline_actual_source import run_inline_event_immediate, choose_inline_option
        w=_initial_world(); _run_legacy_and_initialize(w); _admit_roots(w)
        event_id='ywc_jhg.1000'
        run_inline_event_immediate(w,event_id)
        before=w.available_gold(TAG)
        choose_inline_option(w,event_id,'audit_contract')
        after_first=w.available_gold(TAG)
        choose_inline_option(w,event_id,'audit_contract')
        after_second=w.available_gold(TAG)
        self.assertEqual((before,after_first,after_second),(20000,19000,19000))
        self.assertTrue(w.conditions([('gold_reserves','>=','19000')],TAG))
        self.assertFalse(w.conditions([('gold_reserves','>','19000')],TAG))
    def test_documented_scope_value_copy_guards_and_if_chain_are_modelled(self):
        w=source_scope_model_control_world(); tag=TAG
        w.countries[tag]['ywc_v03_jhg_reservation_epoch']=7
        snippet=__import__('tests.clausewitz_harness',fromlist=['parse']).parse('''
            if = { limit = { always = yes } save_scope_value_as = { name = ywc_v03_jhg_inline_dispatch_candidate value = 23 } }
            else_if = { limit = { always = yes } save_scope_value_as = { name = ywc_v03_jhg_inline_dispatch_candidate value = 99 } }
            save_scope_value_as = { name = ywc_v03_jhg_inline_dispatch_epoch value = 7 }
            trigger_event = { id = ywc_jhg.1000 }
        ''')
        w.execute(snippet,tag)
        dispatch=w.dispatch_contexts[-1]
        self.assertEqual(dispatch['scope_context'],{'ywc_v03_jhg_inline_dispatch_candidate':23.0,'ywc_v03_jhg_inline_dispatch_epoch':7.0})
        guard=__import__('tests.clausewitz_harness',fromlist=['parse']).parse('''
            AND = { exists = scope:ywc_v03_jhg_inline_dispatch_candidate scope:ywc_v03_jhg_inline_dispatch_candidate > 0 scope:ywc_v03_jhg_inline_dispatch_candidate = 23 scope:ywc_v03_jhg_inline_dispatch_epoch > 0 scope:ywc_v03_jhg_inline_dispatch_epoch = 7 }
        ''')
        self.assertTrue(w.conditions(guard,tag))
        self.assertTrue(w.conditions([('scope:ywc_v03_jhg_inline_dispatch_epoch','=','var:ywc_v03_jhg_reservation_epoch')],tag))
        self.assertFalse(w.conditions([('scope:ywc_v03_jhg_inline_dispatch_epoch','!=','var:ywc_v03_jhg_reservation_epoch')],tag))
        with w.invocation({'flag':True}):
            self.assertTrue(w.conditions([('exists','=','scope:flag'),('scope:flag','=','yes')],tag))
            self.assertFalse(w.conditions([('scope:flag','=','no')],tag))
            with self.assertRaises(AssertionError): w.conditions([('scope:flag','=','1')],tag)
        with w.invocation({}): self.assertFalse(w.conditions(guard,tag))
        with w.invocation({'epoch':5}):
            with self.assertRaises(AssertionError): w.conditions([('exists','!=','scope:absent')],tag)
            with self.assertRaises(AssertionError): w.conditions([('scope:absent','~','1')],tag)
            with self.assertRaises(AssertionError): w.conditions([('scope:epoch','=','scope:missing')],tag)
            for malformed in ('yes','NaN','var:missing_country_value'):
                with self.subTest(missing_lhs_rhs=malformed),self.assertRaises(AssertionError): w.conditions([('scope:absent','>','yes' if malformed=='yes' else ('NaN' if malformed=='NaN' else malformed))],tag)
            with self.assertRaises(AssertionError): w.conditions([('scope:absent','=','var:missing_country_value')],tag)
        with self.assertRaises(AssertionError): w.execute([('made_up_scope_command','=','yes')],tag)
        with self.assertRaises(AssertionError): w.execute([('save_scope_value_as','=',[('name','=','x'),('name','=','y'),('value','=','1')])],tag)
        with self.assertRaises(AssertionError): w.execute([('save_scope_value_as','?=',[('name','=','x'),('value','=','1')])],tag)
        with w.invocation({'token':2}):
            with self.assertRaises(AssertionError): w.conditions([('scope:token','~','1')],tag)
        with self.assertRaises(AssertionError): w.conditions([('made_up_optional','?=','yes')],tag)
        with self.assertRaises(AssertionError): w.conditions([('ig:ig_landowners','?=',[('is_powerful','=','yes'),('made_up','=','yes')])],tag)
        with self.assertRaises(AssertionError): w.conditions([('ig:ig_landowners','?=',[('is_powerful','!=','yes')])],tag)
        self.assertTrue(w.conditions([('ig:ig_landowners','?=',[('is_powerful','=','yes')])],tag))
        self.assertTrue(w.conditions([('gold_reserves','>=',[('value','=','9000'),('multiply','=','2')])],tag))
        bad_cash_blocks=(
            [('value','=','1'),('made_up','=','2')],
            [('value','=','1'),('value','=','2')],
            [('value','!=','1')],
            [('value','=','NaN')],
            [('value','=','1'),('multiply','=','inf')],
        )
        for fields in bad_cash_blocks:
            with self.subTest(fields=fields),self.assertRaises(AssertionError): w.conditions([('gold_reserves','>=',fields)],tag)
        with self.assertRaises(AssertionError): w.conditions([('gold_reserves','~','1')],tag)

    def test_dispatch_context_copy_helper_recursion_and_freshness_are_isolated(self):
        parser=__import__('tests.clausewitz_harness',fromlist=['parse']).parse
        w=source_scope_model_control_world(); tag=TAG
        w.countries[tag]['candidate_value']=4
        w.effects['b1_scope_helper_control']=parser('''save_scope_value_as = { name = candidate value = var:candidate_value } trigger_event = { id = ywc_jhg.1000 }''')
        w.effects['b1_scope_outer_control']=parser('''if = { limit = { always = yes } b1_scope_helper_control = yes }''')
        w.run('b1_scope_outer_control',tag)
        first=w.dispatch_contexts[-1]
        w.countries[tag]['candidate_value']=9
        w.effects['b1_scope_helper_control']=parser('''save_scope_value_as = { name = candidate value = var:candidate_value } trigger_event = { id = ywc_jhg.1000 }''')
        w.run('b1_scope_outer_control',tag)
        second=w.dispatch_contexts[-1]
        self.assertEqual((first['scope_context']['candidate'],second['scope_context']['candidate']),(4.0,9.0))
        first['scope_context']['candidate']=77
        self.assertEqual(second['scope_context']['candidate'],9.0)
        with w.invocation({'prior':77}):
            with self.assertRaises(AssertionError):
                with w.invocation({'candidate':12}): w.execute([('made_up_scope_command','=','yes')],tag)
            self.assertEqual(w.scope_context,{'prior':77})
        before=len(w.dispatch_contexts)
        w.execute(parser('trigger_event = { id = ywc_jhg.1000 }'),tag)
        self.assertEqual(w.dispatch_contexts[before]['scope_context'],{})
        w.event_defs['b1.scope.guard']=[('trigger','=',parser('exists = scope:candidate')),('immediate','=',[])]
        with self.assertRaises(ValueError):
            with w.invocation({'candidate':12}):
                from tests.test_v03_jhg_inline_actual_source import run_inline_event_immediate
                run_inline_event_immediate(w,'b1.scope.guard')
        w.event_defs['b1.scope.guard'][1]=('immediate','=',parser('set_variable = { name = b1_scope_body_ran value = yes }'))
        from tests.test_v03_jhg_inline_actual_source import run_queued_inline_event_immediate
        run_queued_inline_event_immediate(w,{'tag':tag,'event_id':'b1.scope.guard','scope_context':{'candidate':12}})
        self.assertTrue(w.countries[tag]['b1_scope_body_ran'])
        with self.assertRaises(AssertionError):
            run_queued_inline_event_immediate(w,{'tag':'OTHER','event_id':'b1.scope.guard','scope_context':{'candidate':12}})
    def test_native_route2_has_real_history_roots_fees_and_terminal_caps(self):
        r=run_native_route(2)
        _assert_route2_contract(self,r)
    def test_route1_source_gate_is_not_rewritten_to_success(self):
        r=run_native_route(1)
        self.assertEqual(r['world'].countries[TAG]['ywc_jhg_convoy_route'],1)
        self.assertFalse(r['partner_watch_possible'])
    def test_registered_public_gate_runs_the_full_generated_story(self):
        from tests.test_v03_jhg_inline_actual_source import actual_jhg_inline_world
        generated_world,evidence=actual_jhg_inline_world()
        self.assertIn('events',generated_world.inline_registries)
        result=run_native_route(2,world=generated_world,evidence=evidence)
        _assert_route2_contract(self,result)

if __name__=='__main__': unittest.main()
